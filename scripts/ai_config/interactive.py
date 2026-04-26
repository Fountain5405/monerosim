#!/usr/bin/env python3
"""
Interactive mode for AI config generator.
"""

import os
import sys
import time
import threading
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
    print(f"  {c.BOLD}[S]{c.RESET} Save scenario only (without expanding)")
    print(f"  {c.BOLD}[R]{c.RESET} Regenerate scenario (same prompt)")
    print(f"  {c.BOLD}[M]{c.RESET} Modify scenario (give new instructions)")
    print(f"  {c.BOLD}[N]{c.RESET} New prompt (start over)")
    print(f"  {c.BOLD}[Q]{c.RESET} Quit")
    print()


def print_final_menu():
    """Print the final config menu."""
    c = Colors
    print(f"  {c.BOLD}[V]{c.RESET} View expanded config")
    print(f"  {c.BOLD}[C]{c.RESET} View scenario (compact)")
    print(f"  {c.BOLD}[B]{c.RESET} Back to scenario editing")
    print(f"  {c.BOLD}[S]{c.RESET} Save and exit")
    print(f"  {c.BOLD}[M]{c.RESET} Modify scenario (give new instructions)")
    print(f"  {c.BOLD}[N]{c.RESET} New prompt (start over)")
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


def print_tips(is_small_model: bool = False):
    """Print tips for writing good prompts."""
    c = Colors

    print(f"{c.BOLD}Tips for good results:{c.RESET}")
    print()

    if is_small_model:
        print(f"  {c.YELLOW}You are using the MoneroWorld LLM (smaller model).{c.RESET}")
        print(f"  {c.YELLOW}Be specific in your prompts for best results.{c.RESET}")
        print()
    else:
        print(f"  {c.GREEN}You are using a larger LLM backend.{c.RESET}")
        print(f"  {c.GREEN}You can be as specific or vague as you like.{c.RESET}")
        print()

    print(f"  {c.DIM}• Minimum 5 initial miners required (hashrates must sum to 100){c.RESET}")
    print(f"  {c.DIM}• Miners start at time 0 with staggered starts (1s apart){c.RESET}")
    print(f"  {c.DIM}• Bootstrap period (min 4h, scales with users) relaxes network{c.RESET}")
    print(f"  {c.DIM}  limits so miners can accumulate XMR for distribution{c.RESET}")
    print(f"  {c.DIM}• Users begin transacting after bootstrap, once they have funds{c.RESET}")
    print(f"  {c.DIM}• Upgrade scenarios use daemon phases (v1 -> v2 transitions){c.RESET}")
    print(f"  {c.DIM}• Spy nodes have high peer counts (100+) for network monitoring{c.RESET}")
    print()


def run_interactive(generator, output_file: str, save_scenario: Optional[str] = None,
                    is_small_model: bool = False):
    """Run the interactive generation loop with scenario review."""
    c = Colors

    # Import here to avoid circular imports
    from ..scenario_parser import parse_scenario, expand_scenario
    import yaml as yaml_lib
    from collections import OrderedDict

    print_header()
    print_tips(is_small_model)

    print("Describe your simulation scenario.")
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
            print()
            response = call_llm_with_waiting(generator.provider.chat, messages)
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
                # Regenerate with same prompt - go back to outer loop
                break

            elif choice == 'N':
                # New prompt - get fresh description and regenerate
                print()
                new_desc = get_multiline_input("New scenario description")
                if new_desc:
                    description = new_desc
                break  # Go back to outer generation loop with new description

            elif choice == 'M':
                # Modify scenario with additional instructions
                print()
                instructions = get_multiline_input("Modification instructions")
                if not instructions:
                    print(f"{c.YELLOW}No instructions provided.{c.RESET}")
                    continue

                print()
                print(f"{c.BOLD}Modifying scenario...{c.RESET}")
                try:
                    modify_messages = [
                        {"role": "system", "content": SCENARIO_SYSTEM_PROMPT},
                        {"role": "user", "content": description},
                        {"role": "assistant", "content": scenario_content},
                        {"role": "user", "content": f"Please modify the scenario as follows:\n{instructions}\n\nOutput the complete updated scenario YAML."}
                    ]
                    print()
                    response = call_llm_with_waiting(generator.provider.chat, modify_messages)
                    modified = generator._extract_yaml(response.content)
                    if modified:
                        scenario_content = modified
                        print(f"{c.GREEN}Scenario modified!{c.RESET}")
                    else:
                        print(f"{c.RED}Failed to extract scenario from LLM response.{c.RESET}")
                except Exception as e:
                    print(f"{c.RED}LLM error: {e}{c.RESET}")
                continue

            elif choice == 'Q':
                print(f"{c.YELLOW}Exiting without saving.{c.RESET}")
                return False

            elif choice == 'S':
                # Save scenario only (without expanding)
                if output_file.endswith('.yaml'):
                    scenario_file = output_file[:-5] + '.scenario.yaml'
                elif output_file.endswith('.yml'):
                    scenario_file = output_file[:-4] + '.scenario.yaml'
                else:
                    scenario_file = output_file + '.scenario.yaml'

                # Use custom path if specified via CLI
                if save_scenario:
                    scenario_file = save_scenario

                # Let user choose filename
                save_path = get_user_input(f"Scenario filename", scenario_file)
                if save_path:
                    scenario_file = save_path

                # Add header indicating this needs expansion
                header = (
                    "# =============================================================\n"
                    "# COMPACT SCENARIO FILE - REQUIRES EXPANSION\n"
                    "# =============================================================\n"
                    "# This file uses compact syntax (e.g., {001..010}) that must be\n"
                    "# expanded before use with monerosim.\n"
                    "#\n"
                    "# To expand this file into a full config:\n"
                    "#   python -m scripts.scenario_parser " + scenario_file + " -o config.yaml\n"
                    "#\n"
                    "# Or use the AI config tool to re-import and expand:\n"
                    "#   python -m scripts.ai_config\n"
                    "# =============================================================\n\n"
                )

                with open(scenario_file, 'w') as f:
                    f.write(header)
                    f.write(scenario_content)

                print(f"{c.GREEN}Scenario saved to: {scenario_file}{c.RESET}")
                print(f"{c.DIM}Note: This file needs expansion before use.{c.RESET}")
                print(f"{c.DIM}Run: python -m scripts.scenario_parser {scenario_file} -o config.yaml{c.RESET}")
                return True

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
                needs_regenerate = False
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
                        # Save and exit - let user choose filename
                        save_path = get_user_input(f"Config filename", output_file)
                        if save_path:
                            output_file = save_path

                        with open(output_file, 'w') as f:
                            f.write(f"# Generated by ai_config for: {description[:60]}...\n\n")
                            f.write(yaml_content)
                        print(f"{c.GREEN}Config saved to: {output_file}{c.RESET}")

                        # Derive scenario filename from config filename
                        if output_file.endswith('.yaml'):
                            scenario_file = output_file[:-5] + '.scenario.yaml'
                        elif output_file.endswith('.yml'):
                            scenario_file = output_file[:-4] + '.scenario.yaml'
                        else:
                            scenario_file = output_file + '.scenario.yaml'

                        # Use custom path if specified via CLI
                        if save_scenario:
                            scenario_file = save_scenario

                        with open(scenario_file, 'w') as f:
                            f.write(scenario_content)
                        print(f"{c.GREEN}Scenario saved to: {scenario_file}{c.RESET}")

                        return True

                    elif choice2 == 'N':
                        # New prompt from final menu - get fresh description
                        print()
                        new_desc = get_multiline_input("New scenario description")
                        if new_desc:
                            description = new_desc
                        needs_regenerate = True
                        break  # Break to scenario loop, then outer loop will regenerate

                    elif choice2 == 'M':
                        # Modify scenario from final menu
                        print()
                        instructions = get_multiline_input("Modification instructions")
                        if not instructions:
                            print(f"{c.YELLOW}No instructions provided.{c.RESET}")
                            continue

                        print()
                        print(f"{c.BOLD}Modifying scenario...{c.RESET}")
                        try:
                            modify_messages = [
                                {"role": "system", "content": SCENARIO_SYSTEM_PROMPT},
                                {"role": "user", "content": description},
                                {"role": "assistant", "content": scenario_content},
                                {"role": "user", "content": f"Please modify the scenario as follows:\n{instructions}\n\nOutput the complete updated scenario YAML."}
                            ]
                            print()
                            response = call_llm_with_waiting(generator.provider.chat, modify_messages)
                            modified = generator._extract_yaml(response.content)
                            if modified:
                                scenario_content = modified
                                print(f"{c.GREEN}Scenario modified!{c.RESET}")
                            else:
                                print(f"{c.RED}Failed to extract scenario from LLM response.{c.RESET}")
                                continue
                        except Exception as e:
                            print(f"{c.RED}LLM error: {e}{c.RESET}")
                            continue
                        break  # Break to scenario review loop to view/approve modified scenario

                    elif choice2 == 'Q':
                        print(f"{c.YELLOW}Exiting without saving.{c.RESET}")
                        return False

                    else:
                        print(f"{c.YELLOW}Invalid choice.{c.RESET}")
                        continue

                # If 'N' was selected, break out of scenario loop to regenerate
                if needs_regenerate:
                    break
                # If we got here from 'B' or 'M', continue scenario review loop
                continue

            else:
                print(f"{c.YELLOW}Invalid choice.{c.RESET}")
                continue

        # If we got here from 'R', regenerate
        continue

    return False


def load_waiting_facts():
    """Load facts from YAML file to display while waiting for LLM.

    Returns the list shuffled in-place so each session shows a fresh
    order rather than cycling through the YAML top-to-bottom every time.
    Non-string entries (e.g. a fact with an unquoted colon that YAML
    silently parsed as a single-key map) are coerced to strings so a
    typo in the YAML can't break the spinner.
    """
    import random
    try:
        import yaml
        facts_file = Path(__file__).parent / 'waiting_facts.yaml'
        with open(facts_file, 'r') as f:
            data = yaml.safe_load(f)
            raw = data.get('facts', []) if data else []
    except Exception:
        # Fallback facts if file not found
        raw = [
            "Waiting for LLM response...",
            "Processing your request...",
            "Generating configuration...",
            "Thinking...",
        ]
    facts: list[str] = []
    for entry in raw:
        if isinstance(entry, str):
            facts.append(entry)
        elif isinstance(entry, dict) and len(entry) == 1:
            # YAML parsed an unquoted "key: value" line as a one-key map;
            # rejoin into a single string so it still displays.
            (k, v), = entry.items()
            facts.append(f"{k}: {v}")
        else:
            facts.append(str(entry))
    random.shuffle(facts)
    return facts


WAITING_FACTS = load_waiting_facts()


def _wrap_fact(fact: str, available_width: int) -> list[str]:
    """Break a fact into chunks that fit in `available_width` columns.

    We render facts on a single overwriting line (\\r-style), so a long
    fact has to be cycled through as a series of chunks rather than a
    multi-line block. Returns at least one chunk; chunks are filled to
    near the width budget without splitting words.
    """
    import textwrap
    if available_width <= 1:
        return [fact]
    # break_long_words=True so a single freakishly long word still fits
    chunks = textwrap.wrap(
        fact,
        width=max(available_width, 20),
        break_long_words=True,
        break_on_hyphens=False,
    )
    return chunks if chunks else [fact]


def call_llm_with_waiting(chat_fn: Callable, messages: list) -> object:
    """
    Call LLM with animated Monero facts while waiting.

    Args:
        chat_fn: The chat function to call
        messages: Messages to pass to chat

    Returns:
        Response from chat function
    """
    import threading

    result = [None]
    error = [None]
    fact_index = [0]
    chunk_index = [0]
    chunk_shown_at = [0.0]  # When the current chunk started displaying
    start_time = time.time()
    stop_animation = threading.Event()

    def run_chat():
        try:
            result[0] = chat_fn(messages)
        except Exception as e:
            error[0] = e
        finally:
            stop_animation.set()

    def animate():
        while not stop_animation.is_set():
            elapsed = time.time() - start_time
            (
                fact_index[0],
                chunk_index[0],
                chunk_shown_at[0],
            ) = show_waiting_indicator(
                elapsed, fact_index[0], chunk_index[0], chunk_shown_at[0]
            )
            time.sleep(0.2)  # Update spinner every 200ms
        # Clear the line — best-effort using current terminal width
        try:
            width = os.get_terminal_size().columns
        except (OSError, ValueError):
            width = 200
        sys.stdout.write('\r' + ' ' * width + '\r')
        sys.stdout.flush()

    # Start chat in background thread
    chat_thread = threading.Thread(target=run_chat, daemon=True)
    chat_thread.start()

    # Animate while waiting
    animate()

    chat_thread.join(timeout=5)
    if error[0]:
        raise error[0]
    return result[0]


def show_waiting_indicator(
    elapsed_time: float,
    fact_index: int,
    chunk_index: int,
    chunk_shown_at: float,
) -> tuple[int, int, float]:
    """
    Show a rotating Monero fact with spinner while waiting.

    Long facts that don't fit the terminal are split into chunks and
    cycled one at a time so nothing gets truncated.

    Args:
        elapsed_time:    Time elapsed since operation started
        fact_index:      Index into WAITING_FACTS
        chunk_index:     Which chunk of the current fact is showing
        chunk_shown_at:  When the current chunk started displaying

    Returns:
        Updated (fact_index, chunk_index, chunk_shown_at)
    """
    spinner = "◐◓◑◒"
    spinner_char = spinner[int(elapsed_time * 2) % len(spinner)]

    try:
        terminal_width = os.get_terminal_size().columns
    except (OSError, ValueError):
        terminal_width = 120

    # Reserve space for spinner + space + " (Ns)" suffix; cap suffix at
    # ~8 chars (good through "9999s") so we don't overshoot.
    suffix_budget = 8
    available = max(20, terminal_width - 2 - suffix_budget)

    current_fact = WAITING_FACTS[fact_index % len(WAITING_FACTS)]
    chunks = _wrap_fact(current_fact, available)
    # Re-clamp chunk_index in case terminal width changed and the new
    # wrapping produced fewer chunks than before.
    if chunk_index >= len(chunks):
        chunk_index = len(chunks) - 1

    # Per-chunk display time: enough to read a line of text, scaled by
    # word count. Minimum 4s, maximum 8s per chunk.
    word_count = len(chunks[chunk_index].split())
    display_time = max(4.0, min(8.0, word_count * 0.35))

    if elapsed_time - chunk_shown_at >= display_time:
        chunk_index += 1
        if chunk_index >= len(chunks):
            # Done with this fact — advance to the next one.
            fact_index += 1
            chunk_index = 0
            current_fact = WAITING_FACTS[fact_index % len(WAITING_FACTS)]
            chunks = _wrap_fact(current_fact, available)
        chunk_shown_at = elapsed_time

    elapsed_str = f"{int(elapsed_time)}s"
    line = f"\r{spinner_char} {chunks[chunk_index]} ({elapsed_str})"
    # Hard-truncate as a safety net (shouldn't trigger since we already
    # wrapped to `available`), then pad to clear any leftover characters
    # from a longer previous chunk.
    line = line[:terminal_width]
    padding = max(0, terminal_width - len(line))
    print(f"{line}{' ' * padding}", end="", flush=True)

    return fact_index, chunk_index, chunk_shown_at


def check_llm_config():
    """Check for LLM configuration and prompt if missing."""
    c = Colors

    config_path = Path.home() / '.monerosim' / 'ai_config.yaml'

    # Load config file if it exists
    file_config = {}
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                file_config = yaml.safe_load(f) or {}
        except Exception:
            pass

    # Resolve each field: env vars > config file
    api_key = os.environ.get('OPENAI_API_KEY') or file_config.get('api_key')
    base_url = os.environ.get('OPENAI_BASE_URL') or file_config.get('base_url')
    model = os.environ.get('AI_CONFIG_MODEL') or file_config.get('model')

    if api_key and base_url:
        return {
            'api_key': api_key,
            'base_url': base_url,
            'model': model or 'qwen3:8b-16k'
        }

    # Prompt for configuration
    print(f"{c.YELLOW}LLM configuration not found.{c.RESET}")
    print()
    print("The AI config generator needs access to an LLM.")
    print()

    print(f"{c.BOLD}Select a backend:{c.RESET}")
    print(f"  {c.GREEN}1. MoneroWorld test server (recommended){c.RESET}")
    print(f"  2. Local llama.cpp server (http://localhost:8080/v1)")
    print(f"  3. Local Ollama (http://localhost:11434/v1)")
    print(f"  4. Groq API (https://api.groq.com/openai/v1)")
    print(f"  5. OpenAI API (https://api.openai.com/v1)")
    print(f"  6. Custom URL")
    print()

    choice = get_user_input("Choice [1-6]", "1")

    # Preset configurations
    presets = {
        '1': {
            'base_url': 'http://test.moneroworld.com:49767/v1',
            'api_key': 'x',
            'model': 'qwen3:8b-16k',
            'name': 'MoneroWorld'
        },
        '2': {
            'base_url': 'http://localhost:8080/v1',
            'api_key': 'x',
            'model': 'qwen3:8b-16k',
            'name': 'llama.cpp'
        },
        '3': {
            'base_url': 'http://localhost:11434/v1',
            'api_key': 'x',
            'model': 'qwen3:8b-16k',
            'name': 'Ollama'
        },
        '4': {
            'base_url': 'https://api.groq.com/openai/v1',
            'api_key': '',  # User must provide
            'model': 'llama-3.3-70b-versatile',
            'name': 'Groq'
        },
        '5': {
            'base_url': 'https://api.openai.com/v1',
            'api_key': '',  # User must provide
            'model': 'gpt-4o-mini',
            'name': 'OpenAI'
        },
    }

    if choice in presets:
        preset = presets[choice]
        base_url = preset['base_url']
        api_key = preset['api_key']
        model = preset['model']

        print(f"{c.DIM}Using {preset['name']}: {base_url}{c.RESET}")

        # Health check for MoneroWorld server
        if choice == '1':
            print(f"{c.DIM}Checking if server is available...{c.RESET}", end='', flush=True)
            try:
                import urllib.request
                req = urllib.request.Request(
                    base_url.rstrip('/') + '/models',
                    headers={'Authorization': 'Bearer x'}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp.read()
                print(f"\r{c.GREEN}Server is online.{c.RESET}                    ")
            except Exception:
                print(f"\r{c.YELLOW}Warning: MoneroWorld server may be down or unreachable.{c.RESET}")
                print(f"{c.YELLOW}The server is maintained by a volunteer and may not always be available.{c.RESET}")
                print(f"{c.YELLOW}If generation hangs or fails, try a local backend (options 2-3) instead.{c.RESET}")
                print()
                proceed = get_user_input("Continue anyway? [y/N]", "n")
                if proceed.lower() != 'y':
                    return None

        # Prompt for API key if needed
        if not api_key:
            api_key = get_user_input(f"{preset['name']} API Key")
            if not api_key:
                return None

        # Allow model override (except for MoneroWorld which has a fixed model)
        if choice != '1':
            model_input = get_user_input(f"Model name", model)
            if model_input:
                model = model_input
    else:
        # Custom URL
        base_url = get_user_input("API Base URL", "http://localhost:8080/v1")
        if not base_url:
            return None

        api_key = get_user_input("API Key (use 'x' for local servers)", "x")
        if not api_key:
            return None

        model = get_user_input("Model name", "qwen3:8b-16k")

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
