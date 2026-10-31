# The strongest hand-written attacker against Share-or-Perish (2026-10-26)

The learned attacker could not recover the hand-written rule
(docs/20261026_sop_learned_attacker.md). The next lower bound on what SoP
(MRL #146, 2026-10-20 rule) concedes is therefore the best rule we can
construct by search: the sim's window_stubborn noown attacker with knobs,
evaluated on the race model with the sims' settings, then validated in a
few 72 h cells. Code: scripts/sop_policy.py `param_stubborn`,
scripts/sop_attacker_search.py (the search), scripts/sop_fidelity_audit.py
(sims vs model). Results: data/sop_search/*.jsonl.

Owner's framing (2026-10-25): sims are for calibration points,
implementation-dependent questions and validation; searching is model
work. Owner's constraint (2026-10-26): lithium and phantom run Monero
stressnet nodes; the search runs as many ~80 MB processes, never big tables.

## The family

`param_stubborn(obs, G, L, M, R, B, Z)` over the exact-MDP observation
(a, D, xa, pa, h, xh, ph); the defaults are exactly the sim's rule
(`sim_stubborn`, give-up at 5 objects):

| knob | default | meaning |
|---|---|---|
| G | 5 | give up once the honest branch is ahead by more than G work objects (blocks + shares, pending included) |
| L | 0 | publish an unopposed private lead of L blocks (0: hold while no honest block, as the sim's rule does) |
| M | 1 | reveal only with a margin of M objects over the honest branch (1: as soon as the network accepts) |
| R | 1 | reveal only once the honest branch holds R blocks (deeper reorgs) |
| B | 0 | give up when behind by B blocks (0: off; the objects deficit G is the only give-up) |
| Z | 0 | 1: hold a pending-shares-only branch (a = 0) against an honest block instead of giving up, the race model's own rule (+0.025 at alpha 0.45 over the sim's) |

Reference points in the race model (sim_stubborn, 2000 d, 5 seeds):
0.2558 at alpha 0.45, 0.5715 at 0.50; the sims measured 0.272 and 0.604.

## Method

Staged grids on lithium (16-24 workers of one rollout each):

1. Stage 1: G x Z at alphas 0.45 / 0.48 / 0.50, 1000 d, 2 seeds (72 runs).
2. Stage 2: L x M x R at the stage-1 best per alpha, same budget.
3. Stage 3: the best combo per alpha and the baseline at 2000 d x 3
   seeds over alphas 0.40 to 0.50 in steps of 0.01: the curve and the
   crossing (share passes alpha), against the sims' stubborn crossing of
   about 0.483.
4. Then (experiment 2 of the plan): K and w of the countermeasure swept
   with the best attacker; (experiment 3): the winner ported to the agent
   and run at 0.48 and 0.50 in 72 h cells against the model's prediction.

Seed noise at 1000 d is about 0.003 (0.001 at 2000 d, measured 2026-10-25).

## Results

### Stage 1 (G x Z)

03:22Z, 72 runs in 192 s on 16 workers (a 1000 d rollout takes ~43 s).
Mean share over 2 seeds; the sim's rule is G=5 Z=0.

| alpha | honest | sim's rule (2000 d) | best | share | reveals/run | att. orphan | net. orphan | mean/max reorg |
|---|---|---|---|---|---|---|---|---|
| 0.45 | 0.45 | 0.2562 | G=8 Z=1 | 0.2809 | 29,049 | 0.643 | 0.428 | 3.44/17 |
| 0.45 | | | G=5 Z=1 | 0.2755 | 29,495 | 0.648 | 0.424 | 3.25/16 |
| 0.48 | 0.48 | 0.4467 | G=8 Z=1 | 0.5173 | 51,802 | 0.400 | 0.443 | 3.49/22 |
| 0.48 | | | G=12 Z=1 | 0.5172 | 47,956 | 0.408 | 0.450 | 3.82/37 |
| 0.50 | 0.50 | 0.5714 | G=20 Z=1 | 0.7149 | 56,024 | 0.240 | 0.468 | 4.47/47 |
| 0.50 | | | G=40 Z=1 | 0.7125 | 39,466 | 0.259 | 0.480 | 6.39/133 |
| 0.50 | | | G=12 Z=1 | 0.7035 | 64,774 | 0.239 | 0.459 | 3.77/31 |

Findings: Z=1 (keep a pending-shares-only branch alive against an honest
block, as the race model's own rule does) helps at every alpha; the best
give-up threshold grows with alpha (8 objects at 0.45-0.48, 20 at 0.50,
where a 40-object patience still scores 0.71 with reorgs of up to 133
blocks). At 0.48 the attack becomes profitable (0.517 against honest's
0.48) where the sim's rule was not (0.447). Interpolated crossings over
the three alphas: G=8 Z=1 0.4746, G=12 Z=1 0.4750, G=5 Z=1 0.4776, the
sim's rule 0.4862 (0.4864 on the 2000 d baseline). The network orphan
rate under the stronger attacker rises to 0.43-0.48 of all blocks found.

### Stage 2 (L x M x R at G in 8/12/20, Z=1)

04:05Z, 864 runs (144 combos x 3 alphas x 2 seeds, 1000 d) in ~35 min on
20 workers. Mean share over 2 seeds:

| alpha | honest | stage-1 best | best | share | reveals/run | att. orphan | net. orphan | mean/max reorg |
|---|---|---|---|---|---|---|---|---|
| 0.45 | 0.45 | 0.2809 (G=8 Z=1) | G=8 L=1 M=1 R=1 Z=1 | 0.3747 | 18,641 | 0.410 | 0.291 | 4.13/23 |
| 0.45 | | | G=8 L=1 M=1 R=2 Z=1 | 0.3738 | 18,330 | 0.413 | 0.293 | 4.22/23 |
| 0.45 | | | G=8 L=1 M=2 R=1 Z=1 | 0.3609 | 16,650 | 0.431 | 0.291 | 4.18/23 |
| 0.48 | 0.48 | 0.5173 (G=8 Z=1) | G=8 L=1 M=1 R=1 Z=1 | 0.5259 | 35,598 | 0.277 | 0.340 | 4.18/20 |
| 0.48 | | | G=8 L=1 M=1 R=2 Z=1 | 0.5254 | 35,054 | 0.280 | 0.342 | 4.26/20 |
| 0.48 | | | G=8 L=2 M=1 R=2 Z=1 | 0.5209 | 41,270 | 0.343 | 0.394 | 4.01/20 |
| 0.50 | 0.50 | 0.7149 (G=20 Z=1) | G=20 L=0 M=1 R=3 Z=1 | 0.7274 | 49,928 | 0.235 | 0.474 | 5.14/47 |
| 0.50 | | | G=20 L=0 M=1 R=2 Z=1 | 0.7205 | 54,048 | 0.237 | 0.471 | 4.69/47 |
| 0.50 | | | G=12 L=0 M=1 R=3 Z=1 | 0.7167 | 56,458 | 0.238 | 0.468 | 4.45/28 |

Findings. At 0.45 and 0.48 the best attacker publishes every unopposed
lead at once (L=1): it never withholds a block the honest network has
not yet matched. Its gain comes from contesting honest blocks with the
share weight it has accumulated (Z=1: a pending-shares-only branch is
kept alive against an honest block, and the attacker keeps mining on it
until the window passes and its branch outweighs the honest one, or the
deficit reaches 8 objects). That is a different attack from the
block-withholding the stubborn family was written for, and it costs the
network fewer orphans (0.29 of all blocks found at 0.45 against 0.43
for the withholding version) while paying the attacker more. Withholding
only pays at 0.50, where L=0 with a deep reveal (R=3: reveal only once
the honest branch holds three blocks) is best. The reveal margin M never
helps (1 is best everywhere): waiting for a larger margin forfeits
accepted reveals. Interpolated crossings: G=8 L=1 M=1 R=1 Z=1 0.4686,
R=2 0.4688, R=3 0.4695; the sim's rule 0.4862.

### Stage 3: the curve and the crossing

04:20Z, 2000 d x 3 seeds, alphas 0.40 to 0.50 in steps of 0.01, seven
configurations and the sim's rule (seed noise ~0.001). Share of the best
no-withholding attacker (publish_lead 1, Z=1; G=6 to 0.47, G=8 at 0.48,
G=10 above), the best withholding attacker (L=0: G=8 R=1 to 0.48, G=12
R=3 at 0.49, G=20 R=3 at 0.50) and the sim's rule:

| alpha | honest | sim's rule | best, no withholding | best, withholding | best overall |
|---|---|---|---|---|---|
| 0.40 | 0.40 | 0.0553 | 0.2808 | 0.0570 | 0.2808 |
| 0.41 | 0.41 | 0.0803 | 0.2933 | 0.0834 | 0.2933 |
| 0.42 | 0.42 | 0.1124 | 0.3095 | 0.1180 | 0.3095 |
| 0.43 | 0.43 | 0.1529 | 0.3304 | 0.1622 | 0.3304 |
| 0.44 | 0.44 | 0.2015 | 0.3566 | 0.2162 | 0.3566 |
| 0.45 | 0.45 | 0.2562 | 0.3892 | 0.2796 | 0.3892 |
| 0.46 | 0.46 | 0.3171 | 0.4278 | 0.3520 | 0.4278 |
| 0.47 | 0.47 | 0.3810 | 0.4724 | 0.4320 | 0.4724 |
| 0.48 | 0.48 | 0.4467 | 0.5249 | 0.5159 | 0.5249 |
| 0.49 | 0.49 | 0.5108 | 0.5882 | 0.6172 | 0.6172 |
| 0.50 | 0.50 | 0.5714 | 0.6553 | 0.7253 | 0.7253 |

Crossings (share passes alpha, interpolated on the 0.01 grid): G=6 L=1
M=1 R=1 Z=1 0.4693, G=8 L=1 0.4703, G=10 L=1 0.4719, G=8 L=0 0.4751,
G=12 L=0 R=3 0.4763, G=20 L=0 R=3 0.4804, the sim's rule 0.4861.

Findings. (1) The strongest hand-written attacker found moves SoP's
profitability threshold from 0.486 to 0.469 in the race model (the sims
run about 0.003-0.01 lower than the model for the same rule, so expect
about 0.46 there): still far above the stock network's, where selfish
mining pays from about 0.40 on this network (0.414/0.381 measured at
0.40, 0.516/0.540 at 0.45). (2) Below the crossing the no-withholding
attacker extracts several times what the stubborn rule does (0.28
against 0.06 at alpha 0.40) by contesting honest blocks with share
weight, while orphaning half as many blocks (0.19 of all blocks found
against 0.39); it still earns less than honest mining there, so it is
irrational, but it is the attack a rational miner would keep in reserve.
(3) Classic withholding only pays from 0.49, and then with deep reveals
(three honest blocks orphaned at a time, 20-object patience at 0.50).
(4) No configuration in the family beats the no-withholding one between
0.40 and 0.48 and the search was exhaustive over its six knobs at the
grid resolution used.

Fine grid (05:25Z; G in 5/6/7 x R in 1/2, L=1 Z=1; alphas 0.455 to 0.48
by 0.005; 2000 d x 3 seeds; data/sop_search/crossing_fine.jsonl): the
crossing is 0.4693 for G=5 and G=6 (0.4698 for G=7), i.e. 0.469 to
within the seed noise; the best give-up drifts up with alpha (5 at
0.46-0.465, 5 or 6 at 0.47, 7 at 0.475-0.48), with differences of a few
thousandths. At alpha 0.47 the best attacker earns 0.4724, 0.0024 above
honest.

### The stock network in the same model

For the comparison point, the model's stock stubborn attacker (no window,
no shares; withhold while unopposed, reveal once ahead by a block after
an honest block, give up when behind by d blocks) over d and alpha,
2000 d x 3 seeds (05:45Z; `scripts/sop_stock_crossing.py`,
data/sop_search/stock_crossing.jsonl):

| alpha | d=1 | d=2 | d=3 |
|---|---|---|---|
| 0.30 | 0.2575 | 0.2620 | 0.2504 |
| 0.34 | 0.3166 | 0.3243 | 0.3147 |
| 0.36 | 0.3474 | 0.3569 | 0.3489 |
| 0.38 | 0.3785 | 0.3901 | 0.3842 |
| 0.40 | 0.4104 | 0.4239 | 0.4206 |
| 0.42 | 0.4425 | 0.4580 | 0.4576 |
| 0.44 | 0.4745 | 0.4920 | 0.4950 |

Crossings: d=2 0.3648, d=3 0.3746, d=1 0.3825. The sims' stock cells
(window_stubborn on the stock network, giving up 5 blocks behind)
measured 0.247 at 0.33, 0.398 at 0.40 and 0.528 at 0.45 (two seeds
each), a crossing near 0.40. Like for like (d=5, 10-27;
data/sop_search/stock_crossing_d5.jsonl) the model gives 0.262, 0.394
and 0.505, crossing 0.405: sims minus model -0.015, +0.004, +0.023, so
the model reproduces the stock sims as it does the SoP ones. (This
paragraph used to compare those cells with the model's d=2 attacker and
read a sign reversal into the gap; that was not like for like.) The
headline's stock figure (d=2, 0.365) is simulated below (10-27/28: 0.369
in Shadow). The textbook
optimum for a zero-propagation-advantage selfish miner is 1/3; this
family is not optimal and lands at 0.365.

**The headline, all in one model and one attacker family:** SoP moves the
profitability threshold from 0.365 (stock, best d) to 0.469 (the
strongest SoP attacker found; 0.468 with the perish rule, 0.464 in
Shadow) and 0.486 (the sims' stubborn rule). The
attacker that sets the SoP figure does not withhold blocks below 0.49;
it contests honest blocks with share weight.

Stock sims with the model's best stock attacker (sop_v4_stock_d2_72h,
give-up depth 2; 10-27, 72 h, all four cells PASS with no dead daemons;
rates per 1,000 found blocks):

| alpha | sims (s1, s2) | mean | model | reveals per 1,000 found, sims / model | attacker orphan rate, sims / model | network orphan rate, sims / model |
|---|---|---|---|---|---|---|
| 0.34 | 0.303, 0.310 | 0.307 | 0.324 | 101.7 / 107.1 | 0.266 / 0.239 | 0.209 / 0.203 |
| 0.36 | 0.352 | 0.352 | 0.357 | 110.4 / 115.5 | 0.233 / 0.216 | 0.216 / 0.209 |
| 0.38 | 0.402, 0.382 | 0.392 | 0.390 | 122.5 / 123.7 | 0.207 / 0.193 | 0.223 / 0.214 |

The sims cross at 0.369 by least squares over the five cells (0.370
between the 0.34 and 0.38 pair means; the 0.36 cell, 10-28, sits on that
line: 0.352 against 0.349), the model at 0.365; as with
give-up depth 5, the sims' curve is a little steeper than the model's
(-0.018 at 0.34, +0.002 at 0.38). The headline comparison holds in
Shadow: the best attacker found needs about 0.370 of the hashrate on the
stock network and 0.4635 under SoP, a rise of about 0.094 (model 0.103).

## Experiment 2: the countermeasure's K and w

K is the window depth in blocks and w the shares per block; the window a
branch must clear before a reveal is (K - 1) * w objects (32 by default).
For each (K, w): the sim's rule as the baseline and the family with G in
{w/2, w, 2w}, L in {0, 1}, R in {1, 3}, Z=1, M=1, at alphas 0.40 / 0.45 /
0.48 / 0.50, 1000 d x 2 seeds (1,248 runs, 04:30-05:05Z 10-26;
`scripts/sop_kw_table.py` on data/sop_search/kw_sweep.jsonl):

| K | w | window | best at 0.40 | best at 0.45 | best at 0.48 | best at 0.50 | best crossing | best combo | sim's rule crossing |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 8 | 8 | 0.331 | 0.456 | 0.573 | 0.721 | 0.446 | G=4 L=1 | 0.470 |
| 3 | 8 | 16 | 0.299 | 0.426 | 0.561 | 0.717 | 0.459 | G=4 L=1 | 0.474 |
| 2 | 16 | 16 | 0.282 | 0.409 | 0.546 | 0.730 | 0.462 | G=8 L=1 | 0.483 |
| 4 | 8 | 24 | 0.278 | 0.401 | 0.547 | 0.713 | 0.467 | G=4 L=1 R=3 | 0.478 |
| 3 | 16 | 32 (default) | 0.259 | 0.375 | 0.526 | 0.727 | 0.469 | G=8 L=1 | 0.486 |
| 2 | 32 | 32 | 0.249 | 0.334 | 0.505 | 0.735 | 0.475 | G=16 L=1 | 0.492 |
| 6 | 8 | 40 | 0.252 | 0.362 | 0.515 | 0.708 | 0.474 | G=8 L=1 R=3 | 0.482 |
| 4 | 16 | 48 | 0.246 | 0.348 | 0.506 | 0.723 | 0.474 | G=8 L=1 | 0.489 |
| 3 | 32 | 64 | 0.240 | 0.302 | 0.483 | 0.731 | 0.480 | G=16 L=1 | 0.494 |
| 6 | 16 | 80 | 0.236 | 0.305 | 0.474 | 0.723 | 0.481 | G=8 L=1 R=3 | 0.491 |
| 4 | 32 | 96 | 0.238 | 0.278 | 0.462 | 0.728 | 0.482 | G=16 L=1 | 0.496 |
| 6 | 32 | 160 | 0.237 | 0.246 | 0.423 | 0.725 | 0.485 | G=16 L=1 R=3 | 0.497 |

(The sim's rule keeps its give-up at 5 objects whatever w is, so its
column is not comparable across w; the "best" columns are.)

Findings. (1) The crossing is set almost entirely by the window length in
objects, with diminishing returns: 0.446 at 8 objects, 0.469 at the
default 32, 0.480 at 64, 0.485 at 160. Doubling the default window buys
about 0.01 of threshold. (2) At a given window length, more shares per
block helps the defender slightly (window 32: 0.469 with w=16, 0.475 with
w=32), i.e. finer weight granularity is worth a little. (3) Above the
crossing the parameters stop mattering: the best attacker takes 0.71 to
0.74 at alpha 0.50 under every setting. (4) Below the crossing a longer
window cuts what an irrational attacker can extract (0.33 at 0.40 with an
8-object window, 0.24 with 160). (5) The best attacker is the
no-withholding one under every setting at these alphas, with its give-up
threshold scaling with w (about half a block of objects: 4 at w=8, 8 at
w=16, 16 at w=32); at the longer windows a reveal depth of 3 helps.

Precision check (09:15Z; each setting's best attacker over alphas 0.44
to 0.50 by 0.01, 2000 d x 3 seeds; data/sop_search/kw_fine.jsonl): the
crossings are 0.4468 (window 8), 0.4599 (16 via K=3, w=8), 0.4630 (16
via K=2, w=16), 0.4703 (32, the default), 0.4797 (64), 0.4811 (80),
0.4855 (160), all within 0.002 of the sweep's values. Defender's rule of
thumb from this: each doubling of the window length in objects raises the
threshold by about 0.01 up to 64 objects, and by less beyond.

With the perish rule (10-27; the L=1 family, M=1, Z=1, G and R as
listed in data/sop_search/kw_perish_047.jsonl, 2000 d x 3 seeds; the
default window from perish_stage3.jsonl), each setting's best attacker:

| K | w | window | best at 0.46 | best at 0.47 | best at 0.48 | crossing | best at 0.47 | reveals per 1,000 found at 0.47 |
|---|---|---|---|---|---|---|---|---|
| 2 | 8 | 8 | 0.497 | 0.536 | 0.576 | below 0.46 (about 0.447 extrapolated) | G=4 | 74.1 |
| 2 | 16 | 16 | 0.470 | 0.514 | 0.568 | 0.4547 (at 0.45: G=1 0.441, G=2 0.438; kw_perish_k2_045.jsonl) | G=6 | 66.9 |
| 3 | 16 | 32 (default) | 0.429 | 0.477 | 0.540 | 0.4684 | G=6 | 46.3 |
| 3 | 32 | 64 | 0.383 | 0.433 | 0.502 | 0.476 | G=6 | 34.0 |
| 6 | 16 | 80 | 0.348 | 0.399 | 0.476 | just above 0.48 (about 0.4805 extrapolated) | G=4 | 18.8 |

The rule lowers the crossings by up to 0.008 at the short windows (16
objects: 0.463 to 0.4547) and by less at the long ones (64: 0.480 to
0.476; 80: 0.481 to about 0.4805), so the rule of thumb stands. At alpha
0.47 the window alone sets the sign of the attack: the best attacker
makes +0.044 over honest mining with a 16-object window and +0.007 with
the default 32, and loses 0.037 with 64 and 0.071 with 80 (R=1 and R=3
tie at 80, within 0.0003). The daemon's K enters only its lateness window
((K - 1) * w objects; its fallback to plain work is at 10 * w blocks,
whatever K), as in the model. The window sims test the flip at w=16:
sop_v4_window_72h, K=2 and K=6 at alpha 0.47, two seeds each, on the
same seeds as the default window's a047 s1 and s2 cells.

The window sims (10-27, 72 h, one lane per box; all four PASS the gate with
no dead daemons; reveals per 1,000 found blocks; model = the perish run's
best attacker at 0.47):

| cell | box | share | model | attacker orphan rate | model | network orphan rate | model | reveals per 1,000 found | model | default window, same seed | run |
|---|---|---|---|---|---|---|---|---|---|---|---|
| K=2 s1 | box80 | 0.546 | 0.514 | 0.240 | 0.274 | 0.332 | 0.337 | 71.9 | 66.9 | 0.451 | 20261027_115702 |
| K=2 s2 | box81 | 0.493 | 0.514 | 0.309 | 0.274 | 0.358 | 0.337 | 67.6 | 66.9 | 0.514 | 20261027_115708 |
| K=6 s1 | box82 | 0.454 | 0.399 | 0.368 | 0.433 | 0.358 | 0.332 | 26.2 | 18.8 | 0.451 | 20261027_115714 |
| K=6 s2 | phantom | 0.436 | 0.399 | 0.410 | 0.433 | 0.372 | 0.332 | 24.5 | 18.8 | 0.514 | 20261027_115719 |

The flip holds in both seeds: at alpha 0.47 the attack pays with a
16-object window (mean 0.520) and does not with an 80-object one (mean
0.445). K=2 matches the model on every measure (share +0.006, reveals +4%,
both orphan rates within 0.01 on the pair). K=6 does not: the sims'
attacker takes 0.046 more than the model, reveals 35% more often (80 and
76 reveals against about 58 expected; each cell 2-3 Poisson sd above) and
loses fewer of its blocks (attacker orphan rate 0.389 against 0.433).
Pairing by seed did not cut the noise (seed 1: K=6 0.454 above the
default window's 0.451; seed 2: K=2 0.493 below its 0.514), so the cells
count as independent (sd about 0.03 per cell). Read as the model's
curve plus the cells' mean offset at 0.47 (+0.006 at K=2, +0.046 at
K=6; the model's curves bend, so a straight line through one alpha
misreads them), the sims put the K=2 crossing near 0.452 and the K=6
crossing near 0.474 (each about +-0.005 from the two-cell noise),
against the default window's 0.4635: a window of 16 objects lowers the
threshold by about 0.011 and one of 80 raises it by about 0.010,
against the model's 0.014 and 0.012. At K=2 and 0.45
(sop_v4_window_k2_a045_72h, G=2; both PASS, no dead daemons) the sims
ran 0.436 and 0.441 against the model's 0.438 (37.9 and 45.2 reveals per
1,000 found against 39.3), so the K=2 crossing is bracketed directly: it
interpolates to 0.454 between the pair means (0.4385 at 0.45, 0.520 at
0.47), the model's 0.4547. K=2 lowers the threshold by about 0.010 in
the sims (model 0.014). At K=6 and 0.48
(sop_v4_window_k6_a048_72h, G=8, the model's break-even at 0.476; both
PASS, no dead daemons) the attack pays in one seed and breaks even in
the other: 0.538 (34.7 reveals per 1,000 found against the model's
28.9) and 0.481 (28.8, as the model). Over the four K=6 cells the sims
run +0.040 +- 0.013 over the model, three of them by 0.04-0.06 and one
not at all. The K=6 crossing interpolates to 0.475 between the pair
means (0.445 at 0.47, 0.510 at 0.48), against the model's 0.4805: K=6
raises the threshold by about 0.011 in the sims (model 0.012). The third
seed at 0.47 (10-28, PASS) ran 0.428 (22.1 reveals per 1,000 found):
three seeds 0.454 / 0.436 / 0.428, mean 0.439 +- 0.008 against 0.399;
over the five K=6 cells the excess is +0.038 +- 0.010 and the crossing
stays at 0.475. The third seed at 0.48 (PASS) ran 0.540 (33.2 reveals
per 1,000 found against 28.9): 0.538 / 0.481 / 0.540, mean 0.520 +- 0.019
against 0.476. Over all six K=6 cells the excess is +0.042 +- 0.009, and
the crossing interpolates to 0.474 between the three-seed means (0.439 at
0.47, 0.520 at 0.48).

Where the K=6 excess comes from (decision histograms, `sop_decision_hist.py
--K --w`: the model with the perish rule, 600 d x 2 seeds, against the cells'
attacker logs, per 1,000 found blocks). At K=2 every count matches: reveals
67.1 vs 71.9 / 67.5, race starts 182.5 vs 184.3 / 181.8, give-ups 52.5 +
69.0 vs 50.1 + 62.3 / 45.7 + 68.9, and the same reveal states. At K=6 the
races start alike (race starts 156.5 vs 146.2 / 139.6, with the same
pending-share, honest-object and deficit quantiles at the start) but end
differently: 26-29% of the races that put blocks on both sides end in a
reveal in the sims against 19% in the model (reveals 26.2 / 24.5 vs 18.8;
give-ups with blocks 64.8 / 71.1 vs 79.7). Every reveal is a distinct race
(no fork is revealed twice), and reveals with fewer attacker blocks than
honest ones are normal in both (48% in the model, 54% in K=6 s1): shares
carry the weight. The weights the network compared at each reveal, from the
honest nodes' per-fork decision records (`SIM-SoP-DEC`: every block on both
branches with its embedded shares, and the pool shares counted; honest-001,
relay-001 within 0.1), against the model's state at its own reveals (600 d,
seed 1):

| at the reveal | K=2 model | K=2 sim s1 | K=6 model | K=6 sim s1 |
|---|---|---|---|---|
| blocks, attacker / honest | 2.59 / 3.11 | 2.40 / 3.23 | 6.49 / 6.82 | 6.25 / 7.23 |
| objects per attacker block | 20.1 | 21.7 | 17.9 | 18.6 |
| objects per honest block (with pending) | 14.9 | 14.5 | 15.7 | 14.6 |
| honest pending (pool) shares counted | 10.4 | 9.4 | 12.2 | 9.7 |
| objects, attacker / honest | 52.0 / 46.3 | 52.0 / 46.8 | 116.5 / 106.9 | 116.0 / 105.8 |

The sims' nodes judged 181 of the 188 K=2 reveals and all 79 K=6 ones after
the window, where SoP's 5 s delay rule does not apply, so that rule is not
the cause. The gap between the sides per block (attacker 18-22 objects,
honest about 15) is selection, the same in the model: the attacker reveals
when its share luck is good. The weights at the reveal match; what differs
is how fast the honest side builds weight: at K=6 the sims' honest side
counts about one object less per block (14.6 against 15.7), split between
shares embedded per honest block (12.3 against 12.9) and pending shares
counted (9.7 against 12.2), and reaches the reveal point with 0.4 more
honest blocks; at K=2 the gap is 0.4 objects per block. At the default
window (K=3; the 0.47 cells s2 and s3, model 15.3 per honest block with
11.4 pending) the sims count 13.7 and 14.6 per honest block with 9.3 and
9.0 pending; the seed with the larger gap is the one that ran far above
the model (s2: 0.514 against 0.477; s3: 0.478). In all five cells the
sims' honest side counts 0.4 to 1.6 objects per block fewer than the
model at the reveal, and the honest pending shares counted stay near 9
to 10 at every window while the model's grow with it (10.4, 11.4, 12.2
at K=2, 3, 6). A candidate cause
the model (one honest miner, no propagation) cannot produce: honest shares
still in flight, or mined on a stale tip, when a node judges or a block is
built. Such a loss grows with race length, as the excess does (K=2 +0.006,
default +0.018, K=6 +0.046); tested next.

The one-honest-miner test (sop_v4_window_k6_1h_72h, owner-approved 10-28):
K=6 at 0.47 as in the k6 a047 cells, but honest-001 mines 5.29 and
honest-002 stays a full node at 0.01 h/s (0 is rejected by the config
validator), so the honest side is one miner. Seed 1 (PASS, no dead
daemons) ran 0.373 against its two-honest-miner partner's 0.454 and the
model's 0.399, with the model's activity exactly: 18.7 reveals per 1,000
found blocks (model 18.8, two honest miners 26.2) and a network orphan
rate of 0.332 (model 0.332, two miners 0.358); attacker orphan rate 0.455
(model 0.433, two miners 0.368). Concentrating the honest hashrate in one
miner removes the excess, so it comes from splitting the honest side
across miners: honest shares lost between them, which the model's single
honest miner cannot lose. Seed 2 (PASS) agrees: 0.382 against its
partner's 0.436, 19.9 reveals per 1,000 found (two miners 24.5) and a
network orphan rate of 0.342 (two miners 0.372). On the same two seeds,
one honest miner averages 0.378 (the model 0.399, within noise) and two
honest miners 0.445: splitting the same honest hashrate over two miners
hands the attacker 0.054 and 0.081. SoP therefore protects less as honest
hashrate spreads over more miners, the realistic direction (Monero has
many pools); the model, with one honest miner, is the best case. The N=4
cell (sop_v4_window_k6_h4_72h, the same hashrate over four miners, base
selfish_micro_sop_h4.yaml) runs from 10-28 09:30Z.

## Validation in the sims

### Smoke (6 h, alpha 0.50, G=20 Z=1, L=0 M=1 R=1)

box81, 03:39-04:15Z 10-26 (cell share_sop2_param_a050_s1 of
sop_v4_param_6h; tree synced from local commit 26d317d9). Return code 0,
oracle 0 mismatches over 12 nodes, 34,800 decisions all from the policy,
no suppressed reveals, give-ups with withheld blocks in the log. Share
0.784 over 116 canonical blocks (the model's 2000 d prediction for these
knobs is 0.715; a 6 h cell is noisy), attacker orphan rate 0.042,
network orphan rate 0.380. The check gate reported reveals=0 and FAILed
because the miner's `<strategy>: reveal fork=` line was only written for
window_stubborn and deep_hunt; fixed before the 72 h cells (the learned
and param strategies now log reveals, and publishes of an unopposed lead
separately).

### 72 h cells

First round (launched 04:22Z 10-26 from local commit 81a3820e):

| cell | box | knobs | model | sims share | att. orphan | net. orphan | reveals/72 h | run |
|---|---|---|---|---|---|---|---|---|
| a047 s1 | box81 | G=6 L=1 M=1 R=1 Z=1 | 0.472 | 0.464 | 0.108 | 0.104 | 36 | 20261026_042332 |
| a048 s1 | box80 | G=8 L=1 M=1 R=1 Z=1 | 0.525 | (0.858: invalid, honest-001's daemon dead from sim 00:04:50) | 0.003 | 0.110 | 83 | 20261026_042327 |
| a048 s2 | box80 | G=8 L=1 M=1 R=1 Z=1 | 0.525 | stopped 11:10Z at 49.5 h (11 of 12 daemons alive) | | | | 20261026_042457 |
| a050 s1 | box82 | G=20 L=0 M=1 R=3 Z=1 | 0.725 | stopped 11:11Z at 45 h (11 of 12 daemons alive) | | | | 20261026_042142 |
| a050 s2 | box82 | G=20 L=0 M=1 R=3 Z=1 | 0.725 | stopped 11:11Z at 41 h (11 of 12 daemons alive) | | | | 20261026_042312 |

The 0.47 cell (rc 0, oracle 0 mismatches, 86,600 decisions all from the
policy, 2,085 blocks) came in 0.008 under the model, but its structure
was far off: 36 reveals (15 per 1,000 found blocks) and orphan rates
near 0.10 where the model's attacker with these knobs makes 40 reveals
per 1,000 found blocks (86 in the model's 72 h, which is 2,160 found
blocks) and orphans 0.30 (`scripts/sop_decision_hist.py`). The attacker log explains it: the sim's
attacker started 980 share races, abandoned 895 of them with no block
and reached a block in only 8.5%, and at EVERY race start its observation
had pa = 0, where the model's attacker holds a median of 12 pending
shares (mean 15) when the honest block lands. The shares exist (its
blocks embed 15-16 objects each, visible in the reveal lines); the
agent's tip-pool lookup needs a header on the branch and an empty
attacker branch has none, so a share-only branch always looked hopeless:
the deficit was the honest branch's objects alone (median 7), 55% of
races exceeded the give-up threshold at once and the rest held with
nothing to race with. This is an agent measurement gap, not a network
rule (the attacker can always count its own pool), and it never touched
the earlier campaigns: the stubborn rule gives up at a = 0 regardless.
Fixed: the empty branch's tip is the fork block and its pool is the
attacker's pending (agents/selfish_miner.py `_fork_header`; test
`test_branch_weights_counts_the_attackers_pool_shares_on_an_empty_branch`).
The gate's three FAILed verdicts are the campaign's Eyal-Sirer
expectations (share above the ES curves and above honest), which every
SoP cell below the crossing fails by design; health was ok.

The four other first-round cells (box80 a048 s1+s2, box82 a050 s1+s2)
ran the same crippled measurement, and a second, independent defect: the
kernel's out-of-memory killer took one daemon from each of them. The
a048 s1 run finished first (10:30Z) with share 0.858, gamma 0.81, an
attacker orphan rate of 0.003 and the health flag "REORG 839/840; SPLIT
1813". The split depth is the giveaway: honest-001's monerod log ends at
sim time 00:04:50 on day 1 at height 997 (no crash text, the process just
stops), and 2810 - 997 = 1813. So that run had one honest miner (2.6 of
7.4 units, an effective alpha of 0.65) for 45 h, and after honest-002's
daemon died too (its log ends at sim 21:22 on day 2; the attacker made no
concession after 20:39, a 27.3 h stuck gap) the attacker mined alone. The
box's dmesg has the kills (09:03Z and 11:09Z on box80; 04:25Z, at launch,
and 10:50Z on box82), and each of the three still-running first-round
cells had 11 of 12 daemons alive when stopped. Cause: the run's own
memory_samples.csv puts one lane's daemons at about 6.5 GB (this attacker
forks far more: 4,008 forks and 4,457 alternative blocks in the a048 s1
run; the lane driver budgets 3.5 GB per lane from the stubborn
campaigns), so two lanes on a 16 GB box ran at "RAM 100% used" from
04:51Z on (memory_alerts.log). The lane gate passed the run because it
never checked that every daemon stayed alive; it does now (check_run.py
`dead_daemons`: a daemon whose log ends more than 2 h before the run's
latest daemon line fails the gate; on the archived runs it flags
honest-001 and honest-002 in a048 s1 and nothing in the healthy a047 s1).
The first-round 0.47 cell ran alone on box81 and was healthy. Rule from
here: one lane per 16 GB box for this spec; the first-round cell JSONs are
kept in data/sop_search/sim_round1/ as the record.

Second round (the fix 61969161, one lane per box):

| cell | box | start (UTC) | model | sims share | att. orphan | net. orphan | reveals/72 h | run |
|---|---|---|---|---|---|---|---|---|
| a045 s1 | lithium | 10-26 16:10 | 0.389 | 0.431 | 0.374 | 0.331 | 107 | 20261026_161026 |
| a045 s2 | lithium | 10-26 21:41 | 0.389 | 0.378 | 0.413 | 0.316 | 96 | 20261026_214158 |
| a046 s1 | phantom | 10-26 10:29 | 0.428 | 0.450 | 0.348 | 0.339 | 127 | 20261026_102909 |
| a046 s2 | phantom | 10-26 16:20 | 0.428 | 0.445 | 0.383 | 0.347 | 126 | 20261026_162014 |
| a047 s1 | box81 | 10-26 10:03 | 0.472 | 0.451 | 0.362 | 0.350 | 135 | 20261026_100300 |
| a047 s2 | lithium | 10-26 10:29 | 0.472 | 0.514 | 0.308 | 0.368 | 160 | 20261026_102904 |
| a047 s3 | box81 | 10-26 16:35 | 0.472 | 0.478 | 0.344 | 0.352 | 143 | 20261026_163526 |
| a048 s1 | box80 | 10-26 11:07 | 0.525 | 0.535 | 0.318 | 0.387 | 173 | 20261026_110702 |
| a048 s2 | box80 | 10-26 17:48 | 0.525 | 0.577 | 0.270 | 0.390 | 202 | 20261026_174808 |
| a050 s1 | box82 | 10-26 11:14 | 0.725 | 0.724 (a) | 0.231 | 0.475 | 248 | 20261026_111408 |
| a050 s2 | box82 | 10-26 19:24 | 0.725 | 0.796 | 0.180 | 0.483 | 264 | 20261026_192424 |

(a) Health flag "INVALID-CHAIN 1": one 'Sent invalid chain' at
monero-seed-006 from relay-002 at sim 22:18:09 on day 2. seed-006 had
asked relay-002 for four blocks from height 2069, synced to 2073 through
another peer 0.35 s before relay-002's answer arrived, and rejected that
answer: a sync race during one of this attacker's deep reveals. No ban
followed, the stale-id count is 0 (the miner bug that flag was built
for), the non-attacker nodes' chains agree (no split), the oracle has 0
mismatches over 12 nodes and all 12 daemons ran to the end. Cell
accepted. Its 35 h of stuck time is the withholding strategy's long
private runs, not a stall.

The fix is confirmed live in the a047 s1 rerun: in its first 3.7 sim
hours the attacker's 279 race-start observations all carried a nonzero
pending count (mode 4, tail to 33), where the first round read 0 at all
8,665; it had made 3 reveals and 8 publishes by then (model: about 4
reveals in 3.7 h).

Second-round readout (all 11 cells, 10-27 03:45Z;
`scripts/sop_param_readout.py matrix_runs/sop_v4_param_72h/cells --pool=<pool>`;
reveals from the lane gate's counts). Every
cell ran to the end with 12 of 12 daemons, 0 oracle mismatches over 12
nodes and gate PASS; the one health flag is note (a).

| alpha | knobs | model share | sim shares | sim mean | sim - model | sim - alpha | reveals per 1,000 found, model / sims |
|---|---|---|---|---|---|---|---|
| 0.45 | G=6 L=1 M=1 R=1 Z=1 | 0.389 | 0.431, 0.378 | 0.405 | +0.016 | -0.045 | 25.2 / 34.3 |
| 0.46 | G=6 L=1 M=1 R=1 Z=1 | 0.428 | 0.450, 0.445 | 0.448 | +0.020 | -0.012 | 32.0 / 42.3 |
| 0.47 | G=6 L=1 M=1 R=1 Z=1 | 0.472 | 0.451, 0.514, 0.478 | 0.481 | +0.009 | +0.011 | 39.6 / 48.2 |
| 0.48 | G=8 L=1 M=1 R=1 Z=1 | 0.525 | 0.535, 0.577 | 0.556 | +0.031 | +0.076 | 49.3 / 59.8 |
| 0.50 | G=20 L=0 M=1 R=3 Z=1 | 0.725 | 0.724, 0.796 | 0.760 | +0.035 | +0.260 | 69.1 / 72.4 |

- **The sims confirm the race model.** Over the 11 cells the sims sit
  +0.021 above the model at the same knobs (sd 0.028 per cell), the sign
  and size the fidelity audit found for the stubborn rule (+0.01 to
  +0.03, from propagation).
- **The sims' crossing of honest mining is 0.4635** by least squares over
  the nine cells from 0.45 to 0.48 (slope 3.8, residual sd 0.027 per
  cell, a rough one-sd band of +-0.0024), and 0.4653 by interpolating
  the per-alpha means; the model's is 0.4693. Under SoP (K=3, w=16) the
  share-weight racing attacker profits from about alpha 0.464 in Shadow,
  against about 0.48 for the stubborn rule in the earlier noown sims
  (round 4; model 0.486) and 0.365 for the best attacker on the stock
  network in the model.
- **Seed noise.** One 72 h cell's share scatters by sd 0.027 (the fit's
  residual; the 0.47 pair alone suggested 0.045), about two to four
  times the binomial 0.011, as expected when races settle several blocks
  at once.
- **Reveals: explained (10-27, next section).** The sims' 1.7-1.9x
  reveal rate per 72 h is two effects: a counting basis (a sim's 72 h
  holds 1.4-1.6x the model's found blocks; per found block the sims
  reveal 1.05-1.36x the model's, the column above) and a model rule
  (honest shares did not perish when the attacker published; with it
  the ratio is 1.03-1.15x).

### The reveal discrepancy (10-27)

Checked in order (scripts/sop_reveal_audit.py, scripts/sop_decision_hist.py
--sim-log, tests in scripts/test_sop_reveal_audit.py and
test_sop_decision_hist.py):

1. **Not double counting.** In all 11 runs every fork is revealed exactly
   once (reveal lines = distinct forks), and reveals mostly succeed (in
   a047 s1, 2 of 135 rejected by the bridge, 3 followed by a concession).
2. **The counting basis.** The model's "72 h" is 2,160 FOUND blocks (720
   a day, canonical and orphaned). The sims' difficulty tracks the main
   chain while 30-48% of found blocks are orphaned, so a sim's 72 h holds
   2,960-3,540 found blocks (canonical / (1 - network orphan rate)). Every
   per-72 h rate compared across the two (reveals, race starts, publishes)
   must be per found block. Shares and orphan rates are ratios and are not
   affected.
3. **A model rule.** At a race start the sims' honest block carries a
   median 9-11 work objects, the model's 18, and the model's attacker
   gave up at once in 30% of races (deficit over G) against 0-1% in the
   sims. Cause: SopEnv._publish reset the attacker's pending shares but
   kept the honest miners' (hon_pending), so shares mined on the old tip
   were counted in the next honest block. Under share-or-perish they
   perish once the attacker's block is the tip (the sims' share slots are
   keyed by prev). New option SimConfig.honest_perish_on_publish
   (race_env(..., perish=True); default off, so every number above is
   unchanged); test
   test_honest_pending_shares_perish_when_the_attacker_publishes_only_with_the_flag.
   It matters only when the attacker publishes (the L=1 family below
   0.49), not at 0.50 (L=0).

Per 1,000 found blocks (model: 600 d, seed 1; sims: mean over seeds):

| alpha | source | reveals | race starts | publishes | give-ups, no block | give-ups with blocks |
|---|---|---|---|---|---|---|
| 0.45 | model | 25.2 | 231.4 | 196.1 | 133.9 | 80.5 |
| 0.45 | model, perish | 29.9 | 181.5 | 153.8 | 65.6 | 92.5 |
| 0.45 | sims (2) | 34.3 | 174.7 | 146.6 | 56.8 | 84.2 |
| 0.46 | model | 32.0 | 218.5 | 192.9 | 120.8 | 73.4 |
| 0.46 | model, perish | 37.8 | 170.4 | 150.4 | 55.0 | 83.6 |
| 0.46 | sims (2) | 41.9 | 168.1 | 141.4 | 49.8 | 76.4 |
| 0.47 | model | 39.6 | 206.9 | 190.0 | 109.2 | 65.1 |
| 0.47 | model, perish | 46.5 | 160.2 | 147.0 | 46.0 | 73.4 |
| 0.47 | sims (3) | 48.1 | 159.0 | 140.9 | 42.0 | 69.2 |
| 0.48 | model | 49.4 | 173.0 | 166.0 | 75.2 | 54.1 |
| 0.48 | model, perish | 56.8 | 133.4 | 128.0 | 23.0 | 58.3 |
| 0.48 | sims (2) | 59.3 | 133.0 | 119.0 | 19.4 | 54.0 |
| 0.50 | model (= perish) | 69.3 | 40.2 | 0.0 | 0.3 | 16.6 |
| 0.50 | sims (2) | 72.2 | 41.8 | 0.0 | 0.4 | 12.2 |

The sims' reveals are releases (the agent's '<strategy>: reveal fork='
lines); the agent's own acceptance test held back a further 0.1-4.2 reveal
decisions per 1,000 found blocks (its suppressed_reveals counter), which a
first tally of the decision lines had counted as reveals. With the perish
rule the model reproduces the sims' race structure: race starts within 4%
at every alpha (160.2 vs 159.0 at 0.47), reveals within 4% at 0.47-0.50
and 11-15% low at 0.45-0.46 (two seeds each).
The share at the cells' knobs moves (one seed, 600 d): 0.389 to 0.377 at
0.45, 0.428 to 0.424 at 0.46, 0.473 to 0.478 at 0.47, 0.526 to 0.543 at
0.48, 0.723 unchanged at 0.50; the crossing at these knobs stays near
0.468. The searched optimum was found without the rule and is not
re-searched yet, and the sims' share is still about +0.02 above the model
with it.

**The sims' "gamma" is not an honest split (10-27).** The cell JSONs'
gamma (0.04-0.15; selfish_mining_analysis.realized_gamma: forks at a height
F with both an attacker and an honest block, resolved by an honest block at
F + 1, counted for the attacker when canonical F is its block) was split
for all 11 runs against the attacker's own release lines (the agent's
`fork` is a daemon height, so the first new block sits at index fork).
Every attacker-side event is one of two things: the top block of a won
reveal with the honest branch at least as long (a <= h; 28-42 per 72 h),
or the attacker's next published block beside an honest block that the
same reveal had already orphaned (14-30 per 72 h; the honest sibling was
found a median 220-370 s before the attacker's block, up to 19 min).
Genuine near-simultaneous ties (honest block within 1 s of the attacker's)
were 2 of 113 checked in a047 s2 and a045 s1. So gamma here measures
SoP's weight-based reveal wins, not tie-breaking, and the model's lack of
block propagation does not explain the sims' +0.02; that gap is still
unexplained. (A first reading of these "ties" as propagation losses, which
would have explained the gap, was wrong: those honest blocks are already
counted as orphaned by the model's reveal.)

### The perish re-search (10-27)

The search rerun with honest shares perishing on an attacker publish
(`sop_attacker_search.py --perish`; the L=1 family, M=1, Z=1, G 3-12, R
1-2, 2000 d x 3 seeds; data/sop_search/perish_stage3.jsonl and, by 0.005,
perish_fine.jsonl):

| alpha | best with perish | share | best without | share |
|---|---|---|---|---|
| 0.44 | G=3 | 0.363 | G=6 | 0.357 |
| 0.45 | G=3 | 0.393 | G=6 | 0.389 |
| 0.46 | G=3 | 0.429 | G=5 | 0.431 |
| 0.465 | G=4 | 0.450 | G=5 | 0.451 |
| 0.47 | G=6 | 0.477 | G=6 | 0.472 |
| 0.475 | G=7 | 0.507 | G=7 | 0.497 |
| 0.48 | G=7 | 0.540 | G=7 | 0.524 |

Crossing 0.4684 with the rule, 0.4693 without (fine grids): the rule
moves the best give-up threshold down at low alpha (an attacker who is
no longer handed a phantom honest lead can afford to give up sooner)
and adds 0.005-0.016 of share above the crossing, but the threshold
itself does not move. The withholding family that wins at 0.49-0.50
never publishes, so its results (0.617, 0.725) stand. The model's
default stays off so that every archived number reproduces; every new
model run passes the option (`--perish`, `race_env(perish=True)`).

## Fidelity audit: sims vs race model

The 72 h cells' JSONs carry the attacker's and the network's orphan rates
and the final-chain block count, which the model reproduces for the same
rule (`scripts/sop_fidelity_audit.py`). The model under-predicted the
sims' share by 0.016 at 0.45 and 0.033 at 0.50 for the same rule; the
orphan rates say whether that is network propagation (honest blocks lost
to natural forks, favouring the attacker) or a rule difference.

Baseline (03:23Z): the sim's rule on the race model at the sims' alphas,
2000 d x 3 seeds, against the 72 h noown cells (n = 2 or 4 per alpha):

| alpha | sims share | model share | diff | sims att. orphan | model | sims net. orphan | model | model reveals/day | reorg |
|---|---|---|---|---|---|---|---|---|---|
| 0.33 | 0.0010 | 0.0016 | -0.0006 | 0.998 | 0.997 | 0.330 | 0.330 | 0.2 | 2.40 |
| 0.40 | 0.0647 | 0.0553 | +0.0094 | 0.900 | 0.915 | 0.385 | 0.387 | 6.0 | 2.55 |
| 0.45 | 0.2726 | 0.2562 | +0.0163 | 0.638 | 0.656 | 0.398 | 0.396 | 27.0 | 2.69 |
| 0.46 | 0.3414 | 0.3171 | +0.0243 | 0.544 | 0.581 | 0.385 | 0.393 | 33.5 | 2.70 |
| 0.47 | 0.3933 | 0.3810 | +0.0124 | 0.480 | 0.505 | 0.385 | 0.389 | 40.4 | 2.71 |
| 0.48 | 0.4591 | 0.4467 | +0.0124 | 0.414 | 0.427 | 0.392 | 0.385 | 47.7 | 2.71 |
| 0.50 | 0.6035 | 0.5714 | +0.0321 | 0.252 | 0.284 | 0.382 | 0.373 | 62.1 | 2.68 |

The model reproduces the sims' orphan structure: the network orphan rate
within 0.01 everywhere, the attacker's own orphan rate within 0.04. The
share gap is one-signed: the sims give the attacker 0.01-0.03 more at
every alpha above 0.33, and the attacker loses fewer of its blocks there
(0.252 vs 0.284 at 0.50) while the network loses slightly more. That is
the signature of a propagation advantage in the 12-daemon network (an
attacker's reveal lands before competing honest blocks have spread, and
honest blocks found meanwhile are lost), not of a rule difference, which
would show in the reveal/give-up structure. The model's crossing (0.4864
for the sim's rule) is therefore an upper bound on the sims' (about
0.483 measured), and the model is a conservative tool for the sweeps:
what it finds profitable, the sims find at least as profitable.
The sims' main chain grows by 1924-1968 blocks per 72 h (a 132-135 s
interval), but with 36-40% of found blocks orphaned they find 3,080-3,240
blocks per 72 h, 4.3-4.5 of the model's 720-block days, so reveal rates
compare per found block (corrected 10-27; this line used to scale by the
main chain): at 0.45 the sims made 40.2 reveals per 1,000 found blocks
(119-138 per 72 h, n = 4) against the model's 37.5, at 0.50 90.6 (272-301,
n = 4) against 86.3. The rule's reveal structure matches within 5-7%.

## The mitigation case (2026-10-28)

The question the owner put on 10-28: what has to be shown for
Share-or-Perish to be worth a place in the Monero codebase. What the
work above already gives: the profitability threshold rises from 0.369
on the stock rule to 0.4635 under SoP against the strongest attacker a
two-stage search found, the race model agrees within 0.01 at every
point, the window parameter behaves as predicted (K=2 0.454, K=6 0.474)
and the gap between the model and the sims is understood (honest
hashrate split across miners helps the attacker; the model is SoP's best
case). What a reviewer will ask for beyond that, and the cell sets that
answer each item (all on the validated 12/14-daemon bases, 72 h, seed
27791 unless stated):

1. **Honest-side cost with no attacker** (`sop_v4_control_72h`, 4
   cells, running): orphan rate, fork-resolution depth and per-miner
   share of an honest network with SoP on versus off.
2. **Honest fragmentation** (`sop_v4_param_1h_72h`, `sop_v4_param_h4_72h`,
   `sop_v4_window_k6_h4_72h`): the threshold with the honest hashrate on
   one, two and four miners. Monero's real hashrate sits in roughly four
   to six pools plus P2Pool, so N=4 is the number that matters; N=8 needs
   the 64-core box (each mining daemon holds ~2.3 GB).
3. **Slow honest miner** (`sop_v4_slow_72h`, 6 cells): SoP weighs a late
   block at 0 and counts a share only if seen 5 s before the competitor,
   so a well-behaved miner on a slow link can lose blocks it would keep
   on the stock rule. The no-attacker control with honest-002 on a node
   3 s / 10 s / 30 s one-way from the rest of the graph
   (`gml_processing/1200_nodes_caida_slow_links.gml`, made by
   `scripts/gml_add_slow_nodes.py`; latency lives only on graph edges),
   stock versus SoP, against the control at latency 0. 3 s is under the
   rule's 5 s and should be benign; 10 s and 30 s are above it.
4. **Network-advantage attacker** (gamma > 0): the one result that could
   sink the case, since item 2 already shows that splitting the honest
   side is the attacker's lever. In Shadow gamma stays ~0 on the stock
   rule because the attacker reacts after seeing the honest block and
   propagation is faster than its reaction. Design pending (below).
5. **Partial adoption** (`sop_v4_adopt_72h`, 7 cells): SoP is a
   fork-choice rule, so deployment is gradual. Four equal honest miners
   at alpha 0.45 (between the two thresholds) with the first N of them on
   SoP; in a mixed network half the forwarding fabric adopts and the
   other relay stays vanilla (drops shares, as a stock node would). The
   validated param attacker at N=1..4, the stock-optimal depth-2 attacker
   at N=0 and N=2, and no attacker at N=2 for the health of a mixed
   network.
6. **The bound is from search, not proof, and there is no upper bound yet**
   (corrected 10-28 after MRL review: an earlier wording said the exact
   MDP "could not beat the family", which misdescribed it). The race
   model's exact MDP (docs/20261025_sop_mdp_notes.md: relative value
   iteration in a bisection on the share, SSZ 2016, validated against
   Monte Carlo) solves only at 3 to 4 blocks per side (85 M states at
   4/4, 12.7 h on lithium), where the optimum is honest mining (0.4500
   at alpha 0.45, 0.5000 at 0.50). The strategies that profit reorg 3 to
   15 blocks deep, so those capped optima are lower bounds on the true
   optimum (every forced action at a cap is legal in the full game) and
   do not bound the family from above. The block-granular tabular
   learner reached 0.577 at alpha 0.50 against the family's 0.725. An
   upper bound needs an optimistic-cap solve (credit the attacker the
   best outcome at a cap; sandwiches the optimum as caps grow) or a
   block-granular abstraction with shares as binned weights that reaches
   8 blocks per side; a stronger attacker may exist until one is done.

Left as stated limitations rather than tested: partition-and-heal
behaviour (Shadow's topology is static for a run), the 5 s share delay
and w=16 as parameters (K covers the window size; d and w are the MRL
defaults).

### 1. The no-attacker control (done 10-28)

`sop_v4_control_72h`: the validated network and hashrate split (4.7 /
2.65 / 2.65) with the third miner mining honestly and connected, every
daemon stock or every daemon SoP (K=3, w=16, delay 5 s), two seeds each.
Shares and orphan rates are the matrix's; the reorg, fork and alt-block
counts are honest-001's daemon health counters.

| cell | third miner's share (hashrate 0.470) | main chain | network orphan rate | reorgs at honest-001 | forks seen | alt blocks added |
|---|---|---|---|---|---|---|
| stock s1 | 0.468 | 2136 | 0.004 | 2 | 18 | 22 |
| stock s2 | 0.469 | 2145 | 0.002 | 0 | 2 | 4 |
| sop s1 | 0.458 | 2151 | 0.003 | 63 | 82 | 97 |
| sop s2 | 0.482 | 2136 | 0.001 | 34 | 45 | 53 |

Revenue and chain quality are the same with SoP on or off: the third
miner's share is within one standard deviation of its hashrate in all four
cells (sd 0.011 at ~2,140 blocks), the main chain grows at the same rate,
the network orphan rate is 0.1-0.4% either way and the deepest split is 1
block in every cell. What SoP changes is tip churn: honest-001 switched
chains 63 and 34 times per 72 h under SoP against 2 and 0 on stock, with
three to twenty times as many forks seen and alt blocks stored. The weight
rule re-judges a natural fork as the competing block's shares arrive,
where the stock rule settles it on first-seen and never revisits; the
switches are all depth-1 and net out to the same orphan count, so the cost
is a node's view flipping for seconds during a race, not lost blocks. A
miner's block template follows those flips, which is the mechanism behind
the honest-side splitting seen in item 2 and the slow-miner question in
item 3.

### 2. Honest fragmentation, first N=4 point (10-28)

K=6 at alpha 0.47, the same seed and attacker (G=4) with the 5.3 h/s of
honest hashrate on one, two and four miners:

| honest miners | attacker share (alpha 0.47) | network orphan rate | main chain / 72 h |
|---|---|---|---|
| 1 (5.29 + 0.01) | 0.373, 0.382 (model 0.399) | 0.332, 0.342 | 2,000 |
| 2 (2.65 x 2) | 0.454, 0.436 | 0.385 | 1,950 |
| 4 (1.325 x 4) | 0.505, 0.507 | 0.386, 0.376 | 1,920, 1,938 |

At the DEFAULT window (K=3, the validated param a047 cell, G=6; 10-29
02:30Z): one honest miner 0.452 and 0.481 (mean 0.467) against 0.451 /
0.514 / 0.478 with two (mean 0.481) and the model's 0.477. At the default
window the one-miner and two-miner cells are within seed noise of each
other and of the model, unlike at K=6 (0.378 vs 0.445): the honest-side
splitting costs more the longer the window keeps a race subjective. The
four-miner cell at the default window (10-29 02:45Z) scored 0.549: the
same +0.07 step from two to four miners as at K=6. So with the honest
hashrate on four miners alpha 0.47 is clearly profitable at the default
window too, and the realistic four-pool threshold lies below 0.4635;
four-miner cells at 0.44 and 0.45 are queued to bracket it.

Each doubling of the honest miner count adds about 0.06 to the attacker's
share at K=6 and alpha 0.47: alpha 0.47 is unprofitable against one honest miner,
marginal against two and clearly profitable against four, at the window
that gave SoP its best threshold (K=6, 0.474 with two miners). The
default-window N=4 cell (lithium, due ~20:45Z) and the K=6 s2 give the
next two points; the N trend, not a single threshold, is the honest
headline.

#### The four-miner crossing (10-29, 14:16Z)

`sop_v4_param_h4_72h share_sop2_param_a045_s1`: the four-honest-miner
network (four pools of 1.375, attacker 4.5) with the default window at
alpha 0.45, one seed: share 0.449 (1,973 canonical blocks), honest to
three decimals; attacker orphan rate 0.380, network 0.371. The a044 cell
(20:45Z, same box and seed) gives 0.395, below honest by 0.045:

| alpha | four-miner share | share - alpha |
|---|---|---|
| 0.44 | 0.395 | -0.045 |
| 0.45 | 0.449 | -0.001 |
| 0.47 | 0.549 | +0.079 |

Linear interpolation on both sides puts the four-pool crossing at 0.450,
against 0.4635 measured with two honest miners (race model 0.469). One
seed per point; the two-miner seed spread at 0.47 was 0.06 in share, so
the crossing carries about 0.01 of uncertainty. For a network of four
equal pools the headline "attacker profits from 0.4635" reads "from
about 0.45", 0.013 lower; the direction is the one the K=6 window's
four-miner points (0.505 / 0.507 at 0.47) showed. Fragmentation of the
honest hashrate costs SoP a little of its margin, not much; eight miners
would say whether it keeps shrinking (owner's call, needs a bigger box).

### 6. The upper bound, first solve (10-28)

`scripts/sop_mdp.py solve --bound upper` (564b5ce5): the
Sapirshtein-Sompolinsky-Zohar over-paying MDP in SoP form (the module
docstring has the award and the argument). At caps 3/3/48/20/20 (7.98 M
states, 1.8 h for the lower bound, 2.6 h for the upper):

| alpha | lower bound (capped optimum) | upper bound (over-paying) | hand-written family |
|---|---|---|---|
| 0.45 | 0.4500 (honest; no reveal accepted) | 0.8036 | 0.389 (model), 0.273 (sims, stubborn) |
| 0.50 | 0.5000 (honest) | 1 (trivial: the walk is not transient at alpha >= 0.5) | 0.727 (model) |

The sandwich [0.45, 0.80] at alpha 0.45 brackets nothing useful: at 3
blocks per side the boundary is hit in most races, and the award at the
boundary is worth most of the race. SSZ's bounds were tight at T = 75 in a
block-only state space; this one is object-granular (one share at a time)
and 4 blocks per side is already 85 M states. The 4/4/64/24/24 upper solve
(below) shows how fast the gap closes with the cap, but a bound tight enough to test whether the family is near-optimal
needs the block-granular abstraction (shares as binned weights), which is
the next piece of model work if MRL wants it.

#### The 4-block cap (10-29, 20:40Z)

`solve --bound upper` with caps 4/4/64/24/24 at alpha 0.45 (85,108,639
states, 17.9 h on lithium): upper bound 0.7265. The action counts over the
decision pairs are hold 240 M, give up 8.9 M, publish 20 k, reveal 0: the
optimistic policy rides the boundary award rather than revealing, as at
3/3.

| caps (blocks per side) | lower bound | upper bound | gap |
|---|---|---|---|
| 3/3 | 0.4500 | 0.8036 | 0.354 |
| 4/4 | 0.4500 | 0.7265 | 0.277 |

One more block per side took 0.077 off the upper bound and 10x the
states; the sandwich at 0.45 is [0.45, 0.73] against a best-known
attacker of 0.39 (model) / 0.43 (sims, two miners). The next cap (5/5)
is about 850 M states and 120 GB of tables, beyond lithium and phantom
(the owner's 256 GB box could run it, for perhaps a 0.06 tighter bound).
The route to a bound that can say whether the family is near-optimal
remains the block-granular abstraction (shares as binned weights, caps
to 8 blocks per side at a few million states); days of model work,
owner's call.

### 5. Partial adoption, first cell (10-29)

`sop_v4_adopt_72h share_k2_a045_s1`: four equal honest miners (1.375 h/s
each), honest-001 and honest-002 on SoP, honest-003 and honest-004 on the
stock rule, relay-001 and seeds 1-3 SoP, relay-002 (vanilla monerod) and
seeds 4-6 stock, the validated param attacker at alpha 0.45.

| measured at honest-001 (SoP) | value |
|---|---|
| attacker share of the canonical chain | 0.998 (1,772 of 1,776 blocks) |
| network orphan rate | 0.547 |
| honest-001 / honest-002 blocks found | 537 / 521, almost all orphaned |
| honest-003 / honest-004 blocks found | 515 / 573, none on this chain |
| health | SPLIT 418 (deepest divergence, blocks) |

The network ran two chains for most of the 72 h. The halves diverged for
good at simulated 06:12 (height 1065 on the SoP side against 1062 on the
stock side, after three transient splits in the previous half hour), and
ended at height 2770 (difficulty 545) on the SoP side and 2615 (480) on the
stock side. The halves stayed connected at the P2P level: honest-001 kept
receiving the stock side's blocks (562 announcements after noon on day 1
against 9,049 from its own side) and honest-003 stored 1,890 of the SoP
chain's blocks as alternatives. honest-003 rejoined the SoP chain only in
three bulk syncs (125, 660 and 1,105 alternative blocks added in bursts at
the same hour of each day, 30 reorganizations in all, the last at day 3
09:42 to height 2352) and diverged again each time. No line in the stock
daemons' logs rejects a block.

Reading: the two rules settle a contested race differently. A SoP node
keeps the branch with the share weight, which with this attacker is the
attacker's; a stock node keeps the first block it saw, which is the honest
one. After a race the halves sit on different branches, the SoP half (the
attacker's 45 % plus two honest miners) outpaces the stock half (two honest
miners, whose difficulty then falls), and the stock half follows the
heavier chain only when its daemon's sync logic pulls it, which happened
once a day here rather than at the next block. Why the resync is that
rare is not established (monerod's chain-request path on a block with an
unknown parent; the vanilla relay-002 also logged 59,031 failed outbound
connections and "wrong network" handshakes against the sim binary, so the
stock half's fabric was its two miners and three seeds). What the cell
shows regardless of that detail: at 50 % adoption the honest side is split
into two 27.5 % halves, the attacker dominates the SoP chain outright and
the stock miners' blocks count on neither chain once they resync. The
remaining adoption cells say whether this is attacker-driven (honest_k2:
the same mixed network with no attacker) and how it scales (k1, k3, and
the all-stock k0 and all-SoP k4 references). Until those are in, the
deployment reading is provisional: a fork-choice change that half the
network runs is a split waiting for a race, and SoP would need a flag-day
rollout.

#### The no-attacker mixed network (10-30, 03:08Z)

`honest_k2_a045_s1`: the same 50 % split (honest-001 / 002, relay-001 and
seeds 1-3 on SoP; honest-003 / 004, relay-002 on vanilla monerod and
seeds 4-6 on the stock rule) with the attacker's node mining honestly at
4.5 of 10: one chain throughout. All 14 nodes end at height 3,138 on the
same block; 2,144 in-run blocks, network orphan rate 0.6 %, the honest
attacker node at 0.444 of blocks for 0.45 of hashrate. The health
check's split detector (tolerance 3 blocks) stays quiet, against 418
blocks of divergence in the attacker cell.

A mixed network does not drift apart on its own: with no withheld blocks
and no bridges there are no competing branches for the two rules to
disagree on (the 0.6 % of orphans are settled by the next block on both
rules). The split in the 50 % attacker cell is attacker-induced: an
attacker at 0.45 can hold the SoP half and the stock half on different
branches and owns the SoP half's chain (0.998). Reading: partial
adoption is safe without an attacker and an attack vector with one, so
SoP has to be deployed as a consensus-wide switch (a flag day, which is
how Monero ships hard forks anyway). The 25 % and 75 % cells with the
attacker (k1 running on phantom from 03:10Z, k3 queued) say whether a
SoP minority or majority is enough for the attacker to split.

#### Partial adoption with the attacker: worse than either rule alone (10-30)

Per-side shares, from each honest node's own final main chain (daemon
log; in-run blocks above the 994 preload; nodes on one side agree block
for block):

| adoption (SoP honest hashrate) | side | final height | attacker share | honest blocks kept | fork from the SoP side |
|---|---|---|---|---|---|
| 25 % (k1: honest-001 SoP, 1.375 of 10) | SoP | 2,746 | 0.906 | 165 of 1,752 | - |
| 25 % | stock (honest-002..004) | 2,750 | 0.858 | 250 of 1,756 | at 2,663 |
| 50 % (k2: honest-001 / 002 SoP, 2.75) | SoP | 2,770 | 0.998 | 4 of 1,776 | - |
| 50 % | stock (honest-003 / 004) | 2,615 | 0.836 | 266 of 1,621 | at 2,352 |

At 25 % adoption the network stayed on one chain until the last 87
blocks, and on it the attacker held about 0.88 of all blocks. With
alpha 0.45 the reference points are 0.449 with full SoP (four miners,
honest) and about 0.65 with the full stock rule (SM1): partial adoption
gave the attacker far more than either rule alone.

The mechanism is the split of the honest hashrate by rule. The SoP honest
miners weigh the attacker's share-carrying branches over the stock
miners' blocks, so they mine on the attacker's chain (and see their own
blocks reorganized away by its releases: honest-001 kept 7 blocks of the
~240 it found at 25 %); the attacker's chain then carries the attacker
plus the SoP miners, 5.9 of 10 at 25 % adoption, against 4.1 for the
stock miners, and wins on the stock rule too. At 50 % the attacker
(4.5) outweighs each honest half (2.75) on its own. The no-attacker
mixed cell stayed on one chain, so the split itself is attacker-induced.

Caveats: one seed per cell, 14 nodes, four honest miners, and alpha 0.45
above the larger honest group in both cells. At a lower alpha (0.30 to
0.35, below the stock group's hashrate) the attacker could not out-mine
the stock side, and whether the SoP minority still hands it a gain there
is untested; that and larger networks (owner 10-30) belong on the 256 GB
box. The 75 % cell (k3) is running on phantom. Reading for the proposal:
SoP must switch on network-wide at one height; a transition period with
mixed rules is worse than not deploying it.

### 4. The network-advantage attacker, first cell (10-29)

`sop_v4_gamma_72h share_sop_a045_f6_s1`: the validated param attacker at
alpha 0.45 on the v3 gamma topology: honest-001 beside the attacker's
bridge 2 at the hub, honest-002 beside the attacker and its bridge 1 on a
node 0.5 s away, the honest path between the two miners a 6 s chain of
relay hops (past SoP's 5 s rule), the attacker reading through whichever
bridge is ahead and publishing through both.

| | this cell (6 s honest path) | base topology (ms paths), same attacker, alpha 0.45 |
|---|---|---|
| attacker share | 0.699 (1,280 of 1,832) | 0.44 |
| attacker orphan rate | 0.176 | 0.64 |
| network orphan rate | 0.487 | 0.40 |
| honest-001 blocks kept | 272 of 1,030 | |
| honest-002 blocks kept | 280 of 990 | |
| realized gamma (analyzer) / ties | 0.173 / 81 | ~0 |

Eyal-Sirer's formula for the stock rule at alpha 0.45 with gamma 0.5 gives
0.68, so on this topology the SoP network gives the attacker what the stock
rule would. Mechanism, from the logs: honest-002's blocks reach the hub
after 6.0 s (857 of 990 through relay-slow-3) while the attacker's reply
to each of them, read from bridge 1 beside honest-002, reaches the hub
through bridge 2 in about a second; by the time the honest block arrives
it is more than 5 s behind the competing block at every hub node and
weighs 0. The same holds in the other direction, where honest-001's blocks
reached honest-002 by block relay only three times in 72 h (the rest only
through chain sync, after the attacker had already won the race). Each
honest half therefore loses nearly every contested block to an attacker
who is never late anywhere: both honest miners kept 27 % of their blocks.
The health flag is two "Sent invalid chain" peer events, not a split
(split depth 0); the attacker's parent feeding worked (52 feeds, no
tracebacks, 268 concessions).

The stock rule's reference on the same topology (10-29 08:40Z): the
depth-2 stubborn attacker at alpha 0.30 scored 0.249 (realized gamma
0.013, 2,032 blocks), below its hashrate, which is the gamma-zero stock
result and says the 6 s detour gives THIS attacker nothing: it reveals
only when strictly ahead on work and never races a tie, so a propagation
edge is irrelevant to it. The attacker Eyal-Sirer's gamma describes (SM1,
which reveals on a tie) is added to the spec at 0.30 and 0.35; the SoP
attacker above, by contrast, contests every honest block with share weight
within seconds, which is why the edge hurts under SoP and not here.

Provisional until two cells land: the same attacker with a 3 s honest
path (under the 5 s rule: if SoP's protection returns there, the collapse
is the lateness rule rather than connectivity itself), and the stock
rule's attacker at 0.45 on the 6 s path (the direct comparison; expected
near 0.68). If both come in as expected, the mitigation case has a hard
condition: SoP protects a network only where honest blocks reach every
miner within d of the attacker's, and a well-connected attacker turns the
rule's lateness penalty against honest miners whose propagation exceeds
d. The parameter d, which we have not varied, then becomes the central
design question.

### 3. The slow honest miner, first pair (10-29)

`sop_v4_slow_72h` l6: the no-attacker control (4.7 / 2.65 / 2.65, third
miner honest and connected) with honest-002 behind a chain of four 1.5 s
relay hops, 6 s one way, just past SoP's 5 s rule; stock and SoP, one seed
each. Blocks found and kept per miner (canonical chain of the connected
reference node, in-run blocks only):

| rule | honest-001 (fast) | honest-002 (6 s) | third miner (fast) | network orphan rate |
|---|---|---|---|---|
| stock | 594 of 601 kept, lost 7 (1.2 %) | 567 of 597, lost 30 (5.0 %) | 953 of 967, lost 14 (1.4 %) | 0.024 |
| SoP | 539 of 541, lost 2 (0.4 %) | 528 of 591, lost 63 (10.7 %) | 1,073 of 1,074, lost 1 (0.1 %) | 0.030 |

On the stock rule a 6 s link costs the slow miner 5 % of its blocks (its
blocks arrive 6 s late and it hears others' 6 s late, so about 7 % of them
meet a competitor and most of those lose on first-seen) and the fast
miners pay about 1 % each when the slow block happened to win. Under SoP
the slow miner loses twice as much, 10.7 %, and the fast miners almost
nothing: every race between a fast block and a slow one is settled for
the fast side, because the slow block is more than d behind at every fast
node and weighs 0, and the slow miner's own view of the fast block is
late too, so it keeps extending its own branch for a while. SoP moves the
whole cost of a slow link onto the slow miner and roughly doubles it. The
network as a whole loses slightly more (3.0 % against 2.4 %). One seed
each; the 3 s pair (under the rule, expected to match stock) and the 12 s
pair are queued. For a pool, 10 % of blocks at a 6 s propagation delay is
the number to weigh against the mitigation.

### 7. Tail emission, first rerun (10-29)

Every cell above ran on the stock emission schedule: the snapshot sits
where a block pays about 35.1 XMR, and the share is counted in blocks, so
the emission can only matter if a daemon's or an agent's behaviour depends
on the reward. The owner asked to test that assumption rather than assume
it. `sop_v4_param_tail_72h` reruns the headline cell (default window,
alpha 0.47, G=6 L=1 M=1 R=1 Z=1, seed 1) with
`general.emission: {mode: tail, from_height: auto}` on top of the original
spec (the matrix test asserts the two specs differ in nothing else). The
generator passed `--sim-tail-emission-height=1054` to all 12 daemons; the
daemon logs show every block from 1054 on paying 0.600 XMR (2,512 such
blocks) and only the preload paying 35.1.

| cell | emission | share | attacker orphan rate | network orphan rate | blocks |
|---|---|---|---|---|---|
| a047 s1 (10-26) | stock | 0.451 | 0.362 | 0.350 | ~1,950 |
| a047 s2 (10-26) | stock | 0.514 | 0.308 | 0.368 | |
| a047 s3 (10-26) | stock | 0.478 | 0.344 | 0.352 | |
| a047 s1 tail (10-29) | tail, 0.6 XMR | 0.508 | 0.301 | 0.353 | 1,948 |
| a046 s1 / s2 (10-26) | stock | 0.450 / 0.445 | 0.348 / 0.383 | 0.339 / 0.347 | |
| a046 s1 tail (10-29) | tail, 0.6 XMR | 0.449 | 0.351 | 0.341 | 1,992 |
| stock d2 a038 s1 / s2 (10-27) | stock | 0.402 / 0.382 | 0.189 / 0.224 | 0.223 / 0.222 | |
| stock d2 a038 s1 tail (10-30) | tail, 0.6 XMR | 0.404 | 0.202 | 0.232 | 2,028 |
| stock d2 a036 s1 (10-28) | stock | 0.352 | 0.233 | 0.216 | |
| stock d2 a036 s1 tail (10-30) | tail, 0.6 XMR | 0.350 | 0.243 | 0.220 | 2,026 |
| one honest miner, a047 s1 / s2 (10-28) | stock | 0.452 / 0.481 | 0.372 / 0.312 | 0.357 / 0.338 | |
| one honest miner, a047 s1 tail (10-30) | tail, 0.6 XMR | 0.472 | 0.331 | 0.351 | 1,985 |
| four honest miners, a047 s1 (10-28) | stock | 0.549 | 0.275 | 0.391 | |
| four honest miners, a047 s1 tail (10-30) | tail, 0.6 XMR | 0.576 | 0.265 | 0.383 | 1,909 |
| no attacker, SoP, s1 / s2 (10-28) | stock | 0.458 / 0.482 | 0.002 / 0.002 | 0.003 / 0.001 | |
| no attacker, SoP, s1 tail (10-30) | tail, 0.6 XMR | 0.468 | 0.003 | 0.002 | 2,128 |
| no attacker, stock, s1 / s2 (10-28) | stock | 0.468 / 0.469 | 0.002 / 0.002 | 0.004 / 0.002 | |
| no attacker, stock, s1 tail (10-30) | tail, 0.6 XMR | 0.462 | 0.002 | 0.001 | 2,158 |

The a047 tail rerun sits inside the stock cells' seed spread (0.451 to
0.514, mean 0.481) on every column, and the a046 tail rerun (19:43Z)
matches its stock cells to 0.005 on share and orphan rates; the stock
rule's depth-2 attacker at 0.38 (00:17Z 10-30) reruns at 0.404 against
0.402 / 0.382, and at 0.36 (00:50Z) at 0.350 against 0.352 (the health
column flags the share term as inert in that cell, which on a stock
network it is by construction). The one-honest-miner cell at 0.47
(02:35Z) reruns at 0.472 against 0.452 / 0.481, and the four-miner cell
(03:25Z) at 0.576 against 0.549, the largest gap so far and still inside
a two-seed spread of 0.06. Same seed as the stock s1 cell, but the
emission change alters every block hash, so this is a fourth sample, not
a paired comparison. No sign that the emission schedule touches the
result, as expected for a block-counted share. All eight are in (10-30 07:31Z): every tail cell lands inside its
stock-emission cells' seed spread, on share and on both orphan rates,
across the param attacker, the stock d2 attacker, one / two / four honest
miners and both no-attacker controls. The emission schedule does not
touch these results; the question is closed.

#### The stock comparison at 0.45 (10-29, 13:12Z)

`d2_stock_a045_f6_s1`: the stock reference attacker (window_stubborn,
give up two behind, weigh difficulty) on the stock fork rule at the same
alpha and the same 6 s topology, bridges and all:

| | stock rule, d2 attacker (this cell) | SoP, param attacker (above) |
|---|---|---|
| attacker share | 0.522 (2,015 canonical blocks) | 0.699 |
| gamma (ties won through the bridges) | 0.000 | 0.173 |
| attacker orphan rate | 0.152 | 0.176 |
| network orphan rate | 0.260 | 0.487 |
| base topology, same attacker and rule | ~0.51 model (0.492 at 0.44), 0.528 give-up-5 cells | 0.44 |

The stock number is the base-topology number. The d2 attacker never races
a tie (gamma 0.000: it withholds until it leads and reveals from ahead),
so bridges beside the miners and a 6 s honest path give it nothing; the
stock first-seen rule only rewards a propagation advantage to an attacker
that publishes into ties. Under SoP the same path lifts the attacker from
0.44 to 0.699 without racing: every honest block is late at the far
miner, weighs 0 there, and the attacker's reply (delivered at 0 s by the
bridge) wins the weighing. On this topology SoP hands its attacker 0.18
more than the stock rule hands the stock reference attacker.

The like-for-like stock comparison is a tie-racing attacker on the stock
rule at 0.45 on this path (arm `es`, SM1), added to the spec and queued
next on box80; with honest-002 (half the honest hashrate) always hearing
the attacker's reply first, gamma is about 0.5 and the Eyal-Sirer formula
gives 0.68. If it measures near 0.68, SoP on a 6 s-path network gives a
non-racing attacker what the stock rule gives only a racing one, and the
honest side keeps nothing of SoP's protection; if it measures below, SoP
is strictly worse than the stock rule there. The 3 s cell (box81) still
decides whether the mechanism is the 5 s lateness rule.

#### The stock gamma reference at 0.30 (10-29, 14:45Z)

`es_stock_a030_f6_s1`: the Eyal-Sirer SM1 attacker (withhold at lead 1,
publish into the tie, reveal all when the lead drops to one) on the
stock rule, alpha 0.30, the same 6 s topology and bridges: share 0.303
(2,044 canonical blocks), attacker orphan rate 0.235, network 0.249. The
SM1 formula gives 0.273 at gamma 0 and 0.327 at gamma 0.5; 0.303 is an
effective gamma of 0.28: the bridges steer part of the honest hashrate
onto the attacker's tie block, but less than the half the topology was
built for (honest-002 hears the attacker's reply about 2 s after the
agent reads honest-001's block through bridge 2, and honest-001's block
6 s later; why that yields 0.28 rather than 0.5 is left open). The
attacker did withhold: an honest miner at the hub loses about 1 % of its
blocks (item 3), this one lost 23.5 %. The reveal audit and the gamma
column read 0 for this arm because they parse the param_stubborn log
lines only; for SM1 cells read the share and the orphan rates. At 0.45
the formula gives 0.67 at gamma 0.28 and 0.68 at 0.5, so the 0.45 cell
(box80, 14:48Z) says whether SoP's 0.699 matches the best stock attacker
on this path or exceeds it.

#### The 3 s path (10-29, 15:30Z): the mechanism is the lateness rule

`share_sop_a045_f3_s1`: the same attacker, alpha and bridges, with
relay-slow-1 peering with the hub directly so the honest path between the
two miners is 3 s (two 1.5 s hops), inside SoP's 5 s rule:

| honest path | SoP attacker share | attacker orphan rate | network orphan rate | gamma (ties through bridges) |
|---|---|---|---|---|
| ms (base topology, a045 s1 / s2) | 0.431 / 0.378 | 0.374 / 0.413 | 0.331 / 0.316 | - |
| 3 s (this cell) | 0.486 (1,932 blocks) | 0.327 | 0.397 | 0.175 |
| 6 s | 0.699 | 0.176 | 0.487 | 0.173 |

Inside the rule the attacker gets 0.486: about 0.07 over the base
topology, which is what bridges beside both miners buy on any rule (they
steer ties; gamma is the same 0.175 as on the 6 s path), while the honest
blocks, late at the far miner but by less than d, keep their weight and
SoP's weighing still beats the attacker. Past the rule the same attacker
gets 0.699. The difference is the lateness rule alone: on the 6 s path the
far miner sees the attacker's bridged reply first and the honest block
more than d later, so the honest block weighs 0 there and the attacker's
reply wins every weighing (verified from the logs for the 6 s cell).

Reading for the mitigation case: SoP protects against a propagation-
advantage attacker as long as the honest network's own propagation, as
seen against the attacker's fastest reply, stays inside d. Where it does
not, SoP turns the honest delay into a gift for the attacker: +0.26 at
alpha 0.45 for a 6 s path, from a rule whose base-topology effect is
-0.08 against the stock reference. The stock rule on the same path gives
its non-racing reference attacker nothing (0.522, item above) and the
tie-racing SM1 attacker about 0.68 by formula (cells at 0.45 on both
paths running). That makes d the central design parameter: it must clear
the honest network's worst propagation delay with margin, and raising it
weakens the share weighting (a share counts only if seen more than d
before the block). A d sweep (5 / 10 / 20 s) on this topology and the
slow-miner topology is the experiment that settles it (owner's call).

#### The stock like-for-like at 0.45 (10-29, 19:04Z)

`es_stock_a045_f6_s1`: the SM1 attacker on the stock rule at alpha 0.45,
same 6 s topology and bridges: share 0.649 (1,936 canonical blocks),
attacker orphan rate 0.109, network 0.385. The SM1 formula gives 0.652 at
gamma 0 and 0.681 at gamma 0.5, so at this alpha the bridges' tie
steering is worth nothing measurable (at 0.30 it read as gamma 0.28); a
tie-racing attacker at 0.45 on the stock rule gets about 0.65 on this
path and would get the same on the base topology.

The best known attacker under each rule, alpha 0.45:

| honest path | stock rule (SM1) | SoP (param attacker) |
|---|---|---|
| ms (base topology) | ~0.65 (formula, gamma 0; give-up-5 stubborn cells 0.528) | 0.44 |
| 3 s | 0.671 (20:04Z; formula 0.652 at gamma 0, 0.681 at 0.5) | 0.486 |
| 6 s | 0.649 | 0.699 |

Inside d SoP is worth 0.19 to 0.21 of attacker share against the stock
rule's best attacker (0.671 vs 0.486 on the 3 s path, ~0.65 vs 0.44 on
the base topology); past d it is worth -0.05, and against the non-racing
attacker class -0.18 (0.522 stock vs 0.699). The 3 s SM1 cell (1,900
canonical blocks, attacker orphan rate 0.113, network 0.399) carries six
invalid-chain warnings in the health column, like the two in the 6 s SoP
cell: parent-feeding submissions, not a chain fault.
The honest mechanism is unchanged by this cell: the lateness rule, not a
tie race, is what the 6 s path hands the SoP attacker.

#### SM1 at 0.35, and what the SM1 points say about the bridges (10-30, 06:48Z)

`es_stock_a035_f6_s1`: 0.338 (2,005 blocks, attacker orphan rate 0.230).
Against the Eyal-Sirer SM1 formula:

| alpha, path | measured | formula, gamma 0 | formula, gamma 0.5 |
|---|---|---|---|
| 0.30, 6 s | 0.303 | 0.273 | 0.327 |
| 0.35, 6 s | 0.338 | 0.367 | 0.416 |
| 0.45, 6 s | 0.649 | 0.652 | 0.681 |
| 0.45, 3 s | 0.671 | 0.652 | 0.681 |

All four sit within 0.03 of the gamma-0 formula, two above and two below,
which is one-seed noise. The reading of the 0.30 cell as "effective gamma
0.28" (above) does not survive this point: the bridges give the stock
tie-racer no measurable tie advantage, although the topology delivers the
attacker's tie block to the far miner seconds before the honest one
(check_paths). Why is not established; the attacker agent's reaction time
(it polls its bridges once per agent tick) is the first suspect. It does
not change the comparison with SoP: a stock tie-racer at gamma 0.5 would
reach 0.68 at 0.45, still below SoP's 0.699 on the 6 s path.

#### SoP on the 6 s path at 0.40: the advantage has a threshold (10-30, 16:39Z)

`share_sop_a040_f6_s1`: the same param attacker, bridges and 6 s honest
path at alpha 0.40: share 0.385 (1,921 blocks), attacker orphan rate
0.415, network 0.382. Below honest. The SM1 formula on the stock rule
gives 0.484 at 0.40 with gamma 0.

| alpha | SoP, 6 s path | SoP, base topology | stock SM1 (formula, gamma 0) |
|---|---|---|---|
| 0.40 | 0.385 | (below the 0.4635 crossing) | 0.484 |
| 0.45 | 0.699 | 0.44 | 0.652 (0.649 measured) |

The lateness gift needs enough hashrate to exploit: at 0.40 the attacker
still loses most races it opens (orphan rate 0.415) and SoP beats the
stock rule's tie-racer by 0.10; at 0.45 it wins them and SoP is 0.05
worse than stock. So "past d, SoP is worse than stock" holds at the top
of the alpha range only, between 0.40 and 0.45 on this topology. One
seed; the 0.35 point on the 6 s path and the 0.35 / 0.40 points on the
3 s path are running (10-30 17:39Z).

#### The slow miner at 3, 6 and 12 s (10-30)

Same method as the 6 s pair (blocks found per miner from the daemons'
"Found block" lines, kept = in-run blocks on honest-001's final chain;
the l6 rows reproduce the earlier counts exactly):

| honest path to the slow miner | rule | slow miner lost | fast miners lost | network orphan rate |
|---|---|---|---|---|
| 3 s (inside d) | stock | 25 of 570 (4.4 %) | 0.3 % / 0.3 % | 0.014 |
| 3 s (inside d) | SoP | 15 of 575 (2.6 %) | 0.5 % / 0.7 % | 0.011 |
| 6 s (past d) | stock | 30 of 597 (5.0 %) | 1.2 % / 1.4 % | 0.024 |
| 6 s (past d) | SoP | 63 of 591 (10.7 %) | 0.4 % / 0.1 % | 0.030 |
| 12 s | stock | 79 of 567 (13.9 %) | 1.5 % / 2.4 % | 0.051 |
| 12 s | SoP | 154 of 594 (25.9 %) | 0.0 % / 0.2 % | 0.068 |

The lateness rule is a cliff at d. Inside it, SoP costs the slow miner
nothing extra (2.6 % against 4.4 % on stock, within one-seed noise or
slightly better); just past it, SoP doubles the slow miner's loss and
takes it off the fast miners. On the stock rule the loss grows smoothly
with the delay (4.4, 5.0, 13.9 %). The 12 s SoP cell (10-30 23:49Z) answers
whether the penalty past d saturates: it does not. The slow miner loses
25.9 % of its blocks against 13.9 % on stock, again about twice the stock
loss, and the fast miners lose nothing. Past d, SoP doubles whatever a
slow link already costs and moves all of it onto the slow miner. One
seed per cell.

#### 75 % adoption, and why the stock side falls away (10-30, 17:46Z)

`share_k3_a045_s1` (honest-001..003 on SoP, honest-004 alone on the stock
rule; attacker 4.5 of 10):

| side | final height | attacker share | honest blocks kept | fork from the SoP side |
|---|---|---|---|---|
| SoP (honest-001..003) | 2,767 | 0.883 | 207 of 1,773 (64 / 71 / 72) | - |
| stock (honest-004) | 2,383 | 0.755 | 340 of 1,389 (172 its own) | at 2,209 |

The attacker again holds about 0.88 of the majority chain. With full
adoption (four SoP miners) the same attacker scored 0.449; removing one
pool of 1.375 from the SoP side leaves 4.125 of honest SoP hashrate
against the attacker's 4.5. All three partial-adoption cells share that
shape: the attacker outweighs whichever honest group it fights.

The stock side does not merely lose races, it drops off the network. The
lone stock node logged "Host relay-001 blocked" at 01:25 and "Host
honest-003 blocked" at 01:48 on day 1, then resynced from 4.8 hours
behind at 01:25 on day 2 and from 6.4 hours behind on day 3: monerod's
24 h peer block. A stock node scores a peer whose chain height drops,
and under SoP a node legitimately reorganizes to a branch with fewer
blocks and more share weight. The SoP patch already stops SoP nodes from
scoring this (stubborn_h10_banlog, 10-07: it banned honest peers for
24 h); stock nodes still do, so in a mixed network they block their SoP
peers, sit isolated for a day, resync, and block again. That is the
"daily resync bursts" left unexplained in the first 50 % cell. Without
an attacker the SoP nodes rarely reorganize to fewer blocks, so the
no-attacker mixed cell never split.

Consequence for deployment: a SoP switch needs every node, not only the
miners, to run the changed peer scoring, or stock nodes will partition
themselves from the SoP network during any attack. The flag day is
required for the relays as much as for the pools. Caveats as before (one
seed, 14 nodes, alpha 0.45 above each honest group).

### 8. Propagation on the owner's stressnet nodes (10-30)

Owner 10-30: "read the stressnet node logs". The owner runs two testnet
stressnet monerod nodes (phantom and lithium, same LAN, both
NTP-synchronized, logging blockchain:INFO and --show-time-stats). Read
read-only; parsed on each box; joined by block hash. Window 10-19 00:00Z
to 10-30 19:26Z: 8,432 blocks both nodes added live (heights 3,112,648
to 3,121,084, 283 h). Phantom added the block first in 80 % of cases.

| measure | median | p90 | p99 | max |
|---|---|---|---|---|
| gap between the two nodes adding a block | 25 ms | 39 ms | 946 ms | 542 s |
| block processing time, phantom | 21 ms | 25 ms | 43 ms | 388 ms |
| block processing time, lithium | 17 ms | 22 ms | 36 ms | 6.8 s |
| block weight | 237 B | 328 B | 382 kB | 1.68 MB |

Processing grows with weight but stays small: 1-1.7 MB blocks took 68-113
ms per node (6 such blocks). Of the 40 gaps over 1 s, 13 of the 14 over
10 s are one lithium stall (10-21 22:12-22:48Z, 35-542 s behind for 13
consecutive blocks) and 7 are one burst (10-30 18:05:56Z, phantom added
blocks 3,121,050-056 at the same millisecond, lithium 2.8 s later). The
rest are isolated: 5 blocks (0.06 %) more than 5 s apart (6.7, 6.8, 7.8,
8.7, 22.1 s), all of them nearly empty, so path, not size. Orphans: 6
alternative blocks on phantom, 2 on lithium, 1 reorganization each in
8,438 blocks. Transaction load came in bursts (pool additions in 1,550 of
the window's 16,980 minutes, median 10 per active minute, peak 549).

What this does and does not say for d. Two well-connected nodes on one
LAN see the same block within tens of milliseconds, verification is not
the bottleneck even for 1.7 MB blocks on these CPUs, and a gap past 5 s
between them is a rare event (0.06 % of blocks) that is not tied to
block size. It is a lower bound on the network's spread, not a
measurement of it: two neighbours, not the far edge of the network from
the finder. Missing-transaction round trips are not logged at these log
levels. The stressnet nodes also run a monitoring sidecar that pushes
each node's block events, with timestamps, to a collection hub; if the
hub operator can share them, those are the multi-node arrival times d
should be set against.

#### Why the stock tie-racer got no tie advantage: it answers ties too slowly (10-30)

From the daemon logs of the SM1 cells: for every height with both an
attacker block and an honest block, when each honest miner first saw each
block (first log line naming the hash; the honest block reaches the far
miner at exactly 6.0 s on f6 and 3.0 s on f3, as check_paths shows).
Ties the attacker answered within 10 s of the honest find:

| cell | ties answered within 10 s | far miner saw the attacker's block first | attacker block at the far miner, median after the honest find |
|---|---|---|---|
| SM1, 0.30, 6 s | 339 | 0.62 | 9.2 s (all contested heights) |
| SM1, 0.35, 6 s | 344 | 0.55 | 11.0 s |
| SM1, 0.45, 6 s | 272 | 0.61 | (most heights are lead releases) |
| SM1, 0.45, 3 s | 227 | 0.03 | |
| SoP param, 0.45, 6 s | 16 of 1,207 contested | 0.50 | |

Counting only fluffy-block receipts, the attacker's tie answers took a
median 4.5 to 5 s from the honest find. A real attacker with nodes beside
both pools answers in well under a second; ours answers in about 5 s,
slower than the 3 s honest path and barely faster than the 6 s one, so it
steers the far miner in about 60 % of its tie races on the 6 s path and
almost never on the 3 s path. The likely cause is the agent's polling
cycle, several RPC calls per tick, some of them across the 0.5 s link to
bridge 2 (not verified; a block-notification subscription instead of
polling would remove it).

Consequences. The measured stock tie-racer (0.649 at 0.45, 6 s; 0.671 on
3 s) understates a fast one; the SM1 formula at gamma 0.5 (0.681) is the
better stock reference. Past d, SoP's 0.699 against that 0.68 is a wash
rather than 0.05 worse; inside d, 0.486 against 0.68 is still about 0.2
better. The SoP attacker's gain does not depend on tie speed: it answered
16 of 1,207 contested heights as ties and wins by publishing leads early,
so the honest block at that height trails its block by more than d at the
far miner. The receipt proxy (first log mention) and the 10 s tie window
are judgement calls.

#### The alpha ladder on both paths (10-30, 22:50Z)

SoP param attacker vs the stock rule's tie-racer (SM1) on the same
topology, bridges beside both honest miners, one seed per cell:

| alpha | SoP, 3 s path (inside d) | SoP, 6 s path (past d) | stock SM1 measured, 3 s / 6 s | SM1 formula, gamma 0 / 0.5 |
|---|---|---|---|---|
| 0.30 | (not run) | (not run) | - / 0.303 | 0.273 / 0.327 |
| 0.35 | 0.175 | 0.209 | 0.363 / 0.338 | 0.367 / 0.416 |
| 0.40 | 0.246 | 0.385 | (not run) | 0.484 / 0.526 |
| 0.45 | 0.486 | 0.699 | 0.671 / 0.649 | 0.652 / 0.681 |

Inside d SoP holds the attacker far below honest up to 0.40 and near
honest at 0.45, against a stock attacker that profits from 0.35 on. Past
d the slow honest path costs SoP 0.03 of attacker share at 0.35, 0.14 at
0.40 and 0.21 at 0.45, and only at 0.45 does SoP fall to the stock
rule's level (0.699 against 0.65-0.68). Read with the reaction-time
finding (the stock tie-racer answers too slowly, so the gamma-0.5
formula column is the better stock reference): past d, SoP still beats
the stock rule by 0.15-0.2 at 0.35-0.40 and ties it at 0.45. The 6 s
honest path is a large, not a fatal, loss for SoP below 0.45. The d sweep
(running) tests whether a larger d removes it.

### 9. The lateness delay d (10-31)

Owner 10-30: does a larger d take away SoP's cost on slow and badly
connected honest miners, and what does it give the attacker? Ten cells,
each its source spec's d = 5 cell plus `--sim-sop-delay-s` 10 or 20 on
every SoP daemon and nothing else (pinned by
test_dsweep_specs_differ_from_their_d5_cells_only_in_the_delay): the slow
miner at 6 s and 12 s, the 6 s honest path at alpha 0.45, and the param
attacker at 0.45 and 0.47 on the headline topology. One seed per cell.

#### The param attacker at d = 10 and 20 (10-31, all four cells)

| alpha | d | share | d = 5, same cell, seeds 1 / 2 / 3 |
|---|---|---|---|
| 0.47 | 10 s | 0.483 | 0.451 / 0.514 / 0.478 (mean 0.481) |
| 0.47 | 20 s | 0.506 | (same) |
| 0.45 | 10 s | 0.393 | 0.431 / 0.378 (s1 / s2, mean 0.405) |
| 0.45 | 20 s | 0.398 | (same) |

All four inside the d = 5 seed spread (0.063 wide at 0.47, 0.053 at 0.45),
so one seed per d cannot separate d = 10 or 20 from d = 5 on the
attacker's side: on the headline topology a longer d neither helps nor
visibly hurts against this attacker; d = 10's gamma 0.116 and orphan rates 0.330 / 0.333 sit inside the
d = 5 seeds too. Shadow runs are
not reproducible, so "seed 1" at d = 20 is not a paired draw of d = 5's
seed 1. d = 20: gamma 0.158, attacker orphans 0.306, network orphans 0.352
(d = 5 seeds: 0.12-0.15, 0.31-0.36, 0.35-0.37); health ok, no stuck time. A
0.03 effect of d on the attacker would need about four seeds per d.

#### The slow miner at d = 10 and 20 on the 6 s path (05:19Z, 13:50Z)

The slow honest miner on the 6 s path (alpha 0.47 attacker mining
honestly, all 19 daemons logging `delay_ms=10000` / `20000`, against 5000
in the d = 5 cell):

| rule | slow miner's blocks lost | lost with the winner found first | lost although found first | of those, gap > 20 s |
|---|---|---|---|---|
| stock | 30 / 597 (5.0 %) | 18 | 12 | 1 |
| SoP d = 5 | 63 / 591 (10.7 %) | 35 | 28 | 24 |
| SoP d = 10 | 67 / 600 (11.2 %) | 34 | 33 | 27 |
| SoP d = 20 | 62 / 576 (10.8 %) | 33 | 29 | 24 |

A 10 s delay covers the 6 s path, yet the loss does not move, so the
lateness rule is not what costs the slow miner. The excess over stock
(33 and 37 blocks) sits almost entirely in losses more than 20 s from the
winning block: the slow node stays on a branch the rest of the network
has left, for longer than d plus the path latency. On the 3 s path SoP
loses fewer blocks than stock (15 against 25, none of them long), and on
the 12 s path 67 of SoP's 154 losses are long against 19 of stock's 79.
No node blocked a peer. Not yet checked: why the slow node diverges; a
guess is that it scores the competing branches' embedded shares by its
own late receipt times and so disagrees with the network about which is
heavier. Script: .claude/campaign9/analysis/slow_forks.py (lost blocks
against the main-chain block at the same height, by found time).

#### The network-advantage attacker at d = 10 and 20 (05:40Z, 05:50Z)

SoP attacker at alpha 0.45, bridges beside both honest miners, 6 s honest
path (16 daemons logging `delay_ms=10000` and `20000`):

| d | attacker share | gamma | attacker orphans | network orphans |
|---|---|---|---|---|
| 5 s (6 s path) | 0.699 | 0.852 | 0.176 | 0.487 |
| 10 s | 0.763 | 0.885 | 0.134 | 0.470 |
| 20 s | 0.746 | 0.881 | 0.136 | 0.488 |
| 5 s, 3 s path (reference) | 0.486 | 0.743 | 0.327 | 0.397 |

A delay that covers the 6 s path does not bring the attacker down toward
the 3 s path's 0.486; both longer delays sit 0.05-0.06 above d = 5 and
above the stock tie-racer (0.649 measured, 0.681 formula at gamma 0.5).
One seed each, inside about one d = 5 seed spread of the param cells, so
"no better" is the safe reading and "worse" is not established. A longer d
also widens the attacker's own grace: its block is late only when first
seen more than d after the honest block at its height (not checked in
these logs). Health INVALID-CHAIN 1 in both, as in the d = 5 cells (see
(a) above).

#### Why d does not help the slow miner: lateness compounds along the relay chain

Every node judges lateness by its OWN first sight of a block, and monerod
forwards a received block only when it lands on the forwarding node's main
chain (`cryptonote_protocol_handler.inl:735-739` at the pinned ref:
`else if (bvc.m_added_to_main_chain) ... relay_block`). On the slow
miner's path, seven relays in a line, a competing block therefore moves
one hop only after that hop has switched to it. Under SoP a hop that saw
the competitor late scores it 0 and keeps its own block, so the
competitor reaches the far end minutes after the block it competes with,
not 6 s after. SIM-SoP-DEC records, competing (alt) blocks per node,
lag = first seen minus the main block's first sight at that height
(script .claude/campaign9/analysis/sop_dec_lag.py):

| node | d = 5, 6 s path: late (> d) / p90 lag / KEEP over a longer alt | d = 10, 6 s path | d = 5, 3 s path |
|---|---|---|---|
| honest-001 (fast) | 6 / 6.6 s / 2 | 3 / 9.8 s / 3 | 3 / 4.1 s / 4 |
| relay-chain-1 (near) | 7 / 7.5 s / 5 | 5 / 8.6 s / 12 | 2 / 2.9 s / 1 |
| relay-chain-4 (middle) | 35 / 399 s / 39 | 42 / 471 s / 42 | 7 / 442 s / 13 |
| relay-chain-7 (far) | 37 / 591 s / 42 | 43 / 670 s / 52 | 7 / 650 s / 13 |
| honest-002 (slow miner) | 41 / 355 s / 44 | 45 / 445 s / 49 | 9 / 134 s / 10 |

From the middle of the chain on, the competing blocks that matter arrive
hundreds of seconds late, so no d that keeps SoP's protection covers them;
d = 10 changes nothing. The cascade needs a run of hops that all kept the
other block, which a line of relays guarantees and a well-meshed network
mostly avoids; how often real Monero nodes sit behind such a run is not
measured here (the stressnet propagation data, item 8, is about blocks
nobody contests). The `--sim-sop-seen-at-notify` knob would not help: the
fluffy block itself only arrives when the upstream hop relays it. A fix
would have to forward competing blocks at the tip height whatever the
local fork choice, or judge lateness by something other than local first
sight.

#### The slow miner at d = 10 and 20 on the 12 s path (11:50Z, 13:40Z)

| rule (12 s path) | slow miner's blocks lost | lost, gap > 20 s | late alt blocks (> d): relay-chain-4 / relay-chain-7 / slow miner | p90 lag at relay-chain-7 |
|---|---|---|---|---|
| stock | 79 / 567 (13.9 %) | 19 | - | - |
| SoP d = 5 | 154 / 594 (25.9 %) | 67 | 53 / 118 / 131 | 510 s |
| SoP d = 10 | 161 / 624 (25.8 %) | 79 | 41 / 101 / 127 | 406 s |
| SoP d = 20 | 107 / 569 (18.8 %) | 41 | 19 / 70 / 79 | 429 s |

On the 12 s path a 20 s delay takes back about two fifths of SoP's excess
loss over stock (12.0 points down to 4.9), all of it from fewer cascades:
fewer hops judge the competitor late, but the far end still sees 70-79
competing blocks late by minutes. d = 10, below the path latency, changes nothing
(25.8 %). One seed per cell (all 19 daemons logging `delay_ms=10000` and
`20000`); with the 6 s path at d = 10 also showing no relief, a longer d
buys some protection back at best partly and only in some cells, and
never removes the cascade.

#### The d sweep in one table

| cost of SoP | d = 5 | d = 10 | d = 20 | stock rule |
|---|---|---|---|---|
| slow miner's blocks lost, 6 s path | 10.7 % | 11.2 % | 10.8 % | 5.0 % |
| slow miner's blocks lost, 12 s path | 25.9 % | 25.8 % | 18.8 % | 13.9 % |
| network-advantage attacker share, 6 s path, alpha 0.45 | 0.699 | 0.763 | 0.746 | 0.649 measured, 0.681 formula |
| param attacker share, alpha 0.45 | 0.405 (2 seeds) | 0.393 | 0.398 | (above 0.45) |
| param attacker share, alpha 0.47 | 0.481 (3 seeds) | 0.483 | 0.506 | (above 0.47) |

A longer d does not undo SoP's costs on badly connected honest miners: the
6 s path's loss stays at about twice stock's at every d, and only the
12 s path at d = 20 recovers part of it (a single seed). The reason is
the lateness cascade (above): the competing blocks that cost the slow
miner arrive minutes late, not d late. On the headline topology d moves
the param attacker by less than the seed spread; with a network advantage
a longer d gives the attacker as much or more. One seed per d cell
throughout; the second seeds of the d = 5 slow and gamma cells are queued
(10-31) and will show the d = 5 spread those columns lack.

### 10. Partial adoption at alpha 0.30 (10-31)

The 50 % adoption cell (k2: honest-001/002 and their side on SoP,
honest-003/004 on the stock rule) with the attacker at alpha 0.30
instead of 0.45, 14 nodes, one seed:

| chain as seen by | attacker share | blocks by h001 / h002 / h003 / h004 | tip |
|---|---|---|---|
| honest-001 / 002 (SoP side) | 0.461 (787 of 1,706) | 456 / 448 / 7 / 8 | 2700 |
| honest-003 / 004 (stock side) | 0.437 (744 of 1,702) | 439 / 436 / 45 / 38 | 2696, forked at 2622 |

The split does not need a strong attacker: at 0.30 it still lifts the
attacker to 0.44-0.46 of either side's chain, and the stock-rule honest
miners lose nearly all their blocks (15 of their blocks on the SoP side's
chain, 83 on their own side's). Each stock-side honest node logged 21
"Host ... blocked" (the 24 h height-drop ban, see the adoption mechanism
above); no SoP-side node did. Health flag SPLIT 78. The stock-only
reference at 0.30 (d2_k0_a030_s1) and 25 % adoption (k1) are queued and
the --sim-no-drop-score mechanism cell runs tonight. Script:
.claude/campaign9/analysis/split_shares_arg.py <run dir>.

The 25 % adoption cell (k1: only honest-001 on SoP; every honest miner at
hashrate 1.75, attacker 3.0, so alpha 0.30) went the other way:

| chain (all four honest nodes agree, tip 2942) | attacker | h001 (SoP) | h002 / h003 / h004 (stock) |
|---|---|---|---|
| blocks | 0 of 1,948 | 284 | 548 / 542 / 574 |

No split: the stock majority's chain wins everywhere, every attacker block
is orphaned (attacker orphan rate 1.000), and the lone SoP honest miner
keeps about half the blocks its equal-hashrate stock peers keep. The three
stock honest nodes logged 6 "Host ... blocked" each. At 0.30 the minority
SoP node, not the attacker, pays for partial adoption; at 0.45 the same
cell gave the attacker about 0.88 (split). Either way partial adoption is
worse than none for someone.
