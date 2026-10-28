# Share-or-Perish selfish-mining study: status for MRL

2026-10-28, Fountain5405. Full write-up with every cell and the attacker search: [docs/20261026_sop_attacker_search.md](20261026_sop_attacker_search.md).

## What we are testing and how

We are measuring whether Share-or-Perish (MRL issue #146) raises the hashrate a selfish miner needs to profit on Monero, and what it costs honest miners. Three tools, cross-checked against each other:

- **Shadow network simulations** running real monerod binaries (a patched monerod-sim that implements the SoP fork-choice rule: window K, workshare ratio w, 5 s share delay). A 12 to 14 daemon network of two to four honest miners, an attacker with a publishing bridge, relays and seeds; 72 simulated hours per cell (about 2,150 main-chain blocks at a 120 s interval), starting from a pre-mined chain snapshot at settled difficulty.
- **A race model** (Python) of the SoP rule and the attacker strategy family, run for thousands of simulated days per point. It predicts revenue, reveal and orphan rates and is checked against the sims cell by cell.
- **An attacker search** over a parametrised family of stubborn strategies (publish lead, reveal margin and depth, give-up rules, share holding), plus an exact MDP solver and a tabular learner as cross-checks. The threshold we quote is the best attacker the search found, not the classic Eyal-Sirer miner, which SoP neutralises outright (0.000 revenue above hashrate in every earlier campaign cell).

## Headline results

SoP raises the selfish-mining profitability threshold from 0.369 to 0.4635 of network hashrate at the MRL defaults (K=3, w=16), against the strongest attacker we could find. The race model agrees within 0.01 at every point, and the window parameter behaves as predicted.

| Rule | Threshold, sims | Threshold, model | Attacker |
|---|---|---|---|
| Stock (longest chain) | 0.369 | 0.365 | stubborn, depth 2 |
| SoP, K=2 | 0.454 | 0.455 | param family, G=2 |
| SoP, K=3 (default) | 0.4635 | 0.468 | param family, G=6 |
| SoP, K=6 | 0.474 | 0.481 | param family, G=4 |

Thresholds are the hashrate at which the attacker's revenue share crosses its hashrate, bracketed by 72 h cells on either side (two to three seeds per point). Larger windows help less and less: K=6 buys 0.01 over K=3.

**No honest-side cost with no attacker** (finished today, four cells). With every daemon on SoP, the three honest miners' revenue shares match their hashrate within noise, the main chain grows at the same rate, and the network orphan rate is 0.1 to 0.4 percent either way. The one measurable difference is tip churn: a SoP node switches chains 30 to 60 times per 72 h during natural forks as shares re-judge them, against 0 to 2 on stock. Those switches are depth 1 and net to the same orphan count.

## Why the sims give the attacker slightly more than the model

The sims run 0.01 to 0.04 above the model's revenue at the same hashrate, and we now know why: the model treats the honest side as one miner, while the sims split it across two. A test with the whole honest hashrate on one miner (K=6, alpha 0.47, two seeds) reproduced the model exactly: revenue 0.373 and 0.382 against the model's 0.399, the same reveal rate (18.7 and 19.9 reveals per 1,000 blocks found against 18.8) and the same orphan rate (0.332 and 0.342 against 0.332). The same seeds with two honest miners gave 0.454 and 0.436.

Splitting the honest side helps the attacker because SoP judges forks by the weight seen so far, so honest miners briefly disagree on the tip during a race and some honest work lands on the losing branch. The model is therefore SoP's best case; the sims are the honest number, and the gap grows with the number of honest miners. Monero's real hashrate sits in roughly four to six pools plus P2Pool, so the four-miner cells running now are the ones that matter for the final threshold.

## The mitigation case: six items and where each stands

We listed what a reviewer will ask for before SoP goes into the codebase and built an experiment for each. All six are done, running or queued; the full set finishes within about a week of simulation time on five lane boxes.

| Item | What it answers | Experiment | Status (2026-10-28 15:00 UTC) |
|---|---|---|---|
| 1. No-attacker control | Does SoP cost an honest network anything? | 4 cells, stock vs SoP, two seeds | Done: no cost beyond depth-1 tip churn |
| 2. Honest fragmentation | How does the threshold move with 1, 2 or 4 honest miners? | N=1, N=2 (done), N=4 at the default window and at K=6 | N=1 and N=4 running; K=6 N=4 seed 1 due today |
| 3. Slow honest miner | Does the 5 s rule punish a well-behaved miner on a slow link? | Control with one miner 3 s, 10 s, 30 s from the network, stock vs SoP | First cell (10 s, SoP) running; 5 queued |
| 4. Network-advantage attacker | Does an attacker with gamma 0.5 beat SoP? | Honest path slow by hops, attacker bridges beside each miner; stock at 0.30 and 0.35, SoP at 0.35 to 0.45 | First cell (SoP, 0.45) running and healthy; 9 queued |
| 5. Partial adoption | Does the mitigation degrade gracefully at 25 to 75 percent adoption? | Four equal miners at 0.45, first N on SoP, half the relays adopting; 7 cells | Queued, starts today on the large boxes |
| 6. Search-bound caveat | Is 0.4635 a proof? | Exact MDP (a lower bound only) and a tabular learner could not beat the hand-written family | Done: stated as a bound from search, not a proof |

## Caveats and open questions

- **The threshold is a bound from search, not a proof.** A stronger attacker may exist. The exact MDP is tractable only at small block caps and the learner never recovered the hand-written strategies; a parametric search over a wider family is the next step if MRL wants a tighter bound.
- **Honest fragmentation moves the number.** The 0.4635 is the two-miner value; the four-miner value will be lower. We will report the trend rather than a single threshold.
- **Gamma in Shadow is ~0 by default.** Propagation is milliseconds and the attacker reacts after seeing an honest block, so the stock threshold measured here (0.369) is the gamma=0 case, slightly above the textbook 1/3. The network-advantage cells (item 4) are the first with gamma > 0; the first result lands tonight.
- **Untested:** partition-and-heal behaviour (Shadow's topology is fixed for a run), and the 5 s share delay and w=16 as parameters (we varied K only; d and w are the MRL defaults).
- **Not modelled:** transaction load (blocks are empty, so fluffy-block round trips never happen), pool-internal share propagation, and any attacker that games shares themselves (withholding or spamming shares) beyond the hold-shares knob in the family.

## What comes next

- **By 2026-10-29:** the first network-advantage result (SoP at 0.45 under gamma 0.5) and its stock reference at 0.30; the N=4 default-window and K=6 cells; the first slow-miner pair at 10 s.
- **By 2026-10-31:** the adoption curve (0, 25, 50, 75, 100 percent) at alpha 0.45, the remaining gamma cells at 0.35 and 0.40, and the slow-miner pairs at 3 s and 30 s.
- **By 2026-11-04:** the N-trend written up with the four-miner threshold, a recommendation on K, and the full mitigation-case section of the write-up ready for MRL review.

Decisions we would like from MRL: whether a four-miner threshold (realistic fragmentation) or the two-miner one should be the headline; whether a wider attacker search is worth the compute before the write-up; and whether eight honest miners (needs a larger box or a sim-only patch that skips the RandomX dataset) matters enough to run.
