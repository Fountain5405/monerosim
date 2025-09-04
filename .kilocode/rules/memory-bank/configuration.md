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
  peer_mode: "Dynamic"   # Peer discovery mode: "Dynamic", "Hardcoded", "Hybrid"
  topology: "Mesh"       # Network topology: "Star", "Mesh", "Ring", "Dag"
  seed_nodes: []         # Optional explicit seed nodes for Hardcoded/Hybrid modes

agents:
  user_agents:
    # Miner example
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"  # Required for miners
      attributes:
        is_miner: true # Boolean indicator (true/false, "true"/"false", "1"/"0", "yes"/"no", "on"/"off")
        hashrate: "25"  # Percentage of total hashrate
        can_receive_distributions: true  # Distribution eligibility

    # Regular user example
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "60"
        min_transaction_amount: "0.5"
        max_transaction_amount: "2.0"
        can_receive_distributions: false  # Distribution eligibility

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

## Peer Discovery Configuration

### Peer Modes

Monerosim supports three peer discovery modes that control how agents connect to each other:

1. **Dynamic Mode**:
   - **Description**: Intelligent seed selection with miners prioritized as seeds
   - **Best for**: Research, optimization, realism
   - **When to use**: When you want automatic seed selection
   - **Pros**: Intelligent, adaptive, no manual configuration
   - **Cons**: Less predictable, may vary between runs

2. **Hardcoded Mode**:
   - **Description**: Explicit peer connections based on topology templates
   - **Best for**: Testing, validation, reproducibility
   - **When to use**: When you need exact control over connections
   - **Pros**: Predictable, reproducible, explicit
   - **Cons**: Manual configuration required

3. **Hybrid Mode**:
   - **Description**: Combines structure with discovery for complex networks
   - **Best for**: Production-like simulations
   - **When to use**: When combining structure with discovery
   - **Pros**: Robust, flexible, realistic
   - **Cons**: More complex configuration

### Network Topologies

Four topology templates are available:

1. **Star Topology**:
   - All nodes connect to a central hub (first agent)
   - Best for: Hierarchical networks, central authority
   - Minimum agents: 2

2. **Mesh Topology**:
   - Every node connects to every other node
   - Best for: Maximum redundancy, fully connected behavior
   - Minimum agents: 2 (but scales poorly >50 agents)

3. **Ring Topology**:
   - Nodes connect in circular pattern
   - Best for: Structured but distributed connections
   - Minimum agents: 3

4. **DAG Topology**:
   - Traditional blockchain behavior (default)
   - Best for: Standard cryptocurrency networks
   - Minimum agents: 2

### Seed Nodes Configuration

For Hardcoded and Hybrid modes, you can optionally specify explicit seed nodes:

```yaml
network:
  peer_mode: "Hardcoded"
  topology: "Star"
  seed_nodes:
    - "192.168.1.10:28080"
    - "192.168.1.11:28080"
```

## Distribution Eligibility

The `can_receive_distributions` attribute controls whether agents can receive mining reward distributions:

- **true/1/yes/on**: Agent can receive distributions
- **false/0/no/off**: Agent cannot receive distributions

This attribute supports multiple formats for flexibility in configuration.

## Important Notes

1. **Wallet Requirement**: All miners must have both a daemon and a wallet to enable the block controller to get addresses for mining rewards
2. **No Nodes Section**: Never use a `nodes` section in configuration files
3. **IP Assignment**: IP addresses are automatically assigned by the system
4. **Port Configuration**: Standard ports are used for all services
5. **Peer Mode Compatibility**: Dynamic mode doesn't use seed_nodes; Hardcoded/Hybrid modes can use them
6. **Topology Requirements**: Some topologies require minimum agent counts

## Example Configurations

- `config_custom_miners.yaml`: Custom miner configuration with specific hashrate distribution
- `config.yaml`: Standard configuration for general testing