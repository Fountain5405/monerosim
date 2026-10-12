# Peak-log phase: costs and design options (not implemented)

**Date:** 2026-10-11 · **Status:** discussion notes + a decision; nothing implemented.
**Context:** the 3k scale-ladder rung (`archived_runs/20261009_211808_scale_ladder_3k_ssl`).

## The problem

Late in a tx-loaded run, when all users are transacting at full rate, ~97% of run bytes are
`net.p2p.msg` transaction-relay lines, and their volume scales as **txs × nodes × peers** — with
peers/node itself growing with network size (~56 at 12 h → ~95 at 15 h on the 3k rung). Measured on
the 3k rung: disk burn 25–30 GB/h during the final sim hours, and the sim clock slows to
~11 sim-seconds per wall-minute. Three separate costs hide under this "peak-log phase":

1. **Disk capacity** — 25–30 GB/h of relay lines. Raw *bandwidth* is trivial (~7 MB/s sustained);
   this is a capacity and headroom problem, not a throughput wall.
2. **Write mechanics** — ~2.4k daemons each appending small lines to their own files, interleaved
   with LMDB writes/fsyncs: page-cache dirty pressure and writeback interference. A blocked write
   deschedules the writing process (same hazard class as the old blocking-flock bug, via the kernel).
3. **Simulated work + in-sim logging cost** — probably the dominant part of the slowdown. The log
   volume is a *symptom*: each relayed tx fans out to ~90 peers and every hop is a simulated event
   (packet, scheduling, verification, mempool insert). Each log line also costs in-sim CPU and a
   modeled syscall latency inside the daemon. The clock would slow substantially even with logging
   off; the correlation with log volume is partly common cause, not pure causation.

Un-tested check worth doing someday: a short A/B with everything at log-level 0 through the peak
phase. Expectation: pace recovers 20–40%, not 100%.

## Decision (2026-10-11, user)

- **Keep the all-encompassing data-gathering ability.** Full `monitor`-level logs stay the primary
  observation channel — the per-peer relay lines feed `prop_delta`, `conn_matrix`, peer graphs,
  fan-out analyses. We do not give that up for performance.
- **The observer-cohort idea (full logs on a fixed stratified subset, everyone else at log-level 0)
  is a LAST RESORT only.** It is the no-patch way to cap volume at O(txs × const), but it costs the
  network-wide per-peer view. Revisit only if the mechanics fixes below demonstrably fail at scale.
- **A tx-observation sidecar patch (peerlist-dump-pattern: nodes append `(sim_time, txid)` on first
  sight to a per-node file) was considered and declined for now.** Rationale: unlike the peerlist
  patch — where the data was *physically unreachable* (RPC stalls in Shadow TCP, not in logs) —
  first-seen tx data already flows through the logs. The sidecar is merely a cheaper channel, which
  is a weak justification for growing the monerod patch stack (rebase surface on every pin bump,
  behavior-risk audit burden, and it would *lose* the per-peer lines that `conn_matrix` needs).
  It also is not sim-free: it is still a file write from inside the simulated process through the
  shim. Its one real advantage is asymptotic — ~50–90× fewer writes at any scale — which may become
  forced at 5k+ nodes.

## Preferred direction: fix the write mechanics (zero patch surface)

Ordered by preference; none implemented yet:

1. **Rotation + out-of-band compress-and-ship.** Set monerod's `max-log-file-size` (currently 0 =
   unlimited) so each node rotates; an *out-of-sim* zstd tailer compresses rotated segments
   (repetitive text, expect 20–30×) and ships them off-box. The compressor living outside the sim
   avoids any flock-class blocking hazard. Ship, don't delete — prop analysis needs full history.
2. **Log flush buffering** in easylogging: fewer, bigger `write()` syscalls per daemon; also fewer
   modeled syscall latencies charged to sim time.
3. **Device isolation** when the planned enterprise U.2 SSD arrives: logs on one device, LMDB on
   the other, so writeback stalls can't interfere with chain-data fsyncs.
4. **tmpfs staging** with an async mover (we already use tmpfs as a safe win; combined with
   compression a small one holds the whole peak phase).

## Back-pocket ideas (ranked), with revisit triggers

- **Deterministic txid-hash sampling of relay lines** (log a relay line only if `hash(txid) % N == 0`):
  unbiased latency percentiles, loses per-tx tails and small-sample resolution. Needs a patch or
  log filter; cheaper and narrower than the sidecar.
- **Compact relay-line format**: constant factor (~2–3×), boring but real.
- **Observer-cohort cap** (the last resort above).
- **Tx-observation sidecar** (declined above; becomes justified if a rung's needs physically outgrow
  what logs can carry, not just expensively).
- **Peak-phase profiling**: check whether the 128 Shadow workers are CPU-saturated at peak; if not,
  find the serial bottleneck (candidate: the single shared shadow-logger thread that funnels all
  process stdout).

**Concrete revisit triggers** (from the 2026-10-11 discussion): re-open this doc when a rung's
relay-log volume (compressed) exceeds what local disk + shipping can absorb across a run, or when
peak-phase sim:wall drops below what rungs are tolerable despite the mechanics fixes. At 3k the
mechanics path is expected to suffice; 5k+ is where the asymptotic term starts to bite.

## Guardrails regardless of direction

- Feed the measured 25–30 GB/h peak rate back into run_sim's pre-flight disk estimate (the 3k
  estimate of 640 GB is trending low against ~750+ actual).
- A clean auto-stop at a free-space threshold (`kill -TERM` our Shadow PID while there is still
  room): a gracefully truncated run is recoverable; ENOSPC hangs Shadow silently and loses
  everything (see the 2026-10-03 incident).
- The scale-ladder watcher already trips LOW_DISK at 60 GB free.

## Operational note (related)

On 2026-10-11, nine superseded local runs (~33.7 GB) were moved to
`/mnt/remote_spinny/20261011_local_run_moves/` (verified: 0 rsync dry-run diffs, equal file counts)
and deleted locally, to give the 3k rung disk headroom through its peak-log phase. The eclipse 50 h
reproduction stays local (no confirmed spinny copy).
