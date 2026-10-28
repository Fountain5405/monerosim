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
headline's stock figure (d=2, 0.365) has not been simulated; it is the
same attacker family in a model the d=5 cells validate. The textbook
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
| 0.38 | 0.402, 0.382 | 0.392 | 0.390 | 122.5 / 123.7 | 0.207 / 0.193 | 0.223 / 0.214 |

The sims cross at 0.370 by interpolation (the model at 0.365); as with
give-up depth 5, the sims' curve is a little steeper than the model's
(-0.018 at 0.34, +0.002 at 0.38). The headline comparison holds in
Shadow: the best attacker found needs about 0.370 of the hashrate on the
stock network and 0.4635 under SoP, a rise of about 0.094 (model 0.103).
A 0.36 cell (model 0.357) checks the straight line at the crossing.

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
against the model's 0.014 and 0.012. A K=2 cell at 0.45
(sop_v4_window_k2_a045_72h, model 0.438 with G=2; launched 20:54Z)
brackets the K=2 crossing directly. The
K=6 excess is the one open point; sop_v4_window_k6_a048_72h (K=6 at
0.48 with G=8, the model's break-even at 0.476; two seeds, launched
18:41Z) tests it directly: the excess would put the attacker near 0.52.

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
honest blocks; at K=2 the gap is 0.4 objects per block. A candidate cause
the model (one honest miner, no propagation) cannot produce: honest shares
still in flight, or mined on a stale tip, when a node judges or a block is
built. Such a loss grows with race length, as the excess does (K=2 +0.006,
default +0.018, K=6 +0.046); not yet tested.

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
