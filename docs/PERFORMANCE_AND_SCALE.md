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
wristwatch. This used to be read as a hard wall ("the cliff" at N=1000); the
2026-10 scale ladder ran 3,011 nodes at an overall ratio of 0.44 — dropping to
~0.19 during the peak-transaction hours — with zero failed processes. Ratios
well below 1 are normal at scale and are not, by themselves, a stall. See
[Scale limits and the 2026-10 scale ladder](#scale-limits-and-the-2026-10-scale-ladder).

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
| `process_threads: 2` (default 1) | Thread-pool size inside each simulated daemon (monerod `--max-concurrency`/`--prep-blocks-threads`; cuprated pools). Not wallet-rpc, not Python agents, and **not** Shadow's worker threads (`parallelism`) | `1` = deterministic but slow. Cost scales with N x daemons: large values (the eclipse templates once used 64-192) multiply per-daemon thread state across every node. `0` = monerod sizes its pools from the host core count (256 here) in every node |
| `native_preemption: true` (default false) | Shadow preempts long-running CPU-bound code so other hosts get scheduled | See [Native preemption](#native-preemption) — improves wall perf; breaks strict reproducibility |
| `daemon_defaults.log-level: monitor` (default 1) | Cuts monerod log volume substantially while keeping the lines the live monitor and post-run analyzer parse | See [Tuning monerod log-level](#tuning-monerod-log-level). `log-level: 0` would silence the monitor; `monitor` is the safe perf knob. |
| `shadow_log_level: error` (default warning) | Drops Shadow's own log spam | Lose some Shadow diagnostics |
| `performance.model_unblocked_syscall_latency: false` (default true) | Skips per-syscall sim-time bookkeeping for non-blocking calls | **Don't enable.** See [Modeling syscall latency](#modeling-syscall-latency) — empirically stalls Monerosim runs even at quickstart scale. |
| `run_sim.sh --bootfast` (needs shadowformonero >= v0.2.5) | Every monero process start drops from ~16 to ~0.4 wall-s | None measurable: only a thread that reads the clock more than 10,000 times in a row is charged more. See [Start-up cost](#start-up-cost) |
| `run_sim.sh --allfast` (= `performance.unblocked_vdso_latency: 1 us`) | Same start-up cut | Every clock read in every process charges 1 µs of sim time instead of 10 ns (~0.1 ms per block hop). See [Start-up cost](#start-up-cost) |
| Mount `/tmp` on tmpfs (system-side, not YAML) | LMDB writes go to RAM, not disk | Costs RAM proportional to chain size; for fakechain runs that's small |
| **KSM enabled** (machine-level, plus `scripts/ksm_exec.py` wrapper) | ~10× less RAM per node; the single biggest scale enabler | Needs root once per boot; no wall-time cost measured. See [KSM](#ksm-kernel-same-page-merging) |

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

The mechanism (profiled 2026-10-03, `docs/20261003_startup_cost.md`):
every monero binary (monerod and monero-wallet-rpc) runs a static
initializer before `main()`, `ticks_per_ns = get_ticks_per_ns()` in
`src/common/perf_timer.cpp`, that busy-waits on `steady_clock` until
100 ms have passed. Under Shadow that clock is simulated time, and a
clock read only moves it forward by the modeled per-call latency. With
the modeling off, the loop never sees time pass, so the first daemon
never gets to `main()` and the clock freezes at zero. (An earlier
version of this section blamed a "CPU-bound startup"; that was never
measured, and the profile shows it was this loop.)

This contradicts the earlier guidance in this section that said the
knob was "essentially free for Monero." That guidance was wrong:
Shadow can only advance simulated time when *something* is willing to
block or is charged latency, and this loop does neither without the
modeling.

With the modeling on, the loop still ends only after 100 ms / 10 ns =
10 million clock reads, and with `native_preemption: true` each read
costs ~1.6 µs of real time. That is the ~16-17 wall-seconds every
monero process start costs; see [Start-up cost](#start-up-cost).

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
| `0` | `true` | Fully non-deterministic; every monerod sizes its pools from the host core count -- avoid |
| `2` | `true` | Non-deterministic, small per-node pools (our quickstart and eclipse default) |
| `0` | `false` | Non-deterministic without the throughput win — rarely useful |
| `1` | `false` | Deterministic, slow — pick this for strict reproducibility |
| `1` | `true` | Determinism guarantee is broken; treat as effectively non-deterministic |

If you actually need bit-for-bit reproducibility (e.g., reproducing a
known-good run for a paper), set `process_threads: 1` *and*
`native_preemption: false`. Otherwise leave preemption on.

## Start-up cost

Every monerod and monero-wallet-rpc start used to hold the simulation for
~17 wall-seconds, and the start-time stagger puts starts in a row, so start-up
dominated large runs (a 2232-host run: ~6 wall-hours for the first ~1.1
sim-hours) and did not speed up with more workers. Measured and profiled in
`docs/20261003_startup_cost.md`:

- ~15.5 s: monero's `get_ticks_per_ns()` static initializer busy-waits for
  100 ms of `steady_clock` (see [above](#why-turning-it-off-breaks-monerosim-runs)).
  At Shadow's default `unblocked_vdso_latency` of 10 ns that is 10 million
  clock reads, each ~1.55 µs of real time with `native_preemption: true`.
- ~1.2 s: the RSA-4096 certificate monerod and wallet-rpc generate for RPC SSL.
  Turning it off (`rpc-ssl: disabled`) saves this but breaks wallet sync once
  transactions flow (`docs/20261009_rpc_ssl_off_wallet_stall.md`), so monerosim
  leaves it at the stock `autodetect` (see `docs/CONFIGURATION.md`).
- ~0.3 s: everything else.

Per start on a 70-host test (median, wall-seconds): 17.3 as before, 16.2
with SSL off. Two `run_sim.sh` flags remove the busy-wait cost (explained in
plain language in [`explain_clock_mods.md`](explain_clock_mods.md)):

| Flag | Simulated time a clock read costs | Relay start | Shadow wall (70 hosts) | Normal operation |
|---|---|---|---|---|
| none | 10 ns (Shadow's default) | 16.1 s | 1106 s | as before |
| `--bootfast` | 10 ns, except each read in a row past the 10,000th (no other syscall in between): 1 µs | 0.43 s | 93 s | unchanged: the longest such run in a full quickstart was 371 reads |
| `--allfast` | 1 µs, always | 0.42 s | 93 s | slightly slower in sim time, see below |

```bash
./run_sim.sh --config my.yaml --bootfast
```

`--bootfast` needs shadowformonero >= v0.2.5 (run_sim.sh checks before it
generates anything); `--allfast` works with any Shadow. Both also speed up
daemons that restart mid-run (turnover, upgrade phases), which pay the start
cost again on every restart. The flags override these config knobs, which you
can also set directly (the scenario parser passes `performance:` through):

```yaml
performance:
  unblocked_vdso_busy_threshold: 10000   # what --bootfast sets
  unblocked_vdso_busy_latency: 1 us
  # unblocked_vdso_latency: 1 us         # what --allfast sets
```

What `--allfast` costs: every clock read in every simulated process charges
1 µs of sim time instead of 10 ns, the same as Shadow already charges for a
non-blocking syscall. Measured over a full quickstart, a monerod reads the
clock 110-180 times per simulated second, about as often as it makes syscalls
Shadow already charges 1 µs for; half its busy periods (from waking up to
blocking again) contain one read and 99.9% at most 31; handling a block gets
0.05-0.1 ms later per hop, against 25-95 ms link latencies. Runs are not
seed-for-seed comparable with runs made without it. `--bootfast` charges
none of this: below 10,000 reads in a row it charges exactly what Shadow
charges without it (verified with a test program reading the clock in fixed
patterns).

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

One documented large-scale exception: from 2k nodes up, the scale ladder
runs **relays** at `daemon_options: log-level: 0` while users and miners
keep `monitor`. At those sizes the relay `net.p2p.msg` firehose dominates
disk (see [Disk is the new ceiling](#disk-is-the-new-ceiling)), and the
rungs are compared on the user+miner observer set only.

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

## Scale limits and the 2026-10 scale ladder

### The old N=1000 "cliff" was a misdiagnosis

Earlier versions of this section capped users at ~600 and warned of a
reliable stall at N=1000 "even with abundant RAM and cores". Two real bugs
produced those freezes, and both are fixed:

- **The agents' blocking `flock`** on the shared transaction ledger hung
  Shadow's worker threads in the kernel (fixed 2026-09-12: lock-free
  per-writer JSONL; the same signature had silently killed at least four
  earlier long runs that were written off as one-offs).
- **Shadow's worker count on 2-socket boxes** counted 64 cores twice
  (core_id repeats per socket), so `parallelism: 0` under-planned workers
  and concurrent runs stacked on the same CPUs (fixed 2026-10-02:
  run_sim.sh computes a CPU plan and tasksets each run).

With those, plus `--bootfast`, `monitor`-level logging, and KSM, the scale
ladder (2026-10) ran three fully tx-loaded rungs cleanly:

| Rung | Nodes | Wall (16 h sim) | Overall ratio | Peak RAM | User txs (senders) | Tx latency med / max | Peers / node |
|---|---|---|---|---|---|---|---|
| 1k (200u / 800r) | 1,011 | 9.4 h | 1.7 | 98 GB | 18,953 (200/200) | 4.1 / 13.8 s | 86–90 |
| 2k (400u / 1600r) | 2,011 | 20.4 h | 0.78 | 300 GB | 33,586 (400/400) | 3.8 / 13.8 s | 94–96 |
| 3k (600u / 2400r) | 3,011 | 36.5 h | 0.44 | 438 GB | 39,969 (600/600) | 4.2 / 14.6 s | 91–93 |

All three: native mining (5 × 20 h/s), 5k-node CAIDA GML topology, RPC SSL
`autodetect`, KSM on, 128 workers, users+miners at `monitor` and relays at
`0`, 1 tx/user/300 s. **0 failed processes on every rung; every distinct tx
hash reached every observer node** (205/405/605 observers). Configs:
`test_configs/scale_ladder/`; run data:
`/mnt/remote_spinny/20261007_monerosim_scale_ladder/` (the 1k/2k entries
without `_ssl` are an earlier RPC-SSL-off attempt whose transaction load
collapsed — see `docs/20261009_rpc_ssl_off_wallet_stall.md` — treat them as
under-loaded).

The headline: **network behavior is flat across a 3× node count.** Tx
latency moves ~0.1 s at the median, propagation reaches everyone, peer
counts hold ~90. Wall time grows ×~2 per rung because the relay work grows
as txs × nodes (quadratic when users scale with nodes); Shadow's event
throughput did not degrade (515k → 687k events/wall-s, 1k → 3k). RAM is
sub-linear with KSM. See "Transaction rate vs block capacity" below. There is no observed algorithmic wall at 3k
nodes; the binding constraints are now, in order: **disk (log volume),
wall time, then RAM without KSM**.

The same envelope holds for **synthetic (legacy) mining**: the fixes that
unlocked the ladder — the flock hang, the worker count, `--bootfast`, the
RPC SSL stall — are all mining-mode-independent, and per-monerod memory
measured the same ~295 MB/daemon class on the 2,232-host eclipse
reproduction (1,210 actual monerods; see the KSM section for the
host-count trap). That config's 2026-10 rerun completed 50 sim-hours in
15.6 wall-hours with `--bootfast` and no KSM at 374 GB peak.

### Transaction rate vs block capacity

Keep the network-wide tx rate under the chain's capacity unless congestion
is what you are studying. At low (default) fees blocks stay near the
300 kB penalty-free minimum — about 150 txs, so **~4,500 txs per sim-hour
at 2-min blocks**. The dynamic block size barely moves: miners only
overshoot the median by what fees pay for (~1.5 kB here), so the median
grew ~1.5% over 4 sim-hours of full blocks.

The 3k rung (600 users × 12 tx/h ≈ 5,300/sim-h sent) crossed that line:
from sim ~13 h the mempool backlog grew to ~3,000 txs and wall time per
sim-hour doubled (190 → 368 min) at a constant send rate, because every
node holds and re-announces every pending tx. Below capacity (1k rung)
pace is flat. Analysis: `docs/20261012_3k_slowdown_decomposition.md`.

### Turnover catch-up is serial

With turnover on, every returning daemon downloads and fully verifies the
blocks it missed before it relays anything again (stock monerod ignores
new txs while syncing). In simulated time that takes only the network
round trips, because CPU costs no sim time. In wall time it is one host's
crypto on one Shadow worker, and every other host waits at the round
barrier, so all 128 workers show ~100% CPU, mostly kernel spin-waiting.
Cost per restart ≈ txs missed while offline × verification cost, so it grows
with downtime × tx rate.

Measured on the full mainnet replica (2026-10-13; 1,107 hosts, 1 h on /
1 h off turnover, ~500 restarts per sim-hour, ~850 txs per sim-hour):
pace 2.2× before user activity, 0.25–0.4× after. The busiest host in every
sampled minute was a daemon restarted 1–5 sim-minutes earlier. Example:
relay-320 caught up 55 blocks / ~1,600 txs in 25 sim-s, using ~60 native
CPU-s. The managed processes together used only ~2–3% of the box's CPU.
The 118-host smoke run (8× fewer restarts, ~30× fewer txs per catch-up)
ran at 7.4×. Budget wall time for turnover runs from downtime × tx rate,
not from node count alone.

### Disk is the new ceiling

~97% of run bytes are `net.p2p.msg` transaction-relay lines, and their
volume scales as txs × nodes (peers/node itself grows with network size).
In the final sim hours — when every user is transacting at full rate —
the 3k rung burned 25–30 GB/h and the ratio dropped to ~0.19 (the
"peak-log phase"; decomposed and design options in
`docs/20261011_peak_log_phase_design_notes.md`). From 2k up, the ladder
runs relays at `daemon_options: log-level: 0` while users+miners keep
`monitor` — that is the documented mitigation, trading relay-node log
detail for ~5× less disk. Budget roughly 130 GB (1k) / 180 GB (2k) /
365 GB (3k) of run storage with that split, and pre-flight against the
measured *peak* write rate, not the average — a full disk hangs Shadow
silently rather than failing loudly.

### KSM (kernel same-page merging)

The single biggest RAM lever. Each monerod holds ~300 MB of private
anonymous memory, of which one 256 MB region is the RandomX light
(verification) cache — byte-identical in every node because the genesis
seed is shared. KSM deduplicates those pages across processes:

- **~10× less RAM.** Measured on the 1k rung at sim 4 h: 30 GB with KSM
  vs 305 GB without (~30 MB/node vs ~305). Full 16 h tx-loaded runs
  peaked at 98 / 300 / 438 GB for 1k / 2k / 3k — i.e. ~100–150 MB/node
  once unmergeable per-node state (blockchain, peerlists) has grown.
- **No wall-time cost measured** (wall to sim 4 h: 1.39 h vs 1.42 h); the
  `ksmd` kernel thread used ~0.4 core.
- **The ~10× should apply to synthetic-mining runs too.** Correctly
  re-measured, the 2,232-host eclipse reproduction (synthetic mining) ran
  **1,210 actual monerods** — the other ~1,050 hosts are lightweight
  fake-peer/injector agents with no daemon — at **~295 MB/daemon**, the
  same class as native's ~305. The RandomX cache region is evidently
  allocated there as well (the preloaded chain carries real PoW that gets
  verified at startup), so `--ksm` should merge it just the same —
  unmeasured for synthetic, but the per-daemon sizes match. Two traps this
  corrects: divide the daemon bucket by the **daemon count**, not the
  process count (an earlier pass here divided by all 2,276 processes,
  fake peers included, and wrongly read ~156 MB/daemon); and in
  eclipse-style configs, extrapolate scale by daemons — the 1,000
  fake-peer hosts cost ~26 GB in total, nearly free.

KSM needs two things, both of which must be true:

1. **Root enables it on the machine.** It is compiled into the kernel but
   off by default, and it resets at every reboot:

   ```bash
   sudo sh -c 'echo 10000 > /sys/kernel/mm/ksm/pages_to_scan && echo 20 > /sys/kernel/mm/ksm/sleep_millisecs && echo 1 > /sys/kernel/mm/ksm/run'
   ```

   The scan rate is `pages_to_scan` × 4 KB per `sleep_millisecs`;
   10000 pages every 20 ms (~2 GB/s) keeps merging ahead of thousands of
   node starts. The defaults are far too slow, and "enabled" alone is not
   enough: kernel 100 pages / 20 ms is ~20 MB/s, and Ubuntu 6.8 ships
   `sleep_millisecs=200`, so even `pages_to_scan=10000` gives only ~200 MB/s
   there. Without root you can still *check* it:
   `scripts/ksm_check.sh` reports run, scan rate, and the fix, including a
   `/etc/tmpfiles.d` entry that reapplies the settings at every boot.
   `run_sim.sh --ksm` runs it in preflight and `setup.sh` at the end.

2. **Every process opts in.** Merging is per-process opt-in via
   `prctl(PR_SET_MEMORY_MERGE, 1)`, which survives `execve` and `fork` —
   so `run_sim.sh --ksm` re-execs itself through the unprivileged wrapper
   `scripts/ksm_exec.py`, covering Shadow and everything it starts:

   ```bash
   ./run_sim.sh --config my.yaml --bootfast --ksm
   ```

   The preflight reports whether the kernel side is enabled and scanning
   fast enough (and prints the fix if not); the run proceeds either way, just with
   ~10× the RAM. The wrapper can also be used directly for other commands.

Per-machine guidance, updated for measured per-node costs (full-load
figures assume a 16 h tx-loaded run; boot/light phases are ~3–5× cheaper
per node):

| RAM | Nodes without KSM (~320 MB/node) | Nodes with KSM, full load (~100–150 MB/node) | With KSM, light/short runs |
|---|---|---|---|
| 16 GB | ~40 | ~100–140 | ~300–400 |
| 32 GB | ~85 | ~250–300 | ~600–800 |
| 64 GB | ~180 | ~500–600 | ~1,200 |
| 128 GB | ~380 | ~1,000–1,200 | ~2,500 |
| 1 TB | ~2,800 | ~6,000+ (disk and wall time bind first) | — |

Cores add a second cap: `3 × cores` simulated hosts. Shadow's per-host
scheduler degrades past ~3 hosts per physical core; the 3k rung ran
3,011 hosts on 128 physical cores (~24:1) with preemption on, at the
cost of the peak-phase slowdown above.

### Auto-config caps predate the ladder

The guardrail table the auto-config uses (and its `N > cap` warnings) was
calibrated before the flock and worker-count fixes and before KSM; it is
conservative by roughly an order of magnitude on machines where KSM is
enabled. Treat its warnings as advisory, not as measured limits — the
ladder numbers above are the current measured capability.

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

(The cap that produced that warning predates the flock/worker-count fixes
and KSM; see [Auto-config caps predate the
ladder](#auto-config-caps-predate-the-ladder).)

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
| r7525 | 256 | 1 TB | 1000 | timeout | 0.06× | **"the cliff" — later shown to be the flock hang + worker-count bug, not a Shadow limit; see [above](#the-old-n1000-cliff-was-a-misdiagnosis)** |
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
