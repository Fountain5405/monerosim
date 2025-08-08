# Agent Discovery Module Documentation

## Overview

The Agent Discovery module (`scripts/agent_discovery.py`) provides a comprehensive agent discovery system that replaces the legacy hardcoded network configuration approach. It enables dynamic agent discovery and supports scaling to hundreds of agents.

### Benefits over Legacy Approach

The legacy hardcoded network configuration approach (now removed) had several limitations:
- **Hardcoded Configuration**: All agent IP addresses, ports, and configurations were statically defined
- **Limited Scalability**: Only supported a fixed number of agents (typically 2)
- **Manual Updates**: Adding new agents required manual code changes
- **Rigid Structure**: Couldn't adapt to different simulation scenarios

The new Agent Discovery system addresses these issues with:
- **Dynamic Discovery**: Automatically discovers agents from shared state files
- **Scalability**: Supports hundreds of agents without code changes
- **Flexible Filtering**: Find agents by type, attributes, or custom criteria
- **Caching**: Efficient caching system to minimize disk I/O
- **Error Handling**: Robust error handling and recovery mechanisms

## Architecture

The Agent Discovery system reads agent information from the shared state directory (`/tmp/monerosim_shared/`) where agent registry files are stored. These files are generated during simulation initialization and updated as agents join or leave the simulation.

### Registry Files

The system reads from several JSON files in the shared state directory:
- `agent_registry.json`: Main registry containing all agents
- `miners.json`: Registry of mining agents
- `wallets.json`: Registry of wallet agents
- `block_controller.json`: Registry of block controller agents

## API Documentation

### AgentDiscovery Class

The `AgentDiscovery` class is the main interface for discovering agents in the simulation.

#### Constructor

```python
AgentDiscovery(shared_state_dir: str = "/tmp/monerosim_shared")
```

Initialize the AgentDiscovery with the shared state directory.

**Parameters:**
- `shared_state_dir`: Path to the directory containing agent registry files. Defaults to "/tmp/monerosim_shared".

**Example:**
```python
from scripts.agent_discovery import AgentDiscovery

# Use default shared state directory
discovery = AgentDiscovery()

# Use custom shared state directory
discovery = AgentDiscovery("/custom/path/to/shared/state")
```

#### Methods

##### get_agent_registry()

```python
get_agent_registry(force_refresh: bool = False) -> Dict[str, Any]
```

Load and return the agent registry from the shared state directory. This method aggregates information from all registry files and provides a unified view of all agents.

**Parameters:**
- `force_refresh`: If True, bypass the cache and reload from disk.

**Returns:**
- Dictionary containing agent registry information with the following structure:
  ```python
  {
      "agents": {},          # All agents
      "miners": {},          # Mining agents
      "wallets": {},         # Wallet agents
      "block_controllers": {}, # Block controller agents
      "last_updated": timestamp
  }
  ```

**Raises:**
- `AgentDiscoveryError`: If the registry cannot be loaded.

**Example:**
```python
from scripts.agent_discovery import AgentDiscovery

discovery = AgentDiscovery()
registry = discovery.get_agent_registry()

print(f"Total agents: {len(registry['agents'])}")
print(f"Total miners: {len(registry['miners'])}")
print(f"Total wallets: {len(registry['wallets'])}")
```

##### find_agents_by_type()

```python
find_agents_by_type(agent_type: str, force_refresh: bool = False) -> List[Dict[str, Any]]
```

Return all agents of a specific type.

**Parameters:**
- `agent_type`: The type of agents to find (e.g., "miner", "user", "wallet").
- `force_refresh`: If True, bypass the cache and reload from disk.

**Returns:**
- List of agent dictionaries matching the specified type.

**Raises:**
- `AgentDiscoveryError`: If the registry cannot be loaded.

**Example:**
```python
from scripts.agent_discovery import AgentDiscovery

discovery = AgentDiscovery()
miners = discovery.find_agents_by_type("miner")
users = discovery.find_agents_by_type("user")

print(f"Found {len(miners)} miners")
print(f"Found {len(users)} users")

# Print details of first miner
if miners:
    print(f"First miner: {miners[0]['id']} at {miners[0].get('ip_addr', 'unknown IP')}")
```

##### find_agents_by_attribute()

```python
find_agents_by_attribute(
    attribute_name: str,
    attribute_value: Any,
    force_refresh: bool = False
) -> List[Dict[str, Any]]
```

Return agents matching a specific attribute value.

**Parameters:**
- `attribute_name`: The name of the attribute to match.
- `attribute_value`: The value of the attribute to match.
- `force_refresh`: If True, bypass the cache and reload from disk.

**Returns:**
- List of agent dictionaries matching the specified attribute.

**Raises:**
- `AgentDiscoveryError`: If the registry cannot be loaded.

**Example:**
```python
from scripts.agent_discovery import AgentDiscovery

discovery = AgentDiscovery()

# Find all miners
miners = discovery.find_agents_by_attribute("is_miner", True)

# Find agents with specific hashrate
high_hashrate_miners = discovery.find_agents_by_attribute("hashrate", "50")

print(f"Found {len(miners)} miners")
print(f"Found {len(high_hashrate_miners)} high hashrate miners")
```

##### get_miner_agents()

```python
get_miner_agents(force_refresh: bool = False) -> List[Dict[str, Any]]
```

Return all agents that are miners. This method combines multiple strategies to find miners:
1. Agents with type "miner"
2. Agents with attribute "is_miner" set to True
3. Agents listed in the miners registry

**Parameters:**
- `force_refresh`: If True, bypass the cache and reload from disk.

**Returns:**
- List of miner agent dictionaries.

**Raises:**
- `AgentDiscoveryError`: If the registry cannot be loaded.

**Example:**
```python
from scripts.agent_discovery import AgentDiscovery

discovery = AgentDiscovery()
miners = discovery.get_miner_agents()

print(f"Found {len(miners)} miners")

for miner in miners:
    print(f"Miner {miner['id']}:")
    print(f"  IP: {miner.get('ip_addr', 'unknown')}")
    print(f"  RPC Port: {miner.get('daemon_rpc_port', 'unknown')}")
    print(f"  Hashrate: {miner.get('attributes', {}).get('hashrate', 'unknown')}")
```

##### get_wallet_agents()

```python
get_wallet_agents(force_refresh: bool = False) -> List[Dict[str, Any]]
```

Return all agents that have wallets. This method combines multiple strategies to find wallets:
1. Agents with type "wallet"
2. Agents with attribute "has_wallet" set to True
3. Agents listed in the wallets registry
4. Agents with wallet configuration in their data

**Parameters:**
- `force_refresh`: If True, bypass the cache and reload from disk.

**Returns:**
- List of wallet agent dictionaries.

**Raises:**
- `AgentDiscoveryError`: If the registry cannot be loaded.

**Example:**
```python
from scripts.agent_discovery import AgentDiscovery

discovery = AgentDiscovery()
wallets = discovery.get_wallet_agents()

print(f"Found {len(wallets)} wallets")

for wallet in wallets:
    print(f"Wallet {wallet['id']}:")
    print(f"  IP: {wallet.get('ip_addr', 'unknown')}")
    print(f"  RPC Port: {wallet.get('wallet_rpc_port', 'unknown')}")
    print(f"  Name: {wallet.get('wallet_name', 'unknown')}")
```

##### get_block_controllers()

```python
get_block_controllers(force_refresh: bool = False) -> List[Dict[str, Any]]
```

Return all block controller agents.

**Parameters:**
- `force_refresh`: If True, bypass the cache and reload from disk.

**Returns:**
- List of block controller agent dictionaries.

**Raises:**
- `AgentDiscoveryError`: If the registry cannot be loaded.

**Example:**
```python
from scripts.agent_discovery import AgentDiscovery

discovery = AgentDiscovery()
controllers = discovery.get_block_controllers()

print(f"Found {len(controllers)} block controllers")

for controller in controllers:
    print(f"Controller {controller['id']}:")
    print(f"  Status: {controller.get('status', 'unknown')}")
    print(f"  Last Block: {controller.get('last_block', 'unknown')}")
```

##### get_agent_by_id()

```python
get_agent_by_id(agent_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]
```

Get a specific agent by its ID.

**Parameters:**
- `agent_id`: The ID of the agent to retrieve.
- `force_refresh`: If True, bypass the cache and reload from disk.

**Returns:**
- Agent dictionary if found, None otherwise.

**Raises:**
- `AgentDiscoveryError`: If the registry cannot be loaded.

**Example:**
```python
from scripts.agent_discovery import AgentDiscovery

discovery = AgentDiscovery()
agent = discovery.get_agent_by_id("user000")

if agent:
    print(f"Found agent {agent['id']}:")
    print(f"  Type: {agent.get('type', 'unknown')}")
    print(f"  IP: {agent.get('ip_addr', 'unknown')}")
else:
    print("Agent not found")
```

##### refresh_cache()

```python
refresh_cache() -> Dict[str, Any]
```

Force refresh the agent registry cache.

**Returns:**
- Updated agent registry.

**Raises:**
- `AgentDiscoveryError`: If the registry cannot be loaded.

**Example:**
```python
from scripts.agent_discovery import AgentDiscovery

discovery = AgentDiscovery()

# Force refresh the cache
registry = discovery.refresh_cache()
print(f"Registry refreshed at {registry['last_updated']}")
```

##### get_registry_stats()

```python
get_registry_stats(force_refresh: bool = False) -> Dict[str, Any]
```

Get statistics about the agent registry.

**Parameters:**
- `force_refresh`: If True, bypass the cache and reload from disk.

**Returns:**
- Dictionary containing registry statistics with the following structure:
  ```python
  {
      "total_agents": int,
      "total_miners": int,
      "total_wallets": int,
      "total_block_controllers": int,
      "last_updated": timestamp,
      "cache_time": timestamp,
      "cache_valid": bool,
      "agent_types": Dict[str, int]  # Count of agents by type
  }
  ```

**Raises:**
- `AgentDiscoveryError`: If the registry cannot be loaded.

**Example:**
```python
from scripts.agent_discovery import AgentDiscovery

discovery = AgentDiscovery()
stats = discovery.get_registry_stats()

print(f"Total agents: {stats['total_agents']}")
print(f"Total miners: {stats['total_miners']}")
print(f"Total wallets: {stats['total_wallets']}")
print(f"Cache valid: {stats['cache_valid']}")
print(f"Agent types: {stats['agent_types']}")
```

### Convenience Functions

The module also provides convenience functions for direct usage without creating an AgentDiscovery instance:

```python
# Get agent registry
registry = get_agent_registry()

# Find agents by type
miners = find_agents_by_type("miner")

# Find agents by attribute
high_hashrate_miners = find_agents_by_attribute("hashrate", "50")

# Get miner agents
miners = get_miner_agents()

# Get wallet agents
wallets = get_wallet_agents()
```

## Agent Registry Format

The agent registry files use JSON format with the following structure:

### agent_registry.json

```json
{
  "agents": [
    {
      "id": "user000",
      "type": "miner",
      "ip_addr": "11.0.0.10",
      "daemon_rpc_port": 28081,
      "wallet_rpc_port": 28082,
      "attributes": {
        "is_miner": true,
        "hashrate": "25"
      }
    },
    {
      "id": "user001",
      "type": "user",
      "ip_addr": "11.0.0.11",
      "daemon_rpc_port": 28081,
      "wallet_rpc_port": 28082,
      "attributes": {
        "transaction_interval": "60",
        "min_transaction_amount": "0.5",
        "max_transaction_amount": "2.0"
      }
    }
  ]
}
```

### miners.json

```json
{
  "miners": [
    {
      "id": "user000",
      "ip_addr": "11.0.0.10",
      "daemon_rpc_port": 28081,
      "wallet_rpc_port": 28082,
      "hashrate": "25"
    }
  ]
}
```

### wallets.json

```json
{
  "wallets": [
    {
      "id": "user000",
      "ip_addr": "11.0.0.10",
      "wallet_rpc_port": 28082,
      "wallet_name": "mining_wallet"
    },
    {
      "id": "user001",
      "ip_addr": "11.0.0.11",
      "wallet_rpc_port": 28082,
      "wallet_name": "recipient_wallet"
    }
  ]
}
```

### block_controller.json

```json
{
  "block_controllers": [
    {
      "id": "block_controller",
      "status": "active",
      "last_block": 100,
      "miners_controlled": ["user000", "user001"]
    }
  ]
}
```

## Migration Examples

### From Legacy Hardcoded Network Configuration

The legacy approach (now removed) used hardcoded configuration:

```python
# Legacy approach (no longer available)
# from scripts.network_config import A0_IP, A0_RPC_PORT, WALLET1_IP, WALLET1_RPC_PORT

# Use hardcoded values
# daemon_rpc = f"http://{A0_IP}:{A0_RPC_PORT}/json_rpc"
# wallet_rpc = f"http://{WALLET1_IP}:{WALLET1_RPC_PORT}/json_rpc"
```

With the new Agent Discovery system:

```python
# New approach
from scripts.agent_discovery import AgentDiscovery

discovery = AgentDiscovery()

# Get first miner
miners = discovery.get_miner_agents()
if miners:
    miner = miners[0]
    daemon_rpc = f"http://{miner['ip_addr']}:{miner['daemon_rpc_port']}/json_rpc"
    
    # Get wallet for the same miner
    wallets = discovery.get_wallet_agents()
    for wallet in wallets:
        if wallet['id'] == miner['id']:
            wallet_rpc = f"http://{wallet['ip_addr']}:{wallet['wallet_rpc_port']}/json_rpc"
            break
```

### Complex Migration Example

For more complex scenarios, like finding a miner with specific attributes:

```python
# Legacy approach (would require manual code changes - no longer available)
# from scripts.network_config import A0_IP, A0_RPC_PORT

# Only works with hardcoded miner
# miner_rpc = f"http://{A0_IP}:{A0_RPC_PORT}/json_rpc"
```

With the new system:

```python
# New approach (dynamic and flexible)
from scripts.agent_discovery import AgentDiscovery

discovery = AgentDiscovery()

# Find miner with specific hashrate
high_hashrate_miners = discovery.find_agents_by_attribute("hashrate", "50")

if high_hashrate_miners:
    # Use the first high hashrate miner
    miner = high_hashrate_miners[0]
    miner_rpc = f"http://{miner['ip_addr']}:{miner['daemon_rpc_port']}/json_rpc"
    print(f"Using miner {miner['id']} with hashrate {miner['attributes']['hashrate']}")
else:
    # Fallback to any miner
    miners = discovery.get_miner_agents()
    if miners:
        miner = miners[0]
        miner_rpc = f"http://{miner['ip_addr']}:{miner['daemon_rpc_port']}/json_rpc"
        print(f"Using fallback miner {miner['id']}")
```

## Error Handling

The Agent Discovery module provides robust error handling through the `AgentDiscoveryError` exception class.

### Basic Error Handling

```python
from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError

try:
    discovery = AgentDiscovery()
    miners = discovery.get_miner_agents()
    print(f"Found {len(miners)} miners")
except AgentDiscoveryError as e:
    print(f"Agent discovery failed: {e}")
    # Handle the error appropriately
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Advanced Error Handling with Fallbacks

```python
from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError

def get_miner_with_fallback():
    """Get a miner with multiple fallback strategies."""
    try:
        discovery = AgentDiscovery()
        
        # Try to get miners normally
        miners = discovery.get_miner_agents()
        if miners:
            return miners[0]
        
        # Try to force refresh cache
        miners = discovery.get_miner_agents(force_refresh=True)
        if miners:
            return miners[0]
        
        # Try to find by attribute
        miners = discovery.find_agents_by_attribute("is_miner", True)
        if miners:
            return miners[0]
        
        # No miners found
        raise AgentDiscoveryError("No miners found in registry")
        
    except AgentDiscoveryError as e:
        print(f"Error discovering miners: {e}")
        # Return a default configuration for testing
        return {
            "id": "default_miner",
            "ip_addr": "11.0.0.10",
            "daemon_rpc_port": 28081,
            "wallet_rpc_port": 28082
        }
```

## Best Practices

### 1. Use Caching Wisely

The Agent Discovery system includes a caching mechanism to improve performance. By default, the cache is valid for 5 seconds.

```python
# Good: Use default caching
discovery = AgentDiscovery()
miners = discovery.get_miner_agents()

# Good: Force refresh when you need the latest data
miners = discovery.get_miner_agents(force_refresh=True)

# Good: Explicitly refresh cache when needed
discovery.refresh_cache()
miners = discovery.get_miner_agents()
```

### 2. Handle Empty Results Gracefully

Always check if the returned lists are empty before using them.

```python
discovery = AgentDiscovery()
miners = discovery.get_miner_agents()

if not miners:
    print("No miners found in registry")
    # Handle the case where no miners are available
    return

# Use the first miner
miner = miners[0]
```

### 3. Use Specific Methods When Possible

Use the specific methods (`get_miner_agents`, `get_wallet_agents`) instead of generic filtering when possible, as they may use optimized strategies.

```python
# Good: Use specific method
miners = discovery.get_miner_agents()

# Also good, but less optimized
miners = discovery.find_agents_by_type("miner")

# Also good, but less optimized
miners = discovery.find_agents_by_attribute("is_miner", True)
```

### 4. Check for Required Fields

Agent data may vary, so always check for required fields before using them.

```python
discovery = AgentDiscovery()
miners = discovery.get_miner_agents()

for miner in miners:
    # Check for required fields
    ip_addr = miner.get("ip_addr")
    rpc_port = miner.get("daemon_rpc_port")
    
    if not ip_addr or not rpc_port:
        print(f"Miner {miner['id']} missing required fields")
        continue
    
    # Use the fields
    rpc_url = f"http://{ip_addr}:{rpc_port}/json_rpc"
```

## Performance Considerations

### Caching

The Agent Discovery system uses a time-based cache (TTL) to minimize disk I/O operations. The cache is valid for 5 seconds by default.

```python
# Cache statistics
stats = discovery.get_registry_stats()
print(f"Cache valid: {stats['cache_valid']}")
print(f"Cache time: {stats['cache_time']}")
```

### Large Simulations

For large simulations with hundreds of agents:

1. **Minimize Refresh Operations**: Avoid unnecessary cache refreshes
2. **Use Specific Queries**: Use specific methods instead of loading the entire registry
3. **Process in Batches**: Process agents in batches if possible

```python
# Good for large simulations
discovery = AgentDiscovery()

# Get only what you need
miners = discovery.get_miner_agents()
wallets = discovery.get_wallet_agents()

# Avoid loading the entire registry if not needed
# registry = discovery.get_agent_registry()  # Avoid for large simulations
```

### Memory Usage

The Agent Discovery system loads registry data into memory. For very large simulations, consider:

1. **Processing Results Immediately**: Process results as soon as you get them
2. **Avoid Storing Large Lists**: Don't store large agent lists in memory for extended periods
3. **Use Generators**: Consider processing agents one at a time

```python
# Process agents one at a time
discovery = AgentDiscovery()
miners = discovery.get_miner_agents()

for miner in miners:
    # Process each miner immediately
    process_miner(miner)
    # Don't store the entire list in memory
```

## Troubleshooting

### Common Issues

#### 1. Agent Registry Not Found

**Symptom**: `AgentDiscoveryError: Failed to load agent registry: [Errno 2] No such file or directory: '/tmp/monerosim_shared/agent_registry.json'`

**Cause**: The simulation hasn't been started or the shared state directory doesn't exist.

**Solution**:
```python
try:
    discovery = AgentDiscovery()
    miners = discovery.get_miner_agents()
except AgentDiscoveryError as e:
    print(f"Agent registry not found. Make sure the simulation is running.")
    # Create default configuration for testing
    miners = get_default_miners()
```

#### 2. Empty Agent Lists

**Symptom**: Agent discovery methods return empty lists even though agents should exist.

**Cause**: The registry files might be empty or corrupted.

**Solution**:
```python
discovery = AgentDiscovery()

# Try to force refresh the cache
miners = discovery.get_miner_agents(force_refresh=True)

if not miners:
    print("No miners found even after refresh")
    # Check registry stats
    stats = discovery.get_registry_stats(force_refresh=True)
    print(f"Registry stats: {stats}")
```

#### 3. Missing Required Fields

**Symptom**: KeyError when accessing agent fields.

**Cause**: Agent data structure varies or fields are missing.

**Solution**:
```python
discovery = AgentDiscovery()
miners = discovery.get_miner_agents()

for miner in miners:
    # Use get() with default values
    ip_addr = miner.get("ip_addr", "unknown")
    rpc_port = miner.get("daemon_rpc_port", "28081")
    
    print(f"Miner at {ip_addr}:{rpc_port}")
```

#### 4. JSON Parse Errors

**Symptom**: `AgentDiscoveryError: Invalid JSON in registry file /tmp/monerosim_shared/agent_registry.json`

**Cause**: Registry file is corrupted or contains invalid JSON.

**Solution**:
```python
try:
    discovery = AgentDiscovery()
    miners = discovery.get_miner_agents()
except AgentDiscoveryError as e:
    if "Invalid JSON" in str(e):
        print("Registry file is corrupted. Try restarting the simulation.")
        # Remove corrupted file
        import os
        try:
            os.remove("/tmp/monerosim_shared/agent_registry.json")
            print("Removed corrupted registry file")
        except:
            pass
    else:
        raise
```

### Debugging

The Agent Discovery system includes detailed logging that can help with debugging:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

discovery = AgentDiscovery()
miners = discovery.get_miner_agents()
```

You can also check the registry directly:

```python
discovery = AgentDiscovery()

# Check registry stats
stats = discovery.get_registry_stats()
print(f"Registry stats: {stats}")

# Get raw registry
registry = discovery.get_agent_registry()
print(f"Raw registry: {registry}")
```

## FAQ

### Q: How do I add a new agent type to the discovery system?

A: The Agent Discovery system automatically discovers all agents in the registry. You don't need to modify the discovery system to support new agent types. Just ensure your agents are properly registered in the shared state files.

### Q: Can I use the Agent Discovery system outside of Shadow simulations?

A: Yes, you can use the Agent Discovery system anywhere you have access to the shared state directory. You can even create your own registry files for testing.

### Q: How often is the registry updated?

A: The registry is updated by the simulation system as agents join or leave. The Agent Discovery system caches the registry data for 5 seconds by default to improve performance.

### Q: What happens if the registry files are deleted during a simulation?

A: The Agent Discovery system will continue to use the cached data until the cache expires. After that, it will attempt to reload the files and may return empty results if the files are missing.

### Q: Can I modify the cache TTL?

A: Currently, the cache TTL is fixed at 5 seconds. If you need different behavior, you can either force refresh with `force_refresh=True` or modify the `cache_ttl` attribute of the AgentDiscovery instance.

### Q: How do I handle the case where no agents are found?

A: Always check if the returned lists are empty and handle that case appropriately. You might want to use default values, show an error message, or wait for agents to become available.

```python
miners = discovery.get_miner_agents()

if not miners:
    print("No miners available. Waiting...")
    # Wait and retry
    time.sleep(5)
    miners = discovery.get_miner_agents(force_refresh=True)
```

### Q: Can I use the Agent Discovery system with the legacy hardcoded network configuration?

A: No, the legacy hardcoded network configuration approach has been completely removed. The Agent Discovery system is the exclusive method for agent configuration and discovery.

### Q: How do I get the IP address and port for a specific agent?

A: Use the `get_agent_by_id()` method to get the agent data, then extract the IP address and port fields:

```python
agent = discovery.get_agent_by_id("user000")
if agent:
    ip_addr = agent.get("ip_addr")
    rpc_port = agent.get("daemon_rpc_port")
    rpc_url = f"http://{ip_addr}:{rpc_port}/json_rpc"
```

### Q: What's the difference between agent type and agent attributes?

A: Agent type is a high-level classification (e.g., "miner", "user", "wallet"), while attributes are key-value pairs that provide additional details about an agent (e.g., "hashrate": "25", "is_miner": true).

### Q: How do I find agents with multiple attributes?

A: You can chain multiple calls to `find_agents_by_attribute()` or filter the results manually:

```python
# Find miners with high hashrate
miners = discovery.find_agents_by_attribute("is_miner", True)
high_hashrate_miners = [m for m in miners if m.get("attributes", {}).get("hashrate", "0") > "50"]
```

## Conclusion

The Agent Discovery module provides a powerful, flexible, and scalable system for discovering agents in MoneroSim simulations. It replaces the legacy hardcoded configuration approach with a dynamic system that can handle simulations of any size.

By following the best practices and guidelines in this documentation, you can effectively use the Agent Discovery system to build robust and scalable simulation scripts that adapt to different simulation scenarios.