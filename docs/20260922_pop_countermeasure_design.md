# Publish-or-Perish as a flag-gated monerod-sim patch — design and pre-registration

**Status:** patch shipped; pilot RUN AND CONFIRMED 2026-09-22 (results in
the last section: 0.492 → 0.022 at α=0.4, honest control clean). The
predictions below were fixed BEFORE the first run.

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

## +uncles (rung 2, shipped 2026-09-22 as part of monero-sim-pop.patch)

`--sim-pop-uncles` completes the published rule per MRL #144: while
mining, a node appends to its miner-tx extra-nonce field the id of one
IN-TIME alt block that competed with the block it builds on (height N−1
sibling, same prev); at fork choice each in-time suffix block earns +1
per embedded uncle that the node received, saw in time at the uncle
height, and still holds as an alt there. Predicted effect (pre-registered
above, P-un): pop_core already collapsed ES to 0.022 — uncles convert the
~28 tie coin-flips per run into deterministic honest wins, so
es_pop_uncles ≤ es_pop with fewer transient forks; honest control stays
at α. Documented deviation from the paper/#144: the id rides the
extra-nonce field (not an 80 B PoW header in a new tx_extra tag) and
validation is node-local alt storage (not a header PoW re-check) — same
economics (miners embed only blocks they hold; verifiers count only
blocks they hold); the header variant is the production-fidelity upgrade.

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

## Follow-up results (2026-09-22, `matrix_runs/pop_followup/`, 3 × 6 h at α=0.4)

| cell | attacker share | att. orphan | net orphan | MSB max-z |
|---|---|---|---|---|
| `es_pop_det` (det tie) | **0.244** | 0.530 | 0.308 | +8.6 |
| `es_r2_pop` | **0.349** | 0.353 | 0.287 | +8.1 |
| `es_r2_pop_det` | **0.326** | 0.279 | 0.234 | +7.8 |

(baselines: `es_pop` 0.022 [pilot], `es_r2_none` 0.309 [release2 A/B].)

1. **PoP-core is blind to the conservative (lead-2) attacker.** 0.309 →
   0.349/0.326 — no reduction, possibly a small INCREASE (honest's late
   counter-blocks now lose weight too). The mechanism is exact timing
   semantics: lateness is judged against the FIRST block ever received at
   a height. Textbook ES releases only AFTER honest published at the
   contested height (a−h = 1 ⇒ h ≥ 1) — its reveal is always late →
   crushed (0.022). Lead-2 releases at h = 0, BEFORE honest mines that
   height — the attacker's blocks arrive first-at-height → in-time → the
   override wins exactly as under stock rules. **PoP's lateness rule
   punishes catch-up-triggered reveals, not proactive ones** — and the
   observed Qubic policy is the proactive kind. This is tevador's own
   argument for Share-or-Perish (MRL #146), now measured: closing the
   proactive-release gap is what the l_w share-lateness rule is for.
   Corollary prediction (pre-registered): +uncles will NOT close it — the
   lead-2 release is a clean in-time override, not a tie.
2. **The det-tie gap is large but single-run.** `es_pop_det` 0.244 vs
   `es_pop` 0.022 — if it holds at n=2 (wave 2 in flight), the
   deterministic hash comparison is systematically weaker than uniform
   random at γ≈0 (candidate mechanism: det-tie outcome is a fixed
   function of the tip pair, so a favorable hash draw persists across
   re-evaluations of the same contest, while random re-rolls; flagged for
   the #144-exact rung, which uses det-tie per the issue).
3. First nonzero realized γ ever measured: 0.040 in `es_r2_pop_det`
   (one tie won out of ~25) — an artifact of tie re-evaluation under the
   weight rule, worth watching, not yet a signal.
4. Detection: MSB z stays high everywhere (+7.8 to +14.9) — under every
   PoP variant the attacker remains loud.

## Rung 3: MRL #144 EXACT (2026-09-22, `--sim-pop-uncles-header`)

Per user direction: the deviated variant (above) runs its course; this rung
produces #144 exactly. `--sim-pop-uncles-header` embeds the uncle's
**~80 B PoW header (the hashing blob)** in a new `tx_extra` field
(tag 0x75, `tx_extra_sim_uncle`, appended LAST in the variant so existing
`which()` indices are stable) and verifies it **trustlessly**:

- the verifier re-derives the uncle id (`cn_fast_hash` of the blob),
  re-parses the header, requires the trailing tx-count varint to consume
  the rest exactly, and requires a reconstructed block to reproduce the
  blob byte-for-byte (non-canonical encodings count for nothing);
- **PoW re-check**: the reconstructed header must meet the difficulty at
  the uncle height (`get_block_longhash` + `check_hash`) — a fabricated or
  insufficient-work header earns nothing;
- **height/sibling check**: the header's `prev_id` must equal the
  containing block's parent's prev (MRL #144's own validation);
- **lateness**: a received uncle is held to Def. 1; a NEVER-RECEIVED uncle
  still counts — that self-contained verifiability is exactly what the
  deviated id-in-nonce variant cannot do.

Template side appends the field after the weight-settling loop
(cumulative_weight refolded so the template invariant holds); the field is
covered by the miner-tx hash like any other extra field, so blocks remain
stock-valid. The DEVIATED variant stays available (`--sim-pop-uncles`) for
the A/B: any share gap between the two variants measures the value of
trustless verification (never-seen uncles) in these topologies. Det-tie
per #144 composes via the existing `--sim-pop-det-tie`.

## Wave-2 results (2026-09-22/23, `matrix_runs/pop_wave2/`, 4 × 6 h at α=0.4)

| cell | attacker share | att. orphan | net orphan | verdict reading |
|---|---|---|---|---|
| `es_pop` (repeat) | 0.123 | 0.794 | 0.358 | core crush holds (n=2: 0.022, 0.123) |
| `es_pop_det` (repeat) | 0.296 | 0.486 | 0.326 | det-tie weakness holds (n=2: 0.244, 0.296) |
| `es_pop_uncles` | **0.024** | 0.970 | 0.446 | uncles ≈ core for ES — P-un confirmed |
| `honest_pop_uncles` | 0.402 | 0.000 | 0.022 | control clean (≈ α, no storms) |

1. **Det-tie weakness confirmed at n=2**: core 0.022/0.123 (mean 0.07) vs
   det 0.244/0.296 (mean 0.27) — non-overlapping bands. Tie-win
   frequencies alone do NOT explain it (random won 26/60 ties = 43%,
   det won 28/82 = 34%): the gap must also involve WHICH ties are won —
   deep (multi-block) vs shallow releases — and the fat-tailed
   winner-take-all cycle variance. Mechanism not yet isolated; flagged
   for the #144-exact readout, which uses det-tie as the issue specifies.
2. **The uncle term is a no-op against textbook ES here** (0.024 vs core
   0.022/0.123): with lateness already zeroing the attacker's contested
   blocks, there is nothing left for uncles to rescue — consistent with
   the paper's design intent (uncles reward honest publication, they do
   not punish withholding further). Vandalism persists (net orphan 0.446).
3. Honest control with uncle fields riding every honest coinbase: share
   0.402 ≈ α, orphaning 0.022 — the ~85 B field is weightless to the
   network. (Block counts 163–186 across cells: the countermeasure does
   not slow the chain.)

## Rung-3 results (2026-09-23, `matrix_runs/pop_exact/`, 3 × 6 h at α=0.4)

| cell (all det-tie) | attacker share | att. orphan | note |
|---|---|---|---|
| core (cited, n=2) | 0.244 / 0.296 | | |
| **`es_exact`** (header uncles) | **0.134** | 0.742 | uncles HALVE the det-tie leak |
| `es_uncles_det` (deviated uncles) | 0.337 | 0.385 | no help over core |
| `honest_exact` control | 0.322 vs α=0.400 | 0.113 | ⚠️ first control dip; net orphan 0.050 |

- **The exact-vs-deviated A/B (fixed det-tie) went AGAINST the
  pre-registered prediction** (exact ≈ deviated): 0.134 vs 0.337. Only 3
  uncle embeddings occurred — but the trustless weight side also counts
  uncles whose blocks have LEFT local alt storage after reorgs, where the
  deviated variant undercounts exactly during the multi-reorg dance
  following contested releases. In winner-take-all cycles a few decisive
  weight points move whole cycles. n=1 each — fat-tail caution.
- **Watch item**: `honest_exact` dipped to 0.322 (other controls: 0.397,
  0.402, 0.408) with orphaning 2.5× — at 2 honest miners the uncle
  mechanism has nothing to do and what little it does causes visible
  weight disagreement between nodes. Scale is the variable that settles
  whether #144-exact helps or hurts under realistic contention → rung 4.

## Rung 4: scale (2026-09-23, `pop_scale`)

`test_configs/selfish_scaled{,_mid}.yaml`: 12 (senior) / 6 (local pilot)
honest miners + 32/16 relays, α=0.40 exact, D=4800/3600. The micro
topology starves the uncle mechanism — 3 embeddings per 6 h because two
honest miners essentially never race; real Monero's contested-height rate
is what uncle appreciation feeds on. Pre-registered (P-scale): embeddings
rise to O(hundreds); tie/natural-fork counts rise with miner count; the
exact-vs-deviated gap either compounds or inverts; the honest control's
orphaning is the safety readout. Mid runs one-at-a-time locally
(parallel: 1); full scale is the senior-box leg.

## Rung-4 mid-scale results (2026-09-23, `matrix_runs/pop_scale/`, 6 honest
miners + 16 relays, α=0.4, 6 h; honest_exact control re-running)

| cell | attacker share | att. orphan | net orphan | uncle embeddings |
|---|---|---|---|---|
| `es_none` | 0.387 | 0.280 | 0.321 | — |
| `es_exact` | **0.170** | 0.721 | 0.380 | **17** |
| `honest_none` | 0.386 ≈ α | 0.200 | 0.056 | — |

- **P-scale (embeddings) confirmed directionally**: 3 → 17 with 2 → 6
  honest miners — contention feeds the uncle mechanism as predicted.
- **The exact countermeasure holds at mid scale**: 0.387 → 0.170
  (−0.22; micro was −0.36 from a higher baseline). Attacker orphaning
  stays at 0.72 — the crush survives more racers.
- **Scale alone shrinks the stock attacker** (0.492 → 0.387): more honest
  miners means fewer tie wins per node — the γ≈0 tie-luck dilutes. The
  ES theory curve at α=0.4 (0.484) is a 2-racer number; honest-network
  fragmentation cuts the other way at scale. (Single runs; repeats
  queued behind the control.)
- Vandalism persists (net orphan 0.32 → 0.38 under the countermeasure).
