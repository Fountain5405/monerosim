# shadowformonero: Rebase onto Upstream Shadow v3.3.0

**Date:** 2026-07-14
**Result:** fork tag **v0.2.0** = upstream **v3.3.0** + 22 commits
(`f08eeb1f8`, branch `sync-v3.3.0`). Upstream ctest **216/216**; monerosim
smoke gates **19/19 at both scales**; **perf-neutral** (as predicted from the
changelog — see §4).

## 1. Why and where the fork stood

The fork (previously tag v0.1.0, binary `Shadow 3.2.0 — 404d301dd`) was based
on an upstream `main` snapshot from 2025-07-02 — 524 commits past v3.2.0 and
**33 commits before the v3.3.0 release**. Upstream had moved 256 commits ahead,
containing exactly one release (v3.3.0, 2025-10-16). Notably, the fork's base
already included upstream's big performance work (payload-copy elimination
#3492, Rust interface #3480, `--native-preemption-enabled` #3520), so **no
perf gain was expected from the sync** — the value is currency, upstream
bugfixes (bandwidth #3699, rlimit #3682), and determinism hardening (cpuid
trapping #3619, deterministic FD ordering #3614, `/proc` work).

Rebase target: the **tested v3.3.0 release**, not main tip (which adds only
dependency bumps + 3 patch fixes past v3.3.0).

## 2. The Monero patch set (what had to survive)

19 commits, +1895/−100, all documented in the fork's `shadowformonero.md`:
LMDB syscall no-ops (`mlock*`/`msync`), credential-tracking syscalls
(`setpriority`, `setres*id`), real `sendmmsg`, libunbound LD_PRELOAD
interposition (+667 LOC) with `getaddrinfo` fallback, SO_REUSEADDR + lazy
CLOSED-socket cleanup (daemon phase-switch rebind), no-op socket options
(TCP_NODELAY/IP_TOS/TCP_KEEP*), additive `--dns-server` config knob,
determinism workarounds (injector priority, `_exit` after SIGKILL).

## 3. Rebase outcome

- **Clean picks:** 14 of 19. Real conflicts in `resource.rs` and
  `handler/mod.rs` (upstream added native `getrlimit`/`setrlimit` handling
  next to the fork's additions) — resolved keeping both.
- **Dropped as upstream-superseded:** the `test_unistd` `.to_owned()` fix
  (identical change already in v3.3.0).
- **Deliberate deviation:** restored upstream's rate-limited
  `log_once_per_value_at_level!` unsupported-syscall logging (the fork had
  replaced it with an unthrottled `log::warn!`). Expect quieter logs.
- **API adaptation:** v3.3.0 added a fourth `associate_socket()` caller
  (accept-path child registration, shadow#3563) that needed the fork's
  `reuseaddr` parameter threaded through (`6168f4335`).
- **Pre-existing fork bug found and fixed** (`6d34f160a`): RefCell
  double-borrow panic ("already mutably borrowed") in new-TCP
  `listen`/`connect` `associate_fn` closures under SO_REUSEADDR — present and
  empirically reproduced on fork `main`; it went unnoticed because no test
  exercised the path until v3.3.0 *added*
  `test_tcp_reuse_addr_with_orphaned_child_socket`. The fix mirrors the
  fork's own correct `legacy_tcp.rs` pattern.
- CLI help golden files regenerated for `--dns-server` (`f08eeb1f8`).
- Flagged for later cleanup: three WIP-ish fork commits (shim_sys.c
  local-bypass trio) picked as-is; deserve a squash + real message someday.

## 4. Validation and A/B performance data

Baseline ("before") runs on the v0.1.0 build, quiet box, 2026-07-12/14;
"after" runs on `v3.3.0-22-gf08eeb1f8`, same box, same day, back-to-back.
All rows are in `tests/baselines/*_run_history.csv`.

| Gate | v0.1.0 fork | v3.3.0-22 sync | Verdict |
|---|---|---|---|
| Upstream ctest | n/a (pre-fix state: 19 fails) | **216/216** | ✅ |
| quickstart (15 nodes, 6h sim) | 939–940s wall, 19/19 | **892s, 19/19** | ✅ ~5% faster (within 889–940s historical band) |
| quickstart results | height 129, 168/137 tx | **bit-identical** | determinism preserved |
| refactor_gate (511 nodes, 8h sim) | 5447s wall, 19/19 | **5386s, 19/19** | ✅ ~1% (noise) |
| refactor_gate results | 1546 tx, h185, 8 alerts | 1543 tx, h185, 8 alerts | tiny seed-level shift, within all assertions |

**Perf verdict: neutral**, exactly as the release-note analysis predicted.
Treat this table as the regression reference for future Shadow bumps.

## 5. Integration

- Fork tag **v0.2.0** on `sync-v3.3.0` (`f08eeb1f8`).
- `SHADOWFORMONERO_REF` bumped v0.1.0 → v0.2.0 in `setup.sh` and `update.sh`
  (kept in lock-step by comment contract).
- Installed binary: `~/.monerosim/bin/shadow` → `Shadow 3.3.0 —
  v3.3.0-22-gf08eeb1f8` (rpath `$ORIGIN/../lib`, self-contained).
- **Rollback:** `tar xzf ~/.monerosim/shadow-v0.1.0-404d301dd.backup.tar.gz
  -C ~/.monerosim` restores the previous binary + shim libs in seconds.
- setup.sh's version-stamp guard will self-heal on the next full setup run
  (rebuilds the sibling checkout at the new pin and rewrites the stamp).

## 6. Follow-ups

- ✅ Fork `main` force-moved to the rebased history (old history preserved at
  `archive/main-pre-v3.3.0`); the borrow-panic fix now lives on `main`.
- ✅ The "WIP trio" (localhost fast-path) was investigated: its functional
  part was already reverted during the sync (`a7949246f`); the dead
  stragglers (an unreferenced `is_localhost_addr` carrying a latent, never-fired
  IPv6 over-read) were removed in **fork v0.2.1** (`6f9605fdf`). Pin bumped
  v0.2.0 → v0.2.1 accordingly.
- Four benign `unused_mut` warnings in fork code (`resource.rs:208-210`,
  `socket.rs:1182`) — trivial `cargo fix` fodder, still open.

## 7. Addendum — v0.2.1 (2026-07-14)

Behavior-neutral cleanup on top of v0.2.0: removed the dead localhost
fast-path shim stragglers from `src/lib/shim/shim_sys.c` (see §6). Shim
rebuilds clean; no re-validation needed (dead-code removal, nothing called
it). Installed binary + sibling checkout advanced to v0.2.1.
