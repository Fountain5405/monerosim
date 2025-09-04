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
   ./target/release/monerosim --config config_agents_small.yaml --output shadow_agents_output
   
   # Run the simulation
   shadow shadow_agents_output/shadow_agents.yaml
   ```

## Project Structure

```
monerosim/
├── src/                      # Rust source code
│   ├── main.rs              # CLI entry point
│   ├── config.rs            # Configuration parsing
│   ├── build.rs             # Monero build management
│   └── shadow_agents.rs     # Agent-based Shadow config generation
├── agents/                   # Python agent framework
│   ├── base_agent.py        # Base agent class
│   ├── regular_user.py      # User agent implementation
│   ├── block_controller.py  # Mining orchestration
│   └── monero_rpc.py        # RPC client library
├── scripts/                  # Python test and utility scripts
│   ├── agent_discovery.py   # Dynamic agent discovery system
│   ├── simple_test.py       # Basic functionality test
│   ├── sync_check.py        # Network synchronization test
│   ├── transaction_script.py # Transaction testing
│   ├── monitor.py           # Real-time monitoring
│   └── block_controller.py  # Block generation control
├── legacy_scripts/          # Deprecated bash scripts (historical reference)
├── docs/                    # Detailed documentation
├── config*.yaml             # Example configurations
└── setup.sh                 # Environment setup script
```

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) - System design and components
- [Configuration Guide](docs/CONFIGURATION.md) - How to configure simulations (includes GML networks)
- [Topology Features](docs/TOPOLOGY_FEATURES.md) - Peer discovery modes and topology templates
- [GML IP Assignment and AS Distribution](docs/GML_IP_ASSIGNMENT_AS_DISTRIBUTION.md) - Complex network topologies
- [Development Guide](docs/DEVELOPMENT.md) - Contributing and development workflow
- [Performance Guide](docs/PERFORMANCE.md) - Optimization and scaling
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [Agent Discovery System](scripts/README_agent_discovery.md) - Dynamic agent discovery
- [Unified Agent Architecture](docs/UNIFIED_AGENT_ARCHITECTURE.md) - Agent framework design

## Python Scripts

Monerosim uses Python as the primary scripting language for all testing and monitoring:

- **Test Suite**: Comprehensive unit tests with 95%+ coverage
- **Virtual Environment**: Isolated Python environment at `venv/`
- **Requirements**: Install with `pip install -r scripts/requirements.txt`
- **Run All Tests**: `python3 scripts/run_all_tests.py`

Key scripts:
- `agent_discovery.py` - Dynamic agent discovery system
- `simple_test.py` - Verifies basic mining and synchronization
- `transaction_script.py` - Tests transaction processing
- `sync_check.py` - Monitors blockchain synchronization
- `monitor.py` - Real-time simulation monitoring
- `block_controller.py` - Controls block generation timing

### Agent Discovery System

The Agent Discovery System provides dynamic agent discovery through shared state files, replacing hardcoded network configurations:

```python
from scripts.agent_discovery import AgentDiscovery

# Initialize the discovery system
ad = AgentDiscovery()

# Find all miners
miners = ad.get_miner_agents()

# Find wallets with sufficient balance
wallets = ad.get_wallet_agents()

# Get agent by ID
agent = ad.get_agent_by_id('user001')
```

For more details, see [Agent Discovery System](scripts/README_agent_discovery.md).

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
- **Regular Users**: Autonomous wallet holders sending transactions
- **Block Controller**: Orchestrates mining across pools

### Simulation Scales
- **Small** (`config_agents_small.yaml`): 2-10 participants for development
- **Medium** (`config_agents_medium.yaml`): 10-50 participants for testing
- **Large** (`config_agents_large.yaml`): 50-100+ participants for research

### Features
- Autonomous decision-making based on configurable parameters
- Shared state mechanism for agent coordination
- Realistic transaction patterns and mining behaviors
- Scalable from small tests to large network simulations
- Dynamic agent discovery through shared state files

### Agent Discovery Integration

The Agent Discovery System provides a unified interface for discovering and interacting with agents:

- **Dynamic Discovery**: Agents are discovered at runtime from shared state files
- **Type-Based Queries**: Find agents by type (miners, wallets, block controllers)
- **Attribute Filtering**: Filter agents based on their attributes
- **Caching**: Performance-optimized with 5-second TTL cache

For more details, see [Agent Discovery System](scripts/README_agent_discovery.md).

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
from scripts.agent_discovery import AgentDiscovery

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

For more details, see [Agent Discovery System](scripts/README_agent_discovery.md).

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
