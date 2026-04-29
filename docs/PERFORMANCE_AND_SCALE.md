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
| `native_preemption: true` (default false) | Shadow preempts long-running CPU-bound code so other hosts get scheduled | See [Native preemption](#native-preemption) — improves wall perf; breaks strict reproducibility |
| `daemon_defaults.log-level: 0` (default 1) | Cuts monerod log volume 10–100× | Less granular per-host forensics |
| `shadow_log_level: error` (default warning) | Drops Shadow's own log spam | Lose some Shadow diagnostics |
| `performance.model_unblocked_syscall_latency: false` (default true) | Skips per-syscall sim-time bookkeeping for non-blocking calls | See [Modeling syscall latency](#modeling-syscall-latency) — for Monero this is essentially free |
| Mount `/tmp` on tmpfs (system-side, not YAML) | LMDB writes go to RAM, not disk | Costs RAM proportional to chain size; for fakechain runs that's small |

## Modeling syscall latency

The `performance.model_unblocked_syscall_latency` knob is worth a dedicated
section because it tends to give a real wall-time win on Monero workloads
at near-zero cost in fidelity, and it's the perf knob people most often
misunderstand.

### What it is

A Shadow modeling decision: when a simulated process makes a syscall that
*doesn't actually block* — `getpid()`, `gettimeofday()`, a `read()` on a
buffer that already has data ready, an `epoll_wait` returning immediately
— should Shadow advance the simulated clock by the few microseconds that
syscall would cost on real hardware?

- `true` (default): yes, charge ~1.4 µs of sim-time per non-blocking syscall.
- `false`: no, treat non-blocking syscalls as instantaneous in sim-time.

Blocking syscalls (`recv` on a quiet socket, `nanosleep`, `read` on an
empty pipe, `epoll_wait` with no ready events) are *always* modeled
regardless — the simulated process is properly suspended until whatever
it's waiting on materializes. The toggle only affects the cheap,
non-blocking calls.

### Why the default is `true`

Real syscalls cost real CPU time even when they don't block: kernel
transition, argument copy, table lookup, return. If you skip that cost
in the model, processes that issue millions of cheap syscalls (logging,
time reads, epoll churn) tear through wall-time without ever advancing
sim-time, which:

1. Lets them starve out other processes in the work queue.
2. Produces unrealistic timing — a real Linux kernel does slow you down
   per syscall.
3. Can hide "syscall storm" pathologies that would matter on real hardware.

Shadow's safe default is therefore to model the cost.

### Why turning it off speeds things up

Per syscall, Shadow does extra bookkeeping: compute the latency, apply
it to the process's clock, possibly reschedule. Skipping that for
non-blocking syscalls means less per-syscall work in the simulator and
fewer "tiny" sim-time advances, which means fewer event-queue rebalances.

monerod is *very* talkative. Every socket read/write, every epoll cycle,
every log line involves multiple syscalls. Across 1000 hosts × hours of
sim-time you're talking billions of non-blocking calls. A 48h / 1k-host
run typically reports tens of billions of `Event` objects in
`sim-stats.json`, substantially driven by this. Removing the per-call
cost is one of Shadow's biggest available knobs.

### What you give up

Some accuracy in syscall-density-sensitive scenarios:

- A process doing a tight `gettimeofday()`-in-a-loop will no longer be
  throttled by sim-modeled syscall cost, so it can hog the work queue.
- Behavioral timing of code paths that *should* be slow because of
  syscall density will now appear instant.

For Monero this almost never matters because:

- Block validation / signing / verification is CPU work — Shadow models
  that via `process_threads` accounting, not syscall latency.
- Network behavior is gated by *blocking* `recv`/`epoll_wait`, which are
  still modeled.
- The non-blocking syscalls in the Monero hot path are mostly logging
  and epoll housekeeping — neither affects consensus or P2P semantics.

### Rule of thumb

| Workload | Recommended |
|----------|-------------|
| Anything Monero / CPU-heavy / network-bound | Safe to set `false` |
| Tight syscall-loop benchmarking, kernel-overhead studies, anything where per-syscall µs matter for the *result* | Keep `true` |

For a 1k-host run, `false` should give a real wall-time win with no
observable change in block production, sync behavior, or transaction
propagation. The only thing that'll look different is the `Event` count
in `sim-stats.json` and slightly different syscall-timing in any
forensic-level inspection of per-host stdout.

## Native preemption

The `native_preemption` knob is a sibling perf lever to syscall-latency
modeling — both trade a sliver of fidelity for meaningful throughput.

### What it is

Shadow only gets scheduling control back from a managed process when
that process makes a syscall. A CPU-bound code path with no syscalls
(a tight verification loop, a hash chain) would otherwise monopolize
the worker thread until it finally calls into the kernel.

- `false` (Shadow upstream default): Shadow waits for the next syscall
  before it can deschedule the process.
- `true` (our quickstart default): Shadow installs a signal-based timer
  (SIGVTALRM via `setitimer`) that forcibly yields the process every
  ~10ms of native CPU, so other hosts can make progress.

### Why turning it on speeds things up

Block validation (CLSAG, Bulletproofs+) is the longest CPU stretch in
monerod. Without preemption, one host doing a verify can starve every
other host queued on the same worker thread. With many hosts per core
— we recommend ≤3:1 but real ratios drift higher at scale — preemption
is what keeps the round-robin fair.

The win is most visible when `host_count > core_count`, which on the
target hardware tier is always.

### What you give up

- **Strict reproducibility**: the exact preemption point depends on
  wall-clock CPU timing, so two runs of the same seed can interleave
  differently at the instruction level. Consensus-level outcomes still
  match (Monero's protocol is deterministic), but per-host stdout
  ordering, `Event` counts, and any forensic timestamp comparison
  between runs may shift.
- Tiny overhead from signal delivery itself — negligible compared to
  the throughput gain.

### Interaction with `process_threads`

| `process_threads` | `native_preemption` | Result |
|---|---|---|
| `0` | `true` | Fastest, fully non-deterministic (our quickstart default) |
| `0` | `false` | Non-deterministic without the throughput win — rarely useful |
| `1` | `false` | Deterministic, slow — pick this for strict reproducibility |
| `1` | `true` | Determinism guarantee is broken; treat as effectively non-deterministic |

If you actually need bit-for-bit reproducibility (e.g., reproducing a
known-good run for a paper), set `process_threads: 1` *and*
`native_preemption: false`. Otherwise leave preemption on.

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
