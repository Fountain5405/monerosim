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
optimum. Mid-caps check (3/3/48/20/20, 7,981,414 states, noown): exact
solve running on lithium since 17:05Z; MdpEnv training to follow. Result:
(pending).

For reference, the 4/4/64/24/24 exact solve (85.1 M states, lithium,
07:07Z to ~18:00Z): optimum converging to 0.4499, i.e. honest mining: within a
4-block truncation no policy beats publishing every block, while the
stubborn rule under the same cap scores 0.098 (race model).

### 3. Beat the stubborn rule in the race model

Training alpha 0.45 on lithium from 17:08Z (`train --env race --budget
200000000`, bisection on the share, 2000 d x 3 seeds per step). Result:
(pending). Pass: mean over 5 seeds >= 0.2558 + 0.01.

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
