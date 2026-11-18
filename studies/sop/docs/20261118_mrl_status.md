Status (2026-11-18): current: the status report for the MRL meeting of 2026-11-18. The findings of record are in `studies/sop/STATUS.md`.

# Selfish-mining countermeasures for Monero: status for MRL (2026-11-18)

**AI/LLM statement:** This report was drafted by an AI agent (Claude) from
our results. A second AI agent fact-checked it against the data in four
passes, the last covering the checklist in section 8, and its findings are
applied.
Fountain5405 reviewed it and approved its publication.

Fountain5405. Code: <https://github.com/Fountain5405/pow-countermeasure-mdp>
(GPL-3, commit fa658b9). Data and write-up: <https://github.com/Fountain5405/monerosim>,
`studies/sop/` (commit 42c534c8). Details:
`studies/sop/docs/20261113_countermeasure_mdp_plan.md`.

## Summary

- Following Rucknium's suggestions of 2026-11-13, the countermeasures from
  Zhang & Preneel (2019) and Aumayr et al., and Share-or-Perish (MRL #146),
  are now in one MDP framework. Each is solved exactly for two attacker
  goals: revenue, and reorgs past Monero's 10-block lock (11+ blocks). SoP
  is so far solved for the deep reorgs only.
- Against an attacker who wants deep reorgs, SoP cuts their rate by 970x at
  alpha 0.33: one per ~8 months, against one per 6 hours under the current
  rule. The cut shrinks with alpha: 29x at 0.40, 2.8x at 0.45. PoP and
  Subchains cut it 2.4-2.5x at 0.33.
- Our earlier SoP figure (one per 77 years at alpha 0.33) was wrong by
  about 120x: our model differed from #146's text in two places that matter
  at this depth (section 4). A small part of the 120x comes from the old
  run's tighter state caps.
- Under #146's rule the strongest attacker our search found against SoP
  profits from 0.456 of hashrate (race model). This replaces our October
  figure (0.468 in the same model), which did not count the attacker's own
  pending shares as #146 does. A stronger attacker could profit below it
  (section 5).
- Reward splitting raises the revenue threshold at gamma 0, from 0.329 to
  between 0.35 and 0.38 (RS) and between 0.38 and 0.40 (PRS). It leaves deep
  reorgs at Nakamoto's rate and makes them cheaper for the attacker.
- Three published numbers differ from what the authors' own models give
  when solved exactly; one of them is a correct but loose upper bound
  (section 6).
- None of the models has propagation delay. In albinjm's simulator (#146),
  a fixed attacker's rate of 10+ reorgs under SoP was 1.2x tevador's
  zero-delay figure at zero delay and 4.5x at 1 s mean link delay
  (section 7).

## 1. Method

- Protocols:
  - Nakamoto;
  - reward splitting (RS) and proportional reward splitting (PRS), from
    Aumayr et al.;
  - Fruitchains and Subchains;
  - from Zhang & Preneel: the tie-breaking rules UTB, UDTB and SHTB, and
    Publish-or-Perish (PoP);
  - SoP: the chain scoring of #146's text since 2026-10-20, with zero
    delay, ties to the honest chain (the text picks at random) and without
    the window (section 4).
- The models are written from the papers (PoP from the authors' code, used
  as a specification) and checked against the authors' published values.
- Solver: exact average-reward policy iteration (Howard).
- The grid has 804 solves:
  - alpha 0.10-0.48, 12 points;
  - gamma 0, 0.05, 0.5 and 1 where the protocol has a gamma.
- Revenue is the attacker's share of block rewards. Under Nakamoto, the tie
  rules, PoP and Subchains that is its share of main-chain blocks; under RS,
  PRS and Fruitchains orphaned work is paid too.
- Disruption is majority reorgs of 11+ blocks per block interval.
  - A majority reorg removes blocks from the chain most honest miners had.
  - A block interval is the mean time for the whole network to find a block,
    at fixed difficulty. "One per" times below take it as 120 s.
- Each solved policy also gives its reorg-depth distribution.
- Checks:
  - Revenue matches Zhang & Preneel's published values at all 71 points, to
    8e-5 (their 4-digit rounding).
  - RS, PRS and Fruitchains match Aumayr et al.'s `output.json` to 8e-6.
  - Each solve's value matches a separate stationary evaluation of its
    policy: revenue to 4e-11, the 11+ rate to 8e-8 relative.
  - Where we checked (Nakamoto, Subchains, PoP, SoP), raising the
    state-space caps moves the 11+ rates by at most 4 %.
- Model limits:
  - no propagation delay beyond what gamma stands for;
  - the honest side acts as one miner;
  - one attacker, with constant hashrate;
  - no difficulty adjustment during an attack.

## 2. Deep reorgs (11+ blocks), attacker maximising them

Rate per block interval, gamma 0. UTB, UDTB, SHTB and PoP set ties by their
own rule; SoP's ties go to the honest chain. In brackets, one per, at 120 s.

| alpha | Nakamoto (= RS, PRS) | Fruitchains | Subchains | PoP | UTB / UDTB / SHTB | SoP (#146) |
|---|---|---|---|---|---|---|
| 0.25 | 8.5e-4 (1.6 d) | 8.4e-4 | 1.2e-4 (12 d) | 2.1e-4 (6.6 d) | 1.3e-3 | 3.7e-8 (~100 y) |
| 0.30 | 3.1e-3 (11 h) | 3.0e-3 | 8.7e-4 (1.6 d) | 1.1e-3 (1.3 d) | 4.1-4.2e-3 | 8.9e-7 (4.3 y) |
| 0.33 | 5.6e-3 (6 h) | 5.4e-3 | 2.2e-3 (15 h) | 2.3e-3 (14 h) | 7.0-7.2e-3 | 5.7e-6 (8 months) |
| 0.35 | 7.8e-3 (4.3 h) | 7.4e-3 | 3.8e-3 (8.8 h) | 3.6e-3 (9.3 h) | 9.5-9.8e-3 | 2.0e-5 (69 d) |
| 0.40 | 1.55e-2 (2.2 h) | 1.4e-2 | 1.05e-2 (3.2 h) | 8.6e-3 (3.9 h) | 1.8e-2 | 5.4e-4 (2.6 d) |
| 0.45 | 2.6e-2 (1.3 h) | 2.1e-2 | 2.0e-2 (1.7 h) | 1.6e-2 (2 h) | 2.8-2.9e-2 | 9.3e-3 (3.6 h) |

- **Gamma matters less than alpha.** From gamma 0 to 1, Nakamoto's rate
  rises 24 % at alpha 0.33 (42 % at 0.25, 2.9x at 0.10). Long races are won
  on length, not ties, so a low gamma does not protect against this
  attacker.
- **Paying for orphaned work makes deep reorgs cheaper.** RS, PRS and
  Fruitchains keep Nakamoto's fork choice. At alpha 0.33 the attacker who
  maximises deep reorgs keeps 0.25 / 0.19 / 0.31 of the block rewards while
  causing them, against 0.10 under Nakamoto, because its orphaned work still
  pays.
- **The tie-breaking rules raise deep reorgs** over Nakamoto at gamma 0: by
  49-52 % at alpha 0.25, 26-29 % at 0.33 and 8-14 % at 0.45. At alpha
  0.25-0.45 they are within 10 % of Nakamoto at gamma 1.
- **SoP cuts them the most:** 23,000x at alpha 0.25, 970x at 0.33, 29x at
  0.40, 2.8x at 0.45.

## 3. Deep reorgs of the revenue-maximising attacker

Many policies earn the same optimal revenue. Among them, we report the
fewest and the most 11+ reorgs per block interval.

- **At gamma 0 the number is unique.**
  - Nakamoto, alpha 0.33: 8.0e-4, one per 42 h. That is 14 % of what an
    attacker maximising deep reorgs gets.
  - At alpha 0.33, Fruitchains: 1.4e-3. PoP: 1.3e-4.
  - RS and PRS: none below their thresholds. Above them, more than Nakamoto
    (5.2e-3 against 3.1e-3 at alpha 0.40).
- **At gamma 0.5 and 1, revenue does not decide it.** For Nakamoto at alpha
  0.33 the range is 4.1e-6 to 8.7e-4 at gamma 0.5, and 0 to 2.9e-3 at
  gamma 1. The attacker picks the rate at no cost to itself, so it can only
  be quoted as a range.

## 4. SoP under #146's rules, and a correction

Our earlier SoP models departed from #146's text in two places that matter
at 11+ blocks.

1. **The attacker's own pending tip shares.** Our earlier models did not
   count them at the reveal. That followed our test daemon, whose fork
   choice runs only when a block arrives: the timing tevador confirmed at
   the 2026-10-21 MRL meeting. Shares published with the revealing block
   arrive after it, so they cannot count for it. #146's scoring text and
   tevador's appendix simulator count them. We now follow the text; which
   reading is intended is worth settling.
2. **Honest shares on the fork point.** Our MDP attacker did not use them
   (the race-model search did).
   - Under #146's slot rule, an honest share mined on the fork point also
     fits the attacker's competing first block, if its slot there is free.
   - After giving up, the attacker adopts the honest tip together with that
     tip's pending shares.
   - tevador's simulator plays both.

The corrected model is still a simplification of #146: ties go to the
honest chain (the text picks at random), there is no propagation delay, and
the window is left out. Ties to the honest chain make our rates lower
than the text's random ties would. Zero delay likely makes them lower than
a real network would give (section 7). The window has no effect at 11+ blocks where we could
check it (alpha 0.38-0.48, below).

Effect, in reorgs of 11+ blocks per block interval:
- At alpha 0.33: 4.95e-8 under the old model, 2.4e-7 with the first fix
  (~5x, partly from the old run's tighter caps) and 5.7e-6 with both (24x
  more).
- At alpha 0.40: 6.3e-5 under the old model, 5.4e-4 with both fixes.

How we found the second difference:
- tevador's own fixed stubborn attacker, run in his simulator at alpha 1/3
  with ties to the honest chain, gave 2.75e-7 and 2.89e-7 reorgs of 11+
  blocks per block interval in two runs. A per-object port of his logic
  gives 3.28e-7; his script tests once per simulated second, which lowers
  its rate.
- That was above our model's optimum of 2.384e-7 with only the first fix.
- An optimum cannot be beaten in the same game, so the games differed.
- The effect itself is not new: tevador described it in his first comment
  on #146 (2025-09-25), where the attacker uses the honest workshares in the
  first block of its private chain. Our MDPs had left it out.

Checks of the corrected model:
- **Exact SoP game.** We ran the model's optimal policies in an exact
  object-by-object simulation of the SoP game, 20 M objects each.
  - At alpha 0.38-0.48, game and model agree within 1.2 sigma.
  - There, the counts with and without the window are identical.
  - At alpha 0.33 deep reorgs are too rare to simulate, so that value rests
    on the model alone, and the window's effect there is not checked.
- **tevador's attacker, both ways.** We evaluated his stubborn attacker
  exactly in our model and in a per-object port of his script.
  - The two agree to 0.1-0.9 % at alpha 1/3, 0.40 and 0.45.
  - The 0.9 % at 0.40 is about 2.6 sigma and not yet explained.
- **Caps.** Doubling the caps (x +-64 to +-128) changes the rates by less
  than 2e-6 relative.

## 5. SoP revenue threshold (race model)

- **Under #146's rule the strongest attacker our search found profits from
  0.456 of hashrate** (K=3, w=16).
  - For comparison, in the same model a hand-written stubborn attacker under
    the stock rule needs 0.365. The optimal stock attacker needs 0.329
    (exact MDP, gamma 0).
  - The search is over a hand-written attacker family (give-up, publish and
    reveal settings): 2,184 runs of 2,000 simulated days each. The best four
    settings were then rerun at 0.0025 steps with six new seeds. A share's
    standard error is about 0.0003.
  - The attacker that sets 0.456 counts its own pending tip shares when it
    decides to reveal, as #146 allows.
- **This replaces the October figure** (MRL, 2026-10-28: 0.4635 in network
  simulations, 0.468 in this model). That figure did not count the
  attacker's own pending shares at a reveal (section 4, first difference).
  Rerun today without counting them, the same search gives 0.468-0.469
  again, so in this model the whole change comes from that rule.
- **It is an upper bound on the threshold.** It is set by the best attacker
  found; a better attacker could profit below it. There is no exact SoP
  revenue MDP under #146's rules yet.
- **The race model's honest side is one miner.** Splitting the honest
  hashrate over more pools lowers the threshold: in our October network
  simulations, under the old rule, four equal pools gave about 0.013 less
  than two.

## 6. Published numbers that differ from the authors' own models

Two separate re-checks, both done by AI agents (Claude) that we ran, not by
outside reviewers. One was blind: it was given only the papers, the authors'
code and our solver. Both ran the authors' MATLAB code in Octave, unmodified
apart from print statements and the toolbox path. They agree on every
point.

- **Aumayr et al., Fig. 2.**
  - Their stored Bitcoin baseline (`output.json`) reproduces from their
    code, but it is the upper side of their bisection, capped at lower bound
    + 0.1. Their RS, PRS and Fruitchains values are lower bounds.
  - At alpha 0.45, gamma 0.5 the stored value is 0.8589. Solved exactly
    (state caps 80 and 160 agree), the value is 0.7596, as in Zhang &
    Preneel's `Results.xlsx`.
  - Compared like for like, PRS still beats Bitcoin there, by 0.07 instead
    of 0.17.
- **Zhang & Preneel, Table II, PoP.**
  - The threshold is 0.2640 in their own model; the paper gives 0.2500.
  - Their `Threshold.m` outputs 0.2642 and cannot output 0.25.
  - albinjm independently reported 0.264 on MRL #144.
- **Zhang & Preneel, Table II, SHTB (15 regions).**
  - The paper gives 0.0652 and labels it an upper bound. The exact
    threshold of their model is 0.0580, so the bound holds but is loose.
  - 0.0652 is where their script's tolerance first detects the profit.
- **pto (Zur, Eyal & Tamar).** Applied to rates below about 1e-6 per block,
  a regime its authors did not target, its PTO solver returns wrong values.
  - Part of the cause is in pto and part in the 2025 mdptoolbox-roi release
    it uses.
  - For revenue its policies were optimal.
  - Every disruption value here uses exact policy iteration instead.

We have not contacted the authors yet.

## 7. Limits and open items

- **No propagation delay.**
  - albinjm's event simulator (#146, 2026-10-04) has ten pools, the rule
    before its 2026-10-20 change, and tevador's fixed stubborn attacker.
  - For that attacker at alpha 0.33 it finds 10+ reorgs at 1.2x, 4.5x and
    81x tevador's figure, at 0, 1 and 3 s mean link delay.
  - tevador considers 3 s a large overestimate (0.5 s realistic).
  - Our zero-delay SoP rates are therefore likely low for a real network. We
    have not built a delay-aware SoP model.
- **SoP revenue under #146's rules has no exact MDP yet.** Our earlier MDP
  upper bound (0.7265 at alpha 0.45) covers only an attacker without the two
  corrections of section 4.
- **Revenue thresholds in the grid are at grid resolution**, alpha 0.10,
  0.15, ..., 0.30, 0.33, 0.35, 0.38, 0.40, ....
- **Not covered here:** our earlier network simulations of SoP (costs to
  slow honest miners, partial adoption) are in `studies/sop/STATUS.md`. They
  ran our modified monerod, whose fork choice runs only when a block arrives
  (section 4, first difference), so a revealing chain's own pending shares
  never count. #146's scoring text counts them. Those results are for that
  reading, not for the text as our models score it.

## 8. Checklist against Rucknium's research directions

Against the gist "Research directions for selfish mining countermeasures in
Monero" (<https://gist.github.com/Rucknium/0b6e94811099bfab44e84562621d8fe1>,
updated 2026-11-12): its three next steps and the lessons it draws from the
Qubic episode.

| Gist item | Status | What we did, what we changed and why | Brief finding |
|---|---|---|---|
| Next step 1: one MDP framework for the Zhang & Preneel (2019) countermeasures, Aumayr et al. (2026) and SoP | Done | pow-countermeasure-mdp (GPL-3) has all eight protocols in Zhang & Preneel's MDP code (Nakamoto, UTB, UDTB, SHTB, PoP, Fruitchains, RS, Subchains), PRS from Aumayr et al., and SoP. SoP has no reference MDP, so it is our own model of #146's text (section 4). | Revenue matches the published values (71 Zhang & Preneel points to 8e-5; Aumayr's `output.json` to 8e-6). Three published numbers differ from the authors' own models solved exactly (section 6). |
| Next step 1: the reference code (Zhang & Preneel, Aumayr et al., Zur, Eyal & Tamar) | Changed | The protocol models are rewritten in Python and checked against the reference code's values. pto's model framework (MIT) is used as is; only its PTO solver is replaced, by exact policy iteration: for rates below about 1e-6 per block, which many deep-reorg rates are, it returns wrong values. | Section 6. |
| Next step 1: MDP + RL where an MDP is too large | Not needed so far | Every protocol is solved exactly, at up to 3.9 M states (5 M in one SoP variant run). SoP uses a reduced model, checked against an exact simulation of the SoP game at alpha 0.38-0.48. | None. |
| Next step 2: revenue maximisation | Done, except SoP | Revenue-optimal policy for every protocol, alpha 0.10-0.48, every gamma. SoP's revenue comes from a strategy search in the race model: there is no SoP revenue MDP under #146's rules yet. | RS and PRS raise the gamma-0 threshold to 0.35-0.38 and 0.38-0.40; Subchains and Fruitchains lower it. SoP: 0.456 against the best attacker found (section 5). |
| Next step 2: disruption maximisation, reorgs of depth k > 10 | Done | Majority reorgs of 11+ blocks per block interval. 11 because canonical monerod's spend lock is 10 blocks. | SoP cuts them 970x at alpha 0.33 (one per ~8 months against one per 6 hours); PoP and Subchains 2.4-2.5x. The tie rules raise them. RS, PRS and Fruitchains leave them and make them cheaper (section 2). |
| Lesson 1: larger payoffs for deeper reorgs | Done, except SoP | A second disruption objective, the summed depth of the 11+ reorgs, for every protocol but SoP. | The attacker maximising the count stops at 11-12 blocks on average. The depth-weighted one goes deeper: Nakamoto 39.5 blocks on average at alpha 0.48, gamma 0 (cap 160); the others 14-21. Whether the caps of 20-40 bind there is not tested. |
| Next step 3: the MDP outputs reorg length and frequency | Done | Each transition is tagged with the depth of the reorg it causes. The solved policy's stationary distribution gives the rate at each depth (to 40) and the mean depth. A second stage finds the fewest and the most deep reorgs among all revenue-optimal policies. | At gamma 0 a revenue-maximiser's deep-reorg rate is unique (Nakamoto, alpha 0.33: one per 42 h). At gamma 0.5 it can choose freely over 2-3 orders of magnitude, at gamma 1 from none to half the disruption optimum (section 3). |
| Lesson 2: hashrate share up to 0.38 and beyond | Done to 0.48 | 12 points from 0.10 to 0.48. Not run at 0.5 and above: the gist's adversary is a minority, Zhang & Preneel's models assume alpha < 0.5, and a majority attacker outpaces every rule here. | Section 2. |
| Lesson 3: low gamma (Qubic's below 0.05) | Done | Gamma 0, 0.05, 0.5 and 1, where the protocol has a gamma. | Gamma 0.05 gives the same thresholds as gamma 0 at grid resolution. Gamma moves revenue more than deep reorgs: from gamma 0 to 1 at alpha 0.33, Nakamoto's revenue rises 49 % (0.3306 to 0.4925), its deep-reorg rate 24 %. |
| Lesson 3: peer-to-peer de-prioritising of selfish blocks; detective mining (MRL #98) | Not covered | Outside this MDP work. | None. |
| Lesson 4: discount small revenue differences; prefer the easier implementation | Not assessed | Implementation effort is not part of this work. | The lesson is about revenue; our point is about deep reorgs. There the differences are not small: at alpha 0.25-0.33 SoP's cut is 970x to 23,000x, the others' at most about 7x. |
| Methodology: make the MDP horizon as long as the computing resources allow | Partly | State caps kept as in the reference implementations, so published values can be matched (Nakamoto and UDTB 160, UTB 80, SHTB 40, RS, PRS, Fruitchains and PoP 30, Subchains 20); SoP x +-128. Longer caps tested where feasible. | Where checked (Nakamoto, Subchains, PoP, SoP), raising the caps moves the 11+ rates by at most 4 %. |
