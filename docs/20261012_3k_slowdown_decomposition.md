# 3k slowdown: workload, not engine (2026-10-12)

Question: the 3k scale-ladder rung ran at sim:wall ~0.18 in its final hours
versus ~1.45 at 1k. How much of that is irreducible workload, and how much
is fixable engine cost (Shadow / shadowformonero)?

Answer: **workload.** The aggregate cost follows the quadratic relay work,
Shadow's event throughput did not degrade with node count, and the late-run
slowdown at constant tx rate tracks a growing mempool backlog caused by the
3k tx rate exceeding block capacity. No evidence for an engine defect; no
profiling of shadowformonero is warranted on this data. The planned
"no-activity 3k" control run is not needed to answer the question.

Data: the SSL-on ladder runs on
`/mnt/remote_spinny/20261007_monerosim_scale_ladder/` (`*_1k_ssl`,
`*_2k_ssl`, `*_3k_ssl`): `shadow.data/sim-stats.json`, Progress lines in
`shadow_run.log`, `transaction_registry/{transactions,blocks_with_transactions}.json`,
`memory_samples.csv`, and miner-001's `bitmonero.log` (block height → sim
time, block weight).

## 1. Aggregate cost scales with relay work; engine throughput holds

Tx relay work ≈ txs × nodes (every tx reaches every node).

| | 1k | 2k | 3k | 3k ÷ 1k |
|---|---|---|---|---|
| txs (summary "Created") | 13,101 | 25,684 | 37,198 | 2.8× |
| txs × nodes | 13.2 M | 51.6 M | 112 M | **8.5×** |
| Shadow packets | 2.25 B | 8.37 B | 18.05 B | **8.0×** |
| Shadow events | 17.5 B | 48.6 B | 90.4 B | 5.2× |
| wall time | 9.4 h | 20.5 h | 36.5 h | 3.9× |
| **events / wall-s** | **515 k** | **660 k** | **687 k** | 1.33× |

Packets follow the predicted relay work (8.0× vs 8.5×). Events grow less
(some per-node cost is linear). Event throughput *rises* with scale, so the
engine is not losing efficiency as nodes grow; wall time = events ÷
throughput (5.2 / 1.33 ≈ 3.9). The final window (sim 14→16 h) is 8.7×
slower at 3k for ~9× the relay work.

Caveat: events/wall-s is a whole-run average and cannot exclude a late
degradation — hence section 2.

## 2. Late-run slowdown at constant tx rate

1k, steady state (sim 5.5–15.5 h): ~1,800 user txs per sim-h, a flat
38–46 wall-min per sim-h. No drift.

3k, 30-min bins (rates per sim-h; backlog = cumulative txs created −
cumulative txs included in blocks; RAM = box-wide available):

| sim h | txs sent | txs in blocks | backlog | wall-min / sim-h | box RAM free |
|---|---|---|---|---|---|
| 10.5 | 2,641 | 1,966 | 777 | 144 | 819 GB |
| 11.0 | 2,448 | 1,463 | 1,762 | 218 | 784 GB |
| 11.5 | 2,527 | 3,561 | 728 | 224 | 778 GB |
| 12.0 | 2,671 | 2,808 | 591 | 190 | 781 GB |
| 12.5 | 2,690 | 2,793 | 488 | 190 | 783 GB |
| 13.0 | 2,705 | 2,004 | 1,189 | 196 | 786 GB |
| 13.5 | 2,695 | 2,114 | 1,770 | 230 | 775 GB |
| 14.0 | 2,644 | 2,296 | 2,118 | **340** | 757 GB |
| 14.5 | 2,597 | 1,919 | 2,796 | 312 | 751 GB |
| 15.0 | 2,611 | 2,316 | 3,091 | **368** | 749 GB |

(txs per 30-min bin; wall-min normalised per sim-h.)

From 12 h the send rate is flat (~5,300/sim-h) while wall cost per sim-h
nearly doubles; cost per user tx goes ~2.1 → ~4.2 wall-s. The backlog is
the only measured quantity that moves with it (it also explains the
11.0 h bump: backlog 1,762 then cleared to 728 with a jump in pace).

Mechanism (inferred, not profiled): every pending tx is held, validated
and periodically re-announced by every node, so the same send rate costs
more as the pool grows. That is faithful daemon behaviour — workload.

Ruled out: memory pressure (≥ 749 GB free throughout, swap flat at 8 GB).
**Not ruled out:** disk / shadow-logger and contention from the other user
on this shared box — the run recorded neither disk usage nor box load over
time. The 14 h step fell around 01:30 wall-clock.

## 3. Why there was a backlog: block capacity

Blocks at 3k were full from ~11 h: the fullest held 140–180 txs and weighed
~303–308 kB, just over the 300 kB penalty-free minimum. At 2-min blocks that
is ~4,500–5,000 txs per sim-h of capacity, below the ~5,300 sent. The 1k
rung (~1,800/sim-h) never got near it (2 txs unconfirmed at the end vs
~2,400 at 3k).

### Did the dynamic block size adapt?

It did, but negligibly. From miner-001's block log (median of the last 100
block weights, M100):

| height | sim h | M100 | blocks > 300 kB in last 100 |
|---|---|---|---|
| 380 | 11.9 | 301,125 | 60 |
| 420 | 13.0 | 302,641 | 92 |
| 460 | 14.3 | 303,970 | 96 |
| 510 | 15.9 | 305,690 | 96 |

The penalty-free zone grew ~1.5% (≈ +4.5 kB) over 4 sim-hours. Growth is
fee-limited, not time-limited: a miner exceeds the median M only while the
extra fees beat the penalty `reward × ((W − M)/M)²`. With reward ≈ 35 XMR,
fees ≈ 0.0024 XMR per ~2 kB tx and M ≈ 300 kB, the break-even overshoot is
`fee × M² / (2 × reward × tx_weight)` ≈ 1.5 kB — exactly the 1–3 kB the
blocks actually overshot. The median can only ratchet up by roughly that
much per 100-block window, so a longer run would not have rescued
capacity on any practical timescale. Only higher fees would (a wallet
priority bump makes overshoot pay; agents call `transfer` with
`priority: 0`/auto — whether wallet2's auto-priority escalated under this
backlog was not checked).

This is real Monero behaviour, not a simulator artefact: a sustained tx
rate above ~300 kB / 2 min at low fees produces a growing mempool.

## Conclusions

1. At or below block capacity the cost of a run is ≈ quadratic relay work
   with a healthy engine; this is the price of faithful flooding.
2. Above capacity, cost per tx grows with the backlog. The final hours of
   the 3k rung therefore measure an over-capacity network, not steady
   state. Its cross-scale comparisons (latency, propagation) are taken
   mostly before saturation and remain valid.
3. Size scenarios so the network-wide tx rate stays under
   ~4,500 txs/sim-h (≈ 7.5 tx/user/h at 600 users, vs the 12/user/h
   configured), unless congestion is the thing being studied.
4. Long runs should record disk usage and box load so the remaining
   unknowns (disk, contention) can be excluded from data next time.

Dropped follow-ups: 1k dose-response log-level A/B (shelved 2026-10-12);
3k no-activity control run (not needed); shadowformonero profiling (no
evidence of engine cost).
