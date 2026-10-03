# Why a monero process start costs ~17 wall-seconds under Shadow

**Date:** 2026-10-03, measured on a 24-thread box (Ryzen 9 3900X, 12 cores,
31 GB) following `docs/20261003_startup_ssl_runbook.md`.
**Status:** Cause found. RPC SSL is now off by default (saves ~1.1 s per start).
The main cost needs `performance.unblocked_vdso_latency` (new, opt-in), which
cuts a start from 17.3 s to 0.43 s together with SSL off; making it the
default is an open decision (see [Options](#options)).

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
| `performance.unblocked_vdso_latency: 1 us` | 17.3 → 1.7 s (0.43 s with SSL off) | Yes: every clock read in every process charges 1 µs of sim time instead of 10 ns | monerosim config (knob added, opt-in) |
| `performance.unblocked_vdso_latency: 100 ns` | → 1.9 s with SSL off | Yes, 10x less than 1 µs | same |
| Shim: don't toggle the preemption timer for calls the shim answers itself (clock reads), only before an IPC round trip to Shadow | ~3 s with SSL on (arm C is the bound: no toggling at all) → ~0.5-1 s with SSL off, estimated | No for normal code; tight loops of clock reads become preemptible, as intended | shadowformonero |
| Patch `get_ticks_per_ns` to sleep instead of spin | → ~0.3 s | No | monero (only reaches `monerod-sim`; the default `monerod` and wallet-rpc are vanilla) |
| `native_preemption: false` | 3 s | Yes, and wallet-rpc's ring-signature loops can starve their host (`src/shadow/types.rs`) | not a fix |

Fidelity of the vDSO charge: Shadow already charges 1 µs for every
non-blocking real syscall (`unblocked_syscall_latency`). At 1 µs a clock read
costs the same. A real vDSO `clock_gettime` costs 40-400 CPU cycles (Shadow's
own estimate, i.e. ~10-100 ns), so 1 µs overcharges it, but by microseconds
per event, against network latencies of
milliseconds and a 120 s block time. Results will not be seed-for-seed
comparable with earlier runs, which they already are not with
`native_preemption: true` (`docs/CONFIGURATION.md`, Determinism).

Recommendation: set `performance.unblocked_vdso_latency: 1 us` in the eclipse
and other large configs now (or make it the default), and fix the shim's
timer toggling in shadowformonero as the clean long-term fix.

## Expected effect at scale (not measured here)

- ~240-host 1/10-scale eclipse config: start-up phase ~40 wall-min on the
  big box. With E's settings each start drops from ~17 s to under 0.5 s, so
  expect a few minutes. It does not fit this 31 GB box (each monerod holds
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

Profile a whole start: wait for a new monerod PID, then
`perf record -e cpu-clock -F 199 --call-graph dwarf,16384 -t <pid> -- sleep 25`
and `python3 analysis/startup_cost/profile_phases.py perf.data`. Frame-pointer
stacks stop at the shim's signal frames; use DWARF. With
`perf_event_paranoid` 4 (Ubuntu's default) perf needs
`sysctl kernel.perf_event_paranoid=1`.
