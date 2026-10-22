# Spy-node defenses: experimental journal

The single record of the experiments for the spy (proxy) node test plan,
`docs/20261018_spy_node_defenses.md`. It covers the lab on `phantom` and
`simbox2` only. The Share-or-Perish (MRL #146) campaigns run on another box
under another agent and are not recorded here.

**Status (2026-10-22, 14:35).** X0, the calibration, is under way: the
`legacy` leg passes its targets, the /24-dedup leg reads 44-48% below `legacy` on the
replica and 76% below on the lean k=6 cell (one seed; replicates queued), against a
target of about 70%. X1 has
instruments and two candidate presets, with nothing run yet. Entries E1-E13
below; open questions in section 6.

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

**Queue and guards.** Cells run one at a time from a queue file by
`docs/spy_journal/drivers/x0_queue*.sh`, which kills Shadow if free RAM drops below
1.5 GB, free disk below 30 GB, or swap grows past its allowance while RAM is short,
then scores the run. Event logs of the queues are in `docs/spy_journal/logs/*.events`.

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

### E10. X0 replicates (2026-10-22, in progress)

Light-node outbound share by cell and seed. Blank = not finished.

| Cell | 12345 | 23456 | 34567 | Target |
|---|---|---|---|---|
| `legacy/none` | 0.132 | 0.1385 | 0.133 | ~0.15 |
| `legacy/half` | 0.0687 | 0.0689 | 0.0632 | ~0.07 |
| `24/none` | 0.0703 | 0.0734 | 0.0690 | ~70% below `legacy/none` |
| `24/half` | 0.0347 | 0.0373 | | ~70% below `legacy/half` |

**So far.** `legacy` has all three seeds in both cells and passes both targets:
`legacy/none` within 0.006 of each other (4% of the mean, 0.9x the target),
`legacy/half` 0.0687, 0.0689, 0.0632 (mean 0.0669, spread 0.0057 = 8.5% of the mean, 0.96x
the target). The third `legacy/half` seed also has more fluff per hop than any other
cell (0.235 against 0.19-0.22; implied 4.3 hops, still inside the 1.5x window around 5). `24/none` has all three seeds (mean 0.0709, 47% below `legacy/none`'s 0.1345, spread 0.0044);
`24` is 44-48% below `legacy` in the five `24` cells so far
(0.0703, 0.0734 and 0.0690 against 0.1345; 0.0347 and 0.0373 against 0.0669), which is 1.7-1.8x
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
- One seed. Seeds 23456 and 34567 are queued, with their `legacy` partners (P4).

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
inside the predicted 0.066-0.078 (a hit).** Score so far: 2 hits, 1 miss.

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

## 8. Files

- Per-run record: `docs/spy_journal/runs/<run_id>/`
- Queue drivers: `docs/spy_journal/drivers/`; queue event logs: `docs/spy_journal/logs/`
- Exploratory scripts as run: `docs/spy_journal/adhoc/`
- Cell generators: `test_configs/x0/make_cells.sh` (the 12 X0 cells),
  `test_configs/x0/make_lean.py` (lean and X1 cells); `scripts/spy_ban_list.py`
- Scorers: `analysis/spy/x0_calibration.py`, `analysis/spy/spy_estimators.py`;
  register: `analysis/spy/run_register.py`
