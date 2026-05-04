# Refactor plan and progress (2026-05-03)

Snapshot of the AI-slop audit, refactor tiers, completed work, and open
threads. Picks up if the working session is interrupted.

## How we got here

The codebase has a year of vibecoded accretion. Four parallel audit
agents (Rust src/, Python scripts/, Python agents/, cross-cutting)
identified recurring AI-slop patterns. Highest-value findings were
organized into three tiers; lowest-value (and risky) suggestions were
explicitly marked DO NOT DO so future sessions don't waste time on them.

## Top themes from audit

1. **Parameter explosions** masking missing structs (Rust: 23, 18,
   14-param functions; Python: 32-param `generate_config`).
2. **Near-duplicate functions** that diverged via copy-paste
   (`add_wallet_process` vs `add_remote_wallet_process`,
   `call_daemon_with_retry` vs `call_wallet_with_retry`,
   `generate_config` vs `generate_upgrade_config`, three wallet-recovery
   blocks).
3. **Same concept in N languages** (`parse_duration` in Rust + Python +
   bash; color codes in 3 shell scripts; timing constants scattered
   across 3 Python files).
4. Naming chaos: agent vs node vs host (one term should win).

Most "comment slop" findings turned out to be justified — the team
values "why" comments tied to specific incidents (see
`docs/UPGRADE_WALLET_SIGKILL.md` and recent CHANGELOG entries).

## Tier 1 — high value, low risk

| # | Action | Status | Commit |
|---|---|---|---|
| 1.1 | Delete dead `is_miner` field on `AgentEntry` | DONE | `4c6ccd3a` |
| 1.2 | Extract `scripts/timing_constants.py` | DONE | `496883d3` |
| 1.3 | Merge `add_wallet_process` + `add_remote_wallet_process` (DaemonAddress enum) | DONE | `95b58dc2` |
| 1.4 | Dedupe `call_daemon_with_retry` + `call_wallet_with_retry` | DONE | `21f72c2e` |
| 1.5 | `BaseAgent._recover_wallet_connection()` consolidating wallet recovery | DONE | `39969da1` |
| 1.6 | Extract `scripts/colors.sh` sourced by 3 shell scripts | DONE | `5c0b3c17` |
| 1.7 | Retry `get_info()` in `BaseAgent.setup()` (discovered during 400-node calibration; `AutonomousMinerAgent` was crashing on transient empty-error from `get_info()` at sim t=15s) | DONE | `3e7a49a6` |
| 1.8 | Delete dead `transaction_frequency` field from miner-distributor (parsed but never read; ~25 templates implied seconds-between-distributions which is actually `md_funding_cycle_interval`) | DONE | (this commit) |

Net: ~110 lines removed across Tier 1.1–1.6; all `shadow_agents.yaml`
output verified byte-identical against pre-refactor baseline (paths
normalized via `sed`).

## Tier 2 — worth doing in the next month, NOT STARTED

These are bigger structural changes. Not byte-identical YAML output is
expected (struct field reordering); semantic equivalence verified via
`compare_determinism.py` fingerprint match.

| Action | Effort | Risk |
|---|---|---|
| Introduce `WalletProcessArgs` / `DaemonProcessArgs` / `UserAgentProcessContext` Rust structs to collapse the 14–23 param signatures | 1 day | Mechanical, many call sites |
| `GenerationConfig` dataclass for `generate_config`'s 32 params (nested `TimingOverrides`, `BatchedBootstrap`, `MinerDistributorConfig`) | 1 day | Same |
| Extract common core from `generate_config` ↔ `generate_upgrade_config` (~80% overlap per audit) | 1 day | Need integration tests first to prove behavior unchanged |
| Split `_run_user_iteration` (114 lines, 6 responsibilities) and `_perform_initial_funding` (192 lines) | 1 day | Hot paths — needs sim run to validate after |
| Pick **one term**: agent vs node vs host. Mass-rename. Update SCENARIO_FORMAT.md | 4h | Low risk, high readability win |
| Move dated `test_configs/*.yaml` artifacts to `archived_runs/`. Keep only generic templates | 30min | Pure cleanup |

## Tier 3 — DO NOT DO (explicit traps)

- "Move scenario expansion from Python to Rust." Tempting symmetry, but
  Python lets you iterate scenarios fast (the AI-config flow lives
  there). Don't pay the rewrite cost for orthogonality.
- "Flatten `error_handling.py`'s class hierarchy." Over-engineered, but
  load-bearing in many call sites. Cost-of-change > benefit. Tolerate.
- "Move `run_sim.sh`'s 1628 lines to Python." Bash is fine as glue.
  Only move *specific* functions (preflight disk math, ramdisk mounting)
  if you touch them anyway.
- "Convert `LLMProvider` to a function." It's anaemic now, but you'll
  add streaming / retry / multiple providers later. Leave it.

## Validation strategy

Three layers of verification, cheapest first:

1. **Bytewise YAML diff** (free, instant): generate
   `shadow_agents.yaml` for `test_configs/400node_upgrade.yaml` (or
   smaller) before and after each refactor. For Tier 1, expect
   byte-identical (after path normalization via
   `sed 's|/tmp/.../|PATH/|g'`). For Tier 2, expect a diff but verify
   it's field reordering only.
2. **Functional run**: `quickstart` (~10min wall) and `upgrade_smoke`
   (~17min wall) should both end with `summary.txt` PASS and 0 process
   failures. Determinism fingerprint via `scripts/analyze_success_criteria.py
   --fingerprint-only` then `scripts/compare_determinism.py` for semantic
   equivalence.
3. **Scale gate** before merging Tier 2 to main: full 1011-node
   `large_upgrade` (~15h wall). Catches scale-only regressions.

The 400-node `test_configs/400node_upgrade.{scenario,}yaml` was built
to be a middle-ground gate (~3h wall predicted, ~14h actual at first
run), but the 2026-05-02 run revealed Tier 1.7 first — see Open Issues.

## Open issues / context for next session

### 400-node sim revealed a startup-race crash
`archived_runs/20260502_211209_400node_upgrade/` ran with FIXED code
(reflog confirms HEAD never moved during the run; the `git checkout`
to broken was only ever a recommendation in conversation, never
executed). Result: all 5 miners crashed at sim t=00:00:15 with
`RPCError: {'code': 0, 'message': ''}` from `daemon_rpc.get_info()` in
`BaseAgent.setup()`. No mining → no blocks → no funding → no test
signal for the upgrade pipeline. The daemon RPC server is responsive
to `get_version` (the `wait_until_ready` check) but can briefly return
malformed empty errors for `get_info`. Fix: Tier 1.7.

### Calibration question still open
Even after Tier 1.7, we don't know whether 400 nodes reproduces the
**original** failure mode (wallets fail to bind after upgrade) or just
runs cleanly. Plan after Tier 1.7 fix: re-run the 400-node config and
see what survives.

### 1011-node baseline still trustworthy
The `archived_runs/20260501_195844_20260430_large_upgrade/` run
(pre-Tier-1, pre-Bug-1/2) is the last full upgrade-pipeline validation.
After Tier 1 + 1.7, a full 1011-node `large_upgrade` re-run is the
final trust signal we still need.

### Scenario sprawl untouched
Tier 2 includes "delete duplicate quickstart configs" (canonical is
`test_configs/quickstart.scenario.yaml`; the 4 dated/numbered variants
in test_configs/ and root are abandoned).

### Auto-memory has two notes that may be stale
- `project_max_connections_per_ip.md` and `project_disable_rpc_ban.md`
  are flags-of-the-week reminders. Verify still relevant before acting.

## Commits since baseline (`20260501_195844` archive)

```
5c0b3c17 Extract scripts/colors.sh sourced by all shell scripts
39969da1 Consolidate wallet recovery into BaseAgent._recover_wallet_connection
21f72c2e Deduplicate call_daemon_with_retry and call_wallet_with_retry
95b58dc2 Merge add_wallet_process and add_remote_wallet_process
496883d3 Extract shared timing constants to scripts/timing_constants.py
4c6ccd3a Remove dead is_miner field from AgentEntry
3ef6c513 regular_user: re-open wallet on -13 "No wallet file" error
5505a634 Add --shared-ringdb-dir to phase wallet args
80cb8f90 CHANGELOG: upgrade-pipeline shutdown chain (debash, gap, SIGKILL)
```
