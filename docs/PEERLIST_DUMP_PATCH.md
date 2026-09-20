# Why the target node needs a monerod peer-list-dump patch

**Status:** 2026-09-16. Rationale + design for a measurement-only, flag-gated
monerod patch used by exactly one node (the eclipse target, relay-4000) in the
Nyx reproduction. Written so a reviewer can see *why* modifying monerod is
necessary and that the change **cannot bias the experiment**.

TL;DR: The paper's two headline defence-side metrics (B and OR) require the
target's **full per-entry** white+gray peer list, sampled over time. Under the
Shadow network simulator that list **cannot be pulled over the RPC** — a large
un-chunked HTTP response stalls in Shadow's simulated TCP (verified two
independent ways, and corroborated against Shadow's own bug tracker). Every
non-invasive workaround was tried and falsified. The only reliable path is to
have monerod **serialize its own peer list to a file** on the shared filesystem,
out-of-band of the simulated network. The patch is observation-only: it changes
how we *read* the target's state, not how the target *behaves*.

---

## Status: VERIFIED WORKING (2026-09-16)

Implemented and confirmed on the fast repro
(`test_configs/eclipse_socketbuf_verify.scenario.yaml`, 54 hosts, ~3 min sim).
The patched monerod (flag-gated; now vendored as
`patches/monero-sim-peerlist-dump.patch` and built into `monerod-hf` by
`./setup.sh --hardfork`, base version unchanged v0.18.5.1) wrote `<relay-4000 data-dir>/fake/peerlist_dump.jsonl`:
**23 timestamped snapshots**, `gray_n` climbing 0 → 776 → 2525 → 4511 → **5000**
and holding; the largest snapshot carried a full **5000-entry gray list + 12
white** with declared counts equal to the actual parsed array lengths (no
truncation) and every line valid JSON. Each entry is `["<ip>:<port>",
<last_seen>]` — exactly the per-entry data B and OR require. The file path
completely bypasses the Shadow TCP limit that defeated the RPC. **Blocker
resolved.**

### Where the dump ends up, and how to get it back

monerod resolves the relative `--peerlist-dump-file` path against the chain
subdirectory, so a fakechain node writes it to
`<daemon-data-dir>/monero-<node>/fake/peerlist_dump.jsonl` — one level deeper
than `bitmonero.log`.

`archive_daemon_logs()` in `run_sim.sh` moves every dump it finds into
`archived_runs/<run_id>/daemon_logs/<node>/peerlist_dump.jsonl`, beside that
node's `bitmonero.log`. Run the analysis straight off the archive:

```bash
python analysis/eclipse/analyze_peerlist_dumps.py archived_runs/<run_id>
```

The analyser also still accepts a raw run directory (`/tmp/monerosim-<run_id>`
or a preserved raw-data tree on the backup volume), where the dumps sit in
`<node>/fake/` and the registry in `shared/`. It picks the layout itself.

> **Before 2026-09-20 the dumps were not archived at all.** Only
> `bitmonero.log` and the cuprate logs were collected, and
> `cleanup_tmp_monero --full` then deleted the per-run daemon directories — so
> a normally-archived run lost its dumps. Runs from the eclipse study survive
> only because that workflow used `--no-clean --no-archive` and kept everything
> in the raw `/tmp` tree. `--no-archive` still skips the collection step: pair
> it with `--no-clean` (as the eclipse recipe does) or the dumps are lost.

---

## 1. What the experiment must measure, and why sizes aren't enough

The paper ("Are Unreachable Nodes Truly Safe? Fully Eclipsing Monero's P2P
Network", Shi et al.) reports the eclipse's progress with per-entry peer-list
metrics on the victim:

- **B** — the number of **benign** records remaining in the victim's **gray
  list** over time. The paper's Nyx run shows B collapse from ~717 to ~2 as
  attacker/trash records evict honest ones.
- **OR (occupation rate)** — the **fraction** of the victim's white/gray list
  that is **attacker-controlled** (paper: benign nodes' whitelist OR → ~98.5%).

Both are **compositional**: they depend on *which* IPs are in the list, not how
many. To compute them we must classify every entry as attacker / benign /
seed / miner / target, using the run's `agent_registry.json`. That requires the
**full white_list + gray_list with each entry's IP:port** — up to 1000 + 5000 ≈
6000 records, ~650 KB of JSON at saturation.

What we *can* already capture cheaply and reliably over RPC (small responses,
work fine):
- **CTR** (connection-takeover rate) from `get_connections` — the ~12 active
  outbound peers.
- **peerlist sizes** from `get_info` — `white_peerlist_size` /
  `grey_peerlist_size` (counts only, no IPs).

Sizes and the active-connection set are **not** sufficient for B or OR — those
need the per-entry breakdown. That per-entry list is the one thing we cannot get.

## 2. The blocker: Shadow will not deliver the large RPC response

`get_peer_list` returns the full list, but under Shadow the response is
truncated/stalled every time the list is large. This was reproduced
deterministically (54-host smoke, gray driven to the 5000 cap in ~3.5 min sim;
`test_configs/eclipse_socketbuf_verify.scenario.yaml`) and diagnosed in two
rounds (full detail in the basement copy `investigation/20260916_problem.txt`, EMPIRICAL UPDATE #1 and #2):

- **Symptom:** small responses (≤ ~54 KB) succeed; any response over a fixed
  boundary never completes. Over the node's sim IP the client gets exactly
  **130907** body bytes then the connection is closed (epee's 5–6 s send
  watchdog fires) → `IncompleteRead`. Over 127.0.0.1 loopback the client gets
  exactly one **65536**-byte chunk then **0 further bytes** until it times out.
  In both cases monerod builds the *correct* full response (the `Content-Length`
  header is right — 663230 B at gray = 5000); the bytes simply stop flowing.

- **Not a buffer size.** Raising and pinning Shadow's `--socket-send-buffer` /
  `--socket-recv-buffer` to 4 MiB (autotune on *and* off) changed nothing —
  byte-for-byte the same cutoff. Shadow's own config spec confirms there is no
  other buffer/window knob (CoDel AQM is downlink-only, issue #3701); and per
  #3701 a genuinely-full send buffer would apply backpressure, not silently
  stall — so the send buffer is not the gate.

- **Not the interface.** True 127.0.0.1 loopback (monerod bound `0.0.0.0`,
  sidecar → 127.0.0.1) stalls too, just at a different point.

- **Root cause (best available):** a Shadow simulated-TCP fidelity limit for a
  single large **un-chunked** write. The most likely exact mechanism is Shadow
  issue **#3274** ("partial read triggers an event in Shadow, but not Linux"):
  `boost::asio::async_write` (what epee uses to send an RPC response) needs
  repeated `EPOLLOUT` "writable again" notifications to resume a partially-sent
  buffer; if Shadow drops that notification after part of a 650 KB write has
  gone out, the transfer halts with no error until an external timeout — exactly
  what we observe. Shadow tracks an open milestone (#18, "Validate and improve
  TCP simulation accuracy") with several related open TCP/ACK bugs
  (#3572, #3573, #2683). Shadow is a prebuilt binary here — not patchable.

- **The corroborating asymmetry:** Monero's own **P2P** traffic routinely moves
  payloads far larger than 128 KiB over this same simulated network and works,
  because epee **chunks** P2P messages at 32 KiB
  (`contrib/epee/include/net/abstract_tcp_server2.inl:889`, `CHUNK_SIZE =
  32*1024`). RPC-HTTP responses are handed to `async_write` as **one solid
  piece** (~890–892) and stall. Same network, different traffic shape.

## 3. Why every non-invasive alternative is dead

- **Raise/pin Shadow socket buffers** — falsified (Section 2).
- **127.0.0.1 loopback** — falsified (Section 2).
- **Separate probe host over the sim network** — the sim-IP self-connection is
  already an over-the-sim-network transfer and it stalls; another host reading
  the target's RPC would hit the same Shadow limit.
- **`p2pstate.bin`** (monerod's on-disk peer store, readable from the shared
  FS) — Boost **binary** serialization (not practically parseable in Python),
  and flushed only every **30 min** — far too coarse for the B trajectory.
- **ZMQ** — no pub topic carries peer data; `get_peer_list` is blocked on the
  ZMQ-RPC restricted-method list.
- **`print_pl`** (daemon console command that prints the peer lists) — only
  writes to an interactive console; the node runs `--non-interactive`, and there
  is no signal/RPC to trigger it.
- **Query the RPC from the control shell** (outside Shadow) — impossible; sim
  IPs are not routable outside the simulation.

The only remaining path changes the traffic pattern or removes the network from
the peer-list read entirely. We chose the latter (guaranteed) — the file dump.

## 4. Why the patch does NOT bias the experiment (this is the important part)

The patch is a **measurement instrument**, not an experimental variable. It
changes how we *observe* the target, never how the target *behaves*:

1. **Flag-gated to one node.** The dump only runs when `--peerlist-dump-file` is
   set. Only the target (relay-4000) sets it; the other ~2,200 nodes run
   byte-identically to an unpatched run. (The shared binary is rebuilt, but with
   the flag absent its behavior is unchanged.)
2. **Read-only w.r.t. peer state.** The dump only *serializes* the peer list
   monerod already maintains. It does not add, remove, re-order, or re-score
   peers, does not touch connection selection, the /24 outbound-diversity
   filter, gray/white eviction, or handshake/timed_sync logic. The eclipse
   dynamics (CTR, B, OR trajectories) are produced entirely by the unmodified
   P2P code.
3. **Out-of-band of the simulated network.** The dump is written to a **file on
   the shared real filesystem** (Shadow hosts share the host FS), not sent over
   the simulated network. It therefore adds **zero** sim-network traffic and
   cannot perturb the attack, the target's connectivity, or timing. This is the
   same mechanism the agents already use to record metrics.
4. **Negligible cost.** A periodic serialize + file write (~650 KB every ~30 s
   for one node) is trivial relative to monerod's work and to the existing
   30-min `p2pstate.bin` store; file I/O is not the simulated resource.
5. **Same data, different delivery.** The dumped list is exactly what
   `get_peer_list` would have returned — identical fields (IP, port, last_seen),
   just delivered via a file instead of a stalled HTTP stream. No metric
   definition changes.

In short: the target eclipses (or resists) exactly as it would unpatched; we are
only able to *read* its full peer list, which Shadow's TCP otherwise prevents.
This is standard for network-simulation studies, where the measurement path is
deliberately kept off the modeled network so it can't act as a confound.

## 5. What the patch does (design)

Target-only, gated behind one new net_node option:

- `--peerlist-dump-file <path>` — enable the dump. A **relative** path is written
  under the node's data dir (`m_config_folder`, where `p2pstate.bin` also lives),
  so a static scenario value yields a correct per-run path; an **absolute** path
  is honored as-is. Cadence is fixed at **30 s** (Shadow/epee's
  `once_a_time_seconds` template takes the interval as a compile-time constant,
  mirroring the existing `p2pstate.bin` store interval — so it is not a runtime
  flag).

When enabled, monerod runs a periodic idle task (added next to the existing
`p2pstate.bin` store in `idle_worker()`) that fetches the full white+gray lists
via the same `get_peerlist()` the `get_peer_list` RPC uses, and **appends** one
JSON snapshot every 30 s to the file:

```
{"t":<monerod clock = Shadow sim time>,"white_n":N,"gray_n":M,
 "white":[["<ip>:<port>",<last_seen>], ...],"gray":[["<ip>:<port>",<last_seen>], ...]}
```
(one snapshot per line; each entry is the address string `adr.str()` plus
`last_seen`.)

Appending timestamped snapshots (not overwriting) preserves the **time series**
needed for the B(t)/OR(t) trajectories. monerod's clock under Shadow is the
virtualized sim clock, so `t` is sim time (converted post-hoc, same epoch as the
`bash.*.stdout` logs, `2000-01-01`).

The co-located sidecar (`agents/eclipse_probe.py`) continues to record CTR
(`get_connections`) and sizes (`get_info`) over RPC as today; only the large
per-entry list moves to the file. Post-hoc, each snapshot's IPs are classified
against `agent_registry.json` to compute B and OR. ("Raw data is king" — we dump
the raw lists and analyse offline.)

## 6. Build & wiring

- The patch is vendored at `patches/monero-sim-peerlist-dump.patch` (3 files:
  `src/p2p/net_node.{cpp,h,inl}` — one option descriptor, one member + method
  declaration, one idle-loop call plus the `dump_peerlist_json` method). It is
  diffed against upstream monero v0.18.5.1 (= `monero.pin`) and is disjoint from
  the hard-fork patch (`cryptonote_core.cpp`), so the two stack in either order.
- `./setup.sh --hardfork` applies every patch under `patches/` to a detached
  worktree of the pinned checkout and installs the result as
  `~/.monerosim/bin/monerod-hf` (provenance in `monerod-hf.provenance`, one
  `patch:`/`patch_sha256:` pair per patch). The primary `~/.monerosim/bin/monerod`
  stays byte-for-byte vanilla. The apply-check tripwire fails the build loudly
  if `monero.pin` ever moves past what the patch applies to.
- Wire only the nodes that need the dump via the scenario: `daemon: monerod-hf`
  plus `daemon_options: {peerlist-dump-file: peerlist_dump.jsonl}` (relative →
  the node's data dir). monerosim forwards `daemon_options` to the monerod CLI
  verbatim. In the Nyx scenarios that is the target (relay-4000) and the 30
  observed benign relays (relay-2001..2030); every other node runs vanilla
  `monerod`.
- Analyse the dumps post-hoc with `analysis/eclipse/analyze_peerlist_dumps.py`
  (classifies each snapshot's entries against the run's `agent_registry.json`
  to produce B and OR).
- Verify against the fast repro
  (`test_configs/eclipse_socketbuf_verify.scenario.yaml`, gray → 5000 in
  ~3.5 min sim): the dump file should contain full 5000-entry snapshots with no
  truncation, while `get_peer_list` over RPC still fails — confirming the file
  path is immune to the Shadow limit.

History: during the study (2026-09-16) the patch was hand-applied inside the
monerod-sim build tree and installed over the shared vanilla `monerod` slot;
that hybrid binary was replaced by the vendored build on integration.

## References

- Investigation + empirical evidence: `~/basement_monerosim/20260917_eclipse_reproduction/investigation/20260916_problem.txt`
  (EMPIRICAL UPDATE #1 socket buffers, #2 loopback) and
  `.../investigation/20260916_problem_fixed.txt` (v3 diagnosis, Shadow issue-tracker evidence).
- Shadow: config spec + limitations (shadow.github.io); issues #3701 (uplink
  buffer/AQM), #3274 (partial-read epoll divergence), #3572/#3573/#2683,
  milestone #18 ("Validate and improve TCP simulation accuracy").
- epee traffic-shape asymmetry:
  `contrib/epee/include/net/abstract_tcp_server2.inl:889` (P2P 32 KiB chunking)
  vs ~890–892 (RPC single write).
- Paper metrics: B (benign graylist count), OR (occupation rate); seed
  `general.simulation_seed = 12345`.
