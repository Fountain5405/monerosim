# Monerosim Configuration Guide

All Monerosim configurations are written in YAML. This document describes the current configuration format as implemented in the code.

## Configuration Structure

A configuration file has three top-level sections:

```yaml
general:
  # Simulation parameters

network:
  # Network topology and peer discovery

agents:
  # Named agent definitions
```

## General Section

```yaml
general:
  stop_time: "8h"                  # Required. Simulation duration (e.g., "30m", "2h", "8h")
  simulation_seed: 12345           # Global seed for deterministic simulations (default: 12345)
  parallelism: 0                   # Shadow worker threads: 0=auto, 1=deterministic, N=fixed
  fresh_blockchain: true           # Start from genesis block
  log_level: info                  # Agent log level: trace/debug/info/warn/error
  shadow_log_level: info           # Shadow's own log level
  progress: true                   # Show simulation progress on stderr
  enable_dns_server: true          # Enable DNS server for monerod peer discovery
  bootstrap_end_time: "4h"         # High bandwidth / no packet loss until this time
  difficulty_cache_ttl: 30         # Seconds to cache difficulty in autonomous miners
  process_threads: 1               # Thread count for monerod/wallet-rpc (1=deterministic)
  native_preemption: false         # Shadow native preemption (breaks determinism)

  # Default options applied to all daemons (overridable per-agent)
  daemon_defaults:
    log-level: 1
    log-file: /dev/stdout
    db-sync-mode: fastest
    no-zmq: true
    non-interactive: true
    disable-rpc-ban: true
    allow-local-ip: true

  # Default options applied to all wallets (overridable per-agent)
  wallet_defaults:
    log-level: 1
    log-file: /dev/stdout
```

### General Field Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `stop_time` | string | required | Simulation duration |
| `simulation_seed` | u64 | 12345 | Seed for deterministic simulations |
| `parallelism` | u32 | 0 (auto) | Shadow worker threads |
| `fresh_blockchain` | bool | true | Start from genesis |
| `log_level` | string | "info" | Agent log level |
| `shadow_log_level` | string | "info" | Shadow log level |
| `progress` | bool | true | Show progress on stderr |
| `enable_dns_server` | bool | - | Enable DNS discovery agent |
| `bootstrap_end_time` | string | - | Bootstrap period end time |
| `difficulty_cache_ttl` | u32 | 30 | Difficulty cache TTL (seconds) |
| `process_threads` | u32 | 1 | monerod/wallet thread count |
| `native_preemption` | bool | false | Shadow native preemption |
| `daemon_defaults` | map | - | Default daemon CLI options |
| `wallet_defaults` | map | - | Default wallet CLI options |
| `runahead` | string | - | Shadow runahead duration |
| `python_venv` | string | - | Path to Python virtual environment |

## Network Section

The network section configures the virtual network topology. There are two modes:

### Switch-Based Network (simple)

```yaml
network:
  type: "1_gbit_switch"
  peer_mode: Dynamic
  topology: Dag
```

All hosts share a single high-bandwidth switch. Good for development and testing.

### GML-Based Network (realistic)

```yaml
network:
  path: "gml_processing/1200_nodes_caida_with_loops.gml"
  peer_mode: Dynamic
```

Uses a GML topology file (typically generated from CAIDA AS-links data) for realistic internet topology with variable bandwidth, latency, and packet loss per link.

Optional distribution strategy for GML topologies:
```yaml
network:
  path: "topology.gml"
  peer_mode: Dynamic
  distribution:
    strategy: Weighted       # Global (default), Sequential, or Weighted
    weights:
      north_america: 40
      europe: 30
      asia: 20
      south_america: 5
      africa: 3
      oceania: 2
```

### Peer Discovery Modes

| Mode | Description |
|------|-------------|
| `Dynamic` | Automatic seed selection, miners prioritized. No manual config needed. |
| `Hardcoded` | Explicit seed nodes required. Use with topology templates. |
| `Hybrid` | Combines GML topology with dynamic discovery. |

For Hardcoded/Hybrid modes, provide seed nodes:
```yaml
network:
  type: "1_gbit_switch"
  peer_mode: Hardcoded
  seed_nodes:
    - "10.0.0.1:28080"
    - "10.0.0.2:28080"
  topology: Star             # Star, Mesh, Ring, or Dag
```

### Topology Templates

| Template | Description |
|----------|-------------|
| `Star` | All nodes connect to a central hub (first agent) |
| `Mesh` | Fully connected. Gets slow with >50 agents |
| `Ring` | Circular connections. Minimum 3 agents |
| `Dag` | Hierarchical connections. Default |

## Agents Section

Agents are defined as a flat named map. Each key is the agent's unique ID.

### Miner Agent

```yaml
agents:
  miner-001:
    daemon: monerod
    wallet: "monero-wallet-rpc"
    script: agents.autonomous_miner
    start_time: 0s
    hashrate: 25
    can_receive_distributions: true
```

Miners are identified by having a `hashrate` value. The hashrate values across all miners should sum to 100 (representing percentage of total network hashrate).

### Regular User Agent

```yaml
agents:
  user-001:
    daemon: monerod
    wallet: "monero-wallet-rpc"
    script: agents.regular_user
    start_time: 3h
    transaction_interval: 60
    activity_start_time: 18000
    can_receive_distributions: true
```

### Miner Distributor

Distributes mining rewards to eligible wallets:

```yaml
agents:
  miner-distributor:
    script: agents.miner_distributor
    wait_time: 14400
    initial_fund_amount: "1.0"
    max_transaction_amount: "2.0"
    min_transaction_amount: "0.5"
    transaction_frequency: 30
```

### Simulation Monitor

```yaml
agents:
  simulation-monitor:
    script: agents.simulation_monitor
    poll_interval: 300
    detailed_logging: false
    enable_alerts: true
    status_file: monerosim_monitor.log
```

### Wallet-Only Agent (Remote Daemon)

Connect a wallet to a remote public daemon instead of running a local one:

```yaml
agents:
  light-user-001:
    daemon:
      address: "auto"              # "auto" for discovery, or specific "ip:port"
      strategy: random             # random, first, or round_robin
    wallet: "monero-wallet-rpc"
    script: agents.regular_user
    start_time: 3h
    transaction_interval: 120
```

### Per-Agent Overrides

Override global daemon/wallet defaults for specific agents:

```yaml
agents:
  debug-miner:
    daemon: monerod
    wallet: "monero-wallet-rpc"
    script: agents.autonomous_miner
    hashrate: 50
    daemon_options:
      log-level: 4                 # Override to trace logging
    wallet_options:
      log-level: 3
```

### Daemon/Wallet Phases (Upgrade Scenarios)

For simulating binary upgrades mid-simulation:

```yaml
agents:
  upgrade-miner:
    wallet: "monero-wallet-rpc"
    script: agents.autonomous_miner
    hashrate: 30
    daemon_0: "monerod_v1"
    daemon_0_start: "0s"
    daemon_0_stop: "2h"
    daemon_1: "monerod_v2"
    daemon_1_start: "2h30s"
```

Phase numbering must be sequential (0, 1, 2, ...). Non-final phases require a `stop` time. There must be at least 30 seconds between a phase's stop and the next phase's start.

### Subnet Groups

Group agents into the same /24 subnet (useful for simulating Sybil attacks):

```yaml
agents:
  attacker-001:
    daemon: monerod
    script: agents.autonomous_miner
    hashrate: 5
    subnet_group: "sybil_cluster"
  attacker-002:
    daemon: monerod
    script: agents.autonomous_miner
    hashrate: 5
    subnet_group: "sybil_cluster"
```

## Agent Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `daemon` | string or object | `"monerod"` for local, or `{address, strategy}` for remote |
| `wallet` | string | Wallet binary name (e.g., `"monero-wallet-rpc"`) |
| `script` | string | Python script module (e.g., `"agents.autonomous_miner"`) |
| `start_time` | string | When to start this agent (e.g., `"0s"`, `"3h"`) |
| `hashrate` | u32 | Mining hashrate (presence identifies agent as miner) |
| `transaction_interval` | u32 | Seconds between transactions (regular users) |
| `activity_start_time` | u32 | Seconds from sim start when activity begins |
| `can_receive_distributions` | bool | Whether miner_distributor can fund this agent |
| `wait_time` | u32 | Miner distributor: seconds before starting |
| `initial_fund_amount` | string | Miner distributor: initial fund amount in XMR |
| `max_transaction_amount` | string | Max transaction amount in XMR |
| `min_transaction_amount` | string | Min transaction amount in XMR |
| `transaction_frequency` | u32 | Miner distributor: seconds between distributions |
| `poll_interval` | u32 | Monitor: seconds between status checks |
| `status_file` | string | Monitor: path for status output |
| `enable_alerts` | bool | Monitor: enable alert notifications |
| `detailed_logging` | bool | Monitor: verbose logging |
| `daemon_options` | map | Per-agent daemon CLI overrides |
| `wallet_options` | map | Per-agent wallet CLI overrides |
| `daemon_env` | map | Environment variables for daemon |
| `wallet_env` | map | Environment variables for wallet |
| `attributes` | map | Custom key-value pairs passed to agent scripts |
| `subnet_group` | string | Group agents into same /24 subnet |

## Complete Example

See `test_configs/20260112_config.yaml` for a full working configuration, or check the `examples/` directory.

Additional examples in `examples/`:
- `config_caida_large_scale.yaml` - CAIDA-based topology
- `config_large_scale.yaml` - Large network simulation
- `config_sparse_placement.yaml` - Sparse agent placement

## Determinism

For fully reproducible simulations:
1. Set `simulation_seed` to a fixed value
2. Set `parallelism: 1` (single-threaded Shadow)
3. Set `process_threads: 1`
4. Do not enable `native_preemption`

The same configuration with these settings will produce identical simulation results across runs.
