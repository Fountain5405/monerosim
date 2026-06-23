# Matching Mainnet: Simulator Fidelity Across Rucknium's Four Metrics

**Status:** Reachable-fraction sweep complete (15/40/50/60/80%). Next experiment
is peer churn (§5.3). All results below are final and reproducible.
**Companion:** `docs/20260610_rucknium_review_response_v2.md` (review response —
where clumping and Skellam were resolved).

## 1. Where the simulator stands vs mainnet, on every metric Rucknium measured

Rucknium's review (issue #3) compared mainnet against the simulation on **four**
transaction-propagation statistics. This is the scorecard — the full set of
deltas, not just the headline one:

| Metric | Mainnet (Rucknium) | Simulator | Driver of the gap | Status |
|---|---|---|---|---|
| **Transaction clumping** | 25% single-tx (1.45 tx/s spam wave) | volume-bound; 23.4% single at 0.47 tx/s — the curve matches mainnet | tx **volume** (not topology); spam-wave intensity isn't reachable at 1000 nodes on one box, but the curve does | ✅ resolved (v2 §4) |
| **Skellam timing** | good fit, mild zero-spike | good fit, centered at 0 | — (already matched) | ✅ resolved (v2 §5) |
| **Connection duration** | 23 min (few long conns) | median tunable 150→1.5 min via reachability; hits 23 min at ~50% | **reachable-pool size** (median) — but the *distribution* needs **churn** | 🔧 partial — median fits at ~50%, but not at mainnet's real ~15%, and the >6h tail stays ~8× too heavy (§5.3); churn is next |
| **One-second cycle** | quarter-second | quarter-second appears (15%, 60%); not a clean function of reachability | likely topology, but the plot is a high-variance single-pair statistic | 🔬 mainnet's quarter-second is *reproducible* in-sim; can't yet claim it's controlled (§5.1) |

**Two of the four (clumping, Skellam) were resolved in the review response.** The
other two — connection duration and the one-second cycle — both turned out to be
**topology-driven**, and that is what this study investigates.

The root cause for both: monerosim launched a **"perfect network"** — every node
advertised a reachable P2P port and accepted inbound. Mainnet is the opposite:

- **Most nodes are unreachable** (behind NAT / firewall / `--hide-my-port`).
  Triangulated estimate: **~15% reachable / ~85% unreachable** (Cao et al. 2019:
  86.8% of nodes are low-degree leaves; reachable nodes carry 50–100 inbound,
  which with 12 outbound/node implies ~12–24% reachable).
- **A few supernodes** carry a disproportionate share (Cao 2019: ~0.7% of nodes
  are super-peers with >250 connections; 13% of nodes hold 83% of all edges).

This study adds both to monerosim and measures the effect on the two remaining
gaps, with mainnet's values as the targets.

## 2. The knob: `--reachable`

A configurable fraction of non-seed nodes advertise a reachable port; the
complement get monerod's `--hide-my-port` (advertise `my_port=0`, still dial out
and relay, but never enter peerlists, so they accept ~no inbound — a NAT'd
leaf). Default `1.0` = the historical perfect network. Seeds and miners stay
reachable. Selection is deterministic from `simulation_seed`. Available as
`general.reachable_fraction` (+ per-role override), CLI `--reachable`, and
`run_sim.sh --reachable`.

## 3. Gap #1 — Connection duration: mechanism (peer recurrence, not TCP instability)

Rucknium's "connection duration" is a **tx-gap** metric: per peer, the span over
which you exchange transactions (grouped into contiguous-hour periods) — **not**
raw TCP socket lifetime. We verified what actually drives it:

- The sync-search peer dropper (`update_sync_search`, 101 s timer) cycles each
  node's outbound peers; **individual TCP connections live ~100 s** (measured
  ~100 s median TCP lifetime, ~31 drops/h/node, in the complete all-reachable
  log-level-1 reference run, 20260511).
- What changes with topology is **recurrence**: with a *large* reachable pool,
  each ~100 s connection lands on a *different* peer, so the per-peer tx-gap span
  ≈ one connection ≈ 1.5 min. With a *small* reachable pool, every node
  reconnects to the *same* few reachable peers over and over, so the per-peer
  span stretches across hours.

So **connection duration is governed by the size of the dialable (reachable)
pool**, via peer recurrence in the metric. (This corrects an earlier guess that
the dropper "stops firing" — it does not; checked against drop counts.)

## 4. Feasibility and a side-effect

- **The unreachable-majority mesh stays healthy at 1000 nodes.** With 85% hidden
  (≈161 reachable carrying all discovery + inbound), runs complete with 100%
  sync, 0 process failures, normal block production. Discovery flows through the
  reachable minority + seeds.
- **Supernodes were added as a hypothesis test** (does mainnet's hub structure
  affect these metrics?) — and brought an unexpected byproduct: they **slash the
  simulation cost**. A uniform 85%-hidden network is ~3× *slower to simulate*
  (850 nodes re-dialing 161 reachable = a huge connection event load; ~40 h for
  a 16 h sim). With 5 high-degree hubs (`out-peers`/`in-peers` 256) the topology
  stabilizes and the run **drops to ~6 h** — the hubs absorb connections instead
  of the network thrashing. Hub formation verified (a supernode relayed 414k
  tx-notifies across ~700 peers vs a hidden leaf's 34k across 68). On the
  *metrics*, the hubs did not pull connection duration toward mainnet (still
  150 min at 15% reachable) — the reachable fraction is the lever, not the hubs.
- **Open side-effect:** the NAT-heavy topology throttles *effective tx
  throughput* ~5× (sn_r15: ~12 tx/user vs the control's ~64), **cause not yet
  resolved**. Ruled out: sync (all nodes reach the same height in lockstep,
  ≤0.3 s apart), funding (balances comparable), daemon load (hidden nodes hold
  *fewer* connections). Leading unverified candidate: the send cadence is paced
  by each prior tx reaching the 5 miners to be mined (change-unlock), which may
  be slower through the congested reachable minority. (The high single-tx
  clumping in low-reachable runs is a *consequence* of this low volume —
  clumping is volume-bound — not a topology signal.)

## 5. Results

All runs: 1000 nodes, 200 users / 800 (or 795) relays / 5 miners, 300 s tx
interval, seed 12345, 16 h simulated, monitor log level; connection duration by
Rucknium's `xmrpeers` tx-gap method (10-user sample). Connection duration is
**window-sensitive** (recurrence accumulates), so full-16 h runs are compared
to full-16 h runs.

| reachable | supernodes | conn-duration median | % single-tx | tx created | run |
|---:|:--:|---:|---:|---:|---|
| 100% (0.30 load) | no | 1.47 min | 49.5% | 8,945 | `1k_mainnet` — v2 response\* |
| **100%** (0.67 load) | no | **1.52 min** | 23.0% | 13,678 | `clumping_0p67_monitor` (control)\* |
| **15%** | yes (5) | **150 min** | 91.3%† | 3,254 | `sn_r15` |
| 40% | yes (5) | 62 min | 90.8%† | 3,242 | `sn_sweep_r40` |
| **50%** | yes (5) | **20.7 min** | 90.5%† | 3,245 | **`sn_sweep_r50`** ← ≈ mainnet median |
| 60% | yes (5) | 2.1 min | 90.2%† | 3,262 | `sn_sweep_r60` |
| 80% | yes (5) | 1.5 min | 90.8%† | 3,282 | `sn_sweep_r80` |
| — | — | **23 min** (target) | 25.0% | — | mainnet (Rucknium, 2024 spam wave) |

\* The two 100% rows are from our review-response work (`docs/20260610_rucknium_review_response_v2.md`):
the standard-mainnet milestone (0.30 tx/s) and the matched-config replication
(0.67) — both all-reachable and *completing*. Note connection duration is ~1.5 min
at 100% reachable **regardless of load**, confirming it is topology-driven, not
volume-driven. † 91.3% single is a low-volume artifact of the ~5× throughput
throttle (§4), not a topology effect.

> **Excluded (incomplete):** a uniform 15%-reachable run *without* supernodes
> (`topo1k_r15`, log-level 1) was attempted to capture TCP-level events, but
> **timed out at 48%** — the unreachable-majority topology is ~3× slower to
> simulate (the speedup from supernodes, added separately as a hypothesis test,
> is what later made full runs practical). It is **not used as a data point**;
> its partial logs only informally corroborated the
> mechanism below (TCP connections still ~100 s; sync-search drops still
> firing), consistent with the complete runs.

**Headline:** reachable-pool size is a real lever for the connection-duration
**median** — it sweeps from 150 min (15% reachable) through mainnet's 23 min
(at ~50%, measured 20.7 min) down to the 1.5-min floor (80%+). But the match is
**partial and tells a clear story about what's still missing** (§5.3).

### 5.3 The catch: a fitted median is not a matched network

Two facts keep the ~50%-reachable median match from being "mainnet matched":

1. **~50% reachable is not mainnet's topology.** Mainnet is ~15% reachable
   (§1). At that *realistic* fraction the median is 150 min, ~6.5× too high. So
   hitting 23 min requires cranking reachability to an unrealistic ~50% — fitting
   the metric, not reproducing the network.
2. **The connection-duration distribution is the wrong shape — at every
   fraction.** Mainnet has *few* long-lived connections; the simulator has many,
   and reachability barely dents it:

   | reachable | median | conns lasting > 6 h (OUT / INC) |
   |---:|---:|---:|
   | 15% | 150 min | 20.9% / 25.1% |
   | 40% | 62 min | 16.7% / 17.8% |
   | **50%** | **20.7 min** | **12.9% / 12.4%** |
   | 60% | 2.1 min | 10.0% / 9.8% |
   | 80% | 1.5 min | 9.1% / 8.1% |
   | **mainnet** | **23 min** | **~0% / ~1.5%** |

   Even at the 50% that nails the median, ~12% of connections persist > 6 h
   versus mainnet's ~1.5% — **~8× too many over-stable connections** — and the
   gap shrinks only slowly with reachability, never approaching mainnet.

**Conclusion: reachable fraction is necessary but not sufficient.** It cannot
simultaneously reproduce (a) mainnet's actual reachability (~15%), (b) the 23-min
median, and (c) the connection-duration *distribution*. The mechanism that ties
all three together is **peer churn** (nodes leaving and rejoining): on mainnet a
peer relationship is naturally bounded because peers come and go, which caps the
long tail *and* sets a realistic median *at* a realistic reachability. Churn is
the indicated next experiment — at ~15% reachable, does adding turnover pull the
median to ~23 min **and** the > 6 h share to ~1.5%? Supernodes change the
*simulation cost* (≈6 h vs ≈40 h), not the duration.

**Clumping is volume-bound (from the review response).** Our v2 work established
that transaction clumping tracks delivered tx rate, not topology — so sn_r15's
91% single is just a consequence of its low throughput, not a topology signal:

| delivered tx/s | % single-tx msgs | run |
|---:|---:|---|
| 0.080 | 92.4% | 1k_rerun (under-loaded) |
| 0.226 | 49.5% | 1k_mainnet milestone (standard mainnet) |
| 0.345 | 23.0% | 0.67-config replication |
| 0.466 | 23.4% | original v0.1.0 1000-node |
| 1.45 | 25.0% | mainnet (Rucknium spam wave) |

(Full detail: `docs/20260610_rucknium_review_response_v2.md` §4.)

### 5.1 All of Rucknium's metrics for sn_r15 (not just duration)

| metric | all-reachable control | sn_r15 (15% + supernodes) | mainnet (Rucknium) |
|---|---|---|---|
| conn-duration median | 1.52 min | 150 min (OUT 141 / INC 176) | 23 min |
| connections lasting > 6 h | ~1–2% | **~21% OUT / ~25% INC** | ~1.5% |
| peer recurrence (distinct hrs seen) | low | median 9–10 of 16 | — |
| clumping (% single) | 23.0% | 91.3% (low-vol artifact) | 25.0% |
| one-second cycle | eighth-second (4 cardinal + diagonal sub-lobes) | **quarter-second** (sub-lobes suppressed) | quarter-second |
| Skellam fit | noisier / more off-grid | clean, centered at 0 | good + zero-spike |

Two findings beyond duration:

- **The one-second cycle: mainnet's quarter-second is reproducible, but not a
  clean function of reachability.** sn_r15 (15%) shows clean **quarter-second**
  — mainnet's signature, and the very pattern Rucknium called the "one
  un-matchable item." But across the full sweep the petal count is *not*
  monotonic: 15%→quarter (4 petals), 40%→eighth (8), 60%→quarter (4), 80%→
  sixteenth (~16). The reason is methodological: Rucknium's circular-density plot
  is built from the **single most-common node pair** in the sample
  (`pair.in.time.sync`), so it is a high-variance, one-pair statistic. The honest
  reading: the simulator *can* produce mainnet's quarter-second cycle (so it is
  no longer "un-matchable"), but we cannot claim reachability *controls* it from
  these data. (An earlier draft of this report over-read three points as a clean
  monotonic trend; the fourth point refuted it.)
- **Over-stable connections:** ~21–25% of connections last > 6 h vs mainnet's
  ~1.5% — an independent indicator that 15% reachable overshoots (see §5.3 for
  the full sweep and why this points to churn).

### 5.2 Figures

**(a) Rucknium's original analysis (issue #3) — three reference networks.** His
mainnet column (2024 spam wave) is the target; the bottom row is his analysis of
*our* v0.1.0 1000-node run.

<table>
<tr><th>network</th><th>Connection duration</th><th>One-second cycle</th><th>Skellam</th></tr>
<tr>
<td><b>Mainnet</b><br>(target)</td>
<td><img src="assets/topology_study/mainnet_connection-duration.png" width="230"></td>
<td><img src="assets/topology_study/mainnet_one-second-cycle.png" width="230"></td>
<td><img src="assets/topology_study/mainnet_skellam.png" width="230"></td>
</tr>
<tr>
<td>Rucknium's<br>35-node sim</td>
<td><img src="assets/topology_study/r_35node_connection-duration.png" width="230"></td>
<td><img src="assets/topology_study/r_35node_one-second-cycle.png" width="230"></td>
<td><img src="assets/topology_study/r_35node_skellam.png" width="230"></td>
</tr>
<tr>
<td>v0.1.0 1000-node<br>(our run, his analysis)</td>
<td><img src="assets/topology_study/v010_1k_connection-duration.png" width="230"></td>
<td><img src="assets/topology_study/v010_1k_one-second-cycle.png" width="230"></td>
<td><img src="assets/topology_study/v010_1k_skellam.png" width="230"></td>
</tr>
</table>

**(b) Our topology response.** Fixed all-reachable 1000-node (the "perfect
network" control) → 15% reachable + 5 supernodes → the 50% point where the
connection-duration median matches mainnet. (The one-second-cycle column is a
high-variance single-pair statistic — see §5.1; read it as "quarter-second is
reproducible," not as a clean trend.)

<table>
<tr><th>run</th><th>Connection duration</th><th>One-second cycle</th><th>Skellam</th></tr>
<tr>
<td><b>v2 response: all-reachable 1k</b><br>(standard mainnet, 0.30, 1.47 min)</td>
<td><img src="assets/topology_study/v2_milestone_connection-duration.png" width="230"></td>
<td><img src="assets/topology_study/v2_milestone_one-second-cycle.png" width="230"></td>
<td><img src="assets/topology_study/v2_milestone_skellam.png" width="230"></td>
</tr>
<tr>
<td>All-reachable 1k @ 0.67<br>(matched control, 1.52 min)</td>
<td><img src="assets/topology_study/allreach_connection-duration.png" width="230"></td>
<td><img src="assets/topology_study/allreach_one-second-cycle.png" width="230"></td>
<td><img src="assets/topology_study/allreach_skellam.png" width="230"></td>
</tr>
<tr>
<td><b>15% reachable + 5 supernodes</b><br>(sn_r15, 150 min)</td>
<td><img src="assets/topology_study/sn_r15_connection-duration.png" width="230"></td>
<td><img src="assets/topology_study/sn_r15_one-second-cycle.png" width="230"></td>
<td><img src="assets/topology_study/sn_r15_skellam.png" width="230"></td>
</tr>
<tr>
<td><b>50% reachable + 5 supernodes</b><br>(sn_sweep_r50, 20.7 min ≈ mainnet)</td>
<td><img src="assets/topology_study/r50_connection-duration.png" width="230"></td>
<td><img src="assets/topology_study/r50_one-second-cycle.png" width="230"></td>
<td><img src="assets/topology_study/r50_skellam.png" width="230"></td>
</tr>
</table>

**(c) The reachable-fraction sweep — connection-duration kernel densities.**
The median sweeps down through mainnet's 23 min (at ~50%) toward the all-reachable
floor; the long > 6 h tail (§5.3) persists throughout.

<table>
<tr><th>15% (150 min)</th><th>40% (62 min)</th><th>50% (20.7 min)</th><th>60% (2.1 min)</th><th>80% (1.5 min)</th></tr>
<tr>
<td><img src="assets/topology_study/sn_r15_connection-duration.png" width="150"></td>
<td><img src="assets/topology_study/r40_connection-duration.png" width="150"></td>
<td><img src="assets/topology_study/r50_connection-duration.png" width="150"></td>
<td><img src="assets/topology_study/r60_connection-duration.png" width="150"></td>
<td><img src="assets/topology_study/r80_connection-duration.png" width="150"></td>
</tr>
</table>

## 6. Caveats / open questions

1. **Window-sensitivity:** the tx-gap metric accumulates recurrence over the
   observation window, so matching the *absolute* 23 min requires a window
   comparable to Rucknium's. A static reachable fraction may not produce a
   window-independent 23 min — peer **turnover (churn)** is the mechanism that
   bounds recurrence on real mainnet, and is the natural next lever after the
   fraction sweep.
2. **Throughput-throttle cause** (§4) is unresolved.
3. **Supernode model:** regular reachable nodes use the default *unlimited*
   inbound, so they too become high-degree; the supernodes' distinction here is
   mainly out-degree. A sharper hub model would cap regular-node inbound.

## 7. Reproduction

- Feature + configs: `--reachable` (commit `cbd36f19`);
  `test_configs/topo1k_supernodes.{scenario.,}yaml` (supernode mix),
  `test_configs/clumping_0p67_monitor.yaml` (all-reachable control).
- Run: `./run_sim.sh --config test_configs/topo1k_supernodes.yaml --name <n> --reachable <f>`
- Analyze: `analysis/ruck_analysis.r` (tx-gap conn-duration + clumping);
  `analysis/results_clumping_0p67/conn_gossip_join.py` (TCP-level join, needs
  log-level 1).
- Archives: `archived_runs/20260619_135809_sn_r15/` (the new run);
  `archived_runs/20260610_031558_clumping_0p67_monitor/` and the v2 response doc
  for the all-reachable baselines. (The excluded `topo1k_r15` partial is not a
  data source.)
