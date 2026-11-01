# studies/antiproxy — HANDOFF for the reorganizing agent

Branch: `feat/spy-relay-log` (tag `handoff/antiproxy` on this commit). The spy-node /
anti-proxy study: measuring and defending against Monero peer-list infiltration and
Dandelion++ origin tracing. This file describes the branch's state at 2026-11-01.

## 1. Status

- **Current findings live in `docs/20261027_findings_summary.md`** (Findings 1-8, counters
  E1-E71 / P1-P67 / 111 registered runs). It supersedes the `progress-brief` orphan branch.
- **The full experiment log is `docs/SPY_EXPERIMENT_JOURNAL.md`** (entries, pre-registered
  predictions, decisions, run register) plus per-run artifacts in `docs/spy_journal/runs/`.
- Superseded/corrected: `docs/superpowers/specs/20261030-per-host-peerlist-accounting-design.md`
  appendix A corrects its own section 1 (stock white list is ALREADY one-per-host; the defense
  is gray-side only) — the spec is current WITH that appendix. The P62-P67 filings carry a
  correction block in the journal (10-31 05:10): the port-multiplication premise was wrong for
  the lab's cells (m daemons get distinct IPs, not shared-IP ports).
- **Stopped by the owner 2026-11-01 ~11:20 UTC**: queues empty, nothing running. Four finished
  cells are UNSCORED (M1, B1, M2, I1 — data on the boxes; recipe in SESSION_HANDOFF_20261101.md).
  The R9 patch (id-consistency) is committed (b051d548) and unit-validated but NOT built on any
  box; the S1-S3 cells are unfiled and unqueued.
- `docs/20261028_hashrate_gating_arithmetic.md` is byte-identical to the `hashrate-gating`
  orphan branch's README → **both `hashrate-gating` and `progress-brief` branches can be
  deleted**; their content is in docs/ (verified 2026-11-01).

## 2. Files

Owned by this study (move under studies/antiproxy/): docs/SPY_EXPERIMENT_JOURNAL.md,
docs/20261018_spy_node_defenses.md, docs/20261027_findings_summary.md,
docs/20261028_hashrate_gating_arithmetic.md, docs/20261030_monero_p2p_code_map.md,
docs/spy_journal/** (runs, drivers, adhoc, logs), docs/superpowers/{specs,plans}/*,
docs/X0_CALIBRATION.md, patches/monero-sim-*.patch (the sim-flag patches; see §4 for the
shared ones), analysis/spy/**, analysis/topology_metrics.py, analysis/mainnet/**
(see below), test_configs/x0/** (generator + scenario), scripts/spy_ban_list.py,
studies/antiproxy/**.

Branch changes OUTSIDE the study's own files, each with its reason:
- `setup.sh` — (a) `--sim-binary` option help text listing the sim patches; (b) the
  `patches=(...)` array in `install_sim_monerod` grew from 14 to 16 entries (ports-per-host,
  id-consistency). SoP's copy lacks these two patches; after the merge the array must keep all
  16 or the boxes' R9+ builds silently drop them.
- `run_sim.sh` — `archive_daemon_logs` also collects `peerlist_dump.jsonl` (the peerlist-dump
  patch's output) into run archives; without it the list-share metrics have no source.
- `scripts/calibrate.py` — `_get_core_count` honors `MONEROSIM_CORES` so cells generate
  byte-identically on any box (make_cell.sh pins 32). Pure addition, no behavior change when
  the env is unset.
- `analysis/mainnet/` — NEW on this branch (README, poll_node.py growth: --peerlist-dedup /
  --dial-log; collect_monitors.sh, monitor_series.py, pull_observer.sh, test_mainnet_tools.py).
  Passive measurement tooling for the owner's nodes + observer.monerodevs.org. 48 tests pass
  (`venv/bin/python -m pytest analysis/mainnet/test_mainnet_tools.py -q`).
- `docs/PERFORMANCE_AND_SCALE.md` — +29 lines: the KSM/1h-warmup box-sizing section from this
  study's 300-relay cells.
- `src/agent/user_agents.rs` — wallet-cleanup skip for agents whose daemon cycles under peer
  turnover (false StoppedByShadow failures, run 86). Small, isolated, benefits any study using
  turnover cells.
- Shared with SoP: `patches/monero-sim-pop.patch` is SoP's PoP patch carried at pre-v4 state
  on this branch (flag-gated OFF; no antiproxy cell ever sets it). After the merge, SoP's
  current PoP patch supersedes ours — see §6 smoke runs.

## 3. Daemon

Apply order = the `patches[]` array in setup.sh (`install_sim_monerod`); sha256 of each patch:
`studies/antiproxy/patch_sha256.txt` (16 entries). Base: Monero v0.18.5.1 (patches/monero.pin),
plus monero-fakechain-hardforks.patch first.

Machines (R8 binary in service on both; the R9 rebuild was stopped by the owner mid-flight):
- `zenith2alpha` (ssh alias `tr`, antiproxy@192.168.1.33), checkout `~/monerosim`: provenance
  → `studies/antiproxy/provenance/tr_antiproxy.txt`. Account shared with the PoW/selfish-mining
  study historically; currently only this study uses it (the selfishmining work moved off-box).
- `simbox3` (ssh alias, lever65@192.168.1.176), checkout `~/monerosim`: provenance →
  `studies/antiproxy/provenance/simbox3_lever65.txt`. Shared VM with other users; the account
  is ours alone.
- Control box (this machine, antiproxy@192.168.1.140): no daemons run here; it generates cells
  (`make_cell.sh`, needs `~/.monerosim/calibration.json`, md5 e5276ee06c11 — copy preserved at
  `studies/antiproxy/phantom_calibration.json`) and holds local-only mainnet data.

## 4. Running and queued work

None (stopped by owner 2026-11-01). Resume state, data locations and the R9/S-cell recipe:
`studies/antiproxy/SESSION_HANDOFF_20261101.md`. Paths that need rewriting after the move:
run_sim.sh and setup.sh are invoked from the box checkouts at `~/monerosim` (checkouts stay on
`feat/spy-relay-log` — do NOT switch them until told); queue drivers read
`docs/spy_journal/drivers/x0_queue.sh` and write `~/queue/x0_queue.events`; the journal's
decision rows and the run register cite `docs/spy_journal/runs/<id>/` paths (historical —
leave as-is; only NEW filings need the studies/antiproxy/ prefix).

## 5. Checks after the move

- `venv/bin/python -m pytest analysis/mainnet/test_mainnet_tools.py -q` → 48 passed.
- `bash docs/spy_journal/drivers/make_cell.sh --reachable 300 --spy-subnets 42
  --spies-per-subnet 1 --spy-node0 600 --warmup 46800 --probe 3 --dedup 24 --list none --seed
  12345` → md5 ca7ae836... (k9-m1 cell, byte-identical: proves the generator + calibration +
  MONEROSIM_CORES path survived the move).
- The id-consistency logic driver: compile `studies/antiproxy`'s five-scenario driver (in the
  patch commit message, b051d548) → ALL PASS.
- **PoP-patch smoke runs (SoP v4 PoP supersedes ours)**: our cells never set
  `--sim-publish-or-perish`, so PoP is inert in every antiproxy result. Smoke: re-run one
  stock cell (e.g. the k42 m1 shape, E27's) and the k9 m1 baseline B1 under the merged binary;
  expect light share within ±0.005 of the register's values (0.337, 0.0853) and estimator
  recall/precision unchanged. Also `monerod-sim --help` still lists all 16 sim flags.
- Configs in active use: the six X3b cells and P62-P67 cells in `test_configs/x0/cells/`
  (gitignored; regenerate via make_cell.sh — md5s are in the journal filings).

## 6. Known problems

- Fix only on this branch: the 16th-patch id-consistency work (b051d548) is unbuilt on the
  boxes; the port-front generator feature (same-IP daemons) is designed but unwritten
  (journal correction 3560f58a).
- Main-side: none known to conflict except SoP's newer PoP patch (see smoke runs).
- Half-finished: M1/B1/M2/I1 scoring; R9 binaries; P68-P70 filings; the upstream per-host note.
- M2's run exited 1 from the post-run calibration scorer (data intact, cause undiagnosed).
