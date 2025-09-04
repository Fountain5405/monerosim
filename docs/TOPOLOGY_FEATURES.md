# Monerosim Topology Features

## Overview

Monerosim now supports advanced topology templates for peer connections, enabling more realistic and controlled network simulations. This feature enhances both dynamic and hardcoded peer modes with intelligent seed node selection and structured network topologies.

## Topology Templates

### 1. Star Topology
- **Description**: All nodes connect to a central hub (first seed node)
- **Use Case**: Centralized network architectures, hub-and-spoke models
- **Configuration**: `topology: "Star"`
- **Requirements**: At least 2 agents
- **Peer Connections**: Each node connects only to the central hub

### 2. Mesh Topology
- **Description**: All nodes connect to all other nodes
- **Use Case**: Fully connected networks, maximum redundancy
- **Configuration**: `topology: "Mesh"`
- **Requirements**: Reasonable number of agents (≤50 recommended)
- **Peer Connections**: Each node connects to every other node

### 3. Ring Topology
- **Description**: Circular connections between nodes
- **Use Case**: Token ring networks, circular communication patterns
- **Configuration**: `topology: "Ring"`
- **Requirements**: At least 3 agents
- **Peer Connections**: Each node connects to previous and next node in ring

### 4. DAG Topology (Default)
- **Description**: Hierarchical connections (original Monerosim logic)
- **Use Case**: Traditional blockchain networks, default behavior
- **Configuration**: `topology: "Dag"`
- **Requirements**: Any number of agents
- **Peer Connections**: Nodes connect to agents with lower indices

## Configuration

### Basic Configuration
```yaml
network:
  type: "1_gbit_switch"
  peer_mode: "Hardcoded"
  topology: "Star"  # Choose: Star, Mesh, Ring, Dag
  seed_nodes: []    # Can be empty for automatic seed selection
```

### Dynamic Mode with Intelligent Seed Selection
```yaml
network:
  type: "1_gbit_switch"
  peer_mode: "Dynamic"  # Automatically selects optimal seed nodes
  topology: "Mesh"      # Topology still applies to connection patterns
```

### GML Network with Topology
```yaml
network:
  path: "testnet.gml"
  peer_mode: "Hybrid"
  topology: "Ring"
  seed_nodes: ["192.168.1.1:28080"]
```

## Intelligent Seed Node Selection

### Dynamic Mode Algorithm
When using `peer_mode: "Dynamic"` without explicit seed nodes, Monerosim automatically selects optimal seed nodes based on:

1. **Mining Capability** (100 points)
   - Agents with `is_miner: true` get highest priority
   - Higher hashrate increases score

2. **Network Centrality** (0-20 points)
   - Based on agent index in configuration
   - Earlier agents get higher centrality scores

3. **Geographic Distribution** (0-10 points)
   - Prefers agents in different IP subnets
   - Promotes network diversity

### Selection Process
- Scores all agents using the criteria above
- Selects top N agents (default: 5, configurable)
- Uses weighted random selection for fairness
- Ensures geographic and functional diversity

## Peer Mode Integration

### Dynamic Mode
- Uses intelligent seed selection when no seeds provided
- Enables DNS discovery for additional flexibility
- Topology templates still apply to connection patterns

### Hardcoded Mode
- Uses topology templates to generate structured connections
- Falls back to DAG topology if none specified
- Validates topology requirements before simulation

### Hybrid Mode
- Combines topology-based exclusive connections with peer discovery
- Uses topology for primary connections, peer mode for discovery
- Enables DNS discovery for maximum connectivity

## Validation and Error Handling

### Topology Validation
- **Star**: Requires ≥2 agents
- **Mesh**: Warns for >50 agents (performance impact)
- **Ring**: Requires ≥3 agents
- **DAG**: No restrictions (default)

### Configuration Validation
- Validates peer mode and topology compatibility
- Checks seed node requirements
- Provides clear error messages for invalid configurations

## Examples

### Star Topology Example
```yaml
network:
  type: "1_gbit_switch"
  peer_mode: "Hardcoded"
  topology: "Star"

agents:
  user_agents:
    - daemon: "monerod"  # This becomes the central hub
      attributes:
        is_miner: "true"
    - daemon: "monerod"  # Connects only to first agent
    - daemon: "monerod"  # Connects only to first agent
```

### Mesh Topology Example
```yaml
network:
  type: "1_gbit_switch"
  peer_mode: "Hardcoded"
  topology: "Mesh"

agents:
  user_agents:
    - daemon: "monerod"  # Connects to agents 2, 3, 4
    - daemon: "monerod"  # Connects to agents 1, 3, 4
    - daemon: "monerod"  # Connects to agents 1, 2, 4
    - daemon: "monerod"  # Connects to agents 1, 2, 3
```

### Dynamic Mode with Intelligent Selection
```yaml
network:
  type: "1_gbit_switch"
  peer_mode: "Dynamic"  # No seed_nodes needed

agents:
  user_agents:
    - daemon: "monerod"
      attributes:
        is_miner: "true"    # High priority seed
        hashrate: "100"
    - daemon: "monerod"
      attributes:
        is_miner: "false"   # Lower priority
    - daemon: "monerod"
      attributes:
        is_miner: "true"    # High priority seed
        hashrate: "50"
```

## Performance Considerations

### Topology Performance
- **Star**: Excellent performance, minimal connections
- **Mesh**: High connection overhead, best for small networks
- **Ring**: Moderate performance, good for circular patterns
- **DAG**: Good performance, traditional blockchain patterns

### Recommendations
- Use **Star** for large networks (>20 agents)
- Use **Mesh** only for small networks (≤10 agents)
- Use **Ring** for networks requiring circular communication
- Use **DAG** for traditional blockchain simulations

## Migration Guide

### From Previous Versions
- Existing configurations work unchanged (defaults to DAG)
- Add `topology` field to enable new features
- Dynamic mode now includes intelligent seed selection
- No breaking changes to existing functionality

### Best Practices
1. Start with small networks when testing new topologies
2. Use Dynamic mode for automatic optimization
3. Validate configurations before large simulations
4. Monitor performance with different topology sizes