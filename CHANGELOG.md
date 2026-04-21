# Changelog

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
