> Status: design record of 2026-07-25, kept as history; it may not match the current code. Current docs: docs/README.md.

# Cross-implementation P2P connection characteristics: monerod ↔ cuprate

**Date:** 2026-07-25
**Tool:** `analysis/conn_matrix.py`
**Data:** the 300-node A/B from `docs/20260724_cuprate_scale_experiment.md`
— `archived_runs/20260724_133050_cuprate_exp_cuprate` (157 monerod / 149 cuprate)
and `archived_runs/20260723_212123_cuprate_exp_baseline` (306 monerod)

## Headline

In a half-cuprate network, **cuprate nodes hold ~2.4× more concurrent peers than monerod
nodes** (61.5 vs 26.1). Once that degree difference is accounted for, **connections mix
essentially at random between implementations — there is no clustering by implementation.**
And monerod's own connectivity is **unchanged** by cuprate's presence (26.1 peers vs 25.2 in
the all-monerod baseline).

The degree gap is not a behavioural quirk: it is a **configuration default**. cuprate targets
32 outbound connections, monerod 12.

| | monerod | cuprate |
|---|---|---|
| default outbound target | **12** (`P2P_DEFAULT_CONNECTIONS_COUNT`, `monero/src/cryptonote_config.h:139`) | **32** (`cuprate/binaries/cuprated/src/config/p2p.rs:324`) |
| default max inbound | unlimited (`arg_in_peers` = -1 → `UINT32_MAX`, `net_node.cpp:162`) | 128 (`p2p.rs:326`) |
| observed concurrent peers | 26.1 | 61.5 |

Neither 300-node config overrides these, so the runs used stock defaults for both.
The observed 2.36× degree ratio tracks the 32/12 = 2.67× outbound-target ratio.

## Method

`analysis/conn_matrix.py` reconstructs the peer graph from daemon logs and classifies every
peer relationship by the implementation pair at its endpoints. Peer identity is the **IP** —
sound here because monerosim gives every host a distinct IP. Ports cannot serve as identity:
an outbound connection shows the peer's listen port (18080), an inbound one its ephemeral
source port.

Connection events are extracted per format:

| impl | pattern | direction |
|---|---|---|
| monerod | `[<ip>:<port> INC]` / `[<ip>:<port> OUT]` | explicit |
| cuprate | `inbound_server:handshaker{addr=<ip>:<port>}` | inbound |
| cuprate | `connect_to_<x>:handshaker{addr=<ip>:<port>}` | outbound |
| cuprate | `connection{addr=<ip>:<port>}` | unknown (active connection task) |

Extraction runs through `grep -oE` per file because these archives are ~14 GB; only the
deduplicated token set enters Python. Non-daemon IPs (DNS server, light wallets, monitor,
distributor) are counted and dropped.

## Why cumulative peer counts are the wrong metric

The first pass counted every peer each node *ever* connected to across the 8h run. That
saturates:

| node impl | distinct peers ever connected (of 305 possible) |
|---|---|
| cuprate | **305 — every other node, for every single cuprate node** |
| monerod | ~115–206 (`user-001` 120, `user-010` 115, `miner-001` 206) |

Every cuprate node completed handshakes with the entire rest of the network
(`relay-001`: 1201 `Handshake complete.` events across 305 distinct peers), while monerod
nodes only ever touched ~40% of it. Cuprate cycles through peers far more aggressively.

The consequence is that cumulative pair counts degenerate into complete graphs — the first
run produced monerod↔cuprate = 23393 = exactly 149×157 (complete bipartite) and
cuprate↔cuprate = 11026 = exactly C(149,2). **Any "assortativity" computed from those numbers
is an artifact of saturation, not evidence about topology.** They are not reported here.

The meaningful metric is **concurrent** connectivity: distinct peers a node exchanged P2P
traffic with inside a time window. All figures below use a 5-minute mid-run window
(sim-time 04:00–04:05, well after bootstrap), via `--window='^2000-01-01[ T]04:0[0-4]:'`.

## Concurrent connection matrix (5-minute window)

**Cuprate arm** (157 monerod / 149 cuprate) — 6671 distinct concurrent peer pairs:

| pair | count | share |
|---|---|---|
| monerod ↔ monerod | 563 | 8.4% |
| monerod ↔ cuprate | 3047 | 45.7% |
| cuprate ↔ cuprate | 3061 | 45.9% |

Peer degree:

| node impl | n | peers/node | → monerod | → cuprate | % cuprate |
|---|---|---|---|---|---|
| monerod | 157 | 26.1 | 7.2 | 19.0 | 72.6% |
| cuprate | 149 | **61.5** | 20.4 | 41.1 | 66.8% |

**Baseline arm** (306 monerod) — 3890 pairs, all monerod↔monerod, **25.2 peers/node**.

## Is the mixing assortative? No.

At first glance cuprate↔cuprate looks hugely over-represented: 45.9% observed against 23.7%
expected if you assume both implementations have the same degree. That naive null is wrong
here, because the degrees differ by 2.4×. High-degree nodes appear in more pairs, so pairs of
high-degree nodes are over-represented *by construction*.

The correct null is the degree-corrected (configuration-model) one: expected cross-group edge
share follows each group's share of **degree stubs**, not of nodes. Monerod holds
157×26.1 = 4098 stubs (30.9%); cuprate 149×61.5 = 9164 (69.1%):

| pair | observed | degree-corrected expectation | Δ |
|---|---|---|---|
| monerod ↔ monerod | 8.4% | 9.5% | −1.1pp |
| monerod ↔ cuprate | 45.7% | 42.7% | +3.0pp |
| cuprate ↔ cuprate | 45.9% | 47.7% | −1.8pp |

Agreement is close, and the small residual leans *toward* cross-implementation pairing —
the opposite of homophily. **Implementations do not cluster.** A cuprate node is no more
inclined to peer with another cuprate node than chance-plus-degree predicts.

This is unsurprising mechanically: neither implementation can tell a peer's implementation
before connecting, and peer selection draws from a shared address book. Cuprate's bootstrap
seeds are monerod miners, which if anything biases its early connections toward monerod.

`conn_matrix.py` now prints both nulls and labels the node-count one as misleading.

## Interpretation

1. **Cuprate is a better-connected participant by default.** 32 outbound vs 12 is a
   deliberate design choice, and at 300 nodes it yields ~2.4× the concurrent peers.

2. **This contributes to the ~2× faster transaction propagation** measured in
   `docs/20260724_cuprate_scale_experiment.md`, but it is the *minor* factor.
   **RESOLVED 2026-07-26** (that document's §9): pinning cuprate's outbound to monerod's 12
   via `out-peers` cut its degree 60.2 → 26.4 peers/node, and transaction propagation stayed
   **~1.78× faster** than the all-monerod baseline (vs 2.19× unpinned). Decomposing the
   improvement gives **~80% relay cadence, ~20% fan-out**. So higher fan-out is a real but
   secondary mechanism, and the scale experiment's original cadence attribution was
   substantially right. Caveat: pinning cuprate's outbound also lowers monerod's *inbound*
   (28.9 → 22.9), so degree parity is approximate (1.15× rather than 1.0×), which makes the
   80% cadence share a slight under-estimate.

3. **Monerod is unaffected.** 26.1 peers/node in the mixed network vs 25.2 in the all-monerod
   baseline. Inserting 149 cuprate nodes did not starve or crowd monerod's connectivity —
   consistent with the functional-equivalence finding.

4. **Privacy angle.** A cuprate node observes more of the network per unit time (61.5 vs 26.1
   concurrent peers), so a cuprate-based passive observer has a wider view for the same node
   count. Conversely each cuprate node is visible to more peers. This is a *degree* effect
   available to any node that raises `out_peers`, not something unique to cuprate — but it
   does mean "n% cuprate" changes the network's observability profile, not just its speed.
   Relevant to the deferred adversary experiments.

## Caveats

- **Direction is not recoverable in windowed mode.** Cuprate's handshakes mostly occur outside
  any narrow window, so its IN/OUT rows go empty and traffic lands in the direction-unknown
  bucket. Directionality is only meaningful in cumulative mode, where it is in turn subject to
  the saturation problem above. The tool warns about this.
- **Activity-based, not state-based.** "Concurrent peers" means *exchanged traffic in the
  window*. A connection that was open but idle for the whole 5 minutes is not counted. The
  two implementations log at different granularities, so this could bias the degree comparison
  — however, the degree figures land close to each implementation's configured outbound target
  (26 ≈ 12 out + inbound; 61 ≈ 32 out + inbound), which is independent corroboration.
- Single window, single seed. The degree gap is large and mechanically explained so it is
  robust, but the ±1–3pp mixing residuals are not resolvable at this precision.
- Peer identity is IP, so this cannot distinguish multiple daemons behind one IP. Not an issue
  in monerosim (one daemon per IP, verified).

## Reproducing

```bash
# concurrent (recommended)
python3 analysis/conn_matrix.py --window='^2000-01-01[ T]04:0[0-4]:' \
    archived_runs/20260724_133050_cuprate_exp_cuprate \
    archived_runs/20260723_212123_cuprate_exp_baseline

# cumulative (saturates on cuprate — see above)
python3 analysis/conn_matrix.py archived_runs/20260724_133050_cuprate_exp_cuprate
```

~35 min per archive pair (grep over ~14 GB).
