# Monerosim

A Rust-based tool for generating configuration files for the Shadow network simulator to run Monero cryptocurrency network simulations. Monerosim enables researchers and developers to study Monero network behavior in controlled, reproducible environments.

## Key Features

- **Shadow Integration**: Seamlessly generates Shadow network simulator configurations for Monero
- **Dual Network Topologies**: Support for both simple switch-based and complex GML-based networks
- **AS-Aware IP Assignment**: Intelligent IP allocation based on Autonomous System groupings
- **Agent-Based Mode**: Sophisticated simulations with autonomous network participants
- **Dynamic Agent Discovery**: Runtime agent discovery through shared state files
- **Advanced Peer Discovery**: Multiple peer discovery modes (Dynamic, Hardcoded, Hybrid) with intelligent seed selection
- **Topology Templates**: Pre-built network topologies (Star, Mesh, Ring, DAG) for structured simulations
- **Production Ready**: Proven in production with comprehensive test coverage
- **Python-First Testing**: Modern Python test suite with 95%+ coverage
- **Reproducible Research**: Deterministic simulations for scientific analysis

## Independent Mining Control

Monerosim uses autonomous mining agents for deterministic, reproducible simulations:

### Configuration Example
```yaml
general:
  simulation_seed: 12345  # For reproducibility

agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      mining_script: "agents.autonomous_miner"  # Autonomous mining
      attributes:
        is_miner: true
        hashrate: "60"  # % of total network hashrate
```

### Key Features
- **Reproducible Mining**: Same `simulation_seed` produces identical block sequences
- **Autonomous Miners**: Each miner independently decides when to mine blocks
- **Poisson Distribution**: Realistic inter-block time distribution
- **Deterministic**: Perfect reproducibility for scientific research

### Migration from Block Controller
If you have old configurations using `block_controller`, use the migration utility:
```bash
python scripts/migrate_mining_config.py your_config.yaml
```

See [`examples/config_large_scale.yaml`](examples/config_large_scale.yaml) or [`config_32_agents.yaml`](config_32_agents.yaml) for complete examples.

## Network Scaling and Large-Scale Topologies

Monerosim now supports large-scale network simulations using authentic CAIDA AS-links data for realistic internet topology modeling.

### Features
- **CAIDA-Based Topologies**: Generate authentic internet topologies using real AS relationship data
- **Three-Tier Scaling**: Intelligent algorithms for different network sizes (50-5000 nodes)
- **AS Relationship Semantics**: Preserve customer-provider, peer-peer, and sibling relationships
- **Geographic IP Distribution**: Pre-allocated IPs across 6 continents based on AS locations
- **Sparse Agent Placement**: Efficient placement of hundreds of agents on thousands of nodes
- **Memory-Efficient**: <2GB peak memory usage for 5000-node generation
- **Deterministic Generation**: Reproducible topologies with random seeds

### Quick Example
```bash
# Generate CAIDA-based topology with self-loops
python gml_processing/create_caida_connected_with_loops.py \
  gml_processing/cycle-aslinks.l7.t1.c008040.20200101.txt \
  topology_caida.gml \
  --max_nodes 100

# Create configuration with GML topology
# (edit config.yaml to use network.path: "topology_5k_caida.gml")

# Generate Shadow configuration
./target/release/monerosim --config config.yaml

# Run simulation
shadow shadow_output/shadow_agents.yaml
```

For detailed information, see [NETWORK_SCALING_GUIDE.md](NETWORK_SCALING_GUIDE.md).

## Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd monerosim
   ./setup.sh
   ```

2. **Build Monerosim**
   ```bash
   cargo build --release
   ```

3. **Run an Agent-Based Simulation**
   ```bash
   # Generate agent-based configuration (small/medium/large)
   ./target/release/monerosim --config config_32_agents.yaml --output shadow_agents_output
   
   # Run the simulation
   shadow shadow_agents_output/shadow_agents.yaml
   ```

## Project Structure

```
monerosim/
├── src/                      # Rust source code
│   ├── main.rs              # CLI entry point
│   ├── config_v2.rs         # Configuration structures
│   ├── config_loader.rs     # YAML configuration loading
│   ├── orchestrator.rs      # Shadow config generation orchestration
│   ├── gml_parser.rs        # GML topology file parser
│   ├── analysis/            # Transaction routing analysis (Rust)
│   │   ├── spy_node.rs      # Spy node vulnerability analysis
│   │   ├── propagation.rs   # Propagation timing analysis
│   │   ├── dandelion.rs     # Dandelion++ stem path reconstruction
│   │   └── ...              # Additional analysis modules
│   └── bin/
│       └── tx_analyzer.rs   # Analysis CLI tool
├── agents/                   # Python agent framework
│   ├── agent_discovery.py   # Dynamic agent discovery system
│   ├── base_agent.py        # Base agent class
│   ├── autonomous_miner.py  # Autonomous mining agent (Poisson-based)
│   ├── regular_user.py      # User agent implementation
│   ├── miner_distributor.py # Mining reward distribution
│   ├── simulation_monitor.py # Real-time monitoring agent
│   └── monero_rpc.py        # RPC client library
├── scripts/                  # Python utility scripts
│   ├── tx_analyzer.py       # Transaction routing analysis (Python)
│   ├── log_processor.py     # Log analysis and processing
│   ├── sync_check.py        # Network synchronization monitoring
│   └── migrate_mining_config.py # Config migration utility
├── gml_processing/          # Network topology generation
│   └── create_caida_connected_with_loops.py # CAIDA-based topology generator
├── examples/                # Example configurations
├── docs/                    # Detailed documentation
│   └── ANALYSIS_TOOLS.md    # Analysis tools documentation
├── config_32_agents.yaml    # Default configuration
└── setup.sh                 # Environment setup script
```

## Documentation

- [Architecture Overview](.kilocode/rules/memory-bank/architecture.md) - System design and components
- [Configuration Guide](.kilocode/rules/memory-bank/configuration.md) - How to configure simulations (includes GML networks)
- [Peer Discovery System](.kilocode/rules/memory-bank/peer_discovery.md) - Dynamic agent discovery and topologies
- [GML Integration](.kilocode/rules/memory-bank/architecture.md#gml-integration) - Complex network topologies
- [Development Guide](.kilocode/rules/memory-bank/tech.md) - Technical stack and development setup
- [Project Status](.kilocode/rules/memory-bank/status.md) - Current development status
- [Brief Overview](.kilocode/rules/memory-bank/brief.md) - Project goals and requirements

## Post-Simulation Analysis

After running a simulation, use the analysis tools to examine transaction routing, network topology, and privacy characteristics.

### Quick Analysis
```bash
# Build the Rust analyzer
cargo build --release --bin tx-analyzer

# Run full analysis (spy node, propagation, resilience)
./target/release/tx-analyzer full

# Or use Python
python3 scripts/tx_analyzer.py full
```

### Available Analyses
- **Spy Node Vulnerability**: How effectively could an attacker deanonymize transaction origins?
- **Propagation Timing**: How quickly do transactions spread through the network?
- **Network Resilience**: Connectivity, centralization (Gini coefficient), partition risk
- **Dandelion++ Paths**: Stem path reconstruction and privacy scoring
- **TX Relay V2**: Protocol usage statistics (hash announcements vs full broadcasts)

### Example Output
```
Spy Node Vulnerability:
  Inference accuracy: 52.6%
  High vulnerability TXs: 0

Propagation Timing:
  Average: 89965.4ms
  Median: 13245.5ms

Network Resilience:
  Avg peers: 22.0
  Gini coefficient: 0.37
```

For detailed documentation, see [docs/ANALYSIS_TOOLS.md](docs/ANALYSIS_TOOLS.md).

## Python Scripts

Monerosim uses Python as the primary scripting language for all testing and monitoring:

- **Test Suite**: Comprehensive unit tests with 95%+ coverage
- **Virtual Environment**: Isolated Python environment at `venv/`
- **Requirements**: Install with `pip install -r scripts/requirements.txt`
- **Run All Tests**: `python3 scripts/run_all_tests.py`

Key scripts:
- `simple_test.py` - Verifies basic mining and synchronization
- `transaction_script.py` - Tests transaction processing
- `sync_check.py` - Monitors blockchain synchronization
- `monitor.py` - Real-time simulation monitoring

Key agents:
- `agent_discovery.py` - Dynamic agent discovery system
- `base_agent.py` - Base agent class
- `regular_user.py` - User agent implementation
- `autonomous_miner.py` - Autonomous mining (decentralized block generation)

### Agent Discovery System

The Agent Discovery System provides dynamic agent discovery through shared state files, replacing hardcoded network configurations:

```python
from agents.agent_discovery import AgentDiscovery

# Initialize the discovery system
ad = AgentDiscovery()

# Find all miners
miners = ad.get_miner_agents()

# Find wallets with sufficient balance
wallets = ad.get_wallet_agents()

# Get agent by ID
agent = ad.get_agent_by_id('user001')
```


## Peer Discovery Modes

Monerosim supports three peer discovery modes that control how Monero nodes connect to each other:

### Dynamic Mode
- **Automatic seed selection** based on mining capability, network centrality, and geographic distribution
- **Intelligent algorithm** that prioritizes miners and distributes seeds across different IP subnets
- **No manual configuration** required - optimal seeds are selected automatically
- **Best for**: Research simulations where you want realistic, optimized peer connections

### Hardcoded Mode
- **Explicit seed nodes** defined in configuration
- **Topology templates** (Star, Mesh, Ring, DAG) for structured network patterns
- **Predictable connections** for reproducible testing
- **Best for**: Controlled experiments and validation scenarios

### Hybrid Mode
- **Combines topology-based connections** with peer discovery
- **Structured primary connections** plus dynamic discovery for robustness
- **DNS discovery support** for maximum connectivity
- **Best for**: Production-like simulations with controlled structure

## Topology Templates

Pre-built network topology templates for structured peer connections:

- **Star**: All nodes connect to a central hub (ideal for large networks)
- **Mesh**: Fully connected network (best for small networks ≤10 agents)
- **Ring**: Circular connections (good for circular communication patterns)
- **DAG**: Hierarchical connections (traditional blockchain patterns, default)

## Agent Framework

The agent-based simulation framework enables realistic cryptocurrency network modeling:

### Agent Types
- **Autonomous Miners**: Independent miners using Poisson-distributed block generation
- **Regular Users**: Autonomous wallet holders sending transactions
- **Miner Distributor**: Distributes mining rewards to eligible wallets
- **Simulation Monitor**: Real-time monitoring and status reporting

### Example Configurations
- **Standard** (`config_32_agents.yaml`): 32 agents with realistic network topology
- **Large Scale** (`examples/config_large_scale.yaml`): Large network simulations
- **CAIDA Topology** (`examples/config_caida_large_scale.yaml`): Realistic internet topology

### Features
- Autonomous decision-making based on configurable parameters
- Shared state mechanism for agent coordination
- Realistic transaction patterns and mining behaviors
- Scalable from small tests to large network simulations
- Dynamic agent discovery through shared state files

### Agent Discovery Integration

The Agent Discovery System provides a unified interface for discovering and interacting with agents:

- **Dynamic Discovery**: Agents are discovered at runtime from shared state files
- **Type-Based Queries**: Find agents by type (miners, wallets, users)
- **Attribute Filtering**: Filter agents based on their attributes
- **Caching**: Performance-optimized with 5-second TTL cache


## Requirements

### System Requirements
- **OS**: Linux (Ubuntu 20.04+ recommended)
- **CPU**: 4+ cores (8+ for large simulations)
- **RAM**: 8GB minimum (16GB+ recommended)
- **Storage**: 10GB+ free space

### Dependencies
- **Rust**: Latest stable (1.70+)
- **Python**: 3.6+ (3.8+ recommended)
- **Shadow**: 2.0+ (installed by setup.sh)
- **Build Tools**: CMake, GCC/Clang, Make

### Installation
```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install build-essential cmake libglib2.0-dev libevent-dev libigraph-dev

# Run setup script
./setup.sh

# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r scripts/requirements.txt
```

## Contributing

We welcome contributions! Please follow these guidelines:

1. **Fork and Clone**: Fork the repository and clone locally
2. **Branch**: Create a feature branch (`git checkout -b feature/amazing-feature`)
3. **Test**: Ensure all tests pass (`python3 scripts/run_all_tests.py`)
4. **Commit**: Use clear, descriptive commit messages
5. **Push**: Push to your fork and submit a pull request

### Development Workflow
1. Make changes to Rust code or Python scripts
2. Run tests to ensure nothing breaks
3. Update documentation if needed
4. Submit PR with clear description

### Working with Agent Discovery

When developing new agents or scripts, use the Agent Discovery System for dynamic agent interactions:

```python
from agents.agent_discovery import AgentDiscovery

# Initialize in your script
ad = AgentDiscovery()

# Find agents dynamically
miners = ad.get_miner_agents()
wallets = ad.get_wallet_agents()

# Use agent information for interactions
for miner in miners:
    # Interact with miner
    pass
```


### Code Style
- **Rust**: Follow standard Rust conventions (use `cargo fmt` and `cargo clippy`)
- **Python**: Follow PEP 8 (use `black` for formatting)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Shadow Network Simulator team for the excellent simulation platform
- Monero Project for the cryptocurrency implementation
- Contributors and researchers using Monerosim for their work

## Support

- **Issues**: Report bugs via GitHub Issues
- **Discussions**: Use GitHub Discussions for questions and ideas
- **Documentation**: Check the docs/ directory for detailed guides

---

**Note**: This project is for research and development purposes. Always test thoroughly before using in any production or critical environment.
