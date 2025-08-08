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

MoneroSim's configuration system works in conjunction with the [`agent_discovery.py`](scripts/agent_discovery.md) module to provide dynamic agent discovery during simulation. The YAML configuration defines the initial agent setup, while the agent discovery system enables agents to dynamically find and interact with each other during runtime.

### `agents.user_agents`

**Type**: `array[UserAgent]`
**Required**: No
**Description**: A list of user agents to simulate. These agents will be automatically registered with the agent discovery system at runtime.

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
**Description**: Configures the block controller agent. The block controller is automatically discoverable by other agents through the agent discovery system.

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
**Description**: Agents that run a simple script without a daemon or wallet. These agents can also be discovered by other agents through the agent discovery system.

#### PureScriptAgent Object

```yaml
- script: "scripts.monitor"
  arguments: [] (optional)
```

## Agent Discovery Integration

The configuration system integrates with the [`agent_discovery.py`](scripts/agent_discovery.md) module to provide dynamic agent discovery during simulation:

- **Automatic Registration**: All agents defined in the configuration are automatically registered in the shared state files (`/tmp/monerosim_shared/agent_registry.json`)
- **Dynamic Discovery**: Agents can discover each other at runtime using the `AgentDiscovery` class
- **Agent Classification**: Agents are automatically classified by type (miners, users, wallets, block controllers)
- **Shared State**: Agent information is stored in shared JSON files for coordination between agents

For more details on using the agent discovery system, see [`scripts/README_agent_discovery.md`](scripts/README_agent_discovery.md).

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