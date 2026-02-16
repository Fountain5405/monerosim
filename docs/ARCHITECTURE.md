# Monerosim Architecture

## System Overview

Monerosim is a Rust-based configuration generator that produces configurations for [shadowformonero](https://github.com/Fountain5405/shadowformonero) (a Shadow network simulator fork with Monero socket compatibility) to run Monero cryptocurrency network simulations. It pairs a Rust core for config generation with a Python agent framework for autonomous network behaviors. Monero binaries are built from the official `monero-project/monero` repository and run unmodified inside the simulator.

## Simulation Flow

```
                         +---------------------+
                         |  User Config (YAML)  |
                         +----------+----------+
                                    |
                                    v
                    +-------------------------------+
                    | Rust Configuration Engine     |
                    |  - Parse & validate YAML      |
                    |  - Load GML topology (if any) |
                    |  - Allocate IPs (geographic)   |
                    |  - Generate peer connections   |
                    |  - Write agent/miner registries|
                    +---------------+---------------+
                                    |
                                    v
                    +-------------------------------+
                    | Shadow Config (YAML)          |
                    |  shadow_output/               |
                    |    shadow_agents.yaml          |
                    +---------------+---------------+
                                    |
                                    v
                    +-------------------------------+
                    | shadowformonero               |
                    |  (Shadow fork for Monero)      |
                    |                               |
                    |  Per host:                    |
                    |   - monerod daemon            |
                    |   - monero-wallet-rpc         |
                    |   - Python agent script       |
                    |                               |
                    |  Virtual network connects     |
                    |  all hosts together            |
                    +---------------+---------------+
                                    |
                                    v
                    +-------------------------------+
                    | Simulation Output             |
                    |  - shadow.data/hosts/*/       |
                    |  - /tmp/monerosim_shared/     |
                    +---------------+---------------+
                                    |
                                    v
                    +-------------------------------+
                    | Post-Simulation Analysis      |
                    |  - tx-analyzer (Rust)         |
                    |  - tx_analyzer.py (Python)    |
                    |  - log_processor.py           |
                    +-------------------------------+
```

## Core Components

### 1. Rust Configuration Engine (`src/`)

The Rust core parses a user-written YAML configuration and generates the Shadow configuration files needed to run the simulation.

**Entry point**: `src/main.rs` - CLI using clap. Accepts `--config` (required) and `--output` (default: `shadow_output`).

**Key modules**:

| Module | Purpose |
|--------|---------|
| `config_v2.rs` | Type-safe configuration structures (serde YAML) |
| `config_loader.rs` | Config file loading, validation, and migration |
| `orchestrator.rs` | Main orchestration: coordinates all generation steps |
| `gml_parser.rs` | GML graph format parser for complex topologies |

**Modular sub-packages**:

| Package | Purpose |
|---------|---------|
| `src/agent/` | Agent lifecycle and processing |
| `src/ip/` | IP allocation with geographic distribution (6 continents) |
| `src/process/` | Process configuration (daemon, wallet, agent scripts) |
| `src/registry/` | Agent and miner registry generation |
| `src/shadow/` | Shadow YAML output structures |
| `src/topology/` | Network topology logic and agent distribution |
| `src/utils/` | Shared utilities (validation, duration parsing, logging) |
| `src/mining_shim/` | Mining strategy implementations |
| `src/analysis/` | Transaction routing analysis modules (LLM-generated, unverified) |

### 2. Python Agent Framework (`agents/`)

Agents are autonomous participants that run inside Shadow alongside monerod and wallet-rpc processes.

| Agent | Purpose |
|-------|---------|
| `base_agent.py` | Abstract base class with lifecycle management |
| `autonomous_miner.py` | Independent mining with Poisson-distributed block times |
| `regular_user.py` | Sends transactions at configurable intervals |
| `miner_distributor.py` | Distributes mining rewards to eligible wallets |
| `simulation_monitor.py` | Real-time monitoring and status reporting |
| `agent_discovery.py` | Dynamic agent discovery via shared state (5-sec TTL cache) |
| `monero_rpc.py` | RPC client library for monerod and wallet-rpc |
| `public_node_discovery.py` | Discovers public seed nodes |
| `dns_server.py` | DNS server for monerod peer discovery |

**Agent communication** is decentralized, using shared state files:

```
/tmp/monerosim_shared/
  agent_registry.json      # All agents and their attributes
  miners.json              # Miner hashrate weights
  transactions.json        # Transaction log
  [agent]_stats.json       # Per-agent statistics
```

### 3. shadowformonero Integration

Monerosim uses [shadowformonero](https://github.com/Fountain5405/shadowformonero), a fork of the Shadow network simulator with Monero socket compatibility patches. Standard Monero binaries (built from the official `monero-project/monero` repository) run unmodified inside the simulator.

Monerosim generates a Shadow configuration that defines:

- **Network topology** (switch-based or GML-based)
- **Host definitions** with geographically distributed IPs
- **Process configurations** per host (monerod, monero-wallet-rpc, Python agent)
- **Peer connections** based on the chosen discovery mode
- **Startup scheduling** with staggered times to prevent thundering herd

shadowformonero then executes the entire simulation deterministically within a single process, using its virtual network to connect all hosts.

### 4. Analysis Tools (LLM-generated, unverified)

Post-simulation analysis tools exist in both Rust and Python, but these were LLM-generated and have not been human-verified for correctness. See [ANALYSIS_TOOLS.md](ANALYSIS_TOOLS.md) for details.

- **Rust**: `src/bin/tx_analyzer.rs`
- **Python**: `scripts/tx_analyzer.py`

## Network Architecture

### Two Topology Modes

**Switch-based** (simple, fast):
```yaml
network:
  type: "1_gbit_switch"
```
All hosts share a single high-bandwidth switch. Best for development and small-scale testing.

**GML-based** (realistic):
```yaml
network:
  path: "gml_processing/1200_nodes_caida_with_loops.gml"
```
Uses CAIDA AS-links data for authentic internet topology. Supports variable bandwidth, latency, and packet loss per link. Best for research simulations.

### Peer Discovery Modes

| Mode | Description | Best for |
|------|-------------|----------|
| Dynamic | Automatic seed selection prioritizing miners | Research simulations |
| Hardcoded | Explicit topology (Star/Mesh/Ring/DAG templates) | Controlled experiments |
| Hybrid | GML topology + dynamic discovery | Production-like simulations |

### IP Allocation

Agents are distributed geographically across 6 continents using subnet-based allocation:

| Region | IP range |
|--------|----------|
| North America | 10.x.x.x |
| Europe | 172.16+.x.x |
| Asia | 203.x.x.x |
| South America | 200.x.x.x |
| Africa | 197.x.x.x |
| Oceania | 202.x.x.x |

## Mining Architecture

Monerosim uses **autonomous mining** where each miner agent independently generates blocks:

- Block times follow a Poisson distribution for realism
- Each miner's `hashrate` value determines its mining probability relative to others
- Fully deterministic when using the same `simulation_seed`
- No centralized coordinator needed

## Key Design Decisions

1. **Rust core** for memory safety, performance, and strong typing in config generation
2. **Python agents** for rapid development, accessible RPC libraries, and research flexibility
3. **shadowformonero** to run unmodified official Monero binaries in a virtual network (high fidelity vs simplified models)
4. **Custom GML parser** optimized for Shadow's requirements
5. **Decentralized agent coordination** via shared state files rather than direct communication
6. **Geographic IP distribution** for realistic internet structure modeling

## File Layout

```
monerosim/
  src/                    # Rust configuration engine
  agents/                 # Python agent framework
  scripts/                # Utility scripts (analysis, migration, generation)
  gml_processing/         # CAIDA topology generation
  examples/               # Example configurations
  docs/                   # Documentation
  monerosim.expanded.yaml # Default configuration (expanded format for Rust engine)
  setup.sh                # Environment setup
  run_sim.sh              # Simulation runner
```

## Generated Output

```
shadow_output/
  shadow_agents.yaml      # Main Shadow configuration
  scripts/                # Pre-written wrapper scripts for all Python agents

/tmp/monerosim_shared/
  agent_registry.json     # Agent metadata for discovery
  miners.json             # Miner hashrate distribution
  public_nodes.json       # Public node registry
  [agent]_wallet/         # Pre-created wallet directories

shadow.data/              # Created by Shadow during simulation
  hosts/
    [hostname]/
      monerod.*.stdout    # Daemon logs
      wallet.*.stdout     # Wallet logs
      bash.*.stdout       # Agent logs
```
