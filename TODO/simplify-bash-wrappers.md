# Simplify Bash Wrapper Usage in Shadow Process Generation

## Problem

Every process in the generated Shadow YAML uses `/bin/bash` as the executable. There are 22 bash wrapper instances across the codebase. Most of the complexity exists to handle cleanup of old simulation runs, which could be done once before the simulation starts.

## Current State

Each agent host generates ~5 processes, all through bash:

1. `bash -c 'rm -rf /tmp/monero-X && exec monerod ...'` (cleanup + daemon)
2. `bash -c 'rm -rf .../X_wallet && mkdir -p ... && chmod 755 ...'` (wallet dir cleanup)
3. `bash -c 'monero-wallet-rpc ...'` (wallet)
4. `bash -c 'cat > /tmp/wrapper.sh << EOF...EOF'` (create agent script)
5. `bash /tmp/wrapper.sh` (execute agent script)

For a 25-agent simulation, that's ~125 processes, many of which exist solely for cleanup or file creation.

## What Can Change

### 1. Move cleanup to pre-simulation (main.rs)

**Current**: Each agent cleans its own `/tmp/monero-{id}` directory at daemon start time via bash.

**Proposed**: `main.rs` already cleans `/tmp/monerosim_shared/`. Extend it to also glob and remove `/tmp/monero-*` directories. This eliminates the `rm -rf` from every daemon process.

**Impact**: Daemon processes become `exec monerod ...` instead of `rm -rf ... && exec monerod ...`. Still needs bash for `exec` (signal handling), but simpler.

**Exception**: Daemon phase 0 must still clean (phase 1+ must NOT clean, they reuse the data dir). But if main.rs cleans everything pre-simulation, phase 0 doesn't need its own cleanup either -- the directory is already gone.

**Files**: `main.rs` (add cleanup), `user_agents.rs` (remove rm -rf from phase 0 args)

### 2. Pre-write wrapper scripts at generation time

**Current**: Two Shadow processes per Python agent -- one creates a wrapper script via `cat > file << EOF`, another executes it 1 second later.

**Proposed**: Write all wrapper scripts to disk in the Rust orchestrator (at the same time it writes `shadow_agents.yaml`). Then Shadow only needs one process per agent to execute the pre-written script.

**Impact**: Eliminates 12 "file creation" processes (DNS server, agents, distributor, monitor). Reduces total process count by ~30%.

**Files**: `agent_scripts.rs`, `pure_scripts.rs`, `orchestrator.rs` (DNS), `src/agent/miner_distributor.rs`, `src/agent/simulation_monitor.rs`

**Location for scripts**: Write to `shadow_output/scripts/` alongside `shadow_agents.yaml`. Shadow processes reference these paths.

### 3. Remove redundant curl retry loop from wrapper scripts

**Current**: Wrapper scripts contain a bash retry loop that curls wallet-rpc 30 times (90 seconds total) before starting the Python agent. The Python agent (`base_agent.py` / `monero_rpc.py`) ALSO has its own retry with exponential backoff (120-180 seconds).

**Proposed**: Remove the bash curl loop. The Python-side retry is sufficient and more robust (exponential backoff vs fixed 3-second interval).

**Risk**: Low. The Python retry has a longer timeout (120-180s vs 90s) and better backoff behavior.

**Files**: `agent_scripts.rs` (remove curl loop from wrapper template)

### 4. Pre-resolve environment variables in Rust

**Current**: Wrapper scripts use bash to expand `${PYTHONPATH}`, `${PATH}`, `$HOME` at runtime. This requires bash.

**Proposed**: Resolve these at generation time in Rust:
- `$HOME` is known (Rust reads it from env)
- `PYTHONPATH` can be built as an absolute path (project dir + venv site-packages)
- `PATH` can be built with the monerosim bin dir prepended

Then pass the fully-resolved values through Shadow's `environment` map. No shell expansion needed.

**Impact**: Wrapper scripts become just `cd /path && python3 -m agents.foo args`. Or possibly eliminate the wrapper entirely and use Shadow's process definition directly.

**Complication**: `cd` still requires bash. Shadow's `ShadowProcess` has no `working_directory` field. Either:
- (a) Add `working_directory` support to shadowformonero (upstream change)
- (b) Keep a minimal bash wrapper: `bash -c 'cd /path && exec python3 -m ...'`
- (c) Set PYTHONPATH to include the project root so `cd` isn't needed (Python module resolution would handle it)

Option (c) is the cleanest -- if PYTHONPATH includes the project root, `python3 -m agents.autonomous_miner` will find the module regardless of cwd. Need to verify this works for all agent scripts.

**Files**: `agent_scripts.rs`, `pure_scripts.rs`, `orchestrator.rs`

## What Cannot Change

### Daemon exec pattern still needs bash

Even after removing cleanup, we still want:
```bash
bash -c 'exec monerod --data-dir=/tmp/monero-X ...'
```

The `exec` ensures SIGTERM from Shadow goes directly to monerod, not to a parent bash process. Without bash, we'd need to launch monerod directly:
```yaml
path: "/home/user/.monerosim/bin/monerod"
args: "--data-dir=/tmp/monero-X ..."
```

This would work for signal handling (Shadow sends SIGTERM to the process it launched). But it requires the binary path to be fully resolved at generation time (no `$HOME` expansion). This is feasible since Rust knows `$HOME`, but is a behavioral change to validate.

**Decision needed**: Is `exec` actually necessary when Shadow launches the binary directly? If Shadow's SIGTERM goes to the launched process regardless, we can skip bash entirely for daemon/wallet launches.

### Wallet directory permissions mid-simulation

monero-wallet-rpc occasionally creates files/directories with restrictive permissions (`d---------`) during error recovery. The pre-wallet cleanup process (`rm -rf && mkdir -p && chmod 755`) handles this. If we move cleanup to pre-simulation only, a wallet-rpc crash mid-simulation could leave bad permissions that prevent re-access.

**Mitigation**: This is an edge case. Wallet-rpc doesn't restart mid-simulation in normal operation (no process restart mechanism in Shadow). Daemon phases are the only restart scenario, and wallet phase 0 cleanup would still run at the correct time.

### Daemon phases need per-phase cleanup logic

Phase 0: clean data directory (fresh blockchain)
Phase 1+: do NOT clean (continue from previous phase's blockchain)

Pre-simulation cleanup handles phase 0. Phase transitions still need bash for the `exec` pattern (stop old binary, start new one). The cleanup itself is handled by timing -- phase 0 starts from a clean `/tmp/monero-*` because main.rs cleaned it.

## Implementation Order

1. **Pre-simulation cleanup** (main.rs) -- lowest risk, highest impact
2. **Remove curl retry loop** -- simple deletion, Python retry is sufficient
3. **Pre-write wrapper scripts** -- moderate refactor, eliminates 12 processes
4. **Pre-resolve environment variables** -- enables further simplification
5. **Investigate direct binary launch** -- may eliminate bash for daemon/wallet entirely

## Estimated Process Count Reduction

| Change | Processes eliminated per agent |
|--------|-------------------------------|
| Pre-simulation cleanup | -1 (wallet dir cleanup) |
| Pre-write wrapper scripts | -1 (script creation process) |
| Direct daemon launch (if feasible) | -0 (still 1 process, just simpler) |
| Direct wallet launch (if feasible) | -0 (still 1 process, just simpler) |
| **Total** | **-2 per agent** |

For 25 agents: ~125 processes reduced to ~75. Simpler Shadow YAML. Faster simulation startup.

## Open Questions

- Does Shadow send SIGTERM correctly to directly-launched binaries (no bash wrapper)? Need to test with shadowformonero.
- Does `python3 -m agents.autonomous_miner` work correctly when cwd is not the project root, if PYTHONPATH is set? Need to test.
- Are there any agents that depend on the bash retry loop timing (starting exactly when wallet-rpc is ready, not with a backoff delay)?
- Should wrapper scripts live in `shadow_output/scripts/` or `/tmp/monerosim_scripts/`?
