#!/usr/bin/env python3
"""
Interactive mode for AI config generator.
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional, Callable

from .validator import seconds_to_human

# Try to import readline for better input handling
try:
    import readline
    HAS_READLINE = True
except ImportError:
    HAS_READLINE = False


# ANSI color codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'

    @classmethod
    def disable(cls):
        """Disable colors for non-TTY output."""
        cls.RESET = ''
        cls.BOLD = ''
        cls.DIM = ''
        cls.RED = ''
        cls.GREEN = ''
        cls.YELLOW = ''
        cls.BLUE = ''
        cls.MAGENTA = ''
        cls.CYAN = ''


# Disable colors if not a TTY
if not sys.stdout.isatty():
    Colors.disable()


def clear_line():
    """Clear the current line."""
    if sys.stdout.isatty():
        sys.stdout.write('\r\033[K')
        sys.stdout.flush()


def print_header():
    """Print the application header."""
    c = Colors
    print()
    print(f"{c.CYAN}{c.BOLD}{'─' * 60}{c.RESET}")
    print(f"{c.CYAN}{c.BOLD}  MoneroSim AI Config Generator{c.RESET}")
    print(f"{c.CYAN}{c.BOLD}{'─' * 60}{c.RESET}")
    print()


def print_examples():
    """Print example scenarios."""
    c = Colors
    print(f"{c.DIM}Examples:{c.RESET}")
    examples = [
        '"5 miners, 50 users, running for 8 hours"',
        '"Network upgrade: nodes start on v1, upgrade to v2 at 7h"',
        '"Spy node study with 3 spy nodes monitoring 100 users"',
        '"Large scale test with 200 nodes, batched bootstrap"',
    ]
    for ex in examples:
        print(f"  {c.DIM}•{c.RESET} {ex}")
    print()


def get_user_input(prompt: str, default: str = "") -> str:
    """Get input from user with optional default."""
    c = Colors
    if default:
        prompt = f"{prompt} [{c.DIM}{default}{c.RESET}]: "
    else:
        prompt = f"{prompt}: "

    try:
        value = input(prompt).strip()
        return value if value else default
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def get_multiline_input(prompt: str) -> str:
    """Get potentially multi-line input, ending with empty line or Enter."""
    c = Colors
    print(f"{prompt}")
    print(f"{c.DIM}(Press Enter twice or Ctrl+D when done){c.RESET}")
    print()

    lines = []
    try:
        while True:
            line = input("  > ")
            if not line and lines:  # Empty line after content = done
                break
            if line:
                lines.append(line)
    except EOFError:
        pass
    except KeyboardInterrupt:
        print()
        return ""

    return " ".join(lines)


class ProgressIndicator:
    """Simple progress indicator for generation steps."""

    def __init__(self):
        self.steps = []
        self.current_step = 0

    def add_step(self, name: str):
        self.steps.append({"name": name, "status": "pending"})

    def start_step(self, index: int):
        self.current_step = index
        self.steps[index]["status"] = "running"
        self._render()

    def complete_step(self, index: int, success: bool = True):
        self.steps[index]["status"] = "success" if success else "failed"
        self._render()

    def _render(self):
        c = Colors
        clear_line()

        parts = []
        for i, step in enumerate(self.steps):
            if step["status"] == "pending":
                parts.append(f"{c.DIM}○ {step['name']}{c.RESET}")
            elif step["status"] == "running":
                parts.append(f"{c.YELLOW}◐ {step['name']}...{c.RESET}")
            elif step["status"] == "success":
                parts.append(f"{c.GREEN}✓ {step['name']}{c.RESET}")
            else:
                parts.append(f"{c.RED}✗ {step['name']}{c.RESET}")

        print("  " + "  ".join(parts), end="", flush=True)

    def finish(self):
        print()  # New line after progress


def print_result_summary(report):
    """Print a summary of the generated config."""
    c = Colors

    print()
    print(f"{c.GREEN}{c.BOLD}Generation successful!{c.RESET}")
    print()

    # Agent summary
    print(f"  {c.BOLD}Agents:{c.RESET}")
    if report.miner_count > 0:
        print(f"    • {report.miner_count} miners (hashrate: {report.total_hashrate})")
    if report.user_count > 0:
        print(f"    • {report.user_count} users")
    if report.spy_count > 0:
        print(f"    • {report.spy_count} spy nodes")

    # Timing
    print(f"  {c.BOLD}Timing:{c.RESET}")
    print(f"    • Duration: {seconds_to_human(report.stop_time_s)}")
    print(f"    • Bootstrap ends: {seconds_to_human(report.bootstrap_end_time_s)}")

    # Network
    if report.network_type:
        print(f"  {c.BOLD}Network:{c.RESET}")
        print(f"    • Type: {report.network_type}")

    # Upgrade info
    if report.upgrade and report.upgrade.enabled:
        print(f"  {c.BOLD}Upgrade scenario:{c.RESET}")
        print(f"    • Nodes upgrading: {report.upgrade.agents_with_phases}")

    print()


def print_scenario_menu():
    """Print the scenario review menu."""
    c = Colors
    print(f"  {c.BOLD}[V]{c.RESET} View scenario")
    print(f"  {c.BOLD}[E]{c.RESET} Edit scenario (opens in editor)")
    print(f"  {c.BOLD}[A]{c.RESET} Approve and expand to full config")
    print(f"  {c.BOLD}[R]{c.RESET} Regenerate scenario")
    print(f"  {c.BOLD}[Q]{c.RESET} Quit")
    print()


def print_final_menu():
    """Print the final config menu."""
    c = Colors
    print(f"  {c.BOLD}[V]{c.RESET} View expanded config")
    print(f"  {c.BOLD}[C]{c.RESET} View scenario (compact)")
    print(f"  {c.BOLD}[B]{c.RESET} Back to scenario editing")
    print(f"  {c.BOLD}[S]{c.RESET} Save and exit")
    print(f"  {c.BOLD}[Q]{c.RESET} Quit without saving")
    print()


def view_config(yaml_content: str, max_lines: int = 60):
    """Display the YAML config with syntax highlighting."""
    c = Colors
    print()
    print(f"{c.CYAN}{'─' * 60}{c.RESET}")

    lines = yaml_content.split('\n')
    for line in lines[:max_lines]:
        # Simple syntax highlighting
        if line.startswith('#'):
            print(f"{c.DIM}{line}{c.RESET}")
        elif ':' in line and not line.strip().startswith('-'):
            key, _, value = line.partition(':')
            print(f"{c.BLUE}{key}{c.RESET}:{value}")
        else:
            print(line)

    if len(lines) > max_lines:
        print(f"{c.DIM}... ({len(lines) - max_lines} more lines){c.RESET}")

    print(f"{c.CYAN}{'─' * 60}{c.RESET}")
    print()


def edit_scenario_in_editor(scenario_content: str) -> Optional[str]:
    """Open scenario in user's editor and return edited content."""
    import tempfile
    import subprocess

    c = Colors

    # Get editor from environment
    editor = os.environ.get('EDITOR', os.environ.get('VISUAL', 'nano'))

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.scenario.yaml', delete=False) as f:
        f.write(scenario_content)
        temp_path = f.name

    try:
        # Open editor
        print(f"{c.DIM}Opening {editor}... Save and close when done.{c.RESET}")
        result = subprocess.run([editor, temp_path])

        if result.returncode != 0:
            print(f"{c.YELLOW}Editor exited with error.{c.RESET}")
            return None

        # Read back
        with open(temp_path, 'r') as f:
            edited = f.read()

        return edited

    except Exception as e:
        print(f"{c.RED}Failed to open editor: {e}{c.RESET}")
        return None
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass


def run_interactive(generator, output_file: str, save_scenario: Optional[str] = None):
    """Run the interactive generation loop with scenario review."""
    c = Colors

    # Import here to avoid circular imports
    from ..scenario_parser import parse_scenario, expand_scenario
    import yaml as yaml_lib
    from collections import OrderedDict

    print_header()

    print("Describe your simulation scenario.")
    print("Be as exact or as vague as you'd like.")
    print()
    print_examples()

    # Get initial description
    description = get_multiline_input("Your scenario")

    if not description:
        print(f"{c.YELLOW}No description provided. Exiting.{c.RESET}")
        return False

    scenario_content = None
    yaml_content = None
    validation_report = None

    while True:
        # === PHASE 1: Generate scenario ===
        print()
        print(f"{c.BOLD}Generating scenario...{c.RESET}")

        # Use generator's LLM to get scenario
        from .scenario_prompts import SCENARIO_SYSTEM_PROMPT
        messages = [
            {"role": "system", "content": SCENARIO_SYSTEM_PROMPT},
            {"role": "user", "content": description}
        ]

        try:
            response = generator.provider.chat(messages)
            scenario_content = generator._extract_yaml(response.content)

            if not scenario_content:
                print(f"{c.RED}Failed to generate scenario. Try again.{c.RESET}")
                continue

        except Exception as e:
            print(f"{c.RED}LLM error: {e}{c.RESET}")
            continue

        print(f"{c.GREEN}Scenario generated!{c.RESET}")
        print()

        # === PHASE 2: Scenario review loop ===
        while True:
            print(f"{c.BOLD}Review your scenario before expanding:{c.RESET}")
            print()
            print_scenario_menu()
            choice = get_user_input("Choice").upper()

            if choice == 'V':
                view_config(scenario_content, max_lines=100)
                continue

            elif choice == 'E':
                edited = edit_scenario_in_editor(scenario_content)
                if edited:
                    scenario_content = edited
                    print(f"{c.GREEN}Scenario updated.{c.RESET}")
                continue

            elif choice == 'R':
                # Regenerate - go back to outer loop
                break

            elif choice == 'Q':
                print(f"{c.YELLOW}Exiting without saving.{c.RESET}")
                return False

            elif choice == 'A':
                # Approve and expand
                print()
                print(f"{c.BOLD}Expanding scenario...{c.RESET}")

                try:
                    # Parse and expand
                    scenario = parse_scenario(scenario_content)
                    seed = scenario.general.get('simulation_seed', 12345)
                    config = expand_scenario(scenario, seed=seed)

                    # Convert to plain dict
                    def to_plain_dict(obj):
                        if isinstance(obj, OrderedDict):
                            return {k: to_plain_dict(v) for k, v in obj.items()}
                        elif isinstance(obj, dict):
                            return {k: to_plain_dict(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [to_plain_dict(i) for i in obj]
                        return obj

                    plain_config = to_plain_dict(config)
                    yaml_content = yaml_lib.dump(plain_config, default_flow_style=False, sort_keys=False)

                    # Validate
                    validation_report = generator.validator.validate_yaml(yaml_content)

                    print(f"{c.GREEN}Expansion successful!{c.RESET}")
                    print_result_summary(validation_report)

                except Exception as e:
                    print(f"{c.RED}Expansion failed: {e}{c.RESET}")
                    print(f"{c.DIM}Edit the scenario to fix issues, or regenerate.{c.RESET}")
                    continue

                # === PHASE 3: Final config review ===
                while True:
                    print_final_menu()
                    choice2 = get_user_input("Choice").upper()

                    if choice2 == 'V':
                        view_config(yaml_content, max_lines=80)
                        continue

                    elif choice2 == 'C':
                        view_config(scenario_content, max_lines=100)
                        continue

                    elif choice2 == 'B':
                        # Back to scenario editing
                        break

                    elif choice2 == 'S':
                        # Save and exit
                        # Save expanded config
                        with open(output_file, 'w') as f:
                            f.write(f"# Generated by ai_config for: {description[:60]}...\n\n")
                            f.write(yaml_content)
                        print(f"{c.GREEN}Config saved to: {output_file}{c.RESET}")

                        # Always save scenario alongside
                        if output_file.endswith('.yaml'):
                            scenario_file = output_file[:-5] + '.scenario.yaml'
                        elif output_file.endswith('.yml'):
                            scenario_file = output_file[:-4] + '.scenario.yaml'
                        else:
                            scenario_file = output_file + '.scenario.yaml'

                        # Use custom path if specified
                        if save_scenario:
                            scenario_file = save_scenario

                        with open(scenario_file, 'w') as f:
                            f.write(scenario_content)
                        print(f"{c.GREEN}Scenario saved to: {scenario_file}{c.RESET}")

                        return True

                    elif choice2 == 'Q':
                        print(f"{c.YELLOW}Exiting without saving.{c.RESET}")
                        return False

                    else:
                        print(f"{c.YELLOW}Invalid choice.{c.RESET}")
                        continue

                # If we got here from 'B', continue scenario review loop
                continue

            else:
                print(f"{c.YELLOW}Invalid choice.{c.RESET}")
                continue

        # If we got here from 'R', regenerate
        continue

    return False


def check_llm_config():
    """Check for LLM configuration and prompt if missing."""
    c = Colors

    config_path = Path.home() / '.monerosim' / 'ai_config.yaml'

    # Check environment variables first
    api_key = os.environ.get('OPENAI_API_KEY')
    base_url = os.environ.get('OPENAI_BASE_URL')

    if api_key and base_url:
        return {
            'api_key': api_key,
            'base_url': base_url,
            'model': os.environ.get('AI_CONFIG_MODEL', 'qwen2.5:7b')
        }

    # Check config file
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
                if config and config.get('api_key') and config.get('base_url'):
                    return config
        except Exception:
            pass

    # Prompt for configuration
    print(f"{c.YELLOW}LLM configuration not found.{c.RESET}")
    print()
    print("The AI config generator needs access to an LLM.")
    print("You can use a local server (llama.cpp, ollama) or a cloud API.")
    print()

    print(f"{c.BOLD}Common setups:{c.RESET}")
    print(f"  1. Local llama.cpp server (http://localhost:8080/v1)")
    print(f"  2. Local Ollama (http://localhost:11434/v1)")
    print(f"  3. OpenAI API (https://api.openai.com/v1)")
    print()

    base_url = get_user_input("API Base URL", "http://localhost:8080/v1")
    if not base_url:
        return None

    api_key = get_user_input("API Key (use 'x' for local servers)", "x")
    if not api_key:
        return None

    model = get_user_input("Model name", "qwen2.5:7b")

    config = {
        'api_key': api_key,
        'base_url': base_url,
        'model': model
    }

    # Offer to save
    print()
    save = get_user_input("Save this configuration for future use? [Y/n]", "y")
    if save.lower() != 'n':
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import yaml
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            print(f"{c.GREEN}Configuration saved to: {config_path}{c.RESET}")
        except Exception as e:
            print(f"{c.YELLOW}Could not save config: {e}{c.RESET}")

    return config
