# SoP under MRL #146's rules, disruption (2026-11-18)

These are the `pcmdp.sop_tight` runs at pow-countermeasure-mdp c7f468f, with
the arguments `--own-pending count --honest-shares --q-max 0 --min-depth 11`.
Each JSON is one run: the optimal reorgs of 11+ blocks per block interval
(`g`), the stationary check (`profile.rate`) and, at alpha >= 0.38, the
optimal policy run through the exact SoP game (`exact_no_window` and
`exact_window`, 20 M objects). The write-up is in
`studies/sop/docs/20261113_countermeasure_mdp_plan.md`, section "SoP: the
attacker uses the honest shares on the fork point".

- `hs_a<alpha>_x128` uses caps x +-128 and attacker pending 128. The `_x64`
  runs (x +-64, pending 64) agree with them to 2e-6, so the caps do not
  bind.
- The honest pending count does not matter under these rules (q_max 0, 8 and
  24 agree to 2e-15), so the model leaves it out.
- `STATUS`: one line per run. The first `hs_a0.10_x128 exit 2` was a
  job-list error (`xargs -L 1` joined lines that ended in a blank). It was
  rerun.
