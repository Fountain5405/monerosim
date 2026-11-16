# Countermeasure MDPs: survey of the reference code and plan (2026-11-13)

Status: current plan. It follows Rucknium's "Research directions for selfish
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
a figure, plus two exact values: PoP's profitable threshold 0.2500 (k = 3,
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
| 0.41-0.43 (5 of 9 points) | 0.002-0.04 above our cap-30 upper bound | a looser upper bound (their truncation award is larger) |
| 0.44-0.45 (5 of 6 points) | our cap-30 lower bound + 0.1000 exactly | the second bisection hit its ceiling `rou + 0.1`: a search-range artefact, not a computed bound |

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
