# Node Reachability: Synthetic Firewall vs. Hidden (breaking change)

**Date:** 2026-07-22
**Requires:** shadowformonero **v0.2.4** (adds the `blocked_inbound_ports`
host option).

## TL;DR

Node un-reachability is now modelled two independent ways, and the vocabulary
changed:

- **firewalled** (a.k.a. *unreachable*) — the Shadow **host physically drops
  new inbound TCP connections** to the node's P2P port, like a NAT/firewall
  with no port forwarding. Driven by `reachable_fraction`.
- **hidden** — the monerod **`--hide-my-port` daemon flag**: the node stops
  advertising its port but still `listen()`s and *would* accept an inbound
  connection if dialed. Driven by the new `hidden_fraction`.

**Breaking:** `reachable_fraction < 1.0` used to emit `--hide-my-port`; it now
emits the **firewall**. This changes the behaviour (and results) of any config
that lowered `reachable_fraction`.

## Why

`--hide-my-port` is *cooperative*: monerod still listens and accepts, it just
isn't advertised, so peers don't normally learn to dial it. But a peer that
already has the address (an anchor connection, a peerlist persisted across a
restart, a seed handing it out) can still connect — so an "unreachable" node
could accumulate inbound connections a real NAT node never would. That leaks
into exactly the metrics the topology study cares about (the inbound-connection
count and the long-lived-connection tail).

The **firewall** makes unreachability physically true: an inbound SYN to a
blocked port is dropped, the dialer times out (a firewall DROP, not an RST),
and the node accepts *zero* inbound — while its own **outbound** connections
(and their ACK-carrying return traffic) are untouched. That's real
NAT-without-port-forwarding.

## Configuration

```yaml
general:
  reachable_fraction: 0.15    # fraction of non-seed/miner nodes that are
                              # reachable; the rest are FIREWALLED (their P2P
                              # port is blocked). Default 1.0 (all reachable).
  reachable_by_role: {...}    # optional per-role override (user, relay)
  hidden_fraction: 0.0        # fraction that ALSO runs --hide-my-port.
                              # Default 0.0 (nobody hidden).
```

The `--reachable <f>` CLI flag still overrides `reachable_fraction` (and now
controls the firewall). There is no CLI flag for `hidden_fraction` yet — set it
in the config.

### How the two sets relate

Both sets are chosen from the **same seeded hash ordering** of the non-seed,
non-miner agents, so they *nest*: when `hidden_fraction ≤ 1 − reachable_fraction`,
every hidden node is also firewalled — matching reality, where a node hides
*because* it is unreachable. You never get the nonsensical "hidden but
reachable" node.

- **Realistic NAT** (recommended): `reachable_fraction: 0.15` — 85% physically
  can't receive inbound. Optionally add `hidden_fraction` so those nodes also
  stop advertising (a well-behaved NAT daemon).
- **Old behaviour** (`--hide-my-port` only, no firewall):
  `reachable_fraction: 1.0` + `hidden_fraction: 0.85`. The capability is not
  removed, just spelled differently.

Seeds and miners are always reachable (never firewalled, never hidden) — they
are the bootstrap backbone.

**Nuance / limitation:** `hidden_fraction` is a single global fraction (no
`hidden_by_role` yet). If you combine `reachable_by_role` with a global
`hidden_fraction`, the per-role nesting guarantee weakens (the firewall is
per-role but hidden is global); the global-fraction case nests exactly.

## How it works (shadowformonero v0.2.4)

The generator sets a Shadow **host** option on each firewalled node:

```yaml
hosts:
  user-042:
    blocked_inbound_ports: [18080]   # the monerod P2P port
```

Shadow's internet-facing interface drops any inbound TCP **SYN-without-ACK**
whose destination port is in that set (`NetworkInterface::push`, gated by a new
`Packet::tcp_syn_dst_port()` that handles both TCP stacks). Filtering on
SYN-without-ACK is deliberate: monerod may dial *out from* its P2P port
(`SO_REUSEADDR`), so return traffic can arrive at 18080 with ACK set — that
passes; only genuinely-new inbound is dropped. The firewall is applied to the
`eth0` interface only; the `lo` (loopback) interface gets an empty set, so a
node's own tooling (its agent script → its daemon RPC, all intra-host) is never
affected regardless of which port is blocked.

Iptables/netfilter are **not** emulated by Shadow, which is why this is a
host-config primitive in the fork rather than a guest-side firewall rule.

## Impact on existing docs / study

The published topology study (`docs/20260620_network_topology_study.md`) and its
targets (`docs/20260618_mainnet_topology_targets.md`) were produced with the
`--hide-my-port` mechanism. Those results stand as-is for that mechanism. The
firewall is strictly more faithful (zero inbound vs. hide-my-port's leaky
near-zero), so **re-running the sweeps with the firewall is a natural follow-up**
for even higher fidelity — expect the unreachable nodes' inbound-connection
counts and long-lived-connection tail to drop further toward mainnet.

## Verification

- Fork primitive proven with a 2-host Shadow test (harness:
  `~/basement_monerosim/20260722_inbound_firewall/`): inbound to a firewalled
  port times out (8 s) and never accepts, while the firewalled host's own
  outbound dial connects and is accepted; without the firewall both directions
  connect.
- Generator: `reachable_fraction 0.5` + `hidden_fraction 0.25` on quickstart →
  the firewalled hosts carry `blocked_inbound_ports: [18080]`, the hidden host
  carries `--hide-my-port`, hidden ⊆ firewalled, seeds/miners have neither.
- Defaults unchanged: `reachable_fraction 1.0` / `hidden_fraction 0.0` emits
  nothing new — cargo goldens byte-identical, quickstart smoke 19/19 PASS.
- End-to-end quickstart at `--reachable 0.5` + `hidden_fraction 0.25`: 15
  nodes, 100% sync, height 128 (127 mined), 228 txs / 132 in blocks, 0 alerts,
  ALL CHECKS PASSED — the firewalled nodes participate fully via outbound
  connections, confirming the deployed v0.2.4 host option is honored end to end.
