"""
Main orchestrator for AI-powered config generation.

Uses an agentic feedback loop:
1. LLM generates scenario.yaml (compact format)
2. Scenario parser expands to full monerosim.yaml
3. Validator checks expanded YAML against user intent
4. If issues, LLM corrects the scenario
5. Repeat until valid or max attempts
"""

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import urllib.request
import urllib.error

from .validator import ConfigValidator, ValidationReport
from .scenario_prompts import SCENARIO_SYSTEM_PROMPT, SCENARIO_FEEDBACK_TEMPLATE
from ..scenario_parser import parse_scenario, expand_scenario
import yaml as yaml_lib


def build_metadata_from_report(report: 'ValidationReport', user_request: str) -> Dict[str, Any]:
    """Build machine-parseable metadata from validation report.

    This creates the same metadata structure as generate_config.py for consistency,
    allowing analysis tools to parse configs from either generator.

    Args:
        report: ValidationReport from the validator
        user_request: Original user request string

    Returns:
        Metadata dictionary matching generate_config.py format
    """
    from collections import OrderedDict

    # Determine scenario type
    scenario = "upgrade" if report.upgrade.enabled else "default"

    metadata = OrderedDict([
        ("scenario", scenario),
        ("generator", "ai_config"),
        ("version", "1.0"),
        ("user_request", user_request[:200]),  # Truncate long requests
    ])

    # Agent counts
    metadata["agents"] = OrderedDict([
        ("total", report.miner_count + report.user_count + report.spy_count),
        ("miners", report.miner_count),
        ("users", report.user_count),
        ("spy_nodes", report.spy_count),
    ])

    # Core timing (all in seconds for easy parsing)
    metadata["timing"] = OrderedDict([
        ("duration_s", report.stop_time_s),
        ("bootstrap_end_s", report.bootstrap_end_time_s),
    ])

    # Add user timing if available
    if report.user_count > 0:
        start_min, start_max = report.user_start_time_range
        act_min, act_max = report.activity_start_time_range
        metadata["timing"]["user_spawn_start_s"] = start_min
        metadata["timing"]["user_spawn_end_s"] = start_max
        if act_min > 0:
            metadata["timing"]["activity_start_s"] = act_min

    # Upgrade-specific metadata
    if report.upgrade.enabled:
        upgrade_meta = OrderedDict([
            ("binary_v1", report.upgrade.v1_binary or "monerod"),
            ("binary_v2", report.upgrade.v2_binary or "monerod"),
        ])
        if report.upgrade.upgrade_start_s is not None:
            upgrade_meta["start_s"] = report.upgrade.upgrade_start_s
        if report.upgrade.upgrade_end_s is not None:
            upgrade_meta["complete_s"] = report.upgrade.upgrade_end_s
        if report.upgrade.avg_stagger_s is not None:
            upgrade_meta["stagger_s"] = int(report.upgrade.avg_stagger_s)
        if report.upgrade.min_gap_s is not None:
            upgrade_meta["phase_gap_s"] = report.upgrade.min_gap_s
        upgrade_meta["agents_with_phases"] = report.upgrade.agents_with_phases
        metadata["upgrade"] = upgrade_meta

    # Spy node info
    if report.spy_count > 0 and report.spy_connections:
        spy_meta = OrderedDict()
        for agent_id, (out_p, in_p) in report.spy_connections.items():
            spy_meta[agent_id] = OrderedDict([
                ("out_peers", out_p),
                ("in_peers", in_p),
            ])
        metadata["spy_nodes"] = spy_meta

    # Settings
    settings = OrderedDict([
        ("network", report.network_type or "default"),
        ("peer_mode", report.peer_mode or "Dynamic"),
    ])
    if report.simulation_seed:
        settings["seed"] = report.simulation_seed
    metadata["settings"] = settings

    return metadata


def _convert_ordered_dict(obj: Any) -> Any:
    """Recursively convert OrderedDict to regular dict for clean YAML output."""
    from collections import OrderedDict
    if isinstance(obj, OrderedDict):
        return {k: _convert_ordered_dict(v) for k, v in obj.items()}
    elif isinstance(obj, dict):
        return {k: _convert_ordered_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_ordered_dict(item) for item in obj]
    return obj


def inject_metadata_into_yaml(yaml_content: str, metadata: Dict[str, Any]) -> str:
    """Inject metadata section at the beginning of YAML content.

    Args:
        yaml_content: Original YAML string
        metadata: Metadata dictionary to inject

    Returns:
        YAML string with metadata section prepended
    """
    # Convert OrderedDict to regular dict for clean YAML output
    clean_metadata = _convert_ordered_dict(metadata)

    # Convert metadata to YAML
    metadata_yaml = yaml_lib.dump(
        {"metadata": clean_metadata},
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True
    )

    # Combine metadata with original content
    return metadata_yaml + "\n" + yaml_content


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None


@dataclass
class GenerationResult:
    """Result of the config generation process."""
    success: bool
    yaml_content: Optional[str] = None
    scenario_content: Optional[str] = None  # Compact scenario.yaml
    validation_report: Optional[ValidationReport] = None
    attempts: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class LLMProvider:
    """OpenAI-compatible LLM provider."""

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None):
        self.model = model or os.environ.get('AI_CONFIG_MODEL', 'gpt-4o-mini')
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY', '')
        self.base_url = base_url or os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> LLMResponse:
        """Send a chat completion request."""
        data = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 8192,
        }).encode()

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "monerosim-ai-config/1.0"
            }
        )

        with urllib.request.urlopen(req, timeout=600) as resp:
            result = json.loads(resp.read().decode())
            return LLMResponse(
                content=result["choices"][0]["message"]["content"],
                model=self.model,
                usage=result.get("usage")
            )


class ConfigGenerator:
    """Generates monerosim configs using LLM with feedback loop."""

    def __init__(self, provider: LLMProvider = None, max_attempts: int = 3, verbose: bool = True):
        self.provider = provider or LLMProvider()
        self.validator = ConfigValidator()
        self.max_attempts = max_attempts
        self.verbose = verbose

    def log(self, msg: str):
        """Print message if verbose."""
        if self.verbose:
            print(msg, file=sys.stderr)

    def generate(self, user_request: str, output_file: str = None, save_scenario: str = None) -> GenerationResult:
        """
        Generate a monerosim config from natural language request.

        Uses a two-stage process:
        1. LLM generates compact scenario.yaml
        2. Scenario parser expands to full monerosim.yaml

        Args:
            user_request: Natural language description of the scenario
            output_file: Path to save the expanded YAML config (optional)
            save_scenario: Path to save the compact scenario.yaml (optional)

        Returns:
            GenerationResult with success status, YAML content, and validation report
        """
        result = GenerationResult(success=False)

        self.log(f"\n{'='*60}")
        self.log(f"Generating config for: {user_request[:80]}{'...' if len(user_request) > 80 else ''}")
        self.log(f"{'='*60}\n")

        # Initial generation - ask for scenario.yaml directly
        messages = [
            {"role": "system", "content": SCENARIO_SYSTEM_PROMPT},
            {"role": "user", "content": user_request}
        ]

        current_scenario = None

        for attempt in range(1, self.max_attempts + 1):
            result.attempts = attempt
            self.log(f"Attempt {attempt}/{self.max_attempts}...")

            # Get scenario from LLM
            try:
                response = self.provider.chat(messages)
                current_scenario = self._extract_yaml(response.content)

                if not current_scenario:
                    result.errors.append(f"Attempt {attempt}: Could not extract YAML from response")
                    self.log("  ERROR: No YAML in response")
                    continue

                result.scenario_content = current_scenario

            except Exception as e:
                result.errors.append(f"Attempt {attempt}: LLM error - {e}")
                self.log(f"  ERROR: LLM request failed - {e}")
                continue

            # Parse and expand scenario
            self.log("  Expanding scenario...")
            yaml_content, parse_error = self._expand_scenario(current_scenario)

            if parse_error:
                result.errors.append(f"Attempt {attempt}: Scenario parse error - {parse_error}")
                self.log(f"  ERROR: Parse failed - {parse_error[:100]}")

                # Feed back parse error
                messages.append({"role": "assistant", "content": current_scenario})
                messages.append({"role": "user", "content": f"The scenario has syntax errors:\n{parse_error}\n\nPlease fix it and output only the corrected YAML."})
                continue

            result.yaml_content = yaml_content
            self.log(f"  Expanded to {len(yaml_content)} bytes of YAML")

            # Validate expanded config
            self.log("  Validating...")
            try:
                report = self.validator.validate_yaml(yaml_content)
                result.validation_report = report
            except Exception as e:
                result.errors.append(f"Attempt {attempt}: Validation error - {e}")
                self.log(f"  ERROR: Validation failed - {e}")
                continue

            # Check if it matches user request
            issues = self._check_against_request(user_request, report)

            if not issues:
                self.log("  VALID - Config matches request!")
                result.success = True
                break

            self.log(f"  Issues found: {len(issues.splitlines())} problems")

            if attempt < self.max_attempts:
                # Feed back for correction using scenario feedback template
                feedback = SCENARIO_FEEDBACK_TEMPLATE.format(
                    user_request=user_request,
                    issues=issues,
                    current_scenario=current_scenario
                )
                messages.append({"role": "assistant", "content": current_scenario})
                messages.append({"role": "user", "content": feedback})
            else:
                result.errors.append(f"Max attempts reached. Remaining issues:\n{issues}")

        # Save outputs
        if result.yaml_content and output_file:
            # Build and inject metadata if we have a validation report
            final_yaml = result.yaml_content
            if result.validation_report:
                try:
                    metadata = build_metadata_from_report(result.validation_report, user_request)
                    final_yaml = inject_metadata_into_yaml(result.yaml_content, metadata)
                except Exception as e:
                    self.log(f"  Warning: Could not inject metadata: {e}")

            with open(output_file, 'w') as f:
                f.write(f"# Generated by ai_config for: {user_request[:60]}...\n")
                f.write(f"# Attempts: {result.attempts}, Success: {result.success}\n\n")
                f.write(final_yaml)
            self.log(f"\nYAML saved to: {output_file}")

        if result.scenario_content and save_scenario:
            with open(save_scenario, 'w') as f:
                f.write(f"# Scenario generated for: {user_request[:60]}...\n\n")
                f.write(result.scenario_content)
            self.log(f"Scenario saved to: {save_scenario}")

        return result

    def _extract_yaml(self, response: str) -> Optional[str]:
        """Extract YAML content from LLM response."""
        # Try ```yaml ... ``` blocks (most common)
        pattern = r"```yaml\s*(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            return matches[-1].strip()

        # Try ```yml ... ``` blocks
        pattern = r"```yml\s*(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            return matches[-1].strip()

        # Try any ``` ... ``` block that contains 'general:' and 'agents:'
        pattern = r"```\s*(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)
        for match in reversed(matches):  # Check from last to first
            if 'general:' in match and 'agents:' in match:
                return match.strip()

        # If no code blocks, check if the response itself looks like YAML
        # (starts with 'general:' after any leading whitespace/comments)
        lines = response.strip().split('\n')
        yaml_start = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('general:'):
                yaml_start = i
                break
            # Skip comment lines and empty lines at the start
            if stripped and not stripped.startswith('#'):
                break

        if yaml_start is not None:
            yaml_content = '\n'.join(lines[yaml_start:]).strip()
            if 'agents:' in yaml_content:
                return yaml_content

        return None

    def _expand_scenario(self, scenario_yaml: str) -> tuple[Optional[str], Optional[str]]:
        """Parse and expand scenario.yaml to full monerosim.yaml."""
        from collections import OrderedDict

        try:
            # Parse the scenario
            scenario = parse_scenario(scenario_yaml)

            # Extract seed from general settings
            seed = scenario.general.get('simulation_seed', 12345)

            # Expand to full config
            config = expand_scenario(scenario, seed=seed)

            # Convert OrderedDicts to regular dicts for clean YAML output
            def to_plain_dict(obj):
                if isinstance(obj, OrderedDict):
                    return {k: to_plain_dict(v) for k, v in obj.items()}
                elif isinstance(obj, dict):
                    return {k: to_plain_dict(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [to_plain_dict(i) for i in obj]
                return obj

            plain_config = to_plain_dict(config)

            # Serialize to YAML
            yaml_output = yaml_lib.dump(
                plain_config,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True
            )

            return yaml_output, None

        except yaml_lib.YAMLError as e:
            return None, f"YAML syntax error: {e}"
        except ValueError as e:
            return None, f"Scenario validation error: {e}"
        except Exception as e:
            return None, f"Expansion error: {e}"

    def _check_against_request(self, user_request: str, report: ValidationReport) -> Optional[str]:
        """Check if validation report matches user request. Returns issues or None if valid."""
        issues = []
        warnings = []

        # Check for validation errors (hard failures)
        if report.errors:
            issues.extend(report.errors)

        # Check required components (hard failure)
        if report.user_count > 0 and not report.has_distributor:
            issues.append("Missing miner-distributor (required when users exist)")

        # Check hashrate for initial miners only (those starting in first 60s)
        # Late-joining miners are valid and can add more hashrate
        if report.miner_count > 0:
            initial_hashrate = sum(
                a.hashrate for a in report.agents
                if a.agent_type == "miner" and a.hashrate and a.start_time_s < 60
            )
            if initial_hashrate > 0 and initial_hashrate != 100:
                if abs(initial_hashrate - 100) > 10:  # Only flag if way off
                    issues.append(f"Initial miners hashrate is {initial_hashrate}, should be ~100")
                else:
                    warnings.append(f"Initial miners hashrate is {initial_hashrate} (close to 100)")

        # Check upgrade scenario timing (hard failure for gap violations)
        if report.upgrade.enabled:
            if report.upgrade.agents_with_invalid_gap:
                issues.append(f"Agents with phase gap < 30s: {', '.join(report.upgrade.agents_with_invalid_gap[:5])}")

            # Check that simulation doesn't end before upgrade starts/completes
            if report.upgrade.upgrade_start_s is not None:
                if report.stop_time_s < report.upgrade.upgrade_start_s:
                    issues.append(
                        f"CRITICAL: stop_time ({report.stop_time_s}s) is before upgrade starts ({report.upgrade.upgrade_start_s}s). "
                        f"Simulation would end before any upgrades happen! Increase stop_time to at least {report.upgrade.upgrade_start_s + 7200}s"
                    )
                elif report.upgrade.upgrade_end_s and report.stop_time_s < report.upgrade.upgrade_end_s:
                    issues.append(
                        f"stop_time ({report.stop_time_s}s) is before upgrade completes ({report.upgrade.upgrade_end_s}s). "
                        f"Increase stop_time to at least {report.upgrade.upgrade_end_s + 7200}s for post-upgrade observation"
                    )

        # Log warnings but don't fail on them
        if warnings and self.verbose:
            for w in warnings:
                self.log(f"  Warning: {w}")

        # Only return hard issues, skip semantic LLM check (too noisy)
        return "\n".join(issues) if issues else None
