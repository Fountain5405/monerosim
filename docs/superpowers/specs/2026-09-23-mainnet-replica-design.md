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
3. **Supernode and spy experiments.** Use the replica as the substrate:
   tx-origin inference by spies, hub removal, and the effect of /24
   deduplication and ban lists.

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
| heavy: hubs | `supernode-*` | 5 (0.5%) | out 256 / in 256, pinned reachable, always on | S1 0.77%, S2 0.29%; caps validated in S10 |
| heavy: seeds | auto `monero-seed-*` | 6 | fallback seeds, always on | S1: seeds are among the heavy nodes |
| mining pools | `miner-*` | 5 | stock peering, reachable, always on | S1: 9 of 28 heavy nodes were pools (see A3) |
| medium | `medium-{a,b,c}-*` | 125 (12.5%) | out-peers 16 / 32 / 64 | S1 12.5% |
| light users | `user-*` | 200 | default 12 out, wallet + tx agent | S10 lineage |
| light relays | `relay-*` | 645 | default | — |
| vantage points | `observer-*` | 20 | `monerod-hf` peerlist dump, pinned reachable, always on | S4 used 5 vantage points |
| **spies** | `spy-{a..f}-*` | 108 | see §4 | S6 "2024" preset |

- **Reachability.** `reachable_fraction: 0.13` over the 970 hash-assigned
  daemons gives 126, plus 30 pinned. That is about 15–16% of honest daemons
  (S10 target 15%).
- **Turnover.** 1 h on / 1 h off on all 970 non-pinned daemons, the combination
  that matched mainnet's median connection duration *and* its >6 h tail (S10).
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
| 2026 | 81.6% (S5) | ~14 dense + scattered tail (S7) | ~700 | P (R would need ~190 GB of RAM) |

**Variant R: real-node spies (works today, no code).**
- Stock `monerod`, `hide-my-port: false` (reachable, and exempt from turnover),
  in-peers unlimited, out-peers is the dial budget (starting value 32).
- They observe transactions for free: at `log-level: monitor`, spies log
  `NOTIFY_NEW_TRANSACTIONS` arrivals, which `ruck_analysis.r` already parses.
- They relay normally, which is not how real spies behave.

**Variant P: proxy spies (gap G3).**
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

The spy slot and peerlist shares are **calibration targets** for the spy dial
budget. S4 predates deduplication, so the outbound share should come out lower.
Showing that it does is itself a stage-3 result.

## 7. Gaps and new code

| # | Gap | Stage | Size | Needed for |
|---|---|---|---|---|
| G0 | **Seeded selection is not random.** Three sort-and-take selections in `src/agent/user_agents.rs` sort on the raw FNV-1a `seeded_hash`, whose high bits follow the name's leading bytes: `compute_unreachable_set` (~206), `compute_turnover_set` (~281) and `compute_node_impl_set` (~140). The chosen set is therefore contiguous by name or number. `seeded_unit` already applies a splitmix64 finaliser; the sorts do not. Fix: finalise the hash before sorting. **Breaking: it reshuffles every seeded assignment.** See §7a for the impact. | before stage 2 | small (Rust + tests) | any run with reachable_fraction < 1, turnover fraction < 1, or `node_implementations` |
| G1 | `analysis/topology_metrics.py`: the §6 metrics from logs and peerlist dumps | 2 | medium | validation |
| G2 | "Pinned reachable" also means "exempt from turnover". Add a per-agent opt-out so a class can be forced reachable **and** still turn over. | optional | small (Rust) | pinning medium nodes reachable (A2) |
| G3 | `agents/spy_proxy.py` (variant P) plus `levin_lib` parsing of transaction message 2002 | 1b / 3 | medium | 2026 preset; proxy fingerprint |
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
- **A2.** Medium nodes' reachability is hash-assigned like any relay. The
  literature does not say whether nodes with raised out-peers are reachable.
  If they are, pin them reachable once G2 exists.
- **A3.** Miners keep stock peering, so hashrate and hub roles stay separable.
  A variant makes the miners the hubs, as with pool front-ends.
- **D1 (open).** Transaction load. The parser calibration raises
  `transaction_interval` from 300 s to 2,596 s at 1,108 nodes (wallet-rpc
  safety). S10's connection-duration results used 300 s, and the Rucknium
  metric depends on transaction volume. Options: keep the calibrated value
  (safe, not comparable with S10), or pass `--no-safe-tx-interval` (comparable
  with S10, with wallet-overload risk).
- **D2 (open).** Default spy preset: 2024 (affordable with R) or 2026 (current,
  but needs G3).
- **D3 (open).** Stop time: 16 h (keeps the >6 h tail metric; about 50 h wall
  in S10 before spies) or 8 h (median-only).

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
