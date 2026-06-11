# Rucknium-analysis results — post-fix 1000-node run (200u @ 2400s)

**Run:** `archived_runs/20260607_234752_1k_rerun` (5 miners + 200 users + 800 relays, seed 12345, 16 h sim).
**Analysis:** `analysis/ruck_analysis.r` (Rucknium's `xmrpeers`-based P2P-gossip analysis), 10 user logs sampled with seed 314 — same methodology as his v0.1.0 review (issue #3).
**Date:** 2026-06-08. **Revised 2026-06-11:** interpretation corrected after
the mechanism investigation (`docs/20260610_rucknium_review_response_v2.md`);
all measurements below stand unchanged. Rates here are NOMINAL; this run
delivered 0.080 tx/s actual (see `analysis/results_clumping_0p67/rate_audit.md`).

This run carries the `max-connections-per-ip` fix and runs transactions at
0.083 tx/s nominal. It is the first post-fix 1000-node run analyzed with
Rucknium's own code.

## Headline comparison vs. Rucknium's originals

| Metric | Mainnet\* | 35-node | v0.1.0 1000-node | **Post-fix 200u (this run)** |
|---|---|---|---|---|
| Conn. duration — median | 23 min | ~120 min | ~1.5 min | **1.33 min** |
| Conn. duration — mean / max | — | — | ~20 min / 709 min | **20.5 min / 709.6 min** |
| **Clumping — % single-tx msgs** | **25%** | 89% | 23% (≈mainnet) | **92.4%** |
| One-second cycle | quarter-second | eighth-second | eighth-second | **eighth-second** |
| Skellam fit | good + zero-spike | close | "less close" | **good + modest zero-spike** |

\* Rucknium's "mainnet" reference is the **March 2024 black-marble-flood spam wave** (~1.45 tx/s) — that is the period his report studies.

## Key findings

1. **Clumping collapsed to 92.4% single-tx at low volume.** Transaction
   clumping (multiple txs per relay message) is driven by **tx volume**:
   ~90% single at low rates (35-node; this run at 0.080 tx/s delivered) vs
   ~23–25% single at high rates (mainnet spam wave 1.45 tx/s; the v0.1.0 run
   at 0.466 tx/s delivered). The full mechanism (flooding × Dandelion++
   flush windows × cascade re-batching) and the corrected delivered-rate
   curve are in the v2 response doc §4.

2. **Connection duration is essentially unchanged vs the v0.1.0 run**
   (median 1.33 vs ~1.5 min; mean 20.5 vs ~20 min; max 709.6 vs ~709 min) —
   because this metric is governed by monerod's own sync-search peer
   rotation (`update_sync_search`, 101 s timer), which is insensitive to
   both tx load and the connection-cap fix. Rucknium's tx-gap method is a
   valid proxy for tx-carrying TCP connection lifetimes; see the v2
   response doc §3 for the full mechanism.

3. **Eighth-second clustering persists** (8 petals in the one-second-cycle
   plot) — unchanged by the fix or tx volume. The quarter-second grid is
   Dandelion++'s fluff stepsize (`std::ratio<1,4>`); the jitter-free sim
   sharpens its fine structure (v2 response doc §5). Not runahead-related.

4. **Skellam fit is good** — empirical tracks theoretical closely with a
   modest zero-spike, like mainnet; tighter than the original run's
   "less close."

## Raw tables

### Peer connection duration (minutes; tx-gap method)

| | Minutes |
|---|---|
| Min. | 0.00 |
| 1st Qu. | 1.147 |
| Median | 1.330 |
| Mean | 20.549 |
| 3rd Qu. | 1.424 |
| Max. | 709.561 |

By direction: OUT median 1.285 / mean 20.05; INC median 1.353 / mean 21.06.
Share lasting >6 h: OUT 1.76%, INC 1.88% (>24 h: 0% both).

### Transaction clumping

| Txs in message | Share (%) |
|---|---|
| 1 | 92.37 |
| 2 | 3.54 |
| 3 | 1.64 |
| 4 | 0.36 |
| 5 | 0.23 |
| 6 | 0.27 |
| 7 | 0.36 |
| 8 | 0.48 |
| 9 | 0.40 |
| 10 | 0.22 |
| >10 | 0.12 |

## Plots
- `p2p-connection-duration.png` — kernel density of connection duration (INC/OUT)
- `one-second-period-tx-p2p-msg.png` — circular density; **8 petals = eighth-second** clustering
- `skellam-histogram-tx-p2p-msg.png` — tx-arrival time-difference vs theoretical Skellam (good fit)
- `ruck_plots_200u.pdf` — all three combined
- `ruck_raw_output.txt` — full R stdout (all tables + summaries)

## Bottom line
This run pins the low-volume end of the clumping curve (0.080 tx/s delivered
→ 92.4 % single). Connection-duration is governed by monerod's 101 s
sync-search rotation regardless of load or the cap fix, and the one-second
cycle is the D++ fluff grid sharpened by deterministic timing. For the
current, verified interpretation of all metrics — including the
matched-config replication of the v0.1.0 run on the fixed stack — see
`docs/20260610_rucknium_review_response_v2.md`.
