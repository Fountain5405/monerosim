# Migration Script for is_miner Configuration

This document describes the migration script for converting YAML configurations from boolean-based to attributes-only `is_miner` configuration in Monerosim.

## Overview

The `migrate_is_miner_config.py` script converts Monerosim configuration files from the old format (with `is_miner` at the top level) to the new format (with `is_miner` inside the `attributes` section).

## Migration Details

### Before Migration (Old Format)
```yaml
agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "25"
```

### After Migration (New Format)
```yaml
agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "25"
```

## Usage

### Basic Usage
```bash
python3 scripts/migrate_is_miner_config.py input.yaml output.yaml
```

### With Verbose Logging
```bash
python3 scripts/migrate_is_miner_config.py input.yaml output.yaml --verbose
```

## Features

1. **Moves is_miner to attributes**: The script moves `is_miner: true/false` from the top level to `attributes: { is_miner: "true"/"false" }`

2. **Creates attributes section if missing**: If the `attributes` section doesn't exist, it will be created.

3. **Preserves all other options**: All other configuration options are preserved unchanged.

4. **Handles multiple data types**: The script handles both boolean and string representations of `is_miner`.

5. **Comprehensive error handling**: The script includes robust error handling and logging.

## Testing

The migration script includes a comprehensive test suite that can be run with:

```bash
python3 scripts/test_migrate_is_miner_config.py
```

The test suite verifies:
- Migration of configurations with top-level `is_miner`
- Preservation of configurations already in the desired format
- Creation of `attributes` section when missing
- Preservation of existing attributes
- Handling of different data types for `is_miner`
- Proper handling of configurations without user agents

## Examples

### Example 1: Basic Migration
```bash
# Migrate config_that_works.yaml to the new format
python3 scripts/migrate_is_miner_config.py config_that_works.yaml config_that_works_migrated.yaml
```

### Example 2: Already Migrated Configuration
```bash
# Running the script on a configuration that's already in the desired format
python3 scripts/migrate_is_miner_config.py config_in_desired_attributes_style_but_doesnt_work.yaml config_in_desired_attributes_style_migrated.yaml
```

## Requirements

The script requires the following Python packages:
- PyYAML (>= 6.0)

These can be installed with:
```bash
pip install -r scripts/requirements.txt
```

## Phase 1 Completion

This script represents Phase 1 of the complete transition from boolean-based to attributes-only `is_miner` configuration in Monerosim. Future phases may include:
- Integration with the main Monerosim application
- Automated migration as part of the build process
- Deprecation and removal of the old configuration format