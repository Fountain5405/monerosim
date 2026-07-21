# The Intermittent wallet-rpc Crash: Root Cause

**Date:** 2026-07-17
**Status:** RESOLVED — fixed by bumping monero v0.18.1.0 → v0.18.5.1
(pinned in `monero.pin`, commit 48a34bf1); validated 2026-07-20/21 with 12/12
clean gdb-instrumented solo runs (§5.1).
**TL;DR:** the rare `monero-wallet-rpc` crash that intermittently fails
`refactor_gate` (exit 1, "1 managed process in unexpected final state") is a
**monero v0.18.1.0 wallet bug**: an allocation inside EasyLogging++'s log
dispatch throws `std::bad_alloc` during `wallet2::refresh()`'s routine
"Refresh done" log line, inside the implicitly-`noexcept` `el::base::Writer`
destructor → `std::terminate` → SIGABRT. On a ~25 MB process on a 1 TB box,
`bad_alloc` means a **pathological allocation size — i.e. heap corruption
upstream** in the refresh path, which also explains the SIGSEGV flavor seen
on 2026-07-14. Not shim code, not fork code, not monerosim code.

## 1. Symptom and history

- One managed process — almost always a `monero-wallet-rpc`, once a `bash` —
  dies mid-run; Shadow reports `unexpected final state`, run exits 1 while
  every health metric passes. Sim *data* is unaffected (the other ~505
  agents complete normally).
- Observed rate: **4 crashes in 16 solo refactor_gate runs (~1 in 4)**
  across 2026-07-14 → 07-17, plus 2 wallet + 1 bash instances across 46
  older archives.
- Both kill flavors observed at the same site: `Signaled(11)` SIGSEGV
  (2026-07-14, user-090) and `Signaled(6)` SIGABRT (3×, 2026-07-16/17,
  user-069/user-037/user-060) — the classic signature of memory corruption
  (wild pointer → SEGV; corrupted allocation size → `bad_alloc` → abort).

## 2. The capture

gdb attached to every wallet (see §4), breakpoints on the shim's two fatal
funnels. Captured 2026-07-17 04:36, iter 5, `user-060`, sim time ~05:00:

```
#12 abort()
#15 __cxa_call_terminate                             ← exception escaped noexcept
#18 _Unwind_Resume
#19 el::base::Writer::triggerDispatch() [clone .cold] ← EasyLogging++ threw
#20 el::base::Writer::processDispatch()
#21 el::base::Writer::~Writer()                      ← noexcept destructor
#22 tools::wallet2::refresh(...)                     ← the 20-second refresh tick
#23 wallet_rpc_server::run() idle-timer lambda
#27 epee boosted_tcp_server worker thread
```

Victim stderr (the smoking gun):

```
terminate called after throwing an instance of 'std::bad_alloc'
  what():  std::bad_alloc
```

Victim stdout ends with the routine 20-second cadence:
`I Refresh done, blocks received: 1, balance (all accounts): 10.0 ...` —
then death on the next tick's log write. The 2026-07-14 SIGSEGV also died on
a refresh tick (sim 06:23:52, 20 s after its last logged refresh), so both
flavors sit on the same path.

**Interpretation.** `wallet2::refresh()` logs its result; EasyLogging++'s
dispatch allocates while formatting/writing; the allocation request is
absurd (or the heap metadata is trashed) → `bad_alloc`; it propagates out of
`~Writer()` which is `noexcept` → `std::terminate` → SIGABRT. When the
corruption instead lands on a pointer, the same path (or its neighborhood)
segfaults. The corruption's *origin* is upstream in the refresh/RPC path
(monero v0.18.1.0 is from 2022; upstream fixed multiple wallet races since).

## 3. Why this took a hunt (findings that outlived it)

1. **The crash is not deterministic-per-(binary, seed, config).** A byte-identical
   rerun (same fork binary v0.2.1, seed 12345, sha256-identical generated
   `shadow_agents.yaml`) of the 07-14 crash run passed clean. Shadow
   serializes syscalls, not userspace thread interleaving — this is a real
   thread-timing race, so replay can't summon it; only repeated draws can.
2. **Core dumps do not work under Shadow.** The shim traps *every* SIGSEGV
   (it emulates `rdtsc` via `PR_TSC_SIGSEGV`) and routes real faults to
   `die_with_fatal_signal()`, which re-raises and then `_exit()`s — the
   kernel's core-dump default never runs. Proof: a broken run with 692
   genuine monerod SIGSEGVs produced zero cores despite
   `ulimit -c unlimited` + a writable `kernel.core_pattern`. The
   `docs/debugging.md` "generate a core file" recipe upstream inherits is a
   dead end for SIGSEGV under the shim.
3. **Concurrent monerosim instances self-destruct via `/tmp` collision**
   (separate finding): monerod data dirs live at `/tmp/monero-<hostname>`,
   a namespace shared across instances. Two concurrent runs make each
   `miner-001` open the same LMDB → `mdb_txn_begin` = EAGAIN → init throws →
   monero's error path SIGSEGVs in `mdb_txn_abort` via the
   `boost::thread_specific_ptr<mdb_threadinfo>` deleter during
   `BlockchainLMDB::close()` (captured 3×, byte-identical). **Consequence:
   parallel runs on one box are invalid** — worth documenting or fixing via
   run-id-namespaced dirs (`/tmp/monero-<runid>-<host>`).
   **FIXED 2026-07-21:** run_sim.sh now namespaces each run under
   `/tmp/monerosim-<runid>/`; concurrent runs (one per checkout) are
   supported. See `docs/20260721_per_run_tmp_namespacing.md`.

## 4. The capture kit (reusable; archived in basement)

`~/basement_monerosim/20260717_wallet_crash_hunt/kit/`:

- **`allow_ptrace.c`** — LD_PRELOAD whose constructor calls
  `prctl(PR_SET_PTRACER, PR_SET_PTRACER_ANY)`: gdb can attach to managed
  processes without sudo despite Yama `ptrace_scope=1`, scoped to opted-in
  processes only (shared-box-friendly). Shadow *merges* user `LD_PRELOAD`
  with its shim. Optional `PTRACE_WAIT_SPIN=<iters>` busy-spins (~1e9/s,
  pure userspace so the sim stalls harmlessly) for race-free attach to
  processes that crash at startup.
- **`capture.gdb`** — `handle SIGSYS/SIGSEGV nostop noprint pass` (the shim
  needs both constantly), breakpoints on the two fatal funnels
  (`shim_handle_hardware_error_signal` for hardware faults,
  `shadow_shim::signals::die_with_fatal_signal` for abort/emulated fatal
  signals), `commands` block prints siginfo + full backtraces only on a real
  fatal event; `handle SIGABRT stop print pass` as a safety net.
- Hunt loops (solo-run iteration with disk guards, victim-evidence
  preservation, lever65-scoped cleanup) and a continuous sweeper that
  attaches gdb to every wallet as it spawns (`TracerPid` dedup).

Hard-won operational notes: `pgrep -x` matches the kernel's 15-char comm —
`monero-wallet-rpc` truncates to `monero-wallet-r` (this bug cost one full
overnight run); `pkill -f <pattern>` can self-match the invoking shell.

## 5. Impact and remediation options

Impact today: ~1 in 4 refactor_gate runs lose one wallet out of 105 and
exit 1; simulation *results* are unaffected; smoke exit-code is flaky.

Options (option 1 was chosen and validated — see §5.1):

1. **Bump monero** to a later v0.18.x (or current) where upstream likely
   fixed the corruption. Correct fix; heavy validation cost (new binaries =
   new deterministic traces; baselines, goldens, and study comparability
   need re-establishing).
2. **Tolerate with annotation**: teach `smoke_assertions.py` that ≤1
   wallet-rpc `Signaled(6|11)` death is a known-issue WARN (annotated with a
   pointer to this doc), not a FAIL. Cheap, honest, keeps the gate green for
   the failure mode we understand; risks masking a *new* crash type.
3. **Report upstream**: v0.18.1.0 is ancient; likely answer is "update".
   Low effort, low expected return.
4. **Do nothing**: keep treating exit-1-with-healthy-metrics as a manual
   judgment call.

### 5.1 Resolution and validation (2026-07-20/21)

Option 1 executed: monero bumped v0.18.1.0 → **v0.18.5.1** (latest stable),
pinned via the new `monero.pin` and enforced by the `run_sim.sh` preflight
(commit 48a34bf1). The v0.18.5.x line carries wallet2 refresh hardening
(upstream PRs #10773/#10776) and a txpool use-after-free fix (#10710);
EasyLogging++ itself is unchanged, so validation had to be empirical.

Validation protocol: 12 consecutive **solo** `refactor_gate`-config runs
(the only valid draw type — see §3 on the /tmp collision), every wallet-rpc
under a gdb with the same REAL-FAULT-HIT-gated capture script that caught
the original crash, plus a continuous sweeper for late-spawned processes.

Result: **12/12 clean** — zero gdb captures, zero `Signaled` processes in
any `shadow.log`, all sims completed. At the old ~1/4-per-run crash rate,
12 clean runs would occur with probability ~0.75¹² ≈ 3% — the bump fixed
it with ~97% confidence. Post-bump gates: quickstart smoke 19/19 PASS
(exit 0), cargo goldens PASS, both pin preflights MATCH.

Old v0.18.1.0 binaries preserved in
`~/basement_monerosim/20260720_monero_v0.18.1.0_binaries_pre_bump/`.

## 6. Evidence

- Capture + victim files + crashing run's `shadow.log`:
  `~/basement_monerosim/20260717_wallet_crash_hunt/capture/`
- Uncovered-crash logs (SIGABRT duality proof):
  `.../run1_pgrepbug_evidence/`
- LMDB /tmp-collision backtraces: `.../monerod_lmdb_captures/`
- 2026-07-14 SIGSEGV run archive: `archived_runs/20260714_181025_refactor_gate/`
- Related docs: `docs/20260715_dns_shim_audit_and_fixes.md` (the audit that
  cleared the DNS shim), `docs/20260711_code_quality_review.md`.
