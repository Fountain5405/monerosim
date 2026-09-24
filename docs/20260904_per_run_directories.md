# Per-run directories: parallel simulations from one checkout

**Date:** 2026-09-04
**Supersedes:** section 4 ("The concurrency contract") of
`docs/20260721_per_run_tmp_namespacing.md`, which required one checkout or
worktree per concurrent `run_sim.sh` invocation.
**Design:** `docs/superpowers/specs/2026-09-04-per-run-directories-design.md`
(the authority for exact variable names, phase ordering and preflight
mechanics; this doc is the user-facing summary).

## 1. Why

On 2026-09-04 six `run_sim.sh` instances were live from one checkout. Every
Shadow process was started with the same `-d <checkout>/shadow.data` and read
the same `<checkout>/shadow_output/shadow_agents.yaml`. The July 2026 per-run
`/tmp` namespacing (see the superseded doc above) kept the daemons'
blockchains, wallets and registry apart, and the six virtual networks cannot
see each other, so the network results themselves were not
cross-contaminated. Everything at the checkout root was:

| Mechanism | Where |
|---|---|
| Each launch runs `rm -rf shadow.data shadow.log` and deletes the tree the earlier runs are writing into | `run_sim.sh:906` |
| Host logs collide: Shadow virtual pids are deterministic, so two runs both write `hosts/miner-001/bash.1000.stdout` | Shadow layout |
| Live status files are shared: `block_histogram_state.json`, `sim-stats.json`, `monerosim_monitor.log` | `shadow.data/` |
| The first run to finish moves the whole shared tree into its own archive | `run_sim.sh:1295` |
| Every launch regenerates `shadow_output/` (YAML, topology, `run_env.sh`, per-agent wrappers that hardcode that run's `/tmp` path and are exec'd at simulated seconds 0-10) | `run_sim.sh:840` |
| The daemon base path is derived by grepping the shared YAML; a wrong read makes the end-of-run `rm -rf $DAEMON_DATA_BASE/monero-*` delete another run's live blockchains | `run_sim.sh:862-863`, `1453` |

In short: the simulated network state was safe (per-run `/tmp`), but the
tooling around it (Shadow's own data dir, the generated config, the archive
step, the daemon-cleanup step) all still assumed exactly one live run per
checkout. Any second concurrent run could corrupt or delete the first one's
output. Per-run directories fix the tooling side; nothing about the
simulation semantics changes.

## 2. Layout

Since this change, a run lives in one directory for its whole life:

```
archived_runs/<RUN_ID>/            RUN_DIR  (== ARCHIVE_DIR, same variable)
  .owner_pid                       "<pid> <starttime>" of the run_sim.sh that owns it
  input_config.yaml                copied at launch (unchanged)
  build.log, monerosim.log,        as today
  shadow_run.log
  shadow_output/                   generator output (--output points here)
    shadow_agents.yaml
    topology.gml
    scripts/*.sh
    run_env.sh                     breadcrumb (see below)
  shadow_agents.yaml               top-level copy kept for legacy tools
  shadow.data/                     created by Shadow itself (-d)
  daemon_logs/, blockchain/,       populated by the archive phase as today
  wallets/, ringdbs/, transaction_registry/, monitoring/
  summary.txt                      written last; its presence == complete
```

`RUN_ID` is `<YYYYmmdd_HHMMSS>_<RUN_NAME>` as before. The directory is
created with `mkdir` (no `-p`), so a name collision is an error, not a
merge; `run_sim.sh` retries with `_2`, `_3`, ... up to `_99` before giving
up. Nothing under the checkout root is written or deleted by a run anymore;
the only mutable state a run owns is its run directory and its
`/tmp/monerosim-<RUN_ID>/` namespace.

Variables (see the design spec section 3.2 for full detail):

| Variable | Value | Notes |
|---|---|---|
| `ARCHIVE_BASE` | `--archive-dir`, else `$MONEROSIM_ARCHIVE_BASE`, else `<checkout>/archived_runs` | `run_sim.sh` honours the same `MONEROSIM_ARCHIVE_BASE` environment variable the out-of-band tools use as their default archive base; `--archive-dir` overrides it |
| `RUN_DIR` / `ARCHIVE_DIR` | `$ARCHIVE_BASE/$RUN_ID` | created in Phase 2, never during preflight |
| `SHADOW_OUTPUT` | `$RUN_DIR/shadow_output` | was `<checkout>/shadow_output` |
| `DATA_DIR` | `$RUN_DIR/shadow.data` | was `<checkout>/shadow.data`; Shadow itself creates it |
| `DATA_DIR` with `--data-dir <base>` | `<base>/$RUN_ID/shadow.data` | `--data-dir` now takes a **base directory**, not the final path, so it can host more than one run's scratch data; the archive phase moves the run's data home to `$RUN_DIR/shadow.data` when the run finishes |
| `RUN_TMP_DIR`, `DAEMON_DATA_BASE`, `SHARED_DIR` | unchanged | still `/tmp/monerosim-<RUN_ID>/...` |

Two behaviours worth calling out explicitly:

- **`--no-archive`** deletes `<run>/shadow.data` (and, in the `--data-dir`
  case, the scratch copy) after the run, so its documented "not preserved"
  promise holds and tens of gigabytes are not left sitting in the run
  directory. If you also pass **`--no-clean`**, that deletion is skipped and
  `shadow.data` is kept under the run directory for inspection instead
  (`run_sim.sh` logs "shadow.data is being kept for inspection under
  `<run_dir>`"). A kept `/tmp/monerosim-<run_id>/` gets a `.keep` marker so
  later launches and `scripts/sweep_stale_runs.sh` report it as kept on
  purpose rather than as a crashed run. Remove kept dirs by hand (or
  `sweep_stale_runs.sh --delete --include-kept`). The small pre-run artifacts (`input_config.yaml`,
  `shadow_agents.yaml`, `monerosim.log`, `shadow_run.log`, `build.log`,
  `memory_samples.csv`) are always kept, `--no-archive` or not.
- When a `--data-dir`-based run's scratch data is moved home into
  `$RUN_DIR/shadow.data`, the breadcrumb file `shadow_output/run_env.sh` is
  rewritten so its `MONEROSIM_SHADOW_DATA_DIR` line reflects the final path,
  not the scratch one. Tools that source `run_env.sh` after the run finishes
  see the archived location.

## 3. Which run?

Every out-of-band tool (Python or shell) resolves "which run" the same way,
in this order:

1. an explicit argument: `--run-dir DIR` for Python tools, the first
   positional `DIR` for the shell tools;
2. `$MONEROSIM_RUN_DIR`, if set (`run_sim.sh` exports this into the
   environment of every child it launches after Phase 2, so tools it invokes
   itself resolve the right run with no argument);
3. the newest run: the lexically greatest basename matching
   `^[0-9]{8}_[0-9]{6}_` under `$MONEROSIM_ARCHIVE_BASE`, or, if that is
   unset, `<checkout>/archived_runs`. Names start with a timestamp, so
   lexical order is chronological order.

Whichever way it resolved, the tool prints one line to stderr:

```
run: <dir> (<state>)
```

`<state>` is one of:

- **`live`**: `<dir>/.owner_pid` holds `<pid> <starttime>` (the pid of the
  owning `run_sim.sh` and field 22 of its `/proc/<pid>/stat`), and a
  process with that pid exists whose start time matches. The start time
  is what stops a recycled pid from making a crashed run look live; older
  single-token files fall back to existence only. Existence is checked
  through `/proc/<pid>` rather than `kill -0`, because `kill -0` reports
  another user's process as dead (`EPERM`) and this box is shared;
- **`complete`**: `<dir>/summary.txt` exists (`run_sim.sh` writes it last,
  after everything else);
- **`incomplete`**: neither file is present (crashed, killed, or a
  `--no-archive` run, which never writes `summary.txt`).

If nothing resolves, the tool exits 2 with a message naming the three
sources it tried.

One example per tool:

```bash
# Status dashboard for a specific run (or drop the argument for the newest one)
./scripts/check_sim.sh archived_runs/20260904_184958_par_a_184911

# Post-run analysis against a specific run
./scripts/post_run_analysis.sh test_configs/quickstart.yaml archived_runs/20260904_184958_par_a_184911

# Smoke assertions with an explicit run and baseline
python3 scripts/smoke_assertions.py --run-dir archived_runs/20260904_184958_par_a_184911 \
    --baseline tests/baselines/quickstart_metrics.json

# Pruning refuses a run that is still live
./scripts/prune_archives.sh archived_runs/20260904_184958_par_a_184911
# -> Refusing archived_runs/...: run is LIVE (owner pid 12345); use --force to prune anyway
```

## 4. Preflight report

Before it launches Shadow, `run_sim.sh` looks for other live runs on the box
(discovered from `.owner_pid` files under the archive base and under
`/tmp/monerosim-*/`) and reserves their projected remaining disk growth so
one launch cannot fill the disk that all of them share. It also compares
Shadow worker-thread counts against the machine's core count. Example
output with one other live run present (`--preflight-only`, so nothing is
actually started):

```
  Other live runs on this box:
    20260904_000000_fakelive  pid 3052405  up 17h 40m  0 daemons  used 8 KB  (est. total 485.9 MB, remaining 485.9 MB) [archive]
    Reserving 485.9 MB for their projected growth (0 of 1 with no estimate)
  Effective free space: 667.3 GB after reserving other live runs' growth
  WARNING: Shadow worker threads: this run 256 + other live runs 256 = 512 > 256 cores (wall clock will suffer; results unaffected)
```

When no other run is live, the two lines above collapse to
`Other live runs on this box: none` and there is nothing to reserve, so the
"Effective free space" line does not print at all.

- **`Reserving ...`** is the sum of the other runs' `remaining_kb` estimates
  (their estimated total disk usage minus what they have used so far, from
  `config-summary` of each run's own `input_config.yaml`). It is subtracted
  from free disk space before this run's own disk check runs, and the
  parenthetical says how many of the other runs had no estimate at all (a
  run known only from a `/tmp` namespace, with no readable config, counts as
  unknown and contributes nothing to the reservation).
- **The worker-thread line** adds up `general.parallelism` (0 means
  `nproc`) for this run and every other live run and compares the total to
  the number of cores on the box. It is informational only: it warns when
  the sum exceeds the core count (simulations will be slower, not wrong)
  but never blocks a launch. The existing confirm prompt is the only gate.

## 5. Acceptance

The integration test that exercises all of this is
`scripts/test_parallel_runs.sh`. Rerun it with:

```bash
./scripts/test_parallel_runs.sh [CONFIG]   # default test_configs/quickstart.yaml
```

It launches two `run_sim.sh` runs concurrently from the current checkout
(`--name par_a` / `--name par_b`), then checks:

- both runs get distinct run directories, and while both are still live,
  `./scripts/check_sim.sh <run_dir>` succeeds for each one and announces it
  as `live`;
- both finish with `summary.txt`, Shadow exit code 0, and a populated
  `shadow.data/hosts/`;
- each run's `shadow_output/run_env.sh` names its own run directory, not
  the other one's;
- both pass `scripts/smoke_assertions.py` against the parallel-run baseline
  (a relaxed wall-clock ceiling; correctness metrics are unchanged, since
  concurrent runs share the box's cores and take longer in wall-clock time
  but not in simulated time);
- the checkout root has no new files or directories once both runs finish.

The acceptance run on 2026-09-04 used two concurrent quickstart runs from
this checkout and produced `archived_runs/20260904_184958_par_a_184911`
(wall clock 18m 7s) and `archived_runs/20260904_184959_par_b_184911` (wall
clock 17m 57s). Both exited 0 and passed all 19/19 smoke assertions
against `tests/baselines/quickstart_parallel_metrics.json` (a copy of the
regular quickstart baseline with only `wall_time_seconds_max` doubled, to
account for the two runs sharing the box's cores). The checkout root was
unchanged before and after. Both runs produced identical chain data, which
is itself evidence of isolation: same seed, same result, run concurrently,
with no cross-run interference. For comparison, a solo run of the same
config earlier the same day (`archived_runs/20260904_170732_layout_check`)
took 16m 2s: running two at once costs roughly two extra minutes of wall
clock each, not a doubling, on this box.

### Scale check (2026-09-05)

Three concurrent runs of a generated 105-agent config (5 miners, 100 users
with wallets, 7 simulated hours; `test_configs/par100_6h.yaml`) from this
checkout, with a `--data-dir` quickstart run launched alongside them:

- all three completed with exit code 0, all success criteria passing,
  111 nodes online, zero alerts, zero agent tracebacks, 209 blocks each,
  transaction counts within 0.15% of one another (3390 / 3395 / 3394);
  wall time 8h 41m to 9h 30m at load ~192 on 256 cores;
- the archived chain snapshots were not byte-identical, unlike the
  quickstart pairs. The config enables `native_preemption: true` (the
  generator turns it on at 100+ agents), and preemption fires on real CPU
  time, so under that load transaction timing jitters between runs while
  the block schedule stays identical. The acceptance script therefore
  asserts chain identity only when preemption is off and equal block
  counts always;
- the `--data-dir` run's preflight listed all three live runs with
  estimates, reserved 16.1 GB for their growth and warned about 1024
  worker threads on 256 cores; during the run the scratch path held the
  data and the breadcrumb named it, `check_sim.sh` found the run's own
  Shadow process, and after completion the data was moved home, the
  breadcrumb rewritten, the scratch directory emptied, and 19/19 smoke
  assertions passed;
- nothing at the checkout root changed during any of it.

### Remaining branches (2026-09-05, batch of seven concurrent quickstart-scale runs)

- **Cross-checkout same-second collision** (deterministic, no simulation):
  with the timestamp pinned and `/tmp/monerosim-<run_id>` pre-created, a
  launch aborts with "Another live run ... already owns ..." when the
  owner is alive and "A leftover ... exists with no live owner; remove it
  manually" when it is not; neither leaves a run directory behind or
  touches the foreign namespace.
- **Same-second, same-name launches from one checkout** produce
  `<ts>_<name>` and `<ts>_<name>_2`, both live, both completing.
- **`--no-archive`** deletes `<run>/shadow.data`, keeps the pre-run
  artifacts, writes no `summary.txt` (state `incomplete`, as documented);
  **`--no-archive --no-clean`** keeps `shadow.data` and the daemon data
  dirs with a "kept for inspection" warning.
- **`--data-dir` on a different filesystem** (`/dev/shm`): data lives on
  the tmpfs during the run, the breadcrumb names it, the copy home
  succeeds, the breadcrumb is rewritten, the tmpfs base is left empty;
  19/19 smoke assertions.
- **`MONEROSIM_ARCHIVE_BASE`** set for a full run: the run lands under
  the custom base, `check_sim.sh` with no argument resolves it through
  the same variable and finds its Shadow process, the run completes with
  19/19 smoke assertions, and from the default base the preflight report
  sees it only through its `/tmp` namespace (`[tmp]`, no estimate), which
  is the report's other-checkout branch.
- **Scenario configs through the layout**: a hard-fork micro run
  (`hf_micro_2node.yaml`), a cuprate co-located-wallet run
  (`cuprate_local_wallet.yaml`) and a quickstart with 1h/1h turnover all
  complete with exit 0 (the turnover run's final sync figure is lower
  because some daemons are in a downtime window when the monitor snapshots).
- the interactive picker in `start_here.sh`, driven with scripted input, lists runs newest first labelled with their state, for example `1) 20260905_145438_turnover  (complete)`.
- Nothing at the checkout root changed during any of it.

## 6. Compatibility

- Archives created before this change are untouched and still readable;
  nothing about their internal layout changed.
- Root-level `shadow.data/` and `shadow_output/` directories left over from
  before this change (or from someone driving the generator and Shadow by
  hand at the checkout root, which is no longer the recommended way) are
  inert leftovers. They are not read or written by anything anymore and are
  safe to delete.
- `--data-dir` changed meaning: it used to be the exact Shadow data path and
  now names a base directory; the run's scratch data lands at
  `<base>/<run_id>/shadow.data` and is moved into the run directory at the
  end (unless `--no-archive`).
- `run_sim_helpers.py config-summary` prints a sixth field, `parallelism`;
  anything parsing its output must read six values.
- `run_env.sh` moved: it used to live at `<checkout>/shadow_output/run_env.sh`
  and now lives at `<run_dir>/shadow_output/run_env.sh`. Anything that
  sourced the old fixed path needs to source the new per-run one instead
  (or use `MONEROSIM_RUN_DIR`, which `run_sim.sh` exports to its own
  children automatically).
- Any tool or script that used to read `./shadow.data` directly at the
  checkout root now needs a run directory, resolved as described in
  section 3 above (explicit argument, `$MONEROSIM_RUN_DIR`, or the newest
  run under the archive base).
