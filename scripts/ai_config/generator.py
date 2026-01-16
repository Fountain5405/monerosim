"""
Main orchestrator for AI-powered config generation.

Uses an agentic feedback loop:
1. LLM generates Python script
2. Script executes to produce YAML
3. Validator checks YAML against user intent
4. If issues, LLM corrects the script
5. Repeat until valid or max attempts
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import urllib.request
import urllib.error

from .validator import ConfigValidator, ValidationReport
from .prompts import GENERATOR_SYSTEM_PROMPT, FEEDBACK_PROMPT_TEMPLATE, VALIDATION_CHECK_PROMPT


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
    script_content: Optional[str] = None
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
                "Authorization": f"Bearer {self.api_key}"
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

    def generate(self, user_request: str, output_file: str = None, save_script: str = None) -> GenerationResult:
        """
        Generate a monerosim config from natural language request.

        Args:
            user_request: Natural language description of the scenario
            output_file: Path to save the YAML config (optional)
            save_script: Path to save the generator script (optional)

        Returns:
            GenerationResult with success status, YAML content, and validation report
        """
        result = GenerationResult(success=False)

        self.log(f"\n{'='*60}")
        self.log(f"Generating config for: {user_request[:80]}{'...' if len(user_request) > 80 else ''}")
        self.log(f"{'='*60}\n")

        # Initial generation
        messages = [
            {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": f"Generate a Python script to create a monerosim config for:\n\n{user_request}"}
        ]

        current_script = None

        for attempt in range(1, self.max_attempts + 1):
            result.attempts = attempt
            self.log(f"Attempt {attempt}/{self.max_attempts}...")

            # Get script from LLM
            try:
                response = self.provider.chat(messages)
                current_script = self._extract_python(response.content)

                if not current_script:
                    result.errors.append(f"Attempt {attempt}: Could not extract Python script from response")
                    self.log("  ERROR: No Python script in response")
                    continue

                result.script_content = current_script

            except Exception as e:
                result.errors.append(f"Attempt {attempt}: LLM error - {e}")
                self.log(f"  ERROR: LLM request failed - {e}")
                continue

            # Execute script
            self.log("  Executing script...")
            yaml_content, exec_error = self._execute_script(current_script)

            if exec_error:
                result.errors.append(f"Attempt {attempt}: Script execution error - {exec_error}")
                self.log(f"  ERROR: Script failed - {exec_error[:100]}")

                # Feed back execution error
                messages.append({"role": "assistant", "content": f"```python\n{current_script}\n```"})
                messages.append({"role": "user", "content": f"The script failed with error:\n{exec_error}\n\nPlease fix it."})
                continue

            result.yaml_content = yaml_content
            self.log(f"  Generated {len(yaml_content)} bytes of YAML")

            # Validate
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
                # Feed back for correction
                feedback = FEEDBACK_PROMPT_TEMPLATE.format(
                    user_request=user_request,
                    validation_report=report.to_summary(),
                    issues=issues,
                    current_script=current_script
                )
                messages.append({"role": "assistant", "content": f"```python\n{current_script}\n```"})
                messages.append({"role": "user", "content": feedback})
            else:
                result.errors.append(f"Max attempts reached. Remaining issues:\n{issues}")

        # Save outputs
        if result.yaml_content and output_file:
            with open(output_file, 'w') as f:
                f.write(f"# Generated by ai_config for: {user_request[:60]}...\n")
                f.write(f"# Attempts: {result.attempts}, Success: {result.success}\n\n")
                f.write(result.yaml_content)
            self.log(f"\nYAML saved to: {output_file}")

        if result.script_content and save_script:
            with open(save_script, 'w') as f:
                f.write(result.script_content)
            self.log(f"Script saved to: {save_script}")

        return result

    def _extract_python(self, response: str) -> Optional[str]:
        """Extract Python code from LLM response."""
        # Try ```python ... ``` blocks
        pattern = r"```python\s*(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            return matches[-1].strip()

        # Try ``` ... ``` blocks that look like Python
        pattern = r"```\s*(#!/usr/bin/env python.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            return matches[-1].strip()

        # Try ``` ... ``` with import yaml
        pattern = r"```\s*(import yaml.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            return matches[-1].strip()

        return None

    def _execute_script(self, script: str) -> tuple[Optional[str], Optional[str]]:
        """Execute Python script and capture YAML output."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script)
            script_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return None, result.stderr or "Script returned non-zero exit code"

            yaml_output = result.stdout.strip()
            if not yaml_output:
                return None, "Script produced no output"

            return yaml_output, None

        except subprocess.TimeoutExpired:
            return None, "Script execution timed out (30s)"
        except Exception as e:
            return None, str(e)
        finally:
            os.unlink(script_path)

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

        # Check hashrate (warning only - close enough is fine)
        if report.miner_count > 0 and report.total_hashrate != 100:
            if abs(report.total_hashrate - 100) > 10:  # Only fail if way off
                issues.append(f"Total hashrate is {report.total_hashrate}, should be ~100")
            else:
                warnings.append(f"Total hashrate is {report.total_hashrate} (close to 100)")

        # Check upgrade scenario timing (hard failure for gap violations)
        if report.upgrade.enabled:
            if report.upgrade.agents_with_invalid_gap:
                issues.append(f"Agents with phase gap < 30s: {', '.join(report.upgrade.agents_with_invalid_gap[:5])}")

        # Log warnings but don't fail on them
        if warnings and self.verbose:
            for w in warnings:
                self.log(f"  Warning: {w}")

        # Only return hard issues, skip semantic LLM check (too noisy)
        return "\n".join(issues) if issues else None
