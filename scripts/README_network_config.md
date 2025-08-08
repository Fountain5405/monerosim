# Network Configuration Migration Guide

## Overview

This document provides historical guidance on the migration from the legacy `network_config.py` module (now removed) to the new dynamic Agent Discovery System (`agent_discovery.py`).

## Legacy Network Configuration (Removed)

The `network_config.py` module previously provided hardcoded network configurations with static IP addresses and ports. This module has been completely removed from the project.

**Note:** The `network_config.py` file has been permanently removed. All code must now use the Agent Discovery System.

### Why the Legacy Approach Was Removed

- **Static Configuration**: IP addresses and ports were hardcoded
- **Limited Scalability**: Required manual updates for each new agent
- **No Runtime Discovery**: Agents couldn't be discovered dynamically
- **Maintenance Overhead**: Changes required updating multiple files

## New Agent Discovery System

The new `agent_discovery.py` module provides dynamic agent discovery through shared state files:

```python
# New approach (recommended)
from scripts.agent_discovery import AgentDiscovery

# Initialize the discovery system
ad = AgentDiscovery()

# Find all miners dynamically
miners = ad.get_miner_agents()
for miner in miners:
    print(f"Miner ID: {miner['id']}, IP: {miner['ip']}")

# Find wallets with sufficient balance
wallets = ad.get_wallet_agents()
for wallet in wallets:
    print(f"Wallet ID: {wallet['id']}, Balance: {wallet['balance']}")
```

### Benefits of the New Approach

- **Dynamic Discovery**: Agents are discovered at runtime from shared state files
- **Automatic Scaling**: No manual configuration required for new agents
- **Type-Based Queries**: Find agents by type (miners, wallets, block controllers)
- **Attribute Filtering**: Filter agents based on their attributes
- **Performance Optimized**: 5-second TTL cache reduces file I/O

## Migration Steps

### 1. Replace Imports

**Before:**
```python
# Legacy approach (no longer available)
# from scripts.network_config import get_node_config, get_wallet_config
```

**After:**
```python
from scripts.agent_discovery import AgentDiscovery
```

### 2. Initialize the Discovery System

**Before:**
```python
# Direct function calls
node_config = get_node_config('A0')
wallet_config = get_wallet_config('wallet1')
```

**After:**
```python
# Initialize discovery system
ad = AgentDiscovery()

# Find agents dynamically
miners = ad.get_miner_agents()
wallets = ad.get_wallet_agents()
```

### 3. Update Agent Access Patterns

**Before:**
```python
# Access by hardcoded ID
node_ip = get_node_config('A0')['ip']
wallet_port = get_wallet_config('wallet1')['rpc_port']
```

**After:**
```python
# Find by type and attributes
miners = ad.get_miner_agents()
if miners:
    node_ip = miners[0]['ip']

wallets = ad.get_wallet_agents()
if wallets:
    wallet_port = wallets[0]['rpc_port']
```

### 4. Handle Missing Agents

**Before:**
```python
# Assume configuration exists
node_config = get_node_config('A0')
```

**After:**
```python
# Check if agents exist
miners = ad.get_miner_agents()
if not miners:
    print("No miners found")
    return

# Use first miner
miner = miners[0]
```

## Shared State Files

The Agent Discovery System reads from shared state files in `/tmp/monerosim_shared/`:

- `agent_registry.json` - Registry of all agents
- `miners.json` - Mining agent information
- `wallets.json` - Wallet agent information
- `block_controller.json` - Block controller status

These files are automatically created and updated during simulation runs.

## Code Examples

### Simple Transaction Script

**Legacy Approach:**
```python
from scripts.network_config import get_node_config, get_wallet_config # Legacy approach (no longer available)

# Get hardcoded configurations
sender_node = get_node_config('A0')
sender_wallet = get_wallet_config('wallet1')
receiver_wallet = get_wallet_config('wallet2')

# Use hardcoded values
print(f"Sending from {sender_wallet['address']} to {receiver_wallet['address']}")
```

**New Approach:**
```python
from scripts.agent_discovery import AgentDiscovery

# Initialize discovery system
ad = AgentDiscovery()

# Find agents dynamically
miners = ad.get_miner_agents()
wallets = ad.get_wallet_agents()

if len(miners) > 0 and len(wallets) >= 2:
    sender_wallet = wallets[0]
    receiver_wallet = wallets[1]
    
    print(f"Sending from {sender_wallet['address']} to {receiver_wallet['address']}")
else:
    print("Insufficient agents for transaction")
```

### Block Controller Script

**Legacy Approach:**
```python
from scripts.network_config import get_node_config # Legacy approach (no longer available)

# Get hardcoded node configuration
mining_node = get_node_config('A0')
print(f"Controlling mining node at {mining_node['ip']}")
```

**New Approach:**
```python
from scripts.agent_discovery import AgentDiscovery

# Initialize discovery system
ad = AgentDiscovery()

# Find miners dynamically
miners = ad.get_miner_agents()
for miner in miners:
    print(f"Controlling mining node {miner['id']} at {miner['ip']}")
```

## Advanced Usage

### Filtering by Attributes

```python
from scripts.agent_discovery import AgentDiscovery

ad = AgentDiscovery()

# Find miners with specific hashrate
high_hashrate_miners = [
    miner for miner in ad.get_miner_agents()
    if float(miner.get('hashrate', 0)) > 50
]

# Find wallets with sufficient balance
wealthy_wallets = [
    wallet for wallet in ad.get_wallet_agents()
    if float(wallet.get('balance', 0)) > 10.0
]
```

### Getting Agent by ID

```python
from scripts.agent_discovery import AgentDiscovery

ad = AgentDiscovery()

# Get specific agent by ID
agent = ad.get_agent_by_id('user001')
if agent:
    print(f"Found agent: {agent}")
else:
    print("Agent not found")
```

### Refreshing Cache

```python
from scripts.agent_discovery import AgentDiscovery

ad = AgentDiscovery()

# Force refresh of cached data
ad.refresh_cache()

# Get updated agent list
miners = ad.get_miner_agents()
```

## Error Handling

**Legacy Approach:**
```python
from scripts.network_config import get_node_config # Legacy approach (no longer available)

try:
    node_config = get_node_config('A0')
except KeyError:
    print("Node configuration not found")
```

**New Approach:**
```python
from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError

try:
    ad = AgentDiscovery()
    miners = ad.get_miner_agents()
except AgentDiscoveryError as e:
    print(f"Agent discovery failed: {e}")
```

## Best Practices

1. **Always Check for Agent Existence**: Never assume agents exist
2. **Handle Discovery Errors**: Use try-catch blocks for robust error handling
3. **Use Type-Based Queries**: Find agents by type rather than hardcoded IDs
4. **Leverage Attribute Filtering**: Filter agents based on their properties
5. **Cache Appropriately**: The system includes caching, but force refresh when needed

## Troubleshooting

### Common Issues

1. **No Agents Found**
   - Check if simulation is running
   - Verify shared state files exist in `/tmp/monerosim_shared/`
   - Ensure agents are properly registered

2. **Stale Agent Information**
   - Use `refresh_cache()` to force update
   - Check file timestamps in shared state directory

3. **Permission Errors**
   - Ensure read access to `/tmp/monerosim_shared/`
   - Check file permissions on shared state files

### Debug Commands

```bash
# Check if shared state directory exists
ls -la /tmp/monerosim_shared/

# Check agent registry
cat /tmp/monerosim_shared/agent_registry.json

# Test agent discovery manually
python3 -c "
from scripts.agent_discovery import AgentDiscovery
ad = AgentDiscovery()
print('Miners:', ad.get_miner_agents())
print('Wallets:', ad.get_wallet_agents())
"
```

## Conclusion

The migration from the legacy hardcoded network configuration approach to `agent_discovery.py` is complete. The legacy hardcoded network configuration approach has been permanently removed from the project. All code must now use the Agent Discovery System, which provides significant benefits in terms of scalability, maintainability, and flexibility. The new dynamic agent discovery system eliminates hardcoded configurations and enables more robust and scalable simulations.

For more detailed information about the Agent Discovery System, see [Agent Discovery System](README_agent_discovery.md).