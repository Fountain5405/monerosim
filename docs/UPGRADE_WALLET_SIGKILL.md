# Upgrade-Phase Wallet Shutdown: Why SIGKILL, and What We Lose

## TL;DR

Non-final wallet phases in upgrade scenarios are stopped with **SIGKILL**, not SIGTERM. This bypasses an intermittent monero-wallet-rpc deadlock that left v1 wallets bound to port 18082 and prevented v2 wallets from binding. SIGKILL'd wallet state is recoverable from chain on the next phase, so the cost is acceptable for our simulation use case. A SIGTERM-then-SIGKILL escalation wrapper is documented below as the next step if it ever becomes necessary.

The relevant code is in `src/agent/user_agents.rs` (phase wallet construction) and `src/shadow/types.rs` (`ShadowProcess.shutdown_signal`). The behavior was introduced in commit `eceb2b73`.

---

## The Problem We Were Solving

Upgrade scenarios run a node through two binary phases — `monerod` / `monero-wallet-rpc` (v1) for the first half of the simulation, then `monerod-v2` / `monero-wallet-rpc-v2` for the second. Each v1 process has a `shutdown_time` after which Shadow sends a signal so the next phase can take over the data directory and TCP ports.

Run `archived_runs/20260430_203141_20260430_large_upgrade` (1011 nodes, 72h sim time) showed every single user's v2 wallet failing to bind:

```
Failed to bind IPv4: bind: Address already in use
Error starting server: Failed to bind IPv4 (set to required)
Failed to initialize wallet RPC server
```

The diagnostic chain that followed traced through three distinct issues, each masking the next.

### Issue 1: bash wrapper absorbing SIGTERM

Daemon and wallet processes were launched via `bash -c '...'` wrappers. The daemon used `bash -c 'exec monerod ...'` (the `exec` replaces bash with monerod, so SIGTERM goes directly to the binary). The wallet used `bash -c 'monero-wallet-rpc ...'` — **without** `exec`. Shadow's SIGTERM at `shutdown_time` went to the bash parent, which exited immediately, leaving the wallet orphaned and still holding port 18082.

Fix: commit `ed5ef048` ("De-bash daemon and wallet launches"). `ShadowProcess.args` switched from `String` to a `ProcessArgs` enum mirroring Shadow's own (Str | List), and daemon/wallet processes now launch directly with their args as a YAML list — no bash wrapper, SIGTERM reaches the binary directly.

After this fix, `archived_runs/20260501_165857_upgrade_smoke` showed 2 of 3 user upgrades succeeding cleanly. user-01 still failed with the same bind error, but for a different reason.

### Issue 2: Inadequate gap between phase 0 stop and phase 1 start

Hypothesis at the time: maybe SIGTERM just needs more wall time to take effect under Shadow's cooperative scheduling. Default gap was 30s; bumped to 300s.

Fix: commit `eae0562c` ("Default phase restart gap to 5 min").

This was based on a wrong diagnosis. Shadow doesn't escalate `shutdown_signal` to SIGKILL after a timeout — it sends the configured signal once at `shutdown_time` and that's it. If the wallet ignores SIGTERM, it ignores it forever, regardless of gap size. We kept the 5-min default because it's still useful headroom for legitimate slow shutdowns and costs nothing in wall time, but it didn't fix user-01.

### Issue 3: monero-wallet-rpc deadlock during normal operation

The agent log on user-01 in `archived_runs/20260501_174105_upgrade_smoke` told the real story:

| Sim time | Event |
|---|---|
| 05:02:20 | Last successful wallet activity ("Spent money" notification after tx broadcast) |
| 05:07:00 | First agent error: `Read timed out (180s)` on `103.0.0.10:18082` |
| 05:13:30 | Second timeout, agent attempts wallet-connection reset |
| 05:32:30 | shutdown_time fires (sim time 19950s). No visible response in wallet log. |
| 05:37:30 | wallet_1_start (sim time 20250s, +300s gap). v2 fails to bind, port held. |
| 06:30:00 | sim end — v1 wallet StoppedByShadow |

The wallet was already deadlocked **30 sim minutes before shutdown_time**. It was bound to port 18082, accepting TCP connections (so the kernel knew the port was in use), but never responding to RPC. Classic deadlock signature: main RPC thread blocked on a mutex held by another thread.

This matches the pattern called out in `src/process/wallet.rs:41-46`:

> wallet-rpc's background refresh can deadlock against an in-flight transfer when both need the wallet lock and compete for the same threads

The codebase already removed `--max-concurrency` from the wallet to mitigate this (per the same comment), and that does reduce the frequency. But under Shadow's cooperative single-thread-per-host scheduling, the mitigation is incomplete — `archived_runs/20260501_174105_upgrade_smoke` reproduces the deadlock with no `--max-concurrency` set.

Fix: commit `eceb2b73` ("SIGKILL non-final wallet phases"). v1 wallet phases now use `shutdown_signal: SIGKILL`, which the kernel applies unconditionally regardless of the wallet's internal lock state.

`archived_runs/20260501_184741_upgrade_smoke`: exit code 0, 0 failed processes, all three users (including user-01) successfully upgraded.

---

## What We Give Up With SIGKILL

### What's persistent in monero-wallet-rpc

- **`.keys` file** — private spend/view keys, address. Written eagerly when the wallet is created or modified; not touched during normal RPC operation. **Safe under SIGKILL.**
- **Cache file** — tx history, address book, blockchain sync state. Written periodically (auto-save) and on graceful shutdown. Monero uses atomic rename for cache writes, so partial writes don't leave a corrupted file — you see either the old or new version.

### What's lost on SIGKILL

- In-memory state since the last auto-save: recent address book entries, freshly-generated subaddresses, sync progress between auto-saves.
- Mid-construction transfers that haven't been broadcast yet.

### Why it doesn't matter for our use case

- Once a transfer is broadcast (the `Spent money` log fires after broadcast), it's in the daemon's mempool and chain. The v2 wallet rescans the chain on first refresh and reconstructs the same view. We verified this in `archived_runs/20260501_184741_upgrade_smoke`: the v2 wallets came up healthy and processed RPC calls (refresh / get_balance / set_daemon visible right up to sim end).
- The simulation is testing the *upgrade mechanism*, not preserving local-only wallet UI state across upgrades. The "chain is canonical, wallet rebuilds" recovery path is exactly what's being exercised.
- The autonomous_miner / regular_user agents we run don't hold sensitive in-memory state that wouldn't be reconstructable from chain.

### Cases where SIGKILL would be problematic

- Future tests that depend on wallet-local state surviving an upgrade (e.g., custom subaddress books, multisig signing rounds in progress, tx-not-yet-broadcast scenarios).
- Real-deployment guidance derived from these simulations — operators shouldn't read "always SIGKILL on upgrade" as best practice; that's specific to our simulation tradeoffs.

---

## The Escalation Wrapper (Documented But Not Implemented)

If a future use case needs graceful-then-forceful shutdown, the systemd `KillMode=mixed` pattern can be implemented with a small bash wrapper. It would replace direct launch only for non-final wallet phases:

```bash
#!/bin/bash
graceful_kill() {
  kill -TERM "$pid" 2>/dev/null
  for _ in $(seq 1 30); do
    kill -0 "$pid" 2>/dev/null || return
    sleep 1
  done
  kill -KILL "$pid" 2>/dev/null
}
trap graceful_kill TERM

/home/.../monero-wallet-rpc "$@" &
pid=$!
wait $pid
```

Shadow sends SIGTERM to bash → bash forwards to wallet → polls 30 sim-seconds → SIGKILLs if still alive. From Shadow's perspective: one process, one shutdown signal (SIGTERM), one final state. The escalation is invisible to Shadow.

Tradeoffs of doing this:
- Brings bash back as parent for v1 phase wallets (we removed bash from daemon and wallet launches in `ed5ef048`). Scope is small — only one bash per phase wallet host, only during the phase 0 → phase 1 transition.
- The wrapper script needs to be generated at config time (similar to the existing python wrapper scripts in `shadow_output/scripts/`), with the wallet path and args interpolated.
- `expected_final_state` becomes ambiguous: clean SIGTERM exit returns 0; SIGKILL escalation returns 137 (128+9). Probably want to set `expected_final_state: any` (Shadow doesn't have this — would need to pick one and tolerate the mismatch warning) or accept whichever path was taken on a per-host basis.

Estimated effort: ~30 minutes if we ever need it. The relevant code paths are `src/agent/user_agents.rs` (phase wallet ShadowProcess construction) and `src/utils/script.rs` (wrapper script generation infrastructure).

---

## Other Things Considered

**Companion `pkill -TERM` Shadow process at T-30s, then SIGKILL via shutdown_signal at T.** Cleaner-looking config than the bash wrapper, but `expected_final_state` gets fiddly: if SIGTERM works, the wallet exits with status 0; if not, the SIGKILL fires. Shadow can't accept "either Exited(0) or Signaled(SIGKILL)" — we'd have to pick one and tolerate spurious end-state mismatch warnings on a fraction of nodes. Worse than the wrapper.

**Patching monero-wallet-rpc to fix the deadlock.** Real fix at the source, but out of scope — the deadlock is in upstream Monero code and would require either patching the lock-acquisition order or rearchitecting the refresh/transfer thread interaction. Worth considering only if monerosim becomes a venue for upstream Monero stability work.

**Switching back to `--max-concurrency=1` on the wallet.** Historically this caused a different (and worse) deadlock per the codebase comment in `src/process/wallet.rs`. Don't.

---

## Reproduction Notes

The deadlock is deterministic with `simulation_seed: 12345` on the upgrade_smoke scenario. user-01 hits it; users 02 and 03 do not. Other seeds may shift which agents are affected. At larger scales, expect a small fraction of users to hit the deadlock in any given run (proportional to "how likely is this user to be transferring near shutdown_time").

**Key runs:**
- `archived_runs/20260430_203141_20260430_large_upgrade` — pre-fix baseline. 1011-node upgrade, every wallet failed to bind (pure bash-wrapper-absorbs-SIGTERM issue).
- `archived_runs/20260501_165857_upgrade_smoke` — post-debash. 2 of 3 succeeded; user-01 hit the deadlock and failed.
- `archived_runs/20260501_174105_upgrade_smoke` — post-gap-bump. Same failure pattern as 20260501_165857_upgrade_smoke; gap bump didn't help because Shadow doesn't escalate SIGTERM.
- `archived_runs/20260501_184741_upgrade_smoke` — post-SIGKILL. Exit code 0, all three upgrades clean.

**Key commits:**
- `ed5ef048` — De-bash daemon and wallet launches; exec into Python from wrappers
- `eae0562c` — Default phase restart gap to 5 min (was 30 s)
- `eceb2b73` — SIGKILL non-final wallet phases to bypass wallet-rpc deadlock
