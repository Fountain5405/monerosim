# Antiproxy: switching over to main

The repository reorganization of 2026-11-01 merged `feat/spy-relay-log` into
main (tag `handoff/antiproxy` plus `7c3a9ddb`) and moved the study's files into
`studies/antiproxy/` (`studies/MOVES.tsv`; report:
`docs/20261101_repo_reorganization.md`). HANDOFF.md said to keep the box
checkouts on `feat/spy-relay-log` until told; the owner gives that word. Every
step below that pushes, tags or deletes needs the owner's go-ahead, as the
study's `CLAUDE.md` says.

1. **Let running queues finish in the old checkout.** Don't pull there. The
   owner stopped all work on 2026-11-01, so nothing should be running; check
   the control box, tr and simbox3 before going on.
   - **Before any checkout pulls or checks out main, move its local
     `CLAUDE.md` files aside** (`mv CLAUDE.md CLAUDE.local.md`, and the same
     for `studies/antiproxy/CLAUDE.md`). Main now tracks `CLAUDE.md`; git
     replaces an ignored local `CLAUDE.md` on pull or checkout without a
     warning.
2. **Merge late commits.** If `git log origin/main..origin/feat/spy-relay-log`
   lists anything, merge it into main (`--no-ff`, never rebase). Git's rename
   detection carries edits to moved files over. Then `git mv` new files into
   `studies/antiproxy/` the way `studies/MOVES.tsv` does, add their rows,
   commit the moves apart from content edits, update references, and push
   (with the owner's go-ahead).
3. **Make a fresh checkout or worktree of main** on the control box, tr and
   simbox3.
   - **Rebuild monerod-sim** with `./setup.sh --sim-binary` (feed answers with
     sleeps; see CLAUDE.md). `run_sim.sh` now refuses a binary whose recorded
     patches differ from `patches/series`. The series is the boxes' R8 set,
     but with SoP's current PoP patch (sha256 `3f321bde...`) in place of the
     pre-v4 copy (`44825cd1...`), so both R8 binaries are refused until
     rebuilt. id-consistency is commented out (below).
   - Gitignored cells in the old checkouts' `test_configs/x0/cells/` belong in
     `studies/antiproxy/configs/x0/cells/` now. Regenerate them with
     `make_cell.sh` rather than copying: a cell built with `--list half` or
     stemmable CIDRs embeds the absolute path of its ban list or CIDR file
     (`studies/antiproxy/configs/x0/make_lean.py`), so a copy still points
     into the old checkout, and a regenerated one gets a new md5 for that
     reason alone. Cells with `--list none` and no stemmable CIDRs hold no
     path.
   - Run the checks below.
4. **Update what the reorganization couldn't** (list below).
5. **Archive and delete the branch** (with the owner's go-ahead):
   `git tag -a archive/feat/spy-relay-log origin/feat/spy-relay-log -m "feat/spy-relay-log before switch-over"`,
   `git push origin archive/feat/spy-relay-log`, then
   `git push origin --delete feat/spy-relay-log`.
6. **Fold anything still useful** from `HANDOFF.md` and
   `SESSION_HANDOFF_20261101.md` (the resume recipe for M1, B1, M2 and I1)
   into `STATUS.md` or `CLAUDE.md`, then `git rm` those two files and this
   one, commit and push (with the owner's go-ahead).
7. **From then on, work on main** as the root `CLAUDE.md` says. New journal
   filings cite the new paths.

## Checks

From `HANDOFF.md` section 5, with the new paths:

1. `venv/bin/python -m pytest -q analysis/mainnet/test_mainnet_tools.py studies/antiproxy/analysis/mainnet/test_monitor_series.py`.
   Expected: 48 passed (the mainnet tools stayed in core; the
   `monitor_series.py` test moved to the study).
2. `bash studies/antiproxy/docs/spy_journal/drivers/make_cell.sh --reachable 300 --spy-subnets 9 --spies-per-subnet 1 --spy-node0 600 --warmup 46800 --probe 3 --dedup 24 --list none --seed 12345`
   with the phantom calibration in place. This builds B1
   (`lean_24_none_h300_k9_w13h_p3_m1_n600_s12345`), the cell whose md5
   HANDOFF.md gives (`ca7ae836...`); HANDOFF.md's command says
   `--spy-subnets 42`, a typo (that builds the k42 cell). On the
   reorganization's build box both the pre-move tree and main produce
   `ca7ae836`.
3. The id-consistency logic driver: skip it until the patch is regenerated.
4. PoP-patch smoke runs: rerun B1 (k9 m1) and the k42 m1 stock cell (E27's
   shape) under the new binary. Expect light share within ±0.005 of the
   register's 0.0853 and 0.337, with estimator recall and precision unchanged.
5. `monerod-sim --help` lists every flag in `patches/series` (31 on the
   reorganization's build; id-consistency's two return with its patch).

The reorganization ran checks 1 and 2, and what it could of 4 and 5, on its
build box; its report gives the results.

## What the reorganization could not update

- The boxes' `~/queue/x0_queue.sh` is a copy of the repo's driver. The repo
  copy (`studies/antiproxy/docs/spy_journal/drivers/x0_queue.sh`) now reads
  cells from `studies/antiproxy/configs/x0/cells/` and runs
  `studies/antiproxy/analysis/spy/x0_calibration.py`; copy it again after
  switching. `x0_queue2.sh` and `x0_queue_simbox2.sh` hard-code their box
  checkout path, and `run_install_sim.sh` uses `$HOME/monerosim`.
- `~/queue/spy_stem_receipts.py` copies run with
  `PYTHONPATH=$HOME/monerosim/analysis/spy`, which is now
  `.../studies/antiproxy/analysis/spy`.
- The control box's observer cron calls `analysis/mainnet/pull_observer.sh`,
  which is now `studies/antiproxy/analysis/mainnet/pull_observer.sh`.
- `studies/antiproxy/docs/spy_journal/adhoc/layout_check.py` hard-codes an
  absolute path. The journal's `adhoc/` scripts are kept as they ran, with
  pre-move paths; the reorganization did not edit them.
- Comments inside the study's patches still cite pre-move paths (the
  reorganization does not change patch bytes): `monero-sim-txrelay-log.patch`
  lines 216 and 220, `monero-sim-fixed-randomx-seed.patch` lines 22 and 42.
  Fix them the next time the patches are regenerated.
- The control box's `.claude/HANDOFF.md` session log: keep machine notes in
  `CLAUDE.local.md`, findings in `STATUS.md`.

## Found by the reorganization (the study's to fix)

- **The id-consistency patch does not build.** It includes
  `p2p/id_evidence_map.h`, but the header is not in the patch: `git diff`
  leaves out untracked new files. Regenerate it with the new file included
  (for example `git add -N` the new files in the monero worktree before
  diffing), build the whole series, then uncomment its row in
  `patches/series`. Every box rebuilds after that; the provenance check
  enforces it.
- The study's patches have been built only on top of the pre-v4 PoP patch.
  On main they sit on SoP's current one; the reorganization's 15-patch build
  compiles, and check 4 is the behavioural test.
- HANDOFF.md's file list missed some files and claimed others; the
  reorganization settled each from git history:
  - moved to the study: `docs/20261028_progress_brief.md`,
    `docs/SPY_ESTIMATORS.md`, `docs/TXRELAY_LOG.md`, three smoke scenarios
    and `scripts/test_spy_ban_list.py`;
  - left in core: `agents/spy_refresh.py`, which stays with the agent library;
  - kept in core: `analysis/topology_metrics.py`, which the 2026-09 topology
    work created and the branch never changed;
  - kept in core: `analysis/mainnet/`, which the mainnet-replica work created
    on main (HANDOFF.md's "new on this branch" was wrong for it), except the
    three tools the branch added, now in `studies/antiproxy/analysis/mainnet/`
    (`collect_monitors.sh`, `monitor_series.py`, `pull_observer.sh`). The
    branch's growth of `poll_node.py` (`--peerlist-dedup`, `--dial-log`) and
    its tests stay in core with the tool;
  - of `docs/superpowers/*`, only the four specs and plans the branch added
    moved.
