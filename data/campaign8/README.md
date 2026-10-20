# Campaign 8 analysis outputs

Behind `docs/20261019_sop_campaign8_results.md`. The raw run logs are not in the repository. Every file is the printed output of a repo script, run on 2026-10-19 over `archived_runs/` on the build box.

| file | command | doc section |
|---|---|---|
| `oracle_20261019.txt` | `venv/bin/python scripts/sop_oracle.py check <B2 runs> <n40 stock run>` | §3 |
| `probe_20261019.txt` | `venv/bin/python -m scripts.sop_lateness_probe replay <same runs>` | §3 |
| `flipback_20261019.txt` | `venv/bin/python scripts/selfish_mining/flipback_scan.py <same runs>` | §3 |
| `late_new_20261019.txt`, `late_all_20261019.txt` | `venv/bin/python .claude/campaign8/late_start_scan.py [<run names>]` (all 164 SoP dirs when no names) | §3 |
| `flipback_plusN_by_run_20261019.txt` | the flip-back "+N" (attacker blocks added) histogram per run, rev2 and every archived stock run | §5 |
| `reveals_stats_rev2_vs_stock.{txt,json}` | `venv/bin/python scripts/selfish_mining/sop_reveals.py stats OUT.json <6 rev2 240 h runs> <2 rev2 40-daemon runs> <3 campaign-7 stock 240 h runs>` | §4, §5 |
| `reveals_depths_rev2_vs_stock.txt` | `... sop_reveals.py depths OUT.json <same runs>` | §5 |
| `pending_shares_rev2.txt` | `venv/bin/python -m scripts.selfish_mining.sop_pending <8 rev2 runs>` (run as a module from the repo root) | §4 |
| `*_overnight_20261019.{txt,json}` | the same checks (oracle, probe, flip-back, late-start, reveal stats and depths, pending shares) on the two overnight runs, `sop_rev2_h10_a045_72h` and `sop_rev2_n40_rep` | §3–§5, §8 |
| `modelb_reconcile_40000d_seed{1,2}_20261019.md` | `venv/bin/python -m scripts.sop_race_model reconcile --days 40000 --seed N` | §6.1 |
| `modelb_hunt_a033_20000d_seed1_20261019.md`, `modelb_hunt_a040_a045_2000d_seed1_20261019.md` | `venv/bin/python -m scripts.sop_race_model hunt --alphas 0.33 --days 20000 --seed 1` and `--alphas 0.40 0.45 --days 2000 --seed 1` (Model B as built, SoP and stock) | §6.2 |
| `modelb_hunt_hs_a033_20000d_seed1_20261019.md`, `modelb_hunt_hs_a040_a045_2000d_seed1_20261019.md` | the same with `--rules sop --honest-shares` | §6.2 |
| `modelb_hunt_a040_a045_d2_2000d_seed2_20261019.md`, `modelb_hunt_hs_a040_a045_d2_2000d_seed2_20261019.md` | `... hunt --alphas 0.40 0.45 --rules sop --give-ups d2 --days 2000 --seed 2 [--honest-shares]` | §6.2 |
| `tevador_script_runs_20261019.md` | a summary of the closing `Time:` line of 8 runs of tevador's simulator (6 as published, 2 with `UNIQUE_SHARES = False`) | §6.1 |
| `attacker_embedding_check_20261019.txt` | `venv/bin/python .claude/campaign8/embed_check.py 20261019_111740_deep_hunt_smoke__share_sop2_a045_d2` (own and gossiped shares embedded per node) | §6.2 |

The `*_20261018.txt` files are the same checks on B1 and n40a (h10_long, h10_long_rep, h10_long_depth d3, n40 share_sop2, n40_depth d5), run on 2026-10-18. `late_all_offline_20261018.txt` is the full late-start scan rerun after the `--offline` handling was added.
