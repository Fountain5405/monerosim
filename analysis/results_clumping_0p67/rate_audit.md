# Nominal vs. actual transaction rates — audit (2026-06-10)

The docs and reply draft label runs by **nominal** tx rate (`users / transaction_interval`).
Measured **actual** delivered rates are substantially lower at higher load, so the
clumping-vs-rate table's x-axis needs correcting. Active window = first
`activity_start_time` (18,000 s = sim 5 h) → `stop_time` (16 h) = **39,600 s**.

| run | config | nominal tx/s | created | **actual tx/s** | efficiency | source |
|---|---|---:|---:|---:|---:|---|
| 1k_rerun (20260607_234752) | 200u @ 2400 s | 0.083 | 3,175 | **0.080** | 96 % | summary.txt |
| 1k_mainnet milestone (20260608_164109) | 200u @ 667 s | 0.300 | 8,945 | **0.226** | 75 % | summary.txt |
| captest_cap4 (20260609_153322) | 200u @ 300 s | 0.667 | 13,688 | **0.346** | 52 % | summary.txt |
| **original v0.1.0 (20260511_164600, cap=1, old build)** | 200u @ 300 s | 0.667 | 18,444\* | **0.466** | 70 % | unique `Including transaction` hashes in `xfer_logs/monero-user-103.log` |

\* Unique tx hashes seen by one well-connected user node ≈ network-wide tx count
(its own ~90 originated txs are not re-received, so true count is ~0.5 % higher).
Log spans the full 16 h sim — completion of the original run re-confirmed.

## Implications

1. **Delivered rate saturates with load.** Per-user overhead beyond the configured
   interval grows with load on the current build: +91 s/tx (2400 s interval),
   +219 s (667 s), +279 s (300 s). Per-user counts are uniform (~66 ± 5 at 300 s),
   so the shortfall is systematic per-user blocking (funding/confirmation waits),
   not stragglers. Mechanism not yet verified — do not assert a cause in docs.
2. **Rucknium's 23.4 %-single clumping point sits at ~0.47 tx/s actual** (not 0.67).
   The milestone's 49.5 % point sits at ~0.23 tx/s actual (not 0.30). The 92.4 %
   point is honest (~0.08 ≈ nominal).
3. **Old build outpaced current build at the same config** (0.466 vs 0.346 tx/s,
   +33 %). It also mined more blocks (height 331 vs 272) → faster funding is the
   leading (unverified) candidate. Worth one look at block cadence configs/builds
   before claiming a regression.
4. **Milestone "standard mainnet" claim survives relabeling:** 0.226 tx/s ≈ 19.5 k
   tx/day — still within the normal-2025-mainnet band (~20–26 k tx/day), but the
   docs/reply must say ~0.23 tx/s actual (0.30 nominal), ~20 k tx/day.
5. **Spam-wave sizing math changes.** To deliver 1.45 tx/s actual with ~600 s
   effective per-user cycle would need roughly 870+ users, regardless of interval.
   The old "needs ~57 nodes" claim was wrong in the other direction; the honest
   statement is: delivered ceiling at 1000 nodes/200 users is ≥ 0.35 (current
   build) / ≥ 0.47 (v0.1.0 build) tx/s; 1.45 tx/s actual is untested and likely
   needs a user-count, not interval, change.

## Pending (fills in when clumping_0p67_monitor completes)

- clumping % at ~0.35 tx/s actual on current build (run `20260610_031558_clumping_0p67_monitor`,
  expected to mirror captest_cap4: same seed/build/config, monitor logging).
  If clumping is volume-bound, expect it BETWEEN 23.4 % (0.47) and 49.5 % (0.23) —
  i.e. ~30–40 % single. A 23 %-ish result would instead suggest clumping is not
  purely rate-bound at this scale.
- actual rate + per-user counts for that run (summary.txt).
