#!/usr/bin/env python3
"""
Configuration Migration Utility for Independent Mining Control

Converts old block_controller-based configurations to new autonomous miner format.

Usage:
    python scripts/migrate_mining_config.py <input_config.yaml> [--output <output_config.yaml>]

Changes made:
- Removes block_controller section
- Adds mining_script to miner agents (where is_miner: true)
- Adds simulation_seed to general section if missing
- Creates backup of original file with .bak extension
"""

import sys
import argparse
import yaml
import random
from pathlib import Path
from typing import Dict, Any, List, Tuple


def is_miner_agent(agent: Dict[str, Any]) -> bool:
    """
    Check if an agent is a miner based on attributes.
    
    Args:
        agent: User agent configuration dictionary
        
    Returns:
        True if agent is a miner, False otherwise
    """
    attributes = agent.get('attributes', {})
    if not attributes:
        return False
        
    is_miner_value = attributes.get('is_miner')
    if is_miner_value is None:
        return False
        
    # Handle various boolean representations
    if isinstance(is_miner_value, bool):
        return is_miner_value
        
    # Handle string representations
    if isinstance(is_miner_value, str):
        return is_miner_value.lower() in ('true', '1', 'yes', 'on')
        
    # Handle numeric representations
    if isinstance(is_miner_value, int):
        return is_miner_value == 1
        
    return False


def validate_miner_config(agent: Dict[str, Any], agent_index: int) -> None:
    """
    Validate that a miner agent has required configuration.
    
    Args:
        agent: User agent configuration dictionary
        agent_index: Index of agent in user_agents list
        
    Raises:
        ValueError: If miner configuration is invalid
    """
    # Check for daemon
    if 'daemon' not in agent:
        raise ValueError(
            f"Agent {agent_index}: Miner agents must have 'daemon' defined"
        )
        
    # Check for wallet
    if 'wallet' not in agent:
        raise ValueError(
            f"Agent {agent_index}: Miner agents must have 'wallet' defined"
        )
        
    # Check for hashrate
    attributes = agent.get('attributes', {})
    if 'hashrate' not in attributes:
        raise ValueError(
            f"Agent {agent_index}: Miner agents must have 'hashrate' attribute"
        )


def check_already_migrated(config: Dict[str, Any]) -> bool:
    """
    Check if configuration has already been migrated to new format.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if already migrated, False otherwise
    """
    agents = config.get('agents', {})
    user_agents = agents.get('user_agents', [])
    
    # Check if any miner has mining_script
    for agent in user_agents:
        if is_miner_agent(agent) and 'mining_script' in agent:
            return True
            
    # If no block_controller and no mining_script, unclear state
    if 'block_controller' not in agents:
        # Check if there are any miners at all
        has_miners = any(is_miner_agent(agent) for agent in user_agents)
        if has_miners:
            # Miners exist but no mining_script and no block_controller - partial migration?
            return False
            
    return False


def migrate_config(config: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Migrate configuration from old to new format.
    
    Args:
        config: Original configuration dictionary
        
    Returns:
        Migrated configuration dictionary
        
    Raises:
        ValueError: If configuration is invalid or already migrated
    """
    # Deep copy to avoid modifying original
    migrated = yaml.safe_load(yaml.dump(config))
    
    # Check if already migrated
    if check_already_migrated(migrated):
        raise ValueError(
            "Configuration appears to already use new format (mining_script found). "
            "Migration not needed."
        )
    
    changes_made = []
    
    # 1. Add simulation_seed to general section if missing
    if 'general' not in migrated:
        migrated['general'] = {}
        
    general = migrated['general']
    if 'simulation_seed' not in general:
        # Generate random seed between 10000-99999
        seed = random.randint(10000, 99999)
        general['simulation_seed'] = seed
        changes_made.append(f"Added simulation_seed: {seed}")
    
    # 2. Process user_agents
    if 'agents' not in migrated:
        raise ValueError("Configuration missing 'agents' section")
        
    agents = migrated['agents']
    
    if 'user_agents' not in agents:
        raise ValueError("Configuration missing 'agents.user_agents' section")
        
    user_agents = agents['user_agents']
    miners_updated = 0
    
    for idx, agent in enumerate(user_agents):
        if is_miner_agent(agent):
            # Validate miner configuration
            validate_miner_config(agent, idx)
            
            # Add mining_script
            agent['mining_script'] = 'agents.autonomous_miner'
            miners_updated += 1
    
    if miners_updated > 0:
        changes_made.append(f"Added mining_script to {miners_updated} miner agent(s)")
    
    # 3. Remove block_controller section
    if 'block_controller' in agents:
        del agents['block_controller']
        changes_made.append("Removed block_controller section")
    
    return migrated, changes_made


def create_backup(file_path: Path) -> Path:
    """
    Create backup of original file.
    
    Args:
        file_path: Path to original file
        
    Returns:
        Path to backup file
    """
    backup_path = file_path.with_suffix(file_path.suffix + '.bak')
    
    # If backup already exists, add number suffix
    counter = 1
    while backup_path.exists():
        backup_path = file_path.with_suffix(f'{file_path.suffix}.bak{counter}')
        counter += 1
        
    # Copy original to backup
    backup_path.write_text(file_path.read_text())
    return backup_path


def main():
    """Main entry point for migration utility"""
    parser = argparse.ArgumentParser(
        description='Migrate Monerosim configuration to autonomous mining format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate config.yaml in-place (creates config.yaml.bak)
  python scripts/migrate_mining_config.py config.yaml
  
  # Migrate to new file
  python scripts/migrate_mining_config.py old_config.yaml --output new_config.yaml
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='Input configuration file path'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output configuration file path (default: overwrite input after backup)'
    )
    
    args = parser.parse_args()
    
    # Validate input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
        
    # Load configuration
    try:
        with open(input_path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"Error: Failed to parse YAML: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to read input file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Migrate configuration
    try:
        migrated_config, changes = migrate_config(config)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Migration failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Determine output path
    if args.output:
        output_path = Path(args.output)
        # Only create backup if overwriting input
        if output_path == input_path:
            backup_path = create_backup(input_path)
            print(f"✓ Created backup: {backup_path}")
    else:
        # In-place migration - create backup first
        output_path = input_path
        backup_path = create_backup(input_path)
        print(f"✓ Created backup: {backup_path}")
    
    # Write migrated configuration
    try:
        with open(output_path, 'w') as f:
            yaml.dump(migrated_config, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        print(f"Error: Failed to write output file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Print summary
    print(f"\n✓ Migration completed successfully!")
    print(f"  Input:  {input_path}")
    print(f"  Output: {output_path}")
    print(f"\nChanges made:")
    for change in changes:
        print(f"  • {change}")
    
    print(f"\nNew configuration format:")
    print(f"  - Block controller: Removed (autonomous mining)")
    print(f"  - Mining agents: Use 'agents.autonomous_miner' script")
    print(f"  - Determinism: Ensured via simulation_seed")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())