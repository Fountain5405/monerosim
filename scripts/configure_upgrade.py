#!/usr/bin/env python3
"""
Interactive configurator for network upgrade simulations.

This tool walks you through setting up a simulation where:
1. A network reaches steady state (all nodes online, transacting)
2. After observation, nodes gradually upgrade to a new binary
3. Simulation continues for post-upgrade observation

Run with: python scripts/configure_upgrade.py
"""

import sys
import os

# Add parent directory to path so we can import from generate_config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_config import (
    generate_upgrade_config,
    config_to_yaml,
    format_time_offset,
    parse_duration,
    FIXED_MINERS,
    DEFAULT_GML_PATH,
    DEFAULT_INITIAL_DELAY_S,
)


def print_header():
    """Print welcome header."""
    print()
    print("=" * 70)
    print("  Network Upgrade Scenario Configurator")
    print("=" * 70)
    print()
    print("This tool helps you set up a simulation where a network of nodes")
    print("reaches steady state, then gradually upgrades to a new binary.")
    print()
    print("I'll ask you a few questions to configure the simulation.")
    print("Press Ctrl+C at any time to exit.")
    print()
    print("-" * 70)


def ask_int(prompt: str, default: int = None, min_val: int = None, max_val: int = None) -> int:
    """Ask for an integer input with optional default and validation."""
    while True:
        default_str = f" [{default}]" if default is not None else ""
        try:
            response = input(f"{prompt}{default_str}: ").strip()
            if not response and default is not None:
                return default
            value = int(response)
            if min_val is not None and value < min_val:
                print(f"  Please enter a value >= {min_val}")
                continue
            if max_val is not None and value > max_val:
                print(f"  Please enter a value <= {max_val}")
                continue
            return value
        except ValueError:
            print("  Please enter a valid number")


def ask_duration(prompt: str, default: str = None) -> str:
    """Ask for a duration input (e.g., '2h', '30m', '90s')."""
    while True:
        default_str = f" [{default}]" if default else ""
        response = input(f"{prompt}{default_str}: ").strip()
        if not response and default:
            return default
        if not response:
            print("  Please enter a duration (e.g., '2h', '30m', '90s')")
            continue
        # Validate it can be parsed
        try:
            parse_duration(response)
            return response
        except (ValueError, AttributeError):
            print("  Invalid format. Use something like '2h', '30m', or '90s'")


def ask_choice(prompt: str, choices: list, default: str = None) -> str:
    """Ask user to choose from a list of options."""
    print(f"\n{prompt}")
    for i, choice in enumerate(choices, 1):
        marker = " (default)" if choice == default else ""
        print(f"  {i}. {choice}{marker}")

    while True:
        default_str = f" [{default}]" if default else ""
        response = input(f"Enter choice (1-{len(choices)}){default_str}: ").strip()

        if not response and default:
            return default

        # Check if they typed the choice name directly
        if response.lower() in [c.lower() for c in choices]:
            for c in choices:
                if c.lower() == response.lower():
                    return c

        # Check if they entered a number
        try:
            idx = int(response)
            if 1 <= idx <= len(choices):
                return choices[idx - 1]
            print(f"  Please enter 1-{len(choices)}")
        except ValueError:
            print(f"  Please enter 1-{len(choices)} or the choice name")


def ask_string(prompt: str, default: str = None) -> str:
    """Ask for a string input with optional default."""
    default_str = f" [{default}]" if default else ""
    response = input(f"{prompt}{default_str}: ").strip()
    return response if response else default


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Ask a yes/no question."""
    default_str = "Y/n" if default else "y/N"
    while True:
        response = input(f"{prompt} [{default_str}]: ").strip().lower()
        if not response:
            return default
        if response in ('y', 'yes'):
            return True
        if response in ('n', 'no'):
            return False
        print("  Please enter 'y' or 'n'")


def calculate_and_display_timeline(
    num_agents: int,
    steady_state_duration: str,
    upgrade_stagger: str,
    post_upgrade_duration: str,
) -> dict:
    """Calculate the timeline and display it to the user."""
    num_miners = len(FIXED_MINERS)
    num_users = num_agents - num_miners

    # Parse durations
    steady_state_s = parse_duration(steady_state_duration)
    upgrade_stagger_s = parse_duration(upgrade_stagger)
    post_upgrade_s = parse_duration(post_upgrade_duration)

    # Calculate key times (simplified version of what generate_upgrade_config does)
    # Users spawn at ~3h, bootstrap ends at ~4h, activity starts at ~5h
    bootstrap_end_s = 14400  # 4h minimum
    activity_start_s = bootstrap_end_s + 3600  # +1h for funding
    upgrade_start_s = activity_start_s + steady_state_s

    # Upgrade window duration
    upgrade_window_s = num_agents * upgrade_stagger_s
    upgrade_complete_s = upgrade_start_s + upgrade_window_s + 30  # +30s for last restart gap

    # Total simulation time
    total_s = upgrade_complete_s + post_upgrade_s

    timeline = {
        'bootstrap_end_s': bootstrap_end_s,
        'activity_start_s': activity_start_s,
        'upgrade_start_s': upgrade_start_s,
        'upgrade_window_s': upgrade_window_s,
        'upgrade_complete_s': upgrade_complete_s,
        'total_s': total_s,
        'num_miners': num_miners,
        'num_users': num_users,
    }

    return timeline


def display_timeline(timeline: dict, upgrade_order: str, upgrade_stagger: str):
    """Display the calculated timeline."""
    print("\n" + "=" * 70)
    print("  Calculated Timeline")
    print("=" * 70)
    print()
    print(f"  Network size: {timeline['num_miners']} miners + {timeline['num_users']} users")
    print()
    print("  Phase 1: Bootstrap & Funding")
    print(f"    t=0:           Miners start")
    print(f"    t=~3h:         Users start spawning")
    print(f"    t={format_time_offset(timeline['bootstrap_end_s'], for_config=False):10s}  Bootstrap ends, funding begins")
    print()
    print("  Phase 2: Steady State")
    print(f"    t={format_time_offset(timeline['activity_start_s'], for_config=False):10s}  All nodes transacting (steady state)")
    print(f"    (observing for {format_time_offset(timeline['upgrade_start_s'] - timeline['activity_start_s'], for_config=False)})")
    print()
    print("  Phase 3: Network Upgrade")
    print(f"    t={format_time_offset(timeline['upgrade_start_s'], for_config=False):10s}  Upgrade begins ({upgrade_order} order)")
    print(f"    (nodes switch every {upgrade_stagger}, taking ~{format_time_offset(timeline['upgrade_window_s'], for_config=False)} total)")
    print(f"    t={format_time_offset(timeline['upgrade_complete_s'], for_config=False):10s}  Last node completes upgrade")
    print()
    print("  Phase 4: Post-Upgrade Observation")
    print(f"    t={format_time_offset(timeline['total_s'], for_config=False):10s}  Simulation ends")
    print()
    print("-" * 70)


def main():
    try:
        print_header()

        # Step 1: Network Size
        print("\n[1/6] NETWORK SIZE")
        print("How many agents (nodes) should be in the simulation?")
        print("(This includes 5 fixed miners, the rest will be regular users)")
        num_agents = ask_int("Number of agents", default=30, min_val=6, max_val=1000)
        num_users = num_agents - len(FIXED_MINERS)
        print(f"\n  -> {len(FIXED_MINERS)} miners + {num_users} users = {num_agents} total agents")

        # Step 2: Binary Paths
        print("\n" + "-" * 70)
        print("\n[2/6] DAEMON BINARIES")
        print("What binaries should the nodes use before and after the upgrade?")
        print("(Use the binary name or path as it appears in your environment)")

        binary_v1 = ask_string("Binary BEFORE upgrade (v1)", default="monerod")
        binary_v2 = ask_string("Binary AFTER upgrade (v2)", default="monerod")

        if binary_v1 == binary_v2:
            print("\n  Note: Same binary for both phases. This is fine for testing the")
            print("  upgrade mechanism itself without actual version differences.")

        # Step 3: Steady State Duration
        print("\n" + "-" * 70)
        print("\n[3/6] STEADY STATE OBSERVATION")
        print("How long should nodes transact before the upgrade begins?")
        print("This is the 'steady state' period for baseline observation.")
        steady_state = ask_duration("Observation duration before upgrade", default="2h")

        # Step 4: Upgrade Strategy
        print("\n" + "-" * 70)
        print("\n[4/6] UPGRADE STRATEGY")
        print("How should nodes upgrade?")

        upgrade_order = ask_choice(
            "Upgrade order:",
            ["sequential", "miners-first", "random"],
            default="sequential"
        )

        print("\nHow much time between each node's upgrade?")
        print("(Smaller = faster rollout, larger = more gradual)")
        upgrade_stagger = ask_duration("Time between node upgrades", default="30s")

        # Step 5: Post-Upgrade Observation
        print("\n" + "-" * 70)
        print("\n[5/6] POST-UPGRADE OBSERVATION")
        print("How long should the simulation run after all upgrades complete?")
        post_upgrade = ask_duration("Post-upgrade observation duration", default="2h")

        # Calculate and display timeline
        timeline = calculate_and_display_timeline(
            num_agents, steady_state, upgrade_stagger, post_upgrade
        )
        display_timeline(timeline, upgrade_order, upgrade_stagger)

        # Step 6: Output Configuration
        print("\n[6/6] OUTPUT")
        output_file = ask_string("Output filename", default="upgrade_scenario.yaml")
        if not output_file.endswith('.yaml'):
            output_file += '.yaml'

        # Advanced options
        print("\n" + "-" * 70)
        if ask_yes_no("\nWould you like to configure advanced options?", default=False):
            print()
            seed = ask_int("Random seed (for reproducibility)", default=12345)
            fast_mode = ask_yes_no("Enable fast mode? (runahead, reduced logging)", default=False)
            gml_path = ask_string("Network topology GML file", default=DEFAULT_GML_PATH)
        else:
            seed = 12345
            fast_mode = False
            gml_path = DEFAULT_GML_PATH

        # Confirmation
        print("\n" + "=" * 70)
        print("  Configuration Summary")
        print("=" * 70)
        print(f"""
  Network:        {num_agents} agents ({len(FIXED_MINERS)} miners + {num_users} users)
  Binary v1:      {binary_v1}
  Binary v2:      {binary_v2}
  Steady state:   {steady_state}
  Upgrade order:  {upgrade_order}
  Upgrade stagger: {upgrade_stagger}
  Post-upgrade:   {post_upgrade}
  Total duration: ~{format_time_offset(timeline['total_s'], for_config=False)}
  Output file:    {output_file}
""")

        if not ask_yes_no("Generate this configuration?", default=True):
            print("\nConfiguration cancelled.")
            return 1

        # Generate the config
        print("\nGenerating configuration...")

        config, timing_info = generate_upgrade_config(
            total_agents=num_agents,
            duration=format_time_offset(timeline['total_s']),
            stagger_interval_s=5,  # User spawn stagger
            simulation_seed=seed,
            gml_path=gml_path,
            fast_mode=fast_mode,
            upgrade_binary_v1=binary_v1,
            upgrade_binary_v2=binary_v2,
            upgrade_stagger_s=parse_duration(upgrade_stagger),
            upgrade_order=upgrade_order,
            steady_state_duration_s=parse_duration(steady_state),
            post_upgrade_duration_s=parse_duration(post_upgrade),
        )

        # Generate YAML with header
        yaml_content = config_to_yaml(config)

        header = f"""# Monerosim Upgrade Scenario Configuration
# Generated by configure_upgrade.py (interactive configurator)
#
# Network: {num_agents} agents ({len(FIXED_MINERS)} miners + {num_users} users)
# Upgrade: {binary_v1} -> {binary_v2}
# Order: {upgrade_order}, stagger: {upgrade_stagger}
#
# Timeline:
#   t=0:           Miners start
#   t={format_time_offset(timeline['bootstrap_end_s'], for_config=False):10s}  Bootstrap ends, funding begins
#   t={format_time_offset(timeline['activity_start_s'], for_config=False):10s}  Steady state begins (all nodes transacting)
#   t={format_time_offset(timeline['upgrade_start_s'], for_config=False):10s}  Network upgrade begins
#   t={format_time_offset(timeline['upgrade_complete_s'], for_config=False):10s}  All nodes upgraded
#   t={format_time_offset(timeline['total_s'], for_config=False):10s}  Simulation ends

"""

        with open(output_file, 'w') as f:
            f.write(header + yaml_content + "\n")

        print(f"\nConfiguration saved to: {output_file}")
        print()
        print("To run the simulation:")
        print(f"  cargo run -- {output_file}")
        print()
        print("=" * 70)

        return 0

    except KeyboardInterrupt:
        print("\n\nCancelled.")
        return 1
    except EOFError:
        print("\n\nCancelled.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
