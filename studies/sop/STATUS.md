# SoP study: status

Status as of 2026-11-18; paths are relative to the repository root. The study is
active and works on main. Since 2026-11-13 it follows Rucknium's research
directions (one MDP framework for all countermeasures, revenue and disruption
objectives, reorg-depth output): plan and results in
`studies/sop/docs/20261113_countermeasure_mdp_plan.md`. The MDP code lives in
<https://github.com/Fountain5405/pow-countermeasure-mdp> since 2026-11-16.

The question: does Share-or-Perish (MRL #146) raise the hashrate a selfish
miner needs to profit, and what does it cost honest miners? The full write-up,
with evidence, is `studies/sop/docs/20261026_sop_attacker_search.md`, items 1-11.

## Current findings

- **Threshold.** SoP raises the profitability threshold from 0.369 to 0.4635
  of hashrate, with two honest miners, K=3 and w=16, against the strongest
  attacker the search found. The race model agrees within 0.01. Under SoP the
  classic Eyal-Sirer miner never earns more than its hashrate.
- **MDP bounds.** At alpha 0.45 the optimal attack lies between 0.45 (lower)
  and 0.7265 (upper, 4/4 caps). The solver matches pymdptoolbox and the HiGHS
  LP, and it reproduces the epsilon-OPT column of SSZ's Bitcoin table
  (item 11). The SSZ upper-bound column is not reproduced.
- **Network advantage.** When the honest path is slower than d, SoP loses
  0.03-0.21 of protection. It still beats the stock rule by 0.15-0.2 below
  alpha 0.45, and ties it at 0.45.
- **Slow honest miners lose about twice what they lose under stock:**
  10.7-14.7 % against 5.0-5.8 % on a 6 s path. The cause is a lateness cascade
  along relay chains, because monerod relays only blocks on the relayer's
  main chain. A longer d does not fix it (item 9).
- **Partial adoption** (item 10) is worse than either end for someone at every
  step tested (alpha 0.30 and 0.45). Stock nodes ban their SoP peers for 24 h.
  With the bans removed (`--sim-no-drop-score`) there is no partition, but the
  attacker takes 0.991 of the single chain. SoP needs a flag day.

- **Nakamoto disruption baseline** (countermeasure MDPs, step 1). Under plain
  Nakamoto, an attacker maximising reorgs of 11+ blocks gets one per 886
  main-chain blocks at alpha 0.25, per 228 at 0.30, per 84 at 0.35 and per 22
  at 0.45 (gamma 0; gamma 0.5 adds at most 12 %). Low gamma does not protect
  against it. A revenue-maximiser at gamma 0 causes 1.7e-3 such reorgs per
  block at alpha 0.35.

- **SoP against a disruption attacker, under MRL #146's rules (2026-11-18).**
  The attacker counts its own pending tip shares and uses the honest shares
  on the fork point (#146's slot rule, as tevador's simulator plays it).
  Reorgs of 11+ blocks per block interval, attacker maximising them:

  | alpha | 0.25 | 0.30 | 0.33 | 0.35 | 0.40 | 0.45 |
  |---|---|---|---|---|---|---|
  | SoP | 3.7e-8 | 8.9e-7 | 5.7e-6 | 2.0e-5 | 5.4e-4 | 9.3e-3 |
  | one per | ~100 y | 4.3 y | 8 months | 69 days | 2.6 days | 3.6 h |
  | Nakamoto, gamma 0 | 8.5e-4 | 3.1e-3 | 5.6e-3 | 7.8e-3 | 1.5e-2 | 2.6e-2 |

  - SoP cuts these reorgs 23,000x at alpha 0.25, 970x at 0.33, 29x at 0.40
    and 2.8x at 0.45, still the largest cut of any countermeasure here.
  - It cuts much less than the bullet below said: at 0.33, one per 8 months
    instead of one per 77 years.
  - Checks:
    - The optimal policies run in the exact SoP game at 0.38-0.48 agree
      within 1.2 sigma, with and without the window.
    - tevador's own attacker, evaluated in our model and in a per-object
      port of his simulator, agrees to 0.1-0.9 %.
    - The caps do not bind (2e-6).
  - Our 12-daemon sims' attacker uses no honest shares, which is a weaker
    attacker (2.4e-7 at 0.33, 1.4e-4 at 0.40).
  - Details: "SoP: the attacker uses the honest shares on the fork point" in
    `studies/sop/docs/20261113_countermeasure_mdp_plan.md`.
- **Every countermeasure, revenue and disruption (2026-11-18 grid, 804
  exact solves).** Same plan doc, Steps 3 and 4.
  - Revenue matches Zhang & Preneel's published values at all 71 points to
    8e-5.
  - RS and PRS raise the revenue threshold (gamma 0: 0.33 to 0.38 and 0.40),
    but leave deep reorgs where Nakamoto has them, and make them cheaper: the
    attacker keeps 0.25 / 0.19 of the chain while causing them at alpha 0.33,
    against 0.10.
  - Subchains is profitable at every alpha and Fruitchains from alpha 0.10.
  - The tie-breaking rules (UTB, UDTB, SHTB) raise deep reorgs 17-52 %.
  - Subchains and PoP cut deep reorgs 2.4-7x at alpha 0.25-0.33.
- **The revenue-optimal attacker's deep reorgs (second stage, 2026-11-18).**
  - At gamma 0 the value is unique: 8.0e-4 per block interval at alpha 0.33,
    one per 42 hours, 14 % of the disruption optimum.
  - At gamma 0.5 and 1, policies with the same optimal revenue span from
    none or almost none to most of the disruption optimum. There the number
    is a free choice of the attacker and has to be quoted as a range.
- **SoP against a disruption attacker** (countermeasure MDPs, step 2b, tight
  model). [SUPERSEDED 2026-11-18 by the first bullet above: these rates leave
  out the attacker's use of the honest shares on the fork point.] Its
  policies agree with the exact SoP game within noise at 0.40 and 0.45.
  Reorgs of 11+ blocks per block interval, attacker maximising them:
  Nakamoto (gamma 0) 8.5e-4 / 3.1e-3 / 5.6e-3 / 7.8e-3 / 1.5e-2 / 2.6e-2 at
  alpha 0.25 / 0.30 / 0.33 / 0.35 / 0.40 / 0.45 (one every 39 h ... 78 min);
  SoP 1.1e-11 / 2.1e-9 / 4.95e-8 / 4.0e-7 / 6.3e-5 / 3.8e-3 (one every
  ~340,000 years / 1,800 years / 77 years / 9.5 years / 22 days / 8.7 h).
  The 3-block case (MRL #146's example) needs the window model.
  Corrected 2026-11-17: these SoP rates use our patched daemon's acceptance
  rule: a reveal that needs the attacker's own pending tip shares is
  rejected. MRL #146's current text (2026-10-20) counts those shares. Under
  the text's rule the tight model gives 7.6e-7 at alpha 0.33 (one every ~5
  years, 15x more) and 5.2e-4 at 0.40 (one every ~2.7 days, 8x more). For
  that 0.40 policy the exact game gives 3.3e-4 with the window and 6.7e-4
  without it. The model's count variant is off by up to 27 % there, not yet
  explained. tevador's own simulator (fixed stubborn attacker, gamma 0.5)
  gives 3.9e-7 per block interval at depth 11, alpha 1/3: below our optimal
  attacker, as it should be. Against Nakamoto, SoP still cuts these reorgs
  ~7,000-fold at 0.33 and ~30-fold at 0.40, less than stated above. From
  2026-11-17 SoP is scored by #146's text ("count"; owner: canonical monerod,
  the published literature and #146 are the references). Details:
  "SoP acceptance convention" in
  `studies/sop/docs/20261113_countermeasure_mdp_plan.md`.

- **Published baselines (2026-11-17, two independent reviews).** Run
  unmodified, the authors' own code shows three errors. Aumayr et al.'s
  Bitcoin baseline is a capped upper bound: it stores 0.8589 at alpha 0.45,
  gamma 0.5, where the optimum is 0.7596. PRS still beats Bitcoin there, by
  0.07 rather than 0.17. Zhang & Preneel's PoP threshold is 0.2640 in their
  own model, not the 0.2500 in their paper. Their SHTB threshold is 0.0580,
  not 0.0652; 0.0652 is where their script's tolerance first detects a
  profit. pto's PTOSolver is unusable for rates below about 1e-6 per block,
  so every disruption result here uses exact policy iteration (howard).
  Details are under "Independent reviews" in
  `studies/sop/docs/20261113_countermeasure_mdp_plan.md`.

## Limits

- The d-sweep cells are one seed each; the attacker-side ones sit inside the
  d = 5 seed spread.
- The adoption cells are 14-node networks.
- How often real Monero nodes sit behind a run of late relays is not measured.
- The SoP revenue findings above (threshold 0.4635, MDP bounds) predate the
  2026-11-18 honest-shares correction. Whether their attackers used the
  honest shares on the fork point has not been checked.
- The countermeasure MDPs have no propagation delay. An independent simulator
  on #146 finds that delay multiplies SoP's rate of 10+ reorgs 4.5-fold at
  1 s and 81-fold at 3 s.

## Superseded docs

Each of the study's dated docs starts with a status line. Superseded:
`studies/sop/docs/20260923_sop_design.md`, `studies/sop/docs/20260925_e4_code_data_review.md` (its SoP
numbers), `studies/sop/docs/20260926_dev_branch_handoff.md`, `studies/sop/docs/20260926_sop_h10_rerun.md`,
`studies/sop/docs/20260926_exact_uncles_and_sop_controls.md` §2,
`studies/sop/docs/20261007_sop_campaign7_results.md`, `studies/sop/docs/20261019_sop_campaign8_results.md`,
`studies/sop/docs/20261022_sop_v4_results.md` and `studies/sop/docs/20261028_mrl_status.md`. SoP
findings 9 and 10 in `studies/sop/docs/20260922_selfish_mining_manuscript.md` are
superseded too. `studies/sop/docs/review/20261008_review_report.md` is the independent
review of campaign 7 (2026-10-08), with its prompt next to it; both are
historical.

## Open decisions (owner)

- The large-network adoption ladder and 5/5 MDP caps, on a 256 GB box.
- A block-granular MDP for a tight bound.
- A relay-fix experiment: forward competing tip blocks whatever the local
  fork choice.
- The attacker agent's tie reaction (polling to block notifications).
- A transaction-load cell for the first-seen knob.
- Multi-node arrival data from the stressnet monitoring hub.

## Code and daemon

- The fixes that were only on `sop-research` are on main now: the attacker's
  pool-share count on an empty branch (`61969161`), the `window_rule` 20261020
  fix (`eb070be4`), the two daemon flags (`facf47d5`, `df22d181`), the
  race-model counting changes (`b9242908`, `316bb786`) and the matrix-runner
  overlays (`96a9aede`).
- `monerod-sim` is built from `patches/series` (15 patches). SoP's PoP patch
  (`studies/sop/patches/monero-sim-pop.patch`, sha256 `3f321bde...`, the 10-30 build with
  `--sim-sop-seen-at-notify` and `--sim-no-drop-score`) is the fifth.
  `SWITCHOVER.md` says which boxes need a rebuild.
