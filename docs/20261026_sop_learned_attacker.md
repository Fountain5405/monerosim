# A learned attacker for Share-or-Perish: the validation ladder (2026-10-25/26)

Design: docs/superpowers/specs/2026-10-25-sop-rl-attacker-design.md. Plan:
docs/superpowers/plans/2026-10-25-sop-rl-attacker.md. Code: scripts/sop_rl.py
(learner), scripts/sop_policy.py (numpy-free pieces the agent uses),
scripts/sop_race_model.py `SopEnv` (the race model as reset/step),
agents/selfish_strategy.py `learned`. Policies: data/sop_rl/.

The question: how much does SoP (MRL #146, 2026-10-20 rule) concede to an
attacker that is not hand-written? The window_stubborn noown attacker is a
floor (sims: 0.272 at alpha 0.45, n=4). The exact solver cannot reach
faithful block caps (docs/20261025_sop_mdp_notes.md), so a tabular policy
is learned by reinforcement learning against the race model and then run
in the 12-daemon Shadow cells. Every step below gates the next.

## Ladder

### 1. Fidelity of the environment (done 2026-10-25 17:10Z)

`SopEnv` driven by the race model's own stubborn rule reproduces the old
`simulate()` loop bit for bit (29 pinned 60 d runs across every preset).
Through it, at alpha 0.45, 2000 d, 5 seeds:

| policy | share (5 seeds) | mean | reveals/run | mean reorg | max reorg |
|---|---|---|---|---|---|
| race model's stubborn rule (`stubborn_policy`) | 0.2806 (seed 1) | 0.281 | 60,198 | 3.27 | - |
| the SIM's stubborn rule (`sim_stubborn`) | 0.2569 0.2565 0.2553 0.2560 0.2546 | 0.2558 | 53,871 | 2.69 | 17 |
| 12-daemon sims, window_stubborn noown (n=4) | 0.288 0.279 0.269 0.253 | 0.272 | 119-138 per 72 h | - | - |

At alpha 0.50 (same procedure): `sim_stubborn` 0.5721 0.5705 0.5716 0.5730
0.5703, mean 0.5715, 124,250 reveals/run, mean reorg 2.69, max 19; the sims
measured 0.604 (n=4: 0.591 0.582 0.614 0.628). The race model under-predicts
the sim's rule by 0.016 at 0.45 and 0.033 at 0.50.

Finding: the two hand-written rules differ by 0.025 in the race model. The
sim's rule holds while there is no honest block whatever the objects
deficit, and gives up as soon as an honest block appears while it holds
none; the race model's rule gives up on the objects deficit at every event
(dropping its pending shares) and keeps mining on the fork point behind an
honest block. The sims' measured 0.272 sits between the two. The learned
policy is compared with `sim_stubborn`, the rule the sims actually run.

### 2. Learner correctness against the exact solver

Test suite (`scripts/test_sop_rl.py -m slow`, 2026-10-25): on
Caps(3,3,32,16,16), where reveals are possible, the greedy policy after
40 M steps at the exact rho lands within 0.01 of the Compact solver's
optimum. Mid-caps reference (3/3/48/20/20, 7,981,414 states, noown, alpha 0.45):
exact optimum 0.4500 = honest mining, and the optimal policy never reveals
(action counts over decision pairs: hold 5.69 M, publish 0.34 M, reveal 0,
give_up 10.8 M; 3601 s on lithium). The race-env training at 0.45 found
0.449 / 0.446 on its first two bisection steps, i.e. honest mining too, so
a learner-vs-exact comparison at 0.45 only shows that it learns to mine
honestly. The check is therefore repeated at alpha 0.50, where the
hand-written attacker is profitable (sims 0.604): exact 3/3/48/20/20 solve
at 0.50 launched 18:10Z, MdpEnv training at the same caps to follow.
Result: (pending).

For reference, the 4/4/64/24/24 exact solve (85,108,639 states, lithium,
07:07Z to 19:50Z, 12.7 h): optimum 0.4500, i.e. honest mining: within a
4-block truncation no policy beats publishing every block, while the
stubborn rule under the same cap scores 0.098 (race model). The optimal
policy's action counts (hold 151 M, give up 97 M, publish 0.9 M, reveal
0.37 M over decision pairs) are mostly value ties at rho = alpha resolved
toward hold; the share is honest's. The policy table (2.2 GB JSON) stays
on lithium.

### 3. Beat the stubborn rule in the race model

First attempt (17:08Z-19:20Z, pure eps-greedy, 2000 d x 3 seeds per
bisection step): every alpha converged to honest mining within 2-4 steps
(0.400 at 0.40, 0.449 at 0.45, 0.478 at 0.48, 0.498 at 0.50), including
alpha 0.50 where `sim_stubborn` earns 0.5715. Random exploration never
holds a branch long enough to see a deep reveal pay; the exact solves
show why: at 3 blocks per side the optimum is honest with zero reveals at
both 0.45 and 0.50, so the profitable reveals live in branches deeper than
any solvable truncation, and a learner has to be led there. Second attempt
(from 19:45Z): the design's optional warm start, as an off-policy
behaviour policy: the training step follows `sim_stubborn` with weight
beta decaying from 1 to 0 over the budget, so the table's values along
stubborn's trajectories are grounded before the greedy policy takes over.
Pass bar: the greedy policy's mean over 5 seeds exceeds `sim_stubborn`'s
(0.2558 at 0.45, 0.5715 at 0.50) by 0.01; reported next to honest mining
(alpha) as well, since honest beats stubborn below ~0.48.

Result of the first bisection step (20:16-20:44Z, rho 0.425, 2e8 objects
per step, 52-80 min, tables of 2.3 M to 5.1 M keys): honest mining again
at every alpha: 0.397 (0.40), 0.447 (0.45), 0.478 (0.48), 0.498 (0.50).
The warm start grounds stubborn's values one step at a time: a hold is
valued off its successor, untried on the first pass (so it takes the
reference value), and a reveal's payoff reaches the race's first hold
only after as many revisits as the race is long. With millions of keys
seen a few times each that never happens within the budget, and the
greedy policy settles for publishing and giving up early.

Third attempt (launched ~21:15Z, alpha 0.50 only, bisection bracket
0.45-0.70 so the first step asks for a share above 0.575): (a)
`--returns race`: each race's full return is applied backward when its
fork settles, cut at exploratory actions as in Watkins' Q(lambda), so a
reveal credits every hold of its race in one pass (unit test: a 3-hold
chain ending in a 3-block reveal values its first hold at 3 after one
race, where one-step targets leave it at 0); (b) the design's fallback,
D binned by 2 (`--d-bin 2`); (c) both, with the pending counts binned by
2 as well (`--p-bin 2`). Pass bar unchanged. The 0.40 run was stopped
(stubborn earns 0.06 there against honest's 0.40: nothing to learn or to
simulate).

The first of these to report (race + bins, rho 0.575, 1.57 M keys, 47
min) scored 0.311, which exposed a flaw in the bisection rather than in
the learner: at a rho above the optimum every settlement loses and
holding scores 0, so the greedy policy holds until the deficit cap
forces it, and the probe is wasted by construction; the bisection then
carried that table into the next step. The one-step runs' second step,
at rho 0.6125, was the same waste. Fix: every step now trains from the
best table so far (a failed probe's table is dropped; unit-tested).

Fourth attempt (22:10Z, alpha 0.50, bracket 0.50-0.60 so the first step
asks for a share above 0.55, under `sim_stubborn`'s 0.5715): four runs on
lithium, all warm-started from `sim_stubborn`: one-step targets (the
control), race returns, D binned by 2, race returns with D and pending
counts binned by 2. The one-step runs at 0.45 and 0.48 were stopped: a
one-step learner that cannot reproduce stubborn at 0.50 has nothing to
show at alphas where honest mining already beats stubborn; those alphas
are trained later with whichever configuration passes at 0.50. Result:
(pending).

### 4. Smoke cell (6 h)

(pending)

### 5. 72 h cells

(pending)

## What the policy does

(pending: diff entries by action; where it holds a winning reveal, where
it gives up earlier or later than o5)

## Incidents

- 2026-10-25 14:03 UTC: phantom's kernel OOM-killed the owner's testnet
  monerod under my four sim lanes (reported; phantom runs at most 2 lanes
  from now on; no training there).
