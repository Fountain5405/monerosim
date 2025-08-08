# Unified Agent Architecture

## Overview

The Monerosim agent architecture has been simplified to create a more consistent design. The core architectural principle is now:

**Every node in the simulation is a user_agent with appropriate attributes.**

This document explains the changes made to implement this unified architecture and how to use it.

## Key Changes

### 1. Removal of 'additional_nodes'

Previously, the architecture distinguished between 'user_agents' and 'additional_nodes', which created inconsistency in the agent-based design. Both used the same `UserAgentConfig` type but were processed separately.

The new architecture removes this distinction entirely. All nodes are now user_agents with appropriate attributes.

### 2. Required Daemon for User Agents

In the new architecture, every user_agent must have a daemon. This reflects the reality that every node in the Monero network runs a daemon process.

### 3. Optional Wallet and Script

While the daemon is required, wallet and user_script remain optional, allowing for different types of nodes:

- **Full User Node**: Has daemon, wallet, and user script
- **Mining Node**: Has daemon and is_miner attribute set to true
- **Relay Node**: Has only a daemon

### 4. New 'is_miner' Attribute

A new `is_miner` attribute has been added to identify mining nodes. This attribute is used to:

- Determine if a node is a miner
- Configure appropriate port ranges
- Add the node to seed nodes list
- Set the node ID format (node### vs user###)

### 5. Agent Registry

The agent registry has been enhanced to document all attributes for every user_agent. This registry is created during simulation setup and stored in `agent_registry.json` (renamed from `node_registry.json`).

### 6. Agent Discovery System

A new dynamic Agent Discovery System has been implemented to replace hardcoded network configurations. This system provides:

- **Dynamic Discovery**: Agents are discovered at runtime through shared state files
- **Caching**: 5-second TTL cache improves performance
- **Error Handling**: Robust error handling with `AgentDiscoveryError` exceptions
- **Type-based Discovery**: Find agents by type (miners, wallets, block controllers)

The Agent Discovery System reads from shared state files in `/tmp/monerosim_shared/`:
- `agent_registry.json`: All agent information
- `miners.json`: Mining-specific information
- `wallets.json`: Wallet-specific information
- `block_controller.json`: Block controller information

For more details, see [`scripts/README_agent_discovery.md`](scripts/README_agent_discovery.md).

## Configuration Example

Here's an example of the new configuration format:

```yaml
agents:
  user_agents:
    # Regular user node
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "30"
        min_transaction_amount: "0.5"
        max_transaction_amount: "2.0"
    
    # Mining node
    - daemon: "monerod"
      is_miner: true
      attributes:
        hashrate: "100"
    
    # Relay node (daemon only)
    - daemon: "monerod"
  
  block_controller:
    script: "agents.block_controller"
  
  pure_script_agents:
    - script: "scripts.monitor"
```

## Agent Registry Structure

The agent registry is a JSON file that documents all attributes for every user_agent:

```json
{
  "agents": [
    {
      "id": "user001",
      "ip_addr": "11.0.0.10",
      "daemon": true,
      "wallet": true,
      "user_script": "agents.regular_user",
      "is_miner": false,
      "attributes": {
        "transaction_interval": "30",
        "min_transaction_amount": "0.5",
        "max_transaction_amount": "2.0"
      }
    },
    {
      "id": "node001",
      "ip_addr": "11.0.0.12",
      "daemon": true,
      "wallet": false,
      "user_script": null,
      "is_miner": true,
      "attributes": {
        "hashrate": "100"
      }
    }
  ]
}
```

## Benefits of the Unified Architecture

1. **Consistency**: All nodes follow the same configuration pattern
2. **Simplicity**: Easier to understand and maintain
3. **Flexibility**: Different node types through attributes, not separate structures
4. **Documentation**: Better documentation of node attributes in the registry
5. **Extensibility**: Easier to add new node types in the future
6. **Dynamic Discovery**: Agent Discovery System provides runtime agent discovery instead of hardcoded configurations
7. **Improved Performance**: Caching and optimized file access in the Agent Discovery System
8. **Better Error Handling**: Robust error handling with specific exceptions for agent discovery operations
9. **Enhanced Monitoring**: Better visibility into agent status through shared state files

## Migration Guide

If you have existing configurations using the old format with `additional_nodes`, you'll need to migrate them to the new format:

1. Move all entries from `additional_nodes` to `user_agents`
2. Add `is_miner: true` to nodes that should be miners
3. Ensure all nodes have the required `daemon` field

## Implementation Details

The unified architecture is implemented in:

- `src/config_v2.rs`: Updated data structures
- `src/shadow_agents.rs`: Updated processing logic
- `scripts/agent_discovery.py`: Agent Discovery System implementation
- Configuration files: Updated to use the new structure
- Documentation: Updated to reflect the simplified architecture

## Agent Discovery Integration

The Agent Discovery System is integrated into the unified architecture through:

1. **Automatic Registration**: Agents are automatically registered in shared state files
2. **Dynamic Lookup**: Scripts and agents use `AgentDiscovery` class to find other agents
3. **Type-based Queries**: Find agents by type (miners, wallets, etc.)
4. **Attribute Filtering**: Filter agents based on their attributes

### Example Usage

```python
from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError

# Initialize the discovery system
ad = AgentDiscovery()

# Find all miners
miners = ad.get_miner_agents()
for miner in miners:
    print(f"Miner {miner['id']} at {miner['ip_addr']}")

# Find wallets with sufficient balance
wallets = ad.get_wallet_agents()
for wallet in wallets:
    if wallet.get('balance', 0) > 10:
        print(f"Wallet {wallet['id']} has sufficient balance")

# Get agent by ID
agent = ad.get_agent_by_id('user001')
if agent:
    print(f"Found agent: {agent}")
```

For more detailed examples, see [`scripts/README_agent_discovery.md`](scripts/README_agent_discovery.md).

## Conclusion

The unified agent architecture creates a more consistent and maintainable design for Monerosim. By treating every node as a user_agent with appropriate attributes, we've simplified the codebase while maintaining all the functionality of the previous design.