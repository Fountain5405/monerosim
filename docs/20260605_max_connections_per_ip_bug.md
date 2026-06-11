# `max-connections-per-ip=1` breaks small, dense simulations

**Date:** 2026-06-05 — **revised 2026-06-11** after full verification
(earlier revisions of this doc overstated the bug's scope; see "What this bug
is NOT" below and `docs/20260610_rucknium_review_response_v2.md` §6–§7).
**Status:** Fixed (orchestrator floor, commit `d21f971b`)
**Severity:** High at small/dense scale (full-mesh scenarios unusable);
**no measurable effect at 1000-node scale** (verified pre/post).

## TL;DR

monerod's stock `--max-connections-per-ip` default is **1** — a mainnet
anti-spam measure that assumes one IP rarely needs two simultaneous inbound
connections. In a small **full-mesh** simulation every pair of nodes holds
connections in both directions *and* dials reachability back-pings, so a
second simultaneous incoming connection from the same IP is routine — and
gets refused. At 15 nodes this produced **31,180 refusals across one run**
(7,867 on a single node) and no stable mesh. The orchestrator now floors the
value at **4** for every daemon agent (`src/agent/user_agents.rs`,
`.entry().or_insert(4)` — user overrides still win). At 1000 sparse nodes the
default was nearly harmless and the fix changes nothing measurable; that
verification matters because earlier versions of this doc claimed otherwise.

## Verified mechanics (monerod source)

1. **The default is 1** — `src/p2p/net_node.cpp` (`arg_max_connections_per_ip`,
   default `1`).
2. **The cap counts simultaneous INCOMING connections per remote IP, at
   accept time** — `is_host_limit()` → `has_too_many_connections()`
   (`net_node.inl`, counts only `cntxt.m_is_income &&
   is_same_host(address)`), refusing with
   `"CONNECTION FROM <ip> REFUSED, too many connections from the same
   address"` (`net_node.inl:239`).
3. **`try_ping` opens an extra connection toward the dialing peer.** When a
   node receives a handshake from a peer advertising a real `my_port`, it
   verifies reachability by dialing the peer back on a **new** TCP
   connection (`COMMAND_PING`, levin command 1003). That ping arrives at the
   original dialer as an *incoming* connection. (`handle_handshake` →
   `try_ping`; white-list insertion is gated on the ping succeeding.)

### The collision, caught in the act (quickstart-15 log)

```
00:40:05.249  [3.0.0.11:56022 ... INC] NEW CONNECTION            ← peer's data conn to us
00:40:05.249  [3.0.0.11:56022 INC] 262 bytes ... command-1001    ← handshake
00:40:05.449  CONNECTION FROM 3.0.0.11 REFUSED, too many connections from the same address
00:40:05.449  [3.0.0.11:18080 ... OUT] NEW CONNECTION            ← our back-ping to them
00:40:05.449  [3.0.0.11:18080 OUT] 10 bytes ... command-1003     ← PING
```

One incoming from `3.0.0.11` is already open when a second incoming from the
same IP arrives 200 ms later — refused at cap 1. In a full mesh, where every
pair holds mutual data connections *and* exchanges back-pings, this happens
constantly: the refusal rate on the receiving node was a steady ~246 per
10 minutes for the entire run, and it never converged.

What is **measured** at 15 nodes: 31,180 refusals run-wide, 16,978 failed
back-pings on one miner, 33,993 connection attempts (vs 7,352 post-fix),
~0 stable connections per node, erratic block production. What is **not**
step-by-step traced: the exact path from "ping refused" to "original
connection torn down" — the outcome (no stable mesh) is measured; the
per-step teardown sequence remains a working model.

## Evidence (quickstart-15, before vs after)

| Metric | cap = 1 | cap = 4 |
|---|---|---|
| `REFUSED, too many connections` (user-01) | 7,867 | **0** |
| `REFUSED` run-wide (15 daemons) | 31,180 | **0** |
| Failed back-ping `COMMAND_PING` (miner-004) | 16,978 | **0** |
| Total connection attempts (miner-004) | 33,993 | 7,352 |
| Stable persistent connections / node | ~0 | **14–19** |
| Longest-held connection | < 1 s | **3.63 h (whole run)** |
| Block production | erratic | 2.4–3.2 min/block (target 2) |

(The 3.63 h figure is a quickstart-scale result: with only 14 possible peers
there is no rotation pressure, so connections persist for the whole run —
the same peerlist-exhaustion effect seen in the 35-node review sim.)

## What this bug is NOT (verified 2026-06-09/10)

Earlier revisions of this doc claimed the default cap "degraded P2P
stability at every scale" and put "every daemon into a permanent reconnect
loop", and implied it explained the connection-duration figures in
Rucknium's review. **All of that is retracted**, on direct evidence:

- **At 1000 nodes the fix changes nothing measurable.** Same binary, same
  config, cap=1 vs cap=4: tx-carrying connection median lifetime 100.3 s in
  both; handshake success 9.6 % vs 10.0 %; `before_handshake` closes 65.3 %
  vs 65.8 %; sub-second probe churn identical. The cap was hit only rarely
  per node in sparse topologies (peer pairs seldom hold mutual inbound
  connections simultaneously, so the collision above is rare).
- **The sub-second TCP medians at large scale are not this bug.** That is
  normal monerod peer-discovery probing, present identically post-fix.
- **The 1.5-minute connection duration Rucknium measured is not this bug.**
  It is monerod's own sync-search peer rotation (`update_sync_search`,
  101 s timer) interacting with a perfect network — fully explained, with
  his metric validated, in `docs/20260610_rucknium_review_response_v2.md`
  §3. Pre-fix large-scale results remain valid; the original 1000-node run
  completed and its statistics reproduce on the fixed stack (ibid. §4.4).

## Why mainnet's default of 1 is safe there

- **Most mainnet nodes are unreachable** (NAT/firewalled/`--hide-my-port`)
  and advertise `my_port = 0`; `try_ping` early-returns on `my_port == 0`,
  so the back-ping never fires for them (verified in source — this gate is
  also why such nodes never enter peerlists).
- For reachable pairs, mainnet peer selection across thousands of candidates
  makes *mutual* simultaneous inbound pairs rare, so a back-ping is usually
  the **first** incoming connection from that IP — allowed even at cap 1.
  (Reasoned from the verified counting semantics; not directly measured on
  mainnet.)
- NAT does **not** dodge the cap by splitting source IPs (the count is on
  the incoming source address); NAT's only relevance is making nodes
  unreachable (point 1).

The simulator's clean environment — every node reachable on a unique IP with
a real advertised port, bootstrapping simultaneously, and (in small
scenarios) fully meshed — removes every condition that protects mainnet, so
the latent `try_ping` × cap-1 interaction fires pervasively there and only
there.

## The fix

```rust
// src/agent/user_agents.rs (daemon option assembly)
merged_daemon_options
    .entry("max-connections-per-ip".to_string())
    .or_insert(OptionValue::Number(4));
```

- Covers every daemon agent (miners, users, relays, seeds).
- A **floor, not a force**: `merge_options()` has already applied
  `daemon_defaults` and per-agent options, so the entry only fills in when
  the user set nothing. Setting `max-connections-per-ip: 8` in a config
  yields `=8` everywhere, `=4` nowhere; setting `1` yields `=1` everywhere —
  i.e., **stock monerod behavior is one YAML line away** (both directions
  verified through config generation). The quickstart example configs carry
  the key commented out with this guidance, and `daemon_defaults` is
  documented in `docs/CONFIGURATION.md`. For fidelity-sensitive large-scale
  studies, running at `1` is reasonable: at 1000 nodes the cap value makes
  no measurable difference either way.
- Why 4: verification briefly needs 2 simultaneous inbound from one IP
  (data + back-ping); 4 adds headroom for cleanup races during rapid
  reconnects while staying far below anything that matters in a sim where
  IPs are unique per node.

## Validation

1. Quickstart-15 with the fix: zero refusals, zero failed back-pings,
   stable 14–19-connection mesh for the whole run, block production near
   target (table above).
2. 1000-node, standard-mainnet load (`20260608_164109_1k_mainnet`, cap=4):
   completed, all checks passed.
3. 1000-node at the original review configuration (cap=4,
   `20260609_153322_captest_cap4` and `20260610_031558_clumping_0p67_monitor`):
   completed cleanly, all checks passed, and reproduced the original run's
   propagation statistics with Rucknium's own analysis code — confirming
   both that the fix is safe at scale and that it changes nothing there.

## References

- Rucknium's review: [issue #3]
- Fix commit: `d21f971b` (`src/agent/user_agents.rs`, `src/orchestrator.rs`)
- monerod source: `net_node.cpp` (`arg_max_connections_per_ip`, default 1);
  `net_node.inl:239` (refusal); `has_too_many_connections` (incoming-only
  count); `try_ping` / `handle_handshake` (back-ping, `my_port==0` gate)
- Full mechanism investigation:
  `docs/20260610_rucknium_review_response_v2.md` and
  `analysis/results_clumping_0p67/discrepancy_investigation.md`

[issue #3]: https://github.com/Fountain5405/monerosim/issues/3
