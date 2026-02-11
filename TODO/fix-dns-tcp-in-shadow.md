# DNS Peer Discovery Fix for Shadow Simulations

## Status: FIXED

DNS peer discovery now works. All miners resolve seed domains via DNS and discover each other within 1-10 simulated seconds.

## Problem

DNS peer discovery never worked in Shadow simulations. Monerod uses libunbound for DNS resolution. Libunbound creates TCP sockets inside Shadow but never calls `connect()` — the socket creation succeeds but networking never initiates. This caused:

- DNS server received 0 queries
- `number of results: 0` for all seed domain lookups
- ~15 second timeout delay per miner startup
- ~26K "Failed to connect" log messages per miner

The orchestrator worked around this by injecting `--seed-node` flags.

## Root Cause

Libunbound 1.22.0 creates `AF_INET/SOCK_STREAM/IPPROTO_TCP` sockets inside Shadow but never calls `connect()`. The exact internal reason is unclear — likely related to how libunbound's internal event loop interacts with Shadow's syscall interception. Since we can't modify monero-shadow (the Monero fork), fixing libunbound's behavior directly isn't an option.

## Solution: LD_PRELOAD Interposition of libunbound API

Instead of fixing libunbound's broken networking inside Shadow, we intercept the entire libunbound C API via LD_PRELOAD. The interposer implements `ub_resolve()` by constructing raw DNS wire-format queries and sending them over UDP through Shadow's simulated network.

### Changes

**shadowformonero** (Shadow fork):

| File | Change |
|------|--------|
| `src/lib/preload-libc/unbound_interpose.c` | NEW — Full libunbound API interposition (~500 lines). Implements `ub_ctx_create`, `ub_ctx_set_fwd`, `ub_resolve`, `ub_resolve_free`, and all other `ub_*` functions. Core DNS query sends raw UDP packets to the configured forwarder. |
| `src/lib/preload-libc/CMakeLists.txt` | Added `unbound_interpose.c` to build |
| `src/lib/shim/shim_api_addrinfo.c` | Changed `getaddrinfo()` DNS passthrough from UDP to TCP (with RFC 1035 framing) |

**monerosim** (orchestrator):

| File | Change |
|------|--------|
| `agents/dns_server.py` | Added UDP listener alongside TCP (dual-protocol) |

### How It Works

```
monerod calls ub_resolve("seeds.moneroseeds.se", A, IN)
  -> LD_PRELOAD intercepts -> unbound_interpose.c::ub_resolve()
  -> Constructs DNS wire-format query (RFC 1035)
  -> Creates UDP socket, sends to forwarder (3.0.0.10:53)
  -> Shadow routes UDP packet through simulated network
  -> DNS server receives query, responds with miner IPs
  -> unbound_interpose.c parses response, returns ub_result with IP strings
  -> monerod connects to discovered peers
```

The forwarder address comes from the `DNS_PUBLIC=tcp://3.0.0.10` env var set by the orchestrator, which monero passes to `ub_ctx_set_fwd()`.

### Verification Results

- All miners resolve 4 seed domains, each returning 5 A records (one per miner)
- DNS resolution completes in ~100ms simulated time (was 15+ seconds timeout)
- P2P connections established via DNS-discovered peers (192+ connections in 5-minute test)
- "Not enough DNS seed nodes found" message is expected (< 12 nodes in test, threshold is `MIN_WANTED_SEED_NODES = 12`)
- TXT queries for `updates.moneropulse.*` return NXDOMAIN (expected — version-check domains, not peer discovery)

## Architecture

```
DNS query path (via interposer):
  monerod -> ub_resolve() -> [LD_PRELOAD] -> unbound_interpose.c
    -> UDP socket -> Shadow network -> dns_server.py (UDP:53) -> response

getaddrinfo path (existing, now TCP):
  app -> getaddrinfo() -> [LD_PRELOAD] -> shim_api_addrinfo.c
    -> TCP socket -> Shadow network -> dns_server.py (TCP:53) -> response
```

## Relevant Files

### Shadow (shadowformonero)
- `src/lib/preload-libc/unbound_interpose.c` — libunbound API interposer (THE FIX)
- `src/lib/preload-libc/CMakeLists.txt` — Build config
- `src/lib/shim/shim_api_addrinfo.c` — getaddrinfo() DNS passthrough (TCP)

### Monerosim
- `agents/dns_server.py` — Python DNS server (TCP + UDP)
- `src/orchestrator.rs` — Sets `DNS_PUBLIC` env var

### Monero (read-only reference)
- `src/common/dns_utils.cpp` — libunbound DNS resolver configuration
- `src/p2p/net_node.inl` — DNS seed discovery (`get_dns_seed_nodes()`, lines 763-883)
