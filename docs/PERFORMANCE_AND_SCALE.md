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
| `md_funding_cycle_interval` on `miner-distributor` too low (default 300s) | Funding cycle sends a batch tx every interval; too frequent overloads the network | Default 5min is sane; only override if you need denser funding. |

These knobs **decrease wall time** (improve ratio) but come with tradeoffs:

| Knob | Effect | Tradeoff |
|---|---|---|
| `runahead: 500ms` (default 100ms) | Shadow batches more events before sync | Slightly less accurate timing between hosts |
| `process_threads: 2` (default 2) | Threads per simulated process | `0` = non-deterministic but fastest; `1` = deterministic but slow |
| `native_preemption: true` (default false) | Shadow preempts long-running CPU-bound code so other hosts get scheduled | See [Native preemption](#native-preemption) — improves wall perf; breaks strict reproducibility |
| `daemon_defaults.log-level: monitor` (default 1) | Cuts monerod log volume substantially while keeping the lines the live monitor and post-run analyzer parse | See [Tuning monerod log-level](#tuning-monerod-log-level). `log-level: 0` would silence the monitor; `monitor` is the safe perf knob. |
| `shadow_log_level: error` (default warning) | Drops Shadow's own log spam | Lose some Shadow diagnostics |
| `performance.model_unblocked_syscall_latency: false` (default true) | Skips per-syscall sim-time bookkeeping for non-blocking calls | **Don't enable.** See [Modeling syscall latency](#modeling-syscall-latency) — empirically stalls Monerosim runs even at quickstart scale. |
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

### Why turning it off breaks Monerosim runs

Empirically, setting this to `false` stalls Monerosim simulations —
even at quickstart scale (11 hosts). Sim time stays at `00:00:00.000`
indefinitely while monerod processes burn 100% real CPU.

The mechanism: monerod's startup phase (config parse, fakechain
genesis init, RandomX dataset alloc, etc.) is CPU-bound and makes
relatively few *blocking* syscalls. With non-blocking syscall costs
unmodeled, none of those calls advance Shadow's simulated clock. With
no events queued and no process making a blocking call, Shadow has
nothing to advance to — the clock freezes at zero and the run never
gets past startup.

This contradicts the earlier guidance in this section that said the
knob was "essentially free for Monero." That guidance was wrong:
Shadow can only advance simulated time when *something* is willing to
block, and monerod's hot init path doesn't block enough.

### Verdict

**Leave `model_unblocked_syscall_latency` at the default (`true`).**

Don't include it in the `performance:` block of your scenario YAML.
The other perf knobs (`runahead`, `process_threads`, `native_preemption`,
`daemon_defaults.log-level: monitor`, `shadow_log_level: error`) are
the safe ones; this one is a foot-gun.

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

## Tuning monerod log-level

monerod is the loudest process in the simulation. Per-host stdout
typically dominates archive size (often >99% — see the prune-archives
docs), and writing all those bytes through Shadow's syscall layer
isn't free at runtime either. Cutting log volume is one of the
biggest available perf wins.

But monerod's `--log-level 0` silences the very lines our tooling
needs:

- The live monitor (`agents/simulation_monitor/`) counts blocks by
  parsing `+++++ BLOCK SUCCESSFULLY ADDED` from `bitmonero.log`. That's
  `MINFO()` on the `blockchain` category, which `*:WARNING` (level 0)
  suppresses. Result: post-run summary reports 0 blocks regardless of
  what the chain actually did.
- The Rust post-run analyzer (`src/analysis/log_parser.rs`) needs
  `Received NOTIFY_NEW_FLUFFY_BLOCK`, `Received NOTIFY_NEW_TRANSACTIONS`,
  `NEW CONNECTION`, `Including transaction <HASH>`, and several other
  patterns. All on `net.p2p.msg`, `net.cn`, or `txpool` categories.
  All hidden at level 0.

### Three ways to set `daemon_defaults.log-level`

| Value | What monerod gets | When to use |
|---|---|---|
| `1` (default) | All `MINFO` everywhere — verbose | Default. Safe; enough granularity for debugging an individual host post-mortem. |
| `monitor` | Curated category string: `*:WARNING,blockchain:INFO,txpool:INFO,net.p2p.msg:INFO,daemon.rpc:INFO,...` | Best perf-with-monitoring tradeoff. Keeps every line the live monitor and post-run analyzer parse, drops the bulk noise (peer-conn lifecycle, verify, perf, serialization). |
| Literal category string, e.g. `"*:WARNING,blockchain:INFO,daemon.rpc:INFO"` | Passed through verbatim | Power-user override. You're on your own to keep what your tooling needs. |
| `0` | All `MINFO` suppressed; only WARNING+ globally | **Avoid unless you don't care about per-host data.** The live block counter and post-run analyzer go silent. Useful only for pure Shadow-throughput benchmarking where the simulation summary is irrelevant. |

YAML caveat: the literal-string form must be quoted because a leading
`*` is a YAML alias marker:

```yaml
daemon_defaults:
  log-level: "*:WARNING,blockchain:INFO,daemon.rpc:INFO"
```

### What `log-level: monitor` keeps

The curated string lives in `src/utils/options.rs` as
`MONITOR_LOG_CATEGORIES` and currently expands to:

```
*:WARNING,blockchain:INFO,txpool:INFO,net.p2p.msg:INFO,daemon.rpc:INFO,
global:INFO,stacktrace:INFO,logging:INFO,msgwriter:INFO,
verify:FATAL,serialization:FATAL,perf.*:FATAL
```

That set is calibrated against the patterns parsed by
`agents/simulation_monitor/` and `src/analysis/log_parser.rs`. If
either gains a new pattern that needs a different category, the
`monitor` string should be updated alongside.

### Wallet RPC

`wallet_defaults.log-level: monitor` is coerced to `0` (WARNING) at
config-generation time — `monitor` is a monerod-only shortcut and the
wallet-rpc binary doesn't recognize it. The intent ("be quiet") is
preserved.

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
`poll_interval`, and `start_time_stagger` if you want full manual
control.
