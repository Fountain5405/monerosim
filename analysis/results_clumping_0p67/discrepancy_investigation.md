# Mainnet-vs-sim discrepancies: mechanism investigation (2026-06-10)

Fresh-eyes re-investigation of Rucknium's issue-#3 review against the **original
v0.1.0 200u/800r@300s run's own logs** (`/home/lever65/xfer_logs/`, log-level 1)
and monerod source. Method: join TCP `NEW`/`CLOSE CONNECTION` events with
`NOTIFY_NEW_TRANSACTIONS` gossip per connection (`/tmp/conn_gossip_join.py`),
then verify every inferred mechanism against source constants. Parser validated
two ways: R-method emulation reproduces Rucknium's connection-duration median
(**1.53 min vs his 1.52**) and clumping (**23.8 % vs his 23.4 %** singles).

Build facts established first: all runs (20260511 original AND current) use the
**same monerod binary** `v0.18.1.0-f09c2c858`; levin command census on the logs
shows **only stock protocol commands** (2002/2008/2009/1001-1003 — no txv2
commands; the `txv2` branch checked out in `monero-shadow/` is newer work, NOT
what the sims ran). So mainnet comparisons are protocol-valid, and old-vs-new
"build" throughput differences are orchestrator/agent-side, not monerod.

## 1. Connection duration (his 1.52 min vs mainnet 23 min) — SOLVED

**Mechanism (verified in source, stock monero, unmodified in fork):**
`t_cryptonote_protocol_handler::update_sync_search()` —
`once_a_time_seconds<101> m_sync_search_checker` (cryptonote_protocol_handler.h:185).
When a node is at max out-peers (12) with fewer than
`P2P_DEFAULT_SYNC_SEARCH_CONNECTIONS_COUNT`(=2) peers in `state_synchronizing`,
it **drops the LAST non-anchor synced out-peer** ("dropping synced peer, 0
syncing, 12 synced, 12 max out peers") to search for sync candidates.
`P2P_DEFAULT_ANCHOR_CONNECTIONS_COUNT`(=2) anchor connections are exempt.

**Measurements (user-103, original run):**
- Drop events fire at EXACTLY 101 s cadence (e.g. 02:03:57.246 → 02:05:38.247 →
  02:07:19.247); 497 drops in 16 h ≈ one per 116 s of effective firing.
- Tx-carrying connections: n=842, lifetime **median 100.3 s, p25=100.0,
  p75=100.6, p90=100.9** — exactly one timer period; the sim's instant
  reconnect supplies a fresh "last" victim every cycle.
- Elders: 7.1 % of tx-carrying conns live >1 h (up to 13.9 h) — the protected
  anchors (+ inbound mirrors of peers' anchors). Random victim selection is
  excluded (P(anchor surviving 470 firings by chance) ≈ (11/12)^470 ≈ 1e-18).
- Gossip is CONTINUOUS within connections (median inter-NOTIFY gap 4.9 s,
  98.5 % of tx-conns have ≥2 NOTIFYs; gossip span ≈ lifetime − edges).

**Therefore:** Rucknium's tx-gap metric was a **valid proxy for TCP lifetime of
tx-carrying connections**. Our previous docs' claim that it was a
"measurement-method artifact (tx-exchange span, not TCP)" is **WRONG and
retired**, as is "connections now hold for hours thanks to the cap fix" (the
hours-long conns are anchors; they exist pre-fix).

**Why the 1.5 / 23 / 120-min gradient — one mechanism, three environments:**
- 1000-node sim: everyone is always synced (nobody in `state_synchronizing`)
  and replacement connects/handshakes instantly → dropper fires EVERY 101 s and
  always kills the newest conn → median = one period ≈ 1.7 min.
- Mainnet: fresh peers linger in `state_synchronizing`, many candidates are
  unreachable, replacements are slow → condition often false, victims spread
  across slots → tenure ~12-14 × 101 s ≈ **23 min** (his median; the
  ≈ slots × interval arithmetic is suggestive, labeled interpretation).
- 35-node sim: only 34 candidates, peerlist exhausted → nothing to rotate to →
  tenures bounded by run length → **120 min** median, max ≈ run length.

This is **emergent stock-monerod policy under perfect network conditions**, not
a monerosim bug and not the max-connections-per-ip issue. It is also the
explanation Rucknium asked for ("the cause of the discrepancy is unclear").

## 2. Clumping — sim-side mechanism VERIFIED; mainnet-side gap is the open question

**Verified sim mechanism (source + measurement):**
- Full flooding: 588,387 tx receipts / 18,444 unique txs = **31.9 receipts/tx ≈
  node degree (~32: 12 out + ~20 in)** — every tx crosses every connection.
- Stock D++ per-connection flush batching: `CRYPTONOTE_DANDELIONPP_FLUSH_AVERAGE
  = 5 s` toward incoming conns, half that (2.5 s) toward outgoing
  (levin_notify.cpp:79-88). Direction split on user-103 confirms BOTH timing and
  batching: OUT-received (peers' in-flush): 9.0 % singles, 4.25 txs/msg, median
  gap 6.58 s; INC-received (peers' out-flush): 32.5 % singles, 2.73 txs/msg,
  gap 3.88 s. The 2:1 asymmetry is the D++ constant pair, visible in data.
- Clump AMPLIFICATION: both directions clump more than the Poisson floor at
  network rate (predicted 25.1 % / 52.8 % singles for 5 s / 2.5 s windows at
  0.466 tx/s; measured 9.0 % / 32.5 %) — relayed messages re-batch entire
  incoming clumps, so clumping compounds with hop depth. Consistent with
  in-run growth: 29.7 % singles (h4-8) → 22.5 % (h8-12) → 21.8 % (h12-16).

**Corrected x-axis (ACTUAL delivered rates, see rate_audit.md):** 0.080→92.4 %,
0.226→49.5 %, **0.466→23.4-23.8 %** singles. The old "the 23.4 % match was an
artifact of an overloaded/stalled run" claim is dead (run completed, healthy).

**The real discrepancy (open, good question FOR Rucknium):** at mainnet's
1.45 tx/s, full flooding + 5 s/2.5 s windows would predict ≲5-10 % singles; he
measured **25.05 %**. Mainnet damps clumping ~3× vs the sim mechanism —
back-solving, his per-connection effective λ ≈ 2.4 (≈1.7 s window at full
flood, or full windows at ~1/3 the per-conn rate). Candidate (UNVERIFIED)
mainnet-side differences: his node's connection count; NOTIFY message size
splitting at high rates; real-network jitter spreading flush queues; rate
variability across his measurement window. We cannot test these without
mainnet logs — worth asking him directly (his node's degree + whether every tx
arrived on every connection in his data).

## 3. One-second cycle (quarter vs eighth-second) — partially explained, now source-verified

`fluff_stepsize = std::ratio<1,4>` (quarter-second Poisson quantization) and the
5 s/2.5 s averages are CONFIRMED in the built source family (previous docs
asserted this without provenance; now checked). Mainnet's quarter-second comb
with his own observed "subtle double-mode on either side" vs the sim's clean
eighth-second comb: the deterministic, jitter-free sim sharpens fine structure
that real-network jitter smears. The exact origin of the eighth-second
sub-grid (vs pure quarter) is NOT fully derived — keep the honest framing:
grid verified, sharpening mechanism plausible, sub-grid origin open. (His
hypothesis — longer sim latency — is not supported: same eighth-second comb at
35 and 1000 nodes with very different latency mixes.)

## 4. Skellam (original 1k "less close", off-grid observations) — open

Plausibly related to the 101 s connection rotation (delivery paths churn
mid-hour, mixing flush phases). UNVERIFIED — do not assert. Post-fix completing
runs fit well per results_200u_rerun / results_1k_mainnet.

## Implications for the rewrite

1. The connection-duration section becomes a STRENGTH: his flag exposed a real,
   fully-explained emergent behavior; his metric is validated; we name the
   mechanism (update_sync_search, 101 s, anchors) with measurements.
2. Stop attributing 1k connection behavior to the max-connections-per-ip bug
   anywhere (bug is real but small/dense-scale; binary + profiles identical at
   1 k pre/post in the relevant respects).
3. Clumping section: volume-bound curve with ACTUAL rates; sim mechanism
   verified end-to-end; present the mainnet damping factor as the open
   question; the "needs 17×/57-node" capacity framing is dead.
4. The reply can ASK Rucknium two sharp questions: his node's connection count
   during the 25 %-singles window, and whether mainnet logs show full per-edge
   flooding — these decide the remaining clumping gap.
5. One-second-cycle: keep, with source-verified constants and honest open
   sub-grid note.

## Provenance

- Analysis script: `/tmp/conn_gossip_join.py` (copy into analysis/ before
  committing if kept).
- Logs: xfer_logs user-103 (original run; relay-014/432 unanalyzed, available
  for replication). Post-fix replication on
  archived_runs/20260608_164109_1k_mainnet pending (expect same 101 s
  signature — same binary).
- Source: monerosim_scale/monero (stock v0.18-series) and
  monerosim_scale/monero-shadow (fork; relevant code identical).

---

# Part 2 (2026-06-10, later): binary confound ruled out; cap=4 verdict

## Binary/provenance verification chain (user asked: is txv2 a confound?)

Four binaries exist in `~/.monerosim/bin/`:
| binary | version | mtime |
|---|---|---|
| `monerod` (PRODUCTION) | v0.18.1.0-**f09c2c858** | Apr 25 |
| `monerod-patched` | v0.18.1.0-4286fbe6c | Apr 6 |
| `monerod-v1` | v0.18.1.0-4286fbe6c | Jan 20 |
| `monerod-v2` | v0.18.1.0-**a2ad77425** | Jan 19 |

- `monerod-v2` = the txv2 build: a2ad77425 IS the monero-shadow txv2 branch tip
  (that's why the branch is checked out). It is NOT used by any experiment.
- All 9,592 `daemon:` entries in test_configs say plain `monerod`;
  `src/utils/binary.rs::resolve_binary_path("monerod")` → `~/.monerosim/bin/monerod`.
- `run_sim.sh` rebuilds ONLY the Rust orchestrator (`cargo build --release`;
  62-byte build.logs = cargo output). It never recompiles/copies monerod.
- Same banner across the whole series: original 20260511 run = f09c2c858;
  in-flight clumping run = f09c2c858 (live log checked).
- Behavioral: live run has 0 txv2 messages (`NOTIFY_REQUEST_TX_POOL_TXS` etc.)
  vs 174,475 stock NOTIFY_NEW_TRANSACTIONS; original run's full levin command
  census = stock-only command IDs.
- f09c2c858 resolves in NO local repo (likely a since-rebased shadow-branch
  state). Exact source state unrecoverable; wire behavior verified stock; the
  relevant code regions are identical stock-vs-fork.
- setup.sh, if re-run, clones/builds from the official monero repo /
  $MONERO_DIR (monerosim_scale/monero @ 4286fbe6c) — would produce a DIFFERENT
  binary than production f09c2c858. Don't re-run setup's monero build mid-series.

## cap=4 verdict: fixes NOTHING Rucknium's analysis surfaced (it is bycatch)

| Rucknium finding | cap=4 effect | actual cause |
|---|---|---|
| conn duration 1.52 min (vs 23 mainnet) | none (100.3 s median pre AND post) | update_sync_search 101 s rotation |
| clumping 23.4 % ≈ mainnet 25 % | none | volume × D++ 5 s/2.5 s windows × flooding |
| eighth- vs quarter-second cycle | none | D++ quantization, jitter-free sim |
| Skellam "less close" | none | open |

Handshake profile is IDENTICAL pre/post fix at 1000 nodes (so even the "10 %
handshake success" once cited as the cap=1 disease is just normal discovery
probing at scale):
- pre-fix (cap=1, user-103): 5,319 NEW, 509 handshaked (9.6 %), 3,471
  before_handshake closes (65.3 %)
- post-fix (cap=4, 1k_mainnet user-001): 5,568 NEW, 558 handshaked (10.0 %),
  3,662 before_handshake closes (65.8 %)

What cap=4 DOES fix: small/dense full-mesh sims (quickstart-15: 7,867
refusals, no stable mesh → works at cap=4). Verified harmless at 1000 nodes
(captest_cap4 completed; profiles unchanged). It was found while chasing his
connection-duration flag but is orthogonal to every metric he measured.

NUANCE for the doc: the "mainnet 23 min ≈ 12-14 slots × 101 s" arithmetic is
an INTERPRETATION (labeled as such), not a measurement. The verified statement:
the sim's 100.3-s victim lifetime equals one sync-search period because
replacement conns appear instantly and become the next victim; mainnet's
longer tenures imply slower/spread rotation (refill friction), mechanism of
spread not directly measured.

---

# Part 3 (2026-06-10): adversarial verification + realism feasibility (workflows)

## Claim verification (5-slice adversarial workflow)
~38 claims CONFIRMED exactly (all §3 measurements incl. 101.001s median
inter-drop over all 497 events, 497/497 drop→CLOSE ≤1ms, replacement NEW at
median 0.76s/100%≤2s; all source constants both trees; all rate-audit numbers;
direction split; Poisson math; R-file values; binary chain; command census;
all Rucknium quotes/numbers vs the fetched issue; height 331 PROVEN from log:
331 distinct HEIGHT values 0-330, last block 15:54:29; anchors' anti-eclipse
provenance = commit 8277e67f citing eprint 2015/263 countermeasure 4).
5 corrections applied to the v2 doc:
1. "victim = newest" is NOT source-guaranteed — for_each_connection iterates a
   boost::unordered_map keyed by RANDOM UUIDs (not insertion order). The
   one-period lifetime collapse is EMERGENT (iteration-last victim + instant
   refill); elders = 2 anchors + low-hash-position survivors (explains ~60
   elders >> 2 anchors).
2. "every drop closes a tx-carrying peer": 80% overall, ~94% in tx-era (75
   drops predate tx traffic).
3. quickstart-15 refusals: 7,867 = ONE node; run-wide = 31,180.
4. "no experiment references monerod-v2" only true scoped to this series
   (April upgrade_smoke configs use daemon_0/daemon_1: monerod-v1/v2).
5. fork=stock only for the three cited regions; fork's P2P_SUPPORT_FLAGS adds
   a v2 bit → protocol claim rests on wire census, not tree identity.
   (Also: before_handshake %s use NEW-count denominator; 4079min<72h sim.)

## Realism feasibility (verified in source; 3rd agent died on session limit)
- CHURN IS EXPRESSIBLE TODAY: Shadow 3.2.0 fork supports per-process
  shutdown_time/shutdown_signal/expected_final_state; monerosim daemon_phases
  (daemon_0/daemon_1 scenario keys → DaemonPhase → ShadowProcess, all 4
  lifecycle fields already in src/shadow/types.rs:370-391) already emit
  stop+restart of the SAME binary on same data dir/ports (args are
  phase-independent). Port-rebind/LMDB-lock/wallet-reconnect solved by the
  upgrade machinery (SIGTERM clean exit; fcntl auto-release; fork's
  is_addr_in_use bind-time cleanup; MIN_PHASE_GAP_SECONDS=30, default gap
  300s). Remaining work = generator emitting randomized churn schedules.
  Caveat: daemon-churn with agent/wallet staying up unexercised.
- HIDE-MY-PORT: advertises my_port=0, still listens+dials; try_ping
  early-returns on port 0 → NEVER enters any peerlist → 80% hidden gives
  ZERO dial friction (clean peerlists) — structure/realism only.
  --in-peers 0: stricter, but advertises real port → burns 2s back-ping per
  handshake. Orchestrator passes neither today.
- THE FRICTION AMPLIFIER: failed dial → record_addr_failed →
  P2P_FAILED_ADDR_FORGET_SECONDS = 3600 (1h!) suppression from candidate
  selection + anchor reconnect + gossip merge. So churn's stale white-list
  entries darken the candidate pool for an hour per failure → starves slot
  refill → dropper condition (slots full) fails → rotation stalls. Shadow
  caveat: stopped peers RST instantly (vs mainnet 5s timeouts) → sim churn
  friction weaker per event → calibrate churn upward.
- Failed-connect timeouts: P2P_DEFAULT_CONNECTION_TIMEOUT=5s, ping 2s,
  handshake invoke 5s. Gray housekeeping evicts failing gray entries; white
  stale entries persist (cap 1000).

## Part 3 addendum — FINAL replication numbers (run 20260610_031558, R canonical)

Run completed: ALL CHECKS PASSED, 0 failures, 13,678 txs = 0.345 tx/s actual,
13h18m wall. Rucknium-method (10-node sample, seed 314) results vs his
original v0.1.0 analysis:
- Clumping: 23.03% singles / 32.19 / 23.35 / 12.67 (his: 23.40 / 32.80 /
  23.38 / 11.98) — reproduced within 0.4pp at 26% LESS delivered volume
  (0.345 vs 0.466) → curve SATURATES above ~0.3 tx/s. (Single-node count on
  user-001 was 26.2% — node variance; canonical = 23.03.)
- Conn-duration (tx-gap): median 1.5238 min, max 709.78 (his: 1.5244 /
  709.80) — rotation signature identical across cap=1/4 and orchestrator
  versions; metric fully determined by the 101s mechanism.
- Volume curve x = actual tx/s → % singles: 0.080→92.4, 0.226→49.5,
  0.345→23.0, 0.466→23.4, mainnet 1.45→25.05.
Outputs copied to analysis/results_clumping_0p67/ (raw + 3 PNGs).
v2 response doc COMPLETE: docs/20260610_rucknium_review_response_v2.md §4.4.
