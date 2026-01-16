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


def print_menu():
    """Print the post-generation menu."""
    c = Colors
    print(f"  {c.BOLD}[R]{c.RESET} Regenerate with same description")
    print(f"  {c.BOLD}[E]{c.RESET} Edit description and regenerate")
    print(f"  {c.BOLD}[V]{c.RESET} View full config")
    print(f"  {c.BOLD}[S]{c.RESET} Save and exit")
    print(f"  {c.BOLD}[Q]{c.RESET} Quit without saving")
    print()


def view_config(yaml_content: str):
    """Display the YAML config with syntax highlighting."""
    c = Colors
    print()
    print(f"{c.CYAN}{'─' * 60}{c.RESET}")

    for line in yaml_content.split('\n')[:50]:  # First 50 lines
        # Simple syntax highlighting
        if line.startswith('#'):
            print(f"{c.DIM}{line}{c.RESET}")
        elif ':' in line and not line.strip().startswith('-'):
            key, _, value = line.partition(':')
            print(f"{c.BLUE}{key}{c.RESET}:{value}")
        else:
            print(line)

    if yaml_content.count('\n') > 50:
        print(f"{c.DIM}... ({yaml_content.count(chr(10)) - 50} more lines){c.RESET}")

    print(f"{c.CYAN}{'─' * 60}{c.RESET}")
    print()


def run_interactive(generator, output_file: str, save_script: Optional[str] = None):
    """Run the interactive generation loop."""
    c = Colors

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

    yaml_content = None
    result = None

    while True:
        # Generate
        print()
        print(f"{c.BOLD}Generating configuration...{c.RESET}")
        print()

        progress = ProgressIndicator()
        progress.add_step("Script")
        progress.add_step("Validate")
        progress.add_step("Check")

        # Hook into generator progress (simplified - just show steps)
        progress.start_step(0)

        result = generator.generate(
            user_request=description,
            output_file=None,  # Don't save yet
            save_script=None
        )

        if result.script_content:
            progress.complete_step(0, True)
            progress.start_step(1)

            if result.validation_report:
                progress.complete_step(1, True)
                progress.start_step(2)
                progress.complete_step(2, result.success)
            else:
                progress.complete_step(1, False)
        else:
            progress.complete_step(0, False)

        progress.finish()

        if result.success and result.yaml_content:
            yaml_content = result.yaml_content
            print_result_summary(result.validation_report)
        else:
            print()
            print(f"{c.RED}Generation failed after {result.attempts} attempt(s).{c.RESET}")
            if result.errors:
                print(f"{c.DIM}Last error: {result.errors[-1][:200]}{c.RESET}")
            print()

        # Menu loop
        while True:
            print_menu()
            choice = get_user_input("Choice").upper()

            if choice == 'R':
                # Regenerate with same description
                break

            elif choice == 'E':
                # Edit description
                print()
                print(f"{c.DIM}Current: {description[:100]}{'...' if len(description) > 100 else ''}{c.RESET}")
                new_desc = get_multiline_input("New scenario (or press Enter to keep current)")
                if new_desc:
                    description = new_desc
                break

            elif choice == 'V':
                # View config
                if yaml_content:
                    view_config(yaml_content)
                else:
                    print(f"{c.YELLOW}No config generated yet.{c.RESET}")
                continue

            elif choice == 'S':
                # Save and exit
                if yaml_content:
                    # Save YAML
                    with open(output_file, 'w') as f:
                        f.write(yaml_content)
                    print(f"{c.GREEN}Config saved to: {output_file}{c.RESET}")

                    # Save script if requested
                    if save_script and result and result.script_content:
                        with open(save_script, 'w') as f:
                            f.write(result.script_content)
                        print(f"{c.GREEN}Generator script saved to: {save_script}{c.RESET}")

                    return True
                else:
                    print(f"{c.YELLOW}No config to save. Generate first.{c.RESET}")
                continue

            elif choice == 'Q':
                # Quit without saving
                print(f"{c.YELLOW}Exiting without saving.{c.RESET}")
                return False

            else:
                print(f"{c.YELLOW}Invalid choice. Please enter R, E, V, S, or Q.{c.RESET}")
                continue

    return False  # Should not reach here


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
