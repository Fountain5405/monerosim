# Repository reorganization, 2026-11-01

> Status: current. Record of the reorganization that merged the two research
> branches into main, moved research out of the core folders into `studies/`,
> and gave `monerod-sim` one patch list. One benchmark, the antiproxy B1
> cell, missed its band; the owner judged it run-to-run spread (below).

## Summary

- **Merges.** `sop-research` (tag `handoff/sop`) and `feat/spy-relay-log` (tag
  `handoff/antiproxy`, plus `7c3a9ddb`, the antiproxy `CLAUDE.md` that the tag
  left out) are merged into main with `--no-ff` merges. No history was
  rewritten. The only conflict, `docs/PERFORMANCE_AND_SCALE.md`, kept both
  sides.
- **Moves.** 1,411 files moved into `studies/`, all with `git mv`, and each
  move is a row in `studies/MOVES.tsv` (old path, new path, owner, reason).
  The move commits are pure renames; path and module-name updates follow in
  separate commits.
- **One patch list.** `patches/series` drives `setup.sh --sim-binary`,
  `update.sh`, `setup.sh --help` and run_sim.sh's capability gate.
  `run_sim.sh` now refuses a `monerod-sim` whose provenance does not match the
  series, and records each run's commit and dirty state.
- **id-consistency is out of the build.** The merged 16-patch series did not
  compile: the antiproxy id-consistency patch includes a header that it does
  not contain. Its row is commented out of the series, and the patch's bytes
  are unchanged. `monerod-sim` is built from 15 patches. The owner confirmed
  keeping it out until the antiproxy study regenerates the patch.
- **New docs.** A root `CLAUDE.md`, `studies/README.md`, a `CLAUDE.md`,
  `STATUS.md` and `SWITCHOVER.md` for each active study, a `STATUS.md` for
  the closed eclipse study, `docs/README.md` (the docs index), and a
  CHANGELOG entry.
- **One benchmark missed, and the owner let main move.** Every
  deterministic check passes, and four of the five benchmarks meet their
  bands. The fifth, the antiproxy B1 cell, gives a light share of 0.0927 from
  the final tree, outside the register's 0.0853 ± 0.005. From the pre-move
  tree, with the same binary, it gives 0.0902, just inside. Under the brief's
  rules that stopped the work before main. The owner judged the gap to be
  run-to-run spread and asked for the last step to be finished. The antiproxy
  study will investigate B1.

## Results at a glance

| Check | Result |
|---|---|
| Merges | done; one conflict, both sides kept |
| File accounting | all 2,725 pre-move files present; 1,411 moves valid; 2,458 unchanged, 267 changed, 20 new |
| Historical records | unchanged, except one status line on each of 24 dated docs in `docs/` |
| Config generation, before vs after | 147 of 147 configs identical (14,172 files each side) |
| Patch bytes | all 16 patch files byte-identical to before |
| `monerod-sim` build from the series | 15 patches build; the 16-patch series fails to compile (id-consistency, pre-existing) |
| `cargo test --release` | 201 passed, 0 failed, 1 ignored, before and after |
| pytest, per test id | no test changed outcome; 1,247 tests before, 1,248 after (15 snapshot tests no longer collected, 16 new) |
| Old-path search | no stale live references; 59 deliberate old-to-new mentions remain (lists and notes) |
| Private details (A7) | none added; the ones already published are listed below; every commit by Fountain5405 |
| Antiproxy B1 cell md5 | `ca7ae836` before and after, the handoff's value |
| Benchmarks (A8) | quickstart, refactor_gate (from one worktree), the knob smoke and the double build pass. Antiproxy B1 misses: 0.0927 after against 0.0853 ± 0.005, where the pre-move tree gives 0.0902; the owner judged it run-to-run spread |
| Run provenance | every after-run archive has `source_state.txt` (commit and dirty state) |
| Independent review | 0 critical, 5 important, 14 minor; all addressed (below) |

## Main: held back by one benchmark, then the owner's go-ahead

The brief lets main move only when every check passes. A difference beyond a
benchmark's band is a failed check. If its fix is not a path or a module
name, the change that caused it is reverted and the checks rerun. If they
still fail, main is left alone, and the branch and the report are pushed.

- **Which check:** antiproxy B1. From the final tree its light share is
  0.0927, outside 0.0853 ± 0.005. From the pre-move tree, with the same
  binary and cell, it is 0.0902, inside. A5 covers only checks that the
  pre-move state already fails, so it does not apply.
- **Why there was nothing to fix or revert:** the configs, the binary and the
  code the simulation runs are identical in both trees. Only the file layout
  and the worktree path differ. No single change can be blamed, and
  reverting the moves would undo the reorganization.
- **The rule was fixed before the result.** The pass criterion for the
  pre-move B1 run was written in the work log before that run started. The
  work stopped there, with the branch and this report pushed and main
  untouched.

**The owner's decision.** On 2026-11-02 the owner judged the 0.0025 gap
between the two B1 runs to be run-to-run spread and asked for step 10 to be
finished: the PR, the fast-forward of main, and the archive tags and
deletions under "Branches". The antiproxy study will investigate B1
(follow-ups).

## What moved

Full list: `studies/MOVES.tsv` (1,411 rows).

| Study | Files | What |
|---|---|---|
| sop | 422 | `data/` (campaign7, campaign8, sop_rl, sop_search); 22 dated docs and the MSB calibration note, `docs/assets/sop/`, the 2026-10-08 review report and prompt, SoP's four superpowers specs and plans; `scripts/sop_*` and their tests (except `sop_policy.py` and `sop_health_check.py`), `scripts/selfish_mining/`, `make_sop_scale_base.py`, `gml_add_slow_nodes.py`; `test_configs/matrix/` (136 specs, all but `pipeline_smoke.yaml`) and SoP's own configs; `gml_processing/1200_nodes_caida_slow_links.gml`; `patches/monero-sim-pop.patch` |
| antiproxy | 966 | the journal subtree `docs/spy_journal/` (922 files) and the study's dated and reference docs; four superpowers specs and plans; `analysis/spy/`; the three monitor tools in `analysis/mainnet/`; `test_configs/x0/`; three smoke scenarios; `scripts/spy_ban_list.py` and its test; ten patches |
| eclipse (closed) | 23 | 21 `eclipse_*.scenario.yaml`, `docs/eclipse_reproduction.md`, `docs/20261006_bootfast_eclipse_reproduction.md` |

Stayed in core, because core uses them or the ownership rule does not settle
them:

- **The agents**, including the selfish-mining, eclipse and spy agents
  (amendment A1). Core's Rust code and golden tests load the selfish agents,
  a core test names `agents.eclipse_fakepeer`, and the x0 generator emits
  `agents.spy_refresh`.
- **Shared scripts and the matrix runner:**
  - `scripts/sop_policy.py`: SoP wrote it, but core's `agents/selfish_strategy.py` imports it;
  - `scripts/selfish_matrix.py` and its smoke `test_configs/matrix/pipeline_smoke.yaml`;
  - `scripts/sop_health_check.py`, `scripts/selfish_mining_analysis.py` and `scripts/honest_chain_from_log.py`, with their tests.
- **The selfish-mining apparatus configs** that core tests and
  `docs/SELFISH_MINING.md` use and sop-research never changed:
  `selfish_micro.yaml`, `selfish_release2.yaml`, `selfish_scaled*.yaml`,
  `selfish_sweep*/`, `selfish_eclipse*/`, `selfish_phase2-4/`.
- **Analysis tools:**
  - `analysis/eclipse/`: a core test runs it, and the peer-list-dump patch doc documents it;
  - `analysis/topology_metrics.py`;
  - `analysis/mainnet/`: the mainnet-replica tools, created on main. Only the three monitor tools that the spy branch added moved.
- **Core specs and patches:**
  - the 2026-09 selfish-mining apparatus and withheld-blocks design specs, next to the code they describe, and the other core specs and plans;
  - the core patches: fakechain-hardforks, sim-mining, selfish-relay, peerlist-dump and tail-emission.

## Checks

**Merges and accounting.** `reorg` was cut from `origin/main` (`9d300222`)
and then merged with `handoff/sop` (`83869810`), `handoff/antiproxy`
(`c8ec2865`) and `7c3a9ddb` (`cf44b4f2`). Both research branches are fully
contained in `reorg`, with no commits after the tags. The before state for
every check is `cf44b4f2` (local tag `reorg-premove`).

File accounting compares every file in the tree before the move with the
final tree, following its MOVES.tsv path where it moved:
- **Files:** 2,725 before, all present after. The 1,411 MOVES rows are all
  pure renames, with no duplicates or deletions.
- **Bytes:** 2,458 files unchanged, 267 changed, 20 new.
- **Historical records:** the journal, run records, data, handoffs and the
  moved dated docs are byte-identical. The only exception is the one-line
  status note added to each of the 24 dated docs left in `docs/`.

**Config generation.** Every config the repo ships (147: 92 direct configs
and 55 scenarios) was generated before and after with the same binary. The
after side's paths were translated back through MOVES.tsv. All 147 outputs
are identical: 14,172 files on each side. GML files were compared as sorted
lines, because their attribute order is random per process.

**Patches and the build.**
- **Patch bytes:** all 16 patch files are byte-identical to before. The
  series order is the old `setup.sh` order, minus id-consistency. All 31
  series flags appear in the built `monerod-sim --help`.
- **The 16-patch failure:** the merged 16-patch series applies, but does not
  compile (`p2p/id_evidence_map.h: No such file or directory`). It never
  built anywhere.
- **The installed binary:** the 15-patch build (`f8dc2c38`, sha256
  `1ba9486db417586c...`) passes the new provenance check. The only later
  change to its build inputs is an error-message string in `setup.sh`.

**Tests.**
- **cargo:** `cargo test --release` gives 201 passed, 0 failed, 1 ignored,
  before and after.
- **pytest:** run per area (agents, scripts, tests, analysis, studies) on
  both sides, and compared per test id through JUnit XML, with moved test
  files mapped through MOVES.tsv.
  - **Before:** 1,247 tests (1,243 passed, 3 skipped, 1 failed).
  - **After:** 1,248 tests (1,244 passed, 3 skipped, 1 failed).
  - **No test changed outcome.**
  - **The 15 tests only before** are SoP's `dot-claude/` snapshot tests, which
    are deliberately no longer collected.
  - **The 16 tests only after** are the new series and provenance tests.
  - **Two tests moved** with the study code they import: the `sop_mdp`
    cross-check and the `monitor_series` test.
  - **Per-area counts moved with the study tests:** agents 314 → 313, scripts
    803 → 607, studies 15 → 229, analysis 115 → 99.
- **One known failure on both sides:**
  `scripts/test_monero_sim_patch.py::test_sop_does_not_score_a_peers_height_drop`.
  It pins a PoP patch line from before SoP's 10-30 build (follow-ups).
- **One test file excluded on both sides:** `analysis/eclipse/test_codec.py`
  calls `sys.exit` at import, so the analysis area runs with it ignored.

**Antiproxy B1 cell.** `make_cell.sh` builds B1
(`lean_24_none_h300_k9_w13h_p3_m1_n600_s12345`) with md5 `ca7ae836` from both
the old tree and the new one, the value in the antiproxy handoff. The
handoff's command said `--spy-subnets 42`, a typo for 9. The k42 cell is also
identical before and after (`79aaf8b8`).

**Old-path search.** Every path in MOVES.tsv, and every module name of a
moved Python file, was searched for in the live files; historical records
were skipped. None is stale. 59 lines in 4 files mention old paths on
purpose:
- `docs/README.md`'s moved-docs table;
- the "now at" notes in both SWITCHOVER files;
- the antiproxy `CLAUDE.md`'s note on journal paths.

**Benchmarks (amendment A8).** Each benchmark ran from a pinned worktree:
before at `cf44b4f2` (`runs/reorg-premove`) and after at `7ebee806`
(`runs/reorg-final`). They ran one at a time, with the same binaries and
seeds. quickstart and refactor_gate run stock `monerod`; the knob smoke and
B1 run the 15-patch `monerod-sim`. Commits after `7ebee806` change only
Markdown files.

| Benchmark | Band | Before | After | Result |
|---|---|---|---|---|
| quickstart ×1 | exact | height 179, 178 mined, 191/191 tx, medians 40 and 14 | the same; block ids also identical at all 180 heights | pass |
| refactor_gate ×2 | blocks equal; tx within 5 % | 229/228 in both runs; 2,005 and 2,008 tx created | 230/229 in both runs; 2,039 and 2,040 tx created | missed as planned, from two worktrees: blocks one apart. From one worktree, pass: blocks equal, tx within 0.1 %, per-miner median 26 against 25 (below) |
| SoP knob smoke | gate lines; counts within 10 % | 12 of 12 daemons armed in both cells, 0 exceptions, 1,012 notify lines | 12 of 12 armed, 0 exceptions, 957 notify lines | pass (notify lines 5.4 % apart). The attacker share, which is not a gate line, moved 0.554 → 0.471 in the notify cell (below) |
| antiproxy B1 | light share 0.0853 ± 0.005 (the antiproxy register) | 0.0902 (same binary) | 0.0927 | missed: 0.0024 outside the band, where the pre-move tree is 0.0001 inside (below) |
| `monerod-sim` built twice | bit-identical | the installed binary, sha256 `1ba9486d...` | a rebuild from ccache, and a full rebuild with ccache disabled (188 objects compiled): both `1ba9486d...` | pass |

**refactor_gate: the gap follows the worktree, not the code.** The planned
before-runs used a worktree whose path is two characters longer than the
after-tree's (`runs/reorg-premove` against `runs/reorg-final`). Two more tests
separate the worktree from the code:
- **pre11:** the pre-move code from `runs/reorg-pre11`, a path the
  after-tree's length;
- **same A and same B:** both commits from one worktree (`runs/reorg-same`),
  one after the other, with the run timestamp pinned (`MONEROSIM_RUN_TS`), so
  that every path in the two runs is the same.

| Run | Code | Worktree | Height / mined | Tx created / in blocks | Per-miner median | Chain of `miner-002` |
|---|---|---|---|---|---|---|
| before 1 | `cf44b4f2` | `reorg-premove` | 229 / 228 | 2,005 / 2,008 | 25 | |
| before 2 | `cf44b4f2` | `reorg-premove` | 229 / 228 | 2,008 / 2,011 | 24 | as before 1 to height 147 |
| pre11 | `cf44b4f2` | `reorg-pre11` | 230 / 229 | 2,044 / 2,013 | 24 | differs from before 1 and from after 1 from height 21 |
| after 1 | `7ebee806` | `reorg-final` | 230 / 229 | 2,039 / 2,007 | 26 | differs from before 1 from height 29 |
| after 2 | `7ebee806` | `reorg-final` | 230 / 229 | 2,040 / 2,010 | 26 | as after 1 to height 168 |
| same A | `cf44b4f2` | `reorg-same` | 230 / 229 | 2,043 / 2,012 | 26 | |
| same B | `7ebee806` | `reorg-same` | 230 / 229 | 2,042 / 2,010 | 25 | as same A to height 120 |
| same C | `cf44b4f2` | `reorg-same` | 229 / 228 | 2,005 / 2,011 | 24 | as same A to height 120, as same B to height 202 |

- **From one worktree, the final code meets the band against the pre-move
  code.** Blocks are equal, tx created and tx in blocks are within 0.1 %, and
  the per-miner median is 25 against 26 (3.8 %). The two chains are identical
  to height 120.
- **Two pre-move runs from one worktree differ too,** as runs are known to. A
  second pre-move run, same C, parts from same A at height 121, the same
  height as the final code's run. It ends at 229 blocks with a per-miner
  median of 24. Same C then shares its chain with the final code's run, same
  B, to height 202. The final code's 230 blocks and median of 25 lie inside
  the pre-move code's own spread at that worktree.
- **Across worktrees the spread is the same:** the pre-move code gives 229
  blocks from `reorg-premove` and 230 from `reorg-pre11`. The per-miner
  median is the median of five miners' counts, which run from 13 to 28 tx
  each. Runs from different worktrees part within the first 30 blocks,
  whatever the code.
- **What the simulation runs is the same in both trees:**
  - the generated configs, and the run environment apart from the worktree
    path;
  - the binaries, and every agent and script refactor_gate loads.

  The only runtime files that changed are the selfish-mining agents and
  `scripts/sop_policy.py`, in docstrings and comments, and refactor_gate
  loads neither. `run_sim.sh` changed only in its launch checks and in
  writing `source_state.txt`.
- **The gate's own verdict sits at its limit in every run.** The lowest node
  ends 21 to 23 blocks below the highest in every run but one, against a limit
  of 20: 22 in the before-runs and same C, 21 in the after-runs and same A,
  and 23 in same B. This failure is pre-existing (follow-ups). pre11 passes
  at exactly 20.

**SoP knob smoke: the band passes; the chain follows incidental file
state.** A8's band for the knob smoke is SoP's knob-gate lines, which give,
per daemon, whether the weight table was armed, the exceptions and the
notify lines. Before against after passes it. The attacker share is not a
gate line; it moved 0.554 → 0.471 in the notify cell. To see whether the
code moved it, both commits ran again from one worktree (`runs/reorg-same`)
with the run timestamp pinned (`MONEROSIM_RUN_TS`), so that every path in
the runs is the same. The pre-move code then ran a second time (C):

| Run | Code | Worktree | Full: share / blocks | Notify: share / blocks | Notify lines |
|---|---|---|---|---|---|
| before | `cf44b4f2` | `reorg-premove` | 0.513 / 80 | 0.554 / 92 | 1,012 |
| after | `7ebee806` | `reorg-final` | 0.481 / 77 | 0.471 / 87 | 957 |
| A | `cf44b4f2` | `reorg-same` | 0.422 / 64 | 0.435 / 85 | 935 |
| B | `7ebee806` | `reorg-same` | 0.438 / 80 | 0.340 / 97 | 1,067 |
| C | `cf44b4f2` | `reorg-same` | 0.407 / 86 | 0.435 / 85 | 935 |

- **C's notify cell repeats A's exactly:** every block id and block time.
  B's differs from the first mined block.
- **C's full cell differs from A's from the first block,** although code,
  path and timestamp are the same. What differs is Python's bytecode cache.
  A was the first run in a new worktree, so its agents compiled every module
  during the full cell. In B and C they compiled only the two modules the
  checkout had changed. In all three runs the notify cell ran second, with
  every module cached.
- **The inputs of A and B are the same:**
  - the config, the Shadow host file, the environment and the CPU plan;
  - the topology: the two GML files differ only in the order of attributes
    inside each element.
- **The code the simulation runs is the same.** The changed agents and
  scripts have identical syntax trees once docstrings are removed:
  `agents/selfish_miner.py`, `agents/selfish_strategy.py`,
  `scripts/sop_policy.py` and three analysis scripts. The one functional
  change, `scripts/run_sim_helpers.py`, runs from `run_sim.sh` before the
  simulation starts.
- **The first difference in any log is when the daemons start mining.**
  Native mining hashes once per 10 ms, so each daemon starts on a 10 ms grid.
  In B, all three miners of the notify cell start one step later than in A
  and C. The agents' own logs are identical, to the millisecond, until the
  blocks differ.

So, with every module cached, the pre-move code reproduces itself and the
final tree does not. Something in the tree, not in the code the simulation
runs, moves the start of mining by 10 ms. Native mining turns that into a
different chain. A change of worktree or of bytecode cache does the same.
Which file difference moves it was not isolated (follow-ups).

One run of the knob smoke therefore cannot tell a code change from an
incidental one. Across these five runs of one seed:
- the notify share runs from 0.34 to 0.55;
- the verdict "attacker beats the honest baseline (share > α = 0.47)" flips
  between runs.

**refactor_gate does not show the knob smoke's tree effect.** refactor_gate
loads none of the modules that changed, and it mines with stock `monerod`
rather than native mining. In it, the final code's run shares 202 heights
with a pre-move run from the same worktree, while the two pre-move runs part
at height 121. So the knob smoke's 10 ms step needs either the changed
modules or native mining's 10 ms grid. These runs cannot tell which.

**antiproxy B1: the register's value came from a different binary.** The
register's 0.0853 was measured on another box (simbox3) with the antiproxy
study's own R8 build. Its patch stack differs from the merged series in the
PoP patch: the merged series carries SoP's v4 PoP patch in place of the
study's older one. The antiproxy handoff asked for exactly this smoke run.
B1 never sets `--sim-publish-or-perish`, so PoP should be inert. From the
final tree, B1 gives 0.0927, steady across the window (0.091-0.095 by
quarter), which is 0.0024 outside the band. B1 was planned for the final tree
only. To see whether the merged pre-move state already misses (A5), the
pre-move tree ran it too, with the same binary. It gives 0.0902, also
steady (0.089-0.092 by quarter), and just inside the band. So the merged
pre-move state passes this check and the final tree does not, and A5 does
not apply. The two runs differ by 0.0025, half the band's tolerance. They
used the same binary, the same cell (md5 `ca7ae836`) and the same simulated
code. One run from each tree cannot tell the tree from the run-to-run
spread.

## Independent review

A fresh agent that had not seen the work reviewed the branch at `d8dbba35`.
It had the brief's rules, target layout and checks, and MOVES.tsv. It found
0 critical, 5 important and 14 minor issues. All are addressed in
`b157eb80` (moves) and `7ebee806` (content):

1. **The antiproxy make_cell check used `--spy-subnets 42`**, but the md5 it
   should reproduce is B1's (k9). Fixed in `studies/antiproxy/SWITCHOVER.md`;
   the check passes (above).
2. **The rewritten SoP `CLAUDE.md` dropped standing rules and pitfalls:** the
   perish default, the "could not beat the family" wording, the 5 s P2P
   timeouts, "Text file busy" beside lanes, `pgrep -f`, the pymdptoolbox and
   HiGHS quirks, silence about the stressnet monitoring hub, and
   `remote_test.sh`. All are restored.
3. **The move had created a core-to-study import** (`agents/selfish_strategy.py`
   importing `sop_policy`). `scripts/sop_policy.py` is back in core. The one
   core test that imported `sop_mdp` moved into the SoP study.
4. **id-consistency's exclusion needs the owner's sign-off:** given, 2026-11-01.
5. **Tracking `CLAUDE.md` silently replaces an ignored local `CLAUDE.md` on
   pull.** The CHANGELOG and both SWITCHOVER files now say to rename it to
   `CLAUDE.local.md` first.
6. **Minor issues** (14):
   - **Ownership:** `analysis/mainnet/` and `pipeline_smoke.yaml` are back in
     core.
   - **Historical records:** the journal's two box handovers and ten `adhoc/`
     scripts are restored to their original bytes.
   - **Stale instructions fixed:** three smoke-scenario headers, the eclipse
     how-to, `setup.sh`'s patch message and `update.sh --help`.
   - **Documentation fixes:**
     - the STATUS files use repository-root paths;
     - SoP's check 1 is the handoff's exact test set, with new paths;
     - the SWITCHOVER files require the owner's go-ahead before any push, tag
       or delete, and say to regenerate x0 cells rather than copy them;
     - the stale paths inside patches are listed for their owners;
     - the CHANGELOG marks the provenance refusal BREAKING.
   - **Code and tests:**
     - pytest no longer collects SoP's `dot-claude/` snapshot tests;
     - `run_sim_helpers` reads the series on first use, so a broken series
       cannot break unrelated helpers.
   - **Already fine:** the LAN IP the reviewer flagged in
     `analysis/mainnet/README.md` is back in its pre-move, untouched lines.

## Decisions made where the brief or the handoffs left room

Each was recorded as it was made. The cost if it turns out wrong is in
brackets.

1. **Agents stay in core** (amendment A1, agreed with the owner). SoP's
   FILES.md lists the selfish agents as shared, core's Rust and golden tests
   load them, and moving `spy_refresh` would change the x0 generator's output.
   No config or golden module name changed. [A later move is a small commit.]
2. **Historical records move, with their text unedited** (A2). Data, dated
   docs, the journal and run records now live in their study and keep the
   paths they were written with; MOVES.tsv translates them. [None.]
3. **The work ran in a separate worktree**, not by switching the main
   checkout, which holds the owner's untracked files. [None.]
4. **The late antiproxy commit (`7c3a9ddb`, its `CLAUDE.md`) was merged
   before the baseline**, so the baseline already had it. [None.]
5. **The id-consistency patch is out of the build**, with the owner's
   agreement. Leaving it in would have broken `setup.sh --sim-binary` for
   everyone. Its row is commented out with the reason, and the file is
   byte-identical. [Its two flags are missing from the binary until the
   antiproxy study regenerates the patch.]
6. **`update.sh` builds exactly what `setup.sh` builds.** It used to build
   only 2 of the patches, with different cmake flags (no
   `-DUSE_DEVICE_TREZOR=OFF -DCMAKE_DISABLE_FIND_PACKAGE_HIDAPI=TRUE`), and
   wrote over the running binary. It now reads the series and uses
   `setup.sh`'s flags and install step. [None: tooling, not engine.]
7. **Ownership was settled from git history where the handoffs were silent,
   too broad, or wrong.** The rule: a file belongs to the study that changes
   it; a file that core uses, or that the rule does not settle, stays in
   core.
   - **Antiproxy's patches:** its handoff's `patches/monero-sim-*.patch` glob
     would also have taken the core patches, SoP's patch and the shared
     selfish-relay and peerlist-dump patches. The study got only the ten
     patches its branch added.
   - **Antiproxy's specs:** its `docs/superpowers/*` claim would have taken 22
     core specs; the study got the four its branch added.
   - **Superpowers specs elsewhere:** SoP's sop-rev20261020 and sop-rl-attacker
     specs went to SoP, and the selfish-mining apparatus specs stayed with the
     core code.
   - **Files the antiproxy handoff missed or misclaimed:**
     - it missed `docs/20261028_progress_brief.md`, `docs/SPY_ESTIMATORS.md`,
       `docs/TXRELAY_LOG.md`, three smoke scenarios and
       `scripts/test_spy_ban_list.py`, all moved to the study;
     - it claimed `analysis/topology_metrics.py` and `analysis/mainnet/` as
       new on the branch, but main created them and they stay in core. Only
       the three monitor tools that the branch added moved.
   - **SoP's `test_configs/selfish_*` glob (FILES.md):** the files that core
     tests and docs use, and that sop-research never changed, stay in core.
   - **Files core uses that SoP changed:** `scripts/sop_policy.py` and the
     matrix runner's own smoke spec stay in core.
   - **Tests follow the module they test.**

   [Each is a one-commit move if a study disagrees.]
8. **The antiproxy journal subtree moved intact**, with its drivers still
   inside `docs/spy_journal/`, so the journal's relative paths keep working.
   [The drivers are not in a top-level `drivers/` folder.]
9. **SoP's `dot-claude/` and `home/` copies are snapshots.** They are not
   edited and their tests are not collected. SWITCHOVER.md lists the live
   originals to update. [None.]
10. **Move commits carry their MOVES.tsv rows**; content edits come in later
    commits.
11. **The provenance gate also covers `monerod-hf`** (a symlink to
    `monerod-sim`). For a binary the config names by path, it only warns, as
    the version pin does.
12. **No attribution trailers** on the reorganization's commits, as the
    owner asked: only Fountain5405 identities in the repo. The root
    `CLAUDE.md` now states the rule. The PR is merged by a fast-forward push,
    so GitHub adds no merge commit of its own.
13. **Benchmarks before and after** (A8, the owner's request), on top of the
    deterministic checks.
14. **Lab box names stay in the new study docs** (how A7 was read). The
    studies' own `CLAUDE.md` drafts and their switch-over steps name the
    boxes, for example which box holds the archives or how many lanes a box
    may run. The owner said such details are not critical. Addresses, logins
    and home paths were removed from every new or rewritten file. [If the
    names should go too: a small docs commit that moves them to
    `CLAUDE.local.md`.]
15. **Main moved despite the B1 miss, on the owner's call** (2026-11-02).
    The owner judged the gap between the two B1 runs to be run-to-run
    spread. [If B1's real spread is smaller than that gap, something in the
    final tree moves antiproxy results, and the antiproxy study has to find
    what.]

## Follow-ups

**Stale text inside patches.** Patch bytes were kept unchanged (rule 4). Each
of these is for the patch's owner:
- **SoP,** `studies/sop/patches/monero-sim-pop.patch`:
  - comments still describe the hard-fork vote bypass removed in `1f7ac1fb`;
  - comments cite pre-move paths at lines 203, 373, 1022, 1073, 1163, 1173,
    1617, 1671, 1748, 1801, 2208 and 2307.
- **Antiproxy:**
  - `monero-sim-txrelay-log.patch` cites pre-move paths at lines 216 and 220;
  - `monero-sim-fixed-randomx-seed.patch` cites them at lines 22 and 42;
  - `monero-sim-id-consistency.patch` is missing `src/p2p/id_evidence_map.h`.
    Regenerate it with the new file, build, then uncomment its row in
    `patches/series`.

**Core tests that read study files** (also listed in `studies/README.md`):
`scripts/test_selfish_matrix.py` and `scripts/test_selfish_configs.py` read
SoP's specs and configs, and `scripts/test_monero_sim_patch.py` pins SoP's PoP
patch.

**Pre-existing test failure:**
`scripts/test_monero_sim_patch.py::test_sop_does_not_score_a_peers_height_drop`
pins a PoP line that the 10-30 build changed (`df22d181`). For SoP to update.

**Configs that need monerod-sim only for tail emission are not gated.**
`daemon_capabilities()` reads daemon options, native mining and named
binaries. A config that needs `monerod-sim` only through `general.emission`
therefore gets neither the capability check nor the provenance check. This is
pre-existing, and worth closing.

**README claims that look out of date** (not rewritten). Its "Known
limitations → Simulation fidelity" section says that:
- block production is a Poisson timer firing `generateblocks`;
- selfish mining and reorg dynamics are not modelled;
- difficulty stays regtest-shaped, and per-block PoW is about one hash.

In fact, native mining (`general.mining.mode: native`, v0.4.0) does real,
throttled RandomX hashing with natural races. Chain snapshots preload
difficulty, and the selfish-mining apparatus and the SoP study run on native
mining. The section should say which mode each limitation applies to.

**Building each study's patches separately.** The series builds all 15
patches into one binary. The antiproxy patches have only been built on top of
PoP, and SoP's only on top of the older six. A build of core plus each study
alone would show whether the studies really are independent.

**Read-deny rules for bulky raw records**, such as
`studies/antiproxy/docs/spy_journal/runs/` (922 journal files) and
`studies/sop/data/`, so that agents do not read them by accident.

**`analysis/eclipse/test_codec.py` exits at import**, which breaks a plain
`pytest analysis`. `analysis/` is not in testpaths, so only explicit runs hit
it.

**refactor_gate sits at its height-range limit on both sides.** Seven of
the eight refactor_gate runs here fail `all_nodes_within_height_range`.
miner-001 ends 21 to 23 blocks below the tip, against a limit of 20
(`tests/baselines/refactor_gate_metrics.json`). Only the pre-move rerun from
`runs/reorg-pre11` passed, at exactly 20. The limit was set from
a spread of 0-19 at about 185 blocks. The scenario's last recorded run, on
2026-07-21 (`0ae05625`), came before the pacing fix `ec973683`, which raised
the chain to about 229 blocks over the same time. The pre-move tree fails
the same way, so the reorganization did not cause it. The limit, or the
scenario, needs a look.

**B1 against the antiproxy register.** The final tree's 0.0927 and the
pre-move tree's 0.0902 straddle the band's upper edge, 0.0903. The
register's 0.0853 came from the study's own R8 binary on simbox3, while both
runs here used the merged binary, which carries SoP's v4 PoP patch. The
antiproxy study will investigate. More B1 runs from the merged binary would
show whether its light share really sits above the register's.

**How far runs of one seed spread.** Runs are known to be close but not
deterministic. These benchmarks measured the spread for two scenarios:
- **refactor_gate:** 229 or 230 blocks, and a per-miner median of 24 to 26,
  from one worktree or from several;
- **knob smoke:** a notify-cell attacker share of 0.34 to 0.55 across five
  runs. That spread flips its verdict 3 (share > α = 0.47).

Run-to-run differences seen here follow a change of worktree path, a cold or
warm bytecode cache, and, in the knob smoke, the final tree itself. There the
first difference is a 10 ms step in when native mining starts. What moves it
was not isolated. One candidate mechanism, not verified: Shadow charges a
latency for every non-blocking syscall (`model_unblocked_syscall_latency`,
on by default, and no shipped config turns it off). So anything that changes
a process's syscall count moves its simulated clock.

For the studies: one seed run before and after a commit, even a
comment-only one, is two samples, not a test of the commit. At one seed the
knob smoke's share spread (0.21) is seven times the 0.03 effect that SoP's
pitfall says one seed cannot resolve.

## Private details and identities (amendment A7)

The research branches already carried LAN addresses, logins (`user@host`) and
home paths. They stay as they are, because changing them would mean
rewriting published history. No line the reorganization added contains a
LAN address, a login, a home path or an email address (a scan of
`git diff cf44b4f2` and the new files). The details sit in:
- **LAN addresses and logins:** `studies/antiproxy/HANDOFF.md`,
  `studies/antiproxy/SESSION_HANDOFF_20261101.md`,
  `studies/antiproxy/docs/SPY_EXPERIMENT_JOURNAL.md`, and the journal's
  `BOX_HANDOVER_phantom.md` and `BOX_HANDOVER_simbox2.md`. There is also one
  LAN address in each of `studies/sop/docs/20261024_sop_o5_grid_results.md`
  and `analysis/mainnet/README.md` (main's).
- **Home paths, with account names:** about 200 files, mostly the antiproxy
  journal (125 files) and SoP's `dot-claude/` and `home/` snapshots (48).
- **Lab box names** (without addresses): throughout both studies' journals
  and handoffs. The new study `CLAUDE.md` and `SWITCHOVER.md` files keep the
  box names, because the studies' own drafts and instructions depend on them;
  addresses and accounts were removed and belong in `CLAUDE.local.md`.

The `192.168` addresses in `src/`, `docs/NETWORK_SCALING_GUIDE.md` and the
CAIDA links file are examples and test data, not lab details.

**Identities.** Every commit this brings to main has Fountain5405 as author
and committer. The research commits merged from the two branches carry
`Co-Authored-By` trailers from their own sessions. Those commits were
already public and cannot change without rewriting history. The
reorganization's own commits carry no trailer.

## Branches

Once main points at this branch, each leftover remote branch gets an
annotated `archive/<branch>` tag at its tip, and is then deleted:

| Branch | Tip | Why it can go |
|---|---|---|
| `feat/turnover-return-grid` | `b10f4fae` (2026-10-13) | brief step 10. Only the remote branch goes; the local worktree `../monerosim_grid`, its branch and its untracked A/B configs stay (A4) |
| `hashrate-gating` | `6dc8a8ef` (2026-10-28) | its only file, `README.md`, is `studies/antiproxy/docs/20261028_hashrate_gating_arithmetic.md` minus that doc's two-line status header; the antiproxy `HANDOFF.md` says it can be deleted |
| `progress-brief` | `7ba57451` (2026-10-28) | its only file, `README.md`, is byte-identical to `studies/antiproxy/docs/20261028_progress_brief.md`; same `HANDOFF.md` note |

No `archive/` tag of these names existed before. `sop-research` and
`feat/spy-relay-log` stay: their agents retire them during switch-over
(SWITCHOVER step 5).

## Not verified

- **SoP checks 2 and 3**, the MDP cross-check. They need scipy and
  pymdptoolbox, which the repo venv lacks, and pytest skips the cross-check
  test on both sides for the same reason.
- **Antiproxy check 4's k42 m1 stock cell** (light share 0.337). Only B1 ran,
  as amendment A8 asked.
- **Antiproxy check 3**, the id-consistency logic driver. It waits for the
  regenerated patch.
- **The studies' own drivers and queues.** The drivers that hard-code a box's
  paths (listed in each SWITCHOVER) did not run here.
- **Builds of each study's patches on their own** (follow-ups).
- **What moves the knob smoke's mining start** by 10 ms in the final tree
  (follow-ups).
- **The spread of B1's light share between runs.** B1 ran once from each
  tree. The ±0.005 band comes from the antiproxy handoff; these runs did not
  measure the spread (follow-ups).
