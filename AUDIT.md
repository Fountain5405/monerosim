# Codebase Audit — monerosim

Scope: full repo (Rust `src/`, Python `agents/` and `scripts/`, shell
orchestration, configs, docs, deps). Investigation only — no code modified.

The audit was conducted independently from any prior review/planning files; see
"Skipped files" in Open Questions for what was deliberately not read.

---

## 1. Executive Summary

The codebase is a working, mid-sized hybrid (Rust ~16K LOC, Python ~24K LOC,
shell ~3.7K LOC) and the high-level architecture is sound: a Rust config
generator drives a Shadow simulation, Python "agents" run inside it via RPC,
and a post-run analysis suite parses logs. README/CLAUDE/docs match the code
better than is typical for AI-generated projects, and obvious AI tells (TODO
spam, hedging comments) have largely been pruned.

The remaining problems cluster around three themes:

- **Parallel implementations of the same job that drifted.** The most
  significant: a 1505-line Rust `tx-analyzer` and a 2585-line Python
  `tx_analyzer.py` doing the same analysis; three "post-sim verification"
  Python scripts whose responsibilities overlap; a `error_handling.py` whose
  docstring says it's a port of an `error_handling.sh` that no longer exists.
- **Unused / dead surface area.** Several Python scripts in `scripts/` are
  never imported or invoked from any wrapper (verify_simulation.py,
  verify_transaction_inclusion.py, compare_determinism.py, enhanced_monitor.py,
  post_simulation_monitor_analysis.py, regenerate_enhanced_blocks.py,
  log_processor.py). Test files are blanket-excluded from version control
  (`.gitignore` line 49: `test_*.py`), so the project has no committed tests
  at all despite a `pyproject.toml` that wires up pytest. A `--migrate`
  config-loader path exists for an old format that no current YAML uses.
- **Bloated single units.** A handful of files are doing too much:
  `src/orchestrator.rs::generate_agent_shadow_config` (~650 LOC in one fn),
  `agents/simulation_monitor.py` (1652 LOC), `agents/miner_distributor.py`
  (1457 LOC), `scripts/generate_config.py` (1925 LOC), `scripts/tx_analyzer.py`
  (2585 LOC), `run_sim.sh` (1623 LOC).

Everything else (defensive `.unwrap()`s, hardcoded retry constants, embedded
Python heredocs in shell, mislabeled module names) is real but follow-on. The
codebase is healthier than the line counts suggest; the 2–3 themes above drive
most of the maintenance pain.

---

## 2. Findings

### 2.1 Duplicate / parallel implementations

**F-DUP-1 — Two `tx_analyzer` implementations, both maintained.**
- `src/bin/tx_analyzer.rs` (1505 LOC) and `scripts/tx_analyzer.py` (2585 LOC).
- Both docstrings claim the same scope: "Transaction routing analysis... spy
  node vulnerabilities, network resilience, Dandelion++". Both parse the same
  log inputs.
- `start_here.sh:524–532` documents the Rust binary as canonical. The Python
  version is referenced from `scripts/archive_simulation.sh` and several docs
  but is the larger codebase by 70%, suggesting accumulated drift.
- Recent git history touches both intermittently (commit `7775ff7f "Align
  Python spy node analysis with Rust implementation"` shows manual sync was
  needed at least once) — this is a long-term maintenance tax.
- Effort to consolidate: **large**. Likely outcome: keep Rust as the only
  analyzer; replace `scripts/tx_analyzer.py` with a thin wrapper or delete it
  outright if no doc/script flow requires the Python form.

**F-DUP-2 — Triple-overlap "verify the simulation" scripts in `scripts/`.**
- `scripts/verify_simulation.py` (331 LOC) — reads agent_registry, final_report
  JSON, checks node counts/heights.
- `scripts/analyze_success_criteria.py` (574 LOC) — parses raw daemon logs
  for blocks_mined, tx_received, consensus checks.
- `scripts/post_simulation_monitor_analysis.py` (687 LOC) — reads shared-dir
  monitor files, recounts TXs in blocks.
- Of these, only `analyze_success_criteria.py` is wired up
  (`scripts/post_run_analysis.sh:14`). The other two are unreferenced from
  any shell, Python import, or doc beyond their own headers — see F-DEAD-1.
- Effort: **medium**. Confirm intent (probably consolidate into one tool
  fronted by `post_run_analysis.sh`), then delete the rest.

**F-DUP-3 — `scripts/error_handling.py` (1043 LOC) is a stale port.**
- Module docstring (line 9): "This is a Python port of error_handling.sh,
  providing the same functionality in a more Pythonic way." But
  `find . -name error_handling.sh` returns nothing — the original is gone, so
  the comment is misleading.
- The module is also misnamed: it's not "error handling" — it's a
  Monero-RPC verification + retry library (RetryHandler, VerificationHandler,
  daemon/wallet readiness checks, P2P connectivity polling). Only 3 callers:
  `analyze_network_connectivity.py`, `analyze_success_criteria.py`,
  `sync_check.py`.
- Effort: **small**. Rename to `monero_verification.py` (or split RetryHandler
  out), remove the stale docstring.

**F-DUP-4 — Two agent-discovery modules.**
- `agents/agent_discovery.py` (887 LOC) — caches JSON registries from disk
  for in-sim agents.
- `agents/public_node_discovery.py` (264 LOC) — separate discovery for
  wallet-only agents pointing at remote daemons.
- Both reasonable in isolation; worth verifying they don't share helpers
  that should be in `shared_utils.py`. Some overlap in TTL/round-robin
  logic. Effort: **small**.

**F-DUP-5 — `scripts/colors.sh` extracted but not universally adopted.**
- Per `git log`, `colors.sh` was extracted recently. Sourced from
  `setup.sh`, `run_sim.sh`, `start_here.sh`, but `update.sh:16–20` and
  several `scripts/*.sh` still redefine ANSI codes inline.
- Effort: **trivial**.

**F-DUP-6 — `SIM_EPOCH=946684800` redefined in two scripts.**
- `run_sim.sh:21` and `scripts/check_sim.sh:37`. The same constant is also
  in `src/lib.rs:27` (`SHADOW_EPOCH`). Three definitions in three languages.
- Effort: **trivial** to consolidate the shell pair (move to a sourced
  helper). Nothing to do across the language boundary.

### 2.2 Dead / unwired code

**F-DEAD-1 — Unreferenced Python scripts.**
Searched for invocations and imports across `*.sh`, `*.py`, `*.md`. Each of
the following is referenced *only* from its own header/docstring:
- `scripts/verify_simulation.py`
- `scripts/verify_transaction_inclusion.py`
- `scripts/compare_determinism.py`
- `scripts/regenerate_enhanced_blocks.py`
- `scripts/enhanced_monitor.py`
- `scripts/post_simulation_monitor_analysis.py`
- `scripts/log_processor.py` (referenced as commented-out lines in
  `scripts/check_sim.sh:502` and `scripts/post_run_analysis.sh:14`)

That's ~3–4K LOC of orphaned Python. Some may be intentional one-off tools
the user runs ad-hoc; flag in Open Questions before removal.
Effort to delete (after confirmation): **trivial–small**.

**F-DEAD-2 — `--migrate` config path supports a format no example uses.**
- `src/main.rs:60` exposes `--migrate`/`--migrate-output` flags.
- `src/config_loader.rs:71-108`: implementation strips "# Dummy nodes
  section" if present, otherwise file-copies. No YAML in `examples/` or
  `test_configs/` contains "Dummy nodes section".
- Effort: **trivial** to remove if confirmed-no-longer-needed. Conservative:
  leave one cycle, then delete.

**F-DEAD-3 — `src/analysis/tx_relay_v2.rs` integration unclear.**
- Module is `pub mod tx_relay_v2;` from `analysis/mod.rs` but I did not find
  it called from `bin/tx_analyzer.rs` or from `analysis/report.rs`. May be a
  partially-wired feature. Worth confirming. Effort: **small** to verify.

**F-DEAD-4 — `agents/__init__.py` re-exports types that nothing imports
through `agents`.**
- `MoneroRPC`, `WalletRPC`, `RPCError` are in `__all__`, but every internal
  caller does `from agents.monero_rpc import MoneroRPC`. The re-exports are
  surface area without consumers.
- Effort: **trivial**.

**F-DEAD-5 — `BaseAgent.retry_with_backoff` (`agents/base_agent.py:31–61`)
defined but called from a single site.**
- The single call is in `BaseAgent.setup()` for the daemon `get_info()`
  retry. Other RPC retry sites use ad-hoc loops. Either roll out the helper
  consistently or inline the one use.
- Effort: **small**.

### 2.3 Files that are too big / mixing concerns

**F-BLOAT-1 — `src/orchestrator.rs::generate_agent_shadow_config`
(`src/orchestrator.rs:138–784`).**
- ~650 LOC in one function: topology, IP allocation, environment
  composition, daemon-phase generation, wallet-phase generation, fallback-
  seed handling.
- Hard to test, hard to follow control flow, hard to reuse pieces.
- Effort: **medium**. Extract `setup_topology`, `setup_agent_phases`,
  `compose_environment`, `attach_fallback_seeds` helpers.

**F-BLOAT-2 — `src/agent/user_agents.rs` (819 LOC).**
- Mixes peer-topology builders (hardcoded/dynamic/hybrid + ring/mesh/dag),
  phase-timing math, options merging.
- `UserAgentProcessContext` (line 33) bundles 17 pass-through fields —
  symptom of a function that grew enough to need a struct just for
  arguments.
- Effort: **medium**. Pull the topology builders into
  `src/topology/peer_connections.rs`; let the struct shrink.

**F-BLOAT-3 — `src/config_v2.rs` (1175 LOC).**
- All config types + deserialize impls + validation rules + error enums
  (`PhaseValidationError`, `ValidationError`) in one file.
- Could be a `config/` submodule with `types.rs`, `defaults.rs`,
  `validation.rs`, `errors.rs`. The file no longer fits in a single
  reading.
- Effort: **medium**.

**F-BLOAT-4 — `src/analysis/upgrade_analysis.rs` (1206 LOC) and
`src/analysis/types.rs` (905 LOC).**
- `upgrade_analysis.rs` mixes window pre-partitioning, per-window metrics
  (TX propagation, bandwidth, peer counts), and result assembly.
- `types.rs` is a kitchen-sink of analysis structs; consider splitting per
  consumer.
- Effort: **medium** each.

**F-BLOAT-5 — `agents/simulation_monitor.py` (1652 LOC).**
- One class with ~28 methods covering: transaction tracking, block
  parsing, daemon log scraping, RPC polling, alert generation, file I/O,
  CLI entrypoint.
- Effort: **medium**. Extract `TransactionTracker`, `BlockTailer`,
  `AlertEngine`.

**F-BLOAT-6 — `agents/miner_distributor.py` (1457 LOC).**
- Recent commits have churned the give-up logic; remaining file mixes
  config parsing, miner discovery, funding logic, batch tx logic, state
  persistence. Effort: **medium**.

**F-BLOAT-7 — `scripts/generate_config.py` (1925 LOC).**
- Single config-writer; doable but huge. Reasonable to split timeline-math
  helpers from the YAML emitter.
- Effort: **medium**.

**F-BLOAT-8 — `run_sim.sh` (1623 LOC).**
- Functions are mostly cohesive (phase tagging is consistent), but the
  script embeds 19 separate `python3 -c "…"` heredocs for YAML/JSON
  parsing and arithmetic. Each is a subprocess and a hidden Python-stdlib
  dependency.
- Effort: **medium**. Extract a small `scripts/run_sim_helpers.py` and
  call it once per phase.

### 2.4 Defensive / error-handling smells

**F-ERR-1 — 179 `.unwrap()` calls across 13 Rust files.**
- Concentrated in `src/bin/tx_analyzer.rs` (81), `src/gml_parser.rs` (36),
  `src/config_v2.rs` (18), `src/analysis/upgrade_analysis.rs` (11),
  `src/utils/seed_extractor.rs` (4), `src/analysis/log_parser.rs` (7).
- Many lack `.wrap_err`/`.context` pairs, so users get `unwrap()` panics
  instead of "couldn't parse start_time for agent miner-001". Some are
  load-bearing in the analyzer where panic-on-bad-data is acceptable, but
  not all.
- Effort: **small–medium**. Sweep highest-traffic call sites first
  (config and orchestrator paths).

**F-ERR-2 — Inconsistent Rust error strategy.**
- Mix of `color_eyre::Result<T>`, bare `Result<T, String>` (e.g.
  `src/utils/validation.rs:38, 106, 147, 216, 298`,
  `src/utils/duration.rs:30`, `src/utils/ip_utils.rs:31, 43, 70`), and
  bespoke `thiserror` enums (`PhaseValidationError`).
- `String` errors lose type info and are awkward to chain. Picking one
  pattern (eyre at boundaries, thiserror at libraries) and applying it
  consistently would clean a lot up.
- Effort: **small** for utils; **medium** if extended deeply.

**F-ERR-3 — Bare `except Exception:` followed by warn-and-continue in
`agents/base_agent.py`** at lines 267–269, 292–293, 354–355, 362–363,
397–398, 420–421. Real failures get silently downgraded.
- Effort: **small**. Narrow each `except` and re-raise where the caller
  can't safely proceed.

**F-ERR-4 — `.unwrap_or_default()` on regex-capture in
`src/analysis/log_parser.rs:176`** masks malformed log lines instead of
flagging them. Effort: **trivial**.

**F-ERR-5 — Inconsistent `set` flags across shell scripts.**
- `set -euo pipefail` in `run_sim.sh:16`, `scripts/check_sim.sh:14`.
- `set -e` only in `setup.sh:3`, `update.sh:14`, `scripts/scaling_test.sh:9`.
- `set -u` only in `start_here.sh:10`.
- `set -eu` (no pipefail) in `scripts/scaling_sweep.sh:25`.
- The looser settings can hide pipe failures.
- Effort: **trivial**.

**F-ERR-6 — Dozens of `2>/dev/null` in `run_sim.sh`** that mask both
expected-empty-output cases and real errors. Inventory and tighten in
the high-impact paths (preflight, finish detection, lines 461, 810–812).
- Effort: **small**.

**F-ERR-7 — Funding state file not written atomically.**
- `agents/miner_distributor.py` persists `funding_status.json` via
  `_write_funding_status`. Recent commits add "permanently failed
  recipient" state to it. If the write is interrupted, instance state
  diverges from disk.
- Effort: **small**. Use `os.replace(tmp, dst)` write-then-rename.

### 2.5 Configuration sprawl

**F-CFG-1 — Default constants live in three places.**
- `src/lib.rs` (`SHARED_DIR`, `DEFAULT_DAEMON_DATA_DIR`, port numbers,
  `SHADOW_EPOCH`).
- `agents/constants.py` and `agents/__init__.py` re-export equivalents
  (`SHADOW_EPOCH`, `MONERO_*_PORT`).
- Shell scripts redefine `SIM_EPOCH=946684800`.
- These are deliberate language-boundary copies, not a bug, but the
  trio should be cross-referenced (single comment in each pointing to
  the others) so a future change doesn't drift.

**F-CFG-2 — IP offsets only relevant under one allocation strategy.**
- `DISTRIBUTOR_IP_OFFSET = 100` and `SCRIPT_IP_OFFSET = 200`
  (`src/lib.rs:46–48`) are only consulted by the static IP allocator.
  If dynamic allocation is the default path, these constants exist but
  are unreachable for most runs. Worth flagging in their docstrings.

**F-CFG-3 — `daemon_defaults` are merged in multiple sites.**
- Per-agent options are merged with `daemon_defaults` and
  `wallet_defaults` in `src/agent/user_agents.rs:701, 764` and again in
  `src/utils/options.rs::merge_options`. The `clone().unwrap_or_default()`
  pattern at the call sites is redundant — the `clone` is unnecessary.
- Effort: **trivial**.

### 2.6 Tests / dependencies / docs / artifacts

**F-TEST-1 — No tests are committed.**
- `pyproject.toml` declares `testpaths = ["agents", "scripts"]`,
  `python_files = "test_*.py"`, and `pytest` is in the dev deps. But
  `.gitignore` line 49 has `test_*.py` (and line 47 has `test_*.sh`,
  line 46 `test_*.yaml`). `git ls-files` confirms zero committed tests.
- Rust has unit tests inside 10 files via `#[cfg(test)]`; no `tests/`
  directory for integration tests.
- This is the single biggest gap. The pattern strongly suggests tests
  are written locally, never committed, and effectively don't exist
  for anyone but the author.
- Effort: **medium**. Decide which test files belong in the repo, add
  exceptions in `.gitignore` (`!agents/test_*.py`, `!scripts/test_*.py`,
  `!tests/`, etc.), and commit them.

**F-DEP-1 — Dependencies are clean.**
- Cargo: 13 deps; spot-checked that each is used (`rayon` in
  `analysis/bandwidth.rs`, `bincode`+`zstd` in `analysis/log_parser.rs`,
  `chrono` in `analysis/log_parser.rs`, etc.). No obvious bloat.
- Python: 4 runtime deps (`requests`, `PyYAML`, `networkx`, `dnslib`);
  all are imported. Dev/docs extras consistent. `scripts/requirements.txt`
  and `requirements.lock` may overlap with pyproject — see Open Questions.

**F-DOC-1 — README undercounts agent types.**
- README lines 130–135 list 4 agent types; there are 6 modules in
  `agents/` (also `dns_server`, `agent_discovery`, `public_node_discovery`).
  `docs/ARCHITECTURE.md` is correct. Minor README fix.

**F-DOC-2 — Multiple `docs/*.md` cite specific code line numbers**
(`docs/DETERMINISM_FIXES.md` is the example called out by the deps
agent). These will rot. Tag the relevant lines with comments instead, or
de-cite.

**F-ARTIFACT-1 — Runtime artifacts at root and in `scripts/`:**
`monerosim_errors.log` (root, 0 bytes), `performance_tests.log` (root,
6 KB), `scaling_sweep_results.csv` (root), `scripts/monerosim_errors.log`,
`scripts/simulation_summary_report_20260206_014125.txt`. All are
gitignored — confirmed not tracked — but they're sitting in the working
tree as background noise. Add a `make clean` / `./run_sim.sh --clean`
target, or remove them locally.

### 2.7 Naming / minor

- `config_v2.rs` and `tx_relay_v2.rs` retain `_v2` suffixes although no
  v1 exists in-tree. Cosmetic but signals migration scaffolding that
  should be retired post-migration. Effort: **trivial**.
- `BaseAgent` field group `daemon_rpc_port` / `wallet_rpc_port` /
  `remote_daemon` / `p2p_port` (all optional) lacks documentation about
  which combination is valid. Effort: **small** to add a class-level
  docstring of the valid configurations + a `setup()` precondition check.
- Variable names: `conns`, `merged_daemon_options`, `tmp` appear in
  hot spots; minor. Effort: **trivial** if/when those files are touched.

---

## 3. Remediation Plan

Each wave is independently shippable. Pick highest-value fixes per wave and
ship them; the wave structure is a recommendation, not a contract.

### Wave 1 — Safe, high-leverage cleanup (low risk)

Goal: shrink the code surface so subsequent work has less to track.
Target effort: ~1–2 days.

1. **Delete unwired Python scripts after a usage sanity check (F-DEAD-1).**
   Confirm with the author each file isn't run ad-hoc; remove the rest.
2. **Remove `--migrate` path if no input requires it (F-DEAD-2).**
3. **Remove unused `__init__.py` re-exports (F-DEAD-4).**
4. **Drop `BaseAgent.retry_with_backoff` or wire it in everywhere
   (F-DEAD-5).** Inlining is safer; promoting requires more diff but
   eliminates the ad-hoc retry loops.
5. **Rename `scripts/error_handling.py` → `scripts/monero_verification.py`
   and remove the stale port comment (F-DUP-3).**
6. **Standardize shell `set -euo pipefail` (F-ERR-5).**
7. **Source `colors.sh` from every shell script that uses ANSI
   codes (F-DUP-5).**
8. **Add `.gitignore` exceptions for `tests/`, `agents/test_*.py`,
   `scripts/test_*.py` so test files can be committed (F-TEST-1, prep).**
9. **Add atomic writes for `funding_status.json` (F-ERR-7).**
10. **Drop the redundant `.clone()` before `.unwrap_or_default()` in
    `src/agent/user_agents.rs:701, 764` and similar sites (F-CFG-3).**
11. **Tighten the hot `2>/dev/null` masks in `run_sim.sh`
    (F-ERR-6).**
12. **Remove stale `_v2` filename suffixes once the rest of the slack is
    pulled (F-naming).**

### Wave 2 — Structural consolidation (medium risk)

Goal: eliminate the parallel implementations and the largest grab-bag
files. Target effort: ~3–5 days.

1. **Pick a single tx-analyzer (F-DUP-1).** Recommend keeping Rust;
   replace `scripts/tx_analyzer.py` with a thin shell/python wrapper or
   delete it. Update `archive_simulation.sh` and docs.
2. **Consolidate verify_*/analyze_success_criteria/post_sim_monitor*
   into one validator (F-DUP-2).** Probably rename the kept script to
   `scripts/verify_run.py`, keep only the one wired into
   `post_run_analysis.sh`.
3. **Decide whether `agent_discovery.py` and `public_node_discovery.py`
   share enough to merge or just to share helpers (F-DUP-4).**
4. **Decompose `src/orchestrator.rs::generate_agent_shadow_config`
   (F-BLOAT-1).** Extract topology, environment, phase-generation
   helpers; keep the public entry point.
5. **Split `src/agent/user_agents.rs` (F-BLOAT-2)** — peer-topology
   builders move to `src/topology/peer_connections.rs`, options merging
   into `src/utils/options.rs` (already exists), phase math into a
   small module.
6. **Modularize `src/config_v2.rs` (F-BLOAT-3)** into a `config/`
   submodule.
7. **Modularize `src/analysis/upgrade_analysis.rs` and
   `analysis/types.rs` (F-BLOAT-4).**
8. **Split `agents/simulation_monitor.py` (F-BLOAT-5)** into
   tracker/tailer/alerter classes — start by carving out
   `TransactionTracker` and `BlockTailer`.
9. **Carve config-parsing out of `agents/miner_distributor.py`
   (F-BLOAT-6)** — distinct module for the data class + loader.
10. **Extract `scripts/run_sim_helpers.py` and replace the embedded
    `python3 -c` heredocs in `run_sim.sh` with calls to it (F-BLOAT-8).**

### Wave 3 — Deeper refactors (higher risk, higher value)

Goal: rethink abstractions and finally have tests. Target effort:
~1–2 weeks, can run alongside other work.

1. **Standardize Rust error handling (F-ERR-1, F-ERR-2).** One pass
   across config/orchestrator paths replacing `.unwrap()` with
   `.wrap_err`/`.context`; another replacing `Result<_, String>` with
   `eyre::Result` or a thiserror enum.
2. **Tighten Python error handling in `agents/base_agent.py` (F-ERR-3)** —
   narrow each `except Exception:` and re-raise where the caller can't
   recover.
3. **Commit a baseline test suite (F-TEST-1).**
   Minimum: one Python integration test per agent type (start agent in a
   process, point it at a fake daemon, assert behavior); one Rust
   integration test under `tests/` (load `examples/` YAMLs, generate
   shadow output, compare against checked-in golden files). With those,
   regressions become visible to the rest of the team.
4. **Decompose `scripts/generate_config.py` (F-BLOAT-7)** into
   timeline math vs YAML emission.
5. **Documentation cleanup (F-DOC-1, F-DOC-2)** — fix README counts;
   strip line-number citations from the docs (or replace with
   anchored comments in the cited code).
6. **Start an integration-style test of the full pipeline:**
   `examples/quickstart.scenario.yaml` →
   `scripts/scenario_parser.py` → `monerosim` → emitted Shadow YAML →
   schema validation. Without this, scenario_parser regressions go
   undetected.

---

## 4. Open Questions

These are things that look like slop but might be load-bearing or
intentional. **Please decide before Wave 1.**

1. **Are any of the orphaned `scripts/` Python tools (F-DEAD-1) actually
   run ad-hoc?** Some have CLI args and clear purpose
   (`compare_determinism.py`, `verify_transaction_inclusion.py`,
   `enhanced_monitor.py`). Confirm before deleting.
2. **Does `tx_analyzer.py` have features the Rust binary lacks?** The
   Python file is 70% larger; is that drift, or does it do post-processing
   the Rust analyzer skips? If the Rust binary is missing capabilities,
   port them before deletion.
3. **Is `--migrate` (F-DEAD-2) still needed?** When was the last config
   that used the old format? If never in this repo, remove.
4. **Is `tx_relay_v2.rs` (F-DEAD-3) intended to be wired into the main
   analyzer pipeline, or is it a partial WIP?**
5. **Is the pattern of gitignoring all tests (F-TEST-1) deliberate?**
   E.g., privacy/security concerns about test data? If yes, it should be
   documented; if no, it should change.
6. **`scripts/requirements.txt` vs `pyproject.toml` runtime deps** — are
   both source-of-truth, or is one a vestige? `requirements.lock`
   appears authoritative for the lock; clarify the script flow.
7. **`MONERO_FALLBACK_SEED_IPS` (`src/lib.rs:69`)** is a hardcoded
   defensive default backed up by a runtime extraction from
   `sibling_repos/monero-shadow/.../net_node.inl`. Is the hardcoded list
   intentionally a fallback-of-last-resort, or could it drift from
   upstream and hurt simulations?

### Skipped files (audit/planning artifacts encountered but not read)

Per the audit charter, none of the following influenced the findings:

- `TODO/` (gitignored by `.gitignore:109`; contains
  `block_explorer_txpool_proxy.md` — a feature plan).
- `.claude/` (gitignored by `.gitignore:118`; contains
  `scheduled_tasks.lock`).
- `docs/20260506_1011node_validation.md` (dated validation note,
  planning-style — header inspected, body skipped).
- `docs/20260503_refactor_plan.md` (currently staged for deletion in
  the working tree per `git status`; not read).
- `CHANGELOG.md` (also currently staged for deletion; not read).
- Several deleted-in-history paths surfaced via `git log` only as
  filenames: `docs/20250208_codereviews.md`,
  `docs/refactoring/REFACTORING_PLAN.md`, `docs/refactoring/baseline_*`,
  `docs/refactoring/determinism_fingerprint_*`,
  `TODO/code-quality-refactoring-plan.md`. These tell us prior reviews
  existed; their content was not consulted.

If any of these contain decisions that contradict findings here, the
contradictions are themselves worth a quick reconciliation pass.
