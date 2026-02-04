# How Monerosim Works

This document explains the detailed mechanics of how Monerosim generates Shadow configurations and runs Monero network simulations, including the reasoning behind design decisions.

## The Problem

Running real Monero nodes in a controlled environment is hard. Monero's networking uses raw sockets, DNS-based peer discovery, and expects a real network stack. The [Shadow](https://shadow.github.io/) network simulator can run real binaries in a virtual network, but it has constraints:

- Each process runs on a virtual "host" with its own IP
- Processes are defined in a YAML config with explicit start times
- The filesystem under `/tmp` is shared across all hosts
- Shadow sends SIGTERM/SIGKILL to terminate processes at simulation end
- Shadow's standard build doesn't handle all of Monero's socket operations

[shadowformonero](https://github.com/Fountain5405/shadowformonero) is a Shadow fork that adds the socket compatibility patches needed to run unmodified Monero binaries. Monerosim's job is to bridge the gap between a simple user-written YAML config and the detailed Shadow YAML that shadowformonero needs.

## End-to-End Flow

### Step 1: User writes a config

```yaml
agents:
  miner-001:
    daemon: monerod
    wallet: "monero-wallet-rpc"
    script: agents.autonomous_miner
    hashrate: 50
```

### Step 2: Monerosim generates Shadow YAML and pre-written scripts

The Rust orchestrator (`src/orchestrator.rs`) transforms this into a Shadow host with three processes:

```yaml
hosts:
  miner-001:
    network_node_id: 0
    ip_addr: "10.0.0.10"
    processes:
      # 1. monerod daemon (via bash exec wrapper)
      - path: "/bin/bash"
        args: "-c 'exec /home/user/.monerosim/bin/monerod --data-dir=/tmp/monero-miner-001 --regtest ...'"
        start_time: "0s"

      # 2. monero-wallet-rpc
      - path: "/bin/bash"
        args: "-c '/home/user/.monerosim/bin/monero-wallet-rpc --daemon-address=http://10.0.0.10:18081 ...'"
        start_time: "2s"

      # 3. Execute pre-written agent wrapper script
      - path: "/bin/bash"
        args: "shadow_output/scripts/agent_miner-001_wrapper.sh"
        start_time: "5s"
```

Additionally, the orchestrator writes pre-generated wrapper scripts to `shadow_output/scripts/`:

```bash
#!/bin/bash
cd /home/user/monerosim
export PYTHONPATH=/home/user/monerosim
export PATH=/usr/local/bin:/usr/bin:/bin:/home/user/.monerosim/bin

python3 -m agents.autonomous_miner --id miner-001 \
    --rpc-host 10.0.0.10 --agent-rpc-port 18081 \
    --wallet-rpc-port 18082 --shared-dir /tmp/monerosim_shared \
    --attributes is_miner true --attributes hashrate 50 2>&1
```

All paths in the generated YAML and scripts are fully resolved at generation time -- no shell variable expansion (`$HOME`, `${PYTHONPATH}`, etc.) is needed at runtime.

### Step 3: shadowformonero runs it

Shadow creates a virtual network, assigns each host its IP, and launches processes according to their start times. From monerod's perspective, it's running on a real machine with a real network.

## Pre-Simulation Cleanup

Before generating the Shadow configuration, `main.rs` cleans up all state from previous runs:

1. **Output directory** (`shadow_output/`) -- removed and recreated
2. **Shared state** (`/tmp/monerosim_shared/`) -- removed and recreated
3. **Daemon data directories** (`/tmp/monero-*`) -- glob-matched and removed
4. **Wallet directories** -- recreated fresh with correct permissions (755) by the orchestrator

This centralized cleanup replaces the per-agent bash cleanup processes that previously ran inside the simulation. The benefit is fewer Shadow processes and simpler generated YAML.

## Why Bash Is Still Used

Bash usage has been minimized but not fully eliminated. Here's what remains and why.

### Daemon exec pattern

```bash
bash -c 'exec /home/user/.monerosim/bin/monerod --data-dir=/tmp/monero-miner-001 ...'
```

The `exec` replaces the bash process with monerod, ensuring SIGTERM from Shadow goes directly to monerod rather than to a parent bash process. Without `exec`, bash would receive SIGTERM and monerod would be orphaned.

If Shadow sends SIGTERM correctly to directly-launched binaries (without bash), this could be eliminated entirely. This hasn't been verified with shadowformonero yet.

### Wallet-rpc launch

```bash
bash -c '/home/user/.monerosim/bin/monero-wallet-rpc --daemon-address=...'
```

Wallet-rpc is launched through bash but without `exec`. This is a candidate for direct binary launch once the SIGTERM behavior is verified.

### Python agent wrapper scripts

Shadow's `ShadowProcess` has no `working_directory` field, so `cd` requires bash. The wrapper scripts set the working directory and environment before launching the Python agent. These scripts are pre-written at generation time (in `shadow_output/scripts/`) and executed as a single Shadow process.

Python agents handle their own RPC readiness retries via `wait_until_ready()` with exponential backoff in `base_agent.py`, so no bash retry loop is needed in the wrapper.

## The Startup Sequence

Each agent host runs a timed sequence:

| Time offset | Process | Purpose |
|-------------|---------|---------|
| +0s | monerod | Start the daemon, begin P2P connections |
| +2s | wallet-rpc | Connect to local daemon |
| +5s | agent script | Run pre-written Python agent wrapper |

The gap between daemon and wallet gives monerod time to initialize its RPC server. The Python agent includes its own retry logic (120-180 seconds with exponential backoff) to wait for wallet-rpc readiness.

### Staggered start times across agents

When multiple agents exist, their absolute start times are staggered:

**Miners**: Start at 0s, 1s, 2s, 3s... (one per second)

**Regular users**: Start at `7200s + index` (one per second after 7200s)

The 7200-second delay for users exists because of Monero's coinbase maturity rule: mining rewards cannot be spent until 60 blocks have been confirmed. At the default ~120 seconds per block, that's 60 * 120 = 7200 seconds. Users who try to transact before this will have no spendable funds in the network.

The 1-second stagger between agents prevents a thundering herd of simultaneous monerod startups, which would overwhelm Shadow's scheduler.

## Why Each Agent Gets Its Own IP

Each agent runs on a separate Shadow host with a unique IP address. All three services (monerod :18080/:18081, wallet-rpc :18082, Python agent) share that IP using fixed ports.

The alternative would be running all agents on one IP with different ports (e.g., monerod on :18080, :28080, :38080...). This doesn't work because:

1. **Monero's P2P protocol identifies peers by IP:port**. Multiple nodes on the same IP would confuse peer tracking and ban logic.
2. **`--rpc-bind-ip` must match the P2P bind IP** for Monero's internal cross-references to work.
3. **Realistic simulation requires distinct network identities**. In the real Monero network, each node has its own IP.

## IP Allocation

IPs are assigned through a priority chain:

1. **Subnet group** (if configured) -- All agents in the same `subnet_group` get IPs from the same /24, useful for simulating Sybil attacks from a single subnet.
2. **GML pre-allocation** -- If the GML topology node already has an IP attribute.
3. **AS-aware assignment** -- Maps the GML node's Autonomous System number to a region-appropriate IP range (ARIN ranges for North America, RIPE for Europe, etc.).
4. **Global registry** -- Round-robin across 6 geographic regions based on agent index.
5. **Fallback** -- 192.168.x.x ranges if everything else fails.

Geographic distribution cycles agents across continents:

| Agent index mod 6 | Region | IP range |
|--------------------|--------|----------|
| 0 | North America | 10.x.x.x |
| 1 | Europe | 172.16-31.x.x |
| 2 | Asia | 203.x.x.x |
| 3 | South America | 200.x.x.x |
| 4 | Africa | 197.x.x.x |
| 5 | Oceania | 202.x.x.x |

## Agent Communication via Shared Filesystem

Shadow isolates each host's network, but `/tmp` is shared across all hosts. Monerosim uses `/tmp/monerosim_shared/` as a coordination bus:

| File | Written by | Read by | Content |
|------|-----------|---------|---------|
| `agent_registry.json` | Rust orchestrator (pre-simulation) | All Python agents | Agent IDs, IPs, ports, capabilities, attributes |
| `miners.json` | Rust orchestrator (pre-simulation) | Autonomous miners, DNS server | Miner IDs, IPs, hashrate weights |
| `public_nodes.json` | Rust orchestrator (pre-simulation) | Wallet-only agents | Daemon nodes available for remote connection |
| `[agent]_wallet/` | Rust orchestrator (pre-simulation), wallet-rpc (runtime) | wallet-rpc | Wallet data directories |

The registries and wallet directories are created **before the simulation starts** by the Rust orchestrator. Python agents read registries at runtime to discover peers. The `AgentDiscovery` class caches registry reads with a 5-second TTL to avoid excessive filesystem I/O.

This design was chosen over network-based discovery because:
- No discovery protocol overhead during simulation startup
- Works immediately at t=0 (no bootstrap delay for a discovery service)
- Deterministic: same config always produces same registries
- Simple: JSON files are easy to debug and inspect

## Peer Connectivity

Monero nodes find each other through two mechanisms that Monerosim configures:

### 1. Monerod CLI arguments

The orchestrator generates `--add-priority-node` and `--seed-node` arguments per daemon:

- **Miners** connect to each other in a ring topology via `--add-priority-node`. This ensures the mining network is always connected regardless of peer discovery.
- **Regular nodes** use `--seed-node` to connect to miners (in Dynamic mode) or to explicitly listed nodes (in Hardcoded mode).

### 2. DNS-based peer discovery

If `enable_dns_server: true` is set, the orchestrator creates a DNS server agent that responds to Monero's built-in seed domain queries (`seeds.moneroseeds.se`, etc.) with miner IPs from `miners.json`. This lets monerod's native peer discovery work inside the simulation.

Without the DNS server, monerod would try to resolve these domains and fail, requiring `--disable-seed-nodes` on every daemon.

## Environment Variables

The orchestrator injects environment variables into every Shadow process for determinism and compatibility:

| Variable | Value | Why |
|----------|-------|-----|
| `PYTHONHASHSEED` | `0` | Makes Python's `hash()` deterministic across runs |
| `PYTHONUNBUFFERED` | `1` | Ensures log output appears immediately in Shadow logs |
| `SIMULATION_SEED` | from config | Global seed passed to all agents for reproducible behavior |
| `GLIBC_TUNABLES` | `glibc.malloc.arena_max=1` | Single malloc arena prevents non-deterministic memory layout |
| `MALLOC_ARENA_MAX` | `1` | Same as above (fallback for older glibc) |
| `MONERO_BLOCK_SYNC_SIZE` | `1` | Minimal sync batch size, reduces memory spikes |
| `MONERO_MAX_CONNECTIONS_PER_IP` | `20` | Allows more connections from same subnet |
| `DNS_PUBLIC` | `tcp://[dns_ip]` | Points monerod at the simulation's DNS server |
| `PROCESS_THREADS` | from config | Controls monerod thread count (1 for determinism) |

## The Orchestrator Pipeline

The full generation pipeline in `src/orchestrator.rs`:

1. **Parse and validate** the user config
2. **Load GML topology** if a path is specified
3. **Initialize IP systems** (global registry, AS subnet manager)
4. **Create DNS server host** (if enabled) on GML node 0
5. **Process each agent**:
   - Assign to a GML node (geographic distribution)
   - Allocate IP address
   - Generate daemon arguments (P2P connections, RPC binding, data directory)
   - Generate wallet arguments (daemon address, wallet directory)
   - Generate agent wrapper script content
   - Create the ShadowHost with 3 processes (daemon, wallet, agent)
6. **Generate registries** (agent, miner, public node) as JSON to `/tmp/monerosim_shared/`
7. **Pre-create wallet directories** with correct permissions (755)
8. **Write wrapper scripts** to `shadow_output/scripts/` and rewrite Shadow host processes to reference them
9. **Serialize** the complete ShadowConfig to `shadow_output/shadow_agents.yaml`

Offset management prevents IP collisions between different agent categories:
```
User agents:         index 0, 1, 2, ...
Miner distributor:   offset = total_agents + 100
Pure script agents:  offset = total_agents + 200
Simulation monitor:  offset = total_agents + 250
```

## Generated Output

```
shadow_output/
  shadow_agents.yaml      # Main Shadow configuration
  scripts/                # Pre-written wrapper scripts for all Python agents
    agent_miner-001_wrapper.sh
    mining_agent_miner-001_wrapper.sh
    agent_user-001_wrapper.sh
    dns_server_wrapper.sh
    miner-distributor_wrapper.sh
    simulation-monitor_wrapper.sh
    ...

/tmp/monerosim_shared/
  agent_registry.json     # Agent metadata for discovery
  miners.json             # Miner hashrate distribution
  public_nodes.json       # Public node registry
  miner-001_wallet/       # Pre-created wallet directories
  user-001_wallet/
  ...
```

## Monero-Specific Configuration

Every monerod instance runs with `--regtest --keep-fakechain`, which:
- Runs on a private test network (no connection to mainnet/testnet)
- Keeps the in-memory blockchain between restarts
- Uses minimal difficulty so blocks can be mined quickly

Other key daemon flags:
- `--db-sync-mode=fastest` -- Skip fsync for speed (data loss on crash is acceptable in simulation)
- `--no-zmq` -- Disable ZMQ pub/sub (not needed, saves resources)
- `--disable-rpc-ban` -- Prevent banning peers in the simulated network
- `--allow-local-ip` -- Allow connections to/from private IP ranges
- `--non-interactive` -- No interactive console

## What Happens at Simulation End

When the simulation reaches `stop_time`, Shadow sends SIGTERM to all processes. Because of the `exec` pattern, SIGTERM goes directly to monerod (not to a wrapping bash process). Wallet-rpc and Python agents receive SIGTERM directly from Shadow.

Python agents register `SIGTERM` handlers in `base_agent.py` for graceful shutdown (flushing stats, closing RPC connections). Monerod handles SIGTERM natively.

Shadow logs a message like "N managed processes in unexpected final state" -- this is normal. It means processes were still running when the time limit hit, which is expected behavior for long-running daemons.
