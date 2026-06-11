# Response to Rucknium's v0.1.0 Review (issue #3) — v2: Mechanisms, Not Narratives

**Date:** 2026-06-10
**Status:** COMPLETE DRAFT — all results in. All factual claims herein were
adversarially re-verified against raw logs, source trees, archives, and the
GitHub issue text on 2026-06-10; §10's feasibility statements are
source-verified (Shadow 3.2.0 fork + monerod v0.18 tree + orchestrator). The
matched-config replication run (`20260610_031558_clumping_0p67_monitor`,
cap=4, current stack, completed, all checks passed) was analyzed with
Rucknium's own code (§4.4).
**Supersedes** the never-posted 2026-06-09 response draft, whose central
interpretations did not survive verification (§7).

---

## 1. Executive summary

Rucknium's statistical review of monerosim v0.1.0 compared four propagation
statistics between Monero mainnet (his March-2024 black-marble-flood dataset,
~1.45 tx/s) and two monerosim runs: a 35-node test (30 users + 5 miners,
72 h) **he ran himself** on his own machine, and **our** 1000-node run, whose
logs he analyzed. Re-investigating each
flagged discrepancy against the **original 1000-node run's own logs** and
monerod source:

| His finding | Status | One-line explanation |
|---|---|---|
| Connection duration 1.52 min vs mainnet 23 min ("cause unclear") | **SOLVED** | Stock monerod's sync-search peer rotation (`update_sync_search`, 101 s timer) kills the newest non-anchor out-peer every cycle; the sim's perfect network refills the slot instantly, so victims live exactly one period. His metric measured this faithfully. |
| Clumping 23.40 % single ≈ mainnet 25.05 % | **Sim mechanism verified; comparison reframed** | Clumping is volume-bound. The run delivered 0.466 tx/s (not its 0.67 nominal) and was healthy. Sim-side mechanism (full flooding × Dandelion++ 5 s/2.5 s flush windows × cascade re-batching) verified quantitatively; the open question is why mainnet clumps ~3× less per unit rate. |
| One-second cycle: eighth- vs quarter-second | **Grid verified; sharpening plausible; sub-grid origin open** | `fluff_stepsize = std::ratio<1,4>` confirmed in source. The jitter-free sim resolves fine structure mainnet smears (his mainnet plot already shows the "subtle double-mode"). His latency hypothesis is contradicted by our own data (same comb at 35 and 1000 nodes). |
| Skellam "less close" at 1000 nodes | **Open** | Possibly flush-phase mixing from the 101 s rotation; unverified. Post-fix completing runs fit well. |

Two meta-results:

1. **Rucknium's tx-gap method is validated.** Gossip is continuous within
   connections (median inter-NOTIFY gap 4.9 s), so his inferred "connection
   duration" is a good proxy for the TCP lifetime of tx-carrying connections.
   Our emulation of his method on the same logs reproduces his numbers to
   within rounding (1.53 vs 1.52 min; 23.8 % vs 23.4 % singles).
2. **The `max-connections-per-ip` fix is real but orthogonal** to everything
   he measured (§6). It repairs small/dense full-mesh sims; at 1000 nodes
   every measured profile is statistically identical before and after it.

## 2. Method and validation

- Data: the original v0.1.0 1000-node run's daemon logs at log-level 1
  (`monero-user-103`, `monero-relay-014`, `monero-relay-432`), which contain
  both TCP events (`net.p2p` NEW/CLOSE CONNECTION) and gossip
  (`net.p2p.msg` NOTIFY_NEW_TRANSACTIONS / "Including transaction"); the
  post-fix 1000-node milestone run for replication; monero source for every
  constant cited.
- Tool: `analysis/results_clumping_0p67/conn_gossip_join.py` joins each gossip
  message to the TCP connection that carried it (by ip:port + direction +
  interval), yielding per-connection lifetimes, gossip continuity, clumping,
  and an emulation of Rucknium's hour-bucketed tx-gap method.
- Validation: emulated tx-gap median **1.53 min** (his: 1.52); clumping singles
  **23.82 %** (his: 23.40 %, 10-node sample). Binary and protocol verified
  constant across the whole experimental series (§8).

## 3. Connection duration — solved

### 3.1 The measurements (original run, user-103)

| population | n | median lifetime | p25–p90 | notes |
|---|---:|---:|---|---|
| all TCP connections | 5,319 | 0.5 s | 0.3 s – 100 s | discovery probes dominate |
| **tx-carrying connections** | 842 | **100.3 s** | **100.0 – 100.9 s** | a timer, not churn |
| — of which survive > 1 h | 60 (7.1 %) | — | up to 13.9 h | the protected anchors |
| non-tx connections | 4,477 | 0.3 s | — | handshake probes |

- "Dropping synced peer" events fire at **exactly 101 s cadence** — median
  inter-drop interval 101.001 s across all 497 events in 16 h (e.g.
  02:03:57.246 → 02:05:38.247 → 02:07:19.247). Every drop (497/497) is
  followed by `CLOSE CONNECTION` of that peer within 1 ms, and a replacement
  outbound `NEW CONNECTION` appears at median 0.76 s (100 % within 2 s).
  During the tx-traffic era ~94 % of victims are tx-carrying connections
  (the rest fall in the pre-traffic funding phase).
- Gossip fills connections end-to-end: 98.5 % of tx-carrying connections carry
  ≥ 2 NOTIFYs; median inter-NOTIFY gap 4.9 s; gossip span ≈ lifetime.

### 3.2 The mechanism (stock monerod, verified in source)

`t_cryptonote_protocol_handler::update_sync_search()`, driven by
`epee::math_helper::once_a_time_seconds<101> m_sync_search_checker`:
when a node has all `P2P_DEFAULT_CONNECTIONS_COUNT` (12) out-slots filled with
synced peers and fewer than `P2P_DEFAULT_SYNC_SEARCH_CONNECTIONS_COUNT` (2)
peers in `state_synchronizing`, it drops the **last non-anchor synced
out-peer** ("drop the last sync'd non-anchor", per the in-code comment) to
make room to search for sync candidates. The
`P2P_DEFAULT_ANCHOR_CONNECTIONS_COUNT` (2) anchor connections are exempt — a
countermeasure imported from the Eclipse-attacks literature (the feature's
commit cites Heilman et al. 2015, countermeasure 4).

A precision note: "last" means last in the connection map's iteration order —
a hash map keyed by random connection UUIDs, **not** insertion order. The
razor-sharp lifetime collapse is therefore emergent dynamics rather than a
code guarantee: with the dropper killing the iteration-last non-anchor every
cycle and the sim instantly refilling the slot, fresh entrants are the usual
victims (measured: 100.0–100.9 s spread around one timer period) while a
stable set of low-iteration-position connections — the 2 anchors plus
hash-position survivors — persists for hours. That also explains why the
elder population (~60 per node) exceeds what anchors alone (2 outgoing + a
few inbound) would produce.

In the simulator every node is always synced and every replacement connection
succeeds instantly (median 0.76 s), so the dropper fires every 101 s without
exception. This is **emergent stock-monerod policy under perfect network
conditions**, not a simulator bug, and not the connection-cap issue.

### 3.3 One mechanism, three environments

- **1000-node sim, 1.5 min:** rotation fires every period; in steady state the
  latest entrant is the usual victim (emergent — see §3.2 precision note).
- **Mainnet, 23 min:** rotation throttled — replacement attempts fail or stall
  (most candidates unreachable/stale), slots sit unfilled, victims spread
  across slots. (Mechanism of spread inferred, not directly measured —
  mainnet logs would be needed; see §9.)
- **His 35-node sim, 120 min:** peerlist exhausted, nothing to rotate to;
  tenures bounded by run length (his max 4,079 min ≈ 68 h, within the 72 h he
  ran it for).

Replicated post-fix: the milestone run shows the identical signature
(tx-carrying median 100.3 s, 546 drops, 62 elders) — same binary, cap=4.

## 4. Transaction clumping — sim mechanism verified; comparison reframed

### 4.1 Corrected rates: nominal vs delivered

Configured ("nominal") rates overstate what runs actually deliver (users wait
on funding/confirmations). Measured over the 11 h active window:

| run | nominal | **actual** | % single-tx msgs |
|---|---:|---:|---:|
| post-fix 200u @ 2400 s | 0.083 | 0.080 | 92.4 % |
| post-fix milestone @ 667 s | 0.300 | 0.226 | 49.5 % |
| **original v0.1.0 @ 300 s** | 0.667 | **0.466** | **23.4 %** |
| **matched-config replication @ 300 s (cap=4, current stack)** | 0.667 | **0.345** | **23.0 %** |
| mainnet spam wave (his data) | — | 1.45 | 25.05 % |

The original run **completed** (height 331, full 16 h, 18,444 txs counted from
its own logs) — the earlier internal theory that its clumping match was "an
artifact of an overloaded, stalled run" was wrong on both counts.

### 4.2 The verified sim-side mechanism

- **Full flooding:** 588,387 receipts / 18,444 unique txs = **31.9 receipts per
  tx ≈ node degree** — every transaction crosses every connection.
- **Per-connection flush batching:** stock Dandelion++ fluff queues flush per
  connection on Poisson timers — `CRYPTONOTE_DANDELIONPP_FLUSH_AVERAGE = 5 s`
  toward incoming peers, half that (2.5 s) toward outgoing
  (`levin_notify.cpp`). The direction split in our data shows exactly this
  2:1 asymmetry: messages received on OUT connections (peers' in-flushes):
  9.0 % singles, 4.25 txs/msg, 6.58 s median cadence; on INC connections
  (peers' out-flushes): 32.5 % singles, 2.73 txs/msg, 3.88 s.
- **Cascade amplification:** both directions clump *beyond* the Poisson floor
  for their window (predicted 25 %/53 % singles at 0.466 tx/s; measured
  9 %/32.5 %) because a relayed message re-batches its entire incoming clump.
  Consistent with clumping deepening through the run (29.7 % → 21.8 % singles
  from h4-8 to h12-16) at constant configured rate.

### 4.3 The honest open question

At mainnet's 1.45 tx/s, this same mechanism would predict ≲ 5–10 % singles;
Rucknium measured 25 %. **Mainnet damps clumping roughly 3× per unit rate
relative to the simulator.** Back-solving, his node's effective per-connection
λ ≈ 2.4 txs per flush window. Candidate explanations we cannot test without
mainnet logs: his node's connection count; NOTIFY size-splitting at high
rates; real-network jitter de-synchronizing flush queues; rate variability
within his measurement window. Questions for Rucknium in §9.

### 4.4 Matched-config replication on the fixed stack (run 20260610)

To close the loop we re-ran the original 200u/800r @ 300 s configuration on
the current stack (cap=4 fix in, same seed, same binary, monitor-level
logging) and analyzed it with Rucknium's own `xmrpeers` code. It completed
with all checks passed (1,011 nodes, 0 process failures, 13,678 txs,
0.345 tx/s delivered) and reproduced his original tables almost exactly:

| metric (his method) | original v0.1.0 (his analysis) | replication (cap=4, current) |
|---|---:|---:|
| % single-tx messages | 23.40 | **23.03** |
| 2 tx / 3 tx / 4 tx | 32.80 / 23.38 / 11.98 | 32.19 / 23.35 / 12.67 |
| conn-duration median (min) | 1.5244 | **1.5238** |
| conn-duration max (min) | 709.80 | 709.78 |

Two conclusions. First, the v0.1.0 numbers he measured are **healthy,
reproducible behavior** — not artifacts of a broken or overloaded run; a
clean run on the fixed stack lands within 0.4 pp on clumping and within
rounding on connection duration. Second, the clumping curve **saturates**:
26 % less delivered volume (0.345 vs 0.466 tx/s) moved singles by only
~0.4 pp, consistent with cascade re-batching reaching its fixed point. The
connection-duration identity across cap settings and orchestrator versions
is expected — that metric is fully determined by the 101 s rotation (§3).

## 5. One-second cycle and Skellam

- The quarter-second grid is real and now source-verified:
  `fluff_stepsize = std::chrono::duration<..., std::ratio<1,4>>` quantizes
  fluff delays to 250 ms steps. Mainnet shows the quarter-second comb with a
  "subtle double-mode on either side" (his words); the deterministic,
  jitter-free simulator sharpens that fine structure into a clean
  eighth-second comb. The precise origin of the eighth-second sub-grid is not
  fully derived; we flag it honestly as open.
- His latency hypothesis (Shadow's global latency spreading the comb) is not
  supported by the data: his 35-node run and our 1000-node run produce the same
  eighth-second comb under very different latency mixes.
- Skellam: the original 1000-node run's off-grid excess remains unexplained;
  plausibly flush-phase mixing under the 101 s rotation (unverified). The
  completing post-fix runs fit the theoretical distribution well.

## 6. The `max-connections-per-ip` bug: real, fixed, and orthogonal

Chasing the connection-duration flag, we found that monerod's default
`max-connections-per-ip=1` breaks **small, dense** simulations (15-node full
mesh: 31,180 refused connections across the run, 7,867 on one node alone; no
stable mesh; flooring the cap at 4 fixes it — orchestrator commit
`d21f971b`). At 1000 nodes, however, the fix changes
**nothing measurable**:

| metric @ 1000 nodes | cap=1 (original) | cap=4 (milestone) |
|---|---:|---:|
| tx-carrying conn median lifetime | 100.3 s | 100.3 s |
| all-conn median / probe churn | 0.5 s | 0.3 s |
| handshake success | 509/5,319 (9.6 %) | 558/5,568 (10.0 %) |
| closes in `before_handshake` (share of opened conns) | 65.3 % | 65.8 % |
| sync-search drops / 16 h | 497 | 546 |

(The ~10 % handshake-success and ~0.4 s probe-churn profile is normal monerod
peer discovery at this scale, present identically pre- and post-fix.) So the
cap fix is a genuine correctness improvement for small sims discovered thanks
to this review — but it does not explain, and did not change, any statistic
the review measured at 1000 nodes. The injected `4` is a config default, not
hardcoded behavior: setting `max-connections-per-ip: 1` in `daemon_defaults`
restores stock monerod exactly (verified through config generation), and the
example configs document the knob — fidelity-minded users can run stock at
scale, where it makes no measurable difference anyway.

## 7. Corrections to our earlier (briefly published) analysis

In the spirit of the review, our own first interpretations did not survive
measurement, and we retract them explicitly:

1. *"His connection-duration metric is a measurement artifact (tx-exchange
   span, not TCP)."* — **Wrong.** The metric tracks tx-carrying TCP lifetimes
   well (§3.1); his 1.52 min was a faithful measurement of a real behavior.
2. *"Every daemon was in a reconnect loop (~0.5 s median, ~10 % handshakes) —
   the cap bug broke the 1000-node mesh."* — **Wrong at 1000 nodes.** That
   profile is normal discovery probing and is identical post-fix (§6).
3. *"The 1000-node tx rate (0.67 tx/s) was 8× over the hardware's sustainable
   rate; the clumping match was an overload artifact; spam-wave intensity
   needs ~57 nodes."* — **Wrong.** The run completed; it delivered 0.466 tx/s;
   the capacity model behind "8×/57 nodes" was refuted by direct experiment
   (two completing 1000-node runs at the same config).
4. Rates were reported as configured rather than delivered; corrected in §4.1.

## 8. Build and protocol verification

- All runs in this series (original 20260511 → current) executed the **same
  monerod binary** (`v0.18.1.0-f09c2c858`, banner verified in each run's
  logs). `run_sim.sh` rebuilds only the Rust orchestrator, never monerod.
- Wire-protocol census over the original run's levin traffic: stock command
  IDs only (handshake/timed-sync/ping, NOTIFY_NEW_TRANSACTIONS, fluffy
  blocks). An experimental tx-relay-v2 monerod exists on the build machine
  (`monerod-v2`) but no run in this series (20260511 → current) uses it (only
  an unrelated April upgrade-test config references it); the live run was
  probed and carries zero v2 messages.
- The fork's source is byte-identical to stock monero in the three mechanisms
  cited here (`update_sync_search` + its timer, the sync/anchor constants,
  the levin_notify fluff constants). The fork does diverge elsewhere (e.g.
  its `P2P_SUPPORT_FLAGS` adds a tx-relay-v2 bit), which is why the protocol
  claim above rests on the **wire census**, not on tree identity.

## 9. Questions for Rucknium

1. During your 25 %-singles mainnet window, roughly how many P2P connections
   did your node hold, and does your log show each tx arriving on (nearly)
   every connection — i.e., full flooding? This decides the clumping-damping
   question (§4.3).
2. Does your mainnet node's log show `dropping synced peer` events
   (`update_sync_search`)? Their cadence vs. connection count on a real node
   would confirm the §3.3 account of the 23-minute median directly.

## 10. Toward mainnet-like connection tenure in the simulator

The 101 s rotation result implies the gap is **environmental** (a perfect
network), not protocol infidelity. The simulator runs stock monerod correctly;
mainnet's longer tenures come from friction the sim lacks. We verified the
relevant mechanics in source (monerod v0.18 tree; Shadow 3.2.0 fork;
orchestrator):

1. **Unreachable-majority structure — config-only, but contributes realism,
   not rotation friction.** `--hide-my-port` makes a node advertise
   `my_port=0` while still listening and dialing out (`net_node.inl`,
   `get_local_node_data`). Because white-list insertion happens only via a
   successful back-ping, and `try_ping` early-returns on `my_port==0`, hidden
   nodes **never enter anyone's peerlist** — so an 80 %-hidden network keeps
   peerlists clean (only reachable nodes listed) and produces **zero failed
   dials by itself**. Still worth doing: it reproduces mainnet's
   reachable-minority topology, inbound/outbound mix, and back-ping
   conditions. (`--in-peers 0` is the stricter variant but burns a 2 s
   back-ping per handshake since it still advertises its port;
   `--hide-my-port` is the cleaner primitive. The orchestrator passes neither
   today — both knobs are free.)
2. **Node churn — the verified friction lever, and it needs no new
   orchestrator machinery.** A node that goes offline *leaves its address in
   other nodes' white lists* (inserted while it was up). Dials to it then
   fail, and monerod suppresses a failed address for **one hour**
   (`P2P_FAILED_ADDR_FORGET_SECONDS = 3600`) from candidate selection,
   anchor reconnects, *and* gossip re-learning — so even modest churn (a few
   %/hour) progressively darkens the candidate pool, starving the
   slot-refill that the rotation depends on (`n_synced + n_syncing <
   max_out_peers` ⇒ no drop). Restarted nodes also transit
   `state_synchronizing`, pausing their own rotation while catching up.
   Feasibility is already proven end-to-end: Shadow supports per-process
   `shutdown_time`/`shutdown_signal`/`expected_final_state`, and monerosim's
   **existing upgrade-phase machinery** (`daemon_0`/`daemon_1` scenario keys
   → `DaemonPhase` → `ShadowProcess`) already expresses scheduled
   stop+restart of the *same* binary on the same data dir and ports —
   port-rebind, LMDB-lock, and wallet-reconnect issues were all solved for
   binary upgrades (SIGTERM clean exit; kernel-released fcntl locks; the
   fork's bind-time socket cleanup). What's left is generator convenience:
   emitting randomized per-node churn schedules instead of hand-written
   phases. (Caveat: daemon-churn with the agent/wallet staying up is
   exercised only by the upgrade path so far.)
3. **Handshake/connect latency realism.** Mainnet refill costs RTTs and
   timeouts (failed dials up to `P2P_DEFAULT_CONNECTION_TIMEOUT` = 5 s);
   in Shadow a stopped peer refuses instantly. This makes churn-induced
   friction *weaker* in the sim than the equivalent churn on mainnet —
   worth remembering when calibrating churn rates upward.

Falsifiable prediction: with (2) at a few %/hour churn (plus (1) for
structure), tx-carrying connection median lifetime should rise from ~100 s
toward tens of minutes **with zero monerod changes** — the 1-hour
failed-address memory means even low churn rates should move it
substantially. A medium-scale (~300-node) A/B comparing churn-on vs churn-off
would confirm direction cheaply before a 1000-node run.

## 11. Reproduction

- Join/analysis script: `analysis/results_clumping_0p67/conn_gossip_join.py`
  (run against any log-level-1 / monitor daemon log).
- Rate audit: `analysis/results_clumping_0p67/rate_audit.md`.
- Full investigation notes:
  `analysis/results_clumping_0p67/discrepancy_investigation.md`.
- Rucknium-method analysis: `analysis/ruck_analysis.r` (his xmrpeers code) —
  monitor log level suffices (emits `net.p2p.msg`); log-level 0 yields no data.
- Archives: original-run logs (`xfer_logs/`), milestone
  (`archived_runs/20260608_164109_1k_mainnet`), cap reproduction
  (`archived_runs/20260609_153322_captest_cap4`), matched-config clumping run
  (`archived_runs/20260610_031558_clumping_0p67_monitor`).
