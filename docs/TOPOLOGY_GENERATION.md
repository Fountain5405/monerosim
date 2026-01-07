# Topology Generation Technical Documentation

This document provides technical details about the large-scale topology generation system in Monerosim, including algorithms, file formats, and integration points.

## Architecture

The topology generation system is designed for efficiency and scalability, using streaming I/O and memory-efficient algorithms to handle thousands of nodes.

### Core Components

#### 1. Node Generation Algorithm
- **Geographic Distribution**: Nodes are distributed across 6 continents using weighted probabilities
- **IP Allocation**: Pre-allocates IPv4 addresses in geographic ranges (192.168.x.x for simulation)
- **Coordinate Assignment**: Assigns latitude/longitude coordinates for each continent
- **Memory Efficient**: Generates nodes in batches to minimize memory usage

#### 2. Edge Generation Algorithm
- **Preferential Attachment**: Uses Barabási-Albert model for realistic network structure
- **Connectivity Guarantee**: Ensures the graph remains connected through periodic connectivity checks
- **Degree Distribution**: Maintains power-law degree distribution typical of internet topologies
- **Streaming Output**: Writes edges directly to file to handle large graphs

#### 3. IP Allocation System
- **Geographic Mapping**: Maps continents to IP address ranges
  - North America: 192.168.1.0/16
  - Europe: 192.168.2.0/16
  - Asia: 192.168.3.0/16
  - South America: 192.168.4.0/16
  - Africa: 192.168.5.0/16
  - Oceania: 192.168.6.0/16
- **Conflict Prevention**: Ensures unique IP addresses across all nodes
- **Sparse Allocation**: Reserves space for future expansion

### Data Flow

```
Input Parameters → Node Generation → IP Allocation → Edge Generation → GML Output
      ↓               ↓              ↓              ↓              ↓
   --nodes        Geographic      Continent      Preferential   Streaming
   --seed         Distribution    Mapping       Attachment     Writer
   --avg-degree   Coordinates     Validation    Connectivity   Validation
   --output       Memory Batch    Uniqueness    Guarantee      File
```

### Memory Management

- **Batch Processing**: Nodes generated in chunks of 1000 to limit memory usage
- **Streaming I/O**: Edges written directly to file without storing in memory
- **Garbage Collection**: Periodic cleanup of temporary data structures
- **Peak Memory**: <2GB for 5000 nodes through efficient algorithms

## File Format

The topology generator outputs Graph Modeling Language (GML) files optimized for network simulation.

### GML Structure

```gml
graph [
  # Graph-level attributes
  directed 0
  name "large_scale_topology"

  # Node definitions with geographic attributes
  node [
    id 0
    label "node_0"
    ip "192.168.1.1"
    region "North America"
    latitude 40.7128
    longitude -74.0060
  ]

  # Edge definitions with network attributes
  edge [
    source 0
    target 1
    latency "50ms"
    bandwidth "100Mbit"
    packet_loss "0.0%"
  ]
]
```

### Required Node Attributes

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `id` | Integer | Unique node identifier | `0` |
| `label` | String | Human-readable name | `"node_0"` |
| `ip` | String | Pre-allocated IP address | `"192.168.1.1"` |
| `region` | String | Geographic continent | `"North America"` |
| `latitude` | Float | Geographic latitude | `40.7128` |
| `longitude` | Float | Geographic longitude | `-74.0060` |

### Required Edge Attributes

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `source` | Integer | Source node ID | `0` |
| `target` | Integer | Target node ID | `1` |
| `latency` | String | Link latency | `"50ms"` |
| `bandwidth` | String | Link bandwidth | `"100Mbit"` |
| `packet_loss` | String | Packet loss percentage | `"0.0%"` |

### Optional Attributes

- **Graph Level**: `name`, `description`, `generator_version`
- **Node Level**: `asn` (Autonomous System Number), `city`, `country`
- **Edge Level**: `cost`, `reliability`, `jitter`

### Validation Rules

1. **Node ID Uniqueness**: All node IDs must be unique integers starting from 0
2. **IP Uniqueness**: All IP addresses must be unique within the topology
3. **Edge Validity**: Source and target IDs must reference existing nodes
4. **Connectivity**: The graph must be connected (single component)
5. **Attribute Format**: Latency, bandwidth, and packet_loss must follow specified formats

## Performance Characteristics

### Time Complexity

| Operation | Complexity | 1000 nodes | 5000 nodes | 10000 nodes |
|-----------|------------|------------|------------|-------------|
| Node Generation | O(n) | <1s | <5s | <10s |
| IP Allocation | O(n) | <0.5s | <2s | <4s |
| Edge Generation | O(n × d) | <2s | <8s | <15s |
| Connectivity Check | O(n + e) | <1s | <3s | <6s |
| **Total** | **O(n × d)** | **<4.5s** | **<18s** | **<35s** |

Where:
- n = number of nodes
- d = average degree (typically 4)
- e = number of edges (n × d / 2)

### Memory Usage Patterns

```
Memory Usage Over Time
     ^
2GB -|                        ____
     |                       /    \
1GB -|                      /      \
     |                     /        \
500MB-|                    /          \
     |                   __/            \
     |__________________/                \____
     0    Node Gen    IP Alloc   Edge Gen   Done
         Time →
```

- **Peak Usage**: Occurs during edge generation phase
- **Optimization**: Streaming I/O prevents storing all edges in memory
- **Cleanup**: Automatic garbage collection between phases

### Scaling Metrics

| Node Count | File Size | Memory Peak | Generation Time | Connectivity |
|------------|-----------|-------------|-----------------|--------------|
| 1000      | ~5MB     | <500MB     | <1 minute      | 100%        |
| 5000      | ~25MB    | <2GB       | <5 minutes     | 100%        |
| 10000     | ~50MB    | <4GB       | <15 minutes    | 100%        |

### Optimization Strategies

1. **Batch Processing**: Process nodes in chunks to reduce memory pressure
2. **Streaming Output**: Write edges directly to disk instead of buffering
3. **Lazy Evaluation**: Generate coordinates and IPs on-demand
4. **Parallel Processing**: Use multiple threads for independent operations
5. **Memory Pool**: Reuse allocated objects to reduce GC pressure

## Integration with Monerosim

### GML Parser Integration

The topology generation system integrates with Monerosim's GML parser (`src/gml_parser.rs`) through:

1. **Pre-allocated IP Detection**: Parser recognizes `ip` attributes on nodes
2. **Geographic Metadata**: Extracts region and coordinate information
3. **Validation**: Ensures pre-allocated IPs are valid and unique
4. **Sparse Placement**: Uses geographic distribution for agent placement

### Shadow Configuration Generation

Integration with `src/orchestrator.rs`:

1. **IP Reuse**: Uses pre-allocated IPs from GML nodes instead of generating new ones
2. **Geographic Awareness**: Places agents considering geographic distribution
3. **Sparse Mapping**: Maps agents to GML nodes efficiently (e.g., 1000 agents on 5000 nodes)
4. **Network Topology**: Translates GML edges to Shadow network configuration

### Agent Placement Algorithm

```
Sparse Agent Placement Process
1. Load GML topology with pre-allocated IPs
2. Extract node list with geographic information
3. Sort nodes by region for balanced distribution
4. Assign agents using round-robin within regions
5. Generate Shadow host configurations with assigned IPs
6. Create agent registry with geographic metadata
```

### Configuration Flow

```yaml
# User Configuration
network:
  path: "topology_5k.gml"

# Monerosim Processing
1. Parse GML → Extract 5000 nodes with IPs
2. Place 100 agents → Assign to 100 random nodes
3. Generate Shadow config → Use assigned IPs
4. Create registries → Include geographic data
```

### Error Handling

- **Missing IP Attributes**: Fallback to dynamic IP allocation
- **Invalid IP Format**: Validation with clear error messages
- **Connectivity Issues**: Warning for disconnected graphs
- **Region Mismatches**: Graceful handling of unknown regions

## API Reference

### Command Line Interface

```bash
python scripts/create_large_scale_gml.py [OPTIONS]

Options:
  --output PATH          Output GML file path (required)
  --nodes INTEGER        Number of nodes to generate (default: 1000)
  --avg-degree INTEGER   Average connections per node (default: 4)
  --seed INTEGER         Random seed for reproducibility
  --validate             Validate output file after generation
  --quiet                Suppress progress messages
  --help                 Show help message
```

### Python API

```python
from scripts.create_large_scale_gml import TopologyGenerator

# Create generator instance
generator = TopologyGenerator()

# Generate topology
generator.generate_topology(
    output_path="topology.gml",
    num_nodes=5000,
    avg_degree=4,
    random_seed=42
)

# Validate generated file
is_valid = generator.validate_topology("topology.gml")
```

### Configuration Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `num_nodes` | int | 1000 | 100-10000 | Number of nodes to generate |
| `avg_degree` | int | 4 | 2-10 | Average connections per node |
| `random_seed` | int | None | Any | Seed for reproducible generation |
| `continent_weights` | dict | Balanced | 0.0-1.0 | Geographic distribution weights |

## Implementation Details

### Algorithm Pseudocode

```
function generate_topology(num_nodes, avg_degree, seed):
    # Initialize random number generator
    rng = Random(seed)
    
    # Generate nodes with geographic distribution
    nodes = []
    for i in 0..num_nodes-1:
        region = select_region(rng, continent_weights)
        coords = generate_coordinates(region, rng)
        ip = allocate_ip(region, i)
        nodes.append(Node(i, region, coords, ip))
    
    # Generate edges using preferential attachment
    edges = []
    degrees = [0] * num_nodes
    
    # Ensure minimum connectivity
    for i in 1..min_connectivity:
        connect_initial_nodes(edges, degrees, rng)
    
    # Add remaining edges
    while len(edges) < (num_nodes * avg_degree) / 2:
        source = select_node_preferential(degrees, rng)
        target = select_node_preferential(degrees, rng)
        if not connected(source, target):
            add_edge(edges, degrees, source, target)
    
    # Write GML file
    write_gml_file(nodes, edges, output_path)
```

### Geographic Coordinate Generation

```python
def generate_coordinates(region, rng):
    """Generate realistic coordinates for a continent"""
    bounds = CONTINENT_BOUNDS[region]
    lat = rng.uniform(bounds['lat_min'], bounds['lat_max'])
    lon = rng.uniform(bounds['lon_min'], bounds['lon_max'])
    return lat, lon

CONTINENT_BOUNDS = {
    "North America": {"lat_min": 15, "lat_max": 75, "lon_min": -170, "lon_max": -50},
    "Europe": {"lat_min": 35, "lat_max": 70, "lon_min": -10, "lon_max": 40},
    # ... other continents
}
```

### Connectivity Validation

```python
def ensure_connectivity(nodes, edges):
    """Ensure the graph is connected using Union-Find"""
    uf = UnionFind(len(nodes))
    
    for edge in edges:
        uf.union(edge.source, edge.target)
    
    # If not connected, add missing edges
    components = uf.get_components()
    if len(components) > 1:
        connect_components(components, edges)
```

## Testing and Validation

### Unit Tests

- **Node Generation**: Validates geographic distribution and IP uniqueness
- **Edge Generation**: Ensures connectivity and degree distribution
- **File Output**: Verifies GML format compliance
- **Performance**: Benchmarks generation time and memory usage

### Integration Tests

- **Monerosim Parsing**: Tests GML loading and IP extraction
- **Shadow Generation**: Validates configuration generation with pre-allocated IPs
- **Simulation Execution**: End-to-end testing with small topologies

### Validation Scripts

```bash
# Validate GML file format
python scripts/validate_gml.py topology.gml

# Test connectivity
python scripts/test_connectivity.py topology.gml

# Benchmark generation
python scripts/benchmark_generation.py --nodes 5000
```

## Future Enhancements

### Planned Features

1. **Real Internet Data**: Integration with CAIDA topology data
2. **Dynamic Properties**: Time-varying network conditions
3. **Multi-Modal Networks**: Support for different network types
4. **Advanced Routing**: BGP-aware path simulation
5. **Quality Metrics**: Network centrality and robustness analysis

### Performance Improvements

1. **GPU Acceleration**: Parallel generation on GPU
2. **Distributed Generation**: Multi-machine topology creation
3. **Compressed Storage**: Efficient storage for large topologies
4. **Incremental Updates**: Modify existing topologies

### Research Applications

1. **Network Resilience**: Study failure propagation in large networks
2. **Geographic Effects**: Analyze latency impact on consensus
3. **Scalability Limits**: Determine maximum simulation sizes
4. **Protocol Comparison**: Compare different P2P algorithms at scale