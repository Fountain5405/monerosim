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

The agent registry has been enhanced to document all attributes for every user_agent. This registry is created during simulation setup and stored in `node_registry.json`.

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

## Migration Guide

If you have existing configurations using the old format with `additional_nodes`, you'll need to migrate them to the new format:

1. Move all entries from `additional_nodes` to `user_agents`
2. Add `is_miner: true` to nodes that should be miners
3. Ensure all nodes have the required `daemon` field

## Implementation Details

The unified architecture is implemented in:

- `src/config_v2.rs`: Updated data structures
- `src/shadow_agents.rs`: Updated processing logic
- Configuration files: Updated to use the new structure
- Documentation: Updated to reflect the simplified architecture

## Conclusion

The unified agent architecture creates a more consistent and maintainable design for Monerosim. By treating every node as a user_agent with appropriate attributes, we've simplified the codebase while maintaining all the functionality of the previous design.