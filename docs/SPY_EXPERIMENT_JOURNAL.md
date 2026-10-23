# Spy-node defenses: experimental journal

The single record of the experiments for the spy (proxy) node test plan,
`docs/20261018_spy_node_defenses.md`. It covers the lab on `phantom`, `simbox2` and
`simbox3` only. The Share-or-Perish (MRL #146) campaigns run on another box
under another agent and are not recorded here.

**Status (2026-10-23, 18:05).** X0, the calibration, is closed: the `legacy` leg passes its targets (3 seeds per
cell), the /24-dedup leg reads -45% on the 69-/24 replica and -77% on the lean k=6 cell (3 seeds), and the embargo
target is read as "stems fluff before any timer fires", which is the stock behaviour (open question 4, closed). X1 has
its first long cells: the `--sim-fixed-randomx-seed` patch (E20) lets a 32 GB box run 30 simulated hours, and E22 gives
both presets at a 24 h warmup. `core` (113 spies in one /24): the relay excess of E14-E16 is a transient of the gray-list
drain that ends at the model in about a day (0.0044 light against the model's 0.0045 at a 24 h warmup, E22c); with the ban list
on half the nodes, 0.0025 (0.57x the no-list cell) and no user exposed. `tail` (42
spies in 21 /24s): 0.157, a slow per-relay relaxation set by when the relay started, the latest-started relays still at 3x
the model's ceiling after 30 h; the stock rule's recency bias over the relays' own lists reproduces it (E21), and E22
infers why it survives for a /24-diversified spy and not a dense one (P13 tests that). Under the old rule (v0.18.4.2, E23) the
same fleet reads 0.286, 2.34x its model, with no relaxation at all: stock dedup removes 42% of its slots (the models said 33%), and
the lock-in is not a dedup artefact. Spies per /24 (E24, P13): at 13 h, 1 per /24 reads 0.198, 2 per /24 0.166, 8 per /24 0.175;
the 1-to-2 step is the dilution E22 expected at a third of the 1/m size, the 8-per-/24 window is still inside its drain's transient,
and the steady state goes to P16 (24 h warmups at 1 and 8 per /24). For the unreachable users X1 scores,
the answer is stable across warmups: `sp_r` precision 1, recall 0.035-0.06, 12-18 of 40 twenty-transaction senders exposed
within 4 h in `tail`, 0-3 of 40 in `core`. Whether mainnet relays behave like the lab's (no churn, a white list that holds
the whole network) is open question 8. Running: `simbox2` has P14 (the full-coverage `half` `tail` cell) then P15 (the `legacy`
`tail` replicate at seed 23456); `phantom` has P16a (`tail` at 1 per /24, 24 h); `simbox3` finishes a 6 h filler, then P16b (8 per
/24, 24 h), then the last two fillers. Entries E1-E24 below; predictions P1-P16 in section 5.

## 1. How this journal works

- **A run is registered when it finishes** (`analysis/spy/run_register.py add`),
  which copies the files that define and score it into
  `docs/spy_journal/runs/<run_id>/` and rebuilds the register in section 3. An
  archive is ~12 GB, lives on the box that ran it and gets pruned; the copy is a
  few tens of KB and is enough to see exactly what ran and what was measured.
- **An entry is written when a question is closed or changed**, not per run: what
  was asked, what ran, what was predicted *before* the result, what came out, what
  it means, and what is still wrong with it.
- **Predictions are filed before the runs** (section 5, with the time filed).
  Entries E1-E12 were reconstructed from the run archives, the X0 write-up and the
  working session; they say where a prediction existed in advance (the plan's
  targets, the Monte Carlo model) and where it did not.
- **Nothing is deleted.** Pilots that failed, runs with a flawed setup and results
  that were later corrected stay in the register with a note. A correction is a new
  line in the entry, dated, not an edit of the old claim.
- **Replicates.** monerod is not seed-deterministic, so each cell gets at least 3
  seeds and cells are compared by their distributions, not by seed pairs. Until a
  cell has 3 seeds its entry says so.
- **Detail lives in `docs/X0_CALIBRATION.md`** (the analysis write-up: the preset,
  the model, the scaling argument) and in `docs/SPY_ESTIMATORS.md`,
  `docs/TXRELAY_LOG.md`. This file is the chronology and the index into them.

## 2. Method

**Measured quantity.** The *light-node outbound spy share*: over the activity
window (bootstrap end to stop time), take a snapshot of each honest user, relay
and observer node's connections every 300 s from the `bitmonero.log` connection
tokens; the share is spy outbound slots over all outbound slots, pooled over
snapshots and nodes. `light:q1..q4` split the window in four. Miners, medium hubs
and seeds are reported separately and excluded from "light". The scorer is
`analysis/spy/x0_calibration.py`; the origin estimators are
`analysis/spy/spy_estimators.py`. The X0 targets are: ~0.15 with `legacy`
selection and no list, ~0.07 with the list on half the honest nodes, ~70% lower
with /24 dedup, stem length near a geometric mean of 5, and the embargo rate; a
target passes within 1.5x, or with a written reason.

**Model.** `x0_calibration.py` prints a Monte Carlo of the selection rule over the
run's own pool (12 slots; `legacy` weights a /24 by its IPs, `24` weights every /24
equally, a node skips the /24 of each peer it picks). It is a reference, not a fit.
For more than one spy /24 it is a ceiling, not a prediction (E4).

**Binary.** `monerod-sim`: v0.18.5.1 plus the patches listed in each run's
`binary_provenance.txt`, among them `monero-sim-txrelay-log` (the ground-truth relay
log, I1) and `monero-sim-subnet-dedup` (`--sim-subnet-dedup=legacy|24|none`).
Built 2026-10-20 13:00 UTC on `phantom` (sha256 `ecaadf741f63...`) and
2026-10-22 02:58 UTC on `simbox2` (sha256 `39709561bce4...`); the two are not bit
identical (build time and paths), but their provenance files match line for line
apart from the time stamp.
*(2026-10-23: rebuilt with `monero-sim-fixed-randomx-seed` appended (E20): `simbox3` 03:58 UTC, sha256 `4258da26e187...`;
`simbox2` 08:05, `345d4ced95f1...`; `phantom` 08:10, `1472ed18703f...`. The old binaries are kept beside them as
`monerod-sim.pre-fixedseed`. The flag is off unless a cell sets it, and below block 2113 the behaviour is identical either way.)*

**Simulator settings.** Shadow (shadowformonero), `--bootfast --ksm`, KSM at 20,000
pages per 20 ms, `runahead 100ms`, `native_preemption`, 2 process threads (KSM at 10,000 pages in the first pilots), 5,000-node
CAIDA topology with weighted regions and prefix sharing 0.31 x 3. Spies are variant R
(stock `monerod-sim` that dials one fallback seed and logs relays); they announce
through the seeds only, and do not poison peer lists or multiplex ports.

*Deviations from the plan's X1, stated 2026-10-23 14:40 (the review found them unstated):* (1) **Transaction rate.** Each of the
40 users is configured with `transaction_interval: 300`, one transaction every 5 minutes (the 4 h windows carry 1,000-1,100 stem
transactions), against about one a day for a mainnet wallet: roughly 150x. This inflates the relayed-stem cover for *reachable*
senders and so the `combined` estimator's precision on busy nodes; the slot shares, the headline metric, do not depend on it (E2).
It also sets the time scale of the exposure counts: "12 of 40 senders with 20 or more transactions exposed within 4 h" is a
per-20-transactions figure, which at mainnet rates is weeks, not hours; what carries over is the spy's chance per transaction.
(2) **Spy type.** The plan's X1 spies are an 8-port, list-poisoning fleet; the lab's are variant R (above). A list-poisoning spy
would fill real gray lists with spy entries, which would make the lab's gray-list drain (E16) more like mainnet, not less.

**Boxes.**
- `phantom`: Ryzen 9 5900XT (32 threads), 32 GB (four 8 GB DIMMs at 2133 MT/s),
  ASRock X570, Ubuntu 24.04.5, kernel 6.8.0-146, glibc 2.39; 4 GB swap plus a
  temporary 24 GB swap file for the H=600 cells. Archives on `/mnt/ssdpool`.
- `simbox2` (`lever65@192.168.1.25`): the same CPU, 32 GB at 3200 MT/s, Gigabyte
  B550M, 931 GB NVMe, 8 GB swap, a real testnet `monerod` co-resident. Upgraded from
  Ubuntu 22.04.5 to 24.04.5 and rebuilt on 2026-10-22 (E9). Archives in
  `~/monerosim_archives`.

- `simbox3` (`lever65@192.168.1.176`, hostname `virt76`): a **shared KVM guest**, not bare
  metal. 40 vCPUs (40 single-core sockets), AMD EPYC "cpu family 23" (Zen generation),
  BogoMIPS 5589 (about 2.8 GHz, so each thread is probably well below a 5900XT's), 100 GB
  RAM, 8 GB swap, a 298 GB virtio root with ~96 GB free (267 MB/s direct writes). Other
  accounts live on it (`user`, `user12`, `rclusterworker`; 148 GB under `/home`) and the VM had
  been up 50 days with nothing running except an idle `screen` session. Upgraded on 2026-10-22
  from Ubuntu 22.04.5 to 24.04.5 (kernel 6.8.0-147, glibc 2.39, gcc 13.3), like the other two
  boxes. Rust 1.99.1 via `rustup`, KSM set by hand, archives in `~/monerosim_archives`.
  `monerod-sim` rebuilt there on 2026-10-22 21:47 UTC (sha256 `a5481f17097b...`); its provenance
  file matches `phantom`'s line for line apart from `built:` (checked 22:19). Validated by
  its H=71 run (P6a, 0.0641, inside 0.055-0.066): it behaves like the bare-metal boxes but takes
  about 1.8x `phantom`'s wall time (79 min for the H=71 cell).

**Cell portability rule (found 2026-10-22 22:25).** A cell must be generated on `phantom` and
copied (md5 checked) to the other boxes. `scripts/generate_config.py` resolves
`activity_start_time: auto` through `scripts/calibrate.py:compute_stagger`, which uses the
box's core count and `~/.monerosim/calibration.json`; `make_lean.py --reachable 71` on `simbox3`
gave a stagger of 9 s between users where `phantom` gives 11 s (39 of the 40 `activity_start_time`
lines differ and nothing else does). `simbox2` is a clone of `phantom`, which is why its
cells agreed. The stagger moves the users' first transactions by up to 80 s, so it is not
expected to move the spy share, but a cell that differs between boxes is not the same
experiment.

**Queue and guards.** Cells run one at a time from a queue file by
`docs/spy_journal/drivers/x0_queue*.sh`, which kills Shadow if free RAM drops below
1.5 GB, free disk below 30 GB, or swap grows past its allowance while RAM is short,
then scores the run. Event logs of the queues are in `docs/spy_journal/logs/*.events`.

**Memory by cell** (peak of the simulator processes' memory, sampled every 30 s, from each
run's `memory_samples.csv`; KSM on; one seed each; 2026-10-22). The lowest *free* RAM on a 32 GB
box is in the register.

| Cell | Daemons | Processes | Peak, GB | Peak at sim hour |
|---|---|---|---|---|
| lean H=71 | 124 | 223 | 9.3-9.7 | 0 (start-up) |
| lean H=150 | 216 | 315 | 9.1-10.2 | 3-9 |
| lean H=300 | 393 | 492 | 15.3-16.3 | 6.4-6.9 |
| X0 replica | 419 | 598 | 16.0-17.7 | 7.5-7.7 |
| X1 `core` (113 spies) | 453 | 552 | 18.3 | 10.7 |
| lean H=600 | 746 | 845 | 24.4 | 6-7 |

About 9 GB of that is a start-up spike that does not depend on the size: the 67 hub daemons
(miners, medium nodes, observers, seeds) start at t=0 with their RandomX caches not yet merged
by KSM. After that memory grows with simulated time (blocks, pools, logs). A 12 GB cgroup
with a 24 GB swap file on NVMe ran the X0 cell 7% slower (`docs/PERFORMANCE_AND_SCALE.md`).

**Run-length rule (found 2026-10-23, E18).** On a 32 GB box a cell must stop before simulated hour
~19: at chain height 2112 (about 20.4 h) every daemon re-derives its RandomX cache at once and the box ran out of
memory in seconds, which the driver's 20 s sampling cannot catch. `simbox3` (100 GB) is the only box for longer
cells until the spike has been measured there.
*(2026-10-23 10:40: superseded. The spike was measured on `simbox3` (80 GB in 90 s, E18) and swap cannot cover it; the
`--sim-fixed-randomx-seed` patch removes it (P9, E20) and is now in `monerod-sim` on all three boxes. Cells that stop after about
simulated hour 19 need `make_lean.py --fixed-rx-seed`; the 30 h cells on `phantom` (passed block 2112 at simulated 20:12)
and `simbox2` (20:05) ran through it with 11-13 GB free.)*

**Layout rule.** A spy /24 must hold only spies. Placement is sequential from each
region's first node and prefix sharing packs relays onto its last nodes, so spy pins
beyond 6 /24s at the old default (node 828) collided with honest relays (E12).
`make_lean.py` now refuses such a cell. Cells with 6 or fewer spy /24s were checked
afterwards and are clean.

**Known gaps in the record.**
- Per-run git commits were not recorded before 2026-10-22. What identifies a run is
  its `input_config.yaml` (the cell), its binary provenance and the scorer report;
  the code in `analysis/spy/` and `test_configs/x0/` at the time can be read from git
  history by date (`d858d8d6` 10-21 16:15 added the quarters, `7612d25f` 10-22 00:29
  the probe and warmup options).
- The exploratory scripts behind the gray-list-drain findings were run from a
  scratch directory; they are kept as they ran in `docs/spy_journal/adhoc/`. They are
  not tested and are not maintained.
- The queue event logs are snapshots (`queue_events_<box>_through_<date>.events`), refreshed when the journal is
  updated; the latest are through 2026-10-23 17:49 (`phantom`), 15:29 (`simbox2`) and 14:05 (`simbox3`); the earlier snapshots are kept.
- Entries E1-E12 were written after the fact (section 1); E13 onwards were written when the result came in.
- *(2026-10-23 14:40, from the review)* The `half` ban list at `--ban-coverage 0.5` is tie-broken with the simulation seed
  (open question 9), so a seed replicate of a `half` `tail` cell also changes which 10 of the 21 /24s are banned. One such
  cell has run so far (seed 12345); no replicate is affected yet.

## 3. Run register

Generated by `analysis/spy/run_register.py table` from
`docs/spy_journal/runs/*/meta.json`; do not edit by hand. "Spies / /24s" and
"Honest reachable / /24s" are the cell's population; the model value is for the cell's
own selection rule and its spy layout.

<!-- register:start -->
| Run | Box | Spies / /24s | Honest reachable / /24s | Light out-share (model) | By quarter | Fluff per hop | Stem txs | Wall | Min free RAM (GiB, box) | Exit | Note |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `20261020_021931_spy_estimators_smoke` | phantom | 6 / 6 | 22 / 22 | 0.2030 (0.2176) | 0.197, 0.199, 0.210, 0.206 | 0.221 | 363 | 9m 45s | 12.8 | 0 | I3 pipeline smoke: 48 daemons, 6 spies, 363 txs (docs/SPY_ESTIMATORS.md); not a calibrated preset |
| `20261020_130027_x0_legacy_none_s12345` | phantom | 48 / 6 | 71 / 69 | - (0.3148) | - | - | 0 | 18m 18s | 0.5 | 1 | Pilot, 48 spies (40% of reachable), churn 1 h/1 h; ran out of RAM at sim 1 h 43 m (batched relay waves); stopped, no result |
| `20261020_132230_x0_legacy_none_s12345` | phantom | 48 / 6 | 71 / 69 | 0.3484 (0.3148) | 0.354, 0.348, 0.339, 0.354 | 0.148 | 176 | 1h 36m | 8.9 | 1 | Pilot, 48 spies, churn 1 h/1 h; users sent ~2 txs each (safe-tx-interval); share 0.348 vs target 0.15 FAIL |
| `20261020_165536_x0_legacy_none_s12345_nochurn` | phantom | 48 / 6 | 71 / 69 | 0.2856 (0.3146) | 0.287, 0.286, 0.286, 0.282 | 0.213 | 244 | 1h 15m | 6.6 | 0 | Pilot, 48 spies, no churn; 0.286 FAIL; still ~2 txs per user |
| `20261020_181726_x0_legacy_none_s12345_spies12` | phantom | 12 / 6 | 71 / 69 | 0.1318 (0.1367) | 0.132, 0.131, 0.132, 0.132 | 0.191 | 1828 | 1h 53m | 7.5 | 0 | X0 baseline layout: 12 spies, 2 per /24, no churn; 0.132 PASS (the seed-12345 legacy/none cell) |
| `20261021_004924_x0_legacy_none_s12345_swaptest` | phantom | 12 / 6 | 71 / 69 | 0.1335 (0.1366) | 0.133, 0.136, 0.134, 0.132 | 0.215 | 1919 | 2h 1m | 11.3 | 0 | Swap-as-headroom test of the X0 cell under memory pressure (docs/PERFORMANCE_AND_SCALE.md) [2026-10-22] correction: the run was capped to 12 GB by a cgroup with a 24 GB swap file, so the box-level free RAM shown (11.3 GiB) reflects the cap, not the cell's ~16 GB peak |
| `20261021_102615_x0_legacy_half_s12345` | phantom | 12 / 6 | 71 / 69 | 0.0687 (-) | - | 0.209 | 1887 | 1h 58m | 5.9 | 0 | X0 legacy/half, seed 12345; 0.0687 vs target 0.07 PASS |
| `20261021_122751_lean_legacy_none_h71_k1_s12345` | phantom | 13 / 1 | 71 / 60 | 0.0610 (-) | - | 0.220 | 1061 | 43m 11s | 15.6 | 0 | Lean H=71, 13 spies in 1 /24: the one-spy-slot ceiling (model 0.075) |
| `20261021_131143_lean_24_none_h71_k1_s12345` | phantom | 13 / 1 | 71 / 60 | 0.0212 (0.0181) | - | 0.196 | 1031 | 43m 29s | 15.3 | 0 | Lean H=71 under /24 dedup, 1 h warmup |
| `20261021_135555_lean_legacy_none_h150_k1_s12345` | phantom | 26 / 1 | 150 / 125 | 0.0679 (0.0731) | - | 0.201 | 1006 | 53m 20s | 14.9 | 0 | Lean H=150, flat |
| `20261021_145012_lean_24_none_h150_k1_s12345` | phantom | 26 / 1 | 150 / 125 | 0.0282 (0.0086) | - | 0.192 | 1011 | 53m 5s | 14.9 | 0 | 1 h warmup: the average reads the gray-list drain, not steady state (0.047 to 0.016 by quarter) |
| `20261021_154409_lean_legacy_none_h300_k1_s12345` | phantom | 53 / 1 | 300 / 242 | 0.0707 (0.0730) | 0.073, 0.072, 0.070, 0.067 | 0.194 | 1080 | 1h 22m | 8.6 | 0 | Lean H=300, 393 daemons; min free RAM 8.1-8.8 GB, no swap |
| `20261021_170823_lean_24_none_h300_k1_s12345` | phantom | 53 / 1 | 300 / 242 | 0.0459 (0.0045) | 0.081, 0.046, 0.033, 0.024 | 0.196 | 1056 | 1h 21m | 7.9 | 0 | 1 h warmup: drain, 0.081 falling to 0.024 by quarter |
| `20261021_183133_lean_24_none_h150_k1_w6h_s12345` | phantom | 26 / 1 | 150 / 125 | 0.0145 (0.0086) | 0.016, 0.014, 0.015, 0.013 | 0.192 | 1117 | 1h 20m | 14.3 | 0 | 6 h warmup (80 min wall): plateau 0.0145, 79% below legacy; model 0.0086, so 1.7x unexplained |
| `20261021_195300_lean_24_none_h300_k1_p3_s12345` | phantom | 53 / 1 | 300 / 242 | 0.0467 (0.0045) | 0.083, 0.046, 0.034, 0.025 | 0.207 | 1082 | 1h 23m | 10.3 | 0 | Probe cell (first/last 3 relays dump peer lists, net.p2p DEBUG): gray-list drain table in X0_CALIBRATION.md |
| `20261021_211815_lean_legacy_none_h300_k6_s12345` | phantom | 53 / 6 | 300 / 242 | 0.2453 (0.1359) | 0.246, 0.247, 0.246, 0.243 | 0.203 | 1069 | 1h 21m | 11.6 | 0 | k=6 legacy anchor, flat 0.246; model 0.136, recency explains part |
| `20261021_224109_lean_24_none_h300_k6_s12345` | phantom | 53 / 6 | 300 / 242 | 0.1026 (0.0264) | 0.137, 0.106, 0.090, 0.080 | 0.208 | 964 | 1h 17m | 12.8 | 0 | 1 h warmup, drain: 0.137 falling to 0.080 by quarter; model 0.026 |
| `20261021_235957_lean_legacy_none_h600_k1_s12345` | phantom | 106 / 1 | 600 / 480 | 0.0749 (0.0726) | 0.069, 0.081, 0.077, 0.072 | 0.216 | 1022 | 2h 14m | 1.7 | 0 | 746 daemons on 32 GB + 8 GB swap allowance: min free RAM 1.75 GB vs the 1.5 GB guard; swap +1.8 GB; legacy flat at the model |
| `20261022_021628_lean_24_none_h600_k1_s12345` | phantom | 106 / 1 | 600 / 480 | 0.0611 (0.0024) | 0.009, 0.104, 0.072, 0.055 | 0.196 | 1023 | 2h 12m | 1.5 | 0 | 746 daemons, min free 1.57 GB; 1 h warmup so drain-dominated (0.009, 0.104, 0.072, 0.055); above the 0.083 one-slot ceiling in Q2 (fallback path) |
| `20261022_031422_lean_legacy_none_h71_k1_s12345` | simbox2 | 13 / 1 | 71 / 60 | 0.0614 (0.0750) | 0.067, 0.062, 0.060, 0.059 | 0.218 | 688 | 36m 28s | 21.3 | 0 | simbox2 validation against phantom's 0.061 for the same cell (simbox2 rebuilt on Ubuntu 24.04.5 the same day) |
| `20261022_035357_x0_legacy_none_s23456` | simbox2 | 12 / 6 | 71 / 67 | 0.1385 (0.1371) | 0.137, 0.139, 0.139, 0.139 | 0.194 | 1845 | 1h 55m | 11.9 | 0 | X0 legacy/none replicate |
| `20261022_043220_x0_24_none_s12345` | phantom | 12 / 6 | 71 / 69 | 0.0703 (0.0825) | 0.073, 0.072, 0.070, 0.067 | 0.203 | 1897 | 1h 55m | 10.9 | 0 | X0 24/none, seed 12345; about 48% below legacy/none (target about 70%); estimators run on this cell: sp_r precision 1.00, recall 0.071 |
| `20261022_055131_x0_legacy_half_s23456` | simbox2 | 12 / 6 | 71 / 67 | 0.0689 (0.1370) | 0.070, 0.069, 0.068, 0.068 | 0.190 | 1865 | 1h 55m | 12.1 | 0 | X0 legacy/half replicate |
| `20261022_062954_x0_24_half_s12345` | phantom | 12 / 6 | 71 / 69 | 0.0347 (0.0825) | 0.037, 0.036, 0.034, 0.033 | 0.199 | 1845 | 1h 57m | 11.0 | 0 | X0 24/half, seed 12345; 49% below legacy/half |
| `20261022_074903_x0_legacy_none_s34567` | simbox2 | 12 / 6 | 71 / 69 | 0.1330 (0.1363) | 0.133, 0.132, 0.134, 0.134 | 0.194 | 1844 | 1h 54m | 11.6 | 0 | X0 legacy/none replicate |
| `20261022_083054_x0_24_none_s23456` | phantom | 12 / 6 | 71 / 67 | 0.0734 (0.0845) | 0.080, 0.076, 0.070, 0.069 | 0.193 | 1887 | 1h 57m | 10.5 | 0 | X0 24/none replicate |
| `20261022_094537_x0_legacy_half_s34567` | simbox2 | 12 / 6 | 71 / 69 | 0.0632 (0.1364) | 0.065, 0.064, 0.062, 0.062 | 0.235 | 1841 | 1h 55m | 11.6 | 0 | X0 legacy/half replicate; below the pre-registered 0.066-0.072 (P2), fluff per hop 0.235 |
| `20261022_103027_x0_24_half_s23456` | phantom | 12 / 6 | 71 / 67 | 0.0373 (0.0845) | 0.043, 0.039, 0.035, 0.032 | 0.197 | 1804 | 1h 57m | 9.1 | 0 | X0 24/half replicate; inside the pre-registered 0.031-0.038 (P2); falls 0.043 to 0.032 across the window |
| `20261022_114249_lean_24_none_h300_k6_w6h_s12345` | simbox2 | 53 / 6 | 300 / 242 | 0.0598 (0.0264) | 0.065, 0.061, 0.059, 0.055 | 0.192 | 1092 | 1h 52m | 12.7 | 0 | P1: long-warmup k=6 dedup cell (6.4 h after the last relay start); see E13 |
| `20261022_122958_x0_24_none_s34567` | phantom | 12 / 6 | 71 / 69 | 0.0690 (0.0825) | 0.073, 0.069, 0.068, 0.067 | 0.206 | 1849 | 1h 58m | 10.7 | 0 | X0 24/none replicate; inside the pre-registered 0.066-0.078 (P2) |
| `20261022_134108_lean_24_none_h300_k6_w6h_s23456` | simbox2 | 53 / 6 | 300 / 240 | 0.0574 (0.0265) | 0.060, 0.058, 0.057, 0.055 | 0.193 | 1092 | 1h 52m | 12.6 | 0 | E13 replicate (P4): inside 0.050-0.070, Q4 8% below Q1 |
| `20261022_143050_x0_24_half_s34567` | phantom | 12 / 6 | 71 / 69 | 0.0382 (0.0825) | 0.042, 0.040, 0.036, 0.035 | 0.194 | 1865 | 1h 57m | 11.0 | 0 | X0 24/half replicate; 0.0382, just above the pre-registered 0.031-0.038 (P2 miss by 0.0002) |
| `20261022_153451_lean_legacy_none_h300_k6_s23456` | simbox2 | 53 / 6 | 300 / 240 | 0.2485 (0.1362) | 0.238, 0.247, 0.254, 0.254 | 0.175 | 1024 | 1h 18m | 13.1 | 0 | E13 legacy partner (P4): inside 0.22-0.27; fluff per hop 0.175 |
| `20261022_163001_lean_24_none_h300_k1_w6h_m113_s12345` | phantom | 113 / 1 | 300 / 242 | 0.0352 (0.0045) | 0.045, 0.037, 0.032, 0.027 | 0.195 | 1082 | 2h 1m | 9.5 | 0 | X1 core, no list (P3): light share 0.0352 vs predicted 0.005-0.01, carried by relays (0.041; users 0.006); see E14 |
| `20261022_165425_lean_24_none_h300_k6_w6h_s34567` | simbox2 | 53 / 6 | 300 / 243 | 0.0529 (0.0262) | 0.059, 0.053, 0.051, 0.049 | 0.209 | 1076 | 1h 51m | 12.5 | 0 | E13 replicate (P4): inside 0.050-0.070, Q4 16% below Q1 |
| `20261022_183408_lean_24_none_h300_k21_w6h_m2_n600_s12345` | phantom | 42 / 21 | 300 / 242 | 0.1946 (0.0822) | 0.198, 0.195, 0.195, 0.191 | 0.225 | 1092 | 1h 53m | 11.9 | 0 | X1 tail, no list (P3): light share 0.1946 vs predicted 0.07-0.08, relays 0.222, users 0.055; sp_r recall 0.038, precision 1.00; see E15 |
| `20261022_184706_lean_legacy_none_h300_k6_s34567` | simbox2 | 53 / 6 | 300 / 243 | 0.2519 (0.1361) | 0.245, 0.252, 0.256, 0.253 | 0.187 | 1065 | 1h 20m | 13.4 | 0 | E13 legacy partner (P4): inside 0.22-0.27 |
| `20261022_201141_lean_24_none_h300_k1_w6h_m53_s12345` | simbox2 | 53 / 1 | 300 / 242 | 0.0173 (0.0045) | 0.021, 0.018, 0.016, 0.014 | 0.203 | 1092 | 1h 52m | 12.6 | 0 | P5 diagnostic: core with 53 spies; 0.0173, relays 0.0197, users 0.0068; share per spy matches the 113-spy cell |
| `20261022_202954_lean_24_none_h300_k1_w6h_p3_m113_s12345` | phantom | 113 / 1 | 300 / 242 | 0.0365 (0.0045) | 0.048, 0.038, 0.032, 0.029 | 0.199 | 1074 | 1h 59m | 9.6 | 0 | E16 probe: X1 core with the first/last 3 relays of each start order dumping peer lists and logging net.p2p DEBUG; same seed as E14, share 0.0365 vs 0.0352 (logging does not move it) |
| `20261022_220525_lean_24_none_h300_k1_w6h_m26_s12345` | simbox2 | 26 / 1 | 300 / 242 | 0.0095 (0.0045) | 0.011, 0.009, 0.009, 0.008 | 0.200 | 1096 | 1h 50m | 13.3 | 0 | P5 diagnostic: X1 core with 26 spies in the one /24 (6.4 h warmup, seed 12345); 0.0095 inside the 0.006-0.015 count-reading range |
| `20261022_222209_lean_legacy_none_h71_k1_s12345` | simbox3 | 13 / 1 | 71 / 60 | 0.0641 (0.0750) | 0.067, 0.067, 0.063, 0.059 | 0.218 | 1093 | 1h 19m | 86.0 | 0 | P6a platform check (H=71 legacy, seed 12345): 0.0641 inside 0.055-0.066; phantom 0.061, simbox2 0.0614; wall 79 min vs 43 phantom and 36 simbox2 |
| `20261022_223103_lean_24_half_h300_k1_w6h_m113_s12345` | phantom | 113 / 1 | 300 / 242 | 0.0162 (0.0045) | 0.022, 0.017, 0.014, 0.011 | 0.192 | 1078 | 2h 0m | 9.8 | 0 | E17: X1 core with the spy ban list on half the honest nodes (list in full, seed 12345, 6.4 h warmup); 0.0162 = 0.46 x the no-list cell |
| `20261022_234237_lean_24_none_h300_k1_w24h_m113_s12345` | simbox3 | 113 / 1 | 300 / 242 | - (0.0045) | - | - | 0 | 4h 3m | 9.8 | 1 | E18: the 24 h-warmup core cell (no list) on the UNPATCHED binary, TRIPPED by the driver at 03:46 (350 MB free): the summed process memory went from 16.6 GB to 79.9 GB between two 35 s samples at simulated 21.4 h, as the chain reached block 2112 (the RandomX seed change) and every daemon re-derived its cache; no result. Rerun with --sim-fixed-randomx-seed as P7b |
| `20261022_235712_lean_24_none_h300_k1_w16h_m113_s12345` | simbox2 | 113 / 1 | 300 / 242 | 0.0099 (0.0045) | 0.010, 0.010, 0.009, - | 0.214 | 501 | 2h 37m | 10.0 | 137 | E18 / P7a, PARTIAL: killed by the kernel OOM (exit 137) at sim 20:26:35 = block 2112, the RandomX seed change; scored window is 18-20.4 h of 18-22 h. Light share 0.0099 (provisional) |
| `20261023_003351_lean_24_none_h300_k1_w24h_m113_s12345` | phantom | - / - | - / - | - (-) | - | - | - | - | 10.3 | - | E18: the 24 h-warmup core cell (no list, unpatched binary) STOPPED by the agent at 02:40 at simulated 17.8 h, before its window and before block 2112, after simbox2's copy of the 16 h cell was OOM-killed at that block (decision 10-23 02:40); no result; the same cell was rerun with --sim-fixed-randomx-seed (P7b, simbox3) |
| `20261023_024331_lean_24_none_h300_k21_w13h_m2_n600_s12345` | phantom | 42 / 21 | 300 / 242 | 0.1662 (0.0822) | 0.167, 0.169, 0.167, 0.163 | 0.211 | 1099 | 2h 37m | 11.5 | 0 | E19 / P8a: X1 tail, no list, 13 h warmup (stop 19 h, window 15-19 h), seed 12345; 0.1662 vs 0.1946 at the 6 h warmup (E15); flat by quarter |
| `20261023_024332_lean_24_half_h300_k21_w13h_m2_n600_c50_s12345` | simbox2 | 42 / 21 | 300 / 242 | 0.1309 (0.0822) | 0.130, 0.130, 0.130, 0.133 | 0.207 | 1096 | 2h 32m | 12.5 | 0 | E19 / P8b: X1 tail, ban list on half the nodes naming 10 of 21 /24s, 13 h warmup, seed 12345; 0.1309 = 0.79 x the no-list cell |
| `20261023_035553_lean_24_none_h71_k1_w18h_fx_s12345` | simbox3 | 13 / 1 | 71 / 60 | 0.0094 (0.0181) | 0.011, 0.008, 0.009, 0.010 | 0.214 | 1147 | 3h 29m | 86.5 | 0 | E20 / P9: patched monerod-sim (--sim-fixed-randomx-seed on every daemon), H=71, to 22.5 h simulated; passed block 2112 at sim 19:55 with no memory step; all 124 daemons end at height 2188 |
| `20261023_052647_lean_24_none_h300_k21_w13h_m2_n600_s23456` | simbox2 | 42 / 21 | 300 / 240 | 0.1626 (0.0831) | 0.165, 0.166, 0.161, 0.159 | 0.192 | 1099 | 2h 33m | 12.5 | 0 | E21 / P10b: seed replicate of the 13 h tail cell (seed 23456); 0.1626 vs 0.1662 for seed 12345 |
| `20261023_052647_lean_24_none_h300_k21_w13h_p3_m2_n600_s12345` | phantom | 42 / 21 | 300 / 242 | 0.1626 (0.0822) | 0.163, 0.162, 0.164, 0.162 | 0.191 | 1097 | 2h 37m | 11.5 | 0 | E21 / P10a: the tail probe (first/last 3 relays of each start order log picks and dump lists), 13 h warmup, seed 12345; 0.1626 vs 0.1662 without the probe |
| `20261023_072719_lean_24_none_h300_k1_w24h_m113_fx_s12345` | simbox3 | 113 / 1 | 300 / 242 | 0.0044 (0.0045) | 0.004, 0.005, 0.004, 0.004 | 0.199 | 1093 | 6h 33m | 76.6 | 0 | E22c/P7b: the 24 h-warmup core cell (no list) on the patched binary, 1.6x slower than the 32 GB boxes; light 0.0044 at the model (0.0045), relays 0.0050; P7b's light range 0.005-0.014 missed by 0.0006 below (its floor sat above the model), E18's relay extrapolation 0.005-0.007 hit at the edge; 1 of 40 twenty-tx users exposed; no memory step at block 2112 (daemons 15.6-16.0 GB from hour 6 to 24) |
| `20261023_080537_lean_24_half_h300_k1_w24h_m113_fx_s12345` | simbox2 | 113 / 1 | 300 / 242 | 0.0025 (0.0045) | 0.002, 0.003, 0.003, 0.002 | 0.197 | 1090 | 4h 4m | 9.7 | 0 | E22 / P11b: X1 core with the spy ban list on half the honest nodes, 24 h warmup with --sim-fixed-randomx-seed (stop 30 h, window 26-30 h), seed 12345; 0.0025 flat by quarter (6 h warmup, E17: 0.0162); adopters 0.0, non-adopters 0.0148 (with the miners); relays 0.0027, users 0.0019; sp_r made no guess (0 of 1,015 user txs stemmed to a spy), 0 of 40 exposed; relay curve reaches the half-list model (0.0023) by hour 28; min free RAM 10.0 GB over 30 simulated hours |
| `20261023_081108_lean_24_none_h300_k21_w24h_m2_n600_fx_s12345` | phantom | 42 / 21 | 300 / 242 | 0.1572 (0.0822) | 0.159, 0.159, 0.157, 0.153 | 0.196 | 1099 | 3h 47m | 10.7 | 0 | E22 / P11a: X1 tail, no list, 24 h warmup with --sim-fixed-randomx-seed (stop 30 h, window 26-30 h), seed 12345; 0.1572 (6 h warmup 0.1946, 13 h 0.1662); relays 0.1805, users 0.0431; sp_r precision 1.00, recall 0.035 at its ceiling, 12 of 40 exposed; min free RAM 10.9 GB over 30 simulated hours on a 32 GB box |
| `20261023_123723_lean_24_none_h300_k21_w13h_m8_n600_s12345` | simbox2 | 168 / 21 | 300 / 242 | 0.1749 (0.0822) | 0.179, 0.178, 0.174, 0.169 | 0.205 | 1073 | 2h 49m | 3.4 | 0 | E24/P13b: tail at 8 spies per /24 (168 spies, 508 daemons); light 0.1749 against the 2-per-/24 cell's 0.1662 (E19): P13's dilution reading refuted (threshold 0.16); relays 0.36 at hour 5 falling to 0.18 at hour 19 (not stationary; -30% over hours 8-19 against -12% at m=2); 17 of 40 users exposed; free RAM 3.4 GB at boot (sim 10 min), 8.5 GB after the first simulated hour, so the 6 GB clause is missed |
| `20261023_123723_lean_legacy_none_h300_k21_w13h_m2_n600_s12345` | phantom | 42 / 21 | 300 / 242 | 0.2857 (0.1221) | 0.286, 0.283, 0.286, 0.288 | 0.224 | 1099 | 2h 35m | 11.5 | 0 | E23/P12: the legacy (v0.18.4.2 selection) partner of the 13 h tail cell (E19: 0.1662); light 0.2857 flat, 2.34x the legacy model (0.122); relays 0.3256, no decay from hour 5 to 19 and a stationary start-order gradient (quarters 0.18/0.27/0.37/0.48). P12's 0.16-0.26 missed above; the 24/legacy ratio is 0.58, below the predicted 0.65-1.0: stock /24 dedup cuts this diversified fleet's share by 42% |
| `20261023_140542_lean_24_none_h300_k1_w6h_m113_s23456` | simbox3 | 113 / 1 | 300 / 240 | 0.0428 (0.0046) | 0.055, 0.045, 0.039, 0.033 | 0.203 | 1083 | 3h 8m | 77.5 | 0 | E10 replicate (filler): core at a 6 h warmup, seed 23456, on simbox3; light 0.0428 against 0.0352 at seed 12345 on phantom (the transient's tail at hours 8-12, so seed spread here is spread in the drain, not in a steady state) |
| `20261023_151500_lean_24_none_h300_k21_w13h_m1_n600_s12345` | phantom | 21 / 21 | 300 / 242 | 0.1978 (0.0822) | 0.197, 0.196, 0.201, 0.198 | 0.192 | 1099 | 2h 32m | 12.2 | 0 | E24/P13a: tail at 1 spy per /24 (21 spies); light 0.1978 flat against 0.1662 at 2 per /24 (E19) and 0.1749 at 8 (P13b): P13a's dilution range 0.18-0.27 hit, but the three points are not 1/m and the E24 candidate-count expectation (0.16-0.18) was wrong; relays 0.225, users 0.0605 |
<!-- register:end -->

## 4. Entries

### E1. Instruments (2026-10-19 to 10-20)

Built before any calibration run: the relay log (I1, `5be8b1c0`), the spy-side
estimators (I3, `2cd4bb75`) and the X0 lab with the subnet-dedup patch (`e24ee4a6`).
The estimators' smoke run (`20261020_021931_spy_estimators_smoke`: 48 daemons, 6 spies,
363 txs) checked the pipeline, not a preset: 363 of 363 origins matched the recorded
sender and no stem hop lacked its receipt.

### E2. Pilots at 40% spies, with and without churn (2026-10-20)

Four runs on the 2024 preset (48 spies, 8 per /24, 40% of reachable IPs, Oct 2024's
figure), `legacy` selection, no list. The first ran out of RAM at sim 1 h 43 m
(relays started in batched waves; fixed to a linear start, `bdb04e77`). With churn
(1 h on / 1 h off) the light-node outbound share was 0.348, without churn 0.286: both
about twice the 0.15 target, close to the spies' share of reachable IPs (0.40), as
Kopyciok et al.'s 15.26% followed their 14.74% of IPs. Churn was switched off for the
first experiments (it cut transactions ~10x and who churns on mainnet is unknown).
**Flaw found afterwards:** the cells were expanded without `--no-safe-tx-interval`,
so users sent one transaction per 3,412 s (about 2 each) and the stem statistics rest
on 176 and 244 transactions. Fixed in `1b2c119e`; the slot shares do not depend on the
transaction rate.

### E3. The X0 baseline layout: 12 spies, no churn (2026-10-20 to 10-21)

**Prediction (in advance):** spies at 15% of reachable IPs (Kopyciok, Feb 2025) give
an outbound share near 0.15 under `legacy`; the model said 0.137.
**Result:** 12 spies in 6 /24s (`..._spies12`): 0.132, PASS, with 1,822 transactions
and 0.191 fluff per hop (implied 5.2 hops, PASS). `legacy/half` (ban list on half the
honest nodes, seed 12345, run `20261021_102615`): 0.0687 against 0.07, PASS.
These two, plus the 0.1385 and 0.133 from `simbox2` (E10), are the `legacy` side of X0.
Also on 10-21 00:49, the same cell run inside a 12 GB cgroup with a 24 GB swap file
(`..._swaptest`; `docs/PERFORMANCE_AND_SCALE.md`, "Swap as headroom"): wall time
2 h 1 m against 1 h 53 m, light-node outbound share 0.1335 against 0.1318. The
register's free-RAM column is the box's, so it reads high for this run. **Correction
recorded there:** the 8.5 million "swap-ins" first reported were major page faults; the
swap-ins were 5.0 million.

### E4. Lean cells: can the /24 effect be read at a mainnet-like ratio? (2026-10-21)

**Question.** The X0 replica has 69 honest /24s facing 6 spy /24s; mainnet has about
3,700 facing 6-9, so the replica understates what dedup does (the model: -39% against
the target's -70%). An unreachable node is in nobody's peer list, so the unreachable
majority can be cut to 40 users and the reachable honest set grown (`make_lean.py`).
**Cells** at H=71, 150, 300 and 600 reachable honest daemons, `legacy` and `24`, one
dense spy /24 (and at H=300, six); see the register.
**Result, `legacy`:** flat across the window and near the model: 0.061, 0.0679,
0.0707, 0.0749 at H=71, 150, 300, 600 (model 0.073-0.075). With one dense spy /24 a
node can hold only one spy slot, so these are not the X0 0.15 baseline; the k=6 cells
are: 0.2453 measured against a model of 0.136, of which a Monte Carlo of the nodes'
real recency-biased picks explains 0.186; about 1.3x is unexplained.
**Result, `24`, 1 h warmup:** far above the model and falling across the window (H=300:
0.081, 0.046, 0.033, 0.024 by quarter against a model of 0.0045). Read by the last
quarter, not the average (E5).
**Stems** were on target in every cell: 0.19-0.22 fluff per hop, about 5 implied hops,
about 1,000 transactions.

### E5. The /24 excess is the gray list draining (2026-10-21 evening)

**Hypothesis tested (and rejected):** the early excess comes from small first peer
lists. A probe cell (`..._h300_k1_p3`: the first and last 3 relays of each start order
dump peer lists every 30 s and log `net.p2p` at DEBUG) showed the startup picks are
fine (216-entry list, 139 /24 candidates, 2 spies in 144).
**Finding.** monerod fills 8 of its 12 outbound slots from the white list and the
rest from the gray list, which is picked uniformly. Honest peers leave the gray list as
the white list grows to all 352 IPs; spies stay, because the dedup skips them after the
first in the /24. Per relay age, mean gray-list size and spy picks:

| Relay age | Gray list | Spy picks |
|---|---|---|
| 0-30 min | 205 | 3 of 348 |
| 30-60 min | 145 | 3 of 219 |
| 60-90 min | 90 | 27 of 223 |
| 90-120 min | 57 | 42 of 155 |
| 120-150 min | 20 | 20 of 89 |
| over 150 min | 1 | 0 of 5 |

With no unconnected /24 candidate left, 39 of 39 picks were spies (step 0 finds none and
step 1 falls back to the undeduplicated list); with one candidate, 23 of 38. After the
drain, white-list picks are about uniform (12 spy picks in 1,707 against 7.9 expected);
a Monte Carlo of the real selection over the late white lists gives 0.0049 against the
uniform 0.0045. The spy connections made in that phase age out over hours (~1.5 h per
slot), which is the decay across the window.
**Consequence for method.** A `24` cell needs a warmup long enough for every relay to
leave the drain and its early connections to age out: use at least 6 h after the last
relay start. With 6 h at H=150 the share is flat (0.016, 0.014, 0.015, 0.013) at 0.0145,
79% below `legacy`'s 0.0679.
**Still open:** 0.0145 is 1.7x the model's 0.0086. Ruled out: connection lifetime
(spy and honest stretches are both 8.3 windows), recency, the startup list; inbound-
blocked /24s explain about 12%. About 1.5x is unexplained and the probe cannot resolve
it (10 spy picks against 6 expected).
Mainnet's gray list is large and refilled by churn, so this is a property of the small,
static, no-churn lab, not a prediction about the network.

### E6. k=6 cells (2026-10-21 night)

Six spy /24s at H=300. `legacy`: flat 0.2453. `24` with a 1 h warmup: 0.137, 0.106,
0.091, 0.080 by quarter, still draining; model 0.0264. The model is a ceiling for k>1
(it assumes every spy is in every list), so a measurement above it is not a failure of
the rule.

### E7. Scale: 746 daemons on 32 GB (2026-10-22 00:00-04:30)

**Question.** Does 32 GB plus swap carry the 746 daemons of H=600, mainnet's /24 ratio
with one dense spy /24? (Decides whether the 1 TB box is needed for this and whether
an Optane swap drive is worth buying.)
**Result.** Both H=600 cells (`legacy`, `24`) ran to the end, 134 min wall each, exit 0.
Minimum free RAM 1,750 MB and 1,574 MB against the 1,500 MB guard; swap grew by at most
about 2 GB of the 8 GB allowance, so swap throughput did not matter and resident
memory did. It fits, with 74-250 MB to spare; a longer cell at this size would
very likely trip.
`legacy`: 0.0749 flat (model 0.073). `24`, 1 h warmup: 0.0611, by quarter 0.009, 0.104,
0.072, 0.055. The peak is later than at H=300 and exceeds the 0.083 one-slot ceiling,
which needs the fallback path of E5; a plausible reading is that the relay ramp
(3.3 h) leaves many relays young at the window's start, so they drain during it. Not
tested (no probe in this cell). The cell cannot answer the dedup question; it shows
the `legacy` side holds at 746 daemons.

### E8. Estimators at replica scale (2026-10-22 11:00)

`spy_estimators.py` on the finished `x0_24_none_s12345` (419 daemons): 3 min 17 s,
3.9 GB. **Predictions (the plan's section 2.3):** unreachable senders precision about
1, recall about p. **Result:** `sp_r` precision 1.000 and recall 0.071 on 1,804
unreachable-sender transactions, equal to the ground-truth first-hop ceiling (128 of
1,795 = 0.071) and to the cell's outbound spy share (0.0703). 35 of 69 unreachable
senders with 20 or more transactions had at least one transaction attributed. Fluff-
epoch inference (`fs`) is near zero (precision 0.005). The 12 spies saw all 1,897
transactions.

### E9. `simbox2` commissioned (2026-10-22)

Ubuntu 22.04.5 to 24.04.5 (`apt full-upgrade`, HWE kernel 6.8, `do-release-upgrade`,
two reboots; `stunnel4`/`aznfs` half-configured after the upgrade and fixed by the
reboot), simulator rebuilt from `feat/spy-relay-log` at `7612d25f` with
`setup.sh --clean --sim-binary` (17 min), KSM set by hand. **Validation:**
`lean_legacy_none_h71_k1_s12345` reads 0.0614 against 0.061 on `phantom`, with
quarters 0.067, 0.062, 0.061, 0.059 against 0.070, 0.063, 0.060, 0.052. The generated
cell yaml is byte-identical on the two boxes. The two boxes are used interchangeably
from here; both are recorded in the register.

### E10. X0 replicates (2026-10-22; all 12 replica cells have 3 seeds)

Light-node outbound share by cell and seed. Means: `legacy/none` 0.1345, `legacy/half`
0.0669, `24/none` 0.0709, `24/half` 0.0367 (spreads 0.006, 0.0057, 0.0044, 0.0035).

| Cell | 12345 | 23456 | 34567 | Target |
|---|---|---|---|---|
| `legacy/none` | 0.132 | 0.1385 | 0.133 | ~0.15 |
| `legacy/half` | 0.0687 | 0.0689 | 0.0632 | ~0.07 |
| `24/none` | 0.0703 | 0.0734 | 0.0690 | ~70% below `legacy/none` |
| `24/half` | 0.0347 | 0.0373 | 0.0382 | ~70% below `legacy/half` |

**So far.** `legacy` has all three seeds in both cells and passes both targets:
`legacy/none` within 0.006 of each other (4% of the mean, 0.9x the target),
`legacy/half` 0.0687, 0.0689, 0.0632 (mean 0.0669, spread 0.0057 = 8.5% of the mean, 0.96x
the target). The third `legacy/half` seed also has more fluff per hop than any other
cell (0.235 against 0.19-0.22; implied 4.3 hops, still inside the 1.5x window around 5). `24/none` is 47% below `legacy/none` (0.0709 against 0.1345) and `24/half` 45% below
`legacy/half` (0.0367 against 0.0669); each of the six `24` cells is 44-48% below its `legacy` mean, which is 1.7-1.8x
above the 0.04 the target implies, so outside the 1.5x window and needing a written reason. The
reason: this replica has 69 honest /24s against 6 spy /24s and the model puts stock
dedup at 0.083 against 0.137 for `legacy`, 39% lower, not 70%; the measurement is 85-89%
of the model for the `24` cells and nearly flat across the window (the replica shows
only a weak tail of the drain of E5: Q1 to Q4 falls 8% in `24/none` 12345 but 25% in
`24/half` 23456, 0.043 to 0.032). The -70% claim is about mainnet's ratio; the cell that tests it is
the long-warmup k=6 cell (section 5, P1).
Both defenses together (`24/half` against `legacy/none`) are -74%; that is not the
dedup effect.
Embargo rate reads 0.0 in every cell and the plan gives no reference figure (section 6).

### E11. Spy-/24 placement and the ban-list coverage knob (2026-10-22)

Generating a 21-/24 spy fleet at H=300 for X1 showed 12 of the 21 spy /24s also
holding an honest relay (the layout rule in section 2). Earlier cells were checked and are clean
(X0 `24/none`, lean H=300 k=6, H=600). `make_lean.py` now takes `--spy-node0`,
`--spies-per-subnet` and `--ban-coverage`, and refuses a cell with a mixed /24.
`scripts/spy_ban_list.py --coverage F` lists the densest round(F x n) spy /24s,
ties broken by a seeded shuffle (the real list names the dense fleet and part of the
tail); the default 1.0 reproduces the X0 list byte for byte (checked).

### E12. X1 candidate presets (2026-10-22, generated, not run)

At H=300 with `24` selection and a 6.4 h warmup (12 h run), spy /24 count chosen to
keep mainnet's spy : honest /24 ratio:
- **core:** 113 spies in 1 /24 (27% of reachable IPs, the 2026-09 machine share);
  ratio 1 : 242 (mainnet's dense core 9 : 3,732 = 0.24%; ours 0.41%); model 0.0045.
- **tail:** 42 spies in 21 /24s of 2 (the ban list's tail: 322 /24s of 1-3 IPs,
  8.6% of honest /24s; ours 8.7%), model 0.082; with the list at 50% adoption and 50%
  coverage a further `lean_24_half_..._c50` cell.
**Not representable with variant R spies:** the poisoned peer lists and the 8 ports per
IP of the 2026-09 fleet (the spy answers its handshake itself and pipes to a backend:
plan item I2, splice mode, unbuilt).

### E13. The long-warmup k=6 dedup cell (2026-10-22 11:42-13:36, `simbox2`)

**Question.** Does /24 dedup cut the spy share by about 70% at a larger honest set, once
the gray-list drain (E5) is out of the window? **Setup:** `lean_24_none_h300_k6_w6h_s12345`:
H=300 reachable honest (393 daemons), 53 spies in 6 /24s, `24` selection, activity from 8 h
to 12 h, i.e. 6.4 h after the last relay start. 112 min wall, exit 0, 12,954 MB lowest
free RAM, 1,092 stem transactions, 0.192 fluff per hop (implied 5.2 hops).
**Prediction (P1, filed in advance):** 0.026-0.060, flat by quarter, 75-90% below the
`legacy` k=6 value.
**Result:** light-node outbound share **0.0598**; by quarter 0.0647, 0.0613, 0.0585,
0.0549. That is 76% below the measured `legacy` k=6 value (0.2453, flat), and 2.3x the model
(0.0264). All three P1 criteria hold, each at its edge: 0.0598 against an upper bound of
0.060, a Q1-to-Q4 fall of 15% against a limit of 20%, and -75.6% against -75%.
**Reading.**
- The dedup target holds at this ratio: -76% against about -70%. The model's *ratio*
  (-81%) is within five points of the measured one even though both measured levels sit
  above the model (`legacy` 1.8x, `24` 2.3x; at H=150 the `24` gap was 1.7x).
- The share is still falling across the window, so 0.0598 is probably not the plateau;
  a longer warmup or a probe cell would show where it stops.
- This cell has 6 spy /24s against 242 honest ones (2.5%), ten times mainnet's 9 against
  3,732 (0.24%). By the model the effect at mainnet's ratio is at least as large, but that
  is not measured.
- The `legacy` partner ran with a 1 h warmup and a different box; `legacy` is flat, so
  this should not matter, but the replicates below pair them by seed.
- One seed at first. Seeds 23456 and 34567 are queued, with their `legacy` partners (P4).

| Seed | `24`, 6.4 h warmup | By quarter | `legacy` (1 h warmup) | Dedup effect |
|---|---|---|---|---|
| 12345 | 0.0598 | 0.0647, 0.0613, 0.0585, 0.0549 | 0.2453 | -76% |
| 23456 | 0.0574 | 0.0603, 0.0576, 0.0566, 0.0554 | 0.2485 | -77% |
| 34567 | 0.0529 | 0.0590, 0.0534, 0.0505, 0.0494 | 0.2519 | -79% |
| mean | 0.0567 | | 0.2486 | -77% |

*2026-10-22 15:36:* seed 23456 reads 0.0574, inside P4's 0.050-0.070, with Q4 8% below Q1
(P4: 5-25%). The two seeds differ by 4%.
*2026-10-22 18:48:* seed 34567 reads 0.0529 (P4 0.050-0.070 hit; Q4 16% below Q1, inside
5-25%). The three `24` seeds: mean 0.0567, spread 0.0069 (12% of the mean), all still
falling across the window.
*2026-10-22 20:10:* the seed-34567 `legacy` partner reads 0.2519 (P4 hit), so the dedup
effect for that seed is -79%. **Three seeds: -76%, -77%, -79% (mean -77%), inside P4's -70% to
-80% for all three.** This closes the third X0 target at a larger honest set: the lean k=6
cell meets it (-77% against about -70%) where the 69-/24 replica cannot (-45% to -47%, E10).
Caveats unchanged: the `24` shares are still falling across the window, the spy /24 ratio is
ten times mainnet's, and E14 shows the lab's relays hold more spies than the model gives.
*2026-10-22 16:56:* the seed-23456 `legacy` partner reads 0.2485 (flat: 0.238, 0.247, 0.254,
0.254; P4 0.22-0.27), so the dedup effect for that seed is -77% (P4: -70% to -80%).

### E14. X1 `core`, no list: the lab's relays hold spies the model does not predict (2026-10-22 16:30-18:34, `phantom`)

**Setup.** `lean_24_none_h300_k1_w6h_m113_s12345`: H=300 reachable honest (453 daemons with the
113 spies), 113 spies in one /24 (27% of reachable IPs), stock `24` selection, 40 unreachable
users, activity 8 h to 12 h. 122 min wall, exit 0, 9,771 MB lowest free RAM, 1,082 stem
transactions, 0.195 fluff per hop. Estimators: 2 min 20 s, 2.9 GB.
**Prediction (P3, in advance):** outbound share 0.005-0.01 (model 0.0045), `sp_r` precision
1.00, recall equal to the first-hop ceiling, under 5% of 20-transaction senders exposed.
**Result.**
- **Light-node outbound share 0.0352**, by quarter 0.045, 0.0375, 0.0319, 0.0272: 3.5-7x
  the predicted range, 7.8x the model, and still falling. **Missed.**
- By class: **relays 0.0413**, users 0.006, observers 0.0045, medium hubs 0.0035, miners 0.1169
  (5 nodes), seeds' inbound 0.4063. The users and observers sit at the model; the relays carry
  the excess. By start order the relays read 0.030, 0.033, 0.046, 0.057 (earliest to latest),
  so even the earliest quarter, aged 11 h at the end, is 6.6x the model.
- The observers' final white lists hold the 113 spies as 27% of 412 IPs and an empty gray
  list; the recency Monte Carlo (`adhoc/recency_model.py`) over them gives 0.0047 at 2 h and
  0.0001 at the end, so white-list selection with recency does not explain the relays.
- Estimators, on the 40 unreachable users' 1,020 transactions: `sp_r` precision **1.000**,
  recall **0.004** (4 transactions), equal to the ground-truth first-hop ceiling (4 of 1,017):
  **hit**. Users' own outbound share is 0.006, consistent with that recall. 3 of 40 senders
  with 20 or more transactions had one attributed (7.5%, against a predicted under 5%;
  one sender is 2.5%): **marginal miss**. Busy reachable nodes (5): 6 of 62 transactions
  stemmed to a spy (0.097).
**Reading.** The scored senders (users) behave as the model says, so for the question X1 asks
(who is deanonymized) this preset gives few exposures. But the lab's relays hold 7-9x more spy
slots than the rule predicts, in a cell built with a 6.4 h warmup to avoid exactly that. That
is the same discrepancy as E5's unexplained 1.5x, 4-5x larger here, and it undercuts the claim
that the long warmup reaches a steady state. Candidates, none tested: spy connections made
during the relays' first hours persist far longer than the 1.5 h estimated in E5; the relays'
gray lists keep refilling with spies (113 spies re-gossiped) in a way the observers' do not;
a fallback to the undeduplicated list. A probe version of this cell (first and last 3 relays'
peer lists and `net.p2p` DEBUG pick logs) is queued next (decision below).

### E15. X1 `tail`, no list: the same relay excess, 2.4x the model (2026-10-22 18:34-20:29, `phantom`)

**Setup.** `lean_24_none_h300_k21_w6h_m2_n600_s12345`: 42 spies in 21 /24s (2 each, GML nodes
600-620, the layout check clean), H=300 reachable honest, stock `24`, 40 unreachable users,
activity 8 h to 12 h. 114 min wall, exit 0, 12,206 MB lowest free RAM, 1,092 stem
transactions, 0.225 fluff per hop (implied 4.4 hops, inside the window around 5).
**Prediction (P3, in advance):** outbound share 0.07-0.08 (model 0.0822 at its usual 85%),
`sp_r` precision 1.00, recall equal to the ceiling and within 20% of the share, about 50% of
20-transaction senders exposed.
**Result.**
- **Light-node outbound share 0.1946**, flat by quarter (0.198, 0.195, 0.195, 0.191): 2.4x the
  model and 2.5x the top of the predicted range. **Missed.** It exceeds even the model's `legacy`
  value (0.122) and `none` value (0.123), so stock dedup is giving this fleet *more* slots than
  uniform selection would.
- By class: relays **0.2219**, observers 0.0938, medium hubs 0.1026, miners 0.1469, users
  **0.0554**, seeds' inbound 0.3047. As in E14, the users sit at or below the model and the
  relays far above it. There is no decay across the window, unlike every `24` cell with a
  short warmup.
- Estimators, on the 40 unreachable users' 1,031 transactions: `sp_r` precision **1.000**,
  recall **0.038** (39 transactions), equal to the ground-truth first-hop ceiling (hit), but
  not within 20% of the cell's share (it is 0.69x the users' own 0.0554; **miss as written**).
  15 of 40 senders with 20 or more transactions had a transaction attributed (37.5%, 95%
  interval about 23-54%; predicted about 50%): **marginal miss**. The 5 busy reachable nodes:
  11 of 61 transactions stemmed to a spy (0.18), `combined` precision 0.21.
  Unreachable nodes' median spy share of stem peers 0.039; of outbound peers 0.053.
**Reading (untested).** In both cells the excess is in the relays, which are reachable and so
take in peer lists from every node that dials them, while the users, who nobody dials, take in
only what their own outbound handshakes return. A relay's gray list is refilled by that
gossip with the spies' many IPs (the seeds hand out whites with spies at their share of IPs,
27% in `core`), and honest entries leave the gray list for the white list as they are
connected to while the spies' remaining IPs stay. If gray picks (30% of the 12 slots) then
find only spy /24s, the dedup has no unconnected candidate and falls back to the
undeduplicated list (step 1). That would put the relays near 0.3 x (spy-only gray list), and
the `tail` relays at 0.22 and the `core` relays at 0.04 are in the right order for 21 spy
/24s against 1. The probe cell (relay peer lists and pick logs) and P5's 53- and 26-spy cells
test it.
**Consequence for X1 as designed.** The scored senders are the unreachable users, and the
metric that matters for them is their own outbound and stem share: 0.006 (`core`) and 0.055
(`tail`). If the relay excess is real network behaviour it also exposes the *reachable* senders
(busy nodes at 0.10 and 0.18); if it is an artifact of the lab's static, small, churn-free
peer lists, it overstates the spies' reach. Which one it is decides what X1 can claim.

### E16. The relay excess is the gray-list drain, and its connections outlast a 6 h warmup (2026-10-22 20:29-22:31, `phantom`)

Run `20261022_202954_lean_24_none_h300_k1_w6h_p3_m113_s12345`: the `core` cell of E14 (113 spies
in one /24, `24` selection, no list, 6.4 h warmup, seed 12345) with the first and last 3 relays
of each start order (12 of 233) dumping their peer lists every 30 s and logging `net.p2p`
at DEBUG (`--probe 3`). Light-node share **0.0365** (E14 without the probe: 0.0352, so the
probe does not move the result); relays 0.0411, users 0.0117, observers 0.0255, medium 0.0145,
miners 0.1104; by quarter 0.0475, 0.0384, 0.0320, 0.0289. Wall 1 h 59 m, minimum free RAM
9.8 GB. Scripts (as run): `docs/spy_journal/adhoc/probe_picks.py`, `peerlist_composition.py`,
`spy_share_vs_time.py`.

**The lists.** A relay's white list grows until it holds every reachable node it has heard of
(412 here: 299 honest and all 113 spies) and its gray list then empties. Spies are 30-60% of the
gray list from the start, because the seeds hand out spies at their share of IPs, and their share
of it rises as the honest entries leave:

| Relay | +0.5 h | +1.0 h | +1.5 h | +2.0 h | +2.5 h | +3.0 h | +3.5 h on |
|---|---|---|---|---|---|---|---|
| `relay-r-a-001`: gray size (spy %) | 180 (52) | 198 (40) | 191 (34) | 123 (47) | 59 (64) | 5 (100) | 0 |
| `relay-r-b-114`: gray size (spy %) | 310 (34) | 192 (48) | 98 (78) | 38 (100) | 1 | 0 | 0 |

(Time since the relay started. White list at the end: 412, with 113 spies, for both.) Dedup
keeps one pick per /24, so 112 of the spies' 113 IPs are never chosen while there is an honest
/24 to choose, and the honest entries are used up first.

**The picks** (12 probe relays; a pick is a "Considering connecting" line; spies by IP):

| What | Picks | Spies | Uniform over the candidates would give |
|---|---|---|---|
| Gray, relay age under 1 h | 566 | 2 (0.4%) | 6.1 (1.1%) |
| White, age 1-3 h | 143 | 0 | 0.7 |
| White, age over 3 h | 3,432 | 16 (0.5%) | 15.8 (0.5%) |
| Gray, age 1-3 h, 0 unconnected /24 candidates | 103 | **102** | - |
| Gray, age 1-3 h, 1 candidate | 183 | **98** | - |
| Gray, age 1-3 h, 2-5 / 6-20 / 21-60 / 61+ candidates | 51 / 97 / 184 / 195 | 11 / 9 / 2 / 0 | - |

With no unconnected /24 candidate the selection falls back to the undeduplicated list (step 1),
which is by then nothing but spies; with one candidate that candidate is the spies' own /24. After
the gray list is empty (age over 3 h) every pick is from the white list and sits on the model.
This confirms the reading left open at the end of E15 at every step.

**Why it outlasts the warmup.** The spy connections made during the drain stay up. The spy share
of the relays' outbound slots, all 233 relays, 300 s snapshots (`spy_share_vs_time.py`):

| Sim hour | 2.0 | 3.0 | 3.5 | 4.0 | 5.0 | 6.0 | 8.0 | 10.0 | 12.0 |
|---|---|---|---|---|---|---|---|---|---|
| Relay spy share | 0.0145 | 0.0437 | **0.2276** | 0.2337 | 0.1455 | 0.0972 | 0.0576 | 0.0408 | 0.0330 |

The later a relay started the later and higher it peaks (the first quarter of relays by start
order peaks at 0.17 at 3.5 h, the last quarter at 0.37 at 4.0 h), and the activity window (8-12 h) sees only the tail. The tail is still
falling at 12 h, at 0.033 against the model's 0.0045. So the 6.4 h warmup of E13-E15 is not the
steady state it was meant to be: **every `24` share measured so far is the tail of a one-time
event, not an equilibrium** (E13's "still falling across the window" was this).

**What is and is not shown.**
- Shown: where the excess comes from (the gray picks at 0-1 candidates), that it is spies, and
  that the white-list picks are at the model.
- Not shown: why the spy connections turn over at the rate seen, or how picks map to held slots
  (the 12 probe relays make about 17 spy picks each at 0-1 candidates, against 12 slots).
- Not shown: that mainnet does not do this. The drain needs the relay to know every reachable
  node and hold all of them in the white list (cap 1,000 on mainnet; 412 here), so that the
  gray list holds only the spies. On mainnet the gray list (cap 5,000) is also fed by stale and
  churned addresses, so N should seldom reach 0, but that is an argument, not a measurement.
- Consequence for X0: the dedup reductions (-45% on the replica, -77% on the lean k=6 cell) were
  measured in the tail of the same event, so they probably understate the steady-state effect.
  Untested.
- Consequence for X1: the relay and reachable-sender figures of E14 and E15 are transient values.
  P7 tests whether a later window reads lower: the same `core` cell with a 16 h and a 24 h warmup
  (`phantom` and `simbox3`, queued 22:37).

### E17. X1 `core` with the ban list on half the honest nodes (2026-10-22 22:31 to 2026-10-23 00:33, `phantom`)

`lean_24_half_h300_k1_w6h_m113_s12345`: the `core` cell of E14 (113 spies in one /24, `24`
selection, 6.4 h warmup, seed 12345) with the spy ban list, naming the one spy /24 in full, on
half of the honest nodes (165 adopters). 121 min wall, exit 0, 9,997 MB lowest free RAM,
1,078 stem txs, 0.192 fluff per hop. Estimators: `est_half_core.{txt,json}` in the run folder.
**Prediction (P3b, in advance):** light-node share 0.002-0.005, `sp_r` recall falling with it,
under 5% of 20-transaction senders exposed.
**Result.**
- Light-node share **0.0162**, by quarter 0.0219, 0.0174, 0.0143, 0.0115; relays 0.0187, users
  0.0047, observers 0.0006, medium 0.0029. **The number missed** (3-8x above the range), for
  E16's reason: the P3b range halved the model, and the cell sits in the transient's tail.
- **The ratio did not miss.** 0.0162 / 0.0352 (E14, same cell without the list) = **0.46**, and by
  quarter 0.49, 0.46, 0.45, 0.42: the list removes about half the excess, as adoption of 50%
  implies, and the excess still falls across the window.
- Adopters (165 nodes) show **0.0000** spy outbound share; non-adopters (175, including the 5
  miners) 0.0415. E14's whole honest population read 0.0357. The classes are not matched (the
  non-adopters hold all the miners, whose share is 0.12), so this is not a test of "non-adopters
  unchanged within noise"; it is only consistent with it.
- Estimators, on the 40 unreachable users' 1,016 txs: `sp_r` precision **1.000**, recall
  **0.003** (3 txs), equal to the ground-truth first-hop ceiling (3 of 1,013): **hit**. E14
  without the list had 4 of 1,017. 2 of 40 senders with 20 or more txs had one attributed
  (5.0%, against under 5%): **at the edge**; E14 had 3 of 40. The 5 busy reachable nodes:
  `combined` exposes 4 of 5 (at precision 0.023), `sp_r` none.
**Reading.** For the *unreachable* users the list changes almost nothing that can be seen (3
against 4 attributed txs out of about 1,000), because a user's exposure is already near the
floor with no list; the list's effect shows in the relays and in reachable senders. With 3 and 4
events a difference of that size cannot be read. The list's effect on the exposure of reachable
senders, which is where E14's busy nodes sit, needs the long-warmup cells (P7) and seeds. The
`tail` list cell (`..._c50`, P3b's other half) was removed from `phantom`'s queue at 22:37
and is not run until a long-warmup cell has been read (decision 22:37).

### E18. A 32 GB box cannot run past block 2112; and the first long-warmup read (2026-10-22 23:57 to 2026-10-23 02:36, `simbox2`)

Run `20261022_235712_lean_24_none_h300_k1_w16h_m113_s12345`: the `core` cell with a 16 h warmup (P7a;
window 18-22 h). It ran for 2 h 37 m and was **killed by the kernel's out-of-memory killer at 02:35:05**
(Shadow, exit 137, at simulated 20:26:35), 2.4 h into the 4 h window. Free RAM had sat at 11.7-11.9 GB for
two hours (the driver's samples, every 20 s; the minimum it recorded was 10.3 GB); then, in under
12 s, the box ran out: at the kill `active_anon` + `inactive_anon` was 28.6 GB of 32 GB. The driver's
guard never saw it. `dmesg`: `Out of memory: Killed process (shadow)`.
**Cause (inferred, not observed directly).** The last line in the miner's `bitmonero.log` is
`HEIGHT 2112` at simulated 20:26:35, the 2112th block (the chain starts at height 1535 and gains one block
about every 2.2 min), and 2112 = 2048 + 64 is where RandomX's seed hash changes. Every one of the 453
daemons then re-derives its RandomX cache for the new seed at the same moment, and KSM, which had merged
the old caches into one, cannot merge the new ones until they are written. The match of the kill with
the block height is the evidence; the cache initialisation itself was not seen. `simbox3`
(100 GB), running the same cell for 28 h, passes block 2112 at about 03:40 and its memory samples
will show the size of the spike.
**Consequences.**
- **A cell on a 32 GB box must stop before simulated hour ~19** (chain height 2112 is reached at about
  20.4 h here; I keep a 1.4 h margin, which assumes the chain has the same block times in other cells).
  Cells that end by hour 12 (every cell so far) never reach it. The 28 h cells (P7b) can run on `simbox3` only.
- The 24 h cell on `phantom` (started 00:33) was stopped at 02:40, at simulated 17.8 h and before
  the activity window, to avoid the same end; nothing was lost beyond its box time (decision 02:40).
- A fix for later: a chain snapshot above height 2112 (regeneration is a 10-19 h single-core job,
  `docs/CHAIN_SNAPSHOT_REGEN.md`), or a large swap file and a driver without its 1.5 GB swap guard
  (untested). Either needs the spike's size from `simbox3` first.
**The partial read of P7a** (scored window 18 h to 20.4 h, 60% of the 4 h window; 501 stem txs):
light-node share **0.0099**; relays 0.0114, users 0.0009, observers 0.0092, medium 0.0022; by
quarter of the shortened window 0.0104, 0.0099, 0.0088. `sp_r` made no guess for the 443 unreachable
users' txs (none were stemmed straight to a spy). Prediction 0.009-0.022: inside, at the bottom edge,
and the curve below says a full window would have read lower, so this is not a clean hit.
**The relay curve** (all 233 relays, spy share of outbound slots, `spy_share_vs_time.py`; the
`core` probe cell, E16, for comparison):

| Sim hour | 8 | 10 | 12 | 14 | 16 | 18 | 19 | 20.5 |
|---|---|---|---|---|---|---|---|---|
| This run | 0.0628 | 0.0396 | 0.0308 (12.5 h) | 0.0223 | 0.0188 | 0.0138 | 0.0124 | 0.0100 |
| E16 probe | 0.0576 | 0.0408 | 0.0330 | - | - | - | - | - |

The two agree within 10% where both exist (8-12 h), on two boxes. The excess over the model (0.0045)
is 0.0285 at 12 h, 0.0093 at 18 h and 0.0055 at 20.5 h: a time constant of about 5 h (5.4 h over 12-18 h,
4.7 h over 18-20.5 h), faster than the 6.5-10 h I fitted for P7. At 5 h it reaches 0.0018 above the model by
hour 26 and 0.0008 by hour 30, so the 24 h cell (window 26-30 h) should read near 0.005-0.007 (relays),
which is inside P7b's range. That is an extrapolation of one curve.
*2026-10-23 14:15 (E22c):* the 24 h cell read **0.0050** for the relays over hours 26-30, inside 0.005-0.007 at the bottom
edge. Its curve matches this one within 15% at every common hour, on a third box (`simbox3`): 0.0537 against 0.0628 at 8 h,
0.0293 against 0.0308 at 12-12.5 h, 0.0231 against 0.0223 at 14 h, 0.0122 against 0.0138 at 18-18.5 h, 0.0107 against 0.0100
at 20.5 h.

*2026-10-23 12:36 (added after the review; the numbers were in the decisions log and section 2 only):* `simbox3`'s unpatched
copy of the 24 h cell (`20261022_234237_lean_24_none_h300_k1_w24h_m113_s12345`, now in the register) measured the spike. Between
two memory samples 55 s apart at simulated 21.4 h (03:44:46 and 03:45:41 wall), the summed memory of the simulator's processes rose
from 16.6 GB to 79.9 GB and the box's free RAM fell from 80.3 GB to 10.0 GB; the driver's next 20 s sample read 350 MB free and it
killed Shadow at 03:46 (swap had grown by 4.3 GB). 453 daemons at 256 MB each is 116 GB, so the box ran out before every cache was
built; the miner's log puts block 2112 at about simulated 21:24 in that cell. This is why swap cannot cover it and the patch (E20)
was written instead. `phantom`'s copy, stopped at simulated 17.8 h (`20261023_003351_...`), is also in the register now, with no result.

### E19. X1 `tail` at a 13 h warmup, with and without the list: the excess barely decays (2026-10-23 02:43-05:22, `phantom` and `simbox2`)

Two cells of the `tail` preset (42 spies in 21 /24s, `--spy-node0 600`, `24` selection, seed 12345), each with
a 13 h warmup so that the cell stops at simulated 19 h, before block 2113 (E18); window 15-19 h.
No list: `lean_24_none_h300_k21_w13h_m2_n600_s12345` (`phantom`, 157 min, 11.8 GB lowest free RAM, 1,099 stem txs,
0.211 fluff per hop). Ban list on half the honest nodes naming 10 of the 21 /24s:
`lean_24_half_h300_k21_w13h_m2_n600_c50_s12345` (`simbox2`, 152 min, 12.8 GB, 1,096 stem txs). Predictions P8.
**No list.** Light-node share **0.1662**, flat by quarter (0.1665, 0.1688, 0.1672, 0.1625); at the 6 h warmup
(E15) it was 0.1946. Relays 0.1881 (E15 0.222), users 0.0478 (E15 0.0554), observers 0.1219, medium 0.0842, miners 0.1324.
The model's ceiling for 21 /24s is 0.0822. The relays' spy share of outbound slots against simulated time
(`spy_share_vs_time.py`; whole cell, all 233 relays):

| Sim hour | 8 | 10 | 12 | 15 | 17 | 19 |
|---|---|---|---|---|---|---|
| All relays | 0.2058 | 0.2003 | 0.2012 | 0.1864 | 0.1905 | 0.1812 |
| Earliest-starting quarter | 0.126 | 0.119 | 0.111 | 0.100 | 0.105 | 0.097 |
| Latest-starting quarter | 0.292 | 0.272 | 0.273 | 0.249 | 0.263 | 0.254 |

Where `core`'s relay excess fell by two thirds in six hours (E18), the `tail`'s fell by about 12% in eleven
(8 h to 19 h), and it depends strongly on when the relay started: the earliest quarter is near the ceiling and
the latest is three times it.
**Estimators** (40 unreachable users, 1,033 txs): `sp_r` precision **1.000**, recall **0.059**, equal to the
ground-truth ceiling (61 of 1,026); 18 of 40 senders with 20 or more txs had one attributed (**45%**; E15: 15 of
40). The 5 busy reachable nodes: `sp` reaches 16 of 66 txs (0.24), `combined` precision 0.26.
**With the list at 50% adoption and 50% coverage.** Light-node share **0.1309** = **0.79** x the no-list cell, flat by
quarter (0.130, 0.130, 0.130, 0.133). Adopters (165 nodes) read 0.0777 against 0.1398 for non-adopters (175, with the
miners): a ratio of 0.56, where listing 10 of 21 /24s predicts about 0.52. `sp_r` precision 1.000, recall **0.050**
(52 of 1,031), equal to its ceiling (52 of 1,027); 20 of 40 senders exposed (**50%**).
**Scores (P8).** (a) light share 0.1662 in 0.11-0.17 (top edge), relays 0.1881 in 0.13-0.19 (edge), users 0.0478 in
0.04-0.07, exposure 18 of 40 in 20-45% (edge): **hit, all four at the edge of their ranges**. (b) ratio 0.79 in 0.70-0.85: **hit**;
precision 1.00 and recall at the ceiling: **hit**; exposure 20 of 40 against a predicted 15-40%: **missed** (and
18 against 20 of 40 cannot be told apart).
**Reading.** Unlike `core`, the `tail` excess is not a transient that a 13 h warmup removes. The earliest-started
relays are close to the ceiling and the late-started ones keep 3x it, which fits the drain (E16) leaving more
persistent spy connections in relays that started late (their gray lists drained sooner after they started), but
that is a guess. The probe cell `..._p3_m2_n600_s12345` (relay peer lists and pick logs; `phantom`, started 05:26)
tests two causes (P10). The list lowers the population share by 21% and the adopters' by 44%, but
leaves the unreachable senders' exposure where it was: with this many spies reachable by a sender through its
stem peers, half the nodes listing half the /24s does not protect the users measurably (20 against 18 of 40).

### E20. The fixed-RandomX-seed patch passes block 2112 (2026-10-23 03:55-07:27, `simbox3`)

**Patch.** `patches/monero-sim-fixed-randomx-seed.patch` adds `--sim-fixed-randomx-seed` (off by default). It sets
a flag that makes `rx_seedheight()` return 0 for every height, so every daemon keeps the genesis hash as its RandomX
seed and nothing is re-derived at chain height 2113 (E18). Three files: `crypto/hash-ops.h`, `crypto/rx-slow-hash.c`,
`cryptonote_core/cryptonote_core.cpp`. It is consensus-relevant, so every daemon of a cell gets the flag through
`daemon_defaults` (`make_lean.py --fixed-rx-seed`, cell names with `_fx`). Heights up to 2112 already have seed height 0
under the stock rule, so a cell that stops earlier behaves the same with or without it. Built on `simbox3` only
(`install_sim_monerod` run on its own, a few minutes with ccache): `monerod-sim` sha256 `4258da26e187...` (run's
`binary_provenance.txt`), whose provenance lists the new patch's hash `38ec8e84...`.
**Test (P9).** `lean_24_none_h71_k1_w18h_fx_s12345`: H=71, 13 spies in one /24, `24` selection, no list, 18 h warmup,
stops at 22.5 h simulated; 124 daemons. Wall 209 min, exit 0, lowest free RAM 88.6 GB.
- (a) **Hit.** Exit 0, no failed processes; the miners reach height 2188; the flag is logged by all 124 daemons.
- (b) **Hit.** All five success checks pass; all 124 daemons end at the same height, 2188 (76 blocks past the old seed
  change); no daemon logged a proof-of-work or block-verification error.
- (c) **Hit.** Block 2112 was added at simulated 19:55:23 (wall about 06:42). Summed process memory over simulated
  70,000-75,000 s ranged 6.5-7.2 GB and free RAM 91.3-91.7 GB, i.e. no step; the predicted bound was 5 GB.
**Reading.** With the flag, a cell passes the epoch boundary without the memory event that killed `simbox2`'s cell and
tripped `simbox3`'s. The spy share in this cell (light-node 0.0094 over 18-22.5 h; by quarter 0.0105, 0.0083,
0.0088, 0.0099) is not what it tested. **Limits.** There was no control: the unpatched binary was not run on this
cell. The evidence that the seed change causes the spike is that two unpatched cells (453 daemons, two boxes) spiked at
the boundary and this patched one (124 daemons) did not; the sizes differ, so a spike at this size would have been
about 30 GB by the same arithmetic, which would have shown.
**Block timing.** Block 2112 came at simulated 19:55 in this cell, 20:26 in `simbox2`'s 16 h cell and about 21:15 in
`simbox3`'s 24 h cell (it was at 2099 at 20:41): the time depends on the cell, by up to 1.4 h. The 19 h stops of the
13 h-warmup cells (E19) therefore had a margin of 0.9 h in the worst case seen.
**Next.** The 24 h `core` cell with the flag (P7b) started on `simbox3` at 07:27. `phantom` and `simbox2` are rebuilt
with the patch once their cells end (about 08:05); then all three run long cells with `--fixed-rx-seed`.

### E21. The `tail` excess is the stock rule's steady state; `core`'s has a gap left (2026-10-23 05:26-08:06, `phantom` and `simbox2`)

Two 13 h-warmup `tail` cells (stop 19 h, window 15-19 h; P10). **(a) The probe** `lean_24_none_h300_k21_w13h_p3_m2_n600_s12345`
(`phantom`, 158 min, 11.8 GB lowest free RAM): the same cell as E19's with the first and last 3 relays of each start order
logging picks and dumping lists. Light-node share **0.1626** (E19 without the probe: 0.1662; by quarter 0.1629, 0.1621,
0.1639, 0.1616). `sp_r` precision 1.000, recall 0.047 (49 of 1,028, its ceiling), 20 of 40 senders exposed.
**(b) The seed replicate** `..._s23456` (`simbox2`, 153 min): light-node share **0.1626** (seed 12345: 0.1662; by quarter
0.1651, 0.1658, 0.1611, 0.1586), users 0.0502, `sp_r` precision 1.000, recall **0.031** (32 of 1,027, its ceiling), 16 of 40 senders
exposed. The seed moves the share by 2%; it moves the recall ceiling from 0.059 to 0.031, which P10b did not allow for.
**What the picks say** (12 probe relays, `probe_picks.py`; the script's "uniform expects" column assumes one spy /24 and does
not apply; for 21 spy /24s among about 239 candidate /24s the uniform share is 21/239 = 0.088):

| Picks | n | spies | share |
|---|---|---|---|
| Gray, relay age under 1 h | 570 | 86 | 0.15 |
| White, age 1-3 h | 469 | 132 | **0.281** |
| White, age over 3 h | 6,430 | 1,356 | **0.211** |
| Gray, age over 3 h | 38 | 0 | - |

Early gray picks are near uniform (0.12-0.17); after the lists settle every pick is a white-list pick and a fifth of them
are spies, 2.4x the uniform 0.088. **H1 of P10, "the drain's connections persist and new picks are at the model" (0.06-0.11),
is refuted; H2, "the steady-state picks favour spies" (0.12 or more), is supported.**
**The stock rule explains it.** `recency_model.py`'s Monte Carlo of the rule (one random IP per unconnected /24, sort by
`last_seen`, keep the 20 newest, cubic bias) over the probe relays' own white lists after 3 h (540 dumps) gives **0.190** spy
share per slot; the cell's relays hold 0.1836 (other relays) to 0.1995 (probe relays), and the picks are 0.211. In those lists
the spies' mean `last_seen` rank percentile is 0.39 (newer than the middle). The same model over the *observers'* lists, which
is what E14 used to rule recency out, gives 0.060-0.079 (spy rank 0.58, older): the observers do not make outbound connections
the way relays do, so their lists are not the relays'. The same model over the `core` probe relays' lists gives 0.0054, the
model's value, so recency does not explain `core`.
**Connection lifetimes** (`conn_life.py`, the window): in the `tail`, a (relay, peer) pair appears in 12.8 five-minute windows for
spies (2.0 stretches, about 32 min each) and 21.5 for honest peers (2.5 stretches, about 43 min); in `core`, 18.5 windows in
1.14 stretches for spies (about 81 min) and 19.4 in 2.41 for honest peers (about 40 min). A slot is refilled within the hour.
**Reading.** (1) The `tail` excess (0.163-0.166 light, 0.185-0.19 relays, against the 0.0822 ceiling) is a stationary property
of the stock selection rule in these lists, not a transient: P11a, the 30 h `tail` cell, should read above its predicted
0.10-0.16 if this is right. (2) Why the spies are newer in the relays' lists was not tested; a feedback is plausible (a
connection refreshes the peer's `last_seen`, so a peer once connected is picked again), and whether it exists on mainnet is open.
(3) **A correction to E16.** E16 said the spy connections made during the drain "stay up". The lifetimes above say they last an hour
or two, not until hour 8-12, and in the `core` probe the 12 probe relays hold 0.0295 of their slots in the window (the other
relays 0.0417) against white picks of 0.0047 over ages above 3 h. The drain's gray picks (E16) explain the peak at hour 3.5, but
the slow decay to hour 12 is **not** explained by persistence and is not yet explained. P7b (the 24 h `core` cell) will show
where it ends. (`probe_relay_share.py` gives the slot shares.) *2026-10-23 14:15:* it ends at the model, decaying with a time
constant of 5-6 h all the way down (E22c: relays 0.0050 over hours 26-30 against the model's 0.0045).
**Scores (P10).** (a) H2 supported, H1 refuted, as above; the gray-pick clause (at least 90% spies at 0-1 candidates) could not be
tested (5 picks). (b) light share 0.1626 in 0.14-0.19: hit; users 0.0502 in 0.035-0.06: hit; precision 1.000: hit; recall 0.031
outside 0.045-0.07: **missed**, though equal to its ceiling; 16 of 40 in 15-23: hit.

### E22. The 30 h cells: the `tail` excess relaxes slowly and by start order; the `core` excess ends at the model (2026-10-23 07:27-14:05, `phantom`, `simbox2`, `simbox3`)

The first cells run with `--sim-fixed-randomx-seed` on every daemon (E20), so a 32 GB box could pass block 2113:
24 h warmup, stop at 30 h simulated, window 26-30 h, seed 12345. Predictions P11 (filed 07:30).

**(a) `tail`, no list** (`lean_24_none_h300_k21_w24h_m2_n600_fx_s12345`, `phantom`, 227 min wall, exit 0, lowest free RAM
10.9 GB, 1,099 stem txs, 0.196 fluff per hop). Light-node share **0.1572**, by quarter 0.1591, 0.1593, 0.1572, 0.1535 (a 3.5%
fall across the window). Relays **0.1805**, users 0.0431, observers 0.0483, medium 0.0895, miners 0.1139. The same cell at the
three warmups:

| Warmup (window) | Light | Relays | Users | Observers | 20+-tx users exposed |
|---|---|---|---|---|---|
| 6 h (8-12 h), E15 | 0.1946 | 0.2219 | 0.0554 | 0.0938 | 15 of 40 |
| 13 h (15-19 h), E19 | 0.1662 | 0.1881 | 0.0478 | 0.1219 | 18 of 40 |
| 24 h (26-30 h), this run | 0.1572 | 0.1805 | 0.0431 | 0.0483 | 12 of 40 |

The relays' spy share against simulated time in this run (`spy_share_vs_time.py`), all 233 relays and by start-order quarter:

| Sim hour | 8 | 12 | 15 | 19 | 23 | 26 | 28 | 30 |
|---|---|---|---|---|---|---|---|---|
| All relays | 0.2035 | 0.1946 | 0.1996 | 0.1934 | 0.1875 | 0.1820 | 0.1808 | 0.1783 |
| Earliest-starting quarter | 0.130 | 0.108 | 0.109 | 0.112 | 0.090 | 0.087 | 0.093 | 0.086 |
| Latest-starting quarter | 0.291 | 0.286 | 0.282 | 0.260 | 0.272 | 0.245 | 0.253 | 0.243 |

The ceiling for 21 spy /24s is 0.0822. The whole population falls 12% in 22 hours; the excess over the ceiling falls from 0.121 at
8 h to 0.096 at 30 h, about 2.5% an hour and slowing. The earliest-started quarter of relays reaches the ceiling by hour 23; the
latest-started quarter is still at three times it at hour 30; the observers, which started at t=0, fall from 0.12 to 0.05. So
the excess is neither the flat steady state E21 expected nor the transient that P7 hoped for in `core`: it is a **per-relay
state, set by when the relay started, that relaxes slowly**, if at all, in the late starters. (E21's recency reading fits this:
a connection refreshes a peer's `last_seen`, the stock rule puts about a third of its white picks on the single newest unconnected
/24, so whatever a relay was connected to after its gray list drained is what it keeps re-picking. What breaks the lock is a
disconnection that is not followed by a re-pick, which is slow in a network without churn. That mechanism is inferred, not shown.)
**Estimators** (40 unreachable users, 1,030 txs): `sp_r` precision **1.000**, recall **0.035** (36 txs), equal to its ceiling (36 of
1,026); **12 of 40** senders with 20 or more txs exposed (30%; 95% interval about 17-47%). The 5 busy reachable nodes: `sp` 3 of
69 (0.043), `combined` exposes 3 of the 4 nodes with 10-19 txs at a precision of 0.09. Unreachable nodes' median spy share of
stem peers 0.019, of outbound peers 0.036; reachable nodes 0.125 and 0.146.
**Memory.** Free RAM never fell below 10.9 GB over 30 simulated hours (P11's clause: above 4 GB), and the box passed block 2112
at simulated 20:12 with no step. A 32 GB box runs a 30 h H=300 cell with the flag.
**Score (P11a).** 0.1572 is inside 0.10-0.16, at the top edge: **hit**. The 08:29 note expected a value above 0.16 (a flat steady
state); it was wrong by 0.003, and the curve says why: there is a decay, but it is slow and confined to the relays that started
early. Users 0.0431 and exposure 12 of 40 were not predicted in P11a.
**What this means for X1.** The spies' share of the unreachable users' own stems in the `tail` preset is 0.035-0.06 at every warmup
(recall at its ceiling each time), so for the senders X1 scores the answer is stable: about one unreachable user in three with 20 or
more transactions has at least one attributed within 4 hours at this spy density, with precision 1. The relays' share, which decides
the reachable senders' exposure, is 0.18-0.22 and depends on when the relay started; its mainnet counterpart is untested (open question 8).

**(b) `core` with the ban list on half the honest nodes** (`lean_24_half_h300_k1_w24h_m113_fx_s12345`, `simbox2`, 244 min wall, exit 0,
lowest free RAM 10.0 GB, 1,090 stem txs, 0.197 fluff per hop; written 12:16). Light-node share **0.0025**, by quarter 0.0024, 0.0026,
0.0026, 0.0024: flat. Relays 0.0027, users 0.0019, observers 0.0, medium 0.0029, miners 0.0631. Adopters (165 nodes) **0.0000**,
non-adopters (175, with the 5 miners at 100 out-peers) 0.0148, all honest 0.0081. The same cell at the 6 h warmup (E17) read 0.0162
(non-adopters 0.0415). Half the no-list model (0.0045) is 0.0023. The relays' spy share against simulated time:

| Sim hour | 4 | 6 | 8 | 12 | 15 | 18 | 23 | 28 | 30 |
|---|---|---|---|---|---|---|---|---|---|
| All relays | 0.1036 | 0.0559 | 0.0327 | 0.0154 | 0.0111 | 0.0079 | 0.0038 | 0.0025 | 0.0023 |

The excess over 0.0023 halves every 4-5 h (a time constant of about 6 h over hours 8-18, as E18's 5 h for the no-list cell) and is
gone by hour 28; at hour 30 the start-order quarters read 0.0026, 0.0013, 0.0000, 0.0052, i.e. no start-order structure. **In `core`
the excess is a transient and it ends at the model.** The gap left by E21's correction (the slow decay from hour 3.5 to 12 that
persistence did not explain) is at least bounded: whatever carries it is gone in a day.
**Estimators** (40 unreachable users, 1,019 txs): `sp_r` made **no guess**; 0 of 1,015 user txs were stemmed straight to a spy, so
**0 of 40** senders exposed. The 5 busy reachable nodes (medium hubs, 71 txs): `sp` 8 of 71 correct at a precision of 0.47, `fs` 6
correct of 516 guesses. In the window 10% of unreachable and 16% of reachable nodes ever held a spy outbound slot (median 0).
**Memory.** Lowest free RAM 10.0 GB over 30 simulated hours; block 2112 passed at simulated 20:05 with no step.
**Score (P11b).** 0.0025 is inside 0.0025-0.007, at the bottom edge: **hit**. Exposure 0 of 40 against at most 1: **hit**. Precision
1.00 where `sp_r` guesses: not tested (no guess). Free RAM above 4 GB: **hit**.

**Why `tail` locks in and `core` does not (inferred, not shown).** The stock rule takes one *random* IP per unconnected /24 before it
sorts by `last_seen` (verified in v0.18.5.1, `make_new_connection_from_peerlist`: a uniform shuffle, the first entry per /24, then
the sort and the top 20). A spy /24 of 2 IPs puts its just-disconnected, freshest IP forward half the time; a /24 of 113 puts it
forward 1 time in 113, and the stale rest of the time. So the recency feedback of (a) is diluted by the number of IPs the spy packs
into a /24: a diversified spy (1-3 IPs per /24, as in the ban list's tail) gets the lock-in, a dense one does not. A cheap test, not
yet filed: the `tail` layout at 1 and at 8 spies per /24 (`--spies-per-subnet`), same /24 count; the prediction is a larger excess at
1 and a smaller one at 8.

**(c) `core` without the list** (`lean_24_none_h300_k1_w24h_m113_fx_s12345`, `simbox3`, 394 min wall, exit 0, lowest free RAM
76.6 GiB of 98.2, 1,093 stem txs, 0.199 fluff per hop; written 14:25). Light-node share **0.0044**, by quarter 0.0042, 0.0050,
0.0044, 0.0038: flat, at the model (0.0045). Relays 0.0050, users 0.0017, observers 0.0002, medium 0.0001, miners 0.0411, all
honest 0.0068. The same cell at the three warmups:

| Warmup (window) | Light | By quarter | Relays | Users | 20+-tx users exposed |
|---|---|---|---|---|---|
| 6 h (8-12 h), `20261022_163001` | 0.0352 | 0.045, 0.038, 0.032, 0.027 | 0.0413 | 0.0060 | 3 of 40 |
| 16 h (18-20.4 h, cut by the OOM kill), E18 | 0.0099 | 0.010, 0.010, 0.009 | 0.0114 | 0.0009 | - |
| 24 h (26-30 h), this run | 0.0044 | 0.0042, 0.0050, 0.0044, 0.0038 | 0.0050 | 0.0017 | 1 of 40 |

The relays' spy share against simulated time (`spy_share_vs_time.py`; the full curve with the start-order quarters is
`spy_share_vs_time.txt` in the run's folder):

| Sim hour | 4 | 6 | 8 | 10 | 12 | 14 | 16.5 | 18.5 | 20.5 | 23 | 26.5 | 28 | 30 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| All relays | 0.2006 | 0.0846 | 0.0537 | 0.0368 | 0.0293 | 0.0231 | 0.0165 | 0.0122 | 0.0107 | 0.0083 | 0.0066 | 0.0062 | 0.0049 |

The peak at hour 4 (0.20, the gray-list drain of E16) decays to the model with a time constant of about 6 h the whole way: the
excess over 0.0045 is 0.0248 at 12 h, 0.0062 at 20.5 h and 0.0021 at 26.5 h (6.1 h over 12-20.5 h, 5.5 h over 20.5-26.5 h; E18
fitted 5 h on the 16 h cell, (b) 6 h with the list). Where this curve and E18's overlap (hours 8-20.5) they agree within 15% at
every point, on different boxes (`simbox3` here, `simbox2` there) with the same seed. A weak start-order structure is left at the
end: from hour 21 the earliest-started quarter of the relays sits below the model (0.001-0.004; a quarter is about 750 slots, so
0.0013 is one slot) and the third quarter above it (0.008-0.014 to hour 28); at hour 30 the quarters read 0.0013, 0.0053, 0.0078,
0.0052. Against (a)'s 0.086-0.243 that is noise-sized.
**Estimators** (40 unreachable users, 1,020 txs): `sp_r` made one guess, correct (precision 1.000), recall 0.001, equal to its
ceiling (1 of 1,019 user txs was stemmed straight to a spy); **1 of 40** senders with 20 or more txs exposed. The 5 busy reachable
nodes (73 txs): `sp` 5 of 73 correct at a precision of 1.0; `combined` exposes 2 of the 4 with 10-19 txs and the one with 20 or more,
at a precision of 0.017. In the window 7.5% of unreachable and 24% of reachable nodes ever held a spy outbound slot (median 0);
2.5% and 8% ever had a spy stem peer.
**Memory.** Free RAM never fell below 76.6 GiB of 98.2 over 30 simulated hours. The daemons' summed memory was 15.6-16.0 GB from
simulated hour 6 to hour 24 and 18.2 GB at the end; block 2112 (simulated 21.4 h, about 11:40 wall) passed with no step, on the
box where the unpatched binary went from 16.6 to 79.9 GB in 55 s (E18's addendum). Wall 394 min against 227-244 min on the 32 GB
boxes for the same simulated span: `simbox3` is 1.6-1.7x slower.
**Score (P7b).** Light 0.0044 against 0.005-0.014: **miss**, 0.0006 below the floor, in the direction the range was written to
confirm; the range's floor sat above the model it was meant to test for (section 5, P7). E18's relay extrapolation (0.005-0.007)
is met at its bottom edge. (b)'s 0.5x clause: 0.0025 / 0.0044 = **0.57x**.
**What this means.** `core`'s excess is now read at three warmups on three boxes and it is one curve: a gray-list-drain transient
that decays with a 5-6 h time constant and ends at the stock model in about a day. With no list and a day's uptime, a dense spy
(113 IPs in one /24) holds 0.5% of the light nodes' outbound slots and attributes 1 unreachable user in 40 within 4 hours; with
the list on half the nodes, 0.25% and none. `tail` (a) is the opposite case, and P13 asks whether the IPs per /24 is what
separates them.

### E23. The `legacy` partner of the `tail` cell: the old rule gave this fleet 1.7x what stock dedup gives it (2026-10-23 12:37-15:14, `phantom`)

Prediction P12 (filed and committed 12:36; the run started 12:37). `lean_legacy_none_h300_k21_w13h_m2_n600_s12345`: the `tail`
layout (42 spies in 21 /24s, `--spy-node0 600`) under v0.18.4.2's selection (`--sim-subnet-dedup=legacy`, byte for byte the tag's
`make_new_connection_from_peerlist`), 13 h warmup, window 15-19 h, seed 12345, stock RandomX (the cell stops at 19 h). Its `24`
partner is E19's `20261023_024331_..._s12345`: same box, same seed, 0.1662. 156 min wall, exit 0, lowest free RAM 11.5 GiB,
1,099 stem txs, 0.224 fluff per hop, loop rate 0.063.

**Shares.** Light-node share **0.2857**, by quarter 0.2862, 0.2831, 0.2856, 0.2880: flat (Q4 is 0.6% above Q1). Relays
**0.3256** (1.14x light), users 0.0747, observers 0.1774, medium 0.1755, miners 0.1425. The `legacy` model for this layout is
0.1221 (12 slots, cubic recency over a 20-entry white list, no /24 collapse), so the cell sits at **2.34x** its model; the `24`
partner sits at 2.02x its ceiling (0.1662 against 0.0822). The pair:

| Selection | Light | Relays | Users | Observers | `sp_r` recall (= ceiling) | 20+-tx users exposed | Model |
|---|---|---|---|---|---|---|---|
| `legacy` (this run) | 0.2857 | 0.3256 | 0.0747 | 0.1774 | 0.077 | 23 of 40 | 0.1221 |
| `24` (E19, same seed and box) | 0.1662 | 0.1881 | 0.0478 | 0.1219 | 0.059 | 18 of 40 | 0.0822 |
| `24` / `legacy` | 0.58 | 0.58 | 0.64 | 0.69 | 0.77 | 0.78 | 0.67 |

**The relay curve** (all 233 relays and by start-order quarter, `spy_share_vs_time.py`; the full curve is `spy_share_vs_time.txt`
in the run's folder):

| Sim hour | 2 | 3 | 3.5 | 4 | 6 | 8 | 12 | 15 | 19 |
|---|---|---|---|---|---|---|---|---|---|
| All relays | 0.1690 | 0.2549 | 0.2902 | 0.3001 | 0.3223 | 0.3173 | 0.3371 | 0.3282 | 0.3255 |
| Earliest-started quarter | 0.156 | 0.181 | 0.185 | 0.174 | 0.178 | 0.182 | 0.198 | 0.178 | 0.176 |
| Latest-started quarter | 0.167 | 0.329 | 0.414 | 0.450 | 0.477 | 0.460 | 0.493 | 0.490 | 0.482 |

At hour 2 the four quarters are alike (0.16-0.19, already above the model: under `legacy` the early gray-list picks are spy-rich
too). Between hours 2 and 4 the share rises to 0.30 and the quarters separate; from hour 5 to 19 nothing moves: all relays
0.32-0.34, the earliest-started quarter 0.17-0.20, the latest 0.46-0.49, a 2.7x gradient that is stationary over 14 hours. Under
`24` the same layout (E19, E22a) shows the same gradient with a slow relaxation in the early starters; under `legacy` not even that.

**Estimators** (40 unreachable users, 1,033 txs): `sp_r` 80 guesses, 80 correct: precision **1.000**, recall **0.077**, equal to
its ceiling (80 of 1,030 user txs were stemmed straight to a spy); **23 of 40** senders with 20 or more txs exposed (58%; the `24`
partner 18 of 40). The 5 busy reachable nodes (66 txs): `sp` 24 of 25 correct (precision 0.96, recall 0.36); `combined` exposes
all 4 with 10-19 txs and the one with 5-9. Unreachable nodes' median spy share of stem peers 0.058, of outbound peers 0.067
(`24`: 0.029 and 0.044); reachable nodes 0.271 and 0.263 (`24`: 0.151 and 0.158). 75% of unreachable and 99% of reachable nodes
had a spy stem peer at some point in the window.

**Score (P12).** Light 0.2857 against 0.16-0.26: **miss, above**, which P12 defined as "the old rule was worse against this fleet
than X0's k=6 anchor suggests" (E4, E13: `legacy` at 1.8x the model with 6 spy /24s; here 2.34x with 21). Flat by quarter: hit
(Q4 within 10% of Q1). Relays 1.0-1.2x light: hit (1.14x). `24`/`legacy` ratio 0.65-1.0: **miss, below** (0.58). The reading P12
was filed to test, "below 0.16 means stock dedup gives a /24-diversified spy more slots than the old rule", is refuted: it gives fewer.

**What this means.** (1) The review's first gap is closed with a measurement: stock /24 dedup takes **42%** of this diversified
fleet's light-node slots away compared with v0.18.4.2 (the models said 33%). Dedup is a defence against a 2-per-/24 fleet, a weaker
one than against a dense one (`core`: at the model after a day, E22c), and it does not remove the lock-in. (2) The recency lock-in
is not a dedup artefact: it is larger under the old rule, where every spy IP is its own candidate (42 candidates against 21 /24s),
and there it does not relax at all within 19 h. The excess over the model grows with the number of distinct spy candidates the
selection sees. Under `legacy`: at the model with 1 spy /24 (X0's k=1 cells), 1.8x with 6 /24s (E4, E13), 2.34x with 21 /24s and
42 IPs (this run). Under `24`: at the model with 1 /24 once the transient is gone (E22c), 2.0x with 21 /24s (E19). P13 (1 and 8 spies
per /24 at the same 21 /24s, running) varies the IPs per /24 at a fixed candidate count under `24`. (3) For X1's unreachable users:
under the old rule 23 of 40 twenty-transaction senders are attributed within the window at precision 1, against 18 of 40 under
stock; the per-transaction chance is 0.077 against 0.059. The reachable hubs are hit harder: `sp` recall 0.36 against 0.24.

### E24. Spies per /24 (P13): eight per /24 lock in as two do, so the dilution reading is refuted (2026-10-23 12:37-15:29, `simbox2`; the 1-per-/24 cell on `phantom` to follow)

Prediction P13 (filed and committed 12:36; both runs started 12:37). The `tail` layout at 21 /24s under `24`, 13 h warmup, window
15-19 h, seed 12345, with the spies per /24 varied. **(b) 8 per /24** (`lean_24_none_h300_k21_w13h_m8_n600_s12345`, 168 spies,
508 daemons, `simbox2`, 170 min wall, exit 0, 1,073 stem txs, 0.205 fluff per hop). (a), 1 per /24, runs on `phantom` until about
17:50 and is added below when it lands.

**(b) Shares.** Light-node share **0.1749**, by quarter 0.1790, 0.1778, 0.1744, 0.1685 (a 6% fall across the window). Relays 0.1968,
users 0.0545, observers 0.1380, medium 0.1220, miners 0.1187. The `24` ceiling is the same 0.0822 as at 2 per /24 (it depends on the
/24 count only; the `legacy` model would be 0.337 for 168 IPs). The 2-per-/24 cell (E19, same seed) read 0.1662 light, 0.1881 relays,
0.0478 users: eight spies per /24 give the fleet **5% more**, not the 30-45% less that dilution predicted.

| Spies per /24 | Spies | Light | Relays | Users | `sp_r` recall (= ceiling) | 20+-tx users exposed | Relays, hour 8 to 19 |
|---|---|---|---|---|---|---|---|
| 2 (E19) | 42 | 0.1662 | 0.1881 | 0.0478 | 0.059 | 18 of 40 | -12% |
| 8 (this run) | 168 | 0.1749 | 0.1968 | 0.0545 | 0.063 | 17 of 40 | 0.261 to 0.183, -30% |

**The relay curve** (`spy_share_vs_time.py`; the full curve with the start-order quarters is `spy_share_vs_time.txt` in the run's folder):

| Sim hour | 2 | 3 | 3.5 | 5 | 6 | 8 | 10 | 12 | 15 | 17 | 19 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| All relays | 0.1239 | 0.1732 | 0.2271 | 0.3616 | 0.3197 | 0.2608 | 0.2413 | 0.2303 | 0.1981 | 0.2001 | 0.1831 |

The 168-spy cell has a `core`-sized gray-list drain (E16): the relays peak at 0.36 at hour 5 (the 42-spy cell peaked near 0.22) and
fall by 30% between hours 8 and 19, where the 42-spy cell fell 12% (E19). The start-order gradient is there but weaker: the quarters
read 0.281 / 0.329 / 0.391 / 0.444 at hour 5 and 0.154 / 0.152 / 0.206 / 0.220 at hour 19 (1.4x, against 2.5x in E22a). **The window
is not stationary.** At hour 19 the relays (0.183) have only just come down to the 2-per-/24 cell's level (0.188), so what the
15-19 h window measures at 8 per /24 is a lock-in floor plus the tail of a larger transient; the floor itself is not separated here.

**Estimators** (40 unreachable users, 1,007 txs): `sp_r` 63 guesses, 63 correct: precision **1.000**, recall **0.063**, equal to its
ceiling (63 of 1,006 stemmed straight to a spy); 16 of the 39 twenty-transaction senders and the one 10-19-transaction sender
exposed: **17 of 40**. The 5 busy reachable nodes (66 txs): `sp` 13 of 22 correct (precision 0.59); `combined` exposes all 5 at a
precision of 0.17. Unreachable nodes' median spy share of stem peers 0.035, of outbound peers 0.048; reachable nodes 0.167 and 0.179.

**Memory.** 508 daemons on a 32 GB box: free RAM bottomed at **3.4 GB** at simulated 10 minutes (boot: 252 processes already at
25.8 GB summed), 8.5 GB after the first simulated hour, the daemons at 16.9-19.1 GB in the steady state. The driver's 1.5 GB guard did
not trip. P13's clause (above 6 GB) is missed, by the boot transient; a 30 h version of this cell would clear boot the same way and
then sit at 8-12 GB free.

**Score (P13b).** Light 0.1749 against 0.09-0.14: **miss, above**, and above the 0.16 that P13 set as the refutation threshold:
**the dilution reading is refuted.** Eight spies per /24 do not dilute the lock-in; the fleet gains 5%, consistent with a larger
transient. Relays 0.1968 against 0.10-0.16: miss. Users 0.0545 against 0.03-0.05: miss, above. `sp_r` precision 1.00 and recall at
its ceiling: hit. Lowest free RAM above 6 GB: **miss** (3.4 GB at boot).

**What this means (written 15:45, before (a) lands; the expectation for (a) below is therefore not pre-registered).** E22's inferred
mechanism, "one random IP per /24 goes forward before the recency sort, so a dense /24 rarely puts its freshest IP forward", does not
produce a weaker lock-in at 8 per /24. The reading that survives E22c, E23 and this run together is that the excess follows the
**number of distinct candidates the selection sees**: under `24` the candidates are /24s (1 /24: at the model once the transient is
gone; 21 /24s: 2.0x, whatever the IPs per /24), under `legacy` they are IPs (1 /24: at the model; 6 /24s: 1.8x; 42 IPs: 2.34x). If
that is right, (a), 21 /24s at 1 spy each, reads near the 2-per-/24 cell (0.16-0.18), not P13's dilution range of 0.18-0.27, and a
`24` cell with 42 /24s at 1 spy each would read near 2.3x its (higher) ceiling; that cell is the natural next test, after (a). Why one
spy /24 has no steady excess while 21 do is then the open point. A sketch, not a result: with one spy /24 the stock rule gives it at
most one slot per node and the recency re-pick competes with 242 honest /24s for that slot, while a relay drained into 21 spy /24s
holds several spy slots and every disconnection re-picks among 21 freshly-seen spy /24s.

**(a) 1 per /24** (`lean_24_none_h300_k21_w13h_m1_n600_s12345`, 21 spies, `phantom`, 153 min wall, exit 0, lowest free RAM 12.2 GiB,
1,099 stem txs, 0.192 fluff per hop; written 18:05). Light-node share **0.1978**, by quarter 0.1969, 0.1955, 0.2005, 0.1984: flat.
Relays 0.2250, users 0.0605, observers 0.0939, medium 0.0826, miners 0.1434; the ceiling is 0.0822, so **2.41x**. The three cells at 13 h:

| Spies per /24 | Spies | Light | Relays | Users | `sp_r` recall (= ceiling) | 20+-tx users exposed | Relays, hour 8 to 19 |
|---|---|---|---|---|---|---|---|
| 1 (this run) | 21 | 0.1978 | 0.2250 | 0.0605 | 0.052 | 16 of 40 | 0.221 to 0.225, +2% |
| 2 (E19) | 42 | 0.1662 | 0.1881 | 0.0478 | 0.059 | 18 of 40 | -12% |
| 8 ((b) above) | 168 | 0.1749 | 0.1968 | 0.0545 | 0.063 | 17 of 40 | 0.261 to 0.183, -30% |

**The relay curve** at 1 per /24 has no drain peak and no decay: 0.106 at hour 2, 0.199 at 3.5, 0.208 at 5, 0.221 at 8, 0.221 at 12,
0.225 at 19 (`spy_share_vs_time.txt` in the run's folder). The start-order quarters sit at 0.11-0.13 / 0.17-0.19 / 0.22-0.25 / 0.29-0.35
from hour 4 on, a 2.9x gradient, stationary. This is the `legacy` cell's shape (E23) at a lower level: with 21 spies there is nothing
to drain, and what the window reads is the lock-in alone.
**Estimators** (40 unreachable users, 1,034 txs): `sp_r` 54 guesses, 54 correct: precision **1.000**, recall **0.052**, equal to its
ceiling (54 of 1,033); **16 of 40** senders with 20 or more txs exposed. The 5 busy reachable nodes (65 txs): `sp` 10 of 18 correct
(precision 0.56); `combined` exposes all 5 at a precision of 0.20. Unreachable nodes' median spy share of stem peers 0.035, of
outbound peers 0.048; reachable nodes 0.173 and 0.174.
**Score (P13a).** Light 0.1978 in 0.18-0.27: **hit**; relays 0.2250 in 0.21-0.31: hit; users 0.0605 in 0.05-0.08: hit; `sp_r`
precision 1.00 and recall at its ceiling: hit. P13 as a whole: (a) hit, (b) refuted, so the 1/m dilution reading is **not**
supported as filed (the prior was 50% that both land).
**Reading, revised (18:05).** The expectation written at 15:45 for (a), 0.16-0.18 under a "candidate count" reading, was **wrong**
(0.198): the number of spy /24s is not the whole story either. What the three points say: going from 1 to 2 spies per /24 lowers
the fleet's steady share (0.198 to 0.166, neither window holding a transient), which is the direction E22's dilution reading
predicted, at about a third of the 1/m size; the 8-per-/24 cell cannot be placed, because its window is still inside its own
drain's transient. The steady-state comparison needs the 24 h warmup that E22a already gives for 2 per /24 (0.1572): P16 files
1 and 8 per /24 at 24 h.

## 5. Pre-registered predictions

Filed before the results; the time is when this section was written.

**P1, filed 2026-10-22 11:30.** `lean_24_none_h300_k6_w6h_s12345` (on `simbox2`, 12 h
simulated, 6.4 h warmup): the light-node outbound share is between the model's 0.026
and 0.060 (the H=150 plateau was 1.7x the model), flat by quarter (Q4 within 20% of
Q1), and 75-90% below the `legacy` k=6 value of 0.2453. If it is above 0.060, the
dedup effect at mainnet's ratio is weaker than the model and E5's 1.5x gap is not a
small-lab effect. If it is below 0.026, the model is not a ceiling after all.

*Outcome, 2026-10-22 13:36:* **0.0598, inside the interval, at its upper edge** (see E13).
The registered reading of a result above 0.060 (dedup weaker than the model at this
ratio) is not triggered, but the margin is 0.0002.

**P2, filed 2026-10-22 11:30.** Remaining X0 seeds: `legacy/half` 34567 in 0.066-0.072;
`24/none` 34567 in 0.066-0.078; `24/half` 23456 and 34567 in 0.031-0.038. (From the
spread of the existing seeds and the 85% model ratio.)

*Outcome, 2026-10-22 11:43:* `legacy/half` 34567 read **0.0632, below the predicted
0.066-0.072. Missed.** The interval was drawn from two seeds that agreed to 0.0002;
three seeds give a spread of 0.0057. The target is unaffected (0.0632 is 0.9x of
0.07), but the lesson is that two seeds underestimate the seed spread: for the
remaining predictions use the spread of `legacy/none` (0.006, about 4%) as the
minimum width.

*Outcome, 2026-10-22 12:30:* `24/half` 23456 read **0.0373, inside the predicted
0.031-0.038 (a hit, at the top edge).** *2026-10-22 14:31:* `24/none` 34567 read **0.0690,
inside the predicted 0.066-0.078 (a hit).** *2026-10-22 16:31:* `24/half` 34567 read **0.0382, just above the predicted 0.031-0.038
(a miss by 0.0002).** Final score for P2: 2 hits, 2 misses, both misses by under 10% of
the interval edge. The intervals were too tight for the seed spread of 4-8%; the predictions
for the new seeds (P4) use that spread.

*Outcome for `core`, no list, 2026-10-22 about 19:00 (E14):* share **missed** (0.0352 against
0.005-0.01); precision and recall-equals-ceiling **hit**; exposure **marginal miss** (7.5%
against under 5%). `tail` and the `half` cells (P3b) are pending, and P3b's core figures
assume the model holds, which E14 puts in doubt.

*Outcome for `tail`, no list, 2026-10-22 20:33 (E15):* share **missed** (0.1946 against
0.07-0.08); precision hit; recall equals the ceiling (hit) but is not within 20% of the share
(miss); exposure 37.5% against about 50% (marginal miss).

**P3, filed 2026-10-22 11:30.** X1 `core` and `tail`, no list: `sp_r` precision 1.00 for
unreachable senders; `sp_r` recall equal to the first-hop ceiling and within 20% of the
cell's outbound spy share, which is about 0.005-0.01 for `core` and 0.07-0.08 for
`tail` (the model, at its usual 85%). For `tail` with the list at 50% adoption and 50%
coverage, the population-level share falls by about a quarter, to 0.050-0.060. P(at least
one attributed transaction) for senders with 20 or more transactions: about 50% for
`tail` (E8 measured 51% at p = 0.071), under 5% for `core`.

**P4, filed 2026-10-22 13:40, before the queue started at 13:41.** Replicates of E13 on `simbox2`, seeds 23456 and 34567.
`lean_24_none_h300_k6_w6h`: 0.050-0.070 each, Q4 5-25% below Q1. `lean_legacy_none_h300_k6`
(1 h warmup, flat): 0.22-0.27 each. Dedup effect per seed (`24` against `legacy`, same seed):
-70% to -80%. The width follows the observed seed spread of 4-8%, plus a margin for the
cell's trend.

**P3b, filed 2026-10-22 15:00, before these cells are queued.** X1 `half` cells, seed 12345.
`core` with the list (one spy /24, listed in full) on half the honest nodes: the adopters
see no spies, so the population share is about half of `core` without the list, i.e.
0.002-0.005, and `sp_r` recall falls with it; P(at least one attributed transaction) for
senders with 20 or more transactions under 5%. `tail` with the list at 50% adoption and
50% coverage (10 of the 21 /24s): as P3, 0.050-0.060. Non-adopters' share equals the
no-list cell's within seed noise (4-8%); adopters' share about half of theirs.

*Outcome, `core` half, 2026-10-23 00:38 (E17):* light-node share **0.0162** against 0.002-0.005: **missed**, 3-8x high, because the range assumed E14's base was the model (E16). The structural claim held: 0.0162 is 0.46 of E14's 0.0352 (by quarter 0.49, 0.46, 0.45, 0.42); `sp_r` precision 1.000 and recall at the ceiling (3 of 1,013); 2 of 40 twenty-transaction senders exposed (5.0%, at the edge of "under 5%"). The `tail` half cell was not run (decision 10-22 22:37).

**P5, filed 2026-10-22 20:10, before the cells were queued at 20:11.** Two competing readings of E14's
relay excess, tested by `lean_24_none_h300_k1_w6h_m53_s12345` and `..._m26_...` (as `core`, but
53 and 26 spies in the one /24; same 6.4 h warmup). If the excess scales with the spies'
share of the peer lists (the poisoning reading), the light-node share is 0.012-0.025 at 53 and
0.006-0.015 at 26, and the relays still read 3x the model or more. If it does not (a
persistent early-phase effect), both read 0.025-0.045. Prior: 60% for the first, because the
H=150 cell with 26 spies and a 6.4 h warmup read 0.0145. A result in neither range counts as a
miss for both.

**P6, filed 2026-10-22 21:06, before anything is queued on `simbox3`.** (a) The platform check:
`lean_legacy_none_h71_k1_s12345` on `simbox3` (24.04 after the upgrade, a VM) reads 0.055-0.066
(0.061 on `phantom`, 0.0614 on `simbox2`); if it does not, nothing else run there is used.
(b) The X1 replicates, seeds 23456 and 34567: `core`, no list: light-node share 0.028-0.042
(E14: 0.0352), users' share 0.004-0.009, `sp_r` precision 1.00 and recall equal to the
ceiling; `tail`, no list: share 0.17-0.22 (E15: 0.1946), users' share 0.045-0.065, recall
0.03-0.05. Wider than P3's because the 0.8-12% seed spreads seen so far call for it.

*Outcome (a), 2026-10-22 23:43:* `lean_legacy_none_h71_k1_s12345` on `simbox3` reads **0.0641** (users 0.0628, observers 0.0651, relays 0.0747), inside 0.055-0.066; `phantom` read 0.061 and `simbox2` 0.0614. **`simbox3` is usable.** It is 4-5% above the other two, within their seed spreads. Fluff per hop 0.218, 1,093 stem txs. Wall 79 min, against 43 on `phantom` and 36 on `simbox2`: about 1.8x and 2.2x slower, so the 12-hour cells should take about 3.5-4 h there and the 28-hour P7b cell about 9-10 h. (b) is pending.

*Outcome, 53 spies, 2026-10-22 22:06:* light-node share **0.0173** (relays 0.0197, users 0.0068,
observers 0.0, medium 0.0022; by quarter 0.021, 0.018, 0.016, 0.014), inside the 0.012-0.025
that the spy-count reading predicted and outside the 0.025-0.045 of the other: **the count
reading is supported.** Share per spy IP: 0.0352/113 = 3.1e-4 at 113 spies and 0.0173/53 =
3.3e-4 at 53, i.e. the excess is proportional to the number of spy IPs in the one /24, which
a per-/24 rule should not see at all.

*Outcome, 26 spies, 2026-10-22 23:59* (`simbox2`, wall 110 min): light-node share **0.0095** (relays 0.0109, users 0.0027, observers 0.0004, medium 0.0036, miners 0.0415; by quarter 0.0114, 0.0094, 0.0088, 0.0084), inside the count reading's 0.006-0.015 and outside the other reading's 0.025-0.045. The relays read 2.4x the model (0.0045), under the "3x or more" clause, so that clause is a **miss** on its own. Share per spy IP: 3.7e-4 at 26 spies, 3.3e-4 at 53 and 3.1e-4 at 113, i.e. proportional to the spy count with a mild fall at the top. P5 as a whole: **the count reading is supported at both 53 and 26 spies.** E16 gives the mechanism: each spy IP is one more entry in the gray list that the fallback draws from, and the gray list is all that is left once the honest entries are used up.

**P7, filed 2026-10-22 22:36, before the long-warmup cells are queued (E16).** The probe cell shows the
relays' spy share jumping from about 0.02 to 0.23 at simulated hour 3.5 and then decaying, to
0.058 at hour 8 and 0.033 at hour 12 (the 6 h warmup's activity window reads 8-12). If the
spy-heavy connections made during the gray-list drain simply turn over, a later window reads
lower, tending to the model (0.0045 for `core`). Fit from the relay curve: excess over the
model decays with a time constant of 6.5-10 h between hours 8 and 12 (3 h between 5 and 8,
so it is slowing); light is 0.89 x relay in the probe cell. Same cell and
seed as `core` (113 spies in one /24, no list, seed 12345), only `--warmup` changes.
(a) `--warmup 57600` (16 h; window at sim hours 18-22): light-node share **0.009-0.022**.
(b) `--warmup 86400` (24 h; window at hours 26-30): light-node share **0.005-0.014**.
Outcomes: (b) inside 0.005-0.014 means the excess is a transient that a long enough warmup
removes. 0.014-0.030 for (b) means the decay stalls above the model; above 0.030 means there
is no decay and the excess is not a transient. A result between the ranges counts as a miss
of the narrower one. Prior 55% that (b) lands inside its range. The tail preset is not run
at a long warmup until one of these is read.

*Addendum, 2026-10-22 23:44, before any of these started:* the 16 h cell is placed on `simbox2` (free about 00:00) and the 24 h cell on both `phantom` (after the running `half` core cell, about 00:30) and `simbox3` (already running; about 2x slower, done about 09:30). Same cell, same seed, so the two 24 h reads also check the platforms against each other: expected within 25% of each other (`phantom` and `simbox3` agreed to 5% at H=71, but a 28 h run has more room to diverge). `phantom`'s memory over 28 simulated hours is unmeasured (12 h peaked at 18 GB of 32); if the guard trips it, `simbox3` is the 24 h read.

*Outcome (a), 2026-10-23 02:47, provisional (E18):* the 16 h cell was killed by the out-of-memory killer at simulated 20.4 h, so its window is 18-20.4 h. Light-node share **0.0099**, inside 0.009-0.022 at the bottom edge; the relay curve falls on, so the full window would have read lower. Treat as a partial hit. (b) is pending on `simbox3`; `phantom`'s copy of the 24 h cell was stopped at simulated 17.8 h (E18).

*Outcome (b), 2026-10-23 14:15 (E22c):* `lean_24_none_h300_k1_w24h_m113_fx_s12345` on `simbox3` (the rerun with
`--sim-fixed-randomx-seed`) reads a light-node share of **0.0044** (by quarter 0.0042, 0.0050, 0.0044, 0.0038; relays 0.0050,
users 0.0017, observers 0.0002). That is 0.0006 **below** the range 0.005-0.014: by the letter a **miss**, in the direction the
range was meant to confirm. The cell sits at the model (0.0045), so the excess is a transient that a day removes, which is what
"inside the range" was defined to mean. The range was badly built: its hypothesis was "decays to the model" but its floor (0.005)
sat above the model for light nodes (0.0045; light reads 0.88x the relays here), so a complete decay could not land inside it.
E18's relay extrapolation (0.005-0.007 for the relays, written 02:47 from the 16 h curve) is met at its bottom edge (0.0050).
Lesson for later ranges: a range whose hypothesis is "decays to X" has to contain X.

**P8, filed 2026-10-23 02:43, before the cells are queued (E18).** The `tail` preset (42 spies in 21 /24s,
`24` selection, seed 12345) with a 13 h warmup, so that the cell stops at simulated hour 19,
before the chain reaches block 2112 (E18); window 15-19 h. E15 read 0.1946 at a 6 h warmup,
flat across its window, against the model's 0.0822 (a ceiling). The `core` relays' excess fell
by about 0.33x between hours 12 and 18 (E18), but E15 did not fall inside its 8-12 h window, so
the `tail` excess may decay more slowly.
(a) No list: light-node share **0.11-0.17**; relays 0.13-0.19; users 0.04-0.07. Prior 55%.
A result above 0.17 means the `tail` excess does not decay at this scale (it is then either slow
or a steady state the model misses); below 0.11 means it decays like `core`'s.
(b) The ban list on half the honest nodes naming 10 of the 21 /24s (`--list half --ban-coverage
0.5`): adopters' spy slots fall by the listed share of spy /24s (10/21, 48%), non-adopters' do
not move, so the population share is **0.70-0.85 of (a)**; `sp_r` precision 1.00 and recall at
the ground-truth ceiling for both. P(a 20+-transaction sender has at least one transaction
attributed by `sp_r`) is 20-45% in (a) (E15: 37.5%, 15 of 40) and 15-40% in (b); with 40
senders the two cannot be told apart and are only recorded.

*Outcome, 2026-10-23 05:3x (E19):* (a) light share 0.1662, relays 0.1881, users 0.0478 and 18 of 40 exposed, all inside their ranges at the upper edge; flat by quarter. (b) ratio 0.79 (inside 0.70-0.85), `sp_r` precision 1.000 and recall at the ceiling in both cells (61 of 1,026; 52 of 1,027); exposure 20 of 40 against 15-40%: missed, not distinguishable from (a).

**P9, filed 2026-10-23 03:55, before the test cell is queued (E19).** `lean_24_none_h71_k1_w18h_fx_s12345` on `simbox3`
(H=71 reachable, 13 spies in one /24, `24` selection, no list; 124 daemons; a new `monerod-sim` with
`patches/monero-sim-fixed-randomx-seed.patch`, every daemon started with `--sim-fixed-randomx-seed`; 18 h warmup,
stops at 23 h simulated, past chain height 2113). It tests the patch, not the spy share. Expected: (a) exit 0, no
process failures, and the miners' logs show `HEIGHT` 2113 and on up to at least 2150; (b) the summary's block-propagation
and transaction checks pass, i.e. the daemons stay in consensus across the old seed epoch; (c) the box's free RAM
(`avail_mb`) and the summed process memory (`total_mb`) change by **less than 5 GB** between 40 minutes before and 40
minutes after the miner log first shows `HEIGHT 2112` (an unpatched 124-daemon cell would add roughly 124 x 256 MB = 32 GB
by my E18 reading). Any of: a daemon rejecting blocks above 2112, a memory jump of 10 GB or more, or a crash, counts as a
failure of the patch. If (c) holds on the patched binary the E18 mechanism is confirmed as far as a no-spike result can
confirm it; a spike with the flag on would mean the cause is not the seed change.
*(05:28, 2026-10-23: the patch test is written up as E20, since E19 is the 13 h `tail` pair.)*

*Outcome, 2026-10-23 07:29 (E20):* (a), (b) and (c) all hit: exit 0, 124 of 124 daemons at height 2188, no PoW errors, the flag in every daemon, memory within 6.5-7.2 GB (bound 5 GB) across block 2112. **The patch works.**

**P10, filed 2026-10-23 05:26, before the cells are queued (E19).** Two causes of the `tail` relays' excess that does not
decay (relay spy share 0.206 at hour 8, 0.186 at 15, 0.181 at 19; light share flat by quarter at 0.166; the
model's ceiling is 0.0822). **(a) The probe:** `lean_24_none_h300_k21_w13h_p3_m2_n600_s12345` on `phantom`, the
13 h `tail` cell with the first and last 3 relays of each start order dumping peer lists and logging `net.p2p`
(`probe_picks.py`, `peerlist_composition.py`). H1, the drain connections persist and new picks are at the model:
white-list picks of spies at relay age over 3 h are 0.06-0.11 of picks (21 spy /24s among about 263 candidate /24s
is 0.08). H2, the steady-state picks favour spies (recency or similar): that share is **0.12 or more**. Gray picks
at 0 or 1 unconnected /24 candidates are at least 90% spies either way (E16). Prior 40% H1, 40% H2, 20% neither.
**(b) A seed replicate:** `lean_24_none_h300_k21_w13h_m2_n600_s23456` on `simbox2` (same cell, seed 23456; the
chain and layout are the same, the random draws are not): light share **0.14-0.19**, users 0.035-0.06, `sp_r`
precision 1.000 and recall within 0.045-0.07 and equal to the ground-truth ceiling, 20+-transaction senders exposed
15-23 of 40.

*Outcome, 2026-10-23 08:29 (E21):* (a) H2 supported (white picks of spies 0.211 after 3 h, against 0.06-0.11 for H1); the stock rule's recency model over the relays' own lists gives 0.190. (b) share, users, precision and exposure in range; recall 0.031 (ceiling 0.031) below 0.045-0.07: missed.

**P11, filed 2026-10-23 07:30, before the cells are queued (E20).** Two 24 h-warmup cells with `--sim-fixed-randomx-seed` on every
daemon (stop at 30 h, window 26-30 h, seed 12345), the first long cells that can run on the 32 GB boxes.
(a) `tail`, no list (`lean_24_none_h300_k21_w24h_m2_n600_fx_s12345`, `phantom`): the relays' spy share fell by 12% between
hours 8 and 19 (E19), which if it continues gives a light-node share of **0.10-0.16** (E19: 0.1662 at a 13 h
warmup; the ceiling is 0.0822). A value above 0.16 means the excess is a steady state, not a slow transient (H2 of P10).
Prior 55% for the range.
(b) `core` with the list on half the honest nodes (`lean_24_half_h300_k1_w24h_m113_fx_s12345`, `simbox2`): if `core`'s excess
decays to the model (P7b: 0.005-0.014 without a list), the list gives about 0.5 x that: light-node share **0.0025-0.007**
(E17: 0.0162 at a 6 h warmup, which was 0.46 x the no-list cell). Unreachable users with 20 or more transactions
exposed: at most 1 of 40. `sp_r` precision 1.00 where it makes any guess.
Both runs also test whether a 32 GB box holds 30 simulated hours: lowest free RAM above 4 GB (the 12 h `core` cell bottomed
at 9.8 GB, the 20 h one at 10.3 GB, and `simbox2`'s memory was flat for two hours before the boundary).

*Note, 2026-10-23 08:29:* E21 gives a reason to expect (a) to read **above** 0.16 (the `tail` excess looks like a steady state of the stock rule at about 0.16-0.17 light), which would be a miss of the range, not a contradiction of the data.

*Outcome (a), 2026-10-23 12:07 (E22):* light-node share **0.1572**, inside 0.10-0.16 at the top edge: **hit**; relays 0.1805, users
0.0431, 12 of 40 exposed, lowest free RAM 10.9 GB (above 4 GB: hit). The 08:29 note's "above 0.16" missed by 0.003: the excess
decays, slowly (relays 0.2035 at hour 8 to 0.1783 at hour 30), and only in the relays that started early. (b) is pending on `simbox2`.

*Outcome (b), 2026-10-23 12:16 (E22):* light-node share **0.0025**, inside 0.0025-0.007 at the bottom edge: **hit**; 0 of 40 twenty-transaction
users exposed (at most 1: hit); `sp_r` made no guess, so the precision clause is untested; lowest free RAM 10.0 GB (hit). The relays
reach half the no-list model (0.0023) by hour 28: in `core` the excess is a transient that a day removes. The 0.5x ratio to the no-list
cell is checked against P7b when `simbox3` finishes. *2026-10-23 14:15:* P7b read 0.0044 (E22c), so the list's ratio is
**0.57x** at a 24 h warmup, against 0.46x at 6 h (E17) and the predicted "about 0.5x".

**P12, filed 2026-10-23 12:36, before the cell is queued (E22; the review's first gap).** `lean_legacy_none_h300_k21_w13h_m2_n600_s12345`
on `phantom`: the `tail` layout (42 spies in 21 /24s) under v0.18.4.2's selection (`legacy`, verified byte for byte against the
tag), 13 h warmup, window 15-19 h, seed 12345: the measured partner that the `24` reading (0.1662 in E19, 0.1626 in E21) has lacked;
until now "dedup gives this fleet more slots than the old rule" rests on the model's `legacy` value, 0.122. Measured `legacy` cells
sat at the model with one spy /24 (the cap) and at 1.8x it with six (0.2453 against 0.136, E4, E13), most of which recency explained.
Light-node share **0.16-0.26**, flat by quarter (Q4 within 10% of Q1, as every `legacy` cell has been), relays 1.0-1.2x light; prior
60%. Below 0.16 means stock dedup really does give a /24-diversified spy more slots than the old rule (what E15 read off the model);
above 0.26 means the old rule was worse against this fleet than X0's k=6 anchor suggests. The `24`/`legacy` ratio for the pair: 0.65-1.0.

*Outcome, 2026-10-23 15:25 (E23):* light **0.2857**, above 0.16-0.26: **miss (above)**; flat (Q4 0.6% above Q1): hit; relays 1.14x
light: hit; `24`/`legacy` ratio **0.58**, below 0.65-1.0: **miss (below)**. Both misses point the same way: the old rule was worse
against this fleet than the k=6 anchor suggested (2.34x the model against 1.8x), so stock dedup removes more than the models' 33%
(42%). The reading P12 was filed to test, "dedup gives a diversified spy more slots than the old rule", is refuted. 23 of 40 users
exposed, relays flat at 0.32-0.34 from hour 5 to 19 with a stationary start-order gradient (neither was predicted).

**P13, filed 2026-10-23 12:36, before the cells are queued (E22's dilution reading).** The `tail` layout at 21 /24s, `24` selection,
13 h warmup, window 15-19 h, seed 12345, with 1 and with 8 spies per /24: `lean_24_none_h300_k21_w13h_m1_n600_s12345` (21 spies,
`phantom`, after P12) and `..._m8_...` (168 spies, 508 daemons, `simbox2`). The 2-per-/24 cell reads 0.163-0.166 light, an excess of
about 0.08 over the 0.0822 ceiling. If the recency lock-in is diluted by the IPs the spy packs into a /24 (E22: the stock rule puts
one *random* IP per /24 forward before sorting by `last_seen`), the excess scales about as 1/m: (a) m=1: light **0.18-0.27**, relays
0.21-0.31, users 0.05-0.08; (b) m=8: light **0.09-0.14**, relays 0.10-0.16, users 0.03-0.05. Prior 50% that both land in range.
(a) at or below 0.166 refutes the dilution reading; (b) at or above 0.16 refutes it too (the excess would then follow the spy count,
as `core`'s transient did in P5, not the per-/24 dilution). `sp_r` precision 1.00 and recall at its ceiling in both; exposure is
recorded, not predicted. (b)'s lowest free RAM on a 32 GB box: above 6 GB (the 453-daemon cells bottomed at 9.8-10.9 GB). None of
the three cells needs the fixed-seed flag (they stop at 19 h), so they compare directly with E19 and E21.

*Outcome (b), 2026-10-23 15:45 (E24):* light **0.1749** against 0.09-0.14: **miss, above the 0.16 refutation threshold: the dilution
reading is refuted.** Relays 0.1968 (0.10-0.16: miss), users 0.0545 (0.03-0.05: miss, above), `sp_r` precision 1.000 and recall 0.063
at its ceiling (hit), 17 of 40 exposed (recorded). Lowest free RAM 3.4 GB at boot and 8.5 GB after the first simulated hour: the 6 GB
clause is **missed**. The cell is not stationary (relays -30% over hours 8-19, against -12% at 2 per /24), so the steady-state lock-in
at 8 per /24 is not separated from the transient. (a) is pending on `phantom`.

*Outcome (a), 2026-10-23 18:05 (E24):* light **0.1978** in 0.18-0.27: **hit**; relays 0.2250 (0.21-0.31) and users 0.0605 (0.05-0.08):
hits; `sp_r` precision 1.000, recall 0.052 at its ceiling: hit; 16 of 40 exposed (recorded). P13 overall: (a) hit, (b) refuted; the 1/m
scaling is not supported, a weaker dilution from 1 to 2 per /24 is; the steady state at 8 per /24 goes to P16.

**P14, filed 2026-10-23 15:35, before the cell is queued (open question 7's planned 100% point; E19, E22b).**
`lean_24_half_h300_k21_w13h_m2_n600_s12345` on `simbox2`: the `tail` layout under `24`, 13 h warmup, window 15-19 h, seed 12345,
with the ban list on half the honest nodes naming all 21 spy /24s (`--list half --ban-coverage 1.0`). Its partners: no list 0.1662
(E19, `phantom`) and 0.1626 (E21, seed 23456, `simbox2`); the list naming 10 of the 21 /24s 0.1309 (E19, `simbox2`). In `core` the
full list took the adopters to 0.0000 and lifted the non-adopters to 3.4x the no-list value (E22b: 0.0148 against 0.0044), light
0.57x. Here the adopters' share goes to 0 by construction (every spy /24 is refused), and the non-adopters are expected a little
above the no-list cell (the 50% cell implies about +8%: adopters at about half of 0.166 and light 0.1309 leave about 0.18 for the
non-adopters). Light-node share **0.08-0.12**; adopters at most 0.005; non-adopters 0.17-0.24; relays 1.0-1.25x light. `sp_r`
precision 1.00 and recall at its ceiling; unreachable users with 20 or more transactions exposed **5-12 of 40** (18 of 40 without
the list, E19; the adopting half's users cannot be exposed by `sp_r`, whose guess needs a spy first hop). Prior 55% for the light
range. Above 0.12 means the non-adopters absorb more than the adopters' lost slots (as `core`'s 3.4x hints); below 0.08 means the
list also lowers the non-adopters' share, a network effect worth a cell of its own.

**P16, filed 2026-10-23 18:05, before the cells are queued (E24: the spies-per-/24 question at steady state).** Two 24 h-warmup
cells with `--sim-fixed-randomx-seed` (stop at 30 h, window 26-30 h, seed 12345), the `tail` layout at 21 /24s under `24`, with 1 and
with 8 spies per /24: `lean_24_none_h300_k21_w24h_m1_n600_fx_s12345` (21 spies, `phantom`) and `lean_24_none_h300_k21_w24h_m8_n600_fx_s12345`
(168 spies, 508 daemons, `simbox3`, inserted ahead of the two remaining fillers). The 2-per-/24 partner exists (E22a: 0.1572 light,
0.1805 relays at 24 h; 0.1662 at 13 h). At 13 h the three read 0.198 / 0.166 / 0.175 (E24), but the 8-per-/24 cell was still shedding
its 168-spy drain (relays -30% over hours 8-19) while the 1-per-/24 cell was flat from hour 5; the question is the steady state.
(a) 1 per /24: light **0.18-0.22**, flat by quarter (the 13 h cell rose 2% over hours 8-19; E22a's 2-per-/24 cell fell 5% from 13 h
to 24 h), relays 0.20-0.26, users 0.05-0.08. (b) 8 per /24: if the IPs per /24 dilute the lock-in (E22's reading, which P13b could
not test cleanly), the steady state sits below the 2-per-/24 cell's 0.157: light **0.10-0.15**, relays 0.11-0.17, and the relay
curve flat over hours 20-30 (within 10%). At or above 0.155 means no dilution at steady state either, and the 1-to-2 gap is something
else (the drain's size, or small-number effects at 21 spies). Prior 60% for (a), 50% for (b). Exposure recorded, not predicted;
`sp_r` precision 1.00 and recall at its ceiling in both. Lowest free RAM: (a) on `phantom` above 8 GB (432 daemons; the 453-daemon
cells bottomed at 10.9-12.2 GB); (b) on `simbox3` (100 GB) above 60 GB.

**P15, filed 2026-10-23 15:35, before the cell is queued (E23's seed spread).** `lean_legacy_none_h300_k21_w13h_m2_n600_s23456` on
`simbox2`: E23's cell at the other seed and on the other box, as E21 did for the `24` cell (0.1626 against E19's 0.1662, a 2%
spread). Light-node share **0.26-0.31**, flat by quarter (Q4 within 10% of Q1), relays 1.05-1.25x light; the `24`/`legacy` ratio for
the seed-23456 pair (0.1626 over this read) **0.52-0.63**. Prior 65%. Below 0.26 means E23's 2.34x was the high end of its seed
spread and the 42% claim weakens toward the models' 33%; above 0.31 strengthens it.

## 6. Open questions

1. **The 1.5x in the dedup plateau** (E5). Needs a probe cell at long warmup with
   per-relay peer-list dumps, or a different mechanism.
   *2026-10-23:* resolved as far as E16-E22 go. The H=150 "plateau" at a 6 h warmup was the tail of the gray-list drain (E16)
   plus the recency lock-in (E21, E22); the only `24` cell read at a true long warmup with one spy /24 (H=71, 18 h, E20) sits at
   0.5x the model, so the model is not a reference in either direction and recency is the dominant unmodelled factor.
2. **k=6 `legacy` 1.3x above the recency model** (E4).
3. **The -70% dedup target.** Met on the lean k=6 cell (E13, -76%, one seed) and missed on
   the replica (-44% to -48%, E10); replicates of the first are queued (P4).
   *2026-10-23:* closed by E13's three seeds (-76%, -77%, -79%, all inside P4). The caveat stands that those `24` cells were read
   in the drain's tail (E16), so the steady-state effect against a dense spy is larger, and against a /24-diversified spy the
   question is P12.
4. **Embargo rate is 0.0 in every cell.** No reference value in the plan; a loop rate
   of 0.10-0.15 means stems do end by loop. Check whether the timer path can fire at
   this tx rate before calling X0's last target passed.
   *2026-10-23 (review):* **closed; the 0.0 is stock behaviour.** In v0.18.5.1 the embargo is drawn from
   `crypto::random_poisson_seconds{39}`, a `std::poisson_distribution` (sd about 6 s, so almost never below 25 s), armed in
   `tx_memory_pool::set_relayed` when the node stems a tx (`meta.dandelionpp_stem`), and cancelled when the fluff comes back
   (`add_tx` upgrades the entry to `fluff`, which clears the stem flag); `core::on_idle` polls the pool for due txs on every tick,
   gated by `m_next_check`. A fluff reaches every stem holder in about 5-20 s, so the timer fires only on a black-holed stem. The
   detection path is right (`pool_relay` with `was` = `stem` or `forward`; in the H=71 `24` run all 18,827 `pool_relay` events are
   `was=fluff`, the periodic re-relays). X0's last target has no reference value and is read as "stems fluff before any embargo
   fires", which holds; the embargo becomes a metric in X4 (the black-hole adversary).
5. **Reachable nodes show a higher spy outbound share than unreachable ones** in E8
   (0.117 against 0.066); the reachable class holds the medium hubs, which run 16-28
   outbound slots. Not yet separated.
   *2026-10-23:* explained by E14-E22: the reachable relays carry the excess (the gray-list drain, then the recency lock-in),
   because they take in peer lists from everyone who dials them; the unreachable users sit near the model in every cell. The
   medium hubs add a little on top (0.08-0.10 in the `tail` cells against 0.18 for the relays).
6. **Poisoned lists, port multiplexing, forwarding spies** (I2).
7. **Ban-list coverage** to use for the tail preset's headline cells; start at 100% and
   50%.
8. **Does mainnet drain the gray list?** E16 shows the lab's relays do. Measure it on real nodes
   (a `peerlist` dump from a long-running node: how many unconnected /24s does its gray list
   hold, and what is the spy /24 share of it) before X1's relay figures are quoted. If the
   drain is only a lab effect, either lengthen the warmup (P7), cap the white list in the
   simulator to the lab's ratio, or restart the relays after the drain and clear the gray
   list. Any of the three changes the experiment, so it is the user's call.
9. **The `half` list's tie-break is seeded by the simulation seed** (added 2026-10-23 14:40, from the review).
   `make_lean.py` passes `--seed <simulation seed>` to `spy_ban_list.py`, which orders equally dense /24s by a shuffle
   with that seed. In `tail` every /24 holds 2 spies, so all 21 are ties, and a seed-23456 replicate of the
   `--ban-coverage 0.5` cell bans a different 10 of the 21: a seed replicate would vary the seed and the banned set
   together. Only one such cell has run (`20261023_024332_lean_24_half_h300_k21_w13h_m2_n600_c50_s12345`). Options:
   a constant tie-break seed (later cells then ban a different set from that cell's unless the constant is 12345); a
   separate `--list-seed` defaulting to 12345, which keeps the existing cell's list; or leave it and replicate the
   list rather than the seed. Nothing is changed until a `half` `tail` replicate is queued; the owner's call.

## 7. Decisions log

Since 2026-10-22 14:40 the agent proceeds without asking and logs each decision here so it
can be reviewed and reversed. A row says what was decided, why, what it cost or risked, and
how to undo it. "User" means the user decided; "agent" means the agent did, and reported it
in the conversation.

| Date, time | Decision | Why | Undo | By |
|---|---|---|---|---|
| 10-22 | `phantom` and `simbox2` are for the antiproxy research; SoP runs on another box and agent, so the plan's "nothing runs before the campaign-8 queue" does not bind these boxes | the user said so after the agent proposed moving the SoP queue here | - | user |
| 10-22 | `simbox2` upgraded to Ubuntu 24.04 to match `phantom` | glibc and kernel parity: binaries built on one run on the other, and `--ksm` needs kernel 6.4 or newer | restore from `~/.monerosim.feb2026` and reinstall 22.04 (not planned) | user |
| 10-22 | `legacy` X0 replicates on `simbox2`; `24` replicates on `phantom` | `legacy` is flat so it cannot suffer from the drain; the `24` replicates waited for the first `24` seed to show whether the replica drains (it barely does) | delete the queue lines | agent |
| 10-22 | Long-warmup k=6 `24` cell queued on `simbox2` | it is the one run that tests the -70% target at a larger honest set; `simbox2` would otherwise idle | already ran (E13) | agent |
| 10-22 | Add a ban-list coverage knob; keep this journal | the real list misses part of a diversified tail; the user asked for a record | - | user |
| 10-22 13:40 | Seeds 23456 and 34567 of the long-warmup cell and of its `legacy` partner queued on `simbox2` (4 cells, about 7 h) | the plan wants 3 seeds per cell; the P1 result sat on the edge of its interval | remove lines from `~/queue/q.txt` on `simbox2` | agent |
| 10-22 14:40 | Commit the uncommitted work in three commits on `feat/spy-relay-log`, not pushed | the user asked to commit; push was not asked for | `git reset --soft HEAD~3` | user asked, agent split |
| 10-22 14:40 | X1 `core` and `tail` cells (no list, seed 12345) queued on `phantom` behind `x0_24_half_s34567`, i.e. start about 16:30 | `phantom` would idle; the instruments are verified at replica scale (E8); P3 was filed in advance; the cells are at H=300 so memory is not a risk (H=300 cells bottomed at 8 GB free) | delete the two lines from `x0_queue3.txt` (scratchpad) before 16:30 | agent |
| 10-22 14:40 | X1 starts before X0's replicates finish | X0's remaining runs do not change the stock-binary baseline X1 needs; both boxes are otherwise full | - | agent |
| 10-22 14:40 | `simbox2` keeps the old `make_lean.py`/`spy_ban_list.py` until an X1 cell has to run there | the cells it runs now were generated here with the layout check and copied (md5 checked) | - | agent |
| 10-22 14:40 | The spy ban list for X1 tail cells names the densest 50% of /24s at first | the real list names the dense fleet and part of the tail; the true coverage is unknown, so 100% and 50% bracket it | `--ban-coverage` | agent |
| 10-22 15:00 | X1 `half` cells (`core` with the list in full; `tail` with 10 of 21 /24s listed) queued on `phantom` after the two no-list cells; P3b filed first | the `half` cells are needed whatever the no-list results are; queueing now keeps the box busy overnight; a surprise in the first two cells can still be answered by deleting the last two lines | delete the two lines from `x0_queue3.txt` before they start (about 21:00 and 23:10) | agent |
| 10-22 15:00 | A fourth, small commit (`c977cd44`: P3b and the queue decisions), beyond the three the user asked for | keeps the committed journal in step with the queued runs | `git reset --soft HEAD~1` | agent; no more commits without asking |
| 10-22 ~18:55 | A probe version of the `core` cell (`..._p3_m113`, first/last 3 relays dump peer lists and log `net.p2p` DEBUG) queued next on `phantom`, ahead of the two `half` cells | E14's relays hold 7-9x the modelled spy share after a 6.4 h warmup; every later X1 number rests on knowing why, and E5 found the cause the same way | remove the line from `x0_queue3.txt` before about 20:40 | agent |
| 10-22 20:10 | Two diagnostic cells for E14 on `simbox2` (`core` with 53 and 26 spies in the /24), ahead of any X1 replicate; P5 filed first | `simbox2` is idle and the probe cell on `phantom` does not start until about 20:40; the spy count is the one factor that differs between the cells that drained (E5) and this one; P5 separates the two readings | `~/queue/q.txt` on `simbox2` | agent |
| 10-22 ~20:55 | Set up the user's new VM (`simbox3`) with the HWE kernel only, not a release upgrade, and rebooted it once | it is shared (other accounts, 148 GB of their data, 50 days of uptime); the user said I might upgrade it, and `--ksm` needs only kernel 6.4 or newer; keeping the userland leaves others' R/Python alone. Costs: the binary is built with gcc 11 and glibc 2.35, unlike the 24.04 boxes, so the H=71 validation decides whether it can be used. The reboot ended one idle `screen` session (`transfer`, a bare shell, 29 days old) | `apt remove` the 6.8 kernel and boot the old one from GRUB; `rm -rf ~/monerosim ~/.cargo` | agent |
| 10-22 21:06 | Upgrade `simbox3` to Ubuntu 24.04.5 after all (full-upgrade, then release upgrade); the 22.04 build was killed | the user said to ("no one really uses it") after seeing that it is shared; 24.04 matches the other two boxes (gcc 13, glibc 2.39), which removes the compiler as a reason for results to differ. The full-upgrade also updated the R packages another account installed | restore from nothing: there is no backup of the VM | user |
| 10-22 21:30 | During the `simbox3` upgrade: rebooted while `dpkg --configure --pending` was still running (my error: the reboot sat in the same command as the check, with no gate), then finished the configuration by hand; `grub-pc` would not configure because its saved install device pointed at a disk that no longer exists (`/dev/disk/by-id/ata-QEMU_HARDDISK_QM00001`; the VM's disk is now virtio `vda`), so I set `grub-pc/install_devices` to `/dev/vda` (BIOS boot, with a 1 MB BIOS boot partition) and reconfigured | a half-configured bootloader package leaves apt broken and risks the next kernel update; the VM had booted fine twice, so the old boot code was intact | none needed (the box boots and `dpkg --audit` is clean); the grub-install writes to `vda`'s boot area | agent |
| 10-22 22:22 | The `simbox3` queue holds the H=71 `legacy` validation first, then the four X1 replicates (`core` and `tail`, seeds 23456 and 34567, no list), all generated on `phantom` and copied with an md5 check; the driver is the `simbox2` one (`~/queue/x0_queue.sh`). The replicates run on even if the validation fails | P6 was filed at 21:06; an idle 40-vCPU box earns nothing by waiting for a 1-2 h result, and a failed P6a only means the replicate results are discarded (they stay in the register, flagged) | edit `~/queue/q.txt` on `simbox3` to remove cells; to stop the driver, `kill` the pid of `queue/x0_queue.sh` (it kills Shadow on a TERM) | agent |
| 10-22 22:25 | Archives on `simbox3` are kept, not deleted after each run (this changes the 21:06 plan) | the archives are 2-8 GB (the H=300 `core` cell is 7.7 GB on `phantom`, the H=71 cell 2.7 GB), so five runs need about 35 GB of the 88 GB free; the driver's 30 GB floor stops the queue first. Prune only when free space falls below 45 GB, after the estimators and the register entry | `rm -rf ~/monerosim_archives/<run>` once registered | agent |
| 10-22 22:37 | Probe read (E16). On `phantom` the queued `half` tail cell (`..._c50`) was replaced by `lean_24_none_h300_k1_w16h_m113_s12345` (the `core` cell with a 16 h warmup); the running `half` core cell (started 22:31) was left to finish | E16 shows every `24` share so far is the tail of a transient, so a 50%-list tail cell at a 6 h warmup would measure the list's effect on the transient, not at steady state; the 16 h cell is one of the two P7 points (filed 22:36 first) | re-add `lean_24_half_h300_k21_w6h_m2_n600_c50_s12345` to `x0_queue3.txt` (scratchpad) | agent |
| 10-22 22:37 | On `simbox3` the 24 h-warmup `core` cell (P7b) was put second in the queue, ahead of the four 6 h-warmup replicates, which stay queued after it | the replicates repeat the transient's tail; the 24 h cell asks whether the transient goes away, which decides what the replicates mean. It needs the 100 GB (28 sim-hours, memory growth with sim time unknown). If P6a fails the cell is discarded | edit `~/queue/q.txt` on `simbox3` | agent |
| 10-22 23:44 | The 16 h-warmup `core` cell moved from `phantom` to `simbox2` (queued behind the 26-spy cell), and `phantom` now runs the 24 h cell after its `half` core cell; `simbox3` keeps its own 24 h run | gets both P7 points in about 3.7 h (`simbox2`, from about 00:00) and about 5 h (`phantom`, from about 00:30) instead of waiting 10 h for `simbox3`; the duplicate 24 h run is a platform check. Risk: `phantom` may run short of RAM at 28 simulated hours (the driver kills Shadow at 1.5 GB free) | edit `~/queue/q.txt` on `simbox2`, `x0_queue3.txt` (scratchpad) on `phantom` | agent |
| 10-23 02:40 | Stopped `phantom`'s 24 h-warmup cell (sent TERM to the driver; Shadow killed cleanly, 17.8 simulated hours in, before its window) | `simbox2`'s 16 h cell had just been OOM-killed at block 2112 (E18); `phantom` was 20 minutes of wall time from the same point with 10.6 GB free and a full 4 GB swap, and the OOM killer on this box would have to choose among the processes of the machine this session runs on. `simbox3` runs the same cell with 80 GB free | none needed; rerun later with a swap file or a higher chain snapshot | agent |
| 10-23 02:43 | Two tail cells at a 13 h warmup (stop at simulated 19 h): no list on `phantom`, 50% list at 50% coverage on `simbox2`; P8 filed first (the same minute, 02:43) | both boxes were idle, both are limited to cells that stop before block 2112 (E18), and the tail preset has not been seen past a 6 h warmup (E15 was flat across its window); the pair also gives the list's effect at a later warmup | delete the lines from the queue files (`x0_queue3.txt` in the scratchpad on `phantom`, `~/queue/q.txt` on `simbox2`) | agent |
| 10-23 03:58 | New patch `patches/monero-sim-fixed-randomx-seed.patch` (`--sim-fixed-randomx-seed`, off by default; pins the RandomX seed height to 0, so there is no epoch change at block 2113), added to `setup.sh`'s list; `make_lean.py --fixed-rx-seed` puts the flag in `daemon_defaults`. Built into `monerod-sim` on `simbox3` only (old binary kept as `~/.monerosim/bin/monerod-sim.pre-fixedseed`) by running `install_sim_monerod` alone | swap cannot cover the spike: `simbox3`'s 24 h cell tripped the guard at 350 MB free after growing by 80 GB in 90 s and still rising (E18); the patch removes the cause. Below block 2113 the seed is height 0 either way, so cells that stop earlier behave identically. Risk: a different build from the other boxes; the flag does nothing unless set | `git checkout setup.sh`, delete the patch; on `simbox3` copy the `.pre-fixedseed` binary and provenance back | agent |
| 10-23 03:58 | `simbox3` queue restarted at 03:55: P9's patch test (`lean_24_none_h71_k1_w18h_fx_s12345`, to 23 h simulated), then the 24 h `core` cell with the flag (`..._w24h_m113_fx_s12345`, P7b), then the four 6 h replicates | the patch must pass block 2113 before anything depends on it; the 24 h cell is the one P7 needs; the replicates stay as filler | edit `~/queue/q.txt` on `simbox3` | agent |
| 10-23 05:28 | Two more 19 h cells (P10 filed first): a `tail` probe (`..._w13h_p3_m2_n600_s12345`) on `phantom` and a seed replicate of the 13 h `tail` cell (seed 23456) on `simbox2` | the `tail` relay excess did not decay (E19), so its cause is unknown and X1's headline cell rests on it; both boxes were idle; both cells stop at hour 19 so the stock binary is safe | delete the lines from the queue files | agent |
| 10-23 08:05 | Rebuilt `monerod-sim` with the fixed-seed patch on `simbox2` (old binary kept as `~/.monerosim/bin/monerod-sim.pre-fixedseed`; new sha256 `345d4ced95f1...`), then started `lean_24_half_h300_k1_w24h_m113_fx_s12345` (P11b, 30 simulated hours) | P9 passed on `simbox3` (E20); the box was idle and this is the first long cell it can run | restore the `.pre-fixedseed` binary and provenance | agent |
| 10-23 08:10 | Same on `phantom` (new sha256 `1472ed18703f...`), then started `lean_24_none_h300_k21_w24h_m2_n600_fx_s12345` (P11a, 30 simulated hours) | as above; the memory of a 30 h run on a 32 GB box is unmeasured, the driver's 1.5 GB guard applies | restore the `.pre-fixedseed` binary and provenance | agent |
| 10-23 12:36 | Record fixes from the user's review: the two aborted 24 h `core` runs registered (`simbox3` TRIP `20261022_234237`, `phantom` STOPPED `20261023_003351`), E18 given the measured spike as a dated addendum, open questions 1, 3, 4 and 5 closed with dated lines (4 after reading the 0.18.5.1 embargo code), the status and binary paragraphs refreshed, three misplaced decision rows moved into date order, `run_register.py --box` help names `simbox3` | the journal's own rule is that nothing is deleted and the status must be current; the user asked for it after the review | revert the commit | user asked, agent did |
| 10-23 12:36 | P12 (the `legacy` partner of the `tail` cell) and P13 (`tail` at 1 and 8 spies per /24) filed, then the three cells queued: `phantom` runs the `legacy` partner then the 1-per-/24 cell, `simbox2` the 8-per-/24 cell (copied, md5 checked); all stop at 19 h simulated on the stock rule without the flag | the user said to file the two new cells; both boxes were idle; the `legacy` partner is the missing measurement behind "dedup gives the diversified spy more slots", and the per-/24 pair tests E22's dilution reading | delete the lines from `x0_queue3.txt` (scratchpad, `phantom`) and `~/queue/q.txt` (`simbox2`); `kill` the driver pids | user asked, agent queued |
| 10-23 14:40 | The two plan deviations the review found unstated (tx rate about 150x mainnet, variant R spies) and the `half`-list tie-break confound are stated in the record (section 2, Known gaps, open question 9); `spy_ban_list.py` and `make_lean.py` are not changed | the user approved the record fixes, not code changes; a different tie-break would make later `half` tail cells incomparable with the seed-12345 one already run (`20261023_024332_..._c50`), so which way to go is the owner's call | revert the journal lines | agent |
| 10-23 15:35 | `simbox2`, idle after P13b, gets two 19 h cells: the full-coverage `half` `tail` cell (P14, open question 7's planned 100% point) and then the seed-23456 replicate of E23's `legacy` `tail` cell (P15); both filed and committed before queueing, both generated on `phantom` and copied with an md5 check | the 100% list is the headline X1 cell for `tail` and was planned next to the 50% one ("start at 100% and 50%"); the replicate turns E23's single-seed 42% into a two-seed claim; neither needs P13a's result (17:50), while the candidate-count follow-up it suggests (42 /24s at 1 spy each) does, so that waits | remove the lines from `~/queue/q.txt` on `simbox2`, or kill the driver by pid | agent |
| 10-23 17:18 | A control box for the agents is set up at the user's request: VM `virt9900x` (192.168.1.140, 12 vCPU, 11 GB, Ubuntu 24.04, no experiments on it). Two users created there with `adduser --disabled-password`, no sudo: `antiproxy` (this lab; my key authorized) and `selfishmining` (the other project's agent; `.ssh` created, no key). Nothing of the owner's `lever65` account was touched | the user wants every agent's session on one control box, each project under its own Unix user with its own clone, with experiments run remotely on compute boxes (the lab is to move its big cells to a 256 GB Threadripper, the selfish-mining sims to the small boxes); separate users make the separation enforced | `sudo deluser --remove-home antiproxy` (and `selfishmining`) on the control box | user (decision), agent (execution) |
| 10-23 17:22 | Control box, continued: `python3-venv` and `python3-pip` installed system-wide via the owner's sudo (the only system change); the repository cloned from a git bundle to `/home/antiproxy/monerosim` on this branch (no push); my memory, skills and the handoff note copied into the `antiproxy` account; Claude Code 2.1.309 installed under `~/.local` there (login left to the user); the account's own key authorized on my `lever65` accounts on `phantom`, `simbox2` and `simbox3` so a session there can reach the running queues | the user asked for the agents' sessions to move to the control box; the lab's compute boxes are still the `lever65` accounts until per-project users exist there | `apt-get remove python3-venv python3-pip`; delete the `antiproxy@virt9900x` line from each box's `~/.ssh/authorized_keys`; `rm -rf /home/antiproxy/monerosim` | agent |
| 10-23 18:05 | P16 filed and committed, then queued: the 1-per-/24 24 h cell on `phantom` (idle since 17:49) and the 8-per-/24 24 h cell at the head of `simbox3`'s queue, ahead of the two seed-34567 fillers (the running seed-23456 `tail` filler finishes first). Both generated on `phantom`, the `simbox3` copy md5-checked | P13 ended split (a hit, b refuted) because the 8-per-/24 window sat inside its own drain's transient; only 24 h warmups compare steady states, and E22a already holds the 2-per-/24 point; the fillers are lower value than this | remove the line from `~/queue/q.txt` on `simbox3`; kill `phantom`'s driver by pid | agent |

## 8. Files

- Per-run record: `docs/spy_journal/runs/<run_id>/`
- Queue drivers: `docs/spy_journal/drivers/`; queue event logs: `docs/spy_journal/logs/`
- Exploratory scripts as run: `docs/spy_journal/adhoc/`
- Cell generators: `test_configs/x0/make_cells.sh` (the 12 X0 cells),
  `test_configs/x0/make_lean.py` (lean and X1 cells); `scripts/spy_ban_list.py`
- Scorers: `analysis/spy/x0_calibration.py`, `analysis/spy/spy_estimators.py`;
  register: `analysis/spy/run_register.py`
