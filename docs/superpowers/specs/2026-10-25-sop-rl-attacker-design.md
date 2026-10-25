# A learned attacker for Share-or-Perish (design, 2026-10-25)

## Intent

Find out how much revenue Share-or-Perish (MRL #146, 2026-10-20 rule)
really concedes to a selfish miner, and have an attacker that earns it
that can be run in the 12-daemon Shadow simulations. Every number we have
today comes from one hand-written strategy (`window_stubborn`, o5 give-up)
and is therefore a floor: at alpha 0.45 it earns 0.272 in the sims, while
the exact solver already shows that a better policy in a game capped at
4 blocks per side earns more than 0.275, and the capped game is far below
the real one. The exact solver cannot reach a faithful game (8 blocks per
side are needed; 4 is already 85 M states), so the owner chose
reinforcement learning (option B of docs/20261025_sop_mdp_notes.md).

The owner's stated priority: "mostly something we can run in the sim to
actually test things". The number and the curve follow from that.

## Goals

1. A policy, trained against the race model, that earns strictly more than
   `window_stubborn` noown at alpha 0.45 in the race model, and is then
   confirmed in 72 h Shadow cells.
2. The policy runs inside the simulator's attacker agent as a new strategy
   that loads a plain policy file and uses only information the agent has
   at decision time.
3. The policy is a lookup table over a small discrete state, so it can be
   printed, diffed and reasoned about.
4. Policies at alpha 0.40, 0.45 and 0.48 (0.50 if time allows), giving the
   learned curve and a crossing estimate.
5. A validation ladder that catches a policy exploiting the race model.

## Non-goals and anti-goals

- No neural-network policies, no function approximation. If the table
  does not fit, the state is coarsened, not the policy class changed.
- Not optimising the own-counting attacker: it is strictly dominated.
- Not modelling network topology, latency or ban behaviour in training:
  the race model is the environment, the sims are the check.
- Anti-goal: a policy that wins in the race model by exploiting something
  the sims do not allow (instant share delivery, instant acceptance, an
  action the agent cannot take). The ladder below exists to catch this;
  a policy that fails step 4 or 5 is a finding about the model, not a
  result.
- No training or evaluation on the control box (owner rule 2026-10-25:
  it runs only the Claude instances). Lane boxes only.

## Constraints

- The attacker's decisions in the sim are made by
  `agents/selfish_strategy.py` after each block or share it sees, with the
  actions hold / publish / reveal / give up and the observation it already
  computes: own and honest blocks since the fork, the `branch_weights()`
  tuple (attacker objects, attacker weight, honest weight, the two window
  counts, both sides' objects since the fork including pending shares).
  The learned policy must be a function of those quantities only.
- The race model (`scripts/sop_race_model.py` Model B) matches the sims'
  noown attacker when run with the sims' settings (rule 20261020_noown,
  honest shares via the slot rule, o5 give-up): 0.060 / 0.281 / 0.500 vs
  the sims' 0.065 / 0.272 / 0.474 at alpha 0.40 / 0.45 / 0.48 (2000 d, seed
  1, 2026-10-25). At 0.50 it over-predicts (0.652 vs 0.587). Training uses
  those settings.
- Objective is the long-run revenue share att / (att + hon), a ratio.
  The standard trick (Sapirshtein-Sompolinsky-Zohar, already used in
  `scripts/sop_mdp.py`) is to maximise the average reward
  `a - rho * (a + h)` per settled block for a fixed rho and bisect rho to
  zero gain. The agent inherits this.
- Compute: lithium or phantom (31 GB, 16 cores) when free of sims; a
  16 GB box otherwise. Single process, numpy and the standard library
  only. No new dependencies.

## The design (the owner's decisions, then the builder's)

### Environment (my call: a step-API version of the race model)

Refactor Model B's loop into `reset()` / `step(action)` with the same
state variables, so that one code path serves `simulate()` (policy baked
in) and the agent. The existing `simulate()` keeps its signature and
results; a test runs the stubborn policy through the step API and asserts
identical `SimStats` to `simulate()` for the same seed. The config flags
stay (rule presets, honest shares, cap_blocks); training uses the sims'
noown settings.

Decision points and forced moves (my call, after the reviewer's check of
`simulate()`): the environment offers a decision after EVERY object, with
the legal set exactly as `sop_mdp.actions()` masks it (publish only when
h == 0, reveal only when the network accepts, hold and give up always
once the attacker holds a block). Nothing is forced by the environment
except the far truncation caps of the exact MDP (|D| and the objects
deficit at 200). In particular the o5 give-up is NOT an environment rule:
it is part of the stubborn policy, written as a policy function over the
step API (give up when honest leads by more than 5 objects, including at
a == 0 where it drops the pending shares exactly as `simulate()` does;
after a block, publish/reveal as `simulate()` does; hold at every other
share event). That function through the step API must reproduce
`simulate()` bit for bit, which is the fidelity test. The learned policy
may therefore give up earlier or later than o5, and may hold a winning
reveal; those use no transition `simulate()` does not already have (hold
is "continue"), so the fidelity test still vouches for the dynamics.

Observation returned by `step`: the exact-MDP state
`(a, D, xa, pa, h, xh, ph)` as `scripts/sop_mdp.py` defines it, computed
from the race model's variables (D = attacker weight minus honest weight
including honest pending per the 2026-10-20 rule; x = objects a branch
holds past its first block, capped at 32 and collapsed once either passes).
These are the quantities the sim strategy also has. One difference from
the exact MDP: the race model's objects give-up also fires while the
attacker holds no block and drops its pending shares; the environment
keeps that behaviour (it is the calibrated model).

Actions and their effect: exactly the four of `sop_mdp.py` (hold, publish
when h == 0, reveal only if the network accepts, give up). Reward per step
is `fa - rho * (fa + fh)` where fa / fh are the attacker / honest blocks
settled by that step.

Decisions are taken after every object (block or share), as in the sim.

State equivalence with the sim (my call: a step 0 of the ladder). A unit
test builds `branch_weights()`-style tuples for hand-made forks and
asserts that the `learned` strategy's observation builder and the
environment produce the same `(a, D, xa, pa, h, xh, ph)`. The sim strategy
additionally logs its observation at every decision, so the smoke cell
(step 4) can compare the visited-state distribution with the race model's
and report the fallback rate. A mismatch here is the most likely way the
sim result could silently diverge from training.

### Learner (my call: tabular average-reward Q-learning with rho bisection)

- Q-table keyed by the observation with the D and p fields clipped for the
  key only (|D| <= 128, p <= 48; the game itself is uncapped). States are
  created on first visit (dict of numpy rows); expected size is the
  visited subset of the 7-int space, well under the exact solver's counts.
- Relative-value (RVI) Q-learning for average reward: `Q(s,a) += lr * (r
  - Q(s_ref, a_ref) + max Q(s') - Q(s,a))` with the reference pair fixed
  at (START, hold), which anchors the table and avoids the drift of a
  running gain estimate. Epsilon-greedy exploration decaying from 0.3 to
  0.02. Illegal actions are masked, not punished. Settled rewards arrive
  in bursts (at reveal, publish, give up); that is normal for this
  objective and needs no shaping.
- Outer loop: bisection on rho exactly as in `sop_mdp.py` (bracket 0.05 to
  0.80, tolerance 1e-3 is enough: the sims resolve ~0.01). Each rho gets a
  fixed object budget (start at 2e8 objects, ~14 min at the race model's
  speed; tune). The bisection direction is decided by the gain of the
  GREEDY policy measured in a separate rollout (2000 d, 3 seeds), never by
  the learner's internal estimate.
- Acceptance and budget (my call): "strictly more than stubborn" means
  the greedy policy's mean share over 5 seeds x 2000 d exceeds stubborn's
  by at least 0.01 (race-model seed noise at 2000 d is ~0.001, measured
  2026-10-25 on cap-3 runs: 0.1028 / 0.1024 / 0.1024). Budget: 24 h wall
  per alpha on lithium. If step 2 has not passed within that, coarsen D
  to bins of 2, then p to bins of 2, never a or h; if it still fails,
  stop and report rather than tune further.
- Output: the greedy policy as JSON, `{state: action}` over visited
  states, plus the achieved share, the rho, the visit counts, and the
  training settings. Unvisited states fall back to the stubborn decision
  in the sim (see below), and the file records that rule.

### Policy evaluation (race model)

`sop_rl.py eval --policy p.json --alpha ...` runs the policy through the
step API for 2000 d with several seeds and reports share, reveals, mean
and max reorg, and the fraction of decisions that hit the fallback. This
is the number reported for every policy before any sim time.

### Sim strategy (my call: `learned` in `agents/selfish_strategy.py`)

A new strategy name `learned` with attribute `policy_file`. On each
decision it builds the observation from `a`, `h` and `branch_weights()`
(D = weights[1] - weights[2] under the sop weigh; xa, xh = weights[3],
weights[4]; pa = weights[5] - weights[0]; ph = weights[6] - honest
embedded objects, where the strategy already has the honest weight), looks
the clipped key up, and returns the action. Unseen state: the
`window_stubborn` noown decision, logged with a counter so the cell's
check can report the fallback rate. Reveal is only attempted if the
strategy's own acceptance test passes (same as noown today), so a learned
"reveal" in a state where the network would refuse becomes a hold.

Everything else about the attacker (embedded shares, tip shares,
honest-share slot rule, reject-aware pop) stays as in the noown cells.

### Validation ladder (in order; each step gates the next)

1. Environment fidelity: step API reproduces `simulate()` exactly for the
   stubborn policy (test). Stubborn through the step API at alpha 0.45
   noown with honest shares = 0.281 +- noise.
2. Learner correctness: train on the capped game (`cap_blocks 4`, key caps
   4/4/64/24/24, own-pending ignore) and compare to the exact optimum
   from lithium's `sop_mdp.py solve` at the same caps (available this
   afternoon). Pass: within 0.01. This is the one test that catches a
   broken learner independently of the model.
3. Uncapped at alpha 0.45: learned share > 0.281 (stubborn) in `eval`
   over 3 seeds. Record the policy's reveal rate and reorg depths next to
   stubborn's: a much deeper reorg profile is the first sign of model
   exploitation and goes in the write-up either way.
4. Sim smoke: one 6 h cell at alpha 0.45 with `learned`; grep reveals,
   rejected reveals and the fallback rate before any 72 h cell.
5. Sim confirmation: 72 h cells at 0.45 (two draws), then 0.48 (two) and
   0.40 (two), compared with the race model's prediction for the same
   policy. A gap of the size seen for stubborn (0.272 vs 0.281) is a
   pass; a larger gap is a model-fidelity finding and stops the sim sweep
   until understood. The crossing estimate is a race-model result from
   the learned curve; the sims confirm it at 0.45 and 0.48. Alpha 0.50 is
   simulated only if the learned policy's race-model prediction there
   differs from stubborn's by more than the model's known over-prediction
   (0.065).

Sim budget and fleet (answered from the project): five lane boxes
(box80/81/82 16 GB, phantom/lithium 31 GB), round 5 ends ~18:00 UTC
2026-10-25 and nothing is queued after it, so the whole fleet is free for
the ladder: 1 smoke + 6 confirmation cells is one day of fleet time.
Training runs on lithium after its exact solve ends (this afternoon) or
on phantom; it never competes with the validation cells because they
come later in the ladder.

### Sim use from here on (owner, 2026-10-25)

Sims are for calibration points, implementation-dependent questions, and
final validation; sweeps and search are model work. After round 5 no
further "extra draw" cells; lane boxes idle or run calibration cells until
step 4 is reached. Validation cells go where the model says they matter.

## Deliverables

- `scripts/sop_race_model.py`: step API (`SopEnv` or similar), `simulate()`
  unchanged in behaviour; tests in `scripts/test_sop_race_model.py`.
- `scripts/sop_rl.py`: `train`, `eval`, `export`; tests in
  `scripts/test_sop_rl.py` (small-budget train on a tiny game reproduces
  the exact solver's answer at tiny caps).
- `agents/selfish_strategy.py`: `learned` strategy; unit test with a
  hand-made policy file; `agents/selfish_miner.py` attribute plumbing.
- A matrix spec `test_configs/matrix/sop_v4_learned_72h.yaml` for step 5.
- `docs/2026XXXX_sop_learned_attacker.md`: the results, the policy's
  shape in words, and the ladder's outcomes.

## Left to the builder

- Exact Q-learning hyperparameters (learning rate schedule, epsilon,
  object budget per rho), chosen by making step 2 pass.
- Whether to seed the Q-table from the stubborn policy (an optional
  warm start; must not be required for step 2).
- Table size management if visited states exceed memory: coarsen D first
  (bins of 2), never a or h.
- JSON layout of the policy file, as long as it carries the settings and
  the fallback rule.
- Where to run (lithium after its solve, else phantom), as long as it is
  not the control box.
