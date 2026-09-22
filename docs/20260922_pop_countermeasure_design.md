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
