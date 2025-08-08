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
- **Dynamic Agent Discovery**: Agents can discover and interact with each other without hardcoded configurations using the Agent Discovery System

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

### 6. Migrate to Agent Discovery System

The unified agent architecture is enhanced by the Agent Discovery System, which provides a dynamic mechanism for agents to discover and interact with each other without hardcoded configurations.

#### Legacy Network Configuration (Deprecated)

```python
# Legacy approach using hardcoded network configurations
# Note: This approach has been removed and replaced with Agent Discovery
```

#### New Agent Discovery System

```python
# New approach using dynamic agent discovery
from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError

try:
    ad = AgentDiscovery()
    
    # Discover all wallet agents
    wallet_agents = ad.get_wallet_agents()
    if len(wallet_agents) < 2:
        print("Need at least 2 wallet agents for transactions")
        return
    
    # Discover miner agents
    miner_agents = ad.get_miner_agents()
    if not miner_agents:
        print("No miners found - transactions may not be confirmed")
    
    # Discover block controllers
    block_controllers = ad.get_block_controllers()
    
    # Use discovered agents
    sender = wallet_agents[0]
    receiver = wallet_agents[1]
    print(f"Sending transaction from {sender['agent_id']} to {receiver['agent_id']}")
    
except AgentDiscoveryError as e:
    print(f"Agent discovery error: {e}")
```

#### Benefits of Agent Discovery

- **Dynamic Discovery**: Agents automatically discover each other without hardcoded configurations
- **Flexibility**: Easy to add, remove, or modify agents without updating code
- **Resilience**: Agents can handle changes in the network topology during runtime
- **Simplified Code**: No need to manually manage network configurations in scripts

For detailed information about the Agent Discovery System, see `scripts/README_agent_discovery.md`.

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

## Migration to Agent Discovery System

As part of the migration to the unified agent architecture, we recommend also migrating to the Agent Discovery System. This system provides a more flexible and dynamic approach to agent interactions:

### Steps to Migrate to Agent Discovery

1. **Replace Legacy Configuration Imports**:
   ```python
   # New
   from scripts.agent_discovery import AgentDiscovery
   ```

2. **Update Agent Discovery Code**:
   ```python
   # New
   ad = AgentDiscovery()
   agents = ad.find_agents_by_type("user_agent")
   ```

3. **Handle Discovery Errors**:
   ```python
   from scripts.agent_discovery import AgentDiscoveryError
   
   try:
       ad = AgentDiscovery()
       agents = ad.get_wallet_agents()
   except AgentDiscoveryError as e:
       print(f"Discovery failed: {e}")
   ```

4. **Use Shared State Files**:
   The Agent Discovery System automatically reads from shared state files in `/tmp/monerosim_shared/`:
   - `agent_registry.json` - All registered agents
   - `miners.json` - Mining agent information
   - `wallets.json` - Wallet agent information
   - `block_controller.json` - Block controller status

### Example: Complete Migration

```python
# Legacy approach
# Note: This approach has been removed and replaced with Agent Discovery
def send_transaction_legacy():
    # This code has been removed - see Agent Discovery approach below
    pass

# New approach with Agent Discovery
from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError

def send_transaction_new():
    try:
        ad = AgentDiscovery()
        wallet_agents = ad.get_wallet_agents()
        
        if len(wallet_agents) < 2:
            print("Insufficient wallet agents for transaction")
            return
            
        sender = wallet_agents[0]
        receiver = wallet_agents[1]
        
        # Send transaction logic...
        print(f"Sending from {sender['agent_id']} to {receiver['agent_id']}")
        
    except AgentDiscoveryError as e:
        print(f"Agent discovery error: {e}")
```

The Agent Discovery System provides a more robust and flexible approach to agent interactions in the unified agent architecture. For more details, see `scripts/README_agent_discovery.md`.