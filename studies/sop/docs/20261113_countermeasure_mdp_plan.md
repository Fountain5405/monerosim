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
