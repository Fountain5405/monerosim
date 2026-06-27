# Mainnet network topology: targets + monerosim config approach

**Date:** 2026-06-18
**Status:** Design draft — research done (workflow wojuzgrtv, 4 parallel
investigations: web crawler data + monerod source + monerosim source + Shadow
source). No code/runs yet — awaiting design decisions.
**Goal:** Replace monerosim's "perfect network" (every node reachable on
18080) with a mainnet-like topology where the majority of nodes are unreachable
(behind NAT / `--hide-my-port`), to close the connection-duration realism gap
identified in the Rucknium response (`docs/20260610_rucknium_review_response_v2.md` §10).

## 1. The "perfect network" problem (confirmed in source)

monerosim currently launches **every** daemon with `--p2p-bind-ip=<agent_ip>
--p2p-bind-port=18080` (`src/agent/user_agents.rs:303-305`) — all nodes
advertise a reachable port, all accept inbound. There is no notion of NAT,
private IPs, or unreachability. The GML topology (CAIDA AS graph) supplies only
latency/AS structure and does **not** constrain connectivity; monerod forms its
own full mesh via seed nodes + gossip. So topology realism is a
monerod-peering problem, not a GML problem.

## 2. Mainnet target numbers

### Reachable fraction — the key calibration ratio: ~15% reachable / ~85% unreachable

This is triangulated from three independent lines, all converging on ~10-20%:

1. **Topology skew (Cao et al. 2019, eprint 2019/411, NeighborFinder — the only
   method that infers NAT-active nodes):** 86.8% of active nodes hold ≤8
   outbound and only 17.1% of all connections; 13.2% of nodes hold 82.9% of
   connections. → reachable hubs ≈ **13%**.
2. **Inbound-count derivation (independent):** Rucknium's MRL Black-Marble data
   says reachable nodes "usually have between 50 and 100 incoming connections,"
   and every node makes 12 outbound. If reachable fraction = R and all 12·N
   outbound land on reachable nodes, inbound-per-reachable = 12/R. Setting that
   to 50-100 → **R ≈ 12-24%**.
3. **Investigation-4 synthesis of mainnet behavior:** "roughly 10-20% reachable."

→ **Primary target: 15% reachable (85% `--hide-my-port`).** A nice consequence:
at 1000 nodes / 15% reachable, each reachable node would absorb ~12·1000/150 ≈
**80 inbound** — landing exactly in Rucknium's observed 50-100 band, a built-in
validation check.

NOTE the crawler-visible "~48-60% reachable" figures (Friend-or-Foe 2025:
13,050 / 26,919 IPs; ProbeLab 2026: ~57%) are a *different* ratio —
reachable-vs-all-gossiped-IPs — and **undercount pure-NAT nodes** (which never
enter peerlists, so crawlers can't see them). They are not the topology
fraction we want; the ~15% figure is.

### Reachable node counts (for context / scale realism)
- Direct crawler counts 2024-2026: ~12,000 (monero.fail May 2024) → ~13,600
  (Rucknium 2024) → 13,050 (Friend-or-Foe 2025) → 16,454 Levin handshakes
  (ProbeLab Feb 2026).
- **Spy-node caveat:** ProbeLab Feb-2026 found ~81% of reachable nodes are spy
  nodes from ONE ASN (Spruce Creek Networks); Rucknium's 2024-25 normal-period
  figure was ~40% spies. So *honest* reachable nodes ≈ 3,000 (2026). We are not
  modeling spies; this only matters for absolute-count realism, not the fraction.
- Ignore the moneroswapper.io "45,000-50,000" blog figure (uncited, ~3× every
  primary crawler).

### Connection parameters (verified, stock monerod v0.18)
| param | value | source |
|---|---|---|
| out-peers | **12** (incl. 2 anchors) | P2P_DEFAULT_CONNECTIONS_COUNT, net_node.inl:2851 |
| in-peers | **unlimited** (default -1 → 0xFFFFFFFF) | net_node.inl:2862 |
| anchor connections | **2** | P2P_DEFAULT_ANCHOR_CONNECTIONS_COUNT |
| max-connections-per-ip | 1 stock (we floor 4) | net_node.cpp:172 |
| white / gray peerlist cap | 1000 / 5000 | cryptonote_config.h:136-137 |
| peers per gossip | up to 250 (white only) | P2P_DEFAULT_PEERS_IN_HANDSHAKE |
| reachable node connections | 12 out + **50-100 in** | Rucknium MRL |
| unreachable node connections | 12 out + **~0 in** | derived |

### The validation target (what success looks like)
Rucknium mainnet **median connection duration ≈ 23 min** (both directions).
Our all-reachable sims sit at ~1.5 min (the 101 s sync-search rotation firing
every period because slot refill is instant). An unreachable majority should
push this toward mainnet by adding refill friction (fewer dialable candidates).

## 3. Why an unreachable majority is the right lever (Shadow + monerod source)

- **Shadow has no network-layer unreachability primitive** (no per-host
  firewall; the only drop knob is symmetric per-edge `packet_loss` that never
  drops SYN/handshake packets and is disabled during bootstrap). Unreachability
  must live in monerod.
- **`--hide-my-port` is the clean mechanism** (beats `--in-peers 0`): it makes
  the node advertise `my_port=0` (net_node.inl:2313-2316), still bind/listen,
  and **never enter any peerlist** (white-listing of an inbound peer happens
  only in the `try_ping` success callback, gated on `my_port`; `try_ping`
  early-returns when `my_port==0`, net_node.inl:2446/2677/2704). Result: dials
  out, forms its 12 outbound, accepts ~0 inbound, zero peerlist pollution, zero
  wasted back-pings. `--in-peers 0` is worse — still advertises its port →
  pollutes peerlists + every peer wastes a 2 s back-ping that gets refused.
- **Mesh stays connected** because discovery flows ONLY through reachable nodes
  by construction (gossip = white list = reachable-only). The binding
  constraint is inbound *capacity*: R·max_in ≥ 12·N. With default unlimited
  in-peers this holds easily even at single-digit reachable %. **Seeds and
  miners MUST stay reachable** or bootstrap fails.
- **Second-order effects are all in the mainnet direction:** fewer dial targets
  → more refill friction (→ longer connection duration, the goal); gossip
  converging on the same small reachable set → structural clumping/degree-skew
  onto reachable hubs (mirrors mainnet hubbing) on top of the known
  volume-bound clumping.

## 4. Recommended config approach

Make unreachability a **scenario-level knob** that expands to per-agent
`--hide-my-port`. Per-agent `daemon_options` already merge correctly
(`merge_options`, src/utils/options.rs; explicit-per-agent wins over defaults),
so **no Rust changes are needed** — only the scenario→config expansion.

- Scenario YAML: `network: { unreachable_fraction: 0.85 }` (or role-keyed:
  `user_unreachable_fraction`).
- `scripts/scenario_parser.py` `expand_scenario()`: deterministically select
  that fraction of NON-seed, NON-miner agents and inject
  `daemon_options: { hide-my-port: true }` into each.
- Keep miners + seed/fallback-seed nodes reachable (bootstrap backbone).

**Scout-first plan (no parser changes):** for the first validation run, take an
existing expanded config (e.g. `clumping_0p67_monitor.yaml`) and a small script
that adds `daemon_options: {hide-my-port: true}` to 85% of `user-*`/`relay-*`
agents (excluding miners + seeds). Run the A/B before investing in the knob.

## 5. Validation plan

A/B at ~300-1000 nodes, all-reachable vs 15%-reachable, monitor log level
(for the connection + clumping analysis):
1. **Mesh health:** does it still complete, sync 100%, stable peer counts?
2. **Connection duration:** does tx-carrying median move from ~1.5 min toward
   mainnet's 23 min? (the headline test)
3. **Inbound distribution:** do reachable nodes accumulate ~50-100 inbound
   (the 12/R cross-check)?
4. **Clumping:** does structural hub-clumping appear on top of volume effect?
5. Sweep reachable fraction (e.g. 10/15/20%) if the first run is healthy.

## 5b. IMPLEMENTATION (done 2026-06-18, override semantics, positive naming)

Wired in as `--reachable` (positive: fraction *reachable*, default 1.0 = today's
perfect network) with config + CLI + run_sim.sh, override (not multiply)
semantics:
- **Config:** `general.reachable_fraction: f64` (default 1.0) +
  `general.reachable_by_role: {user: .., relay: ..}` (override per role).
  `src/config/types.rs`.
- **CLI:** `monerosim --reachable 0.15` overrides the global. `src/main.rs`
  (validates [0,1]). `run_sim.sh --reachable 0.15` forwards it.
- **Mechanism:** `src/agent/user_agents.rs` — `compute_unreachable_set()` groups
  non-seed/non-miner agents by role (`user`=has wallet, `relay`=daemon-only),
  and for each role marks `round((1-r)*count)` as unreachable, chosen by a
  deterministic FNV hash of `(simulation_seed, agent_id)` so runs reproduce.
  Selected agents get `--hide-my-port` injected into their daemon options
  (`.entry().or_insert` — explicit per-agent setting still wins). Seeds + miners
  always excluded.
- **Verified:** default → 0 hidden (backward compat); `--reachable 0.15` on the
  300-node config → 251 hidden / 49 reachable (5 miners + 44), 0 miners touched,
  ⇒ ~73 inbound/reachable node (in the 50-100 band). cargo build clean,
  `bash -n run_sim.sh` clean.

### The A/B (single 15% run at 300 nodes — user's choice)
Base config `test_configs/topo300.yaml` (5 miners + 60 users + 235 relays,
monitor log level, seed 12345, 16h). Run the SAME config twice (~78 min wall
each per scenario_parser estimate); only the flag differs:
```
# control (perfect network):
./run_sim.sh --config test_configs/topo300.yaml --name topo300_allreach
# treatment (~85% NAT'd):
./run_sim.sh --config test_configs/topo300.yaml --name topo300_r15 --reachable 0.15
```
Then `analysis/ruck_analysis.r` on each archive → compare tx-carrying
connection-duration median (does treatment rise toward 23 min?), inbound
distribution on reachable nodes, mesh health, clumping.

## 5c. RESULTS (2026-06-18/19)

### 300-node scout (topo300, 8h): feasibility ✅, but wrong scale
control vs treatment (15% reachable): both healthy (306 online, 100% sync), but
conn-duration ~120 min BOTH (the small-network regime, not the 1.5-min regime) —
300 nodes too small to test the gap. Confirmed: the 85%-hidden mesh completes.

### 1000-node treatment (topo1k_r15, 200u/800r/300s, LL1, --reachable 0.15)
Run TIMED OUT at 48% (sim 7.7h/16h) — the 85%-hidden topology is ~3x SLOWER to
simulate (0.39x sim:wall vs control's 1.2x: 850 nodes hammering 161 reachable +
constant dial-retries = huge P2P-event load). LL1 added to the slowness. BUT the
partial /tmp logs were salvaged (analysis in archive .../salvage_analysis/), and
they answer the question conclusively:

**HEADLINE: topology IS the connection-duration lever, and 15% reachable
OVERSHOOTS mainnet badly.** R tx-gap conn-duration (10-user sample, comparable
to the control's method):
- control (clumping_0p67_monitor, all-reachable, 16h): **1.52 min median**
- treatment (15% reachable, PARTIAL ~3h activity): **126.7 min median** (mean
  117, max 212); hidden user 143 min, reachable user 154 min.
- mainnet (Rucknium): 23 min.
So ~85x off the floor — and PAST mainnet's 23 min by ~5.5x (and partial, so the
full 16h would be even higher). **15% reachable is far too aggressive; the
fraction that matches 23 min is HIGHER (bigger pool).**

**MECHANISM — VERIFIED, and it corrects the v2-doc story.** It is NOT that the
sync-search dropper stops firing: it fires ~26/h in the treatment vs ~31/h
all-reachable, and TCP connections stay ~100s in BOTH (tx-carrying TCP median
100.4s here, ~100s all-reachable). The difference is PEER RECURRENCE in
Rucknium's tx-gap metric: with a tiny reachable pool (161), every node
reconnects to the SAME few reachable peers over and over, so the per-(ip,dir)
tx-exchange SPAN stretches across hours (→ 127 min) even though each TCP
connection is still ~100s. All-reachable (huge pool) → each ~100s connection is
to a DIFFERENT peer → per-peer span ≈ one connection ≈ 1.5 min. So the
1.5-vs-23-min gap is a POOL-SIZE → peer-recurrence effect in the metric, NOT TCP
(in)stability. (v2-doc §3's "101s rotation" is real but the duration metric
tracks recurrence, not raw rotation.)

**Mesh health ✅** at 1000 nodes / 85% hidden: height 188 at 48%, both sampled
nodes synced to 188, 0 process failures. Reachable nodes carry heavy inbound
(user-120: 609 INC tx-carrying conns). Clumping 25.4% single (treatment) vs
23.0% (control) — topology barely changes it (volume-bound, same load).

### Implications for next steps
- Don't run low-reachable at 16h LL1 again (3x-slow + heavy = >40h). For a
  fraction SWEEP: higher reachable fractions simulate FASTER (bigger pool, less
  reconnection) and likely bracket 23 min; and partial/short runs already read the
  conn-duration trend (signal is clear by ~3h activity).
- The tx-gap metric is WINDOW-SENSITIVE (recurrence accumulates over the
  observation window), so matching the absolute 23 min needs a consistent window
  vs Rucknium's — a real confound to handle when tuning the fraction.

## 5d. SUPERNODE test (sn_r15, 2026-06-19): 5 hubs (256/256) + 15% reachable, full 16h

archived_runs/20260619_135809_sn_r15. ALL CHECKS PASSED, 1006 online, 100% sync,
height 323. Three findings:

1. **Supernodes FIX the sim slowness.** 6h6m wall (2.6x sim:wall) vs uniform-15%'s
   ~40h (0.39x). The stable hubs absorb connections instead of the whole network
   thrashing on a tiny pool. Hub formation verified: supernode-1 relayed 413,941
   OUT-notifies across 689 distinct peers vs a hidden user's 34,037 across 68.
   (Caveat: regular reachable nodes have UNLIMITED inbound by default, so they
   too became high-degree — the supernode edge was mainly OUT-degree 256 vs 12.)
2. **Supernodes do NOT fix the connection-duration overshoot.** R tx-gap median
   = **150 min** (mean 214, max 710) — vs control 1.52 min, mainnet 23 min. Still
   ~6.5x OVER mainnet, ~100x the all-reachable control (fair full-16h vs full-16h
   comparison). So hubs are NOT the missing piece for conn-duration; the reachable
   FRACTION dominates and 15% overshoots with or without supernodes.
3. **NAT-heavy topology throttles throughput ~5x — CAUSE UNRESOLVED (not sync).**
   Only 3,254 tx created (all 200 users funded ~50 XMR, but ~12 tx each vs
   control's ~64). RULED OUT: daemon/wallet SYNC — every node incl. hidden
   user-001 reached height 331 in lockstep (≤0.3s apart at blocks 100/200/300);
   FUNDING amount (balances comparable); DAEMON LOAD (hidden users hold ~12 conns
   vs control's 16-32, i.e. LESS load → would predict more sends, not fewer).
   Leading UNVERIFIED candidate: the per-user send cadence is gated by how fast
   the prior tx gets MINED (change unlock), and tx propagation to the 5 miners
   may be slower through the congested reachable minority — NOT confirmed; would
   need tx submit→mined tracing. Clumping 91.3% single is the LOW-VOLUME
   consequence (volume-bound), whatever the throughput cause.

**Verdict:** reachable fraction is THE lever for connection duration
(100%→1.5min, 15%→150min; 23 min lies at some HIGHER fraction). Supernodes are
worth keeping for realism AND because they make runs FAST (6h) — i.e. they're
the vehicle for an efficient fraction sweep. Next: sweep reachable fractions
WITH supernodes (e.g. 0.5 / 0.7 / 0.85, ~6h each) to find the ~23-min point.

## 6. Open decisions (for the user)
- Target reachable fraction (recommend 15%; could sweep 10/15/20%).
- Scout-first (hand-built config) vs build the scenario knob first.
- Scale for the first A/B (300 cheap / 1000 definitive).
- Whether to ALSO set an explicit `in-peers` cap on reachable nodes (mainnet is
  effectively unlimited, so probably leave default — but a cap would force
  spillover and is worth considering for extreme fractions).

## Provenance
- Research: workflow wojuzgrtv (full output in the run's task file).
- monerod source: /home/lever65/monerosim_scale/monero (v0.18 series).
- The 101 s sync-search rotation (investigation 4 couldn't locate it in the p2p
  layer) IS confirmed: `once_a_time_seconds<101> m_sync_search_checker`,
  `cryptonote_protocol_handler.h:185` / `update_sync_search` — see
  `docs/20260610_rucknium_review_response_v2.md` §3.
