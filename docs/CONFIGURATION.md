# MoneroSim Configuration Reference

This document provides a complete reference for all configuration options available in MoneroSim.

## Configuration File Format

MoneroSim uses YAML configuration files to define simulation parameters.

## Configuration Schema

### Top-Level Structure

```yaml
general:
  # General simulation parameters
  stop_time: string
  fresh_blockchain: bool (optional)
  log_level: string (optional)

network:
  # Network topology parameters
  type: string (optional)

agents:
  # Agent definitions
  user_agents: [UserAgent] (optional)
  block_controller: BlockController (optional)
  pure_script_agents: [PureScriptAgent] (optional)
```

## General Configuration

### `general.stop_time`

**Type**: `string`  
**Required**: Yes  
**Description**: Specifies how long the simulation should run.
**Format**: Human-readable time duration string (e.g., "30s", "5m", "1h").

### `general.fresh_blockchain`

**Type**: `bool`  
**Required**: No  
**Default**: `true`  
**Description**: If `true`, clears existing blockchain data before starting the simulation.

### `general.log_level`

**Type**: `string`  
**Required**: No  
**Default**: `info`  
**Description**: Sets the log level for the simulation. Options are `trace`, `debug`, `info`, `warn`, `error`.

## Network Configuration

### `network.type`

**Type**: `string`  
**Required**: No  
**Default**: `"1_gbit_switch"`  
**Description**: Defines the network topology.

## Agent Configuration

### `agents.user_agents`

**Type**: `array[UserAgent]`  
**Required**: No  
**Description**: A list of user agents to simulate.

#### UserAgent Object

```yaml
- daemon: "monerod"
  wallet: "monero-wallet-rpc" (optional)
  user_script: "agents.regular_user" (optional)
  attributes:
    is_miner: "true" (optional)
    hashrate: "50" (optional, for miners)
    transaction_interval: "60" (optional, for users)
    min_transaction_amount: "0.1" (optional, for users)
    max_transaction_amount: "1.0" (optional, for users)
```

### `agents.block_controller`

**Type**: `BlockController`  
**Required**: No  
**Description**: Configures the block controller agent.

#### BlockController Object

```yaml
script: "agents.block_controller"
arguments: (optional)
  - "--interval 120"
  - "--blocks 1"
```

### `agents.pure_script_agents`

**Type**: `array[PureScriptAgent]`  
**Required**: No  
**Description**: Agents that run a simple script without a daemon or wallet.

#### PureScriptAgent Object

```yaml
- script: "scripts.monitor"
  arguments: [] (optional)
```

## Complete Example

```yaml
general:
  stop_time: "30m"
  fresh_blockchain: true
  log_level: info

network:
  type: "1_gbit_switch"

agents:
  user_agents:
    # Miner 1
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "50"
    
    # Miner 2
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "50"

    # Regular User
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "60"
        min_transaction_amount: "0.1"
        max_transaction_amount: "1.0"

  block_controller:
    script: "agents.block_controller"
    
  pure_script_agents:
    - script: "scripts.monitor"
    - script: "scripts.sync_check"