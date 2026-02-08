# MoneroSim Code Review Report

Reviewed 2026-02-08 by Claude Opus 4.6. Project has been vibe-coded by AI assistants; this review focuses on code quality for human reviewers.

## Part 1: Shadow Fork (shadowformonero)

12 commits on top of upstream Shadow, modifying 22 files. Most modifications are **necessary and correct**.

### Critical Issue

**`sendmmsg` silently drops all messages** (`handler/socket.rs`) — The stub claims all `vlen` messages were sent without sending any data. If monerod uses `sendmmsg` for actual P2P communication, packets are silently lost. Should iterate over the message vector and call the existing `sendmsg` handler for each.

### Correct and Necessary Modifications
- **Constructor priority 101** for RNG interception — required for deterministic monerod seeding
- **Signal handler `_exit()` replacement** — fixes panic when `kill_process()` doesn't terminate immediately in Shadow
- **Memory locking stubs** (mlock/mlockall/munlock/etc.) — correct no-ops, irrelevant in simulation
- **Socket option stubs** (TCP_NODELAY disable, IP_TOS, TCP_KEEPIDLE, etc.) — prevents monerod crashes
- **Closed socket cleanup in `is_addr_in_use()`** — essential for daemon restart during upgrade scenarios
- **DNS passthrough via `getaddrinfo()`** — functional but the hand-written C DNS parser is a risk area

### Minor Issues
- `setfsuid`/`setfsgid` return 0 instead of previous UID (wrong per man page, but monerod likely doesn't check)
- `setresuid`/`setresgid` accept but don't store values (inconsistent with `getresuid`/`getresgid`)
- `reuseaddr` flag plumbed through 6 files but never actually consulted (`let _ = reuseaddr;`)
- Dead code in `shim_sys.c`: `is_localhost_addr()`, `SYS_SOCKET`/`SYS_CONNECT` defines
- Detailed strace logging for unsupported syscalls was removed, hurting debuggability

---

## Part 2: MoneroSim Rust Orchestrator

### Bash Remnants (the "debash" is incomplete) — HIGH

The debash removed bash wrapper scripts at the *output* level but the *generation* code still produces the old two-process pattern (Process 1: create wrapper script via heredoc, Process 2: execute it 1s later). A 100-line post-processing pass in `orchestrator.rs:770-876` then detects and rewrites these. This is backwards — the generation code should produce single-process definitions directly:

- `agent/pure_scripts.rs` — still generates two-process heredoc pattern
- `agent/miner_distributor.rs` — same
- `agent/simulation_monitor.rs` — same
- `process/agent_scripts.rs` — same (two call sites)
- `orchestrator.rs:400-421` — DNS server uses same pattern
- `orchestrator.rs:51-80` — `extract_heredoc_script()` function exists only to support the rewrite pass

### Dead Code — HIGH/MEDIUM

| File | Issue |
|------|-------|
| `agent/lifecycle.rs` (249 lines) | Not declared as module, references nonexistent config fields, would not compile |
| `agent/types.rs` (91 lines) | Declared but never imported; defines conflicting `AgentType` enum |
| `process/types.rs` (29 lines) | Declared, re-exported, never imported |
| `process/pure_scripts.rs` (127 lines) | Duplicates `agent/pure_scripts.rs`; never imported |
| 5 empty stub files | `process/daemon.rs`, `shadow/process.rs`, `shadow/network.rs`, `registry/miner_registry.rs`, `registry/agent_registry.rs` — all contain only "will be moved here in subsequent phases" |
| `config_v2.rs:1051-1079` | Dead `MinerDistributorConfig`, `PureScriptAgentConfig`, `SimulationMonitorConfig` structs |

### Hardcoded Values — HIGH

| Value | Location | Issue |
|-------|----------|-------|
| `/home/lever65` | `main.rs:145` | Hardcoded as fallback HOME — breaks for any other user |
| `192.168.10.10` | `orchestrator.rs:535,643` | Silent fallback IP when agent not in registry — produces broken config with no warning |
| `/tmp/monerosim_shared` | 8 files, 14 occurrences | Should be a single constant |
| Ports 18080/18081/18082 | scattered across 4+ files | Magic numbers, should be constants |

### Code Duplication — HIGH

- `options_to_args()` / `merge_options()` duplicated between `agent/user_agents.rs` and `process/wallet.rs`
- Bash wrapper script generation pattern copy-pasted 5+ times
- `process/pure_scripts.rs` fully duplicates `agent/pure_scripts.rs`
- Gini coefficient calculated in two analysis files

### Potential Bugs — MEDIUM

- `process/agent_scripts.rs:118,222` — `seconds - 1` with u64 will underflow to `18446744073709551615` if input is "0s"
- `analysis/upgrade_analysis.rs:527-528` — `.partial_cmp().unwrap()` on f64 will panic on NaN
- Stale IP module documentation claims private ranges (10.x.x.x) but code uses public ranges

---

## Part 3: MoneroSim Python Agents

### Correctness Bugs — HIGH

| Issue | Location |
|-------|----------|
| **`hash()` is non-deterministic** across Python processes | `regular_user.py:37`, `autonomous_miner.py:58`, `miner_distributor.py:41` — used for agent seeding, undermines reproducibility unless `PYTHONHASHSEED=0` is enforced |
| **`time.sleep()` in `run_iteration()`** blocks shutdown | `autonomous_miner.py:467` — sleeps for potentially hundreds of seconds, ignoring SIGTERM. Bypasses BaseAgent's 1-second shutdown check loop |
| **Double cleanup via `atexit` + `finally`** | `simulation_monitor.py:117` — `_cleanup_agent()` runs twice on normal shutdown, generating duplicate final reports |
| **Bare `except: pass`** swallows all exceptions | `base_agent.py:248-250` — catches `KeyboardInterrupt`, `SystemExit` during cleanup |

### Dead Code

| Item | Location |
|------|----------|
| `_read_enhanced_block_data()` | `simulation_monitor.py:1154` — explicitly documented as dead, does `pass` |
| `simulation_monitor.py:1541-1542` | Try/except block where try is just `pass` — entire loop is dead |
| Unused imports: `glob`, `argparse`, `sys`, `fcntl` | Scattered across `simulation_monitor.py`, `autonomous_miner.py`, `miner_distributor.py` |
| `_get_simulation_time` comment says "placeholder" | `simulation_monitor.py:1443` — it's the actual production code (Shadow intercepts `datetime.now()`) |

### Code Duplication — HIGH

- **Boolean parsing** implemented 4 different ways in 3 files (`base_agent.py`, `miner_distributor.py`, `agent_discovery.py`) with subtly different behavior
- **Retry-with-exponential-backoff** pattern duplicated 5+ times despite `error_handling.py` already having a generic implementation
- **`generate_config()` / `generate_upgrade_config()`** share ~60% of their code (~200 lines copy-pasted)
- **`parse_duration()` and `calculate_activity_start_times()`** duplicated between `generate_config.py` and `scenario_parser.py`
- `_register_miner_info` / `_register_user_info` in `regular_user.py` are nearly identical

### Confusing for Human Reviewers

| Issue | Location |
|-------|----------|
| `regular_user.py` contains mining logic | `_run_miner_iteration()`, `_setup_miner()` in a file called "regular_user" |
| `agent_rpc` means "daemon RPC" | Throughout `base_agent.py` — name suggests RPC *to* the agent, not *from* it |
| `MoneroRPC.get_connections()` returns an int, not connections | Name implies it returns connection objects |
| `WalletRPC.__init__` sets `self.url` to same value parent already set | `monero_rpc.py:366` — with comment "uses a different endpoint" |
| `tx_interval` appears twice in `generate_config()` docstring | Lines 623 and 633 — merge conflict artifact |
| Agent type derived by stripping "agent" from class name | `base_agent.py:507` — produces `regularuser`, `autonomousminer` |
| Diagnostic `INFO` logging left in production | `base_agent.py:443-461` — every agent logs file sizes and previews at startup |
| `DEFAULT_ACTIVITY_BATCH_SIZE` differs between files | `scenario_parser.py`: 10, `generate_config.py`: 0 (auto-detect) |

### Hardcoded Values

| Value | Location |
|-------|----------|
| Mainnet Monero address as fallback | `autonomous_miner.py:202` — mining rewards silently sent to known address |
| `/tmp/monerosim_shared` | 4+ files — same as Rust side |
| Shadow epoch `946684800` | `regular_user.py:196` and others — scattered constant |

---

## Recommended Priority for Fixes

1. **Finish the debash** — Make generation code produce single-process definitions; remove `extract_heredoc_script()` and the rewrite pass
2. **Remove dead files** — `agent/lifecycle.rs`, `agent/types.rs`, `process/types.rs`, `process/pure_scripts.rs`, 5 empty stubs
3. **Fix `sendmmsg` in Shadow fork** — implement actual message forwarding instead of silent drop
4. **Fix hardcoded `/home/lever65`** and `192.168.10.10` silent fallback
5. **Extract shared constants** — `/tmp/monerosim_shared`, ports, Shadow epoch
6. **Fix Python `hash()` seeding** — use `hashlib` or enforce `PYTHONHASHSEED=0`
7. **Fix miner `time.sleep()`** — use BaseAgent's interruptible sleep pattern
8. **Deduplicate boolean parsing and retry logic** in Python agents
9. **Remove diagnostic INFO logging** from `_register_self()`
10. **Consolidate `generate_config`/`generate_upgrade_config`** shared logic
