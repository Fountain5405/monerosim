# SoP as an MDP: what the exact model can and cannot reach (2026-10-25)

Owner's direction (docs/20261021_research_direction_idea_SoP.txt): put SoP
into an MDP, count the states, solve it exactly if it fits, otherwise fall
back to a modified MDP or reinforcement learning. This note records where
that stands after the first day: the model (`scripts/sop_mdp.py`), its
validation, the state counts, and the truncation cost that decides the route.

## The model

State is 7 small ints: attacker blocks `a` and honest blocks `h` since the
fork, the weight difference `D` (blocks plus embedded shares, attacker minus
honest), the window counters `xa`/`xh` (objects a branch holds past its first
block, capped at 32 and collapsed once either passes), and the pending shares
`pa`/`ph`. Events are single objects (attacker with probability alpha, a
block with probability 1/16). After each event the attacker chooses hold,
publish (no honest block: its blocks become final), reveal (only when the
2026-10-20 rule accepts it: past the window and attacker weight above honest
weight plus honest pending; the attacker's own pending tip shares count only
with `--own-pending count`), or give up. Truncation caps on `a`, `h`, `|D|`,
`p` and the objects deficit force reveal-if-accepted, else publish when there
is no honest block, else give up. The objective is the long-run revenue
share, solved by relative value iteration inside a bisection on the share
(Sapirshtein-Sompolinsky-Zohar), on compact tables (~35 B per state).

## Validation (all on 2026-10-25, alpha 0.45, o5 attacker)

| check | result |
|---|---|
| vectorised enumeration/tables vs the scalar reference | exact (tests) |
| compact solver vs dense solver, small caps | exact (test) |
| relative VI vs Monte Carlo of the same chain, caps 3/3/40/12/12 | 0.1334 vs 0.1343 |
| chain Monte Carlo (3 blocks, unbounded shares) vs race model with `--cap-blocks 3` | own 0.1030 vs 0.1025, noown 0.0965 vs 0.0961 |
| race model, no cap, own-counting o5 | 0.2245 vs the sims' four-draw mean 0.224 |

Two bugs found on the way, both fixed:

- The hand-written stubborn policy (`stubborn_action`, `v_stubborn_masks`)
  tested "at a cap and not accepted, give up" before "no honest block,
  publish", so an attacker reaching the block cap with no honest block
  threw its blocks away. At 3-block caps that was two thirds of the
  revenue (0.033 instead of 0.103). The optimiser's action set never had
  the bug; only the validation chain did.
- Caps that cannot reach the window are silently meaningless: a branch's
  window counter only advances on its own blocks after the first, by one
  plus the embedded shares, so `(blocks - 1) * (1 + p_max) < 32` means no
  reveal is ever accepted. The 3/3/40/12/12 timing run scored the stubborn
  chain 0.000 and "found" honest mining optimal for that reason. The CLI
  now warns.

One modelling difference remains and is documented rather than changed: the
race model's objects give-up also fires while the attacker holds no block,
and then drops the attacker's pending shares; the chain keeps them (they are
still valid shares on the public tip). It is worth about 5 % of the share
at 3-block caps (0.107 vs 0.1025). Which one the 12-daemon sims do has not
been checked.

## State counts

| caps a/h/|D|/p/deficit | states | note |
|---|---|---|
| 3/3/40/12/12 | 768,846 | window unreachable |
| 3/3/48/20/20 | 7,981,414 (stubborn chain 5,641,188) | window reachable, 3 blocks |
| 4/4/64/24/24 | 85,108,639 | 196,806 past the window; enumerated on lithium in 70 min |
| 5/5/96/32/32 | > 11 GB to enumerate on the control box; likely several 1e8 | not counted yet |

The shares dominate: the (D, pa, ph) cube is the bulk, and every extra block
per side multiplies it.

## What the block caps cost (race model, `hunt --cap-blocks N`, 2000 d, seed 1)

| cap | own-counting o5 | noown o5 |
|---|---|---|
| none | 0.2245 | 0.1712 |
| 3 | 0.1028 | 0.0965 |
| 4 | 0.1187 | 0.0975 |
| 5 | 0.1627 | 0.1234 |
| 6 | 0.1983 | 0.1469 |
| 8 | 0.2215 | 0.1661 |
| 10 | 0.2242 | 0.1703 |

Reorgs average 3.2 blocks deep and run to 12-15, so the stubborn attacker
needs 8 blocks per side before the truncation stops biting. An exact
object-level MDP at 8/8 blocks with shares to 24-32 per side is far beyond
what fits in 31 GB (4/4 is already 85 M states).

What a capped solve still gives: the optimum of the capped game is a valid
LOWER bound on the real optimum, because every forced action at a cap is a
legal action in the real game. At 4/4 the stubborn policy itself scores
0.119 (own) / 0.098 (noown) in the capped race model, so the 85 M-state
optimum will land somewhere above that and well below what the uncapped
optimum could be.

## Route

1. The 4/4/64/24/24 solve on lithium (owner's order) runs when lithium is
   idle; the first attempt beside four sim cells was OOM-killed at 12.4 GB
   RSS. Read it as a lower bound only.
2. To approach the real optimum the state has to shed the share dimensions:
   either a block-granular abstraction with shares as (binned) weights, or
   the owner's alternative, reinforcement learning on the race model
   (`sop_race_model.py` Model B is the environment; the stubborn policy is
   the baseline to beat). That choice is the owner's.
