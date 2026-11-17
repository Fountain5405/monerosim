# Independent review: ZP2019 / Aumayr et al. reference MDPs and our solvers

All runs on box90 under ~/mdp_work/blind/work (logs named below). Reference code was copied, not modified in place; the only edits were print statements in the copy (aum/.../SolveMDP.m) and the MDPtoolbox path.

## Q1. Aumayr et al. Bitcoin baseline (incentive_compatibility/Bitcoin/output.json)

**Answer.** output.json stores the result of the *upper-bound* bisection (SSZ "over-paying truncation" MDP), additionally capped at lower bound + 0.1. It is neither the optimal relative revenue nor a valid lower bound; at alpha 0.44-0.45 it is simply lower bound + 0.1.

Evidence (running code; high confidence):
- `Init.m:1,22` returns `lowRou`; `SolveMDP.m:30-43` is the lower-bound bisection, `SolveMDP.m:45-78` the upper-bound bisection with over-paid truncation rewards (`:53-65`) and bracket `highRou = min(rou+0.1, 1)` (`:47`); `lowRou` is overwritten there and never reset. ZP's original (`PoWSecurity/Incentive Compatibility/Bitcoin/SolveMDP.m:24,62`) stores both bounds separately; Aumayr's copy dropped those lines. RS, PRS and Fruitchains `Init.m` return the lower-bound `rou` (upper block commented out, e.g. `RewardSplitting/SolveMDP.m:25-58`), so Fig. 2 mixes a capped upper-bound Bitcoin series with lower-bound series for everything else.
- Octave re-run (jobA_aumayr_btc.log), maxForkLen 30: returned value reproduces output.json to 10 digits at all six points. Lower bound / stored: gamma 0: 0.48768/0.49090 (a=.40), 0.65874/0.75873 (a=.45); gamma 0.5: 0.57250/0.57540, 0.75892/0.85891; gamma 1: 0.66666/0.66798, 0.81776/0.91774. At a=0.45 stored = lower + 0.1 - 1.2e-5 for every gamma (cap hit).
- Independent: `NakamotoModel` + `howard.solve_average`, max_fork 30, matches the lower bounds within 7e-6 (the RVI tolerance; q1_mf30.log). ZP Results.xlsx (lmax 160): gamma 0.5 gives 0.5725 (a=.40), 0.7596 (a=.45); ours at max_fork 80: 0.5725, 0.7596.
- True gamma=0.5 curve (q2_cross2.log, max_fork 80) vs stored: a=.41 0.6061/0.6126, .42 0.6415/0.6582, .43 0.6788/0.7184, .44 0.7182/0.8179, .45 0.7596/0.8589.

Effect on the paper: the ordering in Fig. 2 (PRS < RS < Bitcoin) survives (PRS 0.690, RS 0.701 vs true Bitcoin 0.760 at a=0.45), but Bitcoin is overstated by 0.03-0.10 for a >= 0.42, the kink at 0.43-0.44 is an artifact of the 0.1 cap, and the Bitcoin-PRS gap at 0.45 is 0.07, not 0.17. Statements up to a = 0.40 are unaffected (error <= 0.003).

Safe wording: "The Bitcoin baseline in Fig. 2 is an upper-bound-branch value capped at 0.1 above the lower bound; the optimal selfish-mining revenue at gamma 0.5 is 0.5725 (alpha 0.40) and 0.7596 (0.45)."

## Q2. ZP Table II profitable thresholds, PoP and SHTB

Method: shipped `Threshold.m` run in Octave as-is (only the MDPtoolbox path changed); separately, POut/RsOut/RhOut exported from ZP's own `InitStates.m` (P is affine in alpha, exported at two alphas) and solved with my own exact ratio policy iteration (py/q2_exact.py, sparse LU; a stationary-distribution cross-check agrees to 1e-14).

**PoP (k=3).** Paper: 0.2500.
- (a) Shipped `Chain Quality/PublishOrPerish/Threshold.m` (bracket [0.25, 0.275] `:10-11`, maxB 20, test `rou >= alpha+0.0001` `:18`, with `SolveMDP.m:10` starting the rou bisection at alpha): converges to **0.26421 < PT <= 0.26426** (jobB_pop_threshold.log, 9 bisection steps). It cannot output 0.2500 unless every tested alpha were profitable, and its first midpoint 0.2625 is not.
- (b) Exact optimum: g(alpha) = alpha identically (honest policy, 2 reachable states) up to **PT = 0.26403** (maxB 16: (0.264027, 0.264033]; maxB 20: g = alpha at 0.26400, excess 1.2e-5 at 0.26405; maxB 12: 0.26408). The excess then grows about linearly: 0.0160 at a=0.30, 0.0442 at 0.35, 0.0808 at 0.40 (maxB 20), matching the paper's Fig. 2 data (0.016, 0.0443, 0.082 at lmax 30).
- Why the paper says 0.2500: not reproducible from the code. 0.25 is the last point of the paper's 0.05 alpha grid with ideal chain quality (Results.xlsx row 19); the shipped search's +1e-4 margin shifts the exact 0.2640 to 0.2642, not to 0.25. Our `pop.py` port agrees with the reference exact solve to 4e-6 in revenue (0.272393 vs 0.272395 at a=.27, maxB 12) and puts PT in (0.2640, 0.2641].

**SHTB (15 regions).** Paper: 0.0652 (labelled upper bound).
- (a) Shipped `SmallestHashTieBreaking/Threshold.m` (bracket [0, 0.1], lmax 40, test `lowerBoundReward > alpha`, where `SolveMDP.m:3-24` bisects rou to tolerance 1e-4 starting at 0.99 alpha): output **0.0653-0.0654** (jobC_shtb_threshold*.log; the run was killed twice by an unrelated process and resumed from its bracket). This reproduces the paper's 0.0652 to within the procedure's noise.
- (b) Exact optimum: **PT = 0.05801** (lmax 10: (0.058008, 0.058018]; identical excesses at lmax 20: 2.2034e-6 at 0.0585, 9.212e-6 at 0.060; at a=0.10 excess 5.488e-4 at lmax 10, 20 and 40, matching Results.xlsx's 0.0006). The shipped test needs the excess to exceed a ~1e-4 bisection/RVI noise floor; the excess is only 4.8e-5 at a=0.065, so the shipped threshold sits where noise lets it pass, 0.007 above the model's true PT.
- The value is a discretisation artefact, as the paper itself says: PT ~ 1/regions (exact: 15 regions 0.0580, 10 regions 0.0818, 5 regions 0.1387). Our `tie_breaking.SmallestHashTieBreakingModel` agrees with the reference exact solve to 1e-12 at lmax 10 (q2_cross2.log).

Safe wording: "In ZP's PoP MDP (k=3) the attacker's optimal revenue first exceeds alpha at alpha = 0.2640, not 0.25; in their 15-region SHTB MDP at 0.0580, not 0.0652; the 0.0652 is what their threshold script's tolerance detects. The remaining Table II entries were not checked here."

## Q3. Solver accuracy (q3_revenue.log, q3_disruption.log, q3_tiny.log, q3_tiny2.log)

Check: own stationary-distribution solve of the returned policy, plus a Bellman-residual certificate from an own bias solve (py/q3_check.py).

**howard.solve_average: correct across the whole range.** Nakamoto revenue (max_fork 20/40, gamma 0/0.5, a 0.20-0.45): g equals the stationary value to 1e-13, Bellman gap <= 1e-12 (optimal). Disruption (min_depth 11, time normalisation) from 2.6e-2 down to 6.49e-12 (a=0.04): g agrees with the stationary value to 1e-8 relative at 6e-10 and 5e-7 relative at 6.5e-12 (round-off of the start-column solve), Bellman gap at round-off. Policies optimal on all reachable states.

**PTOSolver (expected_horizon 1e5, epsilon 1e-5): values biased, policies fine for g above ~1e-6, unusable below.**
- Revenue: value low by 2e-5 to 9e-5 absolute (e.g. 0.663252 vs exact 0.663340); relative bias ~10/H; horizon 1e6 cuts it 10x. The returned policies, evaluated exactly, are optimal (Bellman gap 0); they differ from Howard's only on unreachable states.
- Disruption 1e-5..2.6e-2: value low by 2e-4 relative at H=1e5 (2e-6 at 1e7); policies optimal.
- Disruption g <= 1.6e-7 (a <= 0.10): the returned policy takes an illegal action on reachable states with the default epsilon at every horizon tested, and at a <= 0.05 with epsilon 1e-30 as well; at a=0.06, epsilon 1e-30, H=1e7 the policy is legal but the reported value is 1.67e-16 against a true 6.30e-10. Mechanism: `pto_solver.py:55` zeroes transitions into the final state, so under mdptoolbox's PR computation an illegal action looks like reward-0 termination and ties with legal actions whose V is ~g*H; mdptoolbox `PolicyIteration` starts from the reward-greedy (Illegal-almost-everywhere) policy and stops when span(V - Vprev) < epsilon, i.e. as soon as g*H < 1e-5.

Safe wording: "Howard values are exact to round-off and certified optimal; PTO values carry a ~10/H relative downward bias, and PTO must not be used for rates below about 1e-6 per block."

## Not settled
- SHTB exact PT at lmax 40 directly (the 189k-state LU took over an hour per solve; lmax 10 and 20 agree to 7 digits, so 0.0580 is settled for the model).
- The other Table II entries (NC, UTB, UDTB) and all subversion-gain / censorship numbers.
- Whether MATLAB's RVI gives exactly 0.0652 where Octave gives 0.0653 (noise level).
- SoPWalkModel at very low alpha was not completed (stopped for time); the 1e-12 regime was covered with NakamotoModel at alpha 0.04.
