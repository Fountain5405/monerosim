# Performance and Scale Limits

This document describes the knobs that affect how fast a Monerosim simulation
runs on wall-clock time, and the practical scale limits on different hardware.

The core metric is the **wall-to-sim ratio**:

```
ratio = sim_time_reached / wall_time_elapsed
```

A ratio of `1` means the sim takes exactly as long to run as the simulated
duration. A ratio of `5` means a 6-hour sim finishes in 1h 12m. A ratio
below `1` means you are watching simulated time crawl slower than your
wristwatch — and below `~0.1` Shadow tends to stall entirely ("the cliff").

## What makes a simulation slower

These knobs **increase wall time** (reduce ratio):

| Knob | Effect | Notes |
|---|---|---|
| **N user agents** | ~linear in N | Biggest single factor. Each user runs a monerod + wallet + Python agent. |
| **M total nodes** (users + relays + miners) | Scheduler cost per tick | Shadow advances every host every tick. More hosts = slower. |
| `transaction_interval` below the storm floor | Shadow chokes on tx propagation events | Auto-config raises this to `N × M × K / C` (see `calibrate.py`). |
| `poll_interval` on `simulation-monitor` too low | Monitor RPC-polls every node each cycle | Auto-config uses `M / (C × rate)` with a 300s floor. |
| `transaction_frequency` on `miner-distributor` too low | Funding cycle hits every node too often | Same RPC-polling pattern. |

These knobs **decrease wall time** (improve ratio) but come with tradeoffs:

| Knob | Effect | Tradeoff |
|---|---|---|
| `runahead: 500ms` (default 100ms) | Shadow batches more events before sync | Slightly less accurate timing between hosts |
| `process_threads: 2` (default 2) | Threads per simulated process | `0` = non-deterministic but fastest; `1` = deterministic but slow |
| `native_preemption: true` (default false) | Shadow preempts long-running code | Improves wall perf; can break strict reproducibility |

## Hard scale limits per machine

These are guardrail caps used by the auto-config — exceeding them doesn't
immediately fail, but past the cap you are likely to hit stalls, OOM, or
the Shadow host-count cliff:

| RAM | Approx safe N (users) | Who this is |
|---|---|---|
| < 12 GB | 30 | Old laptop; swap-bound quickly (each host ~250 MB) |
| 12–24 GB | 75 | **Typical laptop (16 GB is common)** |
| 24–48 GB | 150 | **Typical desktop / workstation (32 GB is common)** |
| 48–96 GB | 350 | Power-user workstation |
| ≥ 96 GB | 600 | Server-class; top tier is also capped by the host-count cliff |

Most general users are in the 16–32 GB tier and should plan for N ≤ 150
unless they know their machine handles more. N ≥ 350 typically requires
dedicated server hardware.

Cores add a second cap: `3 × cores`, whichever is lower. Shadow's per-host
scheduler starts degrading past ~3 simulated hosts per physical core.

### Why isn't the top tier higher on a 1 TB / 256-core machine?

We observed a reliable stall at N=1000 even on a machine with abundant
RAM and cores. The cause is not RAM or compute — Shadow's event queue and
per-host scheduler scale non-linearly past ~1000 hosts. Until that is
understood or fixed, the top tier is set conservatively at 600.

## Auto-config guardrails

When agents use `auto` values for `transaction_interval`,
`activity_start_time`, `poll_interval`, or `start_time_stagger`, the
scenario parser will:

1. **Calibrate once** per machine using `calibrate.py`, which benchmarks
   CLSAG and Bulletproofs+ verification time (the actual crypto your sim
   will hammer per-tx).
2. **Compute a safe `transaction_interval`** using the measured p95 and
   the Shadow-storm floor `N × M × K / C`.
3. **Estimate wall time** using `p95 × pessimistic_coefficient × N`.
4. **Warn** if the estimated wall time exceeds `stop_time`, or if `N`
   exceeds the per-machine safe cap.

Example output at `N=1000` on a 6-hour sim:

```
Resolved transaction_interval=auto to 11777s (calibrated for 1000 users × 1005 nodes).
Estimated wall time for N=1000 users: ~1038 min (stop_time=360 min, predicted ratio ≈ 0.35).
⚠ Warning: estimated wall time exceeds stop_time.
⚠ Warning: N=1000 exceeds the per-machine safe cap (~600 for this hardware).
```

Power users who know their machine can bypass the guardrail by setting
`transaction_interval` (and related fields) to explicit values per agent.

## Empirical baseline

Cross-machine scaling sweep (all at `stop_time=6h`, 3 miners, no relays):

| Machine | cores | RAM | N | wall | ratio | notes |
|---|---|---|---|---|---|---|
| beryllium | 24 | 59 GB | 100 | 1069 s | 20× | fastest CPU we tested |
| beryllium | 24 | 59 GB | 300 | 1283 s | 17× | |
| phantom | 24 | 31 GB | 100 | 3667 s | 5.9× | |
| phantom | 24 | 31 GB | 160 | 6619 s | 3.3× | |
| r7525 | 256 | 1 TB | 300 | 10 410 s | 2.1× | |
| r7525 | 256 | 1 TB | 500 | 16 440 s | 1.3× | |
| r7525 | 256 | 1 TB | 1000 | timeout | 0.06× | **the cliff** |
| ffcmp | 12 | 8 GB | 30 | 6395 s | 3.4× | swap-bound |

Key observations:

- Wall time grows roughly linearly with N **within** a single machine.
- The per-user slope varies **~12×** across machines and is **not**
  predicted by cores, RAM, sysbench CPU score, or crypto p95 alone.
  Memory bandwidth and NUMA likely dominate.
- Therefore Monerosim does not attempt a universal wall-time formula.
  The auto-config estimator is deliberately pessimistic; actual runs
  are usually faster than the warning suggests.

## When to override the auto-config

Set explicit values per agent (bypassing `auto`) when:

- You know your machine handles larger N than the guardrail suggests
  (e.g., beryllium-class hardware that easily handles N=300).
- You need a specific `transaction_interval` for research (e.g.,
  reproducing a known-good run).
- You're OK with a ratio below 1 because the run is short.

To override, replace `transaction_interval: auto` with an explicit
value (in seconds), and do the same for `activity_start_time`,
`poll_interval`, `transaction_frequency`, and `start_time_stagger` if
you want full manual control.
