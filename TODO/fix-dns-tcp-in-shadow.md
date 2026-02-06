# TODO: Fix DNS TCP Passthrough in Shadow

## Goal

Make the internal DNS server actually work so monerod's libunbound can resolve seed node addresses via DNS, instead of relying on `--seed-node` command-line workarounds.

## Current State

DNS has never worked in any simulation run. The Python DNS server starts correctly on TCP port 53 but receives zero queries. Monerod's libunbound gets 0 results for all seed domain lookups and falls back to hardcoded `--seed-node` flags.

The simulation works despite this because the orchestrator adds `--seed-node=<miner_ip>` flags to every user monerod. But this is a workaround, not real DNS-based peer discovery.

### Symptoms

- DNS server log (`dnsserver/bash.1002.stdout`): only 3 lines — startup message, zero queries logged
- Monerod log: `dns_threads[N] addr_str: seeds.moneroseeds.se  number of results: 0` for all 4 seed domains
- ~15 second delay at every monerod startup (libunbound timeout)
- ~26K "Failed to connect to any of seed peers" messages per miner from repeated DNS retry attempts

### Why It Fails

Monerod uses **libunbound** for DNS resolution. Libunbound creates raw TCP sockets and sends DNS wire-format queries directly — it does NOT use libc's `getaddrinfo()`. Our Shadow patch (`092cd52d7 Add DNS query passthrough for getaddrinfo()`) only intercepts `getaddrinfo()` calls and sends UDP queries, so it doesn't help.

The TCP connection from libunbound to 3.0.0.10:53 apparently never reaches the Python DNS server's `accept()` call. The Python DNS server (using `dnslib.server.DNSServer` with `tcp=True`) runs in a daemon thread via `start_thread()`. Shadow's TCP simulation either fails to route the connection or fails to wake up the DNS server's blocking `accept()`.

## Architecture

```
monerod (libunbound)                    Python DNS server (dnslib)
─────────────────────                   ──────────────────────────
socket(AF_INET, SOCK_STREAM)            socket(AF_INET, SOCK_STREAM)
connect(3.0.0.10:53)                    bind(3.0.0.10:53) + listen()
   │                                       │
   │  Shadow TCP simulation                │  socketserver.TCPServer
   │  ─── connection never arrives ───>    │  select() + accept() in thread
   │                                       │
send(DNS query wire format)             recv() → resolve() → send(response)
recv(DNS response)                      (never happens)
```

## Investigation Plan

### Phase 1: Confirm where the connection drops

1. **Add Shadow-level TCP debug logging** for connections to port 53 specifically. In Shadow's TCP implementation (`src/main/host/`), add trace-level logging when:
   - A TCP SYN is generated targeting port 53
   - A TCP SYN arrives at a host on port 53
   - A listening socket on port 53 accepts/rejects a connection

2. **Check if the DNS server's `listen()` socket is registered** in Shadow's socket tracking. When the Python DNS server calls `bind()` + `listen()` on port 53, Shadow should register this as a listening socket. Verify this registration actually happens.

3. **Test with a minimal reproducer**: Create a tiny Shadow config with just 2 hosts — one running a Python TCP server on port 53, another running a Python TCP client that connects to it. This isolates whether the issue is with Shadow's TCP routing in general or specific to libunbound/dnslib interaction.

### Phase 2: Identify the root cause

Likely candidates (investigate in order):

1. **`select()`/`poll()` not waking up**: The dnslib TCP server uses Python's `socketserver.TCPServer` which calls `select()` in its serve loop. Shadow intercepts `select()` via the shim. If the select doesn't get notified about the incoming TCP connection, the `accept()` never fires. Check Shadow's `select()` implementation for listening sockets.

2. **Thread scheduling issue**: The DNS server's TCP handler runs in a daemon thread started by `dnslib.server.DNSServer.start_thread()`. The main thread does `time.sleep(1)` in a loop. In Shadow, if the daemon thread's `select()`/`accept()` isn't properly scheduled or if it's starved by the main thread's sleep, connections would queue up and never be processed.

3. **Network routing**: The DNS server is on `network_node_id: 0` with IP `3.0.0.10`. Other hosts are on different network nodes. Verify that Shadow's GML-based routing can actually deliver TCP SYNs from arbitrary network nodes to node 0.

4. **Port 53 special handling**: Shadow might have special behavior for port 53 (DNS port) that interferes with normal TCP connection handling — e.g., trying to intercept it as a DNS query at the shim level rather than forwarding as a regular TCP connection.

### Phase 3: Fix

Depending on root cause:

- **If `select()` notification issue**: Fix Shadow's `select()` to properly notify about incoming connections on listening TCP sockets.
- **If thread scheduling**: May need to restructure the DNS server to not use threads (single-threaded async), or fix Shadow's thread scheduling for blocked I/O.
- **If routing**: Fix the GML routing table generation to include routes to node 0.
- **If port 53 interception**: Add a bypass so that when `network.dns_server` is configured, raw TCP connections to that IP:53 are treated as normal TCP, not intercepted.

## Relevant Files

### Shadow (shadowformonero repo)
- `src/main/host/host.rs` — Host-level socket management
- `src/main/core/configuration.rs` — `dns_server` network option (line with `dns_server`)
- `src/lib/shim/shim_api_addrinfo.c` — `getaddrinfo()` passthrough (our patch, doesn't help here)
- `src/lib/shadow-shim-helper-rs/src/shim_shmem.rs` — Shared memory DNS server config
- `src/main/host/network/` — TCP connection routing
- `src/main/core/worker.rs` — Thread/event scheduling

### Monerosim
- `agents/dns_server.py` — Python DNS server implementation
- `src/orchestrator.rs` — Sets `DNS_PUBLIC` env var and `--seed-node` fallback flags

### Monero
- `src/common/dns_utils.cpp` — libunbound DNS resolver (`get_ipv4()`, `ub_resolve()`, TCP config)
- `src/p2p/net_node.inl` — `get_dns_seed_nodes()` function (lines 763-883)
- `src/cryptonote_config.h` — `CRYPTONOTE_DNS_TIMEOUT_MS` = 20000

## Quick Workaround (Already In Place)

The orchestrator adds `--seed-node=<ip>:18080` for all miner IPs to every user monerod. This is functionally equivalent to DNS working. Could also set `MONERO_DISABLE_DNS=1` to skip the 15-second timeout and log spam.
