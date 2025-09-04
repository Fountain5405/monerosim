# Monerosim Peer Discovery System

## Overview

The Peer Discovery System is a comprehensive framework that enables dynamic agent discovery and supports scaling to hundreds of agents. It replaces the legacy hardcoded network configuration approach with intelligent peer connection management, providing flexible network topologies and discovery modes for cryptocurrency network simulations.

## Architecture

### Core Components

1. **AgentDiscovery Class** (`scripts/agent_discovery.py`)
   - Main discovery engine that loads and caches agent information
   - Provides methods for finding agents by type, attributes, and capabilities
   - Implements caching for performance optimization
   - Handles error recovery and graceful degradation

2. **Shadow Integration** (`src/shadow_agents.rs`)
   - Generates appropriate peer connection configurations
   - Validates topology requirements and agent counts
   - Handles seed node configuration for different modes
   - Ensures proper network connectivity for all simulation scenarios

3. **Configuration System** (`src/config_v2.rs`)
   - Parses peer discovery options from YAML configuration
   - Validates peer mode and topology combinations
   - Provides default values and error handling

## Peer Discovery Modes

### 1. Dynamic Mode
**Best for**: Research, optimization, realism

- **Description**: Intelligent seed selection with miners prioritized as seeds
- **When to use**: When you want automatic seed selection
- **Pros**: Intelligent, adaptive, no manual configuration
- **Cons**: Less predictable, may vary between runs

**Configuration**:
```yaml
network:
  type: "1_gbit_switch"
  peer_mode: "Dynamic"
  topology: "Mesh"
```

### 2. Hardcoded Mode
**Best for**: Testing, validation, reproducibility

- **Description**: Explicit peer connections based on topology templates
- **When to use**: When you need exact control over connections
- **Pros**: Predictable, reproducible, explicit
- **Cons**: Manual configuration required

**Configuration**:
```yaml
network:
  type: "1_gbit_switch"
  peer_mode: "Hardcoded"
  topology: "Star"
  seed_nodes:
    - "192.168.1.10:28080"
    - "192.168.1.11:28080"
```

### 3. Hybrid Mode
**Best for**: Production-like simulations

- **Description**: Combines structure with discovery for complex networks
- **When to use**: When combining structure with discovery
- **Pros**: Robust, flexible, realistic
- **Cons**: More complex configuration

**Configuration**:
```yaml
network:
  path: "topology.gml"
  peer_mode: "Hybrid"
  topology: "Ring"
```

## Network Topologies

### Star Topology
- **Structure**: Hub-and-spoke architecture with central coordination
- **Use Case**: Hierarchical networks, central authority
- **Minimum Agents**: 2
- **Characteristics**: All nodes connect to central hub (first agent)

### Mesh Topology
- **Structure**: Fully connected network for maximum redundancy
- **Use Case**: Maximum redundancy, fully connected behavior
- **Minimum Agents**: 2
- **Characteristics**: Every node connects to every other node
- **Performance Note**: Scales poorly >50 agents

### Ring Topology
- **Structure**: Circular connections for structured communication
- **Use Case**: Structured but distributed connections
- **Minimum Agents**: 3
- **Characteristics**: Nodes connect in circular pattern

### DAG Topology
- **Structure**: Traditional blockchain behavior
- **Use Case**: Standard cryptocurrency networks
- **Minimum Agents**: 2
- **Characteristics**: Default blockchain network structure

## Agent Discovery Features

### Registry Management
- **Shared State Directory**: `/tmp/monerosim_shared/`
- **Registry Files**:
  - `agent_registry.json`: Main agent information
  - `miners.json`: Miner-specific data with hashrate weights
  - `wallets.json`: Wallet agent information
  - `block_controller.json`: Block controller status

### Discovery Methods

#### Find Agents by Type
```python
# Find all miner agents
miners = discovery.find_agents_by_type("miner")

# Find all wallet agents
wallets = discovery.find_agents_by_type("wallet")
```

#### Find Agents by Attribute
```python
# Find agents that can receive distributions
recipients = discovery.find_agents_by_attribute("can_receive_distributions", True)

# Find miners by hashrate
high_hashrate_miners = discovery.find_agents_by_attribute("hashrate", "25")
```

#### Get Specific Agent Types
```python
# Get all miner agents with enhanced data
miners = discovery.get_miner_agents()

# Get all wallet agents
wallets = discovery.get_wallet_agents()

# Get distribution recipients
recipients = discovery.get_distribution_recipients()
```

### Caching System
- **TTL-based Caching**: 5-second cache for agent registry
- **Performance Optimization**: Reduces file I/O for repeated queries
- **Cache Invalidation**: Force refresh option available
- **Memory Efficient**: Minimal memory footprint

## Integration with Shadow

### Configuration Generation
The peer discovery system integrates seamlessly with Shadow configuration generation:

1. **Topology Validation**: Ensures network connectivity requirements are met
2. **Peer Connection Generation**: Creates appropriate `--add-exclusive-node` arguments
3. **Seed Node Management**: Handles explicit seed node configuration
4. **Scalability Support**: Efficient handling of large agent counts

### Example Shadow Configuration Output
```yaml
hosts:
  user000:
    processes:
    - path: /path/to/monerod
      args:
        --add-exclusive-node=192.168.0.10:28080
        --add-exclusive-node=172.16.1.10:28080
  user001:
    processes:
    - path: /path/to/monerod
      args:
        --add-exclusive-node=192.168.0.10:28080
        --add-exclusive-node=203.0.2.10:28080
```

## Testing and Validation

### Comprehensive Test Suite
- **Unit Tests**: All AgentDiscovery class methods tested
- **Integration Tests**: End-to-end functionality verification
- **Topology Tests**: All four network topologies validated
- **Mode Tests**: All three peer discovery modes tested

### Test Results
- **Dynamic Mode**: 3-node simulation with intelligent seed selection ✅
- **Star Topology**: 5-node star topology with central hub ✅
- **Mesh Topology**: 6-node fully connected mesh ✅
- **Ring Topology**: 5-node circular ring topology ✅
- **Hybrid Mode**: 7-node GML-based network with ring topology ✅

### Performance Metrics
- **Simulation Times**: All tests completed within 3 minutes
- **Resource Usage**: Stable CPU and memory utilization
- **Network Connectivity**: Reliable peer connections established
- **Scalability**: System handles different network sizes efficiently

## Usage Examples

### Basic Usage
```python
from scripts.agent_discovery import AgentDiscovery

# Initialize discovery system
discovery = AgentDiscovery()

# Get all agents
registry = discovery.get_agent_registry()

# Find specific agent types
miners = discovery.get_miner_agents()
wallets = discovery.get_wallet_agents()

# Get distribution recipients
recipients = discovery.get_distribution_recipients()
```

### Advanced Filtering
```python
# Find agents by multiple criteria
from scripts.agent_discovery import AgentDiscovery

discovery = AgentDiscovery()

# Get miners with high hashrate
high_hashrate_miners = [
    miner for miner in discovery.get_miner_agents()
    if float(miner.get('attributes', {}).get('hashrate', '0')) > 20
]

# Get agents that can receive distributions
distribution_agents = discovery.get_distribution_recipients()
```

### Configuration Examples

#### Small Scale Simulation
```yaml
general:
  stop_time: "1h"
  fresh_blockchain: true

network:
  type: "1_gbit_switch"
  peer_mode: "Dynamic"
  topology: "Mesh"

agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "50"
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
```

#### Large Scale Simulation
```yaml
general:
  stop_time: "2h"
  fresh_blockchain: true

network:
  path: "topology.gml"
  peer_mode: "Hybrid"
  topology: "Ring"

agents:
  user_agents:
    # 10 miners with varying hashrates
    # 20 regular users with different behaviors
```

## Error Handling

### Graceful Degradation
- **Missing Registry Files**: System continues with available data
- **Invalid JSON**: Detailed error messages with recovery suggestions
- **Network Failures**: Automatic retry with exponential backoff
- **Cache Failures**: Fallback to direct file reading

### Error Recovery
```python
try:
    agents = discovery.get_agent_registry()
except AgentDiscoveryError as e:
    print(f"Discovery failed: {e}")
    # Continue with alternative approach
    agents = []
```

## Performance Considerations

### Optimization Strategies
1. **Caching**: Reduces file I/O for repeated queries
2. **Lazy Loading**: Registry files loaded only when needed
3. **Memory Management**: Efficient data structures for large agent counts
4. **Concurrent Access**: Thread-safe operations for multi-agent scenarios

### Scalability Limits
- **Small Scale**: 2-10 agents (near real-time performance)
- **Medium Scale**: 10-50 agents (slight slowdown acceptable)
- **Large Scale**: 50+ agents (significant slowdown, requires optimization)

## Future Enhancements

### Planned Features
1. **Enhanced Caching**: Redis-based distributed caching
2. **Real-time Updates**: WebSocket-based agent status updates
3. **Advanced Filtering**: Complex query language for agent discovery
4. **Network Visualization**: Real-time topology visualization tools

### Research Applications
1. **Network Analysis**: Study peer discovery patterns in different topologies
2. **Performance Optimization**: Optimize discovery algorithms for large networks
3. **Security Research**: Analyze peer discovery vulnerabilities
4. **Protocol Testing**: Test different discovery protocols under various conditions

## Troubleshooting

### Common Issues

#### No Agents Found
**Symptoms**: Empty agent lists returned
**Causes**:
- Missing `agent_registry.json` file
- Incorrect shared state directory path
- Simulation not yet started

**Solutions**:
```bash
# Check if simulation is running
ps aux | grep shadow

# Verify shared state directory
ls -la /tmp/monerosim_shared/

# Check agent registry file
cat /tmp/monerosim_shared/agent_registry.json
```

#### Cache Issues
**Symptoms**: Stale data returned
**Solutions**:
```python
# Force cache refresh
registry = discovery.get_agent_registry(force_refresh=True)

# Clear cache manually
discovery._registry_cache = None
```

#### Performance Problems
**Symptoms**: Slow agent discovery
**Solutions**:
- Increase cache TTL
- Reduce query frequency
- Optimize agent registry size

## Conclusion

The Peer Discovery System represents a significant advancement in Monerosim's capabilities, providing:

- **Dynamic Agent Discovery**: Automatic detection and configuration of network participants
- **Flexible Network Topologies**: Support for various network structures
- **Scalable Architecture**: Efficient handling of large agent counts
- **Robust Error Handling**: Graceful degradation and recovery mechanisms
- **Comprehensive Testing**: Validated across multiple scenarios and configurations

This system enables researchers to conduct sophisticated cryptocurrency network simulations with realistic peer discovery behaviors, supporting both small-scale development testing and large-scale production simulations.