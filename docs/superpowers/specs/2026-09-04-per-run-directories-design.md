# Per-run directories: parallel simulations from one checkout

**Date:** 2026-09-04
**Status:** approved design, not yet implemented
**Supersedes:** section 4 ("The concurrency contract") of
`docs/20260721_per_run_tmp_namespacing.md`, which required one checkout or
worktree per concurrent run.

## 1. Problem

On 2026-09-04 six `run_sim.sh` instances were live from one checkout. Every
Shadow process was started with the same `-d <checkout>/shadow.data` and read
the same `<checkout>/shadow_output/shadow_agents.yaml`. The July per-run `/tmp`
namespacing kept the daemons' blockchains, wallets and registry apart, and the
six virtual networks cannot see each other, so the network results themselves
were not cross-contaminated. Everything in the checkout was:

| Mechanism | Where |
|---|---|
| Each launch runs `rm -rf shadow.data shadow.log` and deletes the tree the earlier runs are writing into | `run_sim.sh:906` |
| Host logs collide: Shadow virtual pids are deterministic, so two runs both write `hosts/miner-001/bash.1000.stdout` | Shadow layout |
| Live status files are shared: `block_histogram_state.json`, `sim-stats.json`, `monerosim_monitor.log` | `shadow.data/` |
| The first run to finish moves the whole shared tree into its own archive | `run_sim.sh:1295` |
| Every launch regenerates `shadow_output/` (YAML, topology, `run_env.sh`, per-agent wrappers that hardcode that run's `/tmp` path and are exec'd at simulated seconds 0-10) | `run_sim.sh:840` |
| The daemon base path is derived by grepping the shared YAML; a wrong read makes the end-of-run `rm -rf $DAEMON_DATA_BASE/monero-*` delete another run's live blockchains | `run_sim.sh:862-863`, `1453` |

## 2. Goals and non-goals

Goals:

- Any number of `run_sim.sh` instances may run concurrently from one checkout.
- Nothing under the checkout root is written or deleted during a run. The
  only mutable state a run owns is its run directory and its `/tmp` namespace.
- Every out-of-band tool addresses a run explicitly and says which run it chose.
- Preflight knows about the other live runs on the box and does not let one
  launch fill the disk that all of them share.
- The Rust generator, the generated YAML, the wrapper scripts and the
  simulation semantics do not change. Golden tests stay byte-identical.
- Existing archives under `archived_runs/` are untouched and stay readable.

Non-goals:

- `scripts/scaling_test.sh` (drives Shadow directly, single-instance by design).
- Snapshotting the Python agent package into the run directory. Agents start
  within the first ten simulated seconds; mid-run edits to the checkout are a
  narrow hazard that does not justify a per-run copy.
- Coordinating runs across different checkouts beyond the existing pid-guarded
  `/tmp` namespace sweep.
- Cleaning up the root-level `shadow.data/` and `shadow_output/` left by
  earlier versions. They are inert and stay gitignored.

## 3. Layout and `run_sim.sh`

### 3.1 The run directory

A run lives in one directory for its whole life:

```
archived_runs/<RUN_ID>/            RUN_DIR  (== ARCHIVE_DIR, same variable)
  .owner_pid                       pid of the run_sim.sh that owns it
  input_config.yaml                copied at launch (unchanged)
  build.log, monerosim.log,        as today
  shadow_run.log
  shadow_output/                   generator output (--output points here)
    shadow_agents.yaml
    topology.gml
    scripts/*.sh
    run_env.sh                     breadcrumb (see 3.4)
  shadow_agents.yaml               top-level copy kept for legacy tools
  shadow.data/                     created by Shadow itself (-d)
  daemon_logs/, blockchain/,       populated by the archive phase as today
  wallets/, ringdbs/, transaction_registry/, monitoring/
  summary.txt                      written last; its presence == complete
```

`RUN_ID` is `<YYYYmmdd_HHMMSS>_<RUN_NAME>` as today. The directory is created
with `mkdir` (no `-p`) so an existing directory is an error, not a merge. On
`EEXIST` the script retries with `_2`, `_3`, ... up to `_99`, then aborts.
`RUN_ID` is the basename that finally succeeded, so `RUN_TMP_DIR`
(`/tmp/monerosim-<RUN_ID>`) and the run directory always share a name.
`RUN_DIR/.owner_pid` is written immediately after creation, mirroring the
existing `RUN_TMP_DIR/.owner_pid`.

`ARCHIVE_DIR` keeps its name inside the script to minimise churn; `RUN_DIR` is
introduced as an alias with the same value and used in new code.

### 3.2 Variables

| Variable | Value | Notes |
|---|---|---|
| `ARCHIVE_BASE` | `--archive-dir`, else `$MONEROSIM_ARCHIVE_BASE`, else `<checkout>/archived_runs` | `run_sim.sh` honours the same `MONEROSIM_ARCHIVE_BASE` environment variable the out-of-band tools use as their default archive base, so a run launched this way lands where the tools already look for it |
| `RUN_DIR` / `ARCHIVE_DIR` | `$ARCHIVE_BASE/$RUN_ID` | created in Phase 2, never in preflight |
| `SHADOW_OUTPUT` | `$RUN_DIR/shadow_output` | was `<checkout>/shadow_output` |
| `DATA_DIR` | `$RUN_DIR/shadow.data` | was `<checkout>/shadow.data`; Shadow creates it |
| `DATA_DIR` with `--data-dir <base>` | `<base>/$RUN_ID/shadow.data` | scratch placement; parent is `mkdir -p`'d, leaf is left to Shadow |
| `RUN_TMP_DIR`, `DAEMON_DATA_BASE`, `SHARED_DIR` | unchanged | the YAML grep at `run_sim.sh:862-871` now reads a per-run file |

### 3.3 Phase changes

- **Preflight** creates no directory and needs no `RUN_ID`: the concurrency
  report (section 5) excludes this invocation by pid, not by id. `RUN_ID`
  becomes final only when Phase 2's `mkdir` succeeds (possibly with a
  suffix); `RUN_TMP_DIR` and everything derived from the id are set after
  that point, as today. `check_disk_space` measures `ARCHIVE_BASE` and, when
  `--data-dir` is given, that base; it no longer `mkdir -p`s the data
  directory's parent. `--preflight-only` therefore still creates nothing.
- **Phase 2** creates `RUN_DIR` as in 3.1, writes `.owner_pid`, exports
  `MONEROSIM_RUN_DIR`, and calls the generator with `--output "$SHADOW_OUTPUT"`.
  The existing `cp shadow_agents.yaml "$ARCHIVE_DIR/"` stays.
- **Phase 3** starts Shadow with `-d "$DATA_DIR" "$SHADOW_OUTPUT/shadow_agents.yaml"`.
  The block at `run_sim.sh:885-906` (the "Cleaning previous simulation data"
  guard and `rm -rf "$DATA_DIR" shadow.log`) is deleted entirely.
- **Live monitor** already reads `$DATA_DIR/...` and `$DAEMON_DATA_BASE/...`
  and needs no change.
- **Phase 5 (`archive_results`)** step 5a becomes: if `DATA_DIR` is not
  already `$RUN_DIR/shadow.data` (the `--data-dir` case) move it there;
  otherwise do nothing. All other archive steps are unchanged.
- **`--no-archive`** additionally runs `rm -rf "$RUN_DIR/shadow.data"` (and,
  in the `--data-dir` case, the scratch copy) after the run so that its
  documented "not preserved" promise holds and tens of gigabytes are not
  left in the run directory. The small pre-run artifacts remain, as today.
  When `--no-clean` is also given, that deletion is skipped instead:
  `shadow.data` (and the scratch copy, if any) is kept under the run
  directory for inspection, and a warning is logged saying so.
- **Launch banner** prints `Run directory: <RUN_DIR>` and
  `Check status: ./scripts/check_sim.sh <RUN_DIR>` (replacing the fixed
  `./scripts/check_sim.sh` line at `run_sim.sh:1037`).
- **Concurrency report** in preflight: see section 5.

### 3.4 `run_env.sh`

Written to `$SHADOW_OUTPUT/run_env.sh` as today, with three added lines:

```
MONEROSIM_RUN_DIR="<abs RUN_DIR>"
MONEROSIM_SHADOW_DATA_DIR="<abs DATA_DIR>"
MONEROSIM_SHADOW_OUTPUT_DIR="<abs SHADOW_OUTPUT>"
```

`run_sim.sh` also exports `MONEROSIM_RUN_DIR` into the environment of every
child it launches after Phase 2 (generator, Shadow, post-run analysis), so
tools invoked by the script resolve the right run without arguments.

When Phase 5 step 5a moves a `--data-dir` run's scratch data into
`$RUN_DIR/shadow.data`, `run_env.sh`'s `MONEROSIM_SHADOW_DATA_DIR` line is
rewritten to the final path, so the breadcrumb always names where the data
currently lives rather than the scratch location it started at.

## 4. The run-directory contract for tools

### 4.1 Resolution

Every out-of-band tool resolves its run directory in this order:

1. an explicit argument (`--run-dir DIR` for Python tools, first positional
   `DIR` for the shell tools);
2. `$MONEROSIM_RUN_DIR` if set;
3. the newest run: the lexically greatest basename matching
   `^[0-9]{8}_[0-9]{6}_` under `$MONEROSIM_ARCHIVE_BASE` or, unset,
   `<checkout>/archived_runs`. Names start with a timestamp so lexical order
   is chronological.

The tool prints one line to stderr: `run: <dir> (<state>)` where state is
`live` (`.owner_pid` exists and the process it names exists, checked
through `/proc/<pid>` rather than `kill -0` so another user's live run is
still detected on a shared box), `complete` (`summary.txt` exists) or
`incomplete` (neither). If nothing resolves it exits 2 with a message
naming the three sources.

### 4.2 Helpers

- `scripts/run_dir_lib.sh` (bash, sourced): `resolve_run_dir [DIR]` echoes
  the directory and prints the state line; `run_dir_state DIR` echoes the
  state word; `run_dir_is_live DIR` returns 0/1.
- `scripts/run_dirs.py` (Python module, importable from `scripts/`):
  `resolve_run_dir(explicit: str | None) -> Path`, `run_state(path) -> str`,
  `newest_run_dir(base) -> Path | None`, `list_live_runs(base) -> list[LiveRun]`
  (used by section 5).

### 4.3 Per-tool changes

| Tool | Change |
|---|---|
| `scripts/check_sim.sh` | takes `[RUN_DIR]`; sources `<run>/shadow_output/run_env.sh`; all `shadow.data/hosts` reads become `<run>/shadow.data/hosts` |
| `start_here.sh` | same treatment for its status/inspection paths (lines 559-617) |
| `scripts/analyze_success_criteria.py` | `--run-dir`; replaces the hardcoded `shadow.data` paths at lines 210-296 |
| `scripts/analyze_network_connectivity.py` | `--run-dir`; replaces lines 55-68 |
| `scripts/smoke_assertions.py` | makes `--run-dir` optional, defaulting per 4.1 (it already read `<run>/shadow.data/hosts`) |
| `scripts/post_run_analysis.sh` | passes `--run-dir "$MONEROSIM_RUN_DIR"` (or its own first argument) to both analysers |
| `scripts/run_sim_helpers.py` disk-rate learner (lines 157-170) | additionally requires `summary.txt`; live and crashed runs are never samples |
| `scripts/prune_archives.sh` | refuses an archive whose `.owner_pid` is alive unless `--force` |
| `agents/simulation_monitor/status_paths.py` | candidate order becomes `output_dir/shadow.data/hosts`, `output_dir/hosts`, `output_dir.parent/shadow.data/hosts`, then the two cwd-relative entries last |
| `run_sim.sh` disk check | uses `run_dirs.py` via a new helper subcommand (section 5) |

Nothing writes a "latest" symlink at the checkout root. The monitor's
cwd-relative fallback would follow such a link into the wrong run.

## 5. Concurrency-aware preflight

A new `run_sim_helpers.py live-runs --archive-base B --exclude RUN_ID`
subcommand prints one TSV line per live run other than this one:

```
run_id  pid  elapsed_s  daemons  used_kb  est_total_kb|-  remaining_kb|-  source  parallelism|-
```

Numeric columns are whole KB (`run_sim.sh` does integer arithmetic on them).

- Live runs are discovered from `B/*/.owner_pid` and `/tmp/monerosim-*/.owner_pid`
  (deduplicated by run id, pid must exist under `/proc/<pid>`, not answer
  `kill -0`, which reports another user's process as dead (EPERM) on a
  shared box). A run known only from its `/tmp` namespace (another checkout
  or archive base) has `source=tmp` and no estimate.
- `elapsed_s` = now minus the timestamp parsed from the run id.
- `daemons` = count of `monero-*` entries in the namespace.
- `used_kb` = `du -sk` of the run directory plus its namespace.
- `est_total_kb` reuses `estimate-disk-mb` fed with `config-summary` of
  `<run_dir>/input_config.yaml` and that config's stop time; `remaining_kb =
  max(0, est_total_kb - used_kb)`. Unparseable config: both fields `-`.

`check_disk_space` then:

1. prints the table under a "Other live runs on this box" heading (or
   "none");
2. sets `effective_free_kb = free_kb - sum(remaining_kb)` and uses that in
   its existing comparison and message, stating the subtraction and the
   number of runs with no estimate;
3. adds one informational line comparing this run's `general.parallelism`
   (0 means `nproc`) plus the live runs' values with `nproc`, prefixed with
   a warning when the sum exceeds the core count. Parallelism is read by
   `config-summary`, which gains a `parallelism` field if it lacks one; a
   live run's value comes from its `input_config.yaml` the same way.

The existing confirm prompt remains the only gate. No new check blocks a
launch.

## 6. Failure handling

- **Directory collision:** suffix retry then abort (3.1). Never merge.
- **Scratch collision:** if `<base>/<RUN_ID>/shadow.data` already exists
  under `--data-dir`, abort before starting Shadow with a message naming it.
- **Crash mid-run:** the run directory stays, `.owner_pid` is dead, no
  `summary.txt`; tools report `incomplete`; nothing deletes run directories
  automatically. The pid-guarded `/tmp` sweep is unchanged.
- **Shadow refuses an existing data directory** (verified: both a populated
  and an empty pre-created directory fail). The design never pre-creates it.
- **Legacy paths:** a stale `<checkout>/shadow.data` is ignored by every
  updated tool; the monitor only reaches it as a last-resort fallback.

## 7. Testing

Unit (pytest, `testpaths = agents, scripts, tests`):

- `scripts/test_run_dirs.py`: resolution order, newest-run selection,
  state classification with a fake pid, `list_live_runs` with fixture
  directories.
- `scripts/test_run_sim_helpers.py`: the learner skips runs lacking
  `summary.txt`; `live-runs` output shape and `remaining_kb` arithmetic.
- `agents/test_simulation_monitor.py`: candidate order prefers output-dir
  paths over cwd-relative ones when both exist.
- `scripts/test_smoke_assertions.py`: `--run-dir` is honoured.

Integration, as `scripts/test_parallel_runs.sh` (kept in the repo so anyone
can rerun it):

1. from one checkout, launch two `./run_sim.sh --config
   test_configs/quickstart.yaml --name par_a` / `--name par_b` concurrently;
2. while both are live, `check_sim.sh <run_dir>` succeeds for each and names
   the right run;
3. both finish with `summary.txt`, zero failed hosts, distinct run
   directories, each with a populated `shadow.data/hosts/`;
4. the checkout root contains no new `shadow.data`, `shadow_output` or
   `shadow.log`;
5. `cargo test` (goldens) and `pytest` pass unchanged.

## 8. Documentation

- `run_sim.sh --help`: the "Concurrency" paragraph, `--data-dir`,
  `--no-archive`, `--preflight-only`.
- `docs/20260721_per_run_tmp_namespacing.md` section 4: marked superseded
  with a pointer to this design's user-facing doc.
- New `docs/20260904_per_run_directories.md`: the user-facing description of
  the layout, the tool contract and the preflight report.
- `CHANGELOG.md` entry noting the two behaviour changes: `--data-dir` now
  takes a base directory, and `run_env.sh` moved from
  `<checkout>/shadow_output/` to `<run_dir>/shadow_output/`.
- `README.md` / `QUICKSTART.md`: replace any `./scripts/check_sim.sh` or
  `shadow.data/` mention with the run-directory form.
