# Monerosim

A tool for running Monero cryptocurrency network simulations inside the [Shadow](https://shadow.github.io/) network simulator. Monerosim generates Shadow configuration files from a concise YAML description of your desired network, then Shadow executes the simulation using real Monero binaries in a virtual network.

> **Tip:** We recommend running monerosim on a dedicated Linux user account (e.g., `sudo useradd -m monerosim`). Monerosim manages several daemons, writes to `/tmp`, and cleans up simulation state between runs. A dedicated user keeps things isolated from your other work.

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

**Stage 2** - shadowformonero runs the simulation. Each agent gets its own monerod daemon, wallet-rpc, and Python script running on a virtual host. Miners generate blocks autonomously using Poisson-distributed timing. Users send transactions. Agents discover each other through shared state files. Simulation output is written to `/tmp/monero-*/bitmonero.log` (daemon logs), `shadow.data/` (agent stdout), and `/tmp/monerosim_shared/` (shared state).

## Quick Start

```bash
# 1. Clone and set up (builds everything: ~30-60 minutes)
git clone https://github.com/Fountain5405/monerosim.git
cd monerosim
./setup.sh

# 2. Verify installation
~/.monerosim/bin/shadow --version      # shadowformonero version
~/.monerosim/bin/monerod --version     # Monero daemon version
./target/release/monerosim --help      # monerosim CLI usage

# 3. Run a test simulation (~10-15 min wall clock)
./run_sim.sh --config test_configs/quickstart.yaml

# 4. Monitor progress
tail -f /tmp/monerosim_shared/monerosim_monitor.log
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
```

Each agent is identified by its key name (e.g., `miner-001`). Miners are identified by having a `hashrate` value. The hashrate values across all miners should sum to 100.

See [`test_configs/`](test_configs/) for working configurations — `quickstart.yaml` is the entry point, with progressively larger scenarios alongside it.

For large-scale simulations, use the config generator:

```bash
source venv/bin/activate
python scripts/generate_config.py --agents 100 --duration 8h -o my_config.yaml
```

Or generate configs with natural language using the AI config tool (requires an LLM API key):

```bash
./smart_config_tool.sh "5 miners, 20 users, 8h simulation"
./smart_config_tool.sh   # Interactive mode
```

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

User-facing agents you place in the YAML:

| Agent | Script | Purpose |
|-------|--------|---------|
| Autonomous miner | `agents.autonomous_miner` | Generates blocks with Poisson-distributed timing |
| Regular user | `agents.regular_user` | Sends transactions at configurable intervals |
| Miner distributor | `agents.miner_distributor` | Distributes mining rewards to user wallets |
| Simulation monitor | `agents.simulation_monitor` | Tracks network stats and block generation |

Infrastructure agents auto-spawned by the orchestrator (not declared in YAML):
`agents.dns_server` (in-sim DNS for monerod peer discovery). The
`agents.agent_discovery` and `agents.public_node_discovery` modules are
shared-state helpers imported by the user-facing agents above.

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
    config/                  # Configuration structures (types, validation, defaults, ...)
    config_loader.rs         # YAML loading and validation
    orchestrator.rs          # Shadow config generation
    gml_parser.rs            # GML topology parser
    agent/                   # Agent lifecycle and processing
    analysis/                # Post-simulation log analysis (LLM-generated, unverified)
    bin/                     # Auxiliary binaries (e.g. tx_analyzer)
    ip/                      # Geographic IP allocation
    process/                 # Daemon, wallet, script config
    topology/                # Network topology logic and peer connections
    shadow/                  # Shadow YAML output
    utils/                   # Shared utilities (duration parsing, validation, ...)
  agents/                    # Python agent framework
    autonomous_miner.py      # Autonomous mining agent
    regular_user.py          # Transaction-sending user agent
    miner_distributor/       # Mining reward distribution (package)
    simulation_monitor/      # Real-time monitoring (package)
    agent_discovery.py       # Dynamic agent discovery
    public_node_discovery.py # Public daemon discovery
    dns_server.py            # In-sim DNS for monerod peer discovery
    base_agent.py            # Base agent class
    monero_rpc.py            # RPC client library
    test_*.py                # Tier 1 unit tests for the agents
  scripts/                   # Utility scripts
    check_sim.sh             # Real-time simulation status dashboard
    generate_config.py       # Config generator for large simulations
    config_generation/       # Helpers used by generate_config.py
    monero_verification.py   # RPC/log verification helpers
    smoke_test.sh            # Tier 2 smoke wrapper around run_sim.sh
    smoke_assertions.py      # Stricter post-run assertion checker
    run_sim_helpers.py       # Python helpers extracted from run_sim.sh
    ai_config/               # LLM-based config generation
  tests/                     # Rust integration tests + golden/baseline fixtures
    orchestrator_smoke.rs
    orchestrator_quickstart.rs
    baselines/               # Smoke-test baselines (e.g. quickstart_metrics.json)
  attic/                     # Ad-hoc / unmaintained tools (see attic/README.md)
  gml_processing/            # CAIDA topology generation
  docs/                      # Documentation
  test_configs/              # Configuration files (scenarios + expanded)
  setup.sh                   # Environment setup (~30-60 min)
  run_sim.sh                 # Quick simulation runner
  smart_config_tool.sh       # AI-powered config generator (requires LLM API key)
```

## Documentation

- [Quick Start](QUICKSTART.md) - Installation and first simulation
- [Configuration Guide](docs/CONFIGURATION.md) - Complete configuration reference
- [Architecture](docs/ARCHITECTURE.md) - System design and component details
- [Running Simulations](docs/RUNNING_SIMULATIONS.md) - End-to-end simulation workflow
- [Network Scaling Guide](docs/NETWORK_SCALING_GUIDE.md) - CAIDA topologies and large-scale simulations
- [Performance and Scale Limits](docs/PERFORMANCE_AND_SCALE.md) - Speed knobs, per-machine safe-N caps, and auto-config guardrails
- [How It Works](docs/FLOW.md) - Detailed mechanics of how monerosim interfaces with Shadow
- [Determinism Fixes](docs/DETERMINISM_FIXES.md) - Sources of non-determinism and fixes
- [AI Config Generator](docs/AI_CONFIG_GENERATOR.md) - LLM-based configuration generation

## Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| OS | Linux (Ubuntu 20.04+) | Ubuntu 22.04+ |
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB (bare minimum — runs the quickstart only, with memory pressure) | 16 GB for any real work (32 GB for 1000+ agents) — see [docs/PERFORMANCE_AND_SCALE.md](docs/PERFORMANCE_AND_SCALE.md) for the RAM-vs-agent-count table |
| Storage | 30 GB free | 50+ GB |
| Rust | 1.80+ | Latest stable |
| Python | 3.10+ | 3.10+ |

### Installation

Install the minimal prerequisites for your distro, then run `setup.sh`.

**Debian/Ubuntu (apt):**

```bash
sudo apt-get update
sudo apt-get install git build-essential cmake libglib2.0-dev libclang-dev clang
```

**RHEL/Fedora/Rocky/Alma (dnf):**

```bash
# On RHEL/Rocky/Alma, enable EPEL first (Fedora has it built in):
# sudo dnf install epel-release
sudo dnf install git cmake glib2-devel clang clang-devel
sudo dnf groupinstall "Development Tools"
```

> Note: RHEL / Rocky / Alma **9** is not currently supported — `simulation_monitor`
> exits without writing `final_report.json` on EL9, causing Shadow to abort the
> sim early. EL10 (Rocky 10 / RHEL 10 / Alma 10) and Fedora work. See
> [PORTABILITY.md](PORTABILITY.md) for details.

**Arch/Manjaro (pacman):**

```bash
sudo pacman -S --needed git base-devel cmake glib2 clang
```

**openSUSE (zypper):**

```bash
sudo zypper install git cmake glib2-devel clang clang-devel gcc gcc-c++ make
```

After prerequisites are installed, `./setup.sh` handles the rest — it auto-detects your package manager and installs the build dependencies for shadowformonero and Monero.

```bash
# Optional: use a dedicated user account (recommended)
sudo useradd -m monerosim
sudo su - monerosim

# Clone and run setup (builds shadowformonero and Monero from source)
git clone https://github.com/Fountain5405/monerosim.git
cd monerosim
./setup.sh
```

Setup installs all binaries to `~/.monerosim/bin/`:
- `shadow` (from shadowformonero)
- `monerod` (from official Monero)
- `monero-wallet-rpc` (from official Monero)

It also builds monerosim itself (`cargo build --release`), creates a Python virtual environment, and generates a test Shadow configuration.

### Verify Installation

```bash
~/.monerosim/bin/shadow --version      # shadowformonero version
~/.monerosim/bin/monerod --version     # Monero daemon version
./target/release/monerosim --help      # monerosim CLI usage
source venv/bin/activate && python -c "import agents; print('Python agents OK')"
```

## Updating

To update monerosim and its dependencies after initial setup:

```bash
./update.sh              # Update monerosim only
./update.sh --all        # Update all repos (monerosim + shadowformonero + monero)
./update.sh --rebuild    # Rebuild binaries after updating
```

## Testing

The Tier 2 smoke test runs a real Shadow simulation end-to-end and then evaluates the resulting archive against a stricter baseline than the default 4 PASS/FAIL success criteria (block height, blocks-mined floor, per-node height spread, per-user transaction floor, disallowed log patterns, etc.). It exists to catch regressions that the loose default checks miss (e.g., wallets sending only a handful of transactions before dying).

```bash
./scripts/smoke_test.sh                # quickstart, ~15 min wall
./scripts/smoke_test.sh quickstart
./scripts/smoke_test.sh refactor_gate  # any scenario with a YAML + baseline
```

Run it pre-release and after non-trivial changes to the agents or orchestrator. Exit code 0 = all assertions PASS; non-zero = at least one assertion failed (see `scripts/smoke_test.sh` for the exit-code map).

Baselines live at `tests/baselines/<scenario>_metrics.json` and capture the expected envelope (wall-time cap, height floor, transaction floors, etc.) for that scenario. To add or refresh one, run a known-good simulation, then copy the canonical metrics from the resulting `archived_runs/<TS>_<scenario>/summary.txt` into a new `<scenario>_metrics.json` (see the existing quickstart baseline for the schema).

## Contributing

1. Fork the repository and clone locally
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Run tests (`cargo test`)
4. Commit with clear, descriptive messages
5. Push and submit a pull request

Code style: Rust uses `cargo fmt` and `cargo clippy`. Python follows PEP 8 (use `black`).

## License

BSD 3-Clause License - see [LICENSE](LICENSE) for details.
