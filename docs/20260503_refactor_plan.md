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
| 1.8 | Delete dead `transaction_frequency` field from miner-distributor (parsed but never read; ~25 templates implied seconds-between-distributions which is actually `md_funding_cycle_interval`) | DONE | `1089af09` |
| 1.9 | Auto-default `native_preemption: true` in scenario_parser + generate_config when total agents >= 100. Without it, a single monerod's LMDB resize can deadlock the entire sim under Shadow's cooperative scheduling (observed in `archived_runs/20260504_104925_large_upgrade_short`). | DONE | `857d0233` |

**Tier 1 fully validated end-to-end at 1011-node scale on 2026-05-06.**
See `docs/20260506_1011node_validation.md` for headline metrics, pre/post
upgrade activity split, and reproduction notes. Post-upgrade tx counts
of 11–18 per user (vs 0–3 pre-upgrade) confirm Bug 1 + Bug 2 + Tier 1.7
all hold under real load at full scale.

Net: ~110 lines removed across Tier 1.1–1.6; all `shadow_agents.yaml`
output verified byte-identical against pre-refactor baseline (paths
normalized via `sed`).

## Tier 2 — DONE 2026-05-07

Net validation: refactor_gate (`archived_runs/20260507_035142_post_md_giveup_v2_gate`)
matches the 2026-05-06 baseline `archived_runs/20260506_193346_refactor_gate`
within ±1 tx. Wall time 1h 36m identical. 0 process failures. All 4
success criteria PASS. Miner tx counts identical per-miner (56/16/96/52/56).

| Action | Status | Commit |
|---|---|---|
| Move dated `test_configs/*.yaml` artifacts to `archived_runs/` | DONE | `63013fee` |
| `GenerationConfig` dataclass for `generate_config`'s 28 params | DONE | `47a55a39` |
| Rust `WalletProcessArgs`/`UserAgentProcessArgs`/`MiningAgentProcessArgs`/`UserAgentProcessContext` structs (22/18/14/14 params) | DONE | `32c3c57a` |
| Extract common core from `generate_config` ↔ `generate_upgrade_config` (-94 lines net) | DONE | `b3460246` |
| Split `_run_user_iteration` (97 lines → 6 helpers) and `_perform_initial_funding` (191 lines → 8 helpers) | DONE | `67d5c1f8` |
| Layer-consistent audit of agent/host/node terminology (5 drift fixes; mass-rename rejected — terms are layer-distinct, see below) | DONE | `02dc7102` |
| MD give-up threshold for permanently-broken recipients (closes plateau bug exposed by the cumulative gate run) | DONE | `c02a975e` |

### Notes for future readers

**agent/host/node are NOT synonymous in this codebase**:

- **agent** = Python script that simulates user activity (`agents/regular_user.py`, etc.). May control a node and/or wallet via RPC.
- **host** = Shadow's process container (one per simulated machine). Has its own network identity. May or may not run a node, may or may not run an agent. Pure relays are hosts with a node but no agent.
- **node** = a monerod process — a peer in the Monero P2P gossip network.

The original audit said "pick one and mass-rename." That would have conflated three layers. The audit-and-fix-only-mis-uses approach (commit `02dc7102`) found the codebase was already roughly correct; only 5 spots needed fixing, all docstring/comment/log-string drift.

**MD give-up first attempt was over-aggressive** (commit `8b7fcb62`, reverted in `d1efcd40`). It counted *all* batch failures including miner-side ones (e.g. "not enough unlocked money" during early sim). The corrected fix (`c02a975e`) only counts recipient-side failures — specifically, failures from `_get_recipient_address()` returning `None`, which surface as the `batch_failed` element of `_send_batch_transaction()`'s `(success=True, funded_ids, batch_failed)` tuple. Don't increment the per-recipient counter from no-miner-available paths or from generic batch-send failures.

**Wallet-rpc keys-file flake** observed at scale (3/100 in `archived_runs/20260507_004801_post_tier2_21_gate`): wallet-rpc fails to write `<host>_wallet/<host>_wallet.keys.new` even though the parent dir is pre-created at config-gen time (`src/orchestrator.rs:653-668`). Cause appears to be inside Monero's `wallet2.cpp::store_to()` — possibly a concurrent-write race when 100 wallet-rpcs bootstrap simultaneously. The MD give-up fix (`c02a975e`) lets MD transition past this gracefully. A separate root-cause fix would be welcome but isn't required.

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
   `shadow_agents.yaml` for `test_configs/refactor_gate.yaml` (or
   smaller) before and after each refactor. For Tier 1, expect
   byte-identical (after path normalization via
   `sed 's|/tmp/.../|PATH/|g'`). For Tier 2, expect a diff but verify
   it's field reordering only.
2. **Functional run**: `upgrade_smoke` (~17min wall) and
   `refactor_gate` (~1h36m wall) should both end with `summary.txt`
   PASS and 0 process failures. Determinism fingerprint via
   `scripts/analyze_success_criteria.py --fingerprint-only` then
   `scripts/compare_determinism.py` for semantic equivalence.
3. **Scale gate** before merging a tier to main: full 1011-node
   `large_upgrade_short` (~31h wall — see
   `docs/20260506_1011node_validation.md`). Catches scale-only
   regressions.

`refactor_gate` (5 miners + 100 users + 400 relays = 505 agents,
no upgrade) is the daily-driver gate, replacing the abandoned
`400node_upgrade` middle-ground attempt.

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
