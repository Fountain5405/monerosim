# Monerosim

A Rust-based tool for generating configuration files for the Shadow network simulator to run Monero cryptocurrency network simulations. Monerosim enables researchers and developers to study Monero network behavior in controlled, reproducible environments.

## Key Features

- **Shadow Integration**: Seamlessly generates Shadow network simulator configurations for Monero
- **Agent-Based Mode**: Sophisticated simulations with autonomous network participants
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
│   ├── marketplace.py       # Marketplace agent
│   ├── mining_pool.py       # Mining pool agent
│   ├── block_controller.py  # Mining orchestration
│   └── monero_rpc.py        # RPC client library
├── scripts/                  # Python test and utility scripts
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
- [Configuration Guide](docs/CONFIGURATION.md) - How to configure simulations
- [Development Guide](docs/DEVELOPMENT.md) - Contributing and development workflow
- [Performance Guide](docs/PERFORMANCE.md) - Optimization and scaling
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

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
- `block_controller.py` - Controls block generation timing

## Agent Framework

The agent-based simulation framework enables realistic cryptocurrency network modeling:

### Agent Types
- **Regular Users**: Autonomous wallet holders sending transactions
- **Marketplaces**: Services receiving and tracking payments
- **Mining Pools**: Coordinated block generation participants
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
