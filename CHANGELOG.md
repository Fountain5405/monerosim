# Changelog

## [0.1.0] — 2026-05-12

First public beta. The codebase is at a stable point after several
months of cleanup, refactor, test-infrastructure, and portability
work; this tag marks "good enough to share."

### Release prep (May 11-12)

A focused round of release-readiness work driven by `RELEASE_PLAN.md`.

- **Project identity finalized.** `Cargo.toml` + `pyproject.toml`
  authors set to `gingeropolous <gingeropolous@gmail.com>`,
  descriptions aligned across both manifests, repository / homepage
  / documentation / keywords / categories added to `Cargo.toml`.
- **Beta signal added to README.** Status banner near the top
  declaring 0.1.0 beta, the stability promise (breaking changes only
  on minor bumps 0.x.0, not on patch 0.x.y), and a pointer to the
  new Known limitations section that covers platform support, scale
  / resource appetite, API stability, and mid-cleanup code-quality
  caveats from `AUDIT.md`.
- **Examples folder deleted (`DOC-1` / `DOC-2`).** The three
  long-stale configs and the broken `generate_caida_topology.sh`
  wrapper are gone. Production flow is `test_configs/` (working
  configs) + `gml_processing/` (topology generation). The
  `200u_800r` scenario from the May 11 benchmark is committed as the
  canonical large-scale reference. `README.md`, `QUICKSTART.md`,
  `docs/ARCHITECTURE.md`, `docs/CONFIGURATION.md`, and
  `docs/NETWORK_SCALING_GUIDE.md` all re-pointed.
- **Hardcoded `/home/lever65` removed from `scripts/scaling_sweep.sh`**
  — `pkill` patterns now use `${HOME}/.monerosim/bin/...`.
- **`run_sim.sh` destructive-ops guard.** Refuses to `rm -rf
  $DATA_DIR` if `--data-dir` resolves outside both the project tree
  and `/tmp`. Catches typos that would otherwise silently wipe a
  user-supplied directory.
- **New files for open-source consumption.**
  - `SECURITY.md`: vulnerability reporting to
    `gingeropolous@gmail.com`, coordinated-disclosure framing, scope
    and non-scope notes (upstream Monero / Shadow issues are
    deliberately out of scope).
  - `CONTRIBUTING.md`: dev environment, the three test tiers in
    order, code style, commit style, PR flow, bug report flow.
- **Portability verified end-to-end on 5 distros** (recorded in
  `PORTABILITY.md` and surfaced in README's Known limitations):
  Ubuntu 24.04, Fedora 43, Debian 13, Rocky 10, openSUSE 16. Each
  ran `setup.sh` to completion followed by a successful quickstart
  simulation. RHEL/Rocky/Alma **9** remains explicitly unsupported.
- **Planning artifacts committed.** `AUDIT.md`, `RELEASE_PLAN.md`,
  and `docs/20260512_how_pow_works.md` (a walkthrough of how block
  production works in the simulator — real RandomX PoW at regtest
  difficulty, agent-driven Poisson rate control, and why
  `start_mining` can't be used: Shadow's sim-clock only advances on
  syscalls, so a tight hash loop freezes simulated time).

### AI config generator hardening (May 11)

- The AI config generator wasn't reliably applying batched-spawn
  guidance to large groups. The small open-weight model used in
  practice (Qwen3-class via Ollama) kept anchoring on the small
  10-relay example with a `5s` linear stagger and copying it onto
  800-relay groups. Fixed by adding an explicit term-mapping
  for "batched bootstrap" / "staged spawn" phrases, a scale callout
  on the relay-nodes prompt section, a large-relay worked example,
  and a final pre-output checklist. Belt-and-suspenders:
  `check_scenario_syntax()` now runs right after generation and
  flags truncated keys, unparseable YAML, **and** any 50+ range
  group with a non-`auto` stagger.
- `scenario_parser`: `total_nodes` (the calibrator's `num_nodes`
  input) now counts only daemon-running agents. Script-only
  singletons like `miner-distributor` and `simulation-monitor` are
  not tx-propagation targets and were inflating the calibrator's
  per-tx propagation cost slightly.

### Audit-driven cleanup, refactor, and test infrastructure (May 7-8)

A multi-day session driven by a fresh-eyes audit (`AUDIT.md`) of the
codebase. The audit identified ~30 findings across three waves
(cleanup, structural decomposition, deeper refactors). All three were
executed end-to-end with **zero behavior regressions** caught by the
test infrastructure introduced in the same session.

Net effect: ~14k LOC removed/restructured across 22 commits; bloated
1500-line files broken into focused modules; test coverage went from
0 committed tests to 86 Python unit tests + 2 Rust integration tests
+ a parameterized Shadow smoke wrapper.

#### Test infrastructure (new)

Three tiers of regression detection:

- **Tier 0** (per-commit, <1s): `tests/orchestrator_smoke.rs` and
  `tests/orchestrator_quickstart.rs` byte-diff the orchestrator's
  emitted YAML against committed goldens (`tests/golden/*.yaml`),
  with regex-based path normalization (`/tmp/...` → `TMPDIR/`,
  `$CWD` → `REPO_ROOT`, `$HOME` → `HOME`). Refresh via
  `UPDATE_GOLDEN=1 cargo test`.
- **Tier 1** (per-commit, seconds): 86 pytest assertions across
  9 agent modules — parsers, helpers, RPC payload shape, registry
  caching, DNS resolution. New `conftest.py` at repo root provides
  shared fixtures (`shared_dir`, `stub_rpc`, autouse `signal.signal`
  mock so `BaseAgent.__init__` doesn't pollute the test process).
- **Tier 2** (manual pre-release, ~14 min): `scripts/smoke_test.sh
  <scenario>` runs the full simulation, then
  `scripts/analyze_success_criteria.py` (the existing 4 PASS/FAIL
  gates), then `scripts/smoke_assertions.py` (new: stricter per-user
  / per-miner / propagation / log-pattern checks against
  `tests/baselines/<scenario>_metrics.json`). Designed to catch
  the class of bug — "wallets sending only 3 txs and dying" —
  that slipped past the existing 4 criteria.

Each smoke run auto-appends a row to
`tests/baselines/<scenario>_run_history.csv` (commit hash + 22
metrics). Backfilled with prior runs.

`.gitignore` simplified — the four blanket-exclude lines for
`test_*.{py,sh,c,yaml}` were removed, finally allowing tests to be
committed.

#### Bug fixes (miner_distributor)

Two related funding-cycle bugs surfaced during the test infrastructure
work, both worth their own commits:

1. **Cycle-level failover.** `_process_funding_batches` selected one
   miner per cycle and abandoned the cycle if its `transfer_split`
   call failed. Combined with the deterministic RNG, that miner
   could be re-picked and re-fail in subsequent cycles too. Added a
   per-cycle failover loop: if the selected miner's send fails,
   exclude it from this cycle and try another. Recognizes "not
   enough unlocked money" (RPC code -37) as a distinct error from
   "not enough money" so we fail over fast instead of burning ~15s
   of backoff retries.

2. **Adaptive batch sizing.** Funding batches required a fixed
   N_recipients × outputs × amount XMR (default 80 XMR). Miners
   whose Poisson block draws clustered late had only ~35 XMR
   unlocked at any moment and never cleared the threshold — they
   silently dropped out of the rotation for entire runs. New
   `_fit_batch_to_unlocked_balance(miner, batch)` queries the
   miner's unlocked balance and trims the recipient list to fit
   (5% headroom for fees). Empty fit → cycle fails over.

Net visible effect: in a 6h `quickstart` smoke (5 miners, 3 users,
seed 12345), miner-002's tx count went from **0 → 6** without
changing any other observable metric. In a 6h30m `upgrade_smoke` run,
collective miner tx volume **doubled** (24 → 50) compared to the
pre-fix May 2 baseline. User-side metrics unchanged.

#### Code organization (structural decomposition)

Eight bloated single-file targets broken into focused modules.
Tier 0 goldens caught zero regressions across all eight refactors.

| Target | Before | After |
|---|---|---|
| `src/orchestrator.rs::generate_agent_shadow_config` | 648 LOC fn | 347 LOC + 8 named helpers |
| `src/agent/user_agents.rs` | 827 LOC | 724 LOC; peer-topology builders moved to new `src/topology/peer_connections.rs` |
| `src/config.rs` | 1175 LOC single file | `src/config/` directory: `types`, `agent_config`, `phases`, `validation`, `defaults`, `errors`, `mod` |
| `src/analysis/upgrade_analysis.rs` | 1206 LOC | `upgrade_analysis/` directory: `windows`, `metrics`, `assembly`, `mod` |
| `src/analysis/types.rs` | 905 LOC | `types/` directory: `core`, `spy`, `propagation`, `resilience`, `tx_relay`, `dandelion`, `upgrade`, `bandwidth`, `mod` |
| `agents/miner_distributor.py` | 1556 LOC single file | `miner_distributor/` package: `agent` + `config` + `discovery` + `funding` + `selection` + `state` |
| `agents/simulation_monitor.py` | 1652 LOC single file | `simulation_monitor/` package: `agent` + `alerts` + `log_parser` + `metadata` + `status_paths` |
| `scripts/generate_config.py` | 1925 LOC | 1397 LOC + new `scripts/config_generation/` (timeline, agent_emit, general_emit, yaml_emit) |
| `run_sim.sh` | 1623 LOC, 19 inline `python3 -c` heredocs | 1335 LOC + new `scripts/run_sim_helpers.py` (9 subcommands) |

Imports preserved via re-exports — every existing
`use crate::config::*` / `from agents.miner_distributor import ...`
continues to resolve unchanged.

#### Cleanup and pruning (Wave 1)

- **Removed `--migrate` CLI flag** in `monerosim` and the underlying
  `migrate_config` / `check_config_compatibility` functions. Was
  scaffolding for a YAML format ("# Dummy nodes section") that no
  current config uses.
- **Deleted three superseded analyzers:** `scripts/tx_analyzer.py`
  (Rust `tx-analyzer` is canonical), `scripts/verify_simulation.py`
  and `scripts/post_simulation_monitor_analysis.py` (both replaced
  by the wired `scripts/analyze_success_criteria.py`).
- **Moved 6 unwired ad-hoc tools to `attic/`** (preserved-but-
  unmaintained; see `attic/README.md`): `log_processor.py`,
  `enhanced_monitor.py`, `assess_internetness.py`,
  `verify_transaction_inclusion.py`,
  `regenerate_enhanced_blocks.py`, `sync_check.py`.
- **Renamed `scripts/error_handling.py` → `scripts/monero_verification.py`.**
  The module's docstring claimed to be "a Python port of
  `error_handling.sh`" — but `error_handling.sh` no longer existed
  and the module is actually a Monero-RPC verification + retry
  library, not error handling.
- **Retired `_v2` filename suffixes:** `src/config_v2.rs` → `config.rs`,
  `src/analysis/tx_relay_v2.rs` → `tx_relay.rs`. (The function name
  `analyze_tx_relay_v2` and CLI subcommand `tx-relay-v2` keep their
  suffix — that's Monero's actual tx-relay-v2 *protocol feature*,
  not module versioning.)
- **Standardized shell `set -euo pipefail`** across 12 scripts.
- **All ANSI-using scripts now source `scripts/colors.sh`** instead
  of duplicating color codes inline.
- **Trimmed unused `agents/__init__.py` re-exports**
  (`MoneroRPC`, `WalletRPC`, `RPCError` were re-exported but never
  imported via `agents`).
- **Discovery-helper consolidation:** extracted shared
  `load_public_nodes_registry` from `agent_discovery.py` and
  `public_node_discovery.py` into `agents/shared_utils.py`. Other
  surface-similar patterns (TTL caching, logger setup) deliberately
  left separate after analysis — semantics diverge.

#### Error handling (Wave 3)

- **`.unwrap()` sweep on user-facing paths.** Replaced unwraps in
  config / orchestrator / agent / topology / IP / utils paths with
  `.expect("invariant: ...")` (Category A: caller invariant) or
  `?` + `.wrap_err_with(...)` (Category B: user-data path).
  Added 3 `wrap_err_with` calls in `src/config_loader.rs` so a typo
  in a YAML config now produces e.g.
  `Error: Mining configuration error: Mining agent 'miner-001':
  hashrate 200% out of valid range (must be 1-100)` instead of a
  panic stack trace.
- **`.unwrap()` sweep on post-hoc analysis paths.** 96 unwraps in
  `src/bin/tx_analyzer.rs` + `src/analysis/**` converted; uniformly
  Category A — the largest tranche (81 in `tx_analyzer.rs`) was
  `writeln!`/`write!` to a `String`, provably infallible. 6
  `partial_cmp(...).unwrap()` sites converted to
  `.unwrap_or(Ordering::Equal)` for NaN safety.
- **Narrowed bare `except Exception:` in `agents/base_agent.py` and
  `monero_rpc.py`.** 15 of 18 sites narrowed to specific
  exception types (`RPCError`, `OSError`, `json.JSONDecodeError`,
  `requests.RequestException`, etc.). 3 sites kept as `Exception`
  deliberately, with `noqa: BLE001` and an explanatory comment
  (the agent run-loop's outer try/except is the load-bearing
  example — narrowing it would risk killing miners on a single
  network hiccup).

#### Documentation accuracy sweep

Updated `README.md`, `QUICKSTART.md`, `docs/ARCHITECTURE.md`,
`docs/DETERMINISM_FIXES.md`, `docs/RUNNING_SIMULATIONS.md`,
`docs/PERFORMANCE_AND_SCALE.md`, `docs/AI_CONFIG_GENERATOR.md` for
post-refactor reality:
- Path renames (`config_v2.rs` → `config/`, `miner_distributor.py` →
  `miner_distributor/`, etc.).
- Stale line-number citations replaced with function-name anchors
  (line numbers rot; function names don't).
- Agent inventory: README's Agent-types table now distinguishes
  user-facing (4) from infrastructure (`dns_server`,
  `agent_discovery`, `public_node_discovery`).
- Project-structure trees re-pegged.
- Removed `--migrate` CLI flag references and dead-script mentions.

#### Other notable

- 4 unused-`mut` clippy warnings in `src/gml_parser.rs` (test code)
  + 1 unused-var in `src/topology/distribution.rs` cleared.
- Funding-status JSON write verified to be already atomic via
  `BaseAgent.write_shared_state` (write-then-rename). No change
  needed.
- Pre-existing flag (not addressed): `MoneroDNSServer._setup_logging`
  in `agents/dns_server.py` lacks the `if not logger.handlers:`
  idempotency guard. Production-safe (instantiated once) but worth
  a small follow-up fix.

### Key fix: upgrade-pipeline shutdown chain

Network upgrade scenarios (where nodes switch from `monerod`/`monero-wallet-rpc`
to `monerod-v2`/`monero-wallet-rpc-v2` mid-simulation) failed at scale: in a
1011-node run with seed 12345, **every** v2 wallet failed to bind because
the v1 wallet held port 18082 past `shutdown_time`. After the fix, the same
1011-node run completes with 0 wallet bind failures and 8.5× more blocks
mined post-upgrade than before.

The diagnosis went through three layers, each masking the next:

1. **`bash -c '...'` wrapper absorbed SIGTERM.** Daemon launches used
   `bash -c 'exec monerod ...'` (the `exec` makes bash hand off to monerod
   so SIGTERM lands on the binary), but the wallet path used
   `bash -c 'monero-wallet-rpc ...'` without `exec`. SIGTERM at
   `shutdown_time` killed bash; the wallet was reparented to PID 1 and
   kept running, holding the port. Fix: removed bash from daemon and
   wallet launches entirely. New `ProcessArgs` enum on `ShadowProcess`
   serializes args as a YAML sequence, passing them straight through
   to `execve`. Wrapper scripts (still needed for Python agents because
   Shadow has no `working_directory` field) now `exec python3 -m ...`
   so bash hands off to the Python interpreter the same way.

2. **Insufficient gap between phase 0 stop and phase 1 start.** Default
   was 30s; bumped to 5min (`DEFAULT_DAEMON_RESTART_GAP_S` and
   `DEFAULT_WALLET_RESTART_GAP_S` in `scripts/scenario_parser.py` and
   `scripts/generate_config.py`). This was based on a wrong diagnosis —
   Shadow doesn't escalate `shutdown_signal` to SIGKILL after a timeout,
   so a wallet that ignores SIGTERM ignores it forever — but the longer
   gap is still useful headroom for legitimate slow shutdowns and costs
   nothing in wall time.

3. **monero-wallet-rpc deadlock during normal operation.** Background
   refresh and in-flight transfer can compete for the wallet lock under
   Shadow's cooperative scheduling, leaving the main RPC thread blocked
   indefinitely. SIGTERM is queued behind the held mutex and never runs.
   Fix: non-final wallet phases now ship with `shutdown_signal: SIGKILL`
   (and `expected_final_state: Signaled(SIGKILL)`). Daemon phases keep
   the default SIGTERM since monerod handles it cleanly. Acceptable in
   the simulation context because the chain is canonical and v2 rebuilds
   wallet state on first refresh; full rationale, tradeoffs, and a
   documented escalation-wrapper alternative are in
   `docs/UPGRADE_WALLET_SIGKILL.md`.

#### Validation
- 1011-node, 72h-sim upgrade run after the fix: exit code 1 only because
  one wallet (user-894) crashed via SIGABRT — its own internal
  `std::length_error`, before our SIGKILL fired — instead of being
  Signaled(SIGKILL). The v2 wallet still bound and ran cleanly. 0/1000
  bind failures.
- Pre-upgrade vs post-upgrade block production stays within 0.3% of
  matching the time split (637 vs 635 blocks across 34h and 38h
  respectively). In the broken baseline, post-upgrade mining collapsed
  because the wallets were dead.

#### Files touched
- New: `docs/UPGRADE_WALLET_SIGKILL.md`
- `src/shadow/types.rs`: new `ProcessArgs` enum, new `shutdown_signal`
  field on `ShadowProcess`.
- `src/agent/user_agents.rs`, `src/process/wallet.rs`,
  `src/utils/script.rs`: direct binary launch for daemon and wallet,
  SIGKILL on non-final wallet phases.
- `src/process/agent_scripts.rs`, `src/agent/pure_scripts.rs`,
  `src/agent/simulation_monitor.rs`, `src/agent/miner_distributor.rs`,
  `src/orchestrator.rs`: wrapper scripts now `exec python3 -m ...`.
- `src/utils/options.rs`: `options_to_args` no longer wraps String
  values in shell quotes (no longer needed without bash); new
  `shell_quote_args` helper for the one path that still needs a shell
  string (`WALLET_RPC_CMD` env var consumed by `restart_wallet_rpc()`).
- `scripts/scenario_parser.py`, `scripts/generate_config.py`,
  `scripts/configure_upgrade.py`: gap defaults, with rationale.
- `docs/FLOW.md`, `docs/SCENARIO_FORMAT.md`,
  `scripts/ai_config/scenario_prompts.py`: doc updates.

## v0.0.2 (2026-04-16)

Changes since v0.0.1 (2025-10-07). The section "Since last shared (Mar 11)"
highlights what changed after the project was shared externally.

### Key fix: transaction starvation in Shadow

Shadow is a discrete-event network simulator where all processes on the same
simulated host share a single real CPU thread, switching only at syscall
boundaries. Each user agent runs two processes on one host: `monerod` (daemon)
and `monero-wallet-rpc` (wallet). When one user broadcasts a transaction, it
propagates to every other daemon for verification — and Monero tx verification
is CPU-heavy (~140ms for CLSAG + Bulletproofs+). While a daemon is verifying,
the wallet on that same host is blocked from running.

This caused a "winner take all" failure: the first user to transact would
flood other daemons with verification work, starving their wallets of CPU time.
The wallets would time out (180s), and only one user would ever successfully
transact.

The fix has two parts:
1. **Stagger**: space out `activity_start_time` values so transaction
   generation is evenly distributed: `stagger = interval / num_users`.
   With 3 users and a 60s interval, users start 20s apart, producing one
   tx every 20s instead of three simultaneous txs.
2. **Calibration**: measure how fast this specific CPU can verify transactions
   (by benchmarking CLSAG and Bulletproofs+ natively), then enforce a minimum
   `transaction_interval` so the network is never asked to verify faster
   than the hardware can handle.

This is a **Shadow simulation artifact**, not a real Monero issue. On real
hardware each node has its own CPU. See `docs/shadow-tx-stagger.md` for the
full explanation.

### Since last shared (Mar 11)

#### Calibration system (new)
- **Native hardware calibration**: `python3 scripts/calibrate.py` runs Monero's
  built-in `performance_tests` binary to benchmark CLSAG ring signature and
  Bulletproofs+ range proof verification on the local machine (~30 seconds).
- Calibration auto-runs on first config generation if no data exists.
  Use `--no-calibrate` on `scenario_parser.py` or `generate_config.py` to skip.
- Results saved to `~/.monerosim/calibration.json` and used to set a floor on
  `transaction_interval` so simulations don't exceed what the hardware can handle.

#### Transaction stagger (rewrite)
- **Replaced complex activity batching** with simple formula:
  `stagger = transaction_interval / num_users`. Removed `activity_batch_size`,
  `activity_batch_interval_s`, `activity_batch_jitter` parameters.
- **Fixed "only one user transacts" bug**: all users now reliably send
  transactions when using staggered `activity_start_time`.
- `activity_start_time: auto` now uses `compute_stagger()` for proper spacing.

#### wallet-rpc stability (Mar 27-28)
- Removed broken wallet-rpc restart logic that caused more harm than good.
- Fixed transfer deadlock by removing `max-concurrency` limit on wallet-rpc.
- Settled on `process_threads: 1` + `native_preemption: true` after testing
  many runahead/threading combinations.

#### run_sim.sh improvements (Mar 26)
- Human-readable `summary.txt` generated in archive directory.
- `--archive-blockchain` flag for percentage-based blockchain archiving.
- Fixed intermittent 0% progress display.
- Archive monitoring data (`final_report.json`) with simulation results.
- Guard archive steps so one failure doesn't skip the rest.

#### Portability and setup (Mar 14-24)
- Duration strings (`4h`, `30m`, `300s`) accepted in all config time fields.
- Auto-activate venv in all shell scripts.
- Move dependency repos into `sibling_repos/` (no more sibling dir assumptions).
- `--shared-ringdb-dir` isolates ring database per simulation.
- Various NameError and path discovery fixes.

#### AI config and scenario parser (Mar-Apr)
- Health check for MoneroWorld LLM server before use.
- Scenario parser bug fixes and Shadow settings documentation in AI prompt.
- Fixed expansion reporting and LLM config updates.

#### Other fixes since Mar 11
- Removed `initial_wait_time` from miner distributor.
- Updated quickstart config: seed 12345, reduced to 6h/8h durations.
- Updated `docs/shadow-tx-stagger.md` for new calibration method.

---

### Earlier changes (v0.0.1 to Mar 11)

#### Simulation runner (Mar 8-10)
- Full simulation runner (`run_sim.sh`) with live progress monitor, archiving,
  and disk space checks.
- Daemon logging switched from stdout to native `bitmonero.log` files.
- Live progress monitor parses Shadow's simulated time correctly.

#### AI config generator (Jan-Mar)
- Scenario YAML compact format with expander (`scenario_parser.py`).
- MoneroWorld test server as default LLM backend.
- Interactive mode with modify/new prompt options.
- Semantic validation and benchmark suite.
- Qwen3:8b model support, think-tag stripping.
- Ollama 8K context requirement documented and enforced.
- Monero facts display while waiting for LLM responses.

#### Config and agents (Jan-Mar)
- Named agents with configurable defaults (daemon_defaults, wallet_defaults).
- `process_threads` convenience setting for monerod/wallet-rpc thread control.
- `native_preemption` configurable.
- Duration strings in config fields.
- Relay node agent support (daemon-only, no wallet).
- Configurable relay node spawn staggering.
- Miner distributor refactored with unified `md_` parameters.
- Wallet recovery and continuous funding for upgrade resilience.

#### Setup and portability (Jan-Mar)
- `--clean` flag for fresh start.
- `--full-monero-compile` flag.
- Auto-install `python3-venv` when missing.
- Monero build dependency checks and auto-install.
- tmux/screen recommendation in setup intro.

#### Determinism (Dec 2025 - Jan 2026)
- Pass `simulation_seed` to Shadow for deterministic RNG.
- Replace `HashMap` with `BTreeMap` for deterministic serialization.
- File locking for shared state files.
- Sort lists before random selection.
- Determinism fingerprint generation and comparison tools.

#### Scaling and performance (Jan)
- 1200-node GML topology for scaling tests.
- Removed unnecessary GML placeholder hosts (major scaling improvement).
- `runahead` support for ~19% speedup.
- Memory monitoring and GML auto-selection.
- Batched bootstrap for large-scale simulations.
- Realistic regional bandwidth (Ookla data) and region-based latencies.

#### Network upgrade simulation (Jan)
- Multi-binary daemon support for upgrade scenarios.
- Wallet phase support and gap validation.
- Upgrade impact analysis for comparing pre/post metrics.
- `--daemon-binary` flag for config generator.

#### Analysis tools (Jan)
- Transaction routing analysis tool (`tx-analyzer`) in Python and Rust.
- Dandelion++ stem path reconstruction.
- Network graph analysis module for P2P topology.
- TX relay v2 protocol analysis for PR #9933 testing.
- Bandwidth analysis with time-windowed upgrade comparison.

#### Code quality (Feb)
- Major refactoring: Rust readability, Python agent cleanup, infrastructure.
- Dead code removal, deduplication, constant extraction.
- Code review fixes across the codebase.
- Consolidated duplicated patterns (deterministic hash, interruptible sleep,
  parse_bool, retry).

## v0.0.1 (2025-10-07)

Initial tagged release. Basic simulation with autonomous miners, regular users,
DNS server, and CAIDA network topology generation.
