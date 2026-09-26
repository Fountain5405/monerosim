# Mainnet replica — design

**Date:** 2026-09-23 · **Branch:** `feat/mainnet-replica` · **Status:** draft for review
**Numbers:** `docs/20260923_mainnet_topology_literature.md` (sources S1–S10)
**Draft scenario:** `test_configs/mainnet_replica.scenario.yaml` (expanded and
generated, **not run**. No simulations run on the shared box for this work.)

## 1. Goal and staging

Build a scaled-down replica of the Monero mainnet P2P network in monerosim, in
three stages. Each stage gets its own plan.

1. **Baseline replica (this spec).** A scenario file whose population
   (node classes, counts, peer caps, reachability, uptime, placement, spies)
   is sourced from the literature. The topology is not imposed: it
   **emerges** from real monerod peering.
2. **Validation.** Run it and compare scale-free topology metrics against the
   literature (§6). Calibrate the knobs the literature leaves open, such as
   the spy dial budget.
3. **Experiments on the replica**, in this order (decided 2026-09-23):
   1. **Tx-origin inference by spies.** Spies log every transaction
      announcement (real-node spies already do, via monitor logs); the per-user
      ledger gives ground truth; measure how often first-seen heuristics find the
      originator, and how Dandelion++, the NAT majority, hub concentration, /24
      dedup and the ban list move that number. Sets the proxy-spy agent's first
      job: observe, don't relay.
   2. **Hub dependence.** Remove or eclipse the pool hubs mid-run; compare
      partition and propagation against S2's "14 hubs removed → −20%".
   3. **Countermeasure effectiveness.** Same runs with and without dedup, the
      ban list and peerlist flooding; measure spy footprint.
   4. **Eclipse and selfish mining** re-run on the replica instead of the uniform
      topology.

**Decisions so far** (user, 2026-09-23):
- Staged delivery.
- Scaling is parametric, with ratios preserved.
- Spies go into the stage-1 profile, and the spy implementation must be
  swappable: real-node spies versus proxy spies, alone or mixed.
- The deliverable is a **scenario file** using existing knobs, with new code
  only where a gap forces it.

## 2. Why a population model, not an edge list

In monerosim, the GML supplies only latency, bandwidth and AS/region structure.
The peering graph is formed by monerod itself (S10 §1). No published edge list
exists: S1–S3 *infer* edges with 69–98% accuracy. Replaying one through
`add-exclusive-node` would also freeze the rotation, turnover and
connection-duration dynamics that S10 validated.

So the replica fixes **who exists and how each class is configured**, and
validation checks that the graph monerod builds has mainnet's shape.

## 3. Populations (N = 1,000 honest daemons)

| Class | Scenario group | Count | Config | Source |
|---|---|---|---|---|
| heavy: pool hubs | `miner-*` | 5 | **native mining** (10 h/s each; D0 = 6,000), out 256 / in 256, pinned reachable, always on | S1: 9 of 28 heavy nodes were pools, the largest hubs; caps validated in S10 (decided 2026-09-23, replaces the separate `supernode-*` group) |
| heavy: seeds | auto `monero-seed-*` | 6 | fallback seeds, unlimited inbound, always on; become hubs naturally | S1: seeds are among the heavy nodes; S2's 14 hubs include public seeds |
| medium | `medium-{a,b,c}-*` | 125 (12.5%) | out-peers 16 / 32 / 64, **pinned reachable, still turning over** (needs G2) | S1 12.5%; S11's "production-recommended" 64 out |
| light users | `user-*` | 200 | default 12 out, wallet + tx agent | S10 lineage |
| light relays | `relay-*` | 640 | default | — |
| vantage points | `observer-*` | 20 | `monerod-hf` peerlist dump, pinned reachable, always on | S4 used 5 vantage points |
| **spies** | `spy-{a..f}-*` | 108 | see §4 | S6 "2024" preset |

- **Reachability.** 150 pinned reachable (5 miners, 125 medium, 20 observers)
  plus `reachable_fraction: 0.01` over the 840 hash-assigned users/relays (~8)
  gives ~158 of 996 honest daemons, about 16% (S10 target 15%).
- **Turnover.** 1 h on / 1 h off on all users, relays and medium nodes, the
  combination that matched mainnet's median connection duration *and* its >6 h
  tail (S10). Medium nodes are pinned reachable but still cycle (G2).
- **Mining.** `general.mining.mode: native` (real RandomX, sleep-throttled),
  hashrate as literal h/s. Difficulty warm-up is removed by the chain snapshot in
  `2026-09-23-difficulty-preload-design.md`; the replica is **blocked on that
  snapshot** for native runs.
- **Honest prefix sharing (decided in stage 1; numbers from S13, our
  2026-09-23 crawl).** Honest reachable nodes share /24s: the densest 12% of
  /24s hold 30.8% of them, ~3.3 per /24 (S11's 55%-of-BGP-prefixes was the
  coarser, 2022 view). One GML node is one /24 in the sim, so
  `network.distribution.prefix_sharing: {fraction: 0.31, per_prefix: 3}` moves
  that fraction of hash-selected honest daemons onto shared GML nodes,
  `per_prefix` per node, inside their region. Spies keep their own pinned
  nodes. Gap G5 (built).
- **DNS bootstrap** is already mainnet-faithful and needs nothing: the in-sim DNS
  server answers `seeds.moneroseeds.*` with the seed hosts, the six fallback IPs
  are in-sim hosts, and monerod runs its stock resolution path (verified
  read-only 2026-09-23; `agents/dns_server.py`, `src/.../fallback_seeds.rs`).
- **Scaling rules** (used when producing other N):
  - Class shares stay fixed.
  - Hub caps ≈ 0.25·N per direction (S2's 82% hub coverage).
  - Medium out-peers stay within (12, 0.07·N], since S1's 250 of 3,626 is
    about 7%. At the N≈100 smoke scale this range is empty, so the medium class
    only exercises plumbing there.
  - The light default of 12 is a protocol constant and does **not** scale. This
    is the one unavoidable scale artefact: a light node sees 1.2% of a
    1,000-node network against about 0.07% of mainnet's.

## 4. Spies: swappable implementations

**Placement (both variants).**
- One GML node is one /24 (`src/ip/as_manager.rs`). Each spy subnet is therefore
  a scenario group pinned with `topology_node: <id>`. This needs no code:
  per-group keys already pass through `scenario_parser`.
- Spies use North America nodes 828–833. Weighted placement fills regions from
  their first node, so honest NA nodes occupy about 0–650 and spy /24s stay
  spy-only. The dry generation verified this: 6 spy /24s, zero honest
  co-tenants.
- monerod v0.18.5.1's /24 deduplication (S8/S9) then applies exactly as on
  mainnet.

**Presets**, swapped by editing the spy groups:

| Preset | Spy share of reachable IPs | /24 shape | Spies at N=1000 | Variant needed |
|---|---|---|---|---|
| 2024 (default) | 40% (S6) | 6 dense | 108 | R or P |
| 2025 | 14.7% (S4) | 7 dense | ~28 | R or P |
| 2026-09 | 73.7% of reachable (S13, our crawl; S5 saw 81.6% in Feb) | 63 dense /24s, ~210 IPs each, 99.6% one ASN | ~440 | P (R would need ~120 GB of RAM) |

**Variant R: real-node spies (works today, no code).**
- Stock `monerod`, `hide-my-port: false` (reachable, and exempt from turnover),
  in-peers unlimited, out-peers is the dial budget (starting value 32).
- They observe transactions for free: at `log-level: monitor`, spies log
  `NOTIFY_NEW_TRANSACTIONS` arrivals, which `ruck_analysis.r` already parses.
- They relay normally, which is not how real spies behave.

**Variant P: proxy spies (`agents.spy_proxy`, built 2026-09-23).**
- A few real backend monerods sit behind many lightweight front-end IPs (S7).
- Built on the eclipse fake-peer stack (`agents/eclipse_fakepeer.py`,
  `levin_lib.py`; about 40 MB per host, proven at 1,000 hosts).
- Front-end behaviour:
  - Answer handshake, timed sync and ping.
  - Report the **backend's real chain state** rather than the genesis trick.
  - Return a different peer ID on ping than in the handshake (S5 fingerprint).
  - Advertise fleet plus backend peerlist.
  - Dial out within a budget.
  - Log every received transaction message (tx hash, peer, time).
  - Optionally forward to the backend.
- Mixed R+P runs are just both group kinds in one file.

## 5. Placement of honest nodes

- Use the 5,000-node GML. The dry generation gave 1,006 distinct honest /24s
  for 1,009 non-spy hosts, so dedup coupling between honest nodes is
  negligible.
- Region weights are NA/EU/Asia/Oceania = 58/30/9/3 (S1-derived, low
  confidence; latency is a second-order effect).

## 6. Validation targets (stage 2)

The simulator gives ground-truth edges while the literature gives inferred
ones, so we compare shapes and ratios (literature §7).

| Metric | Target | Source | Measured from |
|---|---|---|---|
| Outbound-degree class shares, light / medium / heavy | 86.8 / 12.5 / 0.7% | S1 | monitor-level connection logs (`conn_matrix.py` windows) |
| Connection share held by the top 13% of nodes | ~83% | S1 | same |
| Hub coverage: share of nodes adjacent to a hub | ~82% | S2 | same |
| Hub neighbour overlap | >91% | S2 | same |
| Degree assortativity | ≈ −0.28 | S3 | same |
| Inbound per reachable honest node | 50–100 | S10 | same |
| Median connection duration / >6 h share OUT, INC | ~23 min / ~1.5%, ~0% | S10 | `ruck_analysis_turnover.r` |
| Spy share of honest inbound / outbound slots | ~20% / ≤15% (lower post-dedup) | S4 | observer connection logs |
| Spy share of peerlist entries | ~17% | S4 | observer `peerlist_dump.jsonl` |
| Modularity (community structure) | ~0.09 greedy, ~0 random-walk: none | S11 | same connection graph |

The spy slot and peerlist shares are **calibration targets** for the spy dial
budget. S4 predates deduplication, so the outbound share should come out lower.
Showing that it does is itself a stage-3 result.

## 7. Gaps and new code

| # | Gap | Stage | Size | Needed for |
|---|---|---|---|---|
| G0 | **Seeded selection is not random.** Three sort-and-take selections in `src/agent/user_agents.rs` sort on the raw FNV-1a `seeded_hash`, whose high bits follow the name's leading bytes: `compute_unreachable_set` (~206), `compute_turnover_set` (~281) and `compute_node_impl_set` (~140). The chosen set is therefore contiguous by name or number. `seeded_unit` already applies a splitmix64 finaliser; the sorts do not. Fix: finalise the hash before sorting. **Breaking: it reshuffles every seeded assignment.** See §7a for the impact. | before stage 2 | small (Rust + tests) | any run with reachable_fraction < 1, turnover fraction < 1, or `node_implementations` |
| G1 | `analysis/topology_metrics.py`: the §6 metrics from logs and peerlist dumps | 2 | medium | validation |
| G2 | "Pinned reachable" also means "exempt from turnover". Add a per-agent `turnover: true` override so a class can be forced reachable **and** still cycle. | **1** (decided) | small (Rust) | medium nodes reachable and churning |
| G3 | `agents/spy_proxy.py` (variant P) — **built 2026-09-23**: Levin responder on the eclipse stack, reports the backend's real chain state, peer-id mismatch on ping (S5) + support-flag knob (S4/S6) via a small `InjectorConfig` addition, fleet+backend peerlist, dial budget. Tests in `agents/test_spy_proxy.py`. **Follow-up:** proxy-side tx observation needs cryptonote-handshake participation (levin_lib is admin-only); real-node spies carry the tx feed for now. Oversized-peerlist fingerprint gated pending the 250-entry rejection check. | done / 3 | — | 2026 preset; proxy fingerprint |
| G5 | Honest prefix-sharing knob `network.distribution.prefix_sharing` (see §3). **Built** (deb529a1); defaults re-derived from S13. | done | — | mainnet-like /24 co-location of honest nodes |
| G6 | Chain snapshot preload for native mining (own spec). | **1** | medium | any native-mining replica run |
| G4 | Safety: generation outside `run_sim.sh` deletes the default `/tmp/monerosim_shared`, which on this box belongs to **user1**. The delete failed on permissions and nothing was lost. Dry generation must set `shared_dir` and `daemon_data_dir`. Refusing to delete a path we don't own should be the default. | now | small (Rust) | safe dry-runs on a shared box |

### 7a. G0 impact, measured by generating configs with the real binary (no runs)

| Config | Reachable per decile of the numeric suffix (expected ~uniform) |
|---|---|
| `topo1k_supernodes` `--reachable 0.15`: relays (n=790, 118 reachable) | `[0,0,0,0,0,0,0,0,39,79]`: exactly relay-633..790 |
| same, users (n=200, 30 reachable) | `[0,0,0,0,0,1,9,0,1,19]` |
| `mainnet_replica`: medium-a / medium-b / medium-c / relay | 42/42, 0/42, 41/41, 17/645 |
| `mainnet_replica_smoke`: relay / medium-a | 0/62, 10/12 |

A Python replica using a splitmix64 finaliser gives uniform deciles
(`[14,12,18,13,9,9,9,13,15,6]` for the topo1k relays).

**Implications for earlier results. These are flags, not conclusions; nothing
has been re-run.**
- The published topology study (`docs/20260620_network_topology_study.md`,
  the reachable sweep and the turnover result) used a reachable set made of
  the *highest-numbered* relays. Placement also follows agent order, so those
  relays probably sat in a contiguous run of GML nodes (possibly the last
  regions). The pool **size** was correct, and S10 identifies pool size as the
  driver of the connection-duration metric. The **latency geography** of the
  reachable pool was not random.
- Turnover used `fraction: 1.0` in the published runs, so no bias there.
  Fractions < 1 would have been clustered.
- The cuprate A/B (`docs/20260724_cuprate_scale_experiment.md`, half the
  relays cuprate) used `compute_node_impl_set`. Its cuprate nodes were
  therefore probably a contiguous id block with contiguous placement. The
  propagation-speed and "mixing is random" findings should be re-checked for
  regional confounding.

## 8. Assumptions and open decisions

- **A1.** The replica models the honest network plus spies only; the items in
  literature §6 (pruning, Tor/I2P, IPv6, version mix, remote-node wallets) are
  out of scope, each for the reason given there.
- **A2 (decided 2026-09-23).** Medium nodes are pinned reachable and still turn
  over (G2). Rationale: raising `out-peers` is an operator act, and those
  operators run always-on public nodes (S5: ~3,000 honest reachable, 30% with
  public RPC; S1: medium nodes skew to hosting countries).
- **A3 (decided 2026-09-23).** Miners **are** the hubs (pool front-ends, S1),
  with native mining. Hub and hashrate roles are therefore coupled; a hub
  experiment in stage 3 is also a hashrate experiment, which is how mainnet is.
- **D1 (decided 2026-09-23, no user preference; recommendation taken).**
  Transaction load stays at **300 s** so results are comparable with S10.
  Expand with `--no-safe-tx-interval`: the parser calibration would otherwise
  raise it to 2,596 s at 1,108 nodes, and the Rucknium connection metric is
  volume-sensitive. Accepts some wallet-rpc overload risk.
- **D2 (decided).** Default spy preset is **2024** (40%, 6 dense /24s, variant
  R): runnable today. The 2026 preset waits for G3.
- **D3 (decided).** Stop time **16 h**, to keep the >6 h tail metric
  (about 50 h wall in S10 before spies; expect more).

## 9. Verification done without simulations

1. `scenario_parser.py` expansion: 1,110 agents, bootstrap ends at 4 h,
   activity starts at 5 h.
2. `monerosim` generation into a scratch directory with isolated
   `shared_dir`/`daemon_data_dir`: exit 0, 1,117 hosts.
3. Checks on the generated config:
   - 6 spy /24s, each spy-only.
   - 844 firewalled hosts, so reachable = 0.13 × 970.
   - 970 turnover nodes; pinned classes are exempt.
   - 1,006 honest /24s.
   - This check surfaced G0.
4. The smoke variant also generates: 121 hosts, 2 spy /24s, 94 turnover nodes.
   It shows G0 as well (0 of 62 relays reachable).
5. The recipe, for reuse: `scenario_parser.py X -o E --no-calibrate`, insert
   `shared_dir` and `daemon_data_dir` pointing at a scratch directory into E's
   `general:`, then `monerosim --config E --output <scratch>`. **Never generate
   without step 2 on a shared box** (G4).

## 10. Run plan (when a box is available)

1. Fix G0 (and G4). Regenerate and confirm the per-group reachable shares are
   close to 13%.
2. Smoke run at about 100 honest nodes plus 12 spies (2 /24s), about 3 h
   simulated. Checks: mesh health, spies connected, dumps written.
3. Full run of this scenario. Then G1 metrics against §6, and calibrate the spy
   out-peers.
4. Stage 3 planning.
