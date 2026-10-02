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
  parallelism: 0                   # Shadow worker threads: 0=all free physical cores (run_sim.sh), 1=deterministic, N=fixed
  fresh_blockchain: true           # Start from genesis block
  log_level: info                  # Agent log level: trace/debug/info/warn/error
  shadow_log_level: info           # Shadow's own log level
  progress: true                   # Show simulation progress on stderr
  enable_dns_server: true          # Enable DNS server for monerod peer discovery
  bootstrap_end_time: "4h"         # High bandwidth / no packet loss until this time
  difficulty_cache_ttl: 30         # Seconds to cache difficulty in autonomous miners
  process_threads: 1               # Thread-pool size INSIDE each simulated daemon (not Shadow's; see `parallelism`)
  native_preemption: false         # Shadow native preemption (breaks determinism)

  # Default options applied to all daemons (overridable per-agent)
  daemon_defaults:
    log-level: 1
    max-log-file-size: 0
    db-sync-mode: fastest
    no-zmq: true
    non-interactive: true
    # max-connections-per-ip: 1
    #   If unset, monerosim injects 4 (stock monerod's default is 1; the cap
    #   counts simultaneous incoming connections per remote IP). 4 lets
    #   small/dense networks form stable meshes — at 15 nodes the stock
    #   default refuses thousands of same-IP connections and no mesh forms.
    #   At 1000-node scale the value makes no measurable difference
    #   (verified). Set to 1 to match stock monerod exactly.
    #   See docs/20260605_max_connections_per_ip_bug.md.

  # Default options applied to all wallets (overridable per-agent)
  wallet_defaults:
    log-level: 1
```

### General Field Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `stop_time` | string | required | Simulation duration |
| `simulation_seed` | u64 | 12345 | Seed for deterministic simulations |
| `parallelism` | u32 | 0 (auto) | Shadow worker threads, one per physical core. `run_sim.sh` gives each run its own cores: it skips cores that other live Shadow runs have pinned and starts Shadow under `taskset` with the rest. 0 takes every free core (Shadow's own auto mode would count only one socket's cores, 64 of 128 on a 2 x 64-core box). N takes N cores, which leaves the rest of the machine to runs started later. Set N if another simulation may run at the same time; see [Running several simulations at once](#running-several-simulations-at-once). Never more than the physical cores: two workers per core ran 1.29x slower. |
| `fresh_blockchain` | bool | true | Start from genesis |
| `log_level` | string | "info" | Agent log level |
| `shadow_log_level` | string | "info" | Shadow log level |
| `progress` | bool | true | Show progress on stderr |
| `enable_dns_server` | bool | - | Enable DNS discovery agent |
| `bootstrap_end_time` | string | - | Bootstrap period end time |
| `difficulty_cache_ttl` | u32 | 30 | Difficulty cache TTL (seconds) |
| `process_threads` | u32 | 1 | Thread-pool size inside **each simulated daemon**: monerod gets `--max-concurrency=N --prep-blocks-threads=N`; cuprated pins its tokio/rayon/storage pools to N. Not applied to wallet-rpc or Python agents. **Not** Shadow's worker-thread count (that is `parallelism`): cost scales with N x number of daemons, so keep it small (1 or 2). `0` omits the monerod flags, so every node sizes its pools from the host's core count. |
| `native_preemption` | bool | false | Shadow native preemption |
| `daemon_defaults` | map | - | Default daemon CLI options |
| `wallet_defaults` | map | - | Default wallet CLI options |
| `runahead` | string | - | Shadow runahead duration |
| `python_venv` | string | - | Path to Python virtual environment |

### Running several simulations at once

`parallelism: 0` (the default) gives a run **every physical core that no other
live Shadow run is using**, whether or not the run is big enough to use them.
A run started after it then finds no free cores and has to share them, so both
run slower (results are unaffected). If you plan to run more than one
simulation on the same machine, set `parallelism` explicitly in each config,
for example `64` on a 128-core box for two runs side by side. `run_sim.sh`
then gives each run that many cores of its own and leaves the rest for the
next one. A run that is already going keeps its cores until it ends.

Guidance:
- One run at a time: leave `parallelism: 0`.
- Two or more at a time: give each a share, with the shares adding up to no
  more than the physical cores. The preflight's `Shadow CPUs:` line shows what
  each run will get, and warns when a run has to share.
- Small runs cannot use many workers anyway: Shadow never starts more
  workers than there are hosts, and a ~240-host run kept 128 workers mostly
  spinning. Giving such a run fewer cores costs it little and frees them.
- Never more workers than physical cores: two per core (both hyperthreads)
  ran 1.29x slower than one per core.
- Outside the [Determinism](#determinism) recipe (`parallelism: 1`, no
  `native_preemption`, ...), runs are not reproducible even with the same
  config, seed and `parallelism`: three identical 1/10-scale eclipse runs
  (64 workers, `native_preemption: true`) ended with 4, 6 and 9 attacker
  connections to the target. Compare such runs with replicates, not seed for
  seed. No effect of `parallelism` on results has been shown beyond that
  spread (64 vs 128 workers: 8 vs 5).

Note: if `daemon_defaults` does not set `max-connections-per-ip`, monerosim
injects `4` (a floor, not a force — any user-provided value wins, including
stock monerod's default of `1`). See the commented example above and
`docs/20260605_max_connections_per_ip_bug.md` for why.

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

See `test_configs/quickstart.yaml` for a full working configuration. Additional working scenarios live alongside it in `test_configs/` (200-user/800-relay benchmark, upgrade smoke test, etc.).

## Determinism

For fully reproducible simulations:
1. Set `simulation_seed` to a fixed value
2. Set `parallelism: 1` (single-threaded Shadow)
3. Set `process_threads: 1`
4. Do not enable `native_preemption`

The same configuration with these settings will produce identical simulation results across runs.
