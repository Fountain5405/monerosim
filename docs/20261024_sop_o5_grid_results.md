# SoP o5 attacker grid, round 1 (2026-10-24)

The objects-give-up attacker (`give_up_objects 5`, commit `23162f3a`) under
the MRL #146 2026-10-20 rule, measured on 12 daemons over 72 simulated hours
per cell, two draws per cell. Round 1 ran on the new lane boxes (box80/box82:
Ryzen 9 3900X, box81: Ryzen 5 5600G, 16 GB each, two lanes per box); specs
`sop_v4_o5_alpha_72h` and `sop_v4_o5_noown_72h` (commit `ca97daf9`).
Reference cell: `sop_v4_o5_72h` a045, 0.209/0.210 (2026-10-23,
docs/20261023_sop_scale_n300_smoke.md s3.1). Archives: the pool
`/spinny/readfrom/20261024_monerosim_research_effort/<box>/` on 192.168.1.33.

## 1. Results

| cell | alpha | own tip shares counted | share, draw 1 | share, draw 2 | attacker orphan rate | reveals (delivered) | stuck | gate |
|---|---|---|---|---|---|---|---|---|
| share_sop2_a033 | 0.33 | yes | 0.000 | 0.002 | 1.00 / 0.996 | 3 (0), 2 (1) | 0 h | WARN*, PASS |
| share_sop2_a040 | 0.40 | yes | 0.055 | 0.059 | 0.91 / 0.91 | 43 (26), 37 (29) | 0 h | PASS, PASS |
| share_sop2_a045 (ref) | 0.45 | yes | 0.209 | 0.210 | | 174 (110), 160 (103) | 0 h | PASS, PASS |
| share_sop2_noown_a045 | 0.45 | no | 0.288 | 0.279 | 0.61 / 0.62 | 138 (136), 133 (131) | 0 h | PASS, PASS |

Honest mining's share is alpha. Oracle: 0 mismatches on all 12 nodes in
every cell. Stuck time (`scripts/selfish_mining/sop_stuck_time.py`, gaps
over 2 h with no concession or reveal): 0 h everywhere, so the objects
give-up removed the stranding of the block-rule runs (17-27 h per 72 h).

*The a033 draw 1 check gate FAILed on "A3 delivered if reveals > 0": 3
reveals, all rejected by the share-aware bridge. With reveals in the single
digits that test is noise (draw 2 had 2 reveals, 1 delivered, and passed);
read it as WARN. The gate should skip the A3 test below ~10 reveals.

## 2. Reading

1. **Below alpha 0.45 this attacker loses almost everything.** At 0.33 it
   orphans every block it mines and reveals two or three times in 72 h; at
   0.40 it keeps 0.055-0.059 of the blocks against 0.40 for honest mining.
   The curve (0.000, 0.057, 0.210 at 0.33, 0.40, 0.45) bends up steeply; the
   crossing with honest mining, if any, is near a majority (round 2 measures
   0.48 and 0.50).
2. **Not counting its own pending tip shares makes the attacker better, not
   worse.** With `count_own_tip_shares false` the reveal test matches what
   the bridge will accept ("fork choice runs only on a new block or chain",
   author, MRL meeting 2026-10-21): 2 rejected reveals per run instead of
   57-64, and the share rises from 0.21 to 0.28-0.29 at alpha 0.45. The
   block-rule noown comparison (sop_v4_noown_72h, 0.112/0.087 vs 0.078/0.113
   own) showed no clear effect because that attacker was stranded most of
   the run; with the objects give-up the effect is clear. The noown variant
   is the stronger attacker and should be the campaign's default from here.
3. **SoP still holds the attacker under alpha** at every point measured
   (0.29 vs 0.45 at best), but by less than the own-counting number said.
   These are lower bounds on what SoP concedes: the strategy is hand-written,
   and a strategy that scores 0.000 where honest mining scores 0.33 is far
   from optimal. An optimal-policy number (MDP on the race model, RL if the
   state space is too large) is the claim the proposal needs; see
   docs/20261021_research_direction_idea_SoP.txt.
4. Stock reference (campaign 7, `data/campaign7/matrix_cells/stubborn_h10*`,
   same attacker family, difficulty weighing, d1-d3): 0.46-0.54 at alpha
   0.45, 0.36-0.46 at 0.40, 0.23-0.31 at 0.30-0.33. Round 2 adds the d5
   stock control with this exact configuration.

## 3. Rounds 2 and 3 (2026-10-24 14:48Z to 2026-10-25 00:21Z, commits `9f711405`, `489b4cf4`)

Scored 2026-10-25 00:30Z from the pool; oracle 0 mismatches and stuck 0 h
in every SoP cell.

| cell | alpha | own tip shares | share (draws) | reveals (delivered) |
|---|---|---|---|---|
| share_sop2_a048 | 0.48 | yes | 0.343, 0.376 | 235 (168), 267 (180) |
| share_sop2_a050 | 0.50 | yes | 0.460, 0.473 | 300 (221), 296 (220) |
| share_sop2_a045 s3, s4 | 0.45 | yes | 0.246, 0.229 | 180 (122), 166 (114) |
| share_sop2_noown_a040 | 0.40 | no | 0.056, 0.076 | 28 (28), 36 (36) |

- **Own-counting curve, four points:** 0.000/0.002 (0.33), 0.055/0.059
  (0.40), 0.209/0.210/0.246/0.229 (0.45; mean 0.224), 0.343/0.376 (0.48),
  0.460/0.473 (0.50). Still below honest mining at a majority: the crossing,
  if any, is above alpha 0.50 for this attacker.
- **noown at 0.40** gains little (0.056/0.076 vs 0.055/0.059): with so few
  reveals the rejected-reveal loss that noown avoids is small there. The
  noown gain is concentrated where the attacker reveals often (0.45: +0.06).
- **Stock control (`sop_v4_o5_stock_72h`, 6 cells): INVALID.** Every cell
  gave share 0.000, 0 reveals in 72 h, 100% of attacker blocks orphaned,
  36-40 h stuck at alpha 0.45, and the attacker wallet logged "reorg exceeds
  maximum allowed depth 127" from day 3. Campaign 7 measured this attacker
  family on stock at 0.46-0.54 (alpha 0.45, d1-d3). The attacker parsed its
  attributes correctly (weigh difficulty, window_objects 0, give_up_objects
  -1, window_rule 20261020). **Root cause (2026-10-25, fixed in `eb070be4`):**
  `agents/selfish_strategy.py`'s 20261020 window test read the per-branch
  window counts from positions 3 and 4 of the weights tuple, but the
  difficulty weigh returns a 3-tuple, so `past` was never True and the
  strategy held on every tick; only the 5-block give-up ever fired (126
  concessions per run, branches popped at up to 65 blocks, 0 reveal lines).
  The strategy logs nothing when it holds, which is why this looked like
  stranding. The tuple-length test now falls back to the v3 window test;
  unit test added (329 pass). The six invalid runs stay in the pool under
  `_invalid/stock_20261024/`; the control re-runs from 2026-10-25 00:36Z
  (a045 and a040 on lithium first, a033 when a box frees).

Round 4 (launched 2026-10-25 00:28-00:32Z): noown a048 (box80), a050 (box82),
a033 + a045 draws 3-4 (phantom), a040 draws 3-4 (box81).

## 3b. Stock control, fixed code (2026-10-25 00:36Z to 07:03Z on lithium, commit `eb070be4`)

Same attacker family on a stock network (weigh difficulty, window_objects 0,
give_up_objects -1, so the block-depth give-up), 12 daemons, 72 h.

| cell | alpha | share (draws) | reveals | attacker orphan frac | health |
|---|---|---|---|---|---|
| share_stock_a040 | 0.40 | 0.414, 0.381 (mean 0.398) | 288, 246 | 0.27, 0.32 | ok |
| share_stock_a045 | 0.45 | 0.516, 0.540 (mean 0.528) | 319, 355 | 0.19, 0.16 | s1: 2 invalid-chain log lines, else ok |

Stuck time 0 h in all four (was 36-40 h in the invalid runs); oracle 0
mismatches. The check gate's Eyal-Sirer verdicts FAIL as expected (this is
the o5 window_stubborn family, not SM1) and a040 s2 sits just under alpha.

**Reading:** on stock, this attacker is roughly break-even at alpha 0.40
(0.398 vs 0.40) and clearly profitable at 0.45 (0.528, +0.08 over honest).
Under SoP the same hashrate earns 0.057 (own) / 0.066 (noown) at 0.40 and
0.224 (own) / 0.284 (noown) at 0.45: SoP turns a +0.08 profit into a
-0.17 to -0.23 loss at 0.45, and the 0.40 attacker loses 0.34 of its
revenue. The a033 stock cells (s1/s2) re-run when a box frees.

## 3c. Round 4: the noown curve (2026-10-25 00:28Z to 08:55Z, 12 cells on box80/81/82/phantom)

| cell | alpha | own tip shares counted | share (draws) | reveals (rejected) |
|---|---|---|---|---|
| share_sop2_noown_a033 | 0.33 | no | 0.000, 0.002 | 0, 1 |
| share_sop2_noown_a040 s3, s4 | 0.40 | no | 0.068, 0.059 | 32, 29 |
| share_sop2_noown_a045 s3, s4 | 0.45 | no | 0.269, 0.253 | 124 (1), 119 (1) |
| share_sop2_noown_a048 | 0.48 | no | 0.495, 0.452 | 227 (2), 219 (1) |
| share_sop2_noown_a050 | 0.50 | no | 0.591, 0.582 | 272 (1), 277 (0) |

Stuck 0 h, oracle 0 mismatches, health ok in all twelve. The gate's
Eyal-Sirer verdicts FAIL as on every SoP cell (not SM1).

**The two curves, all draws (honest mining = alpha):**

| alpha | own-counting o5 (mean) | noown o5 (mean) | stock network (mean) |
|---|---|---|---|
| 0.33 | 0.000, 0.002 (0.001) | 0.000, 0.002 (0.001) | pending |
| 0.40 | 0.055, 0.059 (0.057) | 0.056, 0.076, 0.068, 0.059 (0.065) | 0.414, 0.381 (0.398) |
| 0.45 | 0.209, 0.210, 0.246, 0.229 (0.224) | 0.288, 0.279, 0.269, 0.253 (0.272) | 0.516, 0.540 (0.528) |
| 0.48 | 0.343, 0.376 (0.360) | 0.495, 0.452 (0.474) | - |
| 0.50 | 0.460, 0.473 (0.467) | 0.591, 0.582 (0.587) | - |

**Reading:**

- **The noown attacker crosses honest mining at about alpha 0.48** (0.474 vs
  0.48 at n=2) **and profits at 0.50** (0.587, +0.09 over honest). The
  own-counting attacker is still below honest at 0.50 (0.467). So under the
  2026-10-20 rule, SoP concedes to this hand-written attacker only at or
  above ~48 % of the hashrate; below 0.45 it loses heavily (0.065 at 0.40,
  i.e. one sixth of honest revenue).
- **The noown gain grows with alpha:** +0.008 (0.40), +0.05 (0.45), +0.11
  (0.48), +0.12 (0.50). Rejected reveals are 0-2 per noown cell against
  ~60 per own-counting cell at 0.45: the own-counting attacker keeps losing
  branches to reveals the network refuses, and that cost is largest where
  it reveals most.
- **Against stock:** at 0.45 the stock network concedes 0.528 and SoP 0.272
  (noown); at 0.40 stock 0.398 vs SoP 0.065.
- All of these are lower bounds on what SoP concedes (hand-written
  strategy, o5, one network topology). The MDP line
  (`docs/20261025_sop_mdp_notes.md`) says the exact optimum is out of reach
  at faithful block caps; the capped 85 M-state solve on lithium gives a
  lower bound only.

Round 5 (launched 2026-10-25 ~09:20Z): noown a046 s1/s2 + a047 s1/s2
(phantom) to pin the crossing, noown a048 s3/s4 (box80) and a050 s3/s4
(box82) for the spread, stock a033 s1/s2 (box81) to finish the control.

## 4. Method notes

- Each cell: `scripts/selfish_matrix.py <spec> --parallel 1 --cells <cell>`
  through `.claude/campaign9/run_lane.py` (on disk only), then
  `check_run.py`, then rsync to the pool. Tables rebuilt on the control box
  with `--reanalyze` over the pooled cell JSONs.
- Wall time: 7.9-8.2 h per 72 h cell with two lanes on a 3900X (24 threads),
  9.7 h on the 5600G. Archives 0.3-0.4 GB per cell after the attacker-wallet
  log fix (`185cd4c0`; 12 GB before).
- Pitfall: two lanes starting in the same second on a fresh box race on the
  chain-snapshot template cache and one dies; the driver now staggers lane
  starts by 90 s and the deploy step warms the cache.
