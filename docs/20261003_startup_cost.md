# Why a monero process start costs ~17 wall-seconds under Shadow

**Date:** 2026-10-03, measured on a 24-thread box (Ryzen 9 3900X, 12 cores,
31 GB) following `docs/20261003_startup_ssl_runbook.md`.
**Status:** Cause found and fixed behind flags. RPC SSL is now off by default
(saves ~1.1 s per start). `run_sim.sh --bootfast` (shadowformonero v0.2.5)
cuts a start from ~16 s to 0.43 s without changing how normal operation is
charged; `run_sim.sh --allfast` does the same by charging every clock read
1 µs. Neither is the default. Plain-language explanation of both:
[`explain_clock_mods.md`](explain_clock_mods.md).

## TL;DR

The ~17 s per daemon start is **not** the RPC SSL certificate. 92% of it is a
clock-calibration busy-wait that every monero binary runs before `main()`:

```cpp
// monero src/common/perf_timer.cpp (v0.18.5.1)
uint64_t ticks_per_ns = get_ticks_per_ns();   // namespace scope: static init

uint64_t get_ticks_per_ns() {
  uint64_t t0 = epee::misc_utils::get_ns_count(), t1;
  ...
  while (1) {
    t1 = epee::misc_utils::get_ns_count();
    if (t1 - t0 > 1*100000000) break; // work 0.1 seconds
  }
  ...
}
```

Under Shadow `steady_clock` is simulated time. A clock read moves it forward
only by `unblocked_vdso_latency` (Shadow default **10 ns**), so the loop needs
100 ms / 10 ns = **10 million** reads. With `native_preemption: true` each read
costs ~1.55 µs of real time, because every entry into the shim disables the
preemption timer (`setitimer` + `rt_sigprocmask`) and every return re-enables
it. That's 4 real syscalls per emulated `clock_gettime`. 10 M x 1.55 µs is about
15.5 s. RSA-4096 keygen for the RPC certificate adds ~1.2 s and the rest of the
start ~0.3 s.

The start-time stagger then puts these starts strictly one after another,
which is why startup dominates wall time and does not speed up with more
workers.

| Arm (70 hosts, 60 relays 5 s apart) | Relay start, median | Last relay ready | Shadow wall |
|---|---|---|---|
| A: as before (SSL autodetect) | 17.31 s | 1194 s | 1229 s |
| B: RPC SSL disabled | 16.19 s | 1100 s | 1137 s |
| C: `native_preemption: false` (diagnostic only) | 3.06 s | 237 s | 277 s |
| D: `unblocked_vdso_latency: 1 us` | 1.69 s | 159 s | 185 s |
| **E: `unblocked_vdso_latency: 1 us` + RPC SSL disabled** | **0.43 s** | **63 s** | **93 s** |
| F: `unblocked_vdso_latency: 100 ns` + RPC SSL disabled | 1.89 s | 155 s | 185 s |

The ~270 sim-seconds after the last relay start take 26-40 wall-s in every
arm. The changes act on start-up only.

## Answers to the runbook's questions

1. **Where do the ~17 wall-seconds go?** On the daemon's main thread (perf,
   `cpu-clock`, DWARF stacks, one complete start of `relay-018` in arm A,
   17.1 s of CPU):

   | Phase | CPU | Share |
   |---|---|---|
   | `_GLOBAL__sub_I_perf_timer.cpp` → `tools::get_ticks_per_ns()` (before `main`) | 15.7 s | 92% |
   | `core_rpc_server::init` → `create_rsa_ssl_certificate` | 1.3 s | 8% |
   | everything else (LMDB, genesis, p2p init) | 0.1 s | <1% |

   Inside the busy-wait (`relay-009`, 8 s window): 27% kernel time under the
   shim's `setitimer`, 25% kernel time under its `rt_sigprocmask`, 23% shim
   code, 21% libcrypto (this window overlapped the keygen). `/proc` showed the
   main thread at 0.32 cores user + 0.69 cores system.
2. **Does disabling RPC SSL cut the per-start time?** Yes, by ~1.1 s (17.31 →
   16.19 s, -6.5%; Shadow wall -7.5%). That is the keygen, not the 17 s. Once
   the busy-wait is fixed it matters more: 1.69 → 0.43 s (D → E).
3. **Default changed?** RPC SSL is now disabled by default for monerod and
   monero-wallet-rpc (commit on this branch). The real cost is the busy-wait;
   the fix is below.

### The open puzzle, resolved

The runbook noted only ~1 ms of simulated time between `Generating SSL
certificate` and `core RPC server initialized OK`, although 17 s of CPU should
have shown up as ~1.7 sim-s under native preemption. Two reasons:

- 15.7 of the 17 s are spent before `main()`, so before the first log line.
  The daemon logs its first line exactly 100 ms of sim time after its
  scheduled start (e.g. relay-060: start 325.0 s, first line 325.100 s).
- The preemption timer (`ITIMER_VIRTUAL`, 100 ms) is reset on every shim entry
  (`ExecutionContext::enter_without_restorer` → `preempt::disable/enable`,
  `src/lib/shim/src/lib.rs` in shadowformonero). Code that reads the clock or
  calls getrandom often never accumulates 100 ms of uninterrupted CPU, so it
  is never preempted and sim time hardly moves.

### Commit 339e9431, corrected

339e9431 explained the sim-time-0 freeze with `model_unblocked_syscall_latency:
false` as a "CPU-bound" start-up. It is this loop: with latency modeling off a
clock read advances nothing, so `get_ticks_per_ns` spins forever in the first
daemon. `docs/PERFORMANCE_AND_SCALE.md` is corrected.

## Cost model

All six arms fit, within ~0.4 s:

```
per start ≈ (0.1 s / unblocked_vdso_latency) × 1.55 µs    busy-wait
          + 1.2 s if RPC SSL is on                         RSA-4096 keygen
          + 0.3 s                                          the rest
```

A: 15.5 + 1.2 + 0.3 = 17.0 (measured 17.3). B: 15.8 (16.2). D: 0.16 + 1.2 + 0.3
= 1.66 (1.69). E: 0.46 (0.43). F: 1.55 + 0.3 = 1.85 (1.89).

The 1.55 µs per read is this box with preemption on. With preemption off (arm
C) the busy-wait took ~1.5 s, i.e. ~0.15 µs per read: the timer toggling is
~90% of the per-read cost.

## Measurements

### Native baseline (step 1), this box

monerod v0.18.5.1, OpenSSL 3.0.13, three runs each. Times include the 0.1 s
busy-wait, which costs real time natively too.

| | default | `--rpc-ssl disabled` |
|---|---|---|
| monerod: start → `core RPC server initialized OK` | 1.13, 3.01, 1.43 s (1 cert line each) | 0.14, 0.14, 0.14 s (0) |
| wallet-rpc `--offline`: start → RPC port accepts | 0.91, 1.65, 1.14 s (1 cert line) | 0.11 x 3 (0) |
| wallet-rpc with a local daemon: start → RPC port accepts | 1.38, 0.80, 1.50 s (1) | 0.11 x 3 (0; daemon and `--daemon-ssl` off too) |
| `openssl genrsa 4096` | 0.67 - 1.96 s (6 runs) | |
| `openssl ecparam -name secp256k1 -genkey` | <0.01 s | |

The keygen costs about the same inside and outside Shadow (~1.1-1.3 s); it was
never the 17 s.

### Shadow arms (step 2)

Scenario as in the runbook: 3 miners with wallets (0-2 s), 60 daemon-only
relays from 30 s at a 5 s stagger, 6 seeds, DNS server, `stop_time: 10m`,
`native_preemption: true`, `process_threads: 2`, 12 Shadow workers. Each arm
ran alone. "Relay start" is the wall time from the monerod process appearing
in `/proc` to `core RPC server started ok` in its log (0.1 s polling).
"Busy median" is the runbook's `busy_tracker.py` (1 s resolution).

| Arm | Run ID | Relay start median / mean / max | Last relay ready | Busy median | Shadow wall |
|---|---|---|---|---|---|
| A | `20261003_045535_startup_ssl_default` | 17.31 / 17.52 / 21.30 s | 1194 s | 16 s | 1229 s |
| B | `20261003_051605_startup_ssl_disabled` | 16.19 / 16.21 / 16.42 s | 1100 s | 15 s | 1137 s |
| C | `20261003_053504_startup_ssl_nopreempt` | 3.06 / 3.25 / 6.95 s | 237 s | 2 s | 277 s |
| D | `20261003_053943_startup_ssl_vdso1us` | 1.69 / 1.84 / 3.68 s | 159 s | 1 s | 185 s |
| E | `20261003_054249_startup_ssl_vdso1us_nossl` | 0.43 / 0.43 / 0.53 s | 63 s | <1 s | 93 s |
| F | `20261003_054423_startup_ssl_vdso100ns_nossl` | 1.89 / 1.86 / 1.90 s | 155 s | 1 s | 185 s |

An earlier round (tracker only) agreed: A 1230 s (`20261003_040225_...`), B
1138 s, C 277 s, D 184 s, E 92 s. Its arm A carried a few short perf samples;
the clean repeat matched it to the second.

Host RNGs are seeded per host, so a host draws the same RSA primes in every
arm: the slow keygens are the same relays each time (relay-048 and -038 are
the slowest in A and C).

### Wallets

monero-wallet-rpc runs the same static initializer, so it pays the same
busy-wait. In arm E it still burned ~3 s of CPU at start, 2.3 s of it in RSA
keygen called from the **MMS client**: `on_create_wallet` / `on_open_wallet` →
`mms::message_transporter::set_options` → `http_simple_client::set_server(...,
ssl_options_t = autodetect)` → `ssl_options_t::create_context()`, which
generates a certificate whenever no key file is given, client or server. No
wallet-rpc option reaches it. This accounts for the repeated `Generating SSL
certificate` lines per wallet start noted in
`docs/20260724_cuprate_wallet_rpc.md`. It costs ~1.1-1.3 s per wallet create
or open (1.28 s and 1.07 s in the profile); removing it would need a monero
patch. The `set_daemon` RPC that agents call at run time
(`agents/monero_rpc.py`) sends no `ssl_support`, so it autodetects and also
builds an SSL context; passing `ssl_support: disabled` there would skip it.

## Options

| Fix | Per start | Changes simulated timing? | Where |
|---|---|---|---|
| RPC SSL off (done, default) | -1.1 s | No (P2P unaffected; RPC answers in plaintext) | monerosim |
| `--allfast` (= `performance.unblocked_vdso_latency: 1 us`) | 17.3 → 1.7 s (0.43 s with SSL off) | Yes: every clock read in every process charges 1 µs of sim time instead of 10 ns | monerosim (done, opt-in) |
| `--bootfast`: charge 1 µs only after 10,000 clock reads in a row with no other syscall | → 0.43 s with SSL off | No, below 10,000 in a row | shadowformonero v0.2.5 + monerosim (done, opt-in) |
| `performance.unblocked_vdso_latency: 100 ns` | → 1.9 s with SSL off | Yes, 10x less than 1 µs | same |
| Shim: don't toggle the preemption timer for calls the shim answers itself (clock reads), only before an IPC round trip to Shadow | ~3 s with SSL on (arm C is the bound: no toggling at all) → ~0.5-1 s with SSL off, estimated | No for normal code; tight loops of clock reads become preemptible, as intended | shadowformonero |
| Patch `get_ticks_per_ns` to sleep instead of spin | → ~0.3 s | No | monero (only reaches `monerod-sim`; the default `monerod` and wallet-rpc are vanilla) |
| `native_preemption: false` | 3 s | Yes, and wallet-rpc's ring-signature loops can starve their host (`src/shadow/types.rs`) | not a fix |

A real vDSO `clock_gettime` costs 40-400 CPU cycles (Shadow's own estimate,
i.e. ~10-100 ns), so 1 µs overcharges it. How much that matters depends on how
often processes read the clock, measured next.

### How often a normal run reads the clock

The full 6 h quickstart at default settings (`20261003_110240_clk_quickstart`:
5 miners, 6 seeds, 1 relay, 3 users with transactions from 4 h), with Shadow's
`experimental.strace_logging_mode: standard`. The shim logs every clock read it
answers (`clock_gettime`, `gettimeofday`, `time`) with its simulated time, and
Shadow logs `= <blocked>` where a thread goes to sleep. A **busy period** is a
thread's run from waking up to blocking again: each clock read in it delays the
thread's next action (e.g. relaying a block) by the vDSO charge. Counted by
`analysis/startup_cost/clock_reads.py`, excluding each process's first 2 sim
minutes:

| Process | Clock reads per sim-second | Syscalls Shadow charges 1 µs, per sim-second | Reads per busy period: median / 99.9% / max | Longest run of reads with no other syscall |
|---|---|---|---|---|
| monerod, miners (5) | 127-176 | 116-185 | 1 / ≤31 / 170-362 | 155-347 |
| monerod, seeds (6) | 109-115 | 94-101 | 1 / ≤31 / 106 | 57-73 |
| monerod, relay | 153 | 163 | 1 / ≤31 / 106 | 73 |
| monerod, users (3) | 152-158 | 160-167 | 1 / ≤31 / 387 | 371 |
| monero-wallet-rpc (8) | 49-50 | 20-23 | 4-7 / ≤63 / 501-1161 | 14 |
| Python agents, DNS server | 1-7 | 2-12 | 1 / ≤511 / 480 | 31 |
| start-up busy-wait, per monero process | 10,000,000 in its first 0.1 sim-s | | | 10,000,000 |

- The rate is steady over the run (100-190 reads/s per monerod, creeping up
  as the chain grows; transactions add little). 40 reads/s per monerod come
  from one periodic timer thread.
- Block handling: on seed-001 every busy period of 100+ reads (all 106)
  falls within 1 s of a block being added. Per block, the busiest thread
  reads the clock 54 times (median; p90 60, max 106) on seed-001 and 66
  (median and p90) on relay-001. The 340-390-read busy periods fall in the
  transaction phase on miner and user daemons.

What `unblocked_vdso_latency: 1 us` would change (+0.99 µs per read):

- **Load:** +0.11-0.17 ms of simulated CPU time per simulated second per
  monerod (0.01-0.02%). Shadow already charges 0.09-0.19 ms/s for syscalls, so
  a monerod's modeled CPU time roughly doubles, from tiny to still tiny.
- **Per event:** the median busy period gets 1 µs later, 99.9% of them at
  most 31 µs later, a block's handling 0.05-0.1 ms later per hop, the worst
  monerod busy period 0.38 ms, the worst wallet one 1.15 ms. Link latencies in
  `1200_nodes_caida_with_loops.gml` are 25-95 ms (p10-p90, median 45 ms), so a
  block's extra 0.05-0.1 ms per hop is under 0.5% of one link's delay.

Runs with it are not seed-for-seed comparable with runs without it, which
runs with `native_preemption: true` already are not (`docs/CONFIGURATION.md`,
Determinism): this run and the smoke run `20261003_055721_quickstart` both
reached height 179 with 180 blocks on miner-001, with different hashes.

### Charging more only where it is needed: `--bootfast`

`unblocked_vdso_latency` is global and fixed for a run: Shadow copies it into
each host's shared memory at start and has no way to change it mid-run. But
normal operation never reads the clock more than 371 times in a row without
another syscall, while the start-up busy-wait does it 10,000,000 times.

shadowformonero v0.2.5 adds two options for this:
`experimental.unblocked_vdso_busy_threshold` (default 0 = off) and
`experimental.unblocked_vdso_busy_latency` (default 1 µs). The shim counts
each thread's clock reads in a row; any other syscall resets the count; past
the threshold each read is charged the busy latency. `run_sim.sh --bootfast`
sets them to 10,000 and 1 µs (27x margin over the longest run measured).

A test program reading the clock in fixed patterns under Shadow
(threshold 10,000):

| Pattern | default | `--bootfast` | `--allfast` |
|---|---|---|---|
| 1,001 reads in a row | 10.1 µs | 10.1 µs | 1.0 ms |
| ~10,000 reads in a row | 100 µs | 100 µs | 10 ms |
| 20,001 reads in a row | 201 µs | 10.1 ms | 20 ms |
| 8,001 reads, one other syscall, 8,001 reads | 161.8 µs | 161.8 µs | 16 ms |
| spin until 100 ms has passed | 9,999,909 iterations | 109,899 | 100,000 |

Below the threshold `--bootfast` charges exactly what Shadow charges without
it. On the 70-host test it starts relays as fast as `--allfast` (0.43 vs
0.42 s median, both runs 93 s of Shadow wall time), against 16.14 s and
1106 s with neither flag on the same Shadow build (`20261003_233145_startup_ssl_v025_default`). It also covers daemons
that restart mid-run (turnover, upgrade phases), which otherwise pay the
start cost on every restart.

Smoke test (`quickstart`, 23 monero processes): without flags on v0.2.5,
19/19 and the exact historical outcome (height 179, 191/191 transactions;
`20261003_235204_quickstart`, 734 s). With `--bootfast`: 520-550 s. One run
(`20261004_000442_quickstart_bootfast`) failed 1 of 19 checks: the distributor
agent logged "Read timed out" because miner-004's wallet sent `/get_outs.bin`
to its own daemon, the daemon handled it at once, and the reply never arrived
(the wallet gave up after 210 s; the retry succeeded). That wallet-to-daemon
"Unexpected recv fail" also appears in 12 runs from September on v0.2.4,
without these changes, where it hit the background refresh instead. The
rerun (`20261004_001553_quickstart_bootfast2`) passed 19/19 with the historical outcome.

Recommendation: use `--bootfast` for large runs, where start-up dominates.

### Does `--bootfast` touch anything besides start-up?

The rule applies to every process in the simulation, so every process type
was checked for runs of 10,000+ clock reads with no other syscall (Shadow's
strace logs; `analysis/startup_cost/clock_reads.py --threshold 10000`, which
counts runs exactly as the shim does: `rdtsc` counts as a read, Shadow's own
`shadow_yield` does not end a run). Longest run per process type, outside
each process's first 2 simulated minutes:

| Scenario (run) | monerod | monerod-sim (native mining) | monero-wallet-rpc | Python agents, DNS server |
|---|---|---|---|---|
| quickstart, 6 h, default (`20261003_110240_clk_quickstart`) | 371 | - | 14 | 31 |
| eclipse_inject_smoke, 60 min, `--bootfast` (`20261004_103028_clk_eclipse_inject_bootfast`): miners, benign and attacker relays, target, 2 injectors, eclipse monitor | 137 | - | 12 | 31 |
| selfish_micro, 2 h, `--bootfast` (`20261004_103536_clk_selfish_micro_bootfast`): native mining, selfish miner and bridge agents | 45 | 49 | 6 | 31 |

Runs over 10,000: exactly one per monero process, its start-up loop
(109,903 reads under `--bootfast`), and none anywhere else in any process.
The busiest Python agent (the selfish miner, 264 reads per simulated second)
never read the clock more than 31 times in a row.

The Python agents read the clock explicitly in 69 places
(`grep -rn "time\.time\|time\.monotonic\|datetime\.now" agents/`). Every
loop among them sleeps, waits on `select`, makes an RPC call or takes a file
lock on each pass (`monero_rpc.py` `wait_until_ready`, `base_agent.py`
`wait_for_height` / `wait_for_wallet_sync`, `autonomous_miner.py`'s wallet
poll, `file_locking.py`, `eclipse_injector.py`'s event loop); the rest are
timestamps and cache-TTL checks. None spins on the clock. Python's own
implicit reads (log timestamps, socket and `select` timeouts) sit next to
the syscalls they time.

Not checked: cuprated (not installed on this box), runs with thousands of
hosts, and transaction loads heavier than the quickstart's. If a run ever did
pass 10,000 reads in a row: a loop waiting for a time to pass would end at
the same simulated time after fewer iterations; a loop doing work with a clock
read per step would take 1 µs more simulated time per read past 10,000.

## Expected effect at scale (not measured here)

- ~240-host 1/10-scale eclipse config: start-up phase ~40 wall-min on the
  big box. With `--bootfast` (or arm E's settings) each start drops from ~17 s
  to under 0.5 s, so expect a few minutes. It does not fit this 31 GB box (each monerod holds
  ~267 MB, mostly the RandomX light cache), so measure it on the big box.
- 2232-host run: 2,220 relay starts x ~17 s ≈ 10 h → x ~0.4-0.5 s ≈ 15-20 min
  of start cost, if nothing else limits the phase.

## Reproduce

`analysis/startup_cost/` has the scenario (arm A; its header lists the
variants), `busy_tracker.py` (the runbook's tracker), `start_watcher.py`
(per-daemon start time) and `profile_phases.py`. Per arm:

```bash
python3 scripts/generate_config.py --from analysis/startup_cost/startup_cost.scenario.yaml -o arm.yaml
./run_sim.sh --config arm.yaml --name startup_arm &
# once `pgrep -x shadow` finds it:
date +%s.%N > shadow_start.txt
python3 analysis/startup_cost/start_watcher.py /tmp/monerosim-<run_id> shadow_start.txt > starts.txt &
python3 analysis/startup_cost/busy_tracker.py > tracker.txt
```

Variants go in the scenario's `general:` (`native_preemption: false`) or in a
top-level block that the scenario parser passes through:

```yaml
performance:
  unblocked_vdso_latency: 1 us      # arms D, E (100 ns: F)
```

Clock reads: run with Shadow's `experimental.strace_logging_mode: standard`
(monerosim does not pass it through; the measurement above added it to the
generated Shadow config with a temporary patch), then
`python3 analysis/startup_cost/clock_reads.py <run>/shadow.data/hosts --skip 120`
(`--glob 'monero-wallet-rpc.*.strace'` for wallets). The 6 h quickstart wrote
21 GB of strace files, half of it the start-up busy-waits; analysis takes
about a minute.

Profile a whole start: wait for a new monerod PID, then
`perf record -e cpu-clock -F 199 --call-graph dwarf,16384 -t <pid> -- sleep 25`
and `python3 analysis/startup_cost/profile_phases.py perf.data`. Frame-pointer
stacks stop at the shim's signal frames; use DWARF. With
`perf_event_paranoid` 4 (Ubuntu's default) perf needs
`sysctl kernel.perf_event_paranoid=1`.
