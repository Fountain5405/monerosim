# Code Quality Refactoring Plan

**Date**: 2026-02-13
**Branch**: 20260208-code-cleanup
**Baseline tests**: 20260212_e54ad610_tests (8/8 PASS)

## Context

The entire monerosim codebase was written via LLM "vibe coding." This plan addresses
systematic code quality issues to make the code readable and maintainable for human
developers. Changes are strictly refactoring — no behavior changes.

After each phase, the full test suite (8 config validation tests + 8 Shadow simulation
tests) must pass to confirm no regressions.

---

## Phase 1: Rust Readability

Goal: Make the two largest Rust functions readable and eliminate the worst duplication.

### 1.1 Split `generate_agent_shadow_config()` (orchestrator.rs, 624 lines)
Break into focused functions:
- `setup_simulation_environment()` — env vars, monero env, malloc tuning
- `configure_dns_server()` — DNS host creation
- `build_registries()` — agent/miner/public-node registry JSON generation
- `write_output_files()` — file I/O, wallet dir creation, logging
- `generate_agent_shadow_config()` — slim orchestrator calling the above

### 1.2 Split `process_user_agents()` (user_agents.rs, 766 lines, 21 params)
- Create `AgentProcessingContext` struct to bundle the 21 parameters
- Replace 6-tuple `(i, is_miner, is_seed_node, id, ip, port)` with named `AgentEntry` struct
- Extract `build_ring_connections()` helper (eliminates miner/seed-node duplication)
- Extract `calculate_start_times()` helper (eliminates redundant `matches!()` branches)
- Extract per-agent host creation into `create_agent_host()`

### 1.3 Extract duplicated bandwidth conversion (orchestrator.rs)
- Lines 72-97 and 107-136 contain identical Gbit/Mbit conversion logic
- Extract to `fn convert_bandwidth_value(value: &str) -> String`

### 1.4 Rename conflicting `AgentInfo` types
- `src/analysis/types.rs:29` → rename to `AnalysisAgentInfo`
- `src/shadow/types.rs:52` stays as `AgentInfo`
- Update all references in analysis modules

### 1.5 Extract magic numbers to named constants
- `MALLOC_MMAP_THRESHOLD: &str = "131072"`
- `DEFAULT_BANDWIDTH_BPS: &str = "1000000000"`
- `MAX_CONNECTIONS_PER_IP: u32 = 20`
- `DISTRIBUTOR_IP_OFFSET: usize = 100`
- `SCRIPT_IP_OFFSET: usize = 200`
- `WALLET_STARTUP_DELAY_SECS: u64 = 2`
- `AGENT_STARTUP_DELAY_SECS: u64 = 3`
- `REGISTRY_PREVIEW_CHARS: usize = 500`

### 1.6 Fix remaining unsafe unwrap() calls
- `orchestrator.rs:344` — `shared_dir_path.to_str().unwrap()` → proper error handling
- Agent modules using `Path::to_str().unwrap()` → `.to_string_lossy()`

**Test checkpoint**: Build, run config tests + shadow simulations.

---

## Phase 2: Python Cleanup

Goal: Eliminate duplication across Python agents and improve error handling.

### 2.1 Create `agents/constants.py`
Centralize magic numbers:
- `MATURITY_WAIT_SECONDS = 3600`
- `BALANCE_CHECK_INTERVAL = 30`
- `MAX_WAIT_SECONDS = 7200`
- `FUNDING_CYCLE_INTERVAL = 300`
- `DEFAULT_POLL_INTERVAL = 5`
- `DEFAULT_TX_INTERVAL = 60`
- `MAX_RETRIES = 5`
- `RETRY_DELAY = 3`
- `TARGET_BLOCK_TIME = 120.0`

### 2.2 Create `agents/shared_utils.py`
Extract repeated patterns:
- `resolve_wallet_address(agent_id, agent_info, shared_dir, rpc_client=None)` —
  centralized address lookup (currently duplicated in 5+ locations)
- `parse_agents_from_registry(registry_data, agent_type=None)` —
  handles both list and dict formats (currently duplicated 4+ times in agent_discovery.py)
- `validate_monero_address(address)` —
  address format validation (currently duplicated in miner_distributor.py)

### 2.3 Break up large methods in miner_distributor.py
- `_perform_initial_funding()` (200 lines) → split into:
  - `_wait_for_mining_maturity()`
  - `_discover_eligible_recipients()`
  - `_process_funding_batches()`
- `_send_batch_transaction()` (170 lines) → use `TransactionResult` dataclass for return type

### 2.4 Fix exception handling
- Replace bare `except Exception: pass` in regular_user.py with specific handlers
- Add logging to all catch blocks (no silent swallowing)
- Use specific exception types where possible (RPCError vs generic Exception)

### 2.5 Remove dead code
- `miner_distributor.py`: Remove unused `last_transaction_time`, `recipient_index`,
  `balance_check_attempts` attributes
- Clean up unreachable branches in `autonomous_miner.py`
- Remove excessive debug logging in `agent_discovery.py`

### 2.6 Clean up `run_sim.sh`
- Delete commented-out commands (lines 2, 4)

**Test checkpoint**: Run config tests + shadow simulations.

---

## Phase 3: Infrastructure

Goal: Improve build performance, add automated testing, and clean up scripts.

### 3.1 Add `LazyLock` for regex compilation (config_v2.rs)
- Replace 8+ `Regex::new().unwrap()` calls in `deserialize_agents()` with
  `std::sync::LazyLock` static patterns (available since Rust 1.80, our MSRV is 1.77
  so use `once_cell::sync::Lazy` or bump MSRV)

### 3.2 Add CI/CD pipeline
- Create `.github/workflows/ci.yml`:
  - `cargo build --release`
  - `cargo test --all`
  - `cargo clippy -- -D warnings`
  - `cargo fmt --check`

### 3.3 Add integration test
- Create `tests/integration_test.rs` that loads a test config YAML and runs
  `generate_agent_shadow_config()` end-to-end, validating the output

### 3.4 Clean up .gitignore
- Add `.claude/` directory
- Add `determinism_fingerprint_*.json`
- Add `benchmark_*.json`

**Test checkpoint**: Run config tests + shadow simulations.

---

## Test Procedure (after each phase)

```bash
# 1. Build
cargo build --release

# 2. Create test directory
COMMIT=$(git rev-parse --short HEAD)
TESTDIR="20260213_${COMMIT}_tests"
mkdir "$TESTDIR"

# 3. Copy test infrastructure
cp 20260212_e54ad610_tests/*.scenario.yaml "$TESTDIR/"
cp 20260212_e54ad610_tests/run_all_tests.sh "$TESTDIR/"
cp 20260212_e54ad610_tests/run_shadow_sims.sh "$TESTDIR/"

# 4. Run config validation tests
bash "$TESTDIR/run_all_tests.sh"

# 5. Run shadow simulation tests (~70 min)
bash "$TESTDIR/run_shadow_sims.sh"

# 6. Verify all pass
tail -5 "$TESTDIR/results.txt"
tail -5 "$TESTDIR/simulation_results.txt"
```
