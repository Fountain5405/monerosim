# Share-or-Perish selfish-mining study: status for MRL

2026-10-28, 17:40 UTC (13:40 EDT; item 6 corrected after MRL review), Fountain5405. Full write-up with every cell and the attacker search: [docs/20261026_sop_attacker_search.md](20261026_sop_attacker_search.md).

## What we are testing and how

We are measuring whether Share-or-Perish (MRL issue #146) raises the hashrate a selfish miner needs to profit on Monero, and what it costs honest miners. Three tools, cross-checked against each other:

- **Shadow network simulations** running real monerod binaries (a patched monerod-sim that implements the SoP fork-choice rule: window K, workshare ratio w, 5 s share delay). A 12 to 14 daemon network of one to four honest miners, an attacker with a publishing bridge, relays and seeds; 72 simulated hours per cell (about 2,150 main-chain blocks at a 120 s interval), starting from a pre-mined chain snapshot at settled difficulty. Mining is real RandomX hashing, throttled to each miner's configured hashrate.
- **A race model** (Python) of the SoP rule and the attacker strategy family, run for thousands of simulated days per point. It predicts revenue, reveal and orphan rates and is checked against the sims cell by cell.
- **An attacker search** over a strategy family written for SoP. The classic Eyal-Sirer miner earns nothing above its hashrate under SoP in any cell we have run, so the threshold we quote is against the strongest attacker the search found: one that publishes every unopposed block at once, contests honest blocks with its accumulated share weight, reveals as soon as its branch outweighs the honest one, and folds once it falls six work objects (blocks plus shares) behind. An exact MDP solver and a tabular learner were run as checks; neither beat the family.

## Headline results

SoP raises the selfish-mining profitability threshold from 0.369 to 0.4635 of network hashrate at the MRL defaults (K=3, w=16) with two honest miners, against the strongest attacker we could find. The race model agrees within 0.01 at every point, and the window parameter behaves as predicted.

| Rule | Threshold, sims | Threshold, model | Attacker |
|---|---|---|---|
| Stock (longest chain) | 0.369 | 0.365 | stubborn, depth 2 |
| SoP, K=2 | 0.454 | 0.455 | SoP family, give-up 2 |
| SoP, K=3 (default) | 0.4635 | 0.468 | SoP family, give-up 6 |
| SoP, K=6 | 0.474 | 0.481 | SoP family, give-up 4 |

Thresholds are the hashrate at which the attacker's revenue share crosses its hashrate, bracketed by 72 h cells on either side (two to three seeds per point), all with the honest hashrate split over two miners. Larger windows help less and less: K=6 buys 0.01 over K=3.

**The threshold depends on how many honest miners there are, and this is today's main new result.** The model treats the honest side as one miner. SoP judges forks by the weight seen so far, so honest miners briefly disagree on the tip during a race and some honest work lands on the losing branch; the more miners, the more of it. Same seed, same attacker, K=6, alpha 0.47:

| Honest miners (5.3 h/s total) | Attacker share | Network orphan rate |
|---|---|---|
| 1 | 0.373, 0.382 (model 0.399) | 0.33 |
| 2 | 0.454, 0.436 | 0.39 |
| 4 | 0.505 (first seed, finished 16:30 UTC) | 0.39 |

One honest miner reproduces the model exactly, including its reveal and orphan rates. Each doubling of the honest miner count then adds about 0.06 to the attacker's share: 0.47 is unprofitable against one miner, marginal against two, clearly profitable against four. Monero's real hashrate sits in roughly four to six pools plus P2Pool, so the four-miner threshold is the realistic one and will be lower than 0.4635. The four-miner cell at the default window finishes at 20:45 UTC today (16:45 EDT); the eight-miner point is now worth running and goes on the 256 GB box.

**No honest-side cost with no attacker** (finished today, four cells). With every daemon on SoP, the three honest miners' revenue shares match their hashrate within noise, the main chain grows at the same rate, and the network orphan rate is 0.1 to 0.4 percent either way. The one measurable difference is tip churn: a SoP node switches chains 30 to 60 times per 72 h during natural forks as shares re-judge them, against 0 to 2 on stock. Those switches are depth 1 and net to the same orphan count, but the same mechanism is what gives the attacker its gain from honest fragmentation above.

## The mitigation case: six items and where each stands

We listed what a reviewer will ask for before SoP goes into the codebase and built an experiment for each. All six are done, running or queued.

| Item | What it answers | Experiment | Status (2026-10-28 16:50 UTC) |
|---|---|---|---|
| 1. No-attacker control | Does SoP cost an honest network anything? | 4 cells, stock vs SoP, two seeds | Done: no cost beyond depth-1 tip churn |
| 2. Honest fragmentation | How does the threshold move with 1, 2, 4, 8 honest miners? | Same attacker and seed with the honest hashrate split N ways, at K=6 and at the default window | 1, 2 and 4 done at K=6 (+0.06 per doubling); default-window N=1 and N=4 land tonight; N=8 queued for the big box |
| 3. Slow honest miner | Does the 5 s rule punish a well-behaved miner on a slow link? | Control with one miner 3 s, 10 s, 30 s from the network, stock vs SoP | First cell (10 s, SoP) running; 5 queued |
| 4. Network-advantage attacker | Does an attacker with gamma 0.5 beat SoP? (gamma = share of honest hashrate that mines on the attacker's block in a tie; ~0 in Shadow by default) | Honest path slow by hops, attacker bridges beside each miner; stock at 0.30 and 0.35, SoP at 0.35 to 0.45 | First cell (SoP, 0.45) running and healthy, result 20:30 UTC; 9 queued |
| 5. Partial adoption | Does the mitigation degrade gracefully at 25 to 75 percent adoption? | Four equal miners at 0.45, first N on SoP, half the relays adopting; 7 cells | First cell (50 percent) running, result 23:10 UTC; 6 queued |
| 6. Search-bound caveat | Is 0.4635 a proof? | The race model is restated as an exact MDP and solved by relative value iteration plus bisection (SSZ 2016, hand-written numpy, validated against Monte Carlo). It solves only at caps of 3 to 4 blocks per side (85 M states at 4/4, 12.7 h), where the optimum is honest mining; the hand-written strategies use reorgs 3 to 15 deep, so those capped optima are lower bounds on the true optimum and do not bound the family from above. A block-granular Q-learner reached 0.577 against the family's 0.725 at alpha 0.50. | Open: no upper bound yet. An optimistic-cap solve or a block-granular abstraction (shares as binned weights, caps to 8 per side) would give one; one to two days each |

## Caveats and open questions

- **The threshold is a bound from search, not a proof, and we have no upper bound yet.** The exact MDP of the race model is only solvable at 3 to 4 blocks per side, where the optimum is honest mining; the strategies that profit need deeper reorgs than those caps allow, so the capped solves are lower bounds on the true optimum (an earlier draft of this report said the MDP "could not beat the family", which misdescribed this: no solve at competitive caps exists). An upper bound needs either an optimistic-cap solve or a block-granular abstraction that reaches 8 blocks per side; we propose doing one before the write-up.
- **Honest fragmentation moves the number, by about 0.06 per doubling of miners so far.** We will report the trend and the four-miner threshold rather than the two-miner 0.4635.
- **Gamma in Shadow is ~0 by default.** Propagation is milliseconds and the attacker reacts after seeing an honest block, so the stock threshold measured here (0.369) is the gamma=0 case, slightly above the textbook 1/3. The network-advantage cells (item 4) are the first with gamma > 0; the first result lands tonight.
- **Untested:** partition-and-heal behaviour (Shadow's topology is fixed for a run), and the 5 s share delay and w=16 as parameters (we varied K only; d and w are the MRL defaults).
- **Not modelled:** transaction load (blocks are empty, so fluffy-block round trips never happen), pool-internal share propagation, and any attacker that games shares themselves beyond the hold-shares knob in the family.

## What comes next

- **Tonight, 2026-10-28 (UTC):** N=1 at the default window 19:15; gamma SoP at 0.45 20:30; N=4 at the default window 20:45; slow miner 10 s 21:30; 50 percent adoption 23:10.
- **By 2026-10-31:** the adoption curve (0, 25, 50, 75, 100 percent) at alpha 0.45, the stock reference under gamma, the remaining gamma cells at 0.35 and 0.40, and the slow-miner pairs at 3 s and 30 s. With the 256 GB box set up, the whole remaining queue (about 36 cells) fits in two or three 6.5 h rounds instead of a week, and the eight-miner cells run there at full speed (24 GB each).
- **By 2026-11-04:** the N-trend written up with the four- and eight-miner thresholds, a recommendation on K, and the full mitigation-case section of the write-up ready for MRL review.

Decisions we would like from MRL: whether the four-miner threshold (realistic fragmentation) or the two-miner one should be the headline; whether an upper bound on the attacker (optimistic-cap MDP solve or a block-granular abstraction) should come before the write-up; and whether the honest-side splitting that fragmentation exposes should be treated as a property of the rule to fix (for example by judging forks on share weight only after the 5 s delay) or as the cost of the mitigation.
