# Monerosim Examples

This directory contains example configurations and scripts demonstrating various Monerosim features and use cases.

## CAIDA-Based Large-Scale Topologies

### Overview

These examples demonstrate how to generate and use authentic internet topologies based on CAIDA AS-links data for realistic network simulations.

### Files

- `generate_caida_topology.sh`: Automated script to generate topologies of different scales
- `config_caida_large_scale.yaml`: Example configuration using a 2000-node CAIDA topology

### Quick Start

1. **Generate topologies**:
   ```bash
   chmod +x examples/generate_caida_topology.sh
   ./examples/generate_caida_topology.sh
   ```

2. **Use in simulation**:
   ```bash
   # Generate Shadow configuration
   ./target/release/monerosim --config examples/config_caida_large_scale.yaml --output shadow_caida_output

   # Run simulation
   rm -rf shadow.data shadow.log
   shadow shadow_caida_output/shadow_agents.yaml
   ```

### Generated Topologies

The generation script creates four example topologies:

- `topology_research_100.gml`: Small research topology (100 nodes)
- `topology_medium_500.gml`: Medium-scale simulation (500 nodes)
- `topology_large_2000.gml`: Large-scale network (2000 nodes)
- `topology_max_5000.gml`: Maximum scale topology (5000 nodes)

### Configuration Example

```yaml
network:
  path: "examples/topology_large_2000.gml"  # CAIDA-based topology
  peer_mode: "Dynamic"                      # Dynamic peer discovery
  topology: "Mesh"                          # Network topology type

agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      mining_script: "agents.autonomous_miner"  # Autonomous mining
      attributes:
        is_miner: true
        hashrate: "5"
      count: 20  # 20 miners distributed across topology

    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "300"
      count: 80  # 80 users for transaction activity
```

### Key Features Demonstrated

- **Authentic Topologies**: Based on real CAIDA AS-links data
- **Geographic Distribution**: Agents placed across different continents
- **AS Relationship Semantics**: Preserves customer-provider relationships
- **Sparse Agent Placement**: 100 agents on 2000+ node topology
- **Dynamic Peer Discovery**: Automatic connection establishment

## Other Examples

See the main `examples/` directory for additional configuration examples:

- `config_large_scale.yaml`: Legacy synthetic topology example
- `config_sparse_placement.yaml`: Sparse agent placement demonstration

## Troubleshooting

### Common Issues

1. **CAIDA data not found**: Ensure `gml_processing/caida_aslinks.txt` exists
2. **Memory issues**: Large topologies (>2000 nodes) require 8GB+ RAM
3. **Generation slow**: 5000-node topologies take ~5 minutes to generate

### Performance Tips

- Start with smaller topologies (100-500 nodes) for testing
- Use SSD storage for faster topology generation
- Close other memory-intensive applications during generation

## Next Steps

- Read [NETWORK_SCALING_GUIDE.md](../NETWORK_SCALING_GUIDE.md) for detailed usage instructions
- Explore the [docs/](../docs/) directory for technical documentation
- Check [gml_processing/](../gml_processing/) for topology generation scripts