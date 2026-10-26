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

(pending)

### Stage 2 (L x M x R)

(pending)

### Stage 3: the curve and the crossing

(pending)

## Fidelity audit: sims vs race model

The 72 h cells' JSONs carry the attacker's and the network's orphan rates
and the final-chain block count, which the model reproduces for the same
rule (`scripts/sop_fidelity_audit.py`). The model under-predicted the
sims' share by 0.016 at 0.45 and 0.033 at 0.50 for the same rule; the
orphan rates say whether that is network propagation (honest blocks lost
to natural forks, favouring the attacker) or a rule difference.

(pending)
