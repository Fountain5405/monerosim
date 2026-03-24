# Monerosim Quick Start

## Prerequisites

- Linux system (Ubuntu 22.04+ recommended, Debian and Arch also supported)
- Sudo access (for installing system packages)
- Internet connection (downloads ~1-2 GB of source code)
- 30 GB free disk space (for building Shadow and Monero from source)
- Python 3.10+

> **Tip:** We recommend using a dedicated Linux user account for monerosim (e.g., `sudo adduser monerosim`). Monerosim manages several daemons, writes to `/tmp`, and cleans up simulation state between runs. A dedicated user keeps things isolated from your other work.

## Installation

```bash
# Clone the repository
git clone https://github.com/Fountain5405/monerosim.git
cd monerosim

# Run the automated setup (~30-60 minutes)
./setup.sh
```

The setup script will:
- Install system dependencies (Rust, build tools, clang, glib)
- Set up a Python virtual environment and install dependencies
- Build Monerosim (`cargo build --release`)
- Clone and build [shadowformonero](https://github.com/Fountain5405/shadowformonero) (a Shadow fork with Monero socket compatibility)
- Clone and build official Monero from source (monerod, monero-wallet-rpc)
- Install all binaries to `~/.monerosim/bin/`
- Generate a test Shadow configuration

## Verify Installation

```bash
~/.monerosim/bin/shadow --version      # Should print Shadow version
~/.monerosim/bin/monerod --version     # Should print Monero version
./target/release/monerosim --help      # Should print monerosim usage

# Test Python agents load correctly
source venv/bin/activate
python -c "import agents; print('Python agents OK')"
```

If any of these fail, re-run `./setup.sh` or check the Troubleshooting section below.

## Running Your First Simulation

The quickest way to verify everything works end-to-end:

```bash
# Run the quickstart test (5 miners, 3 users, 6h simulated time)
# This takes ~10-15 minutes of wall clock time
./run_sim.sh --config test_configs/quickstart.yaml
```

Or run the steps manually:

```bash
# Generate Shadow configuration
./target/release/monerosim --config test_configs/quickstart.yaml --output shadow_output

# Run the simulation
rm -rf shadow.data shadow.log
nohup ~/.monerosim/bin/shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &

# Check progress
tail shadow.log

# Real-time status dashboard
./scripts/check_sim.sh
```

## Customizing

Edit a configuration or create your own:

```yaml
general:
  stop_time: "2.5h"
  simulation_seed: 12345

network:
  path: "gml_processing/1200_nodes_caida_with_loops.gml"
  peer_mode: Dynamic

agents:
  miner-001:
    daemon: monerod
    wallet: "monero-wallet-rpc"
    script: agents.autonomous_miner
    start_time: 0s
    hashrate: 50

  miner-002:
    daemon: monerod
    wallet: "monero-wallet-rpc"
    script: agents.autonomous_miner
    start_time: 1s
    hashrate: 50

  user-001:
    daemon: monerod
    wallet: "monero-wallet-rpc"
    script: agents.regular_user
    start_time: 60s
    transaction_interval: 60
    activity_start_time: 7500
    can_receive_distributions: true
```

Note: Monero wallets need ~60 blocks (~2 hours at 120s block time) to mature before spending. Set `activity_start_time` accordingly.

Then generate and run:

```bash
./target/release/monerosim --config your_config.yaml --output shadow_output
rm -rf shadow.data shadow.log
nohup ~/.monerosim/bin/shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &
```

For large-scale simulations (100+ agents), use the config generator:

```bash
source venv/bin/activate
python scripts/generate_config.py --agents 100 --duration 8h -o my_config.yaml
```

## Analyzing Results

After the simulation completes:

```bash
# Activate Python environment (required for analysis scripts)
source venv/bin/activate

# Process logs
python scripts/log_processor.py

# Run transaction analysis
./target/release/tx-analyzer full
```

Check analysis output in `analysis_output/` and processed logs in `shadow.data/hosts/*/`.

## Troubleshooting

**"shadow: command not found"**: Use the full path `~/.monerosim/bin/shadow` or add `~/.monerosim/bin` to your PATH manually.

**"Permission denied"**: Make sure you can run `sudo` commands. setup.sh needs sudo to install system packages.

**"Python 3.10+ is required"**: Install a newer Python version. On Ubuntu: `sudo apt install python3.10`.

**Simulation seems stuck**: This is normal. Check `tail shadow.log` for progress. Simulations run slower than real time. Use `./scripts/check_sim.sh` for a detailed status dashboard.

**"N managed processes in unexpected final state"**: This is normal. Shadow terminates all processes when simulation time expires.

**setup.sh failed partway through**: Re-run `./setup.sh`. It handles partial installs gracefully. For a clean start: `./setup.sh --clean`.

## Next Steps

- Read the full [README](README.md) for architecture overview
- See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for all configuration options
- See [docs/RUNNING_SIMULATIONS.md](docs/RUNNING_SIMULATIONS.md) for detailed workflow
- See [docs/NETWORK_SCALING_GUIDE.md](docs/NETWORK_SCALING_GUIDE.md) for large-scale simulations
- Check [examples/](examples/) for more configuration examples
