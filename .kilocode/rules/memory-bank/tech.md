# Monerosim Technology Stack

## Languages
- **Rust 1.77+**: Core tool (config parsing, Shadow config generation)
- **Python 3.6+** (3.8+ recommended): Agents, testing, analysis
- **C/C++**: Monero implementation (built from `../monero/`)

## Rust Dependencies
```toml
clap = "4.5"              # CLI parsing
serde/serde_yaml = "1.0"  # Config serialization
color-eyre = "0.6"        # Error handling
thiserror = "1.0"         # Custom errors
log/env_logger = "0.4"    # Logging
rand = "0.8"              # RNG for IP allocation
```

## Python Dependencies
```
requests >= 2.28          # Monero RPC client
PyYAML >= 6.0             # Config parsing
networkx >= 3.0           # Graph algorithms (topology)
pytest >= 7.4             # Testing framework
```

## External Systems
- **shadowformonero**: Modified Shadow with Monero socket compatibility (installed to `~/.monerosim/`)
- **Monero**: Official Monero built from source (binaries in `~/.monerosim/bin/`)

## Development Environment

**Setup**:
```bash
# Full setup (installs Shadow, builds Monero) - takes 20-40 minutes
./setup.sh

# Rust build
cargo build --release

# Python venv
python3 -m venv venv
source venv/bin/activate
pip install -r scripts/requirements.txt
```

**Build Execution**:
```bash
# Generate config
./target/release/monerosim --config config_32_agents.yaml --output shadow_output

# Run simulation
~/.monerosim/bin/shadow shadow_output/shadow_agents.yaml
```

## Installation Paths
- **Shadow binary**: `~/.monerosim/bin/shadow`
- **Shadow libraries**: `~/.monerosim/lib/`
- **Monero binaries**: `~/.monerosim/bin/monerod`, `~/.monerosim/bin/monero-wallet-rpc`
- **PATH**: Automatically added to `~/.bashrc` by setup.sh

## System Requirements
- **OS**: Linux (Ubuntu 20.04+)
- **CPU**: 4+ cores (8+ for large sims)
- **RAM**: 8GB min (16GB+ for 100+ agents, 32GB for 1000 agents)
- **Storage**: 10GB+ for builds + simulation data

## Key Constraints
- Uses shadowformonero (modified Shadow) for Monero socket compatibility
- Simulation speed: 2-10x slower than real-time for medium/large sims
- All components run inside Shadow virtual network
- Deterministic simulations via `simulation_seed` in config
