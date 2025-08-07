# Migration Guide: Moving to Unified Agent Architecture

This guide provides step-by-step instructions for migrating from the legacy node-based configuration to the new unified agent-based architecture in Monerosim.

## Overview of Changes

The Monerosim architecture has evolved to use a unified agent model where:

1. All network participants (miners, users, etc.) are defined as agents
2. The legacy `nodes` section is no longer used
3. Miners are defined as user agents with `is_miner: true`
4. Wallet integration is required for miners

## Benefits of the Unified Agent Architecture

- **Simplified Configuration**: One consistent way to define all network participants
- **Improved Flexibility**: More granular control over agent behavior
- **Better Resource Management**: More efficient allocation of simulation resources
- **Enhanced Realism**: More accurate modeling of cryptocurrency network behavior
- **Scalability**: Better support for large-scale simulations

## Migration Steps

### 1. Update Configuration Structure

#### Legacy Format (Deprecated)

```yaml
general:
  stop_time: "1h"

monero:
  nodes:
    - count: 3
      name: "A"
      base_commit: "shadow-complete"

agents:
  regular_users:
    count: 2
    transaction_interval: 30
    
  additional_nodes:
    count: 1
    
mining:
  block_time: 120
  number_of_mining_nodes: 3
  mining_distribution: [70, 20, 10]
```

#### New Unified Format

```yaml
general:
  stop_time: "1h"
  fresh_blockchain: true
  log_level: debug

agents:
  user_agents:
    # Mining agents
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hash_rate: "70"
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hash_rate: "20"
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hash_rate: "10"
    
    # Regular user agents
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "30"
        min_transaction_amount: "0.5"
        max_transaction_amount: "2.0"
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "30"
        min_transaction_amount: "0.5"
        max_transaction_amount: "2.0"
    
    # Additional node
    - daemon: "monerod"
  
  block_controller:
    script: "agents.block_controller"
    arguments:
      - "--interval 120"
      - "--blocks 1"
```

### 2. Migrate Mining Configuration

#### Legacy Format (Deprecated)

```yaml
mining:
  block_time: 120
  number_of_mining_nodes: 3
  mining_distribution: [70, 20, 10]
```

#### New Unified Format

```yaml
agents:
  user_agents:
    # Mining agents
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"  # Required for miners
      is_miner: true
      attributes:
        hash_rate: "70"
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hash_rate: "20"
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hash_rate: "10"
  
  block_controller:
    script: "agents.block_controller"
    arguments:
      - "--interval 120"  # Equivalent to block_time
      - "--blocks 1"
```

### 3. Migrate Regular Users

#### Legacy Format (Deprecated)

```yaml
agents:
  regular_users:
    count: 2
    transaction_interval: 30
    min_transaction_amount: 0.5
    max_transaction_amount: 2.0
```

#### New Unified Format

```yaml
agents:
  user_agents:
    # Regular user agents
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "30"
        min_transaction_amount: "0.5"
        max_transaction_amount: "2.0"
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "30"
        min_transaction_amount: "0.5"
        max_transaction_amount: "2.0"
```

### 4. Migrate Additional Nodes

#### Legacy Format (Deprecated)

```yaml
agents:
  additional_nodes:
    count: 1
```

#### New Unified Format

```yaml
agents:
  user_agents:
    # Additional node
    - daemon: "monerod"
```

### 5. Update Script References

If you have custom scripts that reference the node registry, update them to use the agent registry:

#### Legacy Code (Deprecated)

```python
node_registry_file = Path("/tmp/monerosim_shared/node_registry.json")
with open(node_registry_file, 'r') as f:
    node_registry_data = json.load(f)
```

#### New Unified Code

```python
agent_registry_file = Path("/tmp/monerosim_shared/agent_registry.json")
with open(agent_registry_file, 'r') as f:
    agent_registry_data = json.load(f)
```

## Common Migration Challenges

### 1. Hashrate Distribution

In the legacy format, mining distribution was specified as percentages in an array. In the new format, each miner specifies its own hashrate percentage:

```yaml
# Legacy
mining:
  mining_distribution: [70, 20, 10]

# New
user_agents:
  - is_miner: true
    attributes:
      hash_rate: "70"
  - is_miner: true
    attributes:
      hash_rate: "20"
  - is_miner: true
    attributes:
      hash_rate: "10"
```

### 2. Block Controller Configuration

The block controller is now explicitly defined as an agent:

```yaml
# Legacy
mining:
  block_time: 120

# New
block_controller:
  script: "agents.block_controller"
  arguments:
    - "--interval 120"
    - "--blocks 1"
```

### 3. User Agent Expansion

In the legacy format, users were defined as a group with a count. In the new format, each user is defined individually:

```yaml
# Legacy
regular_users:
  count: 2
  transaction_interval: 30

# New
user_agents:
  - user_script: "agents.regular_user"
    attributes:
      transaction_interval: "30"
  - user_script: "agents.regular_user"
    attributes:
      transaction_interval: "30"
```

## Example Configurations

For complete examples of the new unified agent architecture, see:

- `config_agents_small.yaml` - Small scale (2 users, 3 mining nodes)
- `config_agents_medium.yaml` - Medium scale (10 users, 5 mining nodes)
- `config_agents_large.yaml` - Large scale (100 users, 10 mining nodes)

## Verification

After migrating your configuration, run the verification script to ensure everything is working correctly:

```bash
./scripts/verify_refactoring.sh
```

## Backward Compatibility

For backward compatibility, Monerosim still generates a `node_registry.json` file alongside the new `agent_registry.json`. However, this is deprecated and will be removed in a future version. Please update your scripts to use the new agent registry.