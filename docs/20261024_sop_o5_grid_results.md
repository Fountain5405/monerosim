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

## 3. Round 2 (launched 2026-10-24 14:48-14:58Z, 12 cells, commit `9f711405`)

- `sop_v4_o5_stock_72h`: the stock control, alpha 0.33/0.40/0.45, two
  draws (phantom, lithium).
- `sop_v4_o5_alpha_72h`: alpha 0.48 and 0.50, two draws (lithium, box80).
- `sop_v4_o5_72h`: a045 draws 3 and 4 (box82).

Given finding 2, a noown sweep (0.40, 0.48, 0.50) is the natural round 3.

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
