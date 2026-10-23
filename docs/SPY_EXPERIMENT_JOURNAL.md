# Spy-node defenses: experimental journal

The single record of the experiments for the spy (proxy) node test plan,
`docs/20261018_spy_node_defenses.md`. It covers the lab on `phantom`, `simbox2` and
`simbox3` only. The Share-or-Perish (MRL #146) campaigns run on another box
under another agent and are not recorded here.

**Status (2026-10-22, 22:39).** X0, the calibration, is done: the `legacy` leg passes its targets
(3 seeds per cell) and the /24-dedup leg reads 45-47% below `legacy` on the 69-/24 replica and 77%
below on the lean k=6 cell. X1 has begun, and E16 explains its main surprise: the lab's relays
hold far more spies than the selection model predicts (E14, E15) because their gray lists drain
to nothing but spies about 2-3 h after they start, the fallback then picks spies, and those
connections outlast the 6 h warmup. Every `24` share measured so far is therefore the tail of a
transient. P7 (filed 22:36) tests whether a 16 h and a 24 h warmup remove it; those cells are
queued on `phantom` and `simbox3`. `simbox3`, the third box, passed its platform check
(P6a, 0.0641; about 2x slower than `phantom`) and is running the 24 h cell. Entries E1-E21 below; open questions in section 6.

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

**Simulator settings.** Shadow (shadowformonero), `--bootfast --ksm`, KSM at 20,000
pages per 20 ms, `runahead 100ms`, `native_preemption`, 2 process threads (KSM at 10,000 pages in the first pilots), 5,000-node
CAIDA topology with weighted regions and prefix sharing 0.31 x 3. Spies are variant R
(stock `monerod-sim` that dials one fallback seed and logs relays); they announce
through the seeds only, and do not poison peer lists or multiplex ports.

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
- The queue event logs are snapshots through 2026-10-22 ~11:30; later events are in
  the register and are added to the logs when the journal is next updated.
- Entries E1-E12 were written after the fact (section 1); E13 onwards were written when the result came in.

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
| `20261022_235712_lean_24_none_h300_k1_w16h_m113_s12345` | simbox2 | 113 / 1 | 300 / 242 | 0.0099 (0.0045) | 0.010, 0.010, 0.009, - | 0.214 | 501 | 2h 37m | 10.0 | 137 | E18 / P7a, PARTIAL: killed by the kernel OOM (exit 137) at sim 20:26:35 = block 2112, the RandomX seed change; scored window is 18-20.4 h of 18-22 h. Light share 0.0099 (provisional) |
| `20261023_024331_lean_24_none_h300_k21_w13h_m2_n600_s12345` | phantom | 42 / 21 | 300 / 242 | 0.1662 (0.0822) | 0.167, 0.169, 0.167, 0.163 | 0.211 | 1099 | 2h 37m | 11.5 | 0 | E19 / P8a: X1 tail, no list, 13 h warmup (stop 19 h, window 15-19 h), seed 12345; 0.1662 vs 0.1946 at the 6 h warmup (E15); flat by quarter |
| `20261023_024332_lean_24_half_h300_k21_w13h_m2_n600_c50_s12345` | simbox2 | 42 / 21 | 300 / 242 | 0.1309 (0.0822) | 0.130, 0.130, 0.130, 0.133 | 0.207 | 1096 | 2h 32m | 12.5 | 0 | E19 / P8b: X1 tail, ban list on half the nodes naming 10 of 21 /24s, 13 h warmup, seed 12345; 0.1309 = 0.79 x the no-list cell |
| `20261023_035553_lean_24_none_h71_k1_w18h_fx_s12345` | simbox3 | 13 / 1 | 71 / 60 | 0.0094 (0.0181) | 0.011, 0.008, 0.009, 0.010 | 0.214 | 1147 | 3h 29m | 86.5 | 0 | E20 / P9: patched monerod-sim (--sim-fixed-randomx-seed on every daemon), H=71, to 22.5 h simulated; passed block 2112 at sim 19:55 with no memory step; all 124 daemons end at height 2188 |
| `20261023_052647_lean_24_none_h300_k21_w13h_m2_n600_s23456` | simbox2 | 42 / 21 | 300 / 240 | 0.1626 (0.0831) | 0.165, 0.166, 0.161, 0.159 | 0.192 | 1099 | 2h 33m | 12.5 | 0 | E21 / P10b: seed replicate of the 13 h tail cell (seed 23456); 0.1626 vs 0.1662 for seed 12345 |
| `20261023_052647_lean_24_none_h300_k21_w13h_p3_m2_n600_s12345` | phantom | 42 / 21 | 300 / 242 | 0.1626 (0.0822) | 0.163, 0.162, 0.164, 0.162 | 0.191 | 1097 | 2h 37m | 11.5 | 0 | E21 / P10a: the tail probe (first/last 3 relays of each start order log picks and dump lists), 13 h warmup, seed 12345; 0.1626 vs 0.1662 without the probe |
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
where it ends. (`probe_relay_share.py` gives the slot shares.)
**Scores (P10).** (a) H2 supported, H1 refuted, as above; the gray-pick clause (at least 90% spies at 0-1 candidates) could not be
tested (5 picks). (b) light share 0.1626 in 0.14-0.19: hit; users 0.0502 in 0.035-0.06: hit; precision 1.000: hit; recall 0.031
outside 0.045-0.07: **missed**, though equal to its ceiling; 16 of 40 in 15-23: hit.

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

## 6. Open questions

1. **The 1.5x in the dedup plateau** (E5). Needs a probe cell at long warmup with
   per-relay peer-list dumps, or a different mechanism.
2. **k=6 `legacy` 1.3x above the recency model** (E4).
3. **The -70% dedup target.** Met on the lean k=6 cell (E13, -76%, one seed) and missed on
   the replica (-44% to -48%, E10); replicates of the first are queued (P4).
4. **Embargo rate is 0.0 in every cell.** No reference value in the plan; a loop rate
   of 0.10-0.15 means stems do end by loop. Check whether the timer path can fire at
   this tx rate before calling X0's last target passed.
5. **Reachable nodes show a higher spy outbound share than unreachable ones** in E8
   (0.117 against 0.066); the reachable class holds the medium hubs, which run 16-28
   outbound slots. Not yet separated.
6. **Poisoned lists, port multiplexing, forwarding spies** (I2).
7. **Ban-list coverage** to use for the tail preset's headline cells; start at 100% and
   50%.
8. **Does mainnet drain the gray list?** E16 shows the lab's relays do. Measure it on real nodes
   (a `peerlist` dump from a long-running node: how many unconnected /24s does its gray list
   hold, and what is the spy /24 share of it) before X1's relay figures are quoted. If the
   drain is only a lab effect, either lengthen the warmup (P7), cap the white list in the
   simulator to the lab's ratio, or restart the relays after the drain and clear the gray
   list. Any of the three changes the experiment, so it is the user's call.

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
| 10-22 15:00 | X1 `half` cells (`core` with the list in full; `tail` with 10 of 21 /24s listed) queued on `phantom` after the two no-list cells; P3b filed first | the `half` cells are needed whatever the no-list results are; queueing now keeps the box busy overnight; a surprise in the first two cells can still be answered by deleting the last two lines | delete the two lines from `x0_queue3.txt` before they start (about 21:00 and 23:10) | agent |
| 10-22 15:00 | A fourth, small commit (`c977cd44`: P3b and the queue decisions), beyond the three the user asked for | keeps the committed journal in step with the queued runs | `git reset --soft HEAD~1` | agent; no more commits without asking |
| 10-22 ~18:55 | A probe version of the `core` cell (`..._p3_m113`, first/last 3 relays dump peer lists and log `net.p2p` DEBUG) queued next on `phantom`, ahead of the two `half` cells | E14's relays hold 7-9x the modelled spy share after a 6.4 h warmup; every later X1 number rests on knowing why, and E5 found the cause the same way | remove the line from `x0_queue3.txt` before about 20:40 | agent |
| 10-22 20:10 | Two diagnostic cells for E14 on `simbox2` (`core` with 53 and 26 spies in the /24), ahead of any X1 replicate; P5 filed first | `simbox2` is idle and the probe cell on `phantom` does not start until about 20:40; the spy count is the one factor that differs between the cells that drained (E5) and this one; P5 separates the two readings | `~/queue/q.txt` on `simbox2` | agent |
| 10-22 21:06 | Upgrade `simbox3` to Ubuntu 24.04.5 after all (full-upgrade, then release upgrade); the 22.04 build was killed | the user said to ("no one really uses it") after seeing that it is shared; 24.04 matches the other two boxes (gcc 13, glibc 2.39), which removes the compiler as a reason for results to differ. The full-upgrade also updated the R packages another account installed | restore from nothing: there is no backup of the VM | user |
| 10-22 21:30 | During the `simbox3` upgrade: rebooted while `dpkg --configure --pending` was still running (my error: the reboot sat in the same command as the check, with no gate), then finished the configuration by hand; `grub-pc` would not configure because its saved install device pointed at a disk that no longer exists (`/dev/disk/by-id/ata-QEMU_HARDDISK_QM00001`; the VM's disk is now virtio `vda`), so I set `grub-pc/install_devices` to `/dev/vda` (BIOS boot, with a 1 MB BIOS boot partition) and reconfigured | a half-configured bootloader package leaves apt broken and risks the next kernel update; the VM had booted fine twice, so the old boot code was intact | none needed (the box boots and `dpkg --audit` is clean); the grub-install writes to `vda`'s boot area | agent |
| 10-22 ~20:55 | Set up the user's new VM (`simbox3`) with the HWE kernel only, not a release upgrade, and rebooted it once | it is shared (other accounts, 148 GB of their data, 50 days of uptime); the user said I might upgrade it, and `--ksm` needs only kernel 6.4 or newer; keeping the userland leaves others' R/Python alone. Costs: the binary is built with gcc 11 and glibc 2.35, unlike the 24.04 boxes, so the H=71 validation decides whether it can be used. The reboot ended one idle `screen` session (`transfer`, a bare shell, 29 days old) | `apt remove` the 6.8 kernel and boot the old one from GRUB; `rm -rf ~/monerosim ~/.cargo` | agent |
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
| 10-22 14:40 | X1 starts before X0's replicates finish | X0's remaining runs do not change the stock-binary baseline X1 needs; both boxes are otherwise full | - | agent |
| 10-22 14:40 | `simbox2` keeps the old `make_lean.py`/`spy_ban_list.py` until an X1 cell has to run there | the cells it runs now were generated here with the layout check and copied (md5 checked) | - | agent |
| 10-22 14:40 | The spy ban list for X1 tail cells names the densest 50% of /24s at first | the real list names the dense fleet and part of the tail; the true coverage is unknown, so 100% and 50% bracket it | `--ban-coverage` | agent |

## 8. Files

- Per-run record: `docs/spy_journal/runs/<run_id>/`
- Queue drivers: `docs/spy_journal/drivers/`; queue event logs: `docs/spy_journal/logs/`
- Exploratory scripts as run: `docs/spy_journal/adhoc/`
- Cell generators: `test_configs/x0/make_cells.sh` (the 12 X0 cells),
  `test_configs/x0/make_lean.py` (lean and X1 cells); `scripts/spy_ban_list.py`
- Scorers: `analysis/spy/x0_calibration.py`, `analysis/spy/spy_estimators.py`;
  register: `analysis/spy/run_register.py`
