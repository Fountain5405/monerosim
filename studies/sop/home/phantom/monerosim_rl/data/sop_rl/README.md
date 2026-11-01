# data/sop_rl: learned SoP attacker policies

Policy tables for `strategy: learned` (agents/selfish_strategy.py), trained
by `scripts/sop_rl.py` against the race model (scripts/sop_race_model.py
`SopEnv`) with the sims' noown attacker settings: rule 20261020_noown, honest
shares via the slot rule, attacker embeds, objects-deficit cap 200. Design:
docs/superpowers/specs/2026-10-25-sop-rl-attacker-design.md; plan:
docs/superpowers/plans/2026-10-25-sop-rl-attacker.md.

## Files

- `policy_noown_a0XX.json.gz`: the policy for attacker hashrate share 0.XX.
  gzip JSON: `meta` (alpha, env, share from the race-model rollout, rho,
  converged, history, budget, settings incl. `returns` and `bins`, trained
  timestamp), `key_clip` (`d`, `p`, `d_bin`, `p_bin`: how an observation
  is clipped and binned into a table key),
  `fallback` (`sim_stubborn`), and `policy`: `"a,D,xa,pa,h,xh,ph": action`.
- `check_mdp_*.json.gz`: learner-correctness runs on the exact solver's
  capped game (ladder step 2), not for the sims.
- `logs/`: the `train` runs' stderr (one line per bisection step).

## What the policy map is

A DIFF against the simulator's own `window_stubborn` noown rule
(`scripts/sop_policy.py::sim_stubborn`): only keys where the learned greedy
action differs are stored. In every other state the strategy plays
sim_stubborn, so a policy file reads as "where the learned attacker departs
from the hand-written one". The observation is scripts/sop_mdp.py's state:
attacker blocks `a`, weight difference `D` in objects (honest pending
excluded), window counters `xa`/`xh` (capped at 32, both collapsed to 32
once either passes), pending shares `pa`/`ph`, honest blocks `h`.

## Training

```
venv/bin/python scripts/sop_rl.py train --alpha 0.45 --env race --budget 200000000 \
    --out data/sop_rl/policy_noown_a045.json.gz 2> data/sop_rl/logs/train_a045.log
venv/bin/python scripts/sop_rl.py eval --policy data/sop_rl/policy_noown_a045.json.gz \
    --alpha 0.45 --env race --days 2000 --seeds 1 2 3 4 5
```

`--behaviour stubborn` (default) follows the sim's stubborn rule with a
weight decaying 1 -> 0 over each rho's budget (off-policy warm start).
`--returns race` applies each race's full return backward when its fork
settles instead of one-step targets (a reveal's payoff then reaches the
race's first hold in one pass). `--d-bin N` / `--p-bin N` coarsen the
table key (the design's fallback when the learner cannot beat stubborn).

Never on the control box (owner rule 2026-10-25): lithium or phantom.
