# Scenario File Format

Scenario files are a compact YAML format for defining monerosim simulations. They support range expansion, stagger fields, and automatic timing — features not available in the flat expanded YAML format (`.expanded.yaml`) that the Rust binary consumes.

## Expanding a Scenario

```bash
python3 scripts/generate_config.py --from my_scenario.yaml -o expanded.yaml
```

This parses the scenario, expands ranges and staggers, resolves `auto` values, and writes a flat `.expanded.yaml` file. You then run the simulation with:

```bash
target/release/monerosim --config expanded.yaml
~/.monerosim/bin/shadow shadow_output/shadow_agents.yaml
```

## Top-Level Sections

```yaml
general:        # Simulation settings (stop_time, seed, defaults, etc.)
network:        # Network topology configuration
agents:         # Agent definitions — the core section
timing:         # Optional overrides for bootstrap/activity timing
```

`general` and `network` are passed through as-is to the expanded config. `agents` is expanded (ranges, staggers, auto values). `timing` controls the automatic timing calculations and is consumed during expansion.

## Range Expansion

Agent IDs with `{START..END}` expand to multiple agents:

```yaml
agents:
  miner-{001..005}:     # Creates miner-001 through miner-005
    daemon: monerod
    hashrate: 25
```

Zero-padding is auto-detected from the start number:

| Pattern | Result |
|---------|--------|
| `miner-{001..005}` | miner-001, miner-002, ..., miner-005 (3-digit) |
| `user-{1..100}` | user-1, user-2, ..., user-100 (no padding) |
| `spy-{01..10}` | spy-01, spy-02, ..., spy-10 (2-digit) |

Agent IDs without `{...}` are singletons — one instance with properties as-is:

```yaml
agents:
  miner-distributor:
    script: agents.miner_distributor
    wait_time: auto
```

## Stagger Fields

Any field can be staggered across agents in a group by adding a `_stagger` suffix:

```yaml
miner-{001..005}:
  start_time: 0s              # Base value
  start_time_stagger: 1s      # Increment per agent
  # Result: 0s, 1s, 2s, 3s, 4s
```

### Stagger Types

**Linear** — fixed interval between agents:

```yaml
start_time: 0s
start_time_stagger: 5s        # 0s, 5s, 10s, 15s, ...
```

**Auto** — selects batched or linear based on group size:

```yaml
start_time: 0s
start_time_stagger: auto
# count >= 50: batched (exponential batch growth)
# count < 50:  linear with 5s interval
```

**Batched** — exponential batch growth for large groups:

```yaml
start_time: 0s
start_time_stagger: batched
```

Batched spawning starts with 5 agents, doubles each batch, up to 200 per batch, with 20 minutes between batches and 5s within-batch stagger. This prevents overwhelming Shadow when many agents start simultaneously.

**Random range** — uniform random per agent:

```yaml
start_time: 0s
start_time_stagger: {range: [10, 30]}   # Random 10-30s offset per agent
```

### Default Staggers

When a multi-agent group omits a `_stagger` field, defaults are applied automatically:

| Agent type | Default `start_time_stagger` |
|------------|------------------------------|
| Users (`agents.regular_user`) | `auto` |
| Miners (`agents.autonomous_miner`) | `1s` |
| Daemon-only (relay nodes) | `5s` |

Daemon upgrade fields (`daemon_0_stop`) default to `30s` stagger when omitted.

### Stagger Continuation for Upgrades

Daemon `_stop` staggers continue their offset across groups so upgrades roll through the network sequentially:

```yaml
miner-{001..005}:
  daemon_0_stop: 36000s
  daemon_0_stop_stagger: 30s     # 36000, 36030, 36060, 36090, 36120

user-{001..020}:
  daemon_0_stop: 36000s
  daemon_0_stop_stagger: 30s     # Continues: 36150, 36180, 36210, ...
```

## Per-Agent Lists

Any field can accept a list with one value per agent:

```yaml
miner-{001..005}:
  hashrate: [30, 25, 20, 15, 10]    # List length must == agent count
```

Agent 001 gets 30, 002 gets 25, etc. No `_stagger` suffix needed for lists.

## The `auto` Keyword

`auto` resolves differently depending on the field:

| Field | Resolves to |
|-------|-------------|
| `bootstrap_end_time` | `max(4h, last_bootstrap_spawn * 1.2)` |
| `activity_start_time` | Staggered per-user times starting at `md_start + 1h` |
| `wait_time` | `md_start_time` (for miner-distributor) |
| `daemon_0_start` | Agent's `start_time` |
| `daemon_1_start` | `daemon_0_stop + 30s` |

## Daemon Phases (Upgrade Scenarios)

Daemon phases allow binary upgrades mid-simulation:

```yaml
miner-{001..005}:
  daemon_0: monerod-v1           # Phase 0 binary
  daemon_0_start: auto           # = start_time
  daemon_0_stop: 25200s          # When to kill v1
  daemon_0_stop_stagger: 30s     # Rolling upgrade
  daemon_1: monerod-v2           # Phase 1 binary
  daemon_1_start: auto           # = daemon_0_stop + 30s
  wallet: monero-wallet-rpc
  script: agents.autonomous_miner
  hashrate: [30, 25, 20, 15, 10]
```

Phase numbering must be sequential (0, 1, 2, ...). There must be at least 30 seconds between a phase's stop and the next phase's start.

## Timing Section

The optional `timing` section overrides automatic timing calculations:

```yaml
timing:
  user_spawn_start: 14h           # When users begin spawning
  bootstrap_end_time: 20h         # When bootstrap period ends
  md_start_time: 18h              # When miner-distributor starts funding
  activity_start_time: 20h        # When users start transacting
  activity_batch_size: 15         # Users per activity batch (default: 10)
  activity_batch_interval: 10m    # Between activity batches (default: 5m)
  activity_batch_jitter: 0.30     # +/- randomization fraction (default: 0.30)
```

All fields are optional. When omitted, timing is calculated automatically:

1. **Bootstrap end** = `max(4h, last_bootstrap_participant_spawn * 1.2)`
2. **Miner distributor start** = bootstrap end
3. **Activity start** = miner distributor start + 1h
4. **Activity batching** = 10 users per batch, 5 minutes apart, +/-30% jitter

Bootstrap participants are agents that start within the first hour and have `activity_start_time: auto`, are miners, or are daemon-only relay nodes.

## Duration Format

Time strings are accepted everywhere: `5s`, `30m`, `3h`, `3h30m`, or plain integers (interpreted as seconds).

## Agent Types

### Miners

```yaml
miner-{001..005}:
  daemon: monerod
  wallet: monero-wallet-rpc
  script: agents.autonomous_miner
  start_time: 0s
  start_time_stagger: 1s
  hashrate: [30, 25, 20, 15, 10]    # Should sum to 100 for initial miners
  can_receive_distributions: true
```

### Users

```yaml
user-{001..050}:
  daemon: monerod
  wallet: monero-wallet-rpc
  script: agents.regular_user
  start_time: 1200s
  start_time_stagger: auto
  transaction_interval: 60
  activity_start_time: auto
  can_receive_distributions: true
```

### Relay Nodes (daemon-only)

Run monerod for P2P block/transaction relay only. No wallet, no script, no transactions.

```yaml
relay-{001..020}:
  daemon: monerod
  start_time: 0s
  start_time_stagger: 5s
```

### Spy Nodes

Users with high peer counts for monitoring network propagation:

```yaml
spy-{001..003}:
  daemon: monerod
  wallet: monero-wallet-rpc
  script: agents.regular_user
  start_time: 0s
  daemon_options:
    out-peers: 100
    in-peers: 100
  subnet_group: spy_cluster
```

### Support Agents (singletons)

```yaml
miner-distributor:
  script: agents.miner_distributor
  wait_time: auto
  transaction_frequency: 30

simulation-monitor:
  script: agents.simulation_monitor
  poll_interval: 300
```

## Complete Example

```yaml
general:
  stop_time: 8h
  simulation_seed: 12345
  bootstrap_end_time: auto
  enable_dns_server: true
  shadow_log_level: warning
  progress: true
  runahead: 100ms
  process_threads: 2
  daemon_defaults:
    log-level: 1
    log-file: /dev/stdout
    db-sync-mode: fastest
    no-zmq: true
    non-interactive: true
    disable-rpc-ban: true
    allow-local-ip: true
  wallet_defaults:
    log-level: 1
    log-file: /dev/stdout

network:
  path: gml_processing/1200_nodes_caida_with_loops.gml
  peer_mode: Dynamic

agents:
  miner-{001..005}:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    start_time: 0s
    start_time_stagger: 1s
    hashrate: [25, 25, 30, 10, 10]
    can_receive_distributions: true

  user-{001..050}:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.regular_user
    start_time: 1200s
    start_time_stagger: auto
    transaction_interval: 60
    activity_start_time: auto
    can_receive_distributions: true

  relay-{001..010}:
    daemon: monerod
    start_time: 0s
    start_time_stagger: 5s

  miner-distributor:
    script: agents.miner_distributor
    wait_time: auto
    transaction_frequency: 30

  simulation-monitor:
    script: agents.simulation_monitor
    poll_interval: 300
```

Expand with:

```bash
python3 scripts/generate_config.py --from scenario.yaml -o expanded.yaml
```

## Constants Reference

| Constant | Value | Description |
|----------|-------|-------------|
| Min bootstrap end | 4h (14400s) | Minimum bootstrap period |
| Bootstrap buffer | 20% | Buffer above last bootstrap spawn |
| Funding period | 1h (3600s) | Time between md_start and activity_start |
| Auto threshold | 50 agents | Use batched stagger above this count |
| Batch initial delay | 20m (1200s) | When first batch spawns |
| Batch interval | 20m (1200s) | Time between batch starts |
| Initial batch size | 5 | First batch agent count |
| Batch growth factor | 2.0x | Exponential growth per batch |
| Max batch size | 200 | Cap per batch |
| Intra-batch stagger | 5s | Between agents within a batch |
| Upgrade stagger | 30s | Default daemon_0_stop stagger |
| Daemon restart gap | 30s | Min gap between daemon phases |
| Activity batch size | 10 | Users per activity batch |
| Activity batch interval | 5m (300s) | Between activity batches |
| Activity batch jitter | 0.30 | +/- 30% randomization |
