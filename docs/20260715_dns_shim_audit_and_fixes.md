# DNS-Shim Forensic Audit + Fixes (fork v0.2.2)

**Date:** 2026-07-15
**Trigger:** the v0.2.1 refactor_gate (511-node) failed one assertion —
`exit_code=1` from a single `monero-wallet-rpc` SIGSEGV — while every health
metric passed. This documents the audit that traced it and the two real,
separate fork bugs the audit surfaced and fixed. Fork tag **v0.2.2**
(`adf69cd34`); `SHADOWFORMONERO_REF` bumped v0.2.1 → v0.2.2.

## 1. The crash is NOT the DNS shim (audit conclusion)

The wallet's last two stderr lines (`ub_ctx_create → ub_ctx_delete`) looked
like a DNS-shim crash but are a red herring — verified:

- **Universal, not a signature.** All 105 wallets print those identical two
  lines (same pointer, Shadow's deterministic layout). It's monero's startup
  self-test `unbound_built_with_threads()` (`util.cpp:438-450`), which leaves
  the shim holding zero state.
- **Crash was 2h42m later** (sim 06:23:52), on the 20-second `wallet2::refresh`
  / `/getblocks.bin` tick — nowhere near the DNS probe. The victim reconnected
  on the same source port as all ~505 prior refreshes, so no `getaddrinfo`
  even ran.
- **Cross-run clincher:** across 46 archived runs, 3 SIGSEGVs — two wallet-rpc
  **and one plain `bash`** (20260418, pre-sync) that never touches libunbound.
  The only shared component is the Shadow **shim/preload core** (310 upstream
  commits vs 2 fork commits for the DNS shim) → likely an **upstream** Shadow
  or monero-v0.18.1.0 wallet bug, not fork code.
- **Pre-existing** (bash crash April, wallet June, both pre-sync); the project
  already has `prune_archives.sh crashed_users()` grepping for these. **Not a
  regression** from the v3.3.0 sync or the cleanup.

**Status:** logged as a known, rare (~1/few-hundred), non-data-affecting,
deterministic-per-(binary,seed) crash. Real-fix path = same-seed replay with
core dumps → backtrace → probable upstream report. Tracked separately; not
fixed here.

## 2. What the audit *did* fix — two real fork bugs

### F1 — memory-safety in monerod (`unbound_interpose.c`)

The shim's `ub_resolve` returned `UB_SYNTAX`/`UB_NOMEM` **without setting
`*result`**. Real libunbound sets `*result = NULL` first, and callers rely on
it: monero's `DNSResolver::get_record` (`dns_utils.cpp:304`) declares an
*uninitialized* `ub_result *result;` and registers a scope-exit that
**unconditionally** calls `ub_resolve_free(result)`. On any early-error return,
that freed uninitialized stack garbage → heap corruption. Allocation-failure-
gated (rare), affects monerod (wallets never resolve).

**Fix:** set `*result = NULL` at `ub_resolve` entry, before any early return
(after the null-check on `result` itself). The shim's `ub_resolve_free`
NULL-guards, so the freed-NULL path is a clean no-op. Audited all other
`ub_*` out-params — only `ub_resolve` had the defect.

### F2 — simulation escape / determinism (`shim_api_addrinfo.c`)

`shim_api_getaddrinfo` runs under `ExecutionContext::Shadow` (`shim/src/lib.rs`),
where non-Shadow syscalls execute **natively**. Its DNS-over-TCP fallback thus
opened a **real host TCP connection** toward the *simulated* DNS server IP
(a routable public range) — leaking SYNs onto the real network, stalling the
worker ~2s/lookup, then failing over to Shadow's hostname DB. Confirmed: the
sim's DNS server received **zero** TCP queries in 8h. For a tool whose value is
reproducible, isolated simulation, this is a fidelity/determinism defect.

**Fix (Option B, behavior-preserving):** the native-TCP DNS attempt is removed;
`getaddrinfo` goes straight to Shadow's internal hostname DB — which is what
every lookup already fell back to. No `socket/connect/send/recv` toward a
simulated address remains. **Preserved:** the libunbound UDP path (Application
context, correctly simulated — monero's actual DNS mechanism), the hostname-DB
and `/etc/hosts` fallbacks.

**Follow-up (Option A, deferred):** to make `--dns-server` *functional* in-sim,
route the query through emulated syscalls (the `shim_api_getifaddrs` pattern),
after confirming the sim DNS host serves TCP:53. Noted in-code at the call site.

## 3. Validation

`./setup build` clean (0 warnings on touched files). Fixes reviewed line-by-line
(guard ordering; `ub_resolve_free` NULL-safety; zero remaining callers of the
disabled DNS-query function). **quickstart smoke 19/19, exit 0** on the v0.2.2
binary — normal operation (peer connectivity, block/tx propagation, all of which
need name resolution) unaffected. F1's path is allocation-failure-gated and F2
is behavior-preserving, so the crash-prone refactor_gate wasn't required to gate
these; a full 511-node run would still occasionally hit the *unrelated*
pre-existing shim-core SIGSEGV (§1).

## 4. Other latent DNS-shim findings (audited, not fixed)

Lower severity, logged for a future hardening pass: NULL-unwrap on
`shimshmem_getDnsServer(shim_hostSharedMem())` when host shmem is uninitialized;
`ub_ctx_delete` bare `free()` with no guard vs concurrent `ub_resolve` readers;
`_dns_skip_name` compression-pointer loop with no jump cap (hang); unchecked
mallocs in `_getaddrinfo_append*`; missing `ub_ctx_set_event`/`ub_resolve_event`
interposition (future type-confusion tripwire if a caller ever uses them).
