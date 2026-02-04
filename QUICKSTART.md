# Monerosim Quick Start

## Prerequisites

- Linux system (Ubuntu 20.04+, Debian, etc.)
- Sudo access
- Internet connection

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd monerosim

# Run the automated setup (builds Shadow and Monero from source)
./setup.sh
```

The setup script will:
- Install system dependencies (Rust, build tools)
- Build Shadow with Monero compatibility patches
- Build Monero binaries (monerod, monero-wallet-rpc)
- Install binaries to `~/.monerosim/bin/`
- Optionally run a test simulation

## Running Your First Simulation

```bash
# Build Monerosim
cargo build --release

# Generate Shadow configuration
./target/release/monerosim --config monerosim.yaml

# Run the simulation
rm -rf shadow.data shadow.log
nohup ~/.monerosim/bin/shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &

# Check progress
tail shadow.log
```

The default configuration (`monerosim.yaml`) runs 25 agents (5 miners + 20 users) for 8 hours of simulated time.

## Customizing

Edit the configuration to change simulation parameters:

```yaml
general:
  stop_time: "30m"          # Shorter simulation for testing
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
    start_time: 20m
    transaction_interval: 60
    activity_start_time: 1200
    can_receive_distributions: true
```

Then regenerate and run:

```bash
./target/release/monerosim --config your_config.yaml
rm -rf shadow.data shadow.log
nohup ~/.monerosim/bin/shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &
```

## Analyzing Results

After the simulation completes:

```bash
# Activate Python environment
source venv/bin/activate

# Process logs
python scripts/log_processor.py

# Run analysis
cargo build --release --bin tx-analyzer
./target/release/tx-analyzer full
```

Check processed logs in `shadow.data/hosts/*/` and analysis output in `analysis_output/`.

## Verification

```bash
# Check daemons started
grep "RPC server initialized OK" shadow.data/hosts/*/monerod.*.stdout

# Check P2P connections
grep "Connected success" shadow.data/hosts/*/monerod.*.stdout

# Check agent registry
cat /tmp/monerosim_shared/agent_registry.json
```

## Troubleshooting

**"Shadow not found"**: Ensure `~/.monerosim/bin/` is in your PATH. Run `source ~/.bashrc`.

**Permission denied**: Make sure you can run `sudo` commands.

**Simulation seems stuck**: Check `tail shadow.log`. Large simulations run slower than real time.

**"N managed processes in unexpected final state"**: This is normal. Shadow terminates all processes when simulation time expires.

## Next Steps

- Read the full [README](README.md) for architecture overview
- See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for all configuration options
- See [docs/RUNNING_SIMULATIONS.md](docs/RUNNING_SIMULATIONS.md) for detailed workflow
- Check [examples/](examples/) for more configuration examples
