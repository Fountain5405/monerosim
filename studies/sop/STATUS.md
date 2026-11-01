# SoP study: status

Status as of 2026-11-01; paths are relative to the repository root. The study is
active, but the owner paused new
experiments on 2026-10-31 until the repository reorganization lands. Nothing
runs or is queued on any machine.

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

## Limits

- The d-sweep cells are one seed each; the attacker-side ones sit inside the
  d = 5 seed spread.
- The adoption cells are 14-node networks.
- How often real Monero nodes sit behind a run of late relays is not measured.

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
