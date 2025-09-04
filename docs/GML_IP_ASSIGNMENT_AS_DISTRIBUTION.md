# GML-Based Network IP Assignment and AS-Aware Distribution

## Overview

Monerosim supports complex network topologies through Graph Modeling Language (GML) files, enabling realistic simulation of cryptocurrency networks across multiple autonomous systems. The GML integration provides sophisticated IP assignment and agent distribution mechanisms that reflect real-world network architectures.

## IP Assignment Logic

### Priority-Based IP Assignment

The IP assignment follows a three-tier priority system:

#### 1. GML Node Attributes (Highest Priority)
If a GML node contains IP address attributes, those are used directly:

```gml
node [ id 0 AS "65001" ip "192.168.1.100" ]
node [ id 1 AS "65001" ip_addr "10.0.0.50" ]
node [ id 2 AS "65002" address "172.16.0.25" ]
```

**Supported attribute keys:**
- `ip` (primary)
- `ip_addr`
- `address`
- `ip_address`

#### 2. AS-Aware Subnet Assignment (Medium Priority)
If no IP is specified in GML attributes, the system assigns IPs based on the node's Autonomous System (AS) number using predefined subnets:

| AS Number | Subnet Range | Starting IP |
|-----------|--------------|-------------|
| 65001 | 10.0.0.0/24 | 10.0.0.10 |
| 65002 | 192.168.0.0/24 | 192.168.0.10 |
| 65003 | 172.16.0.0/24 | 172.16.0.10 |

```gml
graph [
  node [ id 0 AS "65001" ]  # Will get 10.0.0.10
  node [ id 1 AS "65001" ]  # Will get 10.0.0.11
  node [ id 2 AS "65002" ]  # Will get 192.168.0.10
  node [ id 3 AS "65002" ]  # Will get 192.168.0.11
]
```

#### 3. Sequential Fallback (Lowest Priority)
For nodes without AS attributes or when using switch-based topologies:

```rust
format!("11.0.0.{}", counter)  // 11.0.0.10, 11.0.0.11, etc.
```

### IP Validation

All IP addresses undergo validation using Rust's standard library:

- **IPv4 and IPv6 support**: Both address formats are supported
- **Format validation**: Ensures proper IP address syntax
- **Duplicate prevention**: System prevents duplicate IP assignments
- **Range checking**: Validates IP addresses are within valid ranges

## AS-Aware Agent Distribution

### Autonomous System Detection

The system automatically detects and groups nodes by AS number:

```rust
// Supports both "AS" and "as" attributes
node [ id 0 AS "65001" ]
node [ id 1 as "65002" ]  // Also valid
```

### Distribution Algorithm

#### Multi-AS Distribution
When multiple AS groups exist, agents are distributed proportionally based on the number of nodes in each AS:

```rust
// Example: 6 agents distributed across 3 AS groups
AS 65001: [Node 0, Node 1] (2 nodes) -> Agents [0, 1] (2 agents)
AS 65002: [Node 2] (1 node) -> Agents [2] (1 agent)
AS 65003: [Node 3] (1 node) -> Agents [3] (1 agent)
No-AS: [Node 4] (1 node) -> Agents [4] (1 agent)
No-AS: [Node 5] (1 node) -> Agents [5] (1 agent)
```

#### Single-AS Distribution
When only one AS group exists, simple round-robin distribution is used:

```rust
All nodes in single AS -> Round-robin agent assignment
```

#### No-AS Distribution
When no AS attributes are present, agents are distributed across all nodes:

```rust
Nodes [0, 1, 2, 3] -> Agents distributed evenly
```

## Configuration Examples

### Basic GML Configuration

```yaml
general:
  stop_time: "10m"
  fresh_blockchain: true

network:
  path: "topology.gml"

agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "50"
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        transaction_interval: "30"
```

### GML Topology File

```gml
graph [
  # Multi-AS topology
  node [ id 0 AS "65001" label "US-West" bandwidth "1000Mbit" ]
  node [ id 1 AS "65001" label "US-East" bandwidth "500Mbit" ]
  node [ id 2 AS "65002" label "EU-Central" bandwidth "200Mbit" ]
  node [ id 3 AS "65002" label "EU-North" bandwidth "100Mbit" ]

  # Inter-AS connections
  edge [ source 0 target 2 latency "100ms" bandwidth "100Mbit" ]
  edge [ source 1 target 3 latency "80ms" bandwidth "200Mbit" ]

  # Intra-AS connections
  edge [ source 0 target 1 latency "20ms" bandwidth "1Gbit" ]
  edge [ source 2 target 3 latency "10ms" bandwidth "500Mbit" ]
]
```

### Pre-assigned IP Configuration

```gml
graph [
  # Nodes with pre-assigned IPs
  node [ id 0 AS "65001" ip "10.0.0.100" label "Miner-Node" ]
  node [ id 1 AS "65001" ip "10.0.0.101" label "User-Node-1" ]
  node [ id 2 AS "65002" ip "192.168.0.100" label "User-Node-2" ]

  # Connections
  edge [ source 0 target 1 latency "10ms" bandwidth "1Gbit" ]
  edge [ source 1 target 2 latency "50ms" bandwidth "100Mbit" ]
]
```

## Implementation Details

### Core Components

#### AsSubnetManager
Manages IP allocation within AS-specific subnets:

```rust
struct AsSubnetManager {
    subnet_counters: HashMap<String, u8>,
}
```

**Features:**
- Tracks IP allocation per AS
- Automatic subnet assignment
- Prevents IP conflicts within AS
- Extensible for additional AS numbers

#### IP Assignment Function
Main IP assignment logic with fallback chain:

```rust
fn get_agent_ip(
    agent_index: usize,
    network_node_id: u32,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    subnet_manager: &mut AsSubnetManager,
    next_ip: &mut u8,
) -> String
```

### Network Topology Validation

Before IP assignment, the system validates:

1. **Node ID uniqueness**: No duplicate node IDs
2. **Edge validity**: All edges reference existing nodes
3. **Connectivity**: Warns about disconnected networks
4. **Attribute validation**: Validates bandwidth and latency formats

### Agent Registry Generation

The system generates comprehensive registries:

#### Agent Registry (`agent_registry.json`)
```json
{
  "agents": [
    {
      "id": "user000",
      "ip_addr": "10.0.0.10",
      "daemon": true,
      "wallet": true,
      "user_script": "agents.regular_user",
      "attributes": {
        "is_miner": "true",
        "hashrate": "50"
      },
      "wallet_rpc_port": 28082,
      "daemon_rpc_port": 28081
    }
  ]
}
```

#### Miner Registry (`miners.json`)
```json
{
  "miners": [
    {
      "ip_addr": "10.0.0.10",
      "wallet_address": null,
      "weight": 50
    }
  ]
}
```

## Troubleshooting

### Common Issues

#### 1. IP Address Conflicts
**Symptoms:** Multiple agents assigned same IP
**Causes:**
- Insufficient subnet range for number of agents
- AS subnet counter overflow
- Sequential IP counter overflow

**Solutions:**
- Increase subnet size (currently /24)
- Add more AS numbers to configuration
- Reduce number of agents per AS

#### 2. AS Detection Failures
**Symptoms:** Agents not distributed across AS groups
**Causes:**
- Incorrect AS attribute names
- Mixed case in AS numbers
- Missing AS attributes

**Solutions:**
- Use consistent AS attribute names (`AS` or `as`)
- Ensure AS numbers are strings in GML
- Verify AS attributes are present for distribution

#### 3. GML Parsing Errors
**Symptoms:** Invalid GML topology errors
**Causes:**
- Malformed GML syntax
- Invalid node/edge references
- Unsupported GML features

**Solutions:**
- Validate GML syntax with external tools
- Check for valid node IDs in edges
- Use only supported GML features

### Debugging Tools

#### IP Assignment Verification
```bash
# Check agent registry for IP conflicts
cat /tmp/monerosim_shared/agent_registry.json | jq '.agents[].ip_addr' | sort | uniq -c

# Verify AS distribution
cat /tmp/monerosim_shared/agent_registry.json | jq '.agents[] | select(.attributes.is_miner == "true") | .ip_addr'
```

#### Network Topology Analysis
```bash
# Analyze GML structure
python3 -c "
import json
with open('topology.gml', 'r') as f:
    # Parse and analyze GML structure
    pass
"
```

## Performance Considerations

### Scalability Limits

| Topology Type | Max Nodes | Performance Impact |
|---------------|-----------|-------------------|
| Single AS | 254 | Minimal |
| Multi-AS (3 AS) | 762 | Moderate |
| Large GML | 1000+ | High |

### Optimization Strategies

1. **Subnet Sizing**: Use appropriate subnet masks for agent counts
2. **AS Distribution**: Balance agents across multiple AS groups
3. **IP Reuse**: Consider IP reuse patterns for large simulations
4. **Caching**: Cache GML parsing results for repeated runs

## Future Enhancements

### Planned Features

1. **Dynamic Subnet Allocation**
   - Automatic subnet size calculation
   - IPv6 support expansion
   - Custom subnet ranges per AS

2. **Advanced Distribution Algorithms**
   - Geographic load balancing
   - Bandwidth-aware distribution
   - Latency-optimized placement

3. **Network Simulation Features**
   - Packet loss simulation
   - Bandwidth throttling
   - Dynamic topology changes

### Extension Points

The IP assignment system is designed for extensibility:

- **Custom IP allocation strategies**: Implement new allocation algorithms
- **Additional subnet types**: Support for IPv6, custom ranges
- **Network-aware distribution**: Consider network properties in agent placement
- **Dynamic reconfiguration**: Support for topology changes during simulation

## Testing and Validation

### Comprehensive Test Suite

The GML IP assignment and AS-aware distribution functionality is thoroughly tested with a comprehensive test suite comprising **30 regression tests** and **12 unit tests**:

```bash
# Run all GML regression tests
cargo test --test gml_regression_tests

# Run all unit tests (including GML parser tests)
cargo test
```

### Test Coverage Overview

#### Regression Tests (`gml_regression_tests.rs`) - 30 Tests
- **IP Address Management**: Format validation, range generation, subnet management
- **AS-Aware Distribution**: Single-AS, multi-AS, and no-AS scenarios
- **GML Parsing**: Complex attributes, error handling, malformed file detection
- **Network Topology**: Validation, connectivity checks, realistic network modeling
- **Performance**: Large-scale distribution (up to 1000 agents), timing validation
- **Configuration**: End-to-end YAML processing, validation
- **Edge Cases**: Subnet exhaustion, IP conflicts, mixed case attributes

#### Unit Tests (`src/gml_parser.rs`) - 12 Tests
- **GML Parsing**: Simple and complex graph structures
- **Node/Edge Processing**: Attribute handling, ID validation
- **Autonomous Systems**: Detection and grouping algorithms
- **Topology Validation**: Duplicate detection, connectivity validation
- **Backward Compatibility**: Legacy format support
- **IP Utilities**: Validation, formatting, range generation, private IP detection

### Test Categories

#### 1. Core Functionality Tests
- IP address assignment (GML attributes, AS-aware subnets, fallback)
- Agent distribution algorithms (proportional, round-robin, single/multi-AS)
- Autonomous system detection and grouping

#### 2. Validation and Error Handling Tests
- GML syntax validation
- Network topology validation
- IP address format validation
- Subnet range exhaustion handling
- Malformed input error handling

#### 3. Performance and Scalability Tests
- Large topology handling (100+ nodes)
- High agent count distribution (1000+ agents)
- Performance timing validation
- Memory efficiency validation

#### 4. Integration Tests
- End-to-end configuration processing
- Realistic network topology modeling
- Shadow configuration generation compatibility

#### 5. Edge Case and Boundary Tests
- Empty graphs and topologies
- Single node scenarios
- Maximum subnet utilization
- Mixed attribute formats (case sensitivity)

### Recent Improvements

**Version 2.0+ Enhancements:**
- Fixed proportional agent distribution algorithm for accurate AS-aware distribution
- Improved autonomous system detection to handle nodes without AS attributes
- Added overflow protection in IP address assignment
- Enhanced error handling for malformed GML files
- Added comprehensive edge case testing
- Expanded test coverage from 25 to 30 regression tests

**Key Fixes:**
- **Agent Distribution**: Fixed algorithm to properly distribute agents proportionally across AS groups based on node count
- **AS Detection**: Enhanced to include nodes without AS attributes as separate groups
- **IP Assignment**: Added bounds checking to prevent overflow and invalid IP assignments
- **Subnet Management**: Improved exhaustion handling for large-scale simulations
- **Test Coverage**: Added integration tests, performance tests, and comprehensive error handling tests

## References

- [GML Grammar Specification](https://en.wikipedia.org/wiki/Graph_Modelling_Language)
- [Autonomous System Numbers](https://en.wikipedia.org/wiki/Autonomous_system_(Internet))
- [Shadow Network Simulator Documentation](https://shadow.github.io/)
- [Monerosim Architecture](../docs/ARCHITECTURE.md)