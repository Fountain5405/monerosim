# Monerosim Configuration System

## Current Configuration Approach

Monerosim now uses a unified agent-based configuration system that no longer makes a distinction between nodes and agents. This is a significant architectural change from previous versions.

### Key Configuration Principles

1. **Unified Agent Model**: All network participants (miners, users, etc.) are defined as agents
2. **No Separate Node Configuration**: The legacy `nodes` section is no longer used
3. **User Agents with Attributes**: Miners are defined as user agents with `is_miner: true`
4. **Wallet Integration**: Miners require both daemon and wallet components

## Configuration Structure

```yaml
general:
  stop_time: "3h"  # Duration of simulation
  fresh_blockchain: true
  log_level: info

network:
  type: "1_gbit_switch"  # Network topology

agents:
  user_agents:
    # Miner example
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"  # Required for miners
      attributes:
        is_miner: true # Boolean indicator (true/false, "true"/"false", "1"/"0", "yes"/"no", "on"/"off")
        hashrate: "25"  # Percentage of total hashrate
    
    # Regular user example
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "60"
        min_transaction_amount: "0.5"
        max_transaction_amount: "2.0"

  block_controller:
    script: "agents.block_controller"
    
  pure_script_agents:
    - script: "scripts.monitor"
    - script: "scripts.sync_check"
```

## Hashrate Distribution

When configuring miners, the `hashrate` attribute defines the percentage of the total network hashrate allocated to that miner. The sum of all miner hashrates should equal 100.

Example distribution:
- Miner 1: 25%
- Miner 2: 25%
- Miner 3: 20%
- Miner 4: 20%
- Miner 5: 10%

## Important Notes

1. **Wallet Requirement**: All miners must have both a daemon and a wallet to enable the block controller to get addresses for mining rewards
2. **No Nodes Section**: Never use a `nodes` section in configuration files
3. **IP Assignment**: IP addresses are automatically assigned by the system
4. **Port Configuration**: Standard ports are used for all services

## Example Configurations

- `config_custom_miners.yaml`: Custom miner configuration with specific hashrate distribution
- `config.yaml`: Standard configuration for general testing