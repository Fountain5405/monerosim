#!/usr/bin/env python3
"""
Fix Python script exit code handling in Shadow YAML configurations.

This script updates the Shadow YAML files to properly handle Python script
exit codes when executed through bash wrappers in virtual environments.
"""

import yaml
import sys
from pathlib import Path
from typing import Dict, Any, List


def fix_python_command(command: str) -> str:
    """
    Fix a Python command to properly propagate exit codes.
    
    Args:
        command: The original command string
        
    Returns:
        The fixed command string
    """
    # Check if this is a Python script execution in venv
    if "source venv/bin/activate && python" in command:
        # If the command doesn't already handle exit codes, add it
        if not command.endswith("; exit $?") and not command.endswith("|| exit $?"):
            # Remove any trailing semicolon first
            command = command.rstrip(";")
            # Add proper exit code handling
            command = f"{command} || exit $?"
    
    return command


def fix_shadow_yaml(yaml_path: Path) -> bool:
    """
    Fix Python script commands in a Shadow YAML file.
    
    Args:
        yaml_path: Path to the Shadow YAML file
        
    Returns:
        True if changes were made, False otherwise
    """
    print(f"Processing {yaml_path}...")
    
    try:
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        
        changes_made = False
        
        # Process hosts
        if 'hosts' in data:
            for host_name, host_config in data['hosts'].items():
                if 'processes' in host_config:
                    for process in host_config['processes']:
                        if 'args' in process and isinstance(process['args'], str):
                            original_args = process['args']
                            fixed_args = fix_python_command(original_args)
                            
                            if original_args != fixed_args:
                                print(f"  Fixing command for host '{host_name}':")
                                print(f"    Original: {original_args}")
                                print(f"    Fixed:    {fixed_args}")
                                process['args'] = fixed_args
                                changes_made = True
        
        if changes_made:
            # Create backup
            backup_path = yaml_path.with_suffix('.yaml.backup')
            yaml_path.rename(backup_path)
            print(f"  Created backup: {backup_path}")
            
            # Write fixed file
            with open(yaml_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            
            print(f"  Updated: {yaml_path}")
            return True
        else:
            print(f"  No changes needed for {yaml_path}")
            return False
            
    except Exception as e:
        print(f"  Error processing {yaml_path}: {e}")
        return False


def main():
    """Main function to fix Shadow YAML files."""
    shadow_output_dir = Path("shadow_output")
    
    if not shadow_output_dir.exists():
        print(f"Error: {shadow_output_dir} directory not found!")
        sys.exit(1)
    
    # Find all YAML files with Python scripts
    yaml_files = list(shadow_output_dir.glob("*python*.yaml"))
    
    if not yaml_files:
        print("No Python Shadow YAML files found!")
        sys.exit(1)
    
    print(f"Found {len(yaml_files)} Shadow YAML file(s) to check:")
    for f in yaml_files:
        print(f"  - {f}")
    print()
    
    fixed_count = 0
    for yaml_file in yaml_files:
        if fix_shadow_yaml(yaml_file):
            fixed_count += 1
    
    print(f"\nSummary: Fixed {fixed_count} of {len(yaml_files)} files")
    
    if fixed_count > 0:
        print("\nNext steps:")
        print("1. Review the changes in the updated YAML files")
        print("2. Run the simulation again with the fixed configurations")
        print("3. Verify that exit codes are now properly handled")


if __name__ == "__main__":
    main()