# 1011-node end-to-end validation (2026-05-06)

Trust-validation run for the Tier 1 refactor effort and the upstream
upgrade-pipeline fixes. This run is the one that confirms all of
Bug 1, Bug 2, and Tier 1.1–1.9 hold at full production scale through
a complete daemon+wallet phase upgrade.

## Run identifier

- **Archive path**: `archived_runs/20260505_103222_large_upgrade_short/`
  (kept around at least until the next major refactor; can be pruned
   via `start_here.sh > A > P` once trust is established)
- **Scenario**: `test_configs/large_upgrade_short.scenario.yaml`
  (committed; reproducible by re-expanding with `--no-safe-tx-interval`)
- **Wall clock**: started 2026-05-05 10:32 UTC, finished 2026-05-06 ~18:00 UTC

## Code state

HEAD at run start: `857d0233` "Auto-default native_preemption=true for
large sims" — i.e. all of Tier 1.1 through Tier 1.9 in place. Plus the
upstream upgrade-pipeline fixes (Bug 1 ringdb arg, Bug 2 wallet re-open
on -13). Plus the de-bash work from prior sessions.

## Headline metrics

| Metric | Value |
|---|---|
| Wall time | 31h 36m |
| Sim time | full 9h (32400s) reached |
| Exit code | 1 (cosmetic — 3 SIGABRT instead of SIGKILL on phase-0 wallets) |
| All 4 success criteria | PASS |
| Block height at end | 197 |
| Total user transactions sent | 5,242 across 1000 users |
| Process failures | 3 / ~2030 wallet-rpc processes (~0.15%) |
| Pre-upgrade window per user | ~27–60 min (depending on activity stagger) |
| Post-upgrade window per user | ~2h–2h55m |

## Pre/post upgrade activity per user (sample of users 1–15)

```
user-001:  0 pre /  16 post
user-002:  3 pre /  11 post
user-003:  2 pre /  16 post
user-004:  3 pre /  15 post
user-005:  3 pre /  11 post
user-006:  2 pre /  16 post
user-007:  2 pre /  16 post
user-008:  2 pre /  18 post
user-009:  2 pre /  16 post
user-010:  1 pre /  13 post
user-011:  2 pre /  16 post
user-012:  2 pre /  14 post
user-013:  2 pre /  14 post
user-014:  3 pre /  13 post
user-015:  3 pre /  13 post
```

Pre-upgrade ~0–3 txs / user is consistent with the 27–60 min window at
20-min intervals. Post-upgrade ~11–18 txs / user is what we'd expect if
wallets recover cleanly across the binary swap and continue transacting
at the configured cadence. **The ratio of post-upgrade to pre-upgrade
activity is the load-bearing signal that Bug 1 + Bug 2 fixes hold.**

## What was validated

- **Bug 1 (per-agent `--shared-ringdb-dir` for phase wallets)** —
  works at 1000-wallet scale. If it had failed, post-upgrade tx counts
  would have collapsed to near zero (each wallet would deadlock on the
  shared LMDB writer mutex).
- **Bug 2 (`BaseAgent._recover_wallet_connection` on -13)** —
  works at 1000-user scale. v2 wallet-rpc binaries start with no wallet
  loaded; without this fix, regular_user agents would hit `-13 / "No
  wallet file"` indefinitely after the phase boundary.
- **Tier 1.7 (`retry_with_backoff` around `daemon_rpc.get_info` in
  `BaseAgent.setup`)** — 0 miner startup crashes at 1011 nodes. Without
  it, the 400-node calibration run had all 5 miners crash at sim t=15s.
- **Tier 1.1–1.8 (Rust + Python refactors)** — no regressions surfaced.
  All `shadow_agents.yaml` outputs were verified byte-identical against
  pre-refactor baselines per refactor in the development cycle.
- **Tier 1.9 (auto `native_preemption: true` for ≥100 agents)** —
  prevented the LMDB resize freeze that killed the previous attempt at
  sim t=6h07 (`archived_runs/20260504_104925_large_upgrade_short/`).

## What this run does NOT validate

- **Wall-time efficiency at scale.** The 31h36m / 9h sim ratio (~0.28
  overall, ~0.10 in the post-bootstrap steady state) is dramatically
  worse than smoke-test runs. Native preemption fixes correctness but
  costs throughput. Smaller-scale variants (200–400 nodes) are still
  the practical iteration target.
- **The 3 SIGABRT wallet failures.** Identical pattern to the
  documented upstream wallet-rpc instability in
  `docs/UPGRADE_WALLET_SIGKILL.md`. Background ~1-in-1000 rate, not a
  regression. Not investigated further here.
- **2.47-sim/wall jump at wall hour 15.** Shadow apparently
  fast-forwarded ~2.5h of sim time once bootstrap quiesced. Worth
  understanding if it's reproducible / load-bearing or just a fluke.

## Reproduction (if you ever need to)

```bash
# 1. Free disk first — this run consumes ~150-200 GB
./start_here.sh   # > A > D to delete old archives

# 2. Expand scenario with the calibration override
python -m scripts.scenario_parser \
    test_configs/large_upgrade_short.scenario.yaml \
    -o test_configs/large_upgrade_short.yaml \
    --no-safe-tx-interval

# 3. Run (be ready for ~30h wall)
./run_sim.sh --config test_configs/large_upgrade_short.yaml
```

The scenario already declares `native_preemption: true` explicitly, but
even if you removed it the parser would auto-add it (Tier 1.9) for any
sim with ≥ `LARGE_SIM_NATIVE_PREEMPTION_THRESHOLD` agents.

## Cross-references

- **Refactor plan**: `docs/20260503_refactor_plan.md` (Tier 1.1–1.9
  marked done; Tier 2 still TODO)
- **Upgrade-pipeline incident notes**: `docs/UPGRADE_WALLET_SIGKILL.md`
- **Failed predecessor run (LMDB freeze without native_preemption)**:
  `archived_runs/20260504_104925_large_upgrade_short/`
- **Failed predecessor run (broken-state, pre-fix)**:
  `archived_runs/20260503_121247_20260430_large_upgrade/`
