# Simplify Bash Wrapper Usage in Shadow Process Generation

## Status: Implemented

The changes described below have been implemented on the `debash` branch.

## What Changed

### 1. Pre-simulation cleanup (main.rs)

`main.rs` now cleans `/tmp/monero-*` directories in addition to `/tmp/monerosim_shared/` before generating the Shadow config. This eliminated the per-agent `rm -rf /tmp/monero-{id}` from every daemon process.

### 2. Wallet directory pre-creation (orchestrator.rs)

The orchestrator pre-creates all `{agent}_wallet` directories under `/tmp/monerosim_shared/` with correct permissions (755). This eliminated the per-agent wallet cleanup Shadow processes that previously ran inside the simulation.

### 3. Removed curl retry loop from wrapper scripts (agent_scripts.rs)

The bash curl retry loop (30 attempts × 3s = 90s) was redundant with the Python-side retry in `base_agent.py` (`wait_until_ready()` with 120-180s exponential backoff). Removed from all wrapper script variants.

### 4. Pre-written wrapper scripts (orchestrator.rs)

Instead of two Shadow processes per Python agent (create script via heredoc + execute 1s later), wrapper scripts are now written to `shadow_output/scripts/` at generation time. Each agent only needs one Shadow process to execute the pre-written script. The orchestrator detects heredoc creation processes, extracts the script content, writes it to disk, and rewrites the Shadow host to use a single execution process.

### 5. Fully-resolved environment variables (agent_scripts.rs, pure_scripts.rs, orchestrator.rs, miner_distributor.rs, simulation_monitor.rs)

All shell variable expansion (`$HOME`, `${PYTHONPATH}`, `${PATH}`) has been replaced with fully-resolved absolute paths at generation time. Wrapper scripts now set `PYTHONPATH` and `PATH` to literal paths. Binary paths for monerod and monero-wallet-rpc are also fully resolved.

### 6. Fully-resolved binary paths (binary.rs, orchestrator.rs)

`resolve_binary_path_for_shadow()` now returns actual absolute paths instead of `$HOME/...` paths that required bash expansion. The orchestrator resolves `home_dir` and builds binary paths directly.

## Process Count Reduction

For a 25-agent simulation (5 miners, 20 users, 1 DNS server, 1 distributor, 1 monitor = 28 hosts):

| Host type | Processes before | Processes after |
|-----------|-----------------|-----------------|
| Miner (5) | 7 each (daemon+cleanup, wallet cleanup, wallet, 2×agent create+exec, 2×mining create+exec) | 4 each (daemon, wallet, agent, mining) |
| User (20) | 5 each (daemon+cleanup, wallet cleanup, wallet, agent create, agent exec) | 3 each (daemon, wallet, agent) |
| DNS server | 2 (create + exec) | 1 (exec) |
| Distributor | 2 (create + exec) | 1 (exec) |
| Monitor | 2 (create + exec) | 1 (exec) |
| **Total** | **~141** | **83** |

41% reduction in total Shadow processes.

## What Still Uses Bash

### Daemon exec pattern
```bash
bash -c 'exec /home/user/.monerosim/bin/monerod ...'
```
`exec` ensures SIGTERM goes to monerod, not bash. Could be eliminated if Shadow sends SIGTERM correctly to directly-launched binaries.

### Wallet-rpc launch
```bash
bash -c '/home/user/.monerosim/bin/monero-wallet-rpc ...'
```
Launched through bash but without `exec`. Candidate for direct binary launch.

### Python agent wrappers
```bash
bash shadow_output/scripts/agent_miner-001_wrapper.sh
```
Needed because Shadow has no `working_directory` field. The wrapper does `cd` and sets environment before running Python.

## Remaining Opportunities

- **Direct binary launch for daemon/wallet**: Test if Shadow sends SIGTERM correctly to directly-launched binaries (no bash wrapper). If so, daemon and wallet processes can skip bash entirely.
- **Eliminate `cd` from wrapper scripts**: If `PYTHONPATH` is sufficient for Python module resolution (no files loaded relative to cwd), the `cd` can be removed. This would make the wrapper just `export` + `python3`, which could potentially be done through Shadow's environment map + direct python3 launch.
