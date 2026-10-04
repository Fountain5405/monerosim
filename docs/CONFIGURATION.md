# Monerosim Configuration Guide

All Monerosim configurations are written in YAML. This document describes the current configuration format as implemented in the code.

## Configuration Structure

A configuration file has three top-level sections, plus an optional fourth:

```yaml
general:
  # Simulation parameters

network:
  # Network topology and peer discovery

agents:
  # Named agent definitions

performance:
  # Optional Shadow speed knobs (see Performance Section)
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
| `parallelism` | u32 | 0 (auto) | Shadow worker threads, one per physical core. `run_sim.sh` gives each run its own cores: it skips cores that other live Shadow runs have pinned and starts Shadow under `taskset` with the rest. 0 takes one core per simulated host, up to every free core (Shadow never runs more workers than hosts; its own auto mode would count only one socket's cores, 64 of 128 on a 2 x 64-core box). N takes N cores (again at most one per host), which leaves the rest of the machine to runs started later. Set N if another simulation may run at the same time; see [Running several simulations at once](#running-several-simulations-at-once). Never more than the physical cores: two workers per core ran 1.29x slower. |
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
| `mining.mode` | string | "generateblocks" | Block-production mode: `generateblocks` or `native`. See `docs/NATIVE_MINING.md` |
| `mining.chain_snapshot` | string | "auto" | Native mode only: preload a difficulty-warmed chain (`auto`, `off`, or a preset name/path; `auto` is a soft default — falls back to no preload with a warning if no matching preset exists). YAML booleans are accepted as aliases (`false` == `off`, `true` == `auto`). See `docs/CHAIN_SNAPSHOT.md` |

### Running several simulations at once

`parallelism: 0` (the default) gives a run **one physical core per simulated
host, up to every core that no other live Shadow run is using**. The
quickstart (18 hosts) takes 18 cores and leaves the rest free. A run with more
hosts than free cores takes all of them, whether or not it can keep them busy,
and a run started after it then finds no free cores and has to share them, so
both run slower (results are unaffected). If you plan to run more than one
simulation on the same machine, set `parallelism` explicitly in each config,
for example `64` on a 128-core box for two runs side by side. `run_sim.sh`
then gives each run that many cores of its own and leaves the rest for the
next one. A run that is already going keeps its cores until it ends.

Guidance:
- One run at a time: leave `parallelism: 0`.
- Two or more at a time: give each a share, with the shares adding up to no
  more than the physical cores. The preflight's `Shadow CPUs:` line shows what
  each run will get, and warns when a run has to share.
- Runs of a few hundred hosts gain little from many workers: a ~240-host
  eclipse run took 75-77 min of Shadow time with 16, 32 or 64 workers (one run
  each, two at 64). `parallelism: 16` for a run that size frees the other
  cores at no measurable cost. Larger runs have more parallel work (a
  2232-host run's simulated processes used ~14 cores across 64 workers); how
  far they scale has not been measured.
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

### RPC SSL

RPC SSL is off unless you turn it on. monerosim passes `--rpc-ssl=disabled`
to every monerod and `--rpc-ssl=disabled --daemon-ssl=disabled` to every
monero-wallet-rpc. With SSL at its stock setting, monerod and wallet-rpc
generate an RSA-4096 certificate on every start, ~1.1 wall-s per start under
Shadow. RPC SSL has no effect on P2P, and the Python agents and wallets talk
plain HTTP. See `docs/20261003_startup_cost.md`.

To turn it back on for every node (stock Monero behaviour):

```yaml
general:
  daemon_defaults:
    rpc-ssl: autodetect
  wallet_defaults:
    rpc-ssl: autodetect
    daemon-ssl: autodetect
```

For some nodes only, set the same keys in an agent's `daemon_options` /
`wallet_options`. A raw `--rpc-ssl=...` / `--daemon-ssl=...` in the agent's
args also works: monerosim then leaves that flag out instead of passing it
twice.

Use `autodetect`, not `enabled`. With `autodetect` monerod looks at the first
bytes of each RPC connection and uses TLS only if the client starts a TLS
handshake, so plain-HTTP clients keep working. `enabled` requires TLS on every
connection, and the Python agents, which only speak plain `http://`, then
cannot reach the daemon.

With SSL off, monerod's and cuprated's RPC both answer in plaintext, so the
TLS fingerprint described in `docs/20260724_cuprate_wallet_rpc.md` does not
show inside simulations; turn SSL back on to study it.

## Performance Section

Optional. Shadow-level knobs, written into the run's
`shadow_output/shadow_agents.yaml` under `experimental:`.

```yaml
performance:
  unblocked_vdso_busy_threshold: 10000   # fast monero process starts (= run_sim.sh --bootfast)
  unblocked_vdso_busy_latency: 1 us
```

| Field | Default | What it does |
|---|---|---|
| `unblocked_vdso_busy_threshold` | unset (off) | Clock reads in a row, with no other syscall, after which each further read charges `unblocked_vdso_busy_latency`. `10000` with `1 us` is what `--bootfast` sets: every monerod / monero-wallet-rpc start drops from ~16 to ~0.4 wall-s, and nothing else in the simulation changes (outside start-up, the longest run of clock reads measured was 371). **Needs shadowformonero v0.2.5+**; an older Shadow stops at launch with `unknown field 'unblocked_vdso_busy_threshold'`. |
| `unblocked_vdso_busy_latency` | `1 us` once the threshold is set | Simulated time per clock read past the threshold. |
| `unblocked_vdso_latency` | Shadow's 10 ns | Simulated time per clock read, always. `1 us` is what `--allfast` sets: same start-up cut, but every clock read in every process costs more sim time, so runs are not seed-for-seed comparable with runs made without it. Prefer the busy threshold. |
| `model_unblocked_syscall_latency` | `true` | Leave it on: `false` stalls Monerosim runs (`docs/PERFORMANCE_AND_SCALE.md`). |

`run_sim.sh --bootfast` / `--allfast` set the same fields for one run and
override the config's values. Put the block in the config when every run of it
should have it. Big runs gain the most: each monero process start used to hold
the whole simulation for ~17 wall-s, one after another (the 2,232-host eclipse
run spent 7.6 of ~22 wall-hours starting its 1,214 monero processes). How it
works: `docs/explain_clock_mods.md`; measurements:
`docs/20261003_startup_cost.md`.

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

Optional honest-node `/24` co-location (`prefix_sharing`): mainnet honest
nodes are concentrated on relatively few network prefixes (Kirschner 2026:
12% of BGP prefixes hold 55% of nodes), and monerosim otherwise gives every
GML node — and therefore every agent — its own `/24`. This knob moves
`fraction` of eligible honest daemons (non-miner, non-seed, unpinned) onto
shared GML nodes, `per_prefix` at a time, inside their home region, after the
base distribution and before any `topology_node` pins (which always win):
```yaml
network:
  path: "topology.gml"
  peer_mode: Dynamic
  distribution:
    prefix_sharing:
      fraction: 0.55   # 0.0-1.0: share of eligible honest daemons to co-locate
      per_prefix: 11   # 2-200: co-located agents per shared node
```
`per_prefix: 11` is the S11 dense-prefix figure, itself an **upper bound**: a
real BGP prefix is often wider than a single `/24`, so treat `per_prefix`
values near the high end as a stress case rather than a literal target.

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
| `topology_node` | u32 | Pin this agent to a specific GML topology node id, overriding index-based distribution |
| `turnover` | bool | Override this agent's `general.turnover` membership: `true` forces the daemon into the offline/online turnover cycle regardless of `fraction` — including a node that pins `hide-my-port: false` (normally exempt as an always-reachable hub); `false` always excludes it. Unset keeps the default (pinned-reachable excluded, others sampled at `fraction`). Miners and seed nodes are always excluded regardless. |

## Complete Example

See `test_configs/quickstart.yaml` for a full working configuration. Additional working scenarios live alongside it in `test_configs/` (200-user/800-relay benchmark, upgrade smoke test, etc.).

## Determinism

For fully reproducible simulations:
1. Set `simulation_seed` to a fixed value
2. Set `parallelism: 1` (single-threaded Shadow)
3. Set `process_threads: 1`
4. Do not enable `native_preemption`

The same configuration with these settings will produce identical simulation results across runs.
