# Network Scaling Guide

This guide provides comprehensive information about Monerosim's network scaling feature, which enables large-scale cryptocurrency network simulations with thousands of nodes and geographically distributed agents.

## Overview

The network scaling feature allows you to create and simulate large-scale Monero networks with the following capabilities:

### Key Features
- **CAIDA-Based Topologies**: Generate GML network topologies using real CAIDA AS-links data for authentic internet topology simulation
- **Three-Tier Scaling**: Intelligent scaling algorithms (BFS for small networks, high-degree prioritization for medium, hierarchical sampling for large)
- **Geographic Distribution**: Pre-allocated IP addresses across 6 continents (North America, Europe, Asia, Africa, South America, Oceania)
- **AS Relationship Semantics**: Preserve customer-provider, peer-peer, and sibling relationships from CAIDA data
- **Sparse Agent Placement**: Place hundreds of agents on thousands of network nodes efficiently
- **Performance Optimized**: Generate 5000-node topologies in <5 minutes using <2GB memory
- **Deterministic Generation**: Reproducible topologies using random seeds
- **Shadow Integration**: Seamless integration with Shadow network simulator

### Performance Characteristics
- **Generation Time**: <5 minutes for 5000 nodes
- **Memory Usage**: <2GB peak memory for topology generation
- **Simulation Scale**: Supports 1000+ agents on 5000+ node topologies
- **IP Allocation**: Pre-allocated geographic IPs prevent conflicts

### Use Cases
- Research into large-scale cryptocurrency network behavior
- Geographic distribution analysis
- Network resilience testing
- Protocol performance evaluation at scale

## Quick Start

This section provides a minimal example to get you started with network scaling.

### Generate a Large-Scale Topology

```bash
# Generate a 5000-node topology using CAIDA AS-links data
python gml_processing/create_large_scale_caida_gml.py \
  --caida-file gml_processing/caida_aslinks.txt \
  --output topology_5k_caida.gml \
  --nodes 5000
```

Expected output:
```
Loading CAIDA AS-links data...
Found 12345 AS relationships
Selecting 5000 ASes using hierarchical sampling...
Applying geographic IP allocation...
Adding relationship-based edge attributes...
Validating connectivity...
Topology saved to topology_5k_caida.gml (5000 nodes, 18750 edges)
Total time: 4.2s
```

### Create Agent Configuration

Create a configuration file `config_large_scale.yaml`:

```yaml
general:
  stop_time: "1h"
  fresh_blockchain: true

network:
  path: "topology_5k.gml"  # Use the generated GML file
  peer_mode: "Dynamic"
  topology: "Mesh"

agents:
  user_agents:
    # 10 miners
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "10"
        can_receive_distributions: true
    # 90 regular users (sparse placement on 5000 nodes)
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "300"
        can_receive_distributions: false
      count: 90  # This will create 90 instances

  block_controller:
    script: "agents.block_controller"
```

### Generate Shadow Configuration

```bash
# Build Monerosim if needed
cargo build --release

# Generate Shadow configuration
./target/release/monerosim --config config_large_scale.yaml
```

Expected output:
```
Loading configuration from config_large_scale.yaml...
Parsing GML topology: topology_5k.gml...
Found 5000 nodes with pre-allocated IPs
Placing 100 agents sparsely across topology...
Generating Shadow configuration...
Configuration saved to shadow_output/shadow_agents.yaml
```

### Run Simulation

```bash
# Clean previous data
rm -rf shadow.data shadow.log

# Run simulation in background
nohup shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &
```

Monitor progress:
```bash
tail shadow.log
```

## Step-by-Step Tutorial

This tutorial walks through creating and running a large-scale simulation step by step.

### Step 1: Generate Large-Scale Topology

The CAIDA-based topology generation script creates authentic internet topologies using real AS-links data.

**Command:**
```bash
python gml_processing/create_large_scale_caida_gml.py \
  --caida-file gml_processing/caida_aslinks.txt \
  --output topology_5k_caida.gml \
  --nodes 5000 \
  --seed 42
```

**Options:**
- `--caida-file`: Path to CAIDA AS-links data file (required)
- `--output`: Output GML file path (required)
- `--nodes`: Number of ASes to select (50-5000, default: 1000)
- `--seed`: Random seed for reproducible generation (optional)
- `--add-loops`: Add self-loops to nodes for robustness (optional)

**What it does:**
1. Loads CAIDA AS-links dataset with real internet relationships
2. Applies three-tier scaling algorithm based on target node count:
   - Small (50-500): BFS expansion from connected seed
   - Medium (500-2000): High-degree node prioritization
   - Large (2000+): Hierarchical sampling for efficiency
3. Allocates geographic IP addresses based on AS location heuristics
4. Preserves AS relationship semantics (customer-provider, peer-peer, sibling)
5. Adds relationship-based latency and bandwidth attributes to edges
6. Validates network connectivity and saves in GML format

**Output File Structure:**
```gml
graph [
  node [ id 0 AS 12345 label "AS12345" ip "192.168.1.1" region "North America" ]
  node [ id 1 AS 23456 label "AS23456" ip "192.168.2.1" region "Europe" ]
  edge [ source 0 target 1 latency "50ms" bandwidth "100Mbit" relationship "peer" ]
  edge [ source 1 target 2 latency "25ms" bandwidth "1Gbit" relationship "customer" ]
  # ... more nodes and edges with AS relationship semantics
]
```

### Step 2: Create Agent Configuration

Configure agents to be placed sparsely on the large topology.

**Key Configuration Elements:**

```yaml
network:
  path: "topology_5k.gml"  # Path to generated GML file
  peer_mode: "Dynamic"     # Use dynamic peer discovery
  topology: "Mesh"         # Network topology type

agents:
  user_agents:
    # Define agent templates
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "10"
      count: 10  # Number of this agent type

    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "300"
      count: 90
```

**Sparse Placement:**
- Agents are distributed across available GML nodes
- IP addresses are taken from pre-allocated GML node IPs
- Ensures geographic distribution when possible

### Step 3: Generate Shadow Configuration

Run Monerosim to generate the Shadow configuration.

**Command:**
```bash
./target/release/monerosim --config config_large_scale.yaml --output shadow_output
```

**What happens:**
1. Parses YAML configuration
2. Loads and validates GML topology
3. Extracts pre-allocated IPs from GML nodes
4. Places agents sparsely on GML nodes
5. Generates Shadow YAML with network topology
6. Creates agent registry and miner files

**Generated Files:**
- `shadow_output/shadow_agents.yaml`: Main Shadow configuration
- `shadow_output/agent_registry.json`: Agent information
- `shadow_output/miners.json`: Miner configuration

### Step 4: Run and Monitor Simulation

Execute the simulation and monitor its progress.

**Running:**
```bash
# Clean environment
rm -rf shadow.data shadow.log

# Run in background
nohup shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &
```

**Monitoring:**
```bash
# Check if running
ps aux | grep shadow

# View recent logs
tail shadow.log

# Monitor resource usage
top -p $(pgrep shadow)
```

**Expected Outcomes:**
- Simulation starts within 30 seconds
- Agents initialize and connect to peers
- Block generation begins (if miners present)
- Transactions occur (if regular users active)
- Logs show network activity and agent behaviors

## Configuration Reference

### Network Section

```yaml
network:
  path: "topology_5k.gml"     # Path to GML topology file
  peer_mode: "Dynamic"        # Dynamic, Hardcoded, or Hybrid
  topology: "Mesh"            # Star, Mesh, Ring, or DAG
  seed_nodes: []              # Optional explicit seed nodes
```

### Agent Configuration

```yaml
agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"  # Optional script
      attributes:
        is_miner: false                  # Boolean
        hashrate: "10"                   # String percentage
        can_receive_distributions: true  # Boolean
        transaction_interval: "300"      # Seconds
      count: 50                          # Number of instances

  block_controller:
    script: "agents.block_controller"
```

### Performance Tuning

```yaml
general:
  stop_time: "2h"              # Simulation duration
  fresh_blockchain: true       # Start with new blockchain
  log_level: "info"            # Logging verbosity
```

## Advanced Usage

### Understanding CAIDA AS Relationships

The CAIDA-based topology generation preserves real internet AS relationship semantics:

- **Customer-Provider (-1)**: Customer pays provider for transit (higher latency, lower bandwidth)
- **Peer-Peer (0)**: Peers exchange traffic freely (medium latency/bandwidth)
- **Sibling-Sibling (1)**: Siblings under same organization (lower latency, higher bandwidth)

**Relationship Attribute Mapping:**
```python
RELATIONSHIP_ATTRIBUTES = {
    -1: {"latency": "100ms", "bandwidth": "100Mbit"},  # Customer-Provider
     0: {"latency": "50ms", "bandwidth": "500Mbit"},   # Peer-Peer
     1: {"latency": "10ms", "bandwidth": "1Gbit"}      # Sibling
}
```

### Custom Geographic Distributions

Modify the topology generation script for custom distributions:

```python
# In create_large_scale_caida_gml.py
# Customize region weights for AS selection
region_weights = {
    "North America": 0.3,
    "Europe": 0.25,
    "Asia": 0.25,
    "South America": 0.1,
    "Africa": 0.05,
    "Oceania": 0.05
}
```

### Reproducible Topologies

Use seeds for reproducible results:

```bash
# Same seed produces identical topology
python scripts/create_large_scale_gml.py --nodes 5000 --seed 12345 --output topo_v1.gml
python scripts/create_large_scale_gml.py --nodes 5000 --seed 12345 --output topo_v2.gml
# topo_v1.gml and topo_v2.gml will be identical
```

### Large Simulation Optimization

For simulations with 1000+ agents:

1. **Increase system resources**: Use machine with 16GB+ RAM
2. **Adjust Shadow settings**: Modify shadow.yaml for better performance
3. **Stagger agent startup**: Add random delays to prevent resource spikes
4. **Monitor memory usage**: Use tools like `htop` during simulation

### Debugging Large-Scale Simulations

Enable detailed logging:

```yaml
general:
  log_level: "debug"
```

Check agent placement:

```bash
# View agent distribution
python3 -c "
import json
with open('shadow_output/agent_registry.json') as f:
    agents = json.load(f)
    regions = {}
    for agent in agents:
        region = agent.get('region', 'unknown')
        regions[region] = regions.get(region, 0) + 1
    print('Agent distribution by region:', regions)
"
```

## Troubleshooting

### Common Issues

#### Topology Generation Fails
**Symptoms:** Script exits with error during generation
**Solutions:**
- Check available memory (>2GB required)
- Verify write permissions for output directory
- Reduce node count if system resources limited

#### IP Conflicts
**Symptoms:** Shadow reports IP address conflicts
**Cause:** GML file has duplicate IPs
**Solutions:**
- Regenerate topology with different seed
- Check GML file for duplicate IP attributes
- Use `--validate` flag in topology generator

#### Memory Issues During Simulation
**Symptoms:** Shadow killed due to out-of-memory
**Solutions:**
- Reduce agent count or node count
- Increase system RAM
- Use sparse agent placement
- Monitor memory usage with `free -h`

#### Slow Topology Generation
**Symptoms:** Generation takes longer than expected
**Solutions:**
- Reduce `--avg-degree` parameter
- Use SSD storage for output
- Close other memory-intensive applications

#### Agent Connection Failures
**Symptoms:** Agents fail to connect to peers
**Solutions:**
- Verify GML topology connectivity
- Check peer discovery mode configuration
- Ensure sufficient seed nodes for large topologies

### Performance Benchmarks

| Node Count | Generation Time | Memory Usage | File Size |
|------------|-----------------|--------------|-----------|
| 1000      | <1 minute      | <500MB      | ~5MB     |
| 5000      | <5 minutes     | <2GB        | ~25MB    |
| 10000     | <15 minutes    | <4GB        | ~50MB    |

### Getting Help

1. Check the logs in `shadow.data/hosts/` for detailed error messages
2. Run `python scripts/log_processor.py` to analyze processed logs
3. Verify configuration syntax with YAML validator
4. Test with smaller scale first to isolate issues

## Examples

See the `examples/` directory for complete configuration files:

- `examples/config_large_scale.yaml`: 1000 agents on 5000 nodes
- `examples/config_sparse_placement.yaml`: 100 agents on 1000 nodes
- `examples/generate_topology.sh`: Automation script for topology generation

## Next Steps

- Read the technical documentation in `docs/TOPOLOGY_GENERATION.md`
- Explore the example configurations in `examples/`
- Join the Monerosim community for support and updates