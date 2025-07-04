# MoneroSim

A comprehensive tool for simulating Monero cryptocurrency networks using the Shadow discrete-event network simulator.

## Overview

MoneroSim is a Rust-based configuration generator that creates large-scale, discrete-event network simulations of the Monero cryptocurrency network. It generates Shadow simulator configurations that can run multiple Monero nodes in a controlled network environment, allowing researchers to study network behavior, consensus mechanisms, and performance characteristics.

## Features

- 🚀 **One-command setup** - Automated dependency installation and configuration
- 🔧 **YAML-based configuration** - Simple, human-readable simulation parameters
- 🌐 **Network topology control** - Define custom node counts and P2P connections
- 📊 **Comprehensive logging** - Detailed simulation output and analysis
- 🏗️ **Patch support** - Includes Monero patches for simulation compatibility
- 🐛 **Error handling** - Robust error reporting and validation

## Quick Start

### Automated Setup (Recommended)

The easiest way to get started is with our automated setup script:

```bash
# Clone the repository (if not already cloned)
git clone <repository_url>
cd monerosim

# Run the automated setup script
./setup.sh
```

The setup script will:
1. ✅ Check and install system dependencies (Rust, Shadow, build tools)
2. ✅ Clone Monero source code and apply Shadow compatibility patches
3. ✅ Build MoneroSim from source
4. ✅ Build Monero binaries with Shadow compatibility
5. ✅ Install Monero binaries to system PATH for Shadow compatibility
6. ✅ Generate a test Shadow configuration
7. ✅ Run a test simulation to verify everything works
8. ✅ Analyze basic results and provide feedback

**Note**: The setup process includes building Monero from source, which can take 20-40 minutes depending on your system.

### Manual Setup

If you prefer manual setup or the automated script doesn't work for your system:

#### Prerequisites

- **Shadow Simulator** - [Installation guide](https://shadow.github.io/docs/guide/install/)
- **Rust 1.77+** - [Install Rust](https://rustup.rs/)
- **Build tools**: `gcc`, `g++`, `cmake`, `make`
- **Git** for cloning repositories

#### Building

```bash
# Build MoneroSim
cargo build --release

# Install Monero binaries (requires sudo)
sudo ./install_monerod_binaries.sh

# Generate Shadow configuration
./target/release/monerosim --config config.yaml --output shadow_output

# Run simulation
shadow shadow_output/shadow.yaml
```

## Configuration

Edit `config.yaml` to customize your simulation:

```yaml
general:
  stop_time: "10m"  # How long to run the simulation

monero:
  nodes: 5          # Number of Monero nodes to simulate
```

### Configuration Options

- **`general.stop_time`**: Simulation duration (e.g., "10m", "1h", "30s")
- **`monero.nodes`**: Number of Monero nodes (1-100+ depending on system resources)

## Running Simulations

### Basic Usage

```bash
# 1. Configure your simulation
vim config.yaml

# 2. Generate Shadow configuration
./target/release/monerosim --config config.yaml --output shadow_output

# 3. Run the simulation
shadow shadow_output/shadow.yaml

# 4. Analyze results
ls shadow.data/hosts/
```

### Output Structure

After running a simulation, you'll find:

```
shadow.data/
├── shadow.log              # Main Shadow simulator log
└── hosts/
    ├── a0/                 # Node 0 data
    │   ├── monerod.1000.stdout    # Monero daemon output
    │   ├── monerod.1000.stderr    # Error output
    │   └── ...
    ├── a1/                 # Node 1 data
    └── ...
```

### Analyzing Results

Key log patterns to look for:

```bash
# Check if nodes started successfully
grep "RPC server initialized OK" shadow.data/hosts/*/monerod.*.stdout

# Check P2P connections
grep "Connected success" shadow.data/hosts/*/monerod.*.stdout

# Check for errors
grep -i "error\|fail" shadow.data/hosts/*/monerod.*.stdout
```

## Troubleshooting

### Common Issues

1. **"Shadow not found"**
   - Install Shadow from https://shadow.github.io/docs/guide/install/
   - Ensure Shadow is in your PATH

2. **"monerod not found"**
   - Run the setup script or manually install with `sudo ./install_monerod_binaries.sh`
   - Ensure `/usr/local/bin/monerod` exists and is executable

3. **P2P connection failures**
   - This is expected in very short simulations
   - Try increasing `stop_time` in config.yaml to "30m" or longer

4. **Permission errors**
   - The setup script requires sudo access to install monerod binaries
   - Make sure you can run `sudo` commands

### Getting Help

1. Check the Shadow simulator logs: `shadow.data/shadow.log`
2. Check individual node logs: `shadow.data/hosts/*/monerod.*.stdout`
3. Review the configuration: `shadow_output/shadow.yaml`

## Advanced Usage

### Custom Network Topologies

You can modify the network topology by editing the Rust source code in `src/shadow.rs`. The current implementation creates a simple topology where each node connects to the bootstrap node and the previous node.

### Multiple Monero Versions

The project supports building multiple Monero versions (builds A and B). The setup script automatically uses the first available build.

### Performance Tuning

For large simulations (10+ nodes):
- Increase system resources (RAM, CPU)
- Consider running on multiple cores
- Review `SHADOW_OPTIMIZATIONS.md` for performance tips

## Project Structure

```
monerosim/
├── src/                    # Rust source code
│   ├── main.rs            # Main application entry point
│   ├── config.rs          # Configuration parsing
│   ├── shadow.rs          # Shadow configuration generation
│   └── build.rs           # Monero build management
├── patches/               # Monero patches for simulation compatibility
├── builds/                # Compiled Monero binaries
├── config.yaml           # Default simulation configuration
├── setup.sh              # Automated setup script
└── README.md             # This file
```

## Development

### Building from Source

```bash
# Debug build
cargo build

# Release build (recommended for simulations)
cargo build --release

# Run tests
cargo test
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `./setup.sh`
5. Submit a pull request

## License

GPL-3.0 - See LICENSE file for details

## Acknowledgments

- [Shadow Simulator](https://shadow.github.io/) for discrete-event network simulation
- [Monero Project](https://getmonero.org/) for the cryptocurrency implementation
- Contributors and researchers using this tool

---

**Happy simulating!** 🚀

For questions or issues, please check the troubleshooting section above or create an issue in the repository.
