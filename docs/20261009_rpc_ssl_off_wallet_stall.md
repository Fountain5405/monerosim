# RPC SSL off → wallets stop syncing after the first transaction burst

**Date:** 2026-10-09 · **Status:** cause *narrowed*, exact Shadow mechanism **not established** ·
**Nothing has been fixed.** This is an investigation write-up for review.

## 1. Summary

- Since commit `c77fe308` (2026-10-03) monerosim defaults to `--rpc-ssl=disabled` on monerod and
  `--rpc-ssl=disabled --daemon-ssl=disabled` on monero-wallet-rpc (saves an RSA-4096 certificate
  generation per process start: 17.31 → 16.19 wall-s per relay start, −7.5 % Shadow wall on a 70-host run).
- With plain-HTTP RPC, once the chain carries real transaction traffic, a wallet's `/getblocks.bin`
  reply (from its own monerod) grows past ~128 KiB and **never arrives**. The wallet gives up after
  its 210 s timeout (`Unexpected recv fail`), retries, and fails again. User transaction rate decays
  to a trickle, so scale tests are silently under-loaded.
- **Turning RPC SSL back on (`rpc-ssl: autodetect`, `daemon-ssl: autodetect`) removes the problem
  completely** in a controlled A/B: 0 wallet failures vs 4,300 / 2,432 on 200 wallets, and 3,027 vs
  1,157 / 2,066 transactions (§3).
- The same large-single-write limit is already documented for `get_peer_list`
  (`docs/PEERLIST_DUMP_PATCH.md` §2). This is the same phenomenon showing up on a path (wallet sync)
  that every transaction-bearing scenario depends on.
- Why it went unnoticed: quickstart/smoke-size runs never produce a reply over ~128 KiB, and the
  c77fe308 validation (smoke test, 19 PASS) was at that size.

**Not known:** which line of Shadow's simulated TCP (or epoll) loses the wake-up. §5 lists the
evidence for and against each candidate and the cheapest experiments to discriminate them.

## 2. What the failure looks like

Per-wallet log (`shadow.data/hosts/user-006/monero-wallet-rpc.*.stdout`, SSL-off reproducer):

```
05:22:42.495  Refresh done, blocks received: 0 ...        <- normal 20 s refresh loop
05:26:32.495  E Unexpected recv fail                      <- 230 s later (20 s + 210 s timeout)
05:26:32.495  I Failed to invoke http request to /getblocks.bin
05:26:32.495  W ... no_connection_to_daemon, request = getblocks.bin
05:26:32.495  I Another try pull_blocks (try_count=0)...
```

The wallet's own monerod (same host, reached over the host's simulated IP) logs
`POST /getblocks.bin` / `calling /getblocks.bin` for every retry, i.e. the **request arrives and the
daemon builds a reply; the reply bytes do not complete**. The daemon log shows one such request about
every 220 s for the rest of the run (06:50:54, 06:54:34, 06:58:14 … in the sampled wallet).

Related, already-measured data point from the peer-list work (`PEERLIST_DUMP_PATCH.md`): a 663 KB
`get_peer_list` reply delivers exactly **130,907 body bytes** (+ ~165 B of HTTP headers = 131,072 =
128 KiB) over the sim IP and then the connection is closed by epee's send watchdog; over 127.0.0.1
the client gets one 65,536-byte chunk and then nothing. Replies ≲ 54 KB always work.

## 3. Evidence

### 3.1 Controlled A/B (200 users + 5 miners, no relays, 7 h sim, native mining, 5k GML)

Configs differ **only** in the SSL lines (`diff ~/scale_ladder/diag/burst_200u.yaml
~/scale_ladder/diag/burst_200u_ssl.yaml`); the effective args were confirmed in each run's
`shadow_agents.yaml` (`--rpc-ssl=disabled` vs `--rpc-ssl=autodetect`).

| Run (archived_runs/…) | SSL | `--bootfast` | user txs | `Unexpected recv fail` (200 wallets) | wallets with ≥1 fail |
|---|---|---|---|---|---|
| `20261008_102515_diag_burst_nofast` | off | no  | 2,066 | 2,432 | 200 |
| `20261008_102509_diag_burst_bootfast` | off | yes | 1,157 | 4,300 | 200 |
| `20261008_120318_diag_burst_ssl` | **autodetect** | yes | **3,027** | **0** | 0 |

Transactions per 30-min of sim time (registry timestamps; the load starts at sim 5.25 h):

| window starting | SSL off (nofast) | SSL on |
|---|---|---|
| 5.0 h | 538 | 465 |
| 5.5 h | 833 | 813 |
| 6.0 h | 404 | 836 |
| 6.5 h | 243 | 858 |

Both runs match through the first burst; then SSL-off **decays** (833 → 404 → 243) while SSL-on holds
steady. Note the 3,027 is the *seven-hour* total for a deliberately short test; the SSL-off runs
differ in wall-clock behaviour too (the A/B is deterministic in sim terms, not in wall terms).

`--bootfast` is **not** the cause: it stalls with and without it (the bootfast run is in fact worse,
but that is within what I would expect from run-to-run variation, and is not interpreted here).

### 3.2 Scale ladder (SSL off vs on, same configs apart from SSL)

| Rung | SSL off: user txs | SSL on: user txs |
|---|---|---|
| 1k (200u / 800r) | 2,685 | 18,953 |
| 2k (400u / 1600r) | 1,635 (users 265–400 never sent) | in progress |

The SSL-off ladder results (`/mnt/remote_spinny/20261007_monerosim_scale_ladder/20261007_120455_*`,
`…20261008_024930_*`) are therefore **under-loaded and should not be used for scale conclusions**;
their wall times are optimistic by roughly 2×. Caveat: the ladder wallets run at `log-level 0`,
which suppresses the `Unexpected recv fail` line, so for the ladder the evidence is the transaction
collapse, not the error count (the error counts come from the 200-user reproducer, wallet level 1).

## 4. Why the failure is self-reinforcing (inferred, not measured in the sim)

wallet2's refresh requests blocks from its last synced height. A failed `getblocks.bin` leaves the
wallet further behind, so the next reply is *larger*, and therefore more likely to exceed the
threshold again. Hence a wallet that crosses the threshold once stays stuck. I have **not** measured
the reply sizes inside the simulation (monerod logs at `monitor` level do not record them); this is
reasoning from wallet2's behaviour plus the observation that the failure counts per wallet keep
climbing and tx sending never recovers.

## 5. The Shadow mechanism — what is and is not known

Established earlier (PEERLIST_DUMP_PATCH.md, two independent experiments):
- cutoff is deterministic, not random; independent of interface (sim IP and 127.0.0.1 both stall);
- reply is built correctly by monerod (`Content-Length` right); bytes simply stop flowing;
- epee sends P2P messages in 32 KiB chunks (`abstract_tcp_server2.inl`, `CHUNK_SIZE`), RPC HTTP
  responses as a single `async_write` — P2P payloads far larger than 128 KiB work on the same network.

New observations from reading `sibling_repos/shadowformonero/src/main/host/descriptor/tcp.c` and
`main/core/definitions.h` (default `use_new_tcp: false`, i.e. this legacy C TCP is in use):

1. **The cutoff equals Shadow's default send buffer**: `CONFIG_SEND_BUFFER_SIZE 131072` (128 KiB).
   130,907 + ~165 = 131,072. This points at "first `send()` accepts 128 KiB, the rest needs a
   *writable again* wake-up that never comes" (the Shadow issue #3274 hypothesis in the earlier doc).
   **Counter-evidence:** the earlier experiment that pinned `--socket-send-buffer`/`--socket-recv-buffer`
   to 4 MiB reported a byte-for-byte identical cutoff. Either that setting did not reach this socket
   (not verified: effective buffer sizes were not read back) or the 128 KiB match is a coincidence.
   Resolving this is the single most valuable next check.
2. **There is no zero-window probe / persist timer in tcp.c** (`grep -in "persist\|zero.window\|probe"`
   finds only a commented-out `tcpi_probes`). If the receiver's window reaches 0, the only thing that
   restarts the sender is the single window-update ACK sent from `_tcp_sendWindowUpdate`, which carries
   the source comment `// XXX we may be in trouble if this packet gets dropped`. A lost/ignored update
   is a permanent stall.
3. The sender accepts a pure window update only if `ack == lastAcknowledgment && window > prevWin`, or
   `ack > lastAcknowledgment && window != prevWin` (`_tcp_ackProcessing`, `isValidWindow`). A window
   update that arrives with an ack number the sender considers stale, or equal window, is ignored.
   I could not construct from reading alone a concrete interleaving where that happens on a loopback-
   style (lossless) path, so this is a candidate, not a finding.
4. `_tcp_updateReceiveWindow` computes the window in **packets** (`space / MSS`) from
   `legacysocket_getInputBufferSpace` (the in-source comment says the unordered-buffer-aware variant
   "causes throughput problems"), so the advertised window can disagree with what `_tcp_dataProcessing`
   will actually accept (`packetFits` uses the stricter variant).

Candidate causes, ranked by my current belief (all unconfirmed):
- (a) lost writable wake-up after a *partial* `send()` (epoll edge not re-delivered) — fits the 128 KiB
  number; contradicted by the 4 MiB experiment unless that experiment was ineffective;
- (b) lost / ignored receiver window-update ACK, with no persist timer to recover — fits "bytes simply
  stop flowing" with no error until an application timeout;
- (c) the window/`packetFits` inconsistency in item 4.

Why TLS avoids it (**inference**): with SSL, epee/asio writes in ≤16 KiB TLS records, each a separate
small `send()`; a single huge partial write never occurs. This does not by itself explain why filling
the 128 KiB buffer via many small writes is safe while one big write is not, which is a further hint
that the failure is specific to the *partial-write-then-wait* path of (a).

### Experiments that would settle it (not run — the box is busy with the 2k rung)
1. One wallet + one monerod, serve a 1 MiB reply, Shadow `log_level: trace` for just that host pair;
   read whether `_tcp_sendWindowUpdate` fires, whether the sender processes it, and whether EPOLLOUT is
   delivered after the partial send.
2. Run the same with Shadow's `use_new_tcp: true` (Rust TCP). If it passes, the bug is in the legacy
   C path; the fix is then a config choice or a port of the missing behaviour.
3. Read back effective send/receive buffer sizes on the stalled socket to explain the 4 MiB result.
4. Python/C micro-test inside Shadow (no monero): `send()` 1 MiB over a socket pair, reader reads
   slowly. This isolates it from epee/asio entirely and is a minimal upstream bug report.

## 6. Blast radius

Any plain-HTTP RPC reply over ~128 KiB under Shadow stalls: wallet `getblocks.bin` (the case here),
`get_peer_list` (known), and in practice `simulation-monitor`'s status polling, which hangs from the
same cause (the monitor's summary numbers are stale in all runs I looked at; unconfirmed per-call). P2P
traffic and TLS-wrapped RPC are unaffected. Deterministic, so results are *reproducibly wrong*, not
noisy — which is why it looked like a scale limit.

## 7. Options (not acted on — for the reviewers)

| Option | Cost | Notes |
|---|---|---|
| Restore `rpc-ssl: autodetect` / `daemon-ssl: autodetect` as default | ≈ +1.1 wall-s per process start (c77fe308 figure, +6.9 %); one config/default change in `src/process/wallet.rs`, `src/agent/user_agents.rs`, goldens | Fully verified by the A/B above. Does not fix `get_peer_list` for non-SSL probes. |
| Per-scenario opt-in only (keep default off, document) | none | Leaves the trap for everyone who scales up; the ladder shows it is silent. |
| Fix Shadow's TCP | unknown until §5 experiments | The right fix; benefits all plain-HTTP paths and the simulation monitor. |
| Chunk RPC replies in monerod (like P2P) | monerod patch to keep alive | Works around Shadow instead of fixing it; touches the node binary. |

## 8. Reproduction and data locations

- Reproducer configs: `~/scale_ladder/diag/burst_200u.yaml` (SSL off), `burst_200u_ssl.yaml` (SSL on);
  run dirs are under `archived_runs/` as in §3.1 (local, will be moved to `/mnt/remote_spinny`).
- Ladder data and analysis: `/mnt/remote_spinny/20261007_monerosim_scale_ladder/`;
  analysis outputs `~/scale_ladder/analysis/{1k,2k,1k_ssl}/`.
- Ladder configs (SSL on explicitly): `test_configs/scale_ladder/` (commit `3682a85b`).
- Counting failures: `grep -ac 'Unexpected recv fail' <run>/shadow.data/hosts/user-*/monero-wallet-rpc*.stdout`
  (needs wallet `log-level` ≥ 1). Counting txs: `cat <run>/transaction_registry/transactions/user-*.jsonl | wc -l`.
