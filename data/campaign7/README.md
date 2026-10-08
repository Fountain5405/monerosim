# Campaign 7 stored data

The data behind `docs/20261007_sop_campaign7_results.md`.

- `analysis_out/`: stored outputs of the `scripts/selfish_mining/` analyses
  (reveal stats, ban replay, depth tests, Model B comparison and so on).
- `modelb/`: Model B (`scripts/sop_race_model.py`) results used in §3–5:
  `stock_d2`, `sop_d2/d3/d5` and the per-reveal shapes `shapes_d2/3/5`, and
  `alpha_sweep_400d_seed11.md` (α 0.30–0.45, d 1–3; the 10+ reorg rates of §5).
- Added after the 2026-10-08 review, in `analysis_out/`:
  `flipback_scan_240h_{1,5}s.txt` (day-aware scan, honest-001, 16 runs),
  `reveal_stats_banfix.json` and `depth_pooled_d5.txt` (all eight d5 runs).
- `matrix_cells/<matrix>/cells/*.json`: each simulated cell's record (run
  dir, health, attacker share), as written by `scripts/selfish_matrix.py`,
  plus the matrix `table.md`.

The raw run directories (`archived_runs/`, about 181 GB) are not in git. A
filtered extract of the 72 cited runs, laid out like `archived_runs/`, is
distributed separately as `monerosim_campaign7_evidence.tar.xz`. It keeps
every log line the analysis scripts read (block, reorg, fork-choice, P2P
scoring and ban lines; share lines for the `banfix` runs only), the run
summaries, configs and canonical chains. Machine-specific paths were
replaced (`/home/user`, `/tmp/scratch`). Unpack it in the repo root, and the
scripts run on it unchanged:

    tar -xJf monerosim_campaign7_evidence.tar.xz
    venv/bin/python scripts/sop_oracle.py check archived_runs/<run>
