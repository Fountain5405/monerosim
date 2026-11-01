# SoP: switching over to main

The repository reorganization of 2026-11-01 merged `sop-research` into main
(tag `handoff/sop`) and moved the study's files into `studies/sop/`
(`studies/MOVES.tsv`; report: `docs/20261101_repo_reorganization.md`). Follow
these steps once the reorganization is on main. Every step that pushes, tags
or deletes needs the owner's go-ahead, as the study's `CLAUDE.md` says.

1. **Let running queues finish in the old checkout.** Don't pull there. The
   fleet drained on 2026-11-01 at 06:21Z, so nothing should be running; check
   every box before going on.
   - **Before any checkout pulls or checks out main, move its local
     `CLAUDE.md` aside** (`mv CLAUDE.md CLAUDE.local.md`, and the same for
     `studies/sop/CLAUDE.md` if the checkout has one). Main now tracks
     `CLAUDE.md`; git replaces an ignored local `CLAUDE.md` on pull or
     checkout without a warning.
2. **Merge late commits.** If `git log origin/main..origin/sop-research` lists
   anything, merge `origin/sop-research` into main (`--no-ff`, never rebase).
   Git's rename detection carries edits to moved files over. Then `git mv` any
   new files into `studies/sop/` the way `studies/MOVES.tsv` does, add their
   rows to MOVES.tsv, commit the moves apart from content edits, update the
   references, and push (with the owner's go-ahead).
3. **Make a fresh checkout or worktree of main**, on the control box and on
   every lane box. The lane boxes' `~/monerosim` trees were rsync copies;
   replace them with real checkouts, or keep syncing but from a main checkout.
   - **Rebuild monerod-sim** with `./setup.sh --sim-binary`: `run_sim.sh` now
     refuses a binary whose recorded patches differ from `patches/series`.
     The series has 15 patches: the six SoP built before, plus nine of the
     antiproxy study's ten patches, each flag-gated (stock when its flags are
     absent). The tenth, id-consistency, is commented out.
     box80-82 (10-24 daemon) and lithium/phantom (10-30 daemon) all need the
     rebuild. Rebuild between cells, never beside a running cell: box80-82
     have 1-3 GiB free while running.
   - Retire `dot-claude/campaign9/simbin_build.sh`, which has its own six-patch
     list, or make it read `patches/series`.
   - Run the checks below.
4. **Update the drivers the reorganization couldn't** (list below).
5. **Archive and delete the branch** (with the owner's go-ahead):
   `git tag -a archive/sop-research origin/sop-research -m "sop-research before switch-over"`,
   `git push origin archive/sop-research`, then
   `git push origin --delete sop-research`.
6. **Fold anything still useful** from `HANDOFF.md` (and `FILES.md`) into
   `STATUS.md` or `CLAUDE.md`, then `git rm HANDOFF.md SWITCHOVER.md`, commit
   and push (with the owner's go-ahead).
7. **From then on, work on main** as the root `CLAUDE.md` says.

## Checks

From `HANDOFF.md`, with the new paths:

1. HANDOFF.md's test set, with the new paths:
   `venv/bin/python -m pytest -q scripts/test_selfish_matrix.py scripts/test_sop_health_check.py studies/sop/scripts/test_sop_*.py studies/sop/scripts/test_selfish_strategy_sop_mdp.py agents/test_selfish_miner.py agents/test_selfish_strategy.py studies/sop/scripts/test_gml_add_slow_nodes.py`.
   Expected: 379 passed, 1 skipped, as on sop-research (52 min on lithium;
   the skip is `test_sop_mdp_crosscheck.py`, which needs scipy).
2. With scipy and pymdptoolbox (lithium `~/mdpcheck/venv`):
   `python -m pytest -q studies/sop/scripts/test_sop_mdp_crosscheck.py`. Expected: 5 passed.
3. `venv/bin/python -m studies.sop.scripts.sop_mdp_crosscheck btc --alpha 0.35 --gamma 0 --T 95 --T-policy 0`.
   Expected: `hand_written`, `toolbox_rvi` and `highs_lp` all 0.370774.
4. `cargo test --release`, including the selfish golden tests.
5. Shadow smoke: `venv/bin/python scripts/selfish_matrix.py studies/sop/configs/matrix/sop_knob_smoke.yaml`.
   Expected: both cells healthy, every SoP daemon logging the "weight table
   armed" line, and the notify cell logging `first seen at notify`.

The reorganization ran checks 1, 4 and 5 on its build box; its report gives
the results. Checks 2 and 3 need scipy and pymdptoolbox, which the repo venv
lacks, so they were not run.

## Drivers the reorganization did not update

`studies/sop/dot-claude/` and `studies/sop/home/` are snapshots and keep their
pre-move paths. Their live originals in the control box's `.claude/campaign9/`
hard-code these; update them with `studies/MOVES.tsv`, and move the live
campaign scripts into `studies/sop/drivers/`, in git:

- specs: `test_configs/matrix/<spec>.yaml` is now `studies/sop/configs/matrix/<spec>.yaml`
  (except `pipeline_smoke.yaml`, the matrix runner's own smoke, which stays);
- `scripts/selfish_mining/sop_stuck_time.py` is now under `studies/sop/scripts/selfish_mining/`;
- RL data: `data/sop_rl` is now `studies/sop/data/sop_rl`;
- the daemon build: `patches/` plus `monero.pin` is now `patches/series` plus `monero.pin`;
- `remote_test.sh` rsyncs a fixed list: add `studies`, change `data/sop_rl` to
  `studies/sop/data/sop_rl`, and drop `pytest.ini`, which does not exist;
- `sync_tree.sh` copies `agents/ scripts/ test_configs/ gml_processing/`: add
  `studies/`, which now holds SoP's configs, scripts, data and the slow-links GML.

Unchanged: `scripts/selfish_matrix.py`, `scripts/sop_policy.py`,
`scripts/sop_health_check.py`, the agents, `matrix_runs/` and `archived_runs/`
keep their paths.

## Found by the reorganization (SoP's to fix)

- `scripts/test_monero_sim_patch.py::test_sop_does_not_score_a_peers_height_drop`
  fails. It pins the PoP patch's `hit_score` line from before the 10-30
  build, which added `|| m_sim_no_drop_score` (`df22d181`); the test was not
  updated with the patch.
- The PoP patch still has comments describing the hard-fork vote bypass that
  `1f7ac1fb` removed, and comments citing pre-move paths
  (`docs/20260930_sop_conformance.md`, `scripts/sop_oracle.py`,
  `patches/monero-sim-pop.patch`) at lines 203, 373, 1022, 1073, 1163, 1173,
  1617, 1671, 1748, 1801, 2208 and 2307. Patch bytes were left unchanged
  (their sha256 is every binary's provenance); fix them with the next rebuild.
- `scripts/sop_policy.py` stays in core: SoP wrote it and changes it, but core's
  `agents/selfish_strategy.py` imports it. Changing it means running core's
  tests too. The one core test that imported `sop_mdp` moved to
  `studies/sop/scripts/test_selfish_strategy_sop_mdp.py`.
- Core tests still read SoP files: `scripts/test_selfish_matrix.py` and
  `scripts/test_selfish_configs.py` (SoP's specs and base configs) and
  `scripts/test_monero_sim_patch.py` (the PoP patch). Move them into the study
  or settle what they check.
