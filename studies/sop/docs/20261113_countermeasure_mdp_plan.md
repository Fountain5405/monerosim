# Countermeasure MDPs: survey of the reference code and plan (2026-11-13)

Status: current plan. 2026-11-16: the code moved to
<https://github.com/Fountain5405/pow-countermeasure-mdp> (GPL-3.0); code paths
below (`studies/sop/countermeasures/...`) refer to monerosim at `e093a4d7`. It follows Rucknium's "Research directions for selfish
mining countermeasures in Monero"
(<https://gist.github.com/Rucknium/0b6e94811099bfab44e84562621d8fe1>,
2026-11-12). The owner adopted that gist as the study's direction on 2026-11-13.

## What the gist asks

1. Put every reasonable countermeasure in one MDP framework: the Zhang &
   Preneel (2019) set (which includes Publish or Perish), Aumayr et al. (2026)
   proportional reward splitting, and Share or Perish (MRL #146). Fall back to
   MDP + RL where a state space is too large.
2. Solve each protocol for two objectives: attacker revenue, and disruption,
   measured as reorgs deeper than 10 blocks (Monero's 10-block lock), possibly
   weighted by depth.
3. Make the solver report how long and how frequent the attacker's reorgs are.

It also asks for α up to and past Qubic's 0.38, low γ (Qubic's was below
0.05), and for small revenue differences to give way to ease of implementation.

## The three reference codebases

Read-only survey of the three repos the gist names (checked out 2026-11-13).

| | Zhang & Preneel, `nirenzang/PoWSecurity` | Aumayr et al., `commonprefix/proportional-reward-splitting-MDP` | Zur, Eyal & Tamar, `roibarzur/pto-selfish-mining` |
|---|---|---|---|
| Licence | GPL-3 | GPL-3 | MIT |
| Language | MATLAB + MDPtoolbox (not bundled) | MATLAB + bundled MDPtoolbox, Python drivers via `matlab.engine` | Python (numpy, scipy sparse, pymdptoolbox-roi; torch for RL) |
| Protocols | Bitcoin, PoP, three tie-breaking rules (chain quality); Bitcoin, Fruitchains, reward splitting, Subchains (incentive compatibility, censorship, subversion gain) | Bitcoin, Fruitchains, reward splitting, proportional reward splitting | Bitcoin, Ethereum, fee models, a simple model |
| Objective | revenue ratio by bisection on ρ over relative value iteration; subversion gain on absolute reward (double-spend bounty) | same bisection | PTO (probabilistic termination, no bisection), OSM (bisection), SMDP (fixed point); policy iteration |
| Caps | Bitcoin 80/160; PoP race length 28-30 (~3.7 M states at 30) | fork length 30 (24 for subversion gain) | `max_fork` argument; Bitcoin is 3(m+1)²+1 states |
| Reorg output | none | none (a strategy dump only) | none; does have the stationary distribution and a Monte Carlo policy test |
| Results shipped | none | `output.json` per protocol and metric (e.g. PRS α 0.45, γ 0.5, window 3, cap 30 = 0.7292) | none |

Two points decide the approach:
- **Licences.** This repository is BSD-3. GPL code cannot be copied into it.
  The two GPL repos serve as specifications and as numeric oracles (Aumayr's
  `output.json` files, Zhang & Preneel's paper tables). The protocol models are
  written fresh from the papers. pto (MIT) can be vendored with its licence.
- **PoP's encoding is block-granular.** Zhang & Preneel model PoP with the
  state (Bh, Bs, Dw, luck, last, published) and reach race length 30. Our SoP
  MDP (`sop_mdp.py`) carries more per-block detail and is 85 M states at 4
  blocks per side. A PoP-style encoding of SoP is the "block-granular
  abstraction" this study had parked (STATUS, MDP bounds).

## pto validated on a lane box (lithium, 2026-11-13)

pto at commit `89c40863`, Python 3.12, numpy 2.5, pymdptoolbox-roi 4.2.0, 4
BLAS threads. Bitcoin model:

| α | γ | cap | PTO | OSM | reference |
|---|---|---|---|---|---|
| 0.35 | 0 | 40 | 0.370754 (3.5 s) | 0.370754 (47 s) | |
| 0.35 | 0 | 95 | 0.370773 (74 s) | 0.370773 (28 min) | SSZ 0.37077; our cross-check 0.370774 |
| 0.25 | 0.5 | 40 | 0.250000 | 0.250000 | our solver 0.2499995 (cap 40) |
| 0.40 | 0.5 | 80 | 0.572507 | 0.572507 | our solver 0.572507 (cap 40) |

PTO is 13-40x faster than OSM at the same answer. Without a thread cap, the
solve took all 32 cores; every solver job now runs with `OMP_NUM_THREADS=4`.

## Plan

1. **Framework.** Vendor pto's `blockchain_mdps` base (MIT) into the study and
   use its `BlockchainModel` API: state space, actions, per-transition
   probability, reward and difficulty. Solve with PTO and cross-check with
   OSM and with `sop_mdp.py`'s hand-written solver on small caps.
2. **Protocols**, each validated before use:
   - Nakamoto: done (above).
   - PoP: rebuilt from Zhang & Preneel's description; check against their
     published chain-quality numbers.
   - Reward splitting and proportional reward splitting: check against
     Aumayr's `output.json`.
   - Fruitchains: same oracle; lower priority.
   - SoP: a new block-granular encoding in the PoP style. Check it against
     `sop_mdp.py` at 3/3 caps, where both solve exactly.
3. **Reorg output.** Tag each transition with the depth of the public reorg it
   causes. Under the solved policy, take the stationary distribution and
   report the rate of reorgs of each depth per main-chain block. Check this
   with pto's Monte Carlo policy test.
4. **Disruption objective.** The reward is 1 per reorg deeper than 10 blocks
   (and a depth-weighted variant), and the difficulty is blocks added to the
   chain. PTO solves this directly. Caps must exceed 10, so the SoP encoding
   must reach at least 11 blocks per side.
5. **Grid.** Protocols × α 0.10-0.49 (and 0.5-0.6 for disruption) × γ {0,
   0.05, 0.25, 0.5} × both objectives. All runs go on lane boxes, after a load
   check.

### Default definitions (open to the owner and the MRL)

- **Reorg depth** = the number of blocks removed from the chain that most
  honest miners had as their tip. In the (a, h, fork) models, an override
  removes h blocks. A won match race removes h blocks for the γ share of
  honest miners. A lost match race removes a blocks for the miners who
  followed the attacker.
- **Disruption** = expected reorgs deeper than 10 per main-chain block.

## Step 1 result: Nakamoto, revenue and disruption (2026-11-15)

Code: `studies/sop/countermeasures/` (commit `56c7346f` and the next one).
Data: `studies/sop/data/countermeasures/nakamoto_grid_20261115.jsonl`
(lithium, PTO, cap 80, horizon 10^5, 4 BLAS threads, 32 solves in 25 min).
Disruption counts majority reorgs of 11 blocks or more (deeper than the
10-block lock). Caps 40, 80 and 120 give the same disruption values at
alpha 0.40, gamma 0.05.

Deep reorgs (11+ blocks) per main-chain block, and the attacker's chain share:

| alpha | disruption-optimal, gamma 0 | gamma 0.05 | gamma 0.5 | its chain share (gamma 0) | revenue-optimal, gamma 0 | gamma 0.5 |
|---|---|---|---|---|---|---|
| 0.25 | 1.13e-3 (1 per 886 blocks, ~30 h) | 1.15e-3 | 1.36e-3 | 0.014 | 0 (honest) | 0 (honest) |
| 0.30 | 4.39e-3 (1 per 228, ~7.6 h) | 4.44e-3 | 5.00e-3 | 0.055 | 0 (honest) | 1.4e-6 |
| 0.35 | 1.19e-2 (1 per 84, ~2.8 h) | 1.20e-2 | 1.32e-2 | 0.147 | 1.68e-3 | 1.4e-5 |
| 0.40 | 2.51e-2 (1 per 40, ~1.3 h) | 2.52e-2 | 2.76e-2 | 0.311 | 4.49e-3 | 8.7e-5 |
| 0.45 | 4.47e-2 (1 per 22, ~45 min) | 4.48e-2 | 5.00e-2 | 0.549 | 1.08e-2 | 3.6e-4 |

Hours assume Monero's 2-minute blocks. Mean depth of the disruption-optimal
attacker's reorgs: 11.3-12.0 blocks.

Reading:
- **Gamma hardly matters for disruption.** Deep races are won by length, not
  ties: going from gamma 0 to 0.5 adds at most 12 % to the deep-reorg rate.
  Keeping gamma low (the Qubic lesson) protects against revenue attacks, not
  against an attacker who wants deep reorgs.
- **Disruption is cheap at Qubic's scale.** At alpha 0.30-0.35 under plain
  Nakamoto, an attacker who wants reorgs past the 10-block lock gets one every
  3-8 hours. It pays for that with 80-60 % of its mining income (chain share
  0.055 and 0.147 against 0.30 and 0.35 honest). At alpha 0.45 the
  disruption-optimal attacker still earns more than honest mining (0.549).
- **A revenue-maximiser already causes deep reorgs at alpha 0.35 and up when
  gamma is low** (1 per 600 blocks at 0.35), because its races run long. With
  gamma 0.5 it wins short races instead and deep reorgs fall 100-fold.
- **Independent check.** A hand-written rule (mine privately from the fork,
  publish all when a > h >= 11, give up when h - a >= D, best D;
  `studies/sop/countermeasures/giveup_check.py`, 3 M blocks per alpha) reaches
  0.72-0.77 of the MDP rate at every alpha (8.2e-4 at 0.25, 9.3e-3 at 0.35,
  3.2e-2 at 0.45), below the optimum as it must be. The MDP does better by
  publishing only h + 1 blocks and keeping the rest of its lead.

These are the Nakamoto baseline the countermeasures are measured against.
Model limits: instant propagation inside each side, constant attacker
hashrate, one attacker, no difficulty adjustment inside a race.

## Step 2, first findings (2026-11-16)

**Sources.** Zhang & Preneel 2019 (the "Lay Down the Common Metrics" PDF
shipped in Aumayr's repo) describes the reward-splitting MDP in full
(Appendix D), so RS can be built from published text. It gives PoP only as
a figure, plus two exact values: PoP's profitable threshold 0.2500 [2026-11-17: 0.2640 in their own
model, see "Independent reviews" at the end] (k = 3,
race length 30) and Q(0.3901) = 0.5372 for both PoP and NC (gamma 0), the
point where PoP starts to beat NC. The PoP paper itself (CT-RSA 2017) is not
freely available (Springer paywall; the institutional copy is embargoed).
The only full PoP model text is the GPL-3 MATLAB code.

**RS and PRS do not change fork choice.** Aumayr et al. say so for FairChain
and PRS ("work objects play no role in chain selection, only in reward
allocation"); RS is the same. Against an attacker who maximises deep reorgs
and ignores income, their transition dynamics are Nakamoto's, so their
disruption numbers equal the Nakamoto baseline above by construction. They
can only change the revenue side. Of the gist's list, PoP and SoP are the
countermeasures that can change disruption.

**Aumayr's Bitcoin baseline overstates Nakamoto at alpha 0.41 and above.**
Their `incentive_compatibility/Bitcoin/SolveMDP.m` is a script, so its
`global lowRou` binds `Init.m`'s return value. It runs two bisections: a
lower bound on the cap-30 MDP (lines 8-21), then an SSZ-style upper-bound
bisection that pays a truncation award at the cap and searches only up to
`min(rou + 0.1, 1)` (lines 24-56). `Init` returns `lowRou` after the second
one. Their RS and PRS solvers run the lower-bound bisection only (the PRS
upper-bound pass is commented out). `plot.py` plots these `output.json` values.

Review (all 45 shipped Bitcoin points against our cap-30 lower bound, pto,
and cap-30 upper bound, `sop_mdp_crosscheck.py btc --bound upper`; data
`studies/sop/data/countermeasures/aumayr_bitcoin_review_20261116.jsonl`,
script `studies/sop/countermeasures/aumayr_btc_review.py`):

| alpha | their value | reading |
|---|---|---|
| 0.25-0.40 (30 points) | inside our cap-30 [lower, upper], at most 0.0032 above the lower bound | a valid upper bound, close to the optimum |
| 0.41-0.43 (5 of 9 points) | 0.002-0.028 above our cap-30 upper bound | a looser upper bound (their truncation award is weighted twice) |
| 0.44-0.45 (5 of 6 points) | our cap-30 lower bound + 0.1000 exactly | the second bisection hit its ceiling `rou + 0.1`: a search-range artefact, not a computed bound |

Corrected 2026-11-16 after an independent review: the table said "0.002-0.04
above our upper bound"; 0.04 (0.043 at alpha 0.43, gamma 0) is the gap to our
*lower* bound, and the largest excess over the upper bound is 0.028 (alpha
0.43, gamma 0.5). It also said their truncation award is "larger". The cause
is that the award is weighted twice: in `SolveMDP.m` lines 29-44 the cap
awards `mid1` and `mid3` already carry rou (SSZ's form), and
`Wrou = (1-rou).*RsOut - rou.*RhOut` (line 46, `RhOut = 0` there) multiplies
them by (1 - rou) again, which shrinks the penalty at the honest cap and
loosens the bound. The review ran their code unmodified in Octave and got
their `output.json` values to the printed digits, with the alpha 0.45 points
at the ceiling. Zhang & Preneel's own `Results.xlsx` (NC, gamma 0.5, lmax 160)
gives attacker share 0.7596 at alpha 0.45, inside our [0.7596, 0.7647].

Their model is the same as ours: at the saturated points their value minus
0.1 is their own lower bound, and it equals ours to 2e-5 (0.75891 against
0.75893 at alpha 0.45, gamma 0.5). The other gamma-1 points: 0.41-0.43 sit
inside our bracket; 0.44 is 0.075 above our upper bound (0.092 above the
lower bound, short of the ceiling).

At alpha 0.45, gamma 0.5 the Nakamoto optimum lies in [0.7596, 0.7647]
(lower bound 0.75964 at pto caps 80 and 160; upper bound 0.7871 at cap 30,
0.7647 at cap 80). The value their `plot.py` draws for Fig. 2 is 0.8589, about 0.1 too high. Like
for like (cap-30 lower bounds), Bitcoin 0.7589 against PRS 0.6901 (R 6, k 6)
is a gap of 0.069, not the plotted 0.169. PRS still beats Nakamoto there;
the margin is smaller. Below alpha 0.41 their Bitcoin curve is accurate to
0.003.

## Step 2: SoP against Nakamoto, disruption (2026-11-16)

Code: `studies/sop/countermeasures/sop_walk.py` (the SoP model),
`howard.py` (the solver). Data:
`studies/sop/data/countermeasures/disruption_howard_20261116/` (lithium,
exact average-reward policy iteration, 4 BLAS threads).

Note 2026-11-17: in these files `profile.revenue` is not the attacker's
share. The profile divided the attacker's main-chain blocks by the model's
difficulty, which under normalization "time" is block intervals, so for the
`nak_*` files it is attacker main-chain blocks per block interval (0.069 at
alpha 0.33, gamma 0). The `sop_*` files come from the walk model, which has no
revenue objective, and the field means nothing there. Nothing in this doc
quotes it; the reorg rates are per block interval as stated. The Step 1
"chain share" column comes from the per-main-chain-block grid, where the
field is the share. pow-countermeasure-mdp's profile reports the share for
every model from 2026-11-17.

**The SoP walk model.** The exact SoP MDP (`sop_mdp.py`) stops at 4 blocks
a side. On its own rules the attacker's object lead x = D + pa - ph moves +1
per attacker object and -1 per honest object, and past the window a reveal is
accepted iff x - pa > 0 (checked over 200k random events). For disruption the
state (h up to the threshold, a >= 1, x, pa) is enough: 251k states. Three
departures: the window is ignored and the honest pending shares are dropped
when a race restarts (both favour the attacker); shares past 64 pending and
objects past a lead of 80 are discarded (against it). So the walk optimum
overstates the attack; running its policy through `sop_mdp.py`'s exact rules
gives the rate of a policy that is legal in the exact game.

**Solver.** PTO through mdptoolbox-roi misreports tiny rates: its sparse
policy evaluation runs Krylov solvers at rtol 1e-7 on an ill-conditioned
system, and policy iteration stops once values change by less than epsilon.
At alpha 0.25 PTO reported 3.4e-13 for a policy whose exact rate is 1.34e-8
(stationary distribution by sparse LU, and a renewal-reward check by LU and by
monotone iteration, all three 1.3386e-8). `howard.py` solves each policy's
equations exactly and stops only when the policy stops changing. It matches
SSZ (0.370754) and PTO wherever PTO's values are large; warm-started from
PTO's policies it changed no rate, so PTO's policies were optimal and only
its low-rate values were wrong.

**Results.** Reorgs of 11+ blocks (deeper than the 10-block lock) per block
interval, at the network's full hashrate (2 minutes per interval at Monero's
target). Nakamoto at cap 80; SoP with w = 16 (MRL #146's parameters).

| alpha | Nakamoto, gamma 0 | Nakamoto, gamma 0.5 | SoP walk (overstates) | SoP exact game, walk policy (legal) | Nakamoto / SoP walk |
|---|---|---|---|---|---|
| 0.25 | 8.48e-4 (1 per 39 h) | 1.02e-3 | 1.34e-8 (1 per 280 years) | - | 63,000 |
| 0.30 | 3.08e-3 (1 per 11 h) | 3.51e-3 | 3.30e-7 (1 per 11 years) | - | 9,300 |
| 0.33 | 5.58e-3 (1 per 6 h) | 6.22e-3 | 2.24e-6 (1 per 1.7 years) | - | 2,500 |
| 0.35 | 7.82e-3 (1 per 4.3 h) | 8.63e-3 | 8.26e-6 (1 per 168 days) | - | 950 |
| 0.40 | 1.55e-2 (1 per 2.2 h) | 1.68e-2 | 2.51e-4 (1 per 5.5 days) | 3.2e-5 (40 events) | 62 |
| 0.45 | 2.57e-2 (1 per 78 min) | 2.79e-2 | 5.82e-3 (1 per 5.7 h) | 2.91e-3 (3,643 events) | 4.4 |

Exact-game rates come from 20 M objects (1.25 M block intervals) each; at
alpha 0.35 and below the expected count is below one, so none was run.

Reading:
- **SoP cuts deep reorgs by orders of magnitude at Qubic's scale.** At alpha
  0.30-0.35, against an attacker who wants nothing but reorgs past the lock,
  SoP moves the rate from one every 4-11 hours to one every half-year to
  decade, even in the model that overstates the attack. The reason is the
  finer work unit: a reorg of 11 blocks is a race of about 350 objects instead
  of 22 blocks, and a minority's chance of leading such a race falls
  exponentially with its length.
- **The protection shrinks fast as alpha nears 0.5.** At 0.45 SoP leaves one
  deep reorg every 6-11 hours (between the exact-game policy and the walk
  optimum), 4-9 times fewer than Nakamoto. The object walk's drift is
  1 - 2 alpha per object, so long races stop being rare.
- **The two SoP columns still differ by 2-8x at 0.40-0.45.** The walk model's
  favours (no window, no honest pending at a restart) are worth that much. A
  tighter model needs the honest pending at restart; the window matters
  little at 11+ blocks.

**MRL #146's own example, a 3-block reorg at alpha 0.33.** Nakamoto: 4.33e-2
per block interval (one every 23 intervals, about 46 minutes: the issue's
"hourly"). SoP: between 5.0e-5 (the walk policy in the exact game, 63 events;
one every 28 days) and 3.54e-3 (the walk optimum). The 70-fold gap is the
32-object window, which the walk model ignores and which binds for short
races, so for shallow reorgs the walk model is too loose to test the issue's
"~0.06% per attack". It needs the window first.

Model limits: one attacker, instant propagation within each side, constant
hashrates, no difficulty adjustment, no ties under SoP (Model B).

## Step 2b: the tight SoP model (2026-11-16)

Code: `sop_tight.py` (now in pow-countermeasure-mdp, `pcmdp/sop_tight.py`).
Data: `studies/sop/data/countermeasures/tight_20261116/` (lithium, Howard,
one solve at a time, about 14 GB peak; the `.json` files carry Howard's
iteration log before the result line).

**Why.** Running the walk-optimal policy in the exact SoP game with each of the
walk model's favours switched off in turn (same events per variant): at alpha
0.45 exact 2.875e-3, without the window 2.875e-3, without carrying the honest
pending shares into the next race 6.27e-3; at 0.40 (100 M objects) 3.34e-5 /
3.36e-5 / 2.66e-4. At 11+ blocks the window does not bind; restarting at
x = -ph is the whole gap. The tight model keeps ph (state h, a1, x, pa, ph;
restarts as in the exact game) and leaves out only the window. Caps: x in
[-40, 40], pending 24 (1.2 M states); 2.5 M states ran out of memory.

**Check.** Each policy run in the exact, uncapped SoP game (`sop_rules`, with
and without the window: identical counts at every point): alpha 0.45, 3.865e-3
against the model's 3.836e-3 (4,831 events, 20 M objects); 0.40, 6.19e-5
against 6.33e-5 (387 events, 100 M objects); 0.35, 6.4e-7 against 4.0e-7 (4
events). At 0.45 the stationary profile equals g to 1e-14; at 0.30 the profile
check ran out of memory after Howard had converged (38 iterations, the last
with no change).

**Results.** Reorgs of 11+ blocks per block interval (2 minutes at Monero's
target):

| alpha | Nakamoto, gamma 0 | SoP, tight model | Nakamoto / SoP |
|---|---|---|---|
| 0.25 | 8.48e-4 (1 per 39 h) | 1.12e-11 (1 per ~340,000 years) | 7.6e7 |
| 0.30 | 3.08e-3 (1 per 11 h) | 2.13e-9 (1 per ~1,800 years) | 1.4e6 |
| 0.33 | 5.58e-3 (1 per 6 h) | 4.95e-8 (1 per ~77 years) | 1.1e5 |
| 0.35 | 7.82e-3 (1 per 4.3 h) | 4.02e-7 (1 per ~9.5 years) | 1.9e4 |
| 0.40 | 1.55e-2 (1 per 2.2 h) | 6.33e-5 (1 per ~22 days) | 245 |
| 0.45 | 2.57e-2 (1 per 78 min) | 3.84e-3 (1 per 8.7 h) | 6.7 |

These supersede the walk-model column of the step 2 table, which overstated
the attack 1,200-fold at 0.25, 45-fold at 0.33, 4-fold at 0.40 and 1.5-fold
at 0.45. At 0.35 and below the rates cannot be checked by simulation; the
model's departures (no window, pending caps that mostly favour the attacker)
make them upper estimates.

Reading: against an attacker who wants reorgs past the 10-block lock, SoP
turns Nakamoto's every-few-hours into decades or more at Qubic's 0.25-0.38,
and still gives a 6.7-fold cut at 0.45. The 3-block case of MRL #146's own
example still needs the window model.

## Independent reviews of the disagreements with published work (2026-11-17)

Two reviews ran the authors' MATLAB unmodified in Octave on box90. Their
artefacts are in `studies/sop/data/countermeasures/reviews_20261117/`.

- **`adversarial/`** was given our four claims and asked to break them.
- **`blind/`** (see `REPORT.md`) was given only the papers, the reference code
  and a copy of pcmdp. Our docs, git history, conclusions and the first
  review's files were left out. It was asked three neutral questions.

The two reviews agree on every point.

**Aumayr et al.'s Bitcoin baseline** (their Fig. 2,
`incentive_compatibility/Bitcoin/output.json`). The stored value is the
result of the upper-bound bisection, capped at lower bound + 0.1. Their
`Init.m` returns `lowRou`, which `SolveMDP.m`'s second loop overwrites.
Zhang & Preneel's original kept the two bounds apart. RS, PRS and Fruitchains
return lower bounds, so the figure compares a capped upper bound for Bitcoin
with lower bounds for everything else.

At alpha 0.45 the cap is hit for every gamma. At gamma 0.5 the optimum is
0.5725 (alpha 0.40) and 0.7596 (0.45), against 0.8589 stored. These match
Zhang & Preneel's `Results.xlsx` (lmax 160) and our Howard solve (max_fork 80).
Bitcoin is overstated by 0.03-0.10 for alpha >= 0.42, and the kink at
0.43-0.44 is an artefact. The ordering PRS < RS < Bitcoin survives (0.690,
0.701, 0.760 at 0.45); the Bitcoin-PRS gap there is 0.07, not 0.17.

**Zhang & Preneel Table II, PoP (k = 3).** The paper gives PT 0.2500. In their
own model the attacker's optimal revenue first exceeds alpha at 0.2640
(maxB 12-20, exact ratio policy iteration on their exported matrices). Their
shipped `Threshold.m` outputs 0.2642 and cannot output 0.25: its first probe,
0.2625, is not profitable. Their other PoP numbers do reproduce: the excess is
0.0160 / 0.0442 / 0.0808 at alpha 0.30 / 0.35 / 0.40, against 0.016 / 0.0443 /
0.082 in the paper. The most likely source of 0.25 is the last point of their
0.05 alpha grid with ideal chain quality, but that cannot be proven. Our
`pop.py` gives PT in (0.2640, 0.2641] and agrees with their model to 4e-6.

**Zhang & Preneel Table II, SHTB (15 regions).** The paper gives 0.0652 and
labels it an upper bound. Their threshold script reproduces it to within its
noise (0.0652 in the first review, 0.0653-0.0654 in the blind one). The exact
PT of their model is 0.0580: lmax 10 and 20 agree to 7 digits, and at alpha
0.10 the excess is 5.5e-4 at lmax 10, 20 and 40. The script's test needs the
excess to clear about 1e-4 of bisection noise, but the excess at 0.065 is only
4.8e-5. PT scales about as 1/regions (10 regions 0.0818, 5 regions 0.1387).
Our SHTB port agrees with their model to 1e-12.

**pto's PTOSolver on mdptoolbox-roi** is not usable for rates below about 1e-6
per block. It returns policies that take illegal actions, or values near zero
(1.67e-16 against a true 6.30e-10; 3.4e-13 against 1.34e-8 in our SoP case).
There are three mechanisms:

- `pto_solver.py` zeroes transitions into the final state, so an illegal
  action looks like a reward-0 termination;
- policy iteration stops once span(V - Vprev) < epsilon, which holds as soon
  as g*H < epsilon;
- the sparse policy evaluation's Krylov solvers (rtol 1e-7) accept V near 0,
  and three of the four break down silently before gmres "converges".

Above that range PTO's policies were optimal, but its values run low by about
10/H relative: 2e-5 to 9e-5 absolute in revenue at H = 1e5. Our `howard.py`
values are exact to round-off (1e-13 in revenue, 5e-7 relative at a rate of
6.5e-12), and a Bellman-residual check certifies its policies optimal.

What this changes here:

- **The 0.04 / "larger award" wording** above was corrected on 2026-11-16.
- **The PoP threshold quoted from the paper** (0.2500) is 0.2640 in their
  model.
- **PTO values in this doc** (the Step 1 grid, the pto lower bounds in the
  Aumayr review) carry the ~1e-4 relative low bias; no conclusion here
  depends on that digit. Step 1's rates and shares are the stationary values
  of PTO's policies, which the review found optimal at those rates.
- **Not checked:** the other Table II entries (NC, UTB, UDTB), and the
  subversion-gain and censorship numbers.

During the blind review its SHTB job was killed twice by a loose `pkill -f`
from another of our agents on the same account. It resumed from its bracket.

## SoP acceptance convention (2026-11-17)

Our SoP models accept a reveal iff D > ph past the window. Here D is the
attacker's object lead in blocks and shares and ph the honest pending tip
shares; the attacker's own pending tip shares pa do not count. This is
monerosim's `--own-pending ignore`, chosen because our patched daemon in the
12-daemon sims rejects reveals that need them. MRL #146's text since
2026-10-20 counts pool shares that extend a chain's tip under sop_objective,
the attacker's pending shares included (`--own-pending count`, accept iff
D + pa > ph). tevador's appendix simulator does the same (COUNT_TIP_SHARES).
Every SoP rate above (Step 2, Step 2b, STATUS until 2026-11-17) is for
"ignore", and the docs did not say so.

pow-countermeasure-mdp's `sop_tight.py` now takes `--own-pending`. Results
are reorgs of 11+ blocks per block interval, caps x +-40, pending 24; the
"ignore" runs reproduce the published values:

| alpha | ignore | count | count / ignore |
|---|---|---|---|
| 0.33 | 4.95e-8 (one per ~77 y) | 7.57e-7 (one per ~5 y) | 15.3 |
| 0.40 | 6.33e-5 (one per ~22 d) | 5.23e-4 (one per ~2.7 d) | 8.3 |

At alpha 0.40 we ran the "count" policy through the exact game (20 M
objects). It gave 6.65e-4 without the window (831 events, 27 % above the
model's g) and 3.26e-4 with it (408 events). Under "ignore" the model matched
the exact game within noise. The 27 % gap under "count" is not explained yet:
for the same policy, model and game should agree without the window.

tevador's simulator, run verbatim (MIT, from the #146 appendix): alpha 1/3,
fixed attacker with stubbornness 10, gamma 0.5 (his GAMMA is the honest
chain's chance of winning a tie), 80 s blocks. Rates per block interval:

| setting | events | rate | one per |
|---|---|---|---|
| his defaults (depth 10+) | 42 | 1.48e-6 | 1.7 y |
| depth 11+ | 22 | 3.87e-7 | 6.5 y |
| depth 11+, his ties go to the attacker | 38 | 6.69e-7 | 3.8 y |

His time unit is an 80 s block. He leaves the attacker out of difficulty, so
his "one per" values are not in 120 s Monero blocks.

Most of the 17-fold gap between his published figure and ours comes from
two things. The depth threshold, 10 against 11, accounts for about 4x in his
simulator. Counting the attacker's own pending shares accounts for about 15x
in our model. With both aligned, our optimal attacker (7.6e-7) sits about
2x above his fixed one (3.9e-7) at depth 11.

Still open:
- the 27 % model-game gap under "count";
- the window's effect at alpha 0.33, which is too rare to simulate;
- ~~which convention SoP should be scored by~~ Decided 2026-11-17 by the
  owner: Monero behaviour follows canonical monerod (monero-project/monero),
  selfish-mining conventions follow the published literature, and SoP follows
  tevador's MRL #146 text. SoP is therefore scored with "count"; "ignore" (our
  daemon patch) is reported only as a labelled variant. Canonical monerod's
  spend lock is 10 blocks (`CRYPTONOTE_DEFAULT_TX_SPENDABLE_AGE`, master and
  release-v0.18), so the disruption threshold stays at 11+ blocks.

Neither our models nor tevador's include propagation delay. An independent
event simulator on #146 shows delay multiplies SoP's 10+ rate 4.5-fold at
1 s and 81-fold at 3 s (`pow-countermeasure-mdp/docs/references/monero.md`).
