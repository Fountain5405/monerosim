# Per-Run /tmp Namespacing

**Date:** 2026-07-21
**TL;DR:** every `run_sim.sh` invocation now gets a private
`/tmp/monerosim-<runid>/` namespace for its monerod data dirs and shared
registry, so **concurrent monerosim runs on one box no longer collide**.
One run per checkout/worktree; the paths are breadcrumbed for tooling in
`shadow_output/run_env.sh`.

## 1. Why

Historically all runs shared two global namespaces:

- `{daemon_data_dir}/monero-<agent>/` with `daemon_data_dir` defaulting to
  plain `/tmp` — agent hostnames repeat across runs (miner-001, user-042…),
  so two concurrent runs opened the **same LMDB databases**;
- `/tmp/monerosim_shared/` — the agent registry / miners.json / wallet dirs,
  overwritten wholesale by whichever run generated last.

The failure mode was ugly and *silent-ish*: LMDB `mdb_txn_begin` returns
EAGAIN on the cross-run open, monero v0.18.x's error path then crashes in
`mdb_txn_abort` (boost TLS deleter against a failed env), and the sims
degrade into hundreds of spurious monerod SIGSEGVs — all artifact, zero
signal. On top of that, generator startup and `run_sim.sh` cleanup did
`rm -rf` over the *global* globs, actively deleting the other run's live
data. This burned ~2 days of the 2026-07 wallet-crash hunt (see
`docs/20260717_wallet_crash_root_cause.md` §3) and made parallel A/B sweeps
impossible even though the box (128c/1TB) has headroom for several sims.

## 2. Mechanism

`run_sim.sh` (Phase 2, `build_and_generate`) mints
`RUN_ID=<timestamp>_<run-name>` — same string as the archive dir basename —
and exports, **only if not already set by the user**:

```
MONEROSIM_DAEMON_DATA_DIR=/tmp/monerosim-<runid>        # daemon dirs: monero-<agent>/
MONEROSIM_SHARED_DIR=/tmp/monerosim-<runid>/shared      # registry, wallets, monitoring
```

The Rust generator already reads both env vars as the *defaults* for
`general.daemon_data_dir` / `general.shared_dir` (`src/lib.rs`), and those
config values flow into every generated artifact: monerod `--data-dir=` /
`--log-file=` args, wallet `--wallet-dir=` / `--shared-ringdb-dir=`, every
Python agent's `--shared-dir` argument, and (new) the per-process
environment map in `shadow_agents.yaml`, so in-sim fallback defaults
(`base_agent.DEFAULT_SHARED_DIR`, the simulation-monitor's daemon-log
discovery) resolve to the same namespace.

Precedence, most-specific wins:

1. explicit `general.daemon_data_dir` / `general.shared_dir` in the YAML
   config (also what `--ramdisk` sets via its config rewrite),
2. pre-set `MONEROSIM_*` env vars,
3. run_sim.sh's per-run namespace,
4. legacy globals (`/tmp`, `/tmp/monerosim_shared`) — still the defaults
   when the generator runs outside `run_sim.sh`.

After generation, `run_sim.sh` extracts the paths the generator *actually
baked in* (from `shadow_agents.yaml`, so YAML/ramdisk overrides are
honored) and writes them to **`shadow_output/run_env.sh`**:

```sh
MONEROSIM_RUN_ID="20260721_211606_nsA"
MONEROSIM_DAEMON_DATA_DIR="/tmp/monerosim-20260721_211606_nsA"
MONEROSIM_SHARED_DIR="/tmp/monerosim-20260721_211606_nsA/shared"
```

Out-of-band tooling sources that breadcrumb instead of hardcoding paths:
`scripts/check_sim.sh` does so automatically; `start_here.sh` exports it
before live-run analysis; for manual digging,
`source shadow_output/run_env.sh` puts the vars in your shell.

## 3. Cleanup lifecycle

- **End of run:** after archiving (daemon logs, registry, wallets,
  monitoring, summary all read/moved first), `cleanup_tmp_monero --full`
  removes the entire run dir. `--no-clean` leaves it for inspection;
  `--no-archive` removes only the daemon dirs (shared/ kept, matching the
  old behavior of leaving `/tmp/monerosim_shared` in place).
- **Crashed runs:** each run dir carries `.owner_pid`. At the next
  `run_sim.sh` start, run dirs whose owner PID is dead are swept; dirs with
  a live owner (a concurrent run) or no breadcrumb (manual generator
  invocation) are left alone.
- **Legacy leftovers:** pre-namespacing `/tmp/monero-*` dirs are detected
  and reported with a manual-removal hint, never auto-deleted.

## 4. The concurrency contract

Multiple simultaneous runs on one box are supported with:

- **one run per checkout/worktree** — `shadow.data/` and `shadow_output/`
  live in the repo dir and remain per-checkout;
- shared read-only infrastructure is fine: `~/.monerosim/bin` binaries and
  the venv can be shared (a worktree can symlink `venv/` and copy/symlink
  `target/release/monerosim`).

Remaining per-invocation (not per-run-dir) tmpfiles were PID-suffixed in
the same change (`monerosim_disk_est_info_$$`, `monerosim_monitor_sizes_$$`;
the ramdisk mount was already `_$$`). `scripts/scaling_test.sh` got its own
PID-suffixed namespace under `/tmp/monerosim_scaling_test_$$/`.

## 5. Validation

2026-07-21, two rounds of two concurrent quickstart sims (15 hosts each,
6h sim time) from two checkouts of the same working tree:

- Both rounds: distinct `/tmp/monerosim-*` namespaces, zero
  cross-namespace references in the generated configs, all success
  criteria PASS in all four runs, archives complete (daemon logs,
  registry, wallets, blockchain snapshots, monitoring), `/tmp` left clean.
- **Metrics identical to the historical solo baseline** (height 129,
  128 mined) in every run — concurrency and the new paths don't perturb
  the simulation.
- Round 1 exposed one ordering bug in the change itself (the summary
  printer read `final_report.json` from the shared dir after the run dir
  was already cleaned → script exit 1 despite a healthy sim); fixed by
  preferring the archived copy. Round 2: clean exit 0 end-to-end, both
  instances.

Under the old global namespace this exact scenario produced hundreds of
spurious monerod SIGSEGVs and invalid runs (2026-07-16 hunt logs). Rust
goldens regenerated (the process env map now carries the two `MONEROSIM_*`
vars); full cargo + pytest suites pass; quickstart smoke gate 19/19 PASS
on the final state.

## 6. Notes for older archives / scripts

- Archives are unaffected — analysis tools take archive paths explicitly.
- The Rucknium/turnover analysis scripts operate on archives; no change.
- Scratch scripts that globbed `/tmp/monero-*` (e.g. the 2026-07 crash-hunt
  kit) predate this change; if reused, source `run_env.sh` first.
