# Monerosim Technology Stack

## Languages
- **Rust 1.77+**: Core tool (config parsing, Shadow config generation)
- **Python 3.6+** (3.8+ recommended): Agents, testing, analysis
- **C/C++**: Monero implementation (builds/A/monero/)

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
- **Shadow 2.0+**: Network simulator (discrete-event)
- **Monero**: Modified with Shadow patches in `builds/A/monero/`

## Development Environment

**Setup**:
```bash
# System
./setup.sh                # Installs Shadow, builds Monero

# Rust
cargo build --release

# Python venv
python3 -m venv venv
source venv/bin/activate
pip install -r scripts/requirements.txt
```

**Build Execution**:
```bash
# Generate config
./target/release/monerosim --config config.yaml --output shadow_output

# Run simulation
shadow shadow_output/shadow_agents.yaml
```

## System Requirements
- **OS**: Linux (Ubuntu 20.04+)
- **CPU**: 4+ cores (8+ for large sims)
- **RAM**: 8GB min (16GB+ for 50+ agents)
- **Storage**: 10GB+ for builds + simulation data

## Key Constraints
- Monero requires Shadow compatibility patches (DNS disabled, seed nodes disabled, fixed difficulty)
- Simulation speed: 2-10x slower than real-time for medium/large sims
- All components run inside Shadow virtual network
