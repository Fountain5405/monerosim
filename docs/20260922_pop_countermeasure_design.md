# Publish-or-Perish as a flag-gated monerod-sim patch — design and pre-registration

**Status:** patch `patches/monero-sim-pop.patch` built and compiling clean
(2026-09-22); experiments not yet run. This document fixes the mechanism
mapping and the predictions BEFORE the first countermeasure run, so the
outcome can't be fit after the fact.

## Sources

- **Published rule:** Zhang & Preneel, *Publish or Perish: A
  Backward-Compatible Defense against Selfish Mining in Bitcoin*,
  CT-RSA 2017. Weighted fork-resolving policy: Def. 1 in-time/late blocks,
  Def. 2 uncles, Def. 3 chain weight = in-time blocks + embedded in-time
  uncles, k-block longest-chain fail-safe, uniform-random tie-break.
- **Monero adaptation:** MRL #144 (tevador, 2025-08-27): k=3, D=5 s,
  relative-time lateness only, one N−1 uncle in coinbase `tx_extra`
  (weight-only, no reward/difficulty effect), **deterministic** tie-break.
- **Successor (not in this patch):** MRL #146 Share-or-Perish — workshares
  at 1/w difficulty, l_b/l_w lateness pair, k·w=48 window. Full digest:
  `docs/20260920_selfish_mining_literature.md` Part F.

## What the patch implements (and deliberately does not)

`--sim-publish-or-perish` (+ `--sim-pop-k` [3], `--sim-pop-delay-s` [5],
`--sim-pop-det-tie` [false]) on `monerod-sim`:

1. **Receive-time ledger** (`Blockchain::m_sim_recv`): every block id →
   first local receive time in ms, recorded in `add_new_block` — the one
   funnel through which P2P, RPC-submitted, and miner-found blocks all
   pass. Shadow virtualizes the clock, so these are sim-milliseconds.
2. **Def. 1 lateness** evaluated at fork-choice time, per node: a block is
   in time iff it was received ≤ D after the earliest block this node ever
   received at the same height (min over main + all stored alt blocks at
   that height — heights of both candidate chains are known at decision
   time, so no extra bookkeeping hook is needed).
3. **The weighted fork-resolving policy** replaces the raw
   cumulative-difficulty reorg comparison in
   `Blockchain::handle_alternative_block`: (rule 1) a competing chain ≥ k
   blocks longer always switches (partition recovery); (rule 2) otherwise
   the larger in-time weight over the divergent suffixes switches;
   (rule 3) exact-weight ties resolve uniformly at random (paper) or by
   tip-hash comparison (`--sim-pop-det-tie`, MRL #144). Every decision
   logs a grep-able `SIM-PoP:` line with both weights.
4. **NOT implemented:** uncle embedding (paper Def. 2/3's second term).
   This patch measures the fork-choice CORE. A later `+uncles` patch
   completes published PoP; the difference between the two is itself a
   measurement (how much of PoP's published benefit rides on uncles).

Honest-network deployment is modeled by setting the flag on honest
agents' `daemon_options`; the attacker's covert bridge keeps stock rules
(an attacker does not upgrade). Off by default; absent the flag the code
path is byte-for-byte stock.

## Why the mechanism should bite here (hand derivation, pre-registered)

Stock Monero at γ≈0, ES reveal at lead 2 vs honest catch-up 1: the
private chain is 2 blocks long vs the honest branch's 1 → cumulative
difficulty strictly greater → the honest node reorgs and the attacker
banks 2 blocks. Under PoP-core on an honest node: the private block at
the contested height f+1 was first seen (honest's version) one honest
block-finding time earlier ≫ D=5 s → **late, weight 0**; the private
block at f+2 is the first ever seen at that height → in time, weight 1.
Honest branch weight: 1. **Tie 1=1** → coin flip (random tie) instead of
a guaranteed attacker win; if honest had already found f+2, the attacker
outright loses (1 vs 2). The deep-release case is stronger: a withheld
chain released after honest advanced several heights has every
contested-height block late — near-total discounting, bounded only by
rule 1 (the attacker must be ≥ k+ blocks longer to force through).

Counter-pressure: ties that a γ≈0 network's first-seen rule makes the
attacker ALWAYS lose now flip 50/50 — random tie-breaking transfers some
lost ties to the attacker. The net sign at Monero speeds is an empirical
question; that is precisely the measurement.

## Pre-registered predictions (E4, before any run)

- **P1 (direction):** with PoP-core on honest miners at α=0.4 vs the
  same-seed no-countermeasure baseline, the attacker's canonical share
  drops by ≥ 0.05 absolute. Mechanism: reveals at contested heights
  become ties/losses instead of guaranteed wins.
- **P2 (magnitude ordering):** drop(pop-core, random tie) <
  drop(pop-core + det tie) is NOT assumed — det-tie may preserve more
  network consistency; we record both.
- **P3 (honest control):** PoP-core on honest miners with
  `strategy: honest` leaves shares ≈ α (within the ±0.10 band) and shows
  no reorg storms: all honest blocks are in time (propagation ≪ D), so
  weight = length = stock behavior except at natural forks.
- **P4 (falsifier for the patch itself):** the honest control showing
  elevated orphaning or stalls means an implementation defect (e.g.
  mis-signed lateness on the node's own mined blocks), not a PoP property
  — the node that MINES a block records its receive time at submission
  (earliest possible), so self-mined blocks are never late by
  construction.
- **P5:** attacker reaction (200 ms ticks) ≪ D=5 s, so SHORT single-block
  races stay in-time for the attacker — PoP-core's bite concentrates on
  multi-block reveals. If measured shares barely move at α=0.4 while
  `SIM-PoP: TIE` lines are frequent, the tie-flip offset (P1's
  counter-pressure) is dominating — an honest negative result worth
  reporting, and the case for the uncles patch.

## Planned runs (E4 ladder)

1. ~~Pipeline smoke~~ ✅ done 2026-09-22 (`matrix_runs/pipeline_smoke/`,
   4 × 1 h, 0 failures): matrix path validated end-to-end — honest control
   share 0.409 ≈ α=0.4 with all verdicts PASS through the runner; the two
   honest cells are statistically identical, consistent with relay being a
   no-op without withholding. (This smoke exercised the daemon_options
   overlay + preflight via the *relay* flag; the PoP overlay's end-to-end
   cell is `honest_pop`/`es_pop` below.)
2. Pilot A/B: `strategy × countermeasure` at α=0.4, 6 h, same seed
   (P1) — `test_configs/matrix/pop_pilot.yaml` (4 cells: es_none/es_pop +
   honest_none/honest_pop).
3. Full matrix on senior: strategy {es, es_r2, honest} × countermeasure
   {none, pop, pop_det} × α {0.30, 0.40, 0.45} + later SoP.

## Pilot results (2026-09-22, `matrix_runs/pop_pilot/`, 4 × 6 h at α=0.4)

| cell | attacker share | att. orphan | net orphan | MSB max-z | canonical blocks | PoP decisions |
|---|---|---|---|---|---|---|
| `es_none` | 0.492 (ES curve 0.484, all verdicts PASS) | 0.174 | 0.312 | +7.9 | 183 | — |
| `es_pop` | **0.022** | **0.973** | **0.447** | +14.9 | 184 | 77 (73 KEEP / 4 SWITCH / 28 ties) |
| `honest_none` | 0.397 | 0.027 | 0.021 | +0.1 | 184 | — |
| `honest_pop` | 0.408 | 0.024 | 0.020 | +2.0 | 196 | 15 |

- **P1 CONFIRMED at ~10× the pre-registered threshold**: 0.492 → 0.022
  (predicted drop ≥ 0.05, measured 0.47). The attacker still mines (its
  orphan rate 0.973 = it found ~183 blocks and banked 4) but every
  withheld-then-released chain loses the weight race at the honest nodes:
  73 of 77 PoP decisions KEEP the honest branch. P5's counter-pressure
  (random-tie flips favoring the attacker at γ=0) did not materialize
  net — lateness discounting dominates at Monero propagation speeds.
- **P3/P4 clean**: `honest_pop` sits at α (0.408 vs 0.400), orphan rates
  indistinguishable from `honest_none` (0.020–0.027 vs 0.021), canonical
  throughput unchanged (196 vs 184 blocks — no reorg storms, no
  self-harm). The patch is not breaking mining generally.
- **New finding — the harm/profit asymmetry inverts into pure
  vandalism**: under PoP the attack becomes UNPROFITABLE (0.022 < α) but
  the network damage RISES (orphan rate 0.312 → 0.447): withholding still
  orphans honest work even when it can never pay. A deployed PoP removes
  the attacker's incentive but not the DoS; MSB detectability also RISES
  (+7.9 → +14.9). Killing the profit and surviving the vandalism are
  separate problems.
- Verdict semantics: `es_pop` FAILs its (attack-shaped) verdicts because
  it lands far BELOW the ES curve — that is the countermeasure working,
  not a defect. `honest_none` FAILs the above-α check by 0.003 — an
  honest actor is not supposed to clear it.

Runs: `20260922_140138_pop_pilot__es_none`, `__es_pop`,
`20260922_144601_pop_pilot__honest_none`, `__honest_pop` (commit
`5751f7df`, monerod-sim 5-patch build 2026-09-22T13:05Z). Caveats:
single 6 h runs (σ≈0.05); the A/B gap (0.47) is ~9σ — not noise. Next
rung: the +uncles patch (isolates the uncle term the paper credits),
det-tie axis, and the full strategy × countermeasure × α matrix on
senior.
