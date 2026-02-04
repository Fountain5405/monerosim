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

### Step 2: Monerosim generates Shadow YAML

The Rust orchestrator (`src/orchestrator.rs`) transforms this into a Shadow host with five processes:

```yaml
hosts:
  miner-001:
    network_node_id: 0
    ip_addr: "10.0.0.10"
    processes:
      # 1. monerod daemon (via bash exec wrapper)
      - path: "/bin/bash"
        args: "-c 'rm -rf /tmp/monero-miner-001 && exec monerod --data-dir=/tmp/monero-miner-001 --regtest ...'"
        start_time: "0s"

      # 2. Wallet directory cleanup
      - path: "/bin/bash"
        args: "-c 'rm -rf /tmp/monerosim_shared/miner-001_wallet && mkdir -p ...'"
        start_time: "46s"

      # 3. monero-wallet-rpc
      - path: "/bin/bash"
        args: "-c 'monero-wallet-rpc --daemon-address=http://10.0.0.10:18081 ...'"
        start_time: "48s"

      # 4. Create agent wrapper script
      - path: "/bin/bash"
        args: "-c 'cat > /tmp/agent_miner-001_wrapper.sh << EOF\n#!/bin/bash\n...EOF'"
        start_time: "64s"

      # 5. Execute agent wrapper script
      - path: "/bin/bash"
        args: "/tmp/agent_miner-001_wrapper.sh"
        start_time: "65s"
```

### Step 3: shadowformonero runs it

Shadow creates a virtual network, assigns each host its IP, and launches processes according to their start times. From monerod's perspective, it's running on a real machine with a real network.

## Why Everything Goes Through Bash

Every process in the generated Shadow YAML uses `/bin/bash` as the executable. This is not optional -- it's required for three reasons.

### Reason 1: Pre-launch cleanup with exec

```bash
rm -rf /tmp/monero-miner-001 && exec monerod --data-dir=/tmp/monero-miner-001 ...
```

The `rm -rf` clears stale data from previous runs. The `exec` replaces the bash process with monerod, so monerod becomes the actual process that Shadow tracks. Without `exec`, Shadow would send SIGTERM to bash at simulation end, and bash might not forward it to monerod, leaving orphaned processes.

### Reason 2: Python agents need a wrapper script

Shadow's process model is `path + args`, which works for simple binaries but not for Python modules that need environment setup. The agent launch is split into two Shadow processes:

1. **Process 4** (creation): Writes a wrapper script to `/tmp/agent_[id]_wrapper.sh` using a bash heredoc. This script sets up `PYTHONPATH`, `PATH`, and includes a retry loop that waits for wallet-rpc to be ready.
2. **Process 5** (execution): Runs the wrapper script 1 second later.

The 1-second gap ensures the file is fully written before execution. The wrapper script contains:

```bash
#!/bin/bash
cd /home/user/monerosim
export PYTHONPATH="${PYTHONPATH}:/home/user/monerosim"
export PATH="${PATH}:$HOME/.monerosim/bin"

# Wait for wallet RPC to be ready
for i in {1..30}; do
    if curl -s --max-time 1 http://10.0.0.10:18082 >/dev/null 2>&1; then
        python3 -m agents.autonomous_miner --id miner-001 \
            --rpc-host 10.0.0.10 --agent-rpc-port 18081 \
            --wallet-rpc-port 18082 --shared-dir /tmp/monerosim_shared \
            --attributes is_miner true --attributes hashrate 50
        exit $?
    fi
    sleep 3
done
# Fallback: start anyway after 90 seconds
python3 -m agents.autonomous_miner ...
```

The retry loop is necessary because wallet-rpc takes time to initialize and connect to its daemon. Without it, the Python agent would fail immediately on its first RPC call.

### Reason 3: Wallet directory cleanup

Monero wallet-rpc creates directories with restrictive permissions (`d---------`). A separate bash process runs 2 seconds before wallet-rpc to `rm -rf` and recreate the wallet directory with proper permissions. This prevents failures when re-running simulations.

## The Startup Sequence

Each agent host runs a carefully timed sequence:

| Time offset | Process | Purpose |
|-------------|---------|---------|
| +0s | monerod | Start the daemon, begin P2P connections |
| +46s | bash cleanup | Clean wallet directory |
| +48s | wallet-rpc | Connect to local daemon |
| +64s | bash create | Write agent wrapper script |
| +65s | bash execute | Run agent (with wallet-rpc retry loop) |

The 48-second gap between daemon and wallet gives monerod time to initialize its RPC server. The agent starts at +65s but the retry loop adds up to 90 more seconds of tolerance.

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
| `[agent]_wallet/` | wallet-rpc (runtime) | wallet-rpc | Wallet data directories |

The registries are written **before the simulation starts** by the Rust orchestrator. Python agents read them at runtime to discover peers. The `AgentDiscovery` class caches registry reads with a 5-second TTL to avoid excessive filesystem I/O.

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
   - Generate agent wrapper script (retry loop, environment, module arguments)
   - Create the ShadowHost with all 5 processes
6. **Generate registries** (agent, miner, public node) as JSON to `/tmp/monerosim_shared/`
7. **Serialize** the complete ShadowConfig to `shadow_output/shadow_agents.yaml`
8. **Clean up** previous output directory and shared state

Offset management prevents IP collisions between different agent categories:
```
User agents:         index 0, 1, 2, ...
Miner distributor:   offset = total_agents + 100
Pure script agents:  offset = total_agents + 200
Simulation monitor:  offset = total_agents + 250
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

When the simulation reaches `stop_time`, Shadow sends SIGTERM to all processes. Because of the `exec` pattern, SIGTERM goes directly to monerod/wallet-rpc/Python (not to a wrapping bash process).

Python agents register `SIGTERM` handlers in `base_agent.py` for graceful shutdown (flushing stats, closing RPC connections). Monerod handles SIGTERM natively.

Shadow logs a message like "N managed processes in unexpected final state" -- this is normal. It means processes were still running when the time limit hit, which is expected behavior for long-running daemons.
