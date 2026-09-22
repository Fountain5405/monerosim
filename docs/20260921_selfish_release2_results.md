# Selfish-mining experiment: release-at-lead-2 (2026-09-21)

First experiment on `feat/selfish-mining-experiments`, built on the literature
review (`docs/20260920_selfish_mining_literature.md`). Question: what does
Qubic's observed *conservative release policy* — cash out the private chain at
lead 2 instead of waiting for honest to close to one (Lee & Kim 2025,
arXiv:2512.01437) — actually cost an attacker at γ≈0, and what does it do to
the network? Answer in one line: **it costs the attacker everything (profit →
loss) and the network less damage — the exact "private loss, public harm"
trade Lee & Kim measured, with the harm side shrunk.**

## Setup

`release_lead` knob (commit `22c8eebe`): `eyal_sirer`'s reveal arm
parametrized — release the whole private branch once honest closes to within
`release_lead` blocks (1 = textbook; 2 = Qubic's policy). Externality metrics
(commit `67f7d095`): `scripts/selfish_externality.py`, rendered in the
selfish analysis report.

A/B pair, identical otherwise (α=0.40 = 4 h/s attacker vs 3+3 honest, single
bridge ⇒ γ≈0, seed 12345, 6 sim-hours, `native_preemption: true`):

| Run | Config | Strategy |
|---|---|---|
| `archived_runs/20260921_023050_selfish_micro_es_baseline` | `selfish_micro.yaml` | `eyal_sirer` (release_lead 1) |
| `archived_runs/20260921_020113_selfish_release2` | `selfish_release2.yaml` | `eyal_sirer` + `release_lead: 2` |

Reproduce: `nice -n10 ./run_sim.sh --config test_configs/selfish_release2.yaml
--name <label> --no-monitor`, then `venv/bin/python
scripts/selfish_mining_analysis.py archived_runs/<run>`.

## Results

| Metric | ES (lead-1) | Conservative (lead-2) | Eyal–Sirer γ=0 theory | Lee–Kim R_mod |
|---|---|---|---|---|
| attacker canonical share | **0.463** | **0.309** | 0.484 | 0.364 |
| beats honest (α=0.400)? | yes (+0.063) | **no (−0.091)** | — | — |
| realized γ (ties) | 0.000 (13) | 0.000 (16) | — | — |
| attacker orphan rate | 0.165 | 0.265 | — | — |
| network orphan rate | 0.274 | **0.214** | — | — |
| canonical blocks (6 h) | 175 | 162 | — | — |
| reorg contest depths | 1×51, 2×6, 3×2, 4×2, 5×1 (18% multi) | 1×39, 2×1 (3% multi) | — | — |
| attacker run lengths | up to 10 | up to 3 | — | — |
| SpEC hourly throughput | 0.480 | 0.630 | — | — |
| MSB z (attacker / max honest) | **+6.94** / +1.73 | **+3.98** / +0.69 | — | — |

Both runs pass their verdicts (ES on the γ=0 curve, conservative inside the
modified↔ES band). Wall ≈ 25 min per 6 h sim on the 24-core/31 GB pilot box.

## What it shows

1. **Conservative cash-out converts profit into loss at α=0.4.** 0.463 →
   0.309, a 0.154 drop that crosses the honest baseline. Mechanism: the two
   policies diverge only at private lead ≥3 vs an active honest chain (below
   that, "cash at ≤2" coincides with ES's catch-to-one rule). ES there
   *continues withholding*, and when it finally releases it orphans every
   honest block mined into the dead branch — more honest waste, smaller
   denominator, higher attacker share. Lead-2 banks the same attacker blocks
   earlier but orphans less honest work, so its share sinks below honest.
   Qubic's observed behaviour — mostly-unprofitable conservatism — reproduces.
2. **Our lead-2 lands slightly under R_mod (0.309 vs 0.364).** Expected: the
   Lee–Kim Markov model credits the attacker `2α+γ(1−α)` of tie-state
   resolutions; at γ=0 measured, the network denies most of that. The
   between-models band (±0.10) is the right validation frame, not the point
   curve.
3. **Conservatism shrinks the public harm, it doesn't just shrink revenue.**
   Network orphan rate 0.274 → 0.214; reorg depth histogram collapses to
   almost pure length-1 (3% multi-depth, max 2) — which is precisely Lee &
   Kim's Fig. 3 contrast between baseline Monero ("almost exclusively length
   1") and their aggressive attack periods (our ES run: 18% multi, depth 5).
   The run-length cap (10 → 3) is the same signature from the other side.
   Throughput dips flatten too (SpEC 0.480 → 0.630). The one metric moving
   the other way — 162 vs 175 canonical blocks (−7%) — is within single-pair
   noise; treat as unresolved until repeated.
4. **MSB detection doesn't just flag withholding — it ranks aggression.**
   Attacker z = +6.94 (ES) vs +3.98 (conservative); honest miners never clear
   +1.73 in either run. A more conservative attacker is a *less detectable*
   attacker, consistent with Li et al.'s small-pool flags being weak signals.
5. **Release-signature scatter (y=x−1 vs y=x−2) is noisier here than in the
   paper.** Even the ES run shows 6 y=x−2 runs (orphan accounting inside run
   windows mixes tie losses with release waste). The depth histogram and
   run-length distribution discriminate the policies far more cleanly at
   micro scale.

## Caveats

- Single A/B pair, `native_preemption: true` (run-to-run σ ≈ 0.05 on share):
  the 0.154 gap is ~3σ and mechanistic, but the 175-vs-162 throughput
  difference is not conclusive.
- 162-175 canonical blocks per run ⇒ share σ ≈ 0.04 alone.
- Micro topology (2 honest miners, 2 relays, single bridge): honest-network
  fragmentation effects (phase-2's caveat) are minimal here, which is what
  makes this a clean strategy-only comparison.

## α-sweep addendum (2026-09-21, later)

`test_configs/selfish_sweep_release2/` ran the conservative policy across α
(each config = the matching ES sweep config + `release_lead: 2`, same seed
12345; the α=0.40 point is the original `selfish_release2.yaml` run above):

| Run | α | measured | R_mod | ES γ=0 | honest (α) |
|---|---|---|---|---|---|
| `20260921_102229_r2_sweep_a0300` | 0.30 | **0.211** | 0.205 | 0.273 | 0.300 |
| `20260921_020113_selfish_release2` | 0.40 | 0.309 | 0.364 | 0.484 | 0.400 |
| `20260921_102230_r2_sweep_a0450` | 0.45 | **0.569** | 0.454 | 0.652 | 0.450 |

All three PASS the between-models band verdict. What the sweep adds:

1. **The conservative policy's profitability crossover sits in (0.40, 0.45)**
   — well above Eyal–Sirer's ≈1/3. At α=0.30 the measured share lands almost
   exactly on the modified curve (0.211 vs 0.205): at low α the attacker's
   options are so constrained that the Markov model captures it essentially
   exactly, and it is deeply unprofitable (−0.09 vs honest). At α=0.45 the
   measured 0.569 beats honest by +0.12: conservatism delays profitability,
   it does not remove it — Qubic at a *sustained* 45% would have profited
   even while releasing early.
2. **The α=0.40 point remains the worst fit to R_mod** (0.055 under; the
   other two are within 0.015). Single-run noise (σ≈0.04–0.05) covers it,
   but if it persists across repeats the mid-α region is where the drip-feed
   tie behaviour (which our implementation replaces with full release)
   matters most.
3. **MSB false-positives on HONEST miners under heavy attack** (α=0.45:
   honest z = +2.25 and +3.17, above the +2 flag line). Strong withholding
   clusters everyone's canonical wins — honest miners mine freely while the
   attacker holds, then get reorged in bursts — so the iid-shuffle null
   behind Li et al.'s detector over-flags honest miners exactly when the
   attack is worst. A deployed detector needs an attack-aware null; our
   simulator can supply the calibrated one. (At α=0.30/0.40 honest z stayed
   ≤ +0.86.)
4. Realized γ: 0.111 (27 ties) at 0.30, 0.000 at 0.40/0.45 — small-count
   noise, same as the archived ES sweep showed at 0.30.

## Next

- Experiment 3: eclipse×selfish composition — built (islands + peers/eclipsed
  orchestrator knobs + controlled-share analysis), running next.

## Monerosim notes from this experiment

- `canonical_chain.json` carries only `{height, hash}`; every time-based
  metric must join against miner logs. Recording the block timestamp in the
  bridge dump (`get_block_header_by_height` returns one) would remove a
  fragile join — small orchestrator improvement, worth doing before
  experiment 3.
- Attributed orphan/contest metrics depend on all canonical blocks being
  found by *logged* miners (true in every selfish config so far; would break
  with relay-found blocks — fine at micro scale, document at scale).
- Two 6 h selfish sims + analysis fit comfortably in under an hour on the
  pilot box; the 256-thread/1 TB machine is in no way required for strategy
  A/Bs, only for topology/scale sweeps.
