# Monerosim

A tool for running Monero cryptocurrency network simulations inside the [Shadow](https://shadow.github.io/) network simulator. Monerosim generates Shadow configuration files from a concise YAML description of your desired network, then Shadow executes the simulation using real Monero binaries in a virtual network.

## How It Works

Monerosim simulations proceed in two stages:

```
 1. CONFIGURE             2. SIMULATE
 +--------------+        +----------------------+
 | YAML config  | -----> | shadowformonero runs:|
 | (your input) |  rust  |  - monerod daemons   |
 |              |  gen   |  - wallet-rpc         |
 +--------------+        |  - Python agents      |
                         |  on virtual network   |
                         +----------------------+
```

**Stage 1** - You write a YAML config describing the network: how many miners, users, what topology, how long to run. Monerosim's Rust engine parses this and generates Shadow configuration files.

**Stage 2** - shadowformonero runs the simulation. Each agent gets its own monerod daemon, wallet-rpc, and Python script running on a virtual host. Miners generate blocks autonomously using Poisson-distributed timing. Users send transactions. Agents discover each other through shared state files. Simulation output (logs, shared state) is written to `shadow.data/` and `/tmp/monerosim_shared/`.

## Quick Start

```bash
# 1. Clone and set up (installs shadowformonero, builds Monero from source)
git clone <repository-url>
cd monerosim
./setup.sh

# 2. Build Monerosim
cargo build --release

# 3. Generate Shadow configuration from the default config
./target/release/monerosim --config monerosim.expanded.yaml

# 4. Run the simulation
rm -rf shadow.data shadow.log
nohup ~/.monerosim/bin/shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &

# 5. Monitor progress
tail shadow.log
```

## Configuration

Configurations are YAML files with three sections: `general`, `network`, and `agents`. Here is a minimal example:

```yaml
general:
  stop_time: "2h"
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
    start_time: 1h
    transaction_interval: 60
    activity_start_time: 3600
    can_receive_distributions: true

  miner-distributor:
    script: agents.miner_distributor
    wait_time: 3600
    initial_fund_amount: "1.0"
    transaction_frequency: 30
```

Each agent is identified by its key name (e.g., `miner-001`). Miners are identified by having a `hashrate` value. The hashrate values across all miners should sum to 100.

See [`monerosim.expanded.yaml`](monerosim.expanded.yaml) for the full default configuration (25 agents, 8h simulation).

For the complete configuration reference, see [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Architecture

### Components

| Component | Language | Purpose |
|-----------|----------|---------|
| Config engine | Rust | Parse YAML, generate Shadow config, allocate IPs, set up topology |
| Agent framework | Python | Autonomous miners, users, monitors running inside Shadow |
| shadowformonero | C/C++ | Shadow fork with Monero socket compatibility, runs real Monero binaries |

### What runs inside Shadow

For each agent in your config, Shadow launches:
- A **monerod** daemon (the real Monero node software)
- A **monero-wallet-rpc** instance (for wallet operations)
- A **Python agent script** (autonomous behavior: mining, transactions, monitoring)

These all run on a virtual host with a geographically-distributed IP address. The virtual network (provided by shadowformonero, a Shadow fork with Monero socket compatibility) connects all hosts and simulates realistic network conditions.

### Agent types

| Agent | Script | Purpose |
|-------|--------|---------|
| Autonomous miner | `agents.autonomous_miner` | Generates blocks with Poisson-distributed timing |
| Regular user | `agents.regular_user` | Sends transactions at configurable intervals |
| Miner distributor | `agents.miner_distributor` | Distributes mining rewards to user wallets |
| Simulation monitor | `agents.simulation_monitor` | Tracks network stats and block generation |

### Network topologies

**Switch-based** (`type: "1_gbit_switch"`) - Simple shared network. Good for testing.

**GML-based** (`path: "topology.gml"`) - Realistic internet topology from CAIDA AS-links data. Supports variable bandwidth, latency, and packet loss per link. Agents are distributed geographically across 6 continents.

### Peer discovery modes

| Mode | Description |
|------|-------------|
| Dynamic | Automatic seed selection prioritizing miners |
| Hardcoded | Explicit seed nodes with topology templates (Star/Mesh/Ring/Dag) |
| Hybrid | Combines topology structure with dynamic discovery |

## Project Structure

```
monerosim/
  src/                       # Rust configuration engine
    main.rs                  # CLI entry point
    config_v2.rs             # Configuration structures
    config_loader.rs         # YAML loading and validation
    orchestrator.rs          # Shadow config generation
    gml_parser.rs            # GML topology parser
    agent/                   # Agent lifecycle and processing
    ip/                      # Geographic IP allocation
    process/                 # Daemon, wallet, script config
    topology/                # Network topology logic
    registry/                # Agent/miner registries
    shadow/                  # Shadow YAML output
  agents/                    # Python agent framework
    autonomous_miner.py      # Autonomous mining agent
    regular_user.py          # Transaction-sending user agent
    miner_distributor.py     # Mining reward distribution
    simulation_monitor.py    # Real-time monitoring
    agent_discovery.py       # Dynamic agent discovery
    base_agent.py            # Base agent class
    monero_rpc.py            # RPC client library
  scripts/                   # Utility scripts
    log_processor.py         # Log processing
    sync_check.py            # Blockchain sync monitoring
    migrate_mining_config.py # Config migration
    ai_config/               # LLM-based config generation
  gml_processing/            # CAIDA topology generation
  examples/                  # Example configurations
  docs/                      # Documentation
  monerosim.expanded.yaml    # Default configuration (expanded format for Rust engine)
  setup.sh                   # Environment setup
  run_sim.sh                 # Simulation runner
```

## Documentation

- [Configuration Guide](docs/CONFIGURATION.md) - Complete configuration reference
- [Architecture](docs/ARCHITECTURE.md) - System design and component details
- [Running Simulations](docs/RUNNING_SIMULATIONS.md) - End-to-end simulation workflow
- [Network Scaling Guide](docs/NETWORK_SCALING_GUIDE.md) - CAIDA topologies and large-scale simulations
- [How It Works](docs/FLOW.md) - Detailed mechanics of how monerosim interfaces with Shadow
- [Determinism Fixes](docs/DETERMINISM_FIXES.md) - Sources of non-determinism and fixes
- [AI Config Generator](docs/AI_CONFIG_GENERATOR.md) - LLM-based configuration generation

## Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| OS | Linux (Ubuntu 20.04+) | Ubuntu 22.04+ |
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16 GB (32 GB for 1000+ agents) |
| Storage | 10 GB | 20+ GB |
| Rust | 1.70+ | Latest stable |
| Python | 3.6+ | 3.8+ |

### Installation

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install build-essential cmake libglib2.0-dev libclang-dev clang

# Run the setup script (builds shadowformonero and Monero from source)
./setup.sh

# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r scripts/requirements.txt
```

Binaries are installed to `~/.monerosim/bin/` (shadow from shadowformonero, monerod and monero-wallet-rpc from official Monero).

## Contributing

1. Fork the repository and clone locally
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Run tests (`python3 scripts/run_all_tests.py`)
4. Commit with clear, descriptive messages
5. Push and submit a pull request

Code style: Rust uses `cargo fmt` and `cargo clippy`. Python follows PEP 8 (use `black`).

## License

MIT License - see [LICENSE](LICENSE) for details.
