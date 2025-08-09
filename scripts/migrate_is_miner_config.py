#!/usr/bin/env python3
"""
Migration script to convert YAML configurations from boolean-based to attributes-only is_miner configuration.

This script:
1. Moves is_miner: true/false from the top level to attributes: { is_miner: "true"/"false" }
2. Creates the attributes section if missing
3. Preserves all other options
4. Handles both boolean and string representations of is_miner
"""

import argparse
import logging
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, Union

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def load_yaml_file(file_path: str) -> Dict[str, Any]:
    """Load YAML file with error handling."""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {file_path}: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error loading {file_path}: {e}")
        sys.exit(1)


def save_yaml_file(data: Dict[str, Any], file_path: str) -> None:
    """Save data to YAML file with error handling."""
    try:
        # Create directory if it doesn't exist
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Successfully saved migrated configuration to {file_path}")
    except Exception as e:
        logger.error(f"Error saving YAML file {file_path}: {e}")
        sys.exit(1)


def migrate_user_agent(user_agent: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate a single user agent configuration."""
    migrated = user_agent.copy()
    
    # Check if is_miner exists at the top level
    if 'is_miner' in migrated:
        is_miner_value = migrated['is_miner']
        
        # Convert to string representation
        if isinstance(is_miner_value, bool):
            is_miner_str = "true" if is_miner_value else "false"
        elif isinstance(is_miner_value, str):
            is_miner_str = is_miner_value.lower()
        else:
            logger.warning(f"Unexpected is_miner type: {type(is_miner_value)}, converting to string")
            is_miner_str = str(is_miner_value)
        
        # Remove top-level is_miner
        del migrated['is_miner']
        
        # Create attributes section if it doesn't exist
        if 'attributes' not in migrated:
            migrated['attributes'] = {}
        
        # Add is_miner to attributes
        migrated['attributes']['is_miner'] = is_miner_str
        
        logger.info(f"Migrated is_miner to attributes: {is_miner_str}")
    
    return migrated


def migrate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate the entire configuration."""
    migrated = config.copy()
    
    # Check if agents section exists
    if 'agents' in migrated and 'user_agents' in migrated['agents']:
        user_agents = migrated['agents']['user_agents']
        if isinstance(user_agents, list):
            migrated_user_agents = []
            for i, user_agent in enumerate(user_agents):
                if isinstance(user_agent, dict):
                    logger.info(f"Migrating user agent {i+1}")
                    migrated_user_agents.append(migrate_user_agent(user_agent))
                else:
                    logger.warning(f"Skipping non-dict user agent {i+1}: {user_agent}")
                    migrated_user_agents.append(user_agent)
            
            migrated['agents']['user_agents'] = migrated_user_agents
        else:
            logger.warning("user_agents is not a list, skipping migration")
    else:
        logger.warning("No agents.user_agents section found, skipping migration")
    
    return migrated


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Migrate YAML configuration from boolean-based to attributes-only is_miner configuration"
    )
    parser.add_argument(
        'input_file',
        help="Path to input YAML configuration file"
    )
    parser.add_argument(
        'output_file',
        help="Path to output YAML configuration file"
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info(f"Starting migration from {args.input_file} to {args.output_file}")
    
    # Load input configuration
    config = load_yaml_file(args.input_file)
    
    # Migrate configuration
    migrated_config = migrate_config(config)
    
    # Save migrated configuration
    save_yaml_file(migrated_config, args.output_file)
    
    logger.info("Migration completed successfully")


if __name__ == "__main__":
    main()