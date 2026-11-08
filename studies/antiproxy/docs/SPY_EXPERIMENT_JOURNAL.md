# Spy-node defenses: experimental journal

The single record of the experiments for the spy (proxy) node test plan,
`docs/20261018_spy_node_defenses.md`. It covers the lab on `phantom`, `simbox2` and
`simbox3` only. The Share-or-Perish (MRL #146) campaigns run on another box
under another agent and are not recorded here.

**Status (2026-10-24, 06:19).** X0, the calibration, is closed: the `legacy` leg passes its targets (3 seeds per
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
and the steady state goes to P16 (24 h warmups at 1 and 8 per /24). The ban list naming all 21 spy /24s on half the nodes takes
the `tail` fleet to 0.093 light (E25; the list naming 10 of 21: 0.131): adopters at zero, the other half 12% above the no-list cell,
7 of 40 users exposed against 18. For the unreachable users X1 scores,
the answer is stable across warmups: `sp_r` precision 1, recall 0.035-0.06, 12-18 of 40 twenty-transaction senders exposed
within 4 h in `tail`, 0-3 of 40 in `core`. Whether mainnet relays behave like the lab's (no churn, a white list that holds
the whole network) is open question 8. The `legacy` `tail` cell replicates to 1% across seeds (E23b, P15 hit on all four clauses:
0.2826 against 0.2857, `24`/`legacy` 0.575). The same 42 spies spread over 42 /24s read **0.3369**, 2.20x their 0.1531 ceiling, and
expose 27 of 40 users (E27, P17 five of six): under the stock rule the excess is a 2.0-2.4x multiplier on the subnet model in every
layout tried, so the operator's lever is /24s, not IPs. Under the old rule the same 42 IPs read 0.2984 in 42 /24s against 0.2857
in 21 (E28, P18 four of four): the layout is irrelevant where the selection counts IPs, and stock dedup gives the spread fleet
**1.13x** what the old rule gave it, against 0.58x for the packed fleet. E27 replicates to 1% at seed 23456 (0.334, E27b; P19 five
of six, the users' clause missed on a 25% user-level seed spread). The full 42-entry ban list on half the nodes takes the spread
fleet to **0.184** (0.55x, the same ratio as on the packed fleet), adopters to zero, non-adopters +10%, exposed users from 27 to 15
of 40 (E29, P20 eight of eight): the list's effect does not depend on the layout, and half the network adopting recovers only what
the stock rule's /24 counting gave the spread fleet. Eight spies per /24 at 26-30 h read 0.1497, below the 2-per-/24 cell's 0.1572 but still draining
(-14% over hours 20-30; E30, P16b three of four): packing IPs into /24s dilutes a little and delays a lot, and the /24 count is what
buys share. Running (04:25 10-26): `zenith2alpha`, the 256 GB Threadripper, validated by E31/P22 at 06:12 (0.0624 on the H=71 `legacy` cell), finished P23 at 09:36
(E34: **0.3524**, the seed-23456 read of the 24 h spread fleet, 5% above P21's; four of seven), P24 at 12:01 (E35: **0.3207** with the white-list
pick made uniform, 2.09x the ceiling, gradient intact: the recency draw is not the cause of the 2.2x; one of five) and P26 at 17:15 (E36: **0.1577**,
1.03x the ceiling with the 20-candidate cap lifted, gradient gone: **the cap is the whole 2.2x**; five of six, the miss being exposed users up from 28 to
37 of 40 because the users' own share rose from 0.10 to 0.16 while the relays' fell from 0.36), P27 at 19:34 (E37: **0.1705**, 1.11x with the cap lifted
and the stock cubic draw kept: the draw's shape is worth 8%; two of five) and P28 at 21:53 (E38: **0.1557**, P26 replicated at seed 23456, 1.01x; three
of five, the users at 0.139 just under their clause), sat idle until 00:35 (no watcher), finished P29 at 03:55 (E39: **0.1655**, the 24 h spread fleet
with the cap lifted, 1.08x the ceiling, nothing accumulates over the day; recall 0.187 against the stock 24 h cells' 0.134 and 0.109; four of five) and P31 at 06:15 (E40: **0.0771**, E29's half ban list
with the cap lifted, 0.49x the no-list cell and 1.01x the half-list model, adopters at zero and the non-adopters at exactly their ceiling; four of five), P32 at 12:43 (E42: **0.0764**, the half list with the cap lifted at seed 23456, 1.00x the half-list model and 0.49x the no-list cell again; five of five; the user, before 10:20: "proceed with the twelfth patch, and queue P31 at seed 23456 meanwhile"), P34 at 15:01 (E43: **0.1657**, the twelfth patch, 20 random /24 candidates with the stock cubic draw, 1.08x the ceiling, the same as the lifted cap with that draw; six of six), rebuilt with the thirteenth patch (runtime peer-list limits) at 15:09, finished P36 at 17:36 (E45: **0.1616**, the stock rule with the white list trimmed to 70 entries, 1.06x the ceiling against the untrimmed 2.20x: **the trim alone removes the multiplier**, the trimmed lists holding the spies below their pool share; three of five, the share clause missed far below) and P37 at 19:56 (E46: **0.1619**, the cap lifted with the same trim, 1.06x: the candidate-set fix is a no-op once the list is trimmed; four of five), finished P38 at 23:00 (E48: **0.3512**; the turnover reached only the users, the reachable nodes being exempt as pinned, and the run exited 1 at its end-of-run cleanup, fixed in `5115b02b`), stopped P39 at 23:13 for the same defect, and runs P42 (the stock rule with the reachable honest nodes cycling as well, started 23:16) with P43 (the cap lifted under the same turnover) behind it, hung at 01:25 10-26 (P42 lost mid-run, its run dir empty after the 02:42 reboot — no partial to salvage), its queue restarted 03:17 on the OQ13 smoke cell (the py-Levin refresh agent's validation, ~1 h wall) ahead of the P42 re-run and P43, and the smoke (04:05, exit 0) killed v1's design — ping-backs cannot refresh an existing white entry's `last_seen` (open question 13 (b)); v2 (a rotating front end, fresh-insert entries the port-dedup takes as the spy host's representative) replaces it pending smoke #2 on `simbox3` behind P41, which passed (07:31, exit 0: light **0.2299**, 12.7x the smoke cell's ceiling, the front entries 102 s fresh against the honest 19,600 s and present even in the unreachable users' lists via gray-list dials — open question 13 (c)); P44/P45 (the spread fleet under the v2 adversary, two seeds) filed and queued on simbox3; the P42 re-run finished at 07:46 (E51: **0.3936**, 1.64x the online-/24 ceiling under hourly relay churn — the absolute exposure rises over the no-churn 0.337 — with the honest cost small: restart fill 1.6 m median, 1.4% of sessions unfilled) and P43 finished at 11:19 (E52: **0.3237**, 1.35x the online ceiling, above its band, with the honest cost LOWER than the stock rule's — 1.37 against 2.85 failed dials per relay-hour — so the recency filter buys nothing at this churn and the honest-cost objection to the candidate rules is empty); P45 (the v2 adversary, seed 23456) runs there since 11:19, moved from simbox3's queue to keep both boxes busy (path-adapted md5 `9d1f1ca2` there against the filed `56143402`); the plan was reviewed against its three questions on 10-25 (plan section 7: the cap finding's transfer to mainnet is gated by the list age structure, the honest cost under churn and an active-recency adversary; revised order there); `phantom` finished P21 at 07:19 (E32: **0.3354**, E27's number at a 24 h warmup, five of seven clauses) and P25 at 08:11
(E33: 0.0628, the ten-patch binary passes its flag-off check) and has left the lab (its 38 archives on the Threadripper's array, the pool's home since 10-24; the source deleted 18:26); `simbox3` drained at 09:49 (the `tail` seed-34567 filler read 0.1812, E10's third seed: 0.176-0.195 across three seeds; the `core` one 0.0348), its five archives moved to the array 10-25 00:35 (local copies deleted, 89 GB free), was rebuilt with the eleven patches at 00:46 10-25 and finished P30 at 07:56 (E41: **0.1482**, P26 at seed 34567, 0.97x the ceiling, flat to 0.3%; five of five; the rebuilt binary passes its gate; three seeds mean 1.005x), its archive moved to the array (91 GB free), was rebuilt with the twelve patches at 10:37 (3 min, ccache), finished P33 at 15:16 (E44: **0.0792**, the half list with the cap lifted at seed 34567, 1.04x the half-list model; five of five; the half-list line closed at three seeds; the user, 10:30: "is there anything that could be running on .176? its idle") and P35 at 19:51 (E47: **0.1716**, the twelfth patch at seed 23456, 1.12x; six of six; two seeds 1.10x, the lifted cap's number), was rebuilt with the thirteen patches at 20:42 and runs P40 (the trim sweep: the stock rule with the white list at 140 entries, started 20:46) and finished it at 01:23 10-26 (E49: **0.1640**, the trim sweep's 140 point, **1.07x** the ceiling, flat with the 70 point — the multiplier needs a list holding nearly every /24; two of four; run 87); it finished P41 at 06:01 (E50: **0.152**, 0.99x, three of three; run 89), ran the OQ13 smoke #2 (06:01-07:31, v2 passes) and runs P44/P45 (the spread fleet under the active adversary, two seeds) behind them; P44 read **0.9083** at 12:11 (E53: 5.93x — the eclipse regime; combined recall 0.967 at precision 1.000, 40/40 users exposed; one entry per host so the lists never flood, the newest entry in every list a spy front) with P45 moved to tr, and P46 (the uniform draw against the adversary) and P47 (the trim against it) filed and queued on simbox3; P45 replicated on tr at 13:47 (E54: **0.9075** against P44's 0.9083 — 0.09%, the eclipse regime is seed-stable) ; P46 read **0.5994** at 17:02 (E55: the uniform draw cuts the eclipse by a third and restores direct attribution to the passive level, but cannot hold the subnet share — the fronts' immortal connections accumulate slots under any draw — so the candidate set is exhausted and the recommendation reverts to the list defenses); P47 (the trim against the adversary) read **0.0248** at 21:48 (E56: the trim is the defense, not the amplifier — the honest refresh cycle a trimmed list forces outruns the rotation, 1/40 users exposed against the untrimmed 40/40; the candidate-rule story inverts: mainnet's capped lists are the protection, and its strength prices the adversary's dialing budget) and P48 (wl70 with a 60 s rotation, the arms race at its tightest) read **0.0262** at 00:36 (E57: the 30x rotation changes nothing — the trim's protection is absolute at this budget; sp/combined 0.002, 1/40 exposed); both queues are empty and the OQ13 arc is complete;
`simbox2` is handed over to the selfish-mining project (its 21 archives on the array, the source deleted 18:26, handover note written). Since 10-24 the session runs on the control box and cells are generated
there (`make_cell.sh`, section 2 addendum). Entries E1-E62 below; predictions P1-P54 in section 5.

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

*2026-10-24 06:01:* the rule is now stated by its inputs, not by a box. The stagger depends on exactly two host facts, the p95
verify time in `~/.monerosim/calibration.json` and `os.cpu_count()`; with phantom's calibration file (md5 `e5276ee0`) and
`MONEROSIM_CORES=32` (a new override in `scripts/calibrate.py:_get_core_count`, explicit argument > env > nproc) the control box
regenerates `lean_legacy_none_h71_k1_s12345` and `lean_24_none_h300_k42_w24h_m1_n600_fx_s12345` byte-identical to phantom's
(md5 `8a79b809`, `dd1f63eb`), end to end including the Rust validation step; without the pin the first reads `b9759d63` (the
12-core stagger, 39 lines). Cells are generated on the control box with `docs/spy_journal/drivers/make_cell.sh`, which enforces
both inputs and prints the md5; phantom is no longer required for it.

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
  updated; the latest are through 2026-10-23 18:12 (`simbox2`), 17:49 (`phantom`) and 14:05 (`simbox3`); the earlier snapshots are kept.
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
| `20261023_153612_lean_24_half_h300_k21_w13h_m2_n600_s12345` | simbox2 | 42 / 21 | 300 / 242 | 0.0928 (0.0822) | 0.091, 0.094, 0.095, 0.091 | 0.193 | 1095 | 2h 34m | 12.6 | 0 | E25/P14: the tail cell with the full 21-/24 ban list on half the honest nodes (165 adopters); light 0.0928 (P14's 0.08-0.12 hit), adopters 0.0 (hit), the scorer's non-adopter group 0.1537 (0.17-0.24 missed below, slot-weighted with the five 100-peer miners), relays 0.1058 = 1.14x light (hit); the 50% list read 0.1309 and no list 0.1662 (E19) |
| `20261023_171700_lean_24_none_h300_k21_w6h_m2_n600_s23456` | simbox3 | 42 / 21 | 300 / 240 | 0.1763 (0.0831) | 0.177, 0.176, 0.177, 0.175 | 0.216 | 1095 | 2h 59m | 79.8 | 0 | simbox3 filler: tail 6 h seed replicate (seed 23456) of the E10/E19 cell; light 0.1763 |
| `20261023_175508_lean_24_none_h300_k21_w24h_m1_n600_fx_s12345` | phantom | 21 / 21 | 300 / 242 | 0.1911 (0.0822) | 0.191, 0.189, 0.192, 0.192 | 0.203 | 1109 | 3h 41m | 10.6 | 0 | P16a: tail at 1 spy per /24, 24 h warmup (window 26-30 h), fixed RandomX seed; light 0.1911 (13 h cell: 0.1978), flat; relays 0.2187; all P16a clauses hit |
| `20261023_181247_lean_legacy_none_h300_k21_w13h_m2_n600_s23456` | simbox2 | 42 / 21 | 300 / 240 | 0.2826 (0.1223) | 0.285, 0.283, 0.283, 0.279 | 0.193 | 1097 | 2h 32m | 12.7 | 0 | P15: legacy tail at seed 23456 (E23's seed replicate); light 0.2826 vs 0.2857 at seed 12345, flat; 24/legacy ratio 0.575; 24 of 40 users exposed |
| `20261023_201931_lean_24_none_h300_k21_w24h_m8_n600_fx_s12345` | simbox3 | 168 / 21 | 300 / 242 | 0.1497 (0.0822) | 0.153, 0.151, 0.150, 0.145 | 0.190 | 1079 | 6h 52m | 73.8 | 0 | P16b: tail at 8 spies per /24 (168 spies, 508 daemons), 24 h warmup, window 26-30 h; light 0.1497 (1.82x ceiling) but still falling (relays 0.18 at hour 20, 0.155 at 30); 16 of 39 exposed |
| `20261023_205427_lean_24_none_h300_k42_w13h_m1_n600_s12345` | simbox2 | 42 / 42 | 300 / 242 | 0.3369 (0.1531) | 0.339, 0.338, 0.337, 0.334 | 0.214 | 1098 | 2h 33m | 12.5 | 0 | P17: tail's 42 spies spread over 42 /24s at 1 each, stock 24; light 0.3369 = 2.20x the 0.1531 ceiling, flat; 27 of 40 users exposed |
| `20261023_214454_lean_legacy_none_h300_k42_w13h_m1_n600_s12345` | phantom | 42 / 42 | 300 / 242 | 0.2984 (0.1237) | 0.299, 0.296, 0.297, 0.302 | 0.199 | 1100 | 2h 33m | 10.5 | 0 | P18: the 42-/24 one-spy-each layout under legacy (P17's control); light 0.2984 = 2.41x its 0.1237 model, flat; 24/legacy at 42 /24s 1.13 (stock dedup gives this fleet more); 24 of 40 exposed |
| `20261023_233601_lean_24_none_h300_k42_w13h_m1_n600_s23456` | simbox2 | 42 / 42 | 300 / 240 | 0.3340 (0.1539) | 0.328, 0.334, 0.338, 0.336 | 0.197 | 1097 | 2h 32m | 12.5 | 0 | P19: E27's 42-/24 cell at seed 23456; light 0.334 vs 0.3369 (1% spread), 2.17x ceiling, flat; users 0.103 (seed 12345: 0.133); 26 of 40 exposed |
| `20261024_002607_lean_24_half_h300_k42_w13h_m1_n600_s12345` | phantom | 42 / 42 | 300 / 242 | 0.1840 (0.1531) | 0.187, 0.184, 0.183, 0.182 | 0.207 | 1095 | 2h 34m | 10.6 | 0 | P20: the 42-/24 spread fleet with the full 42-entry ban list on half the nodes; light 0.184 (no list: 0.3369, 0.55x), adopters 0.0, 15 of 40 exposed |
| `20261024_031641_lean_24_none_h300_k1_w6h_m113_s34567` | simbox3 | 113 / 1 | 300 / 243 | 0.0348 (0.0045) | 0.046, 0.037, 0.030, 0.026 | 0.195 | 1068 | 3h 17m | 77.3 | 0 | E10 replicate (filler): core at the 6 h warmup, seed 34567: 0.0348 against seed 12345's 0.0352 and seed 23456's 0.0428; every quarter falls (drain transient); sp_r precision 1.00, recall 0.009, 3 of 39 heavy users exposed |
| `20261024_033150_lean_24_none_h300_k42_w24h_m1_n600_fx_s12345` | phantom | 42 / 42 | 300 / 242 | 0.3354 (0.1531) | 0.331, 0.333, 0.337, 0.341 | 0.193 | 1100 | 3h 45m | 10.3 | 0 | P21: the spread fleet (42 spies in 42 /24s) at a 24 h warmup, window 26-30 h: 0.3354 against E27's 0.3369 at 13 h; flat (quarters 0.331-0.341); sp_r precision 1.00, recall 0.134, 33 of 40 heavy users exposed |
| `20261024_052857_lean_legacy_none_h71_k1_s12345` | zenith2alpha | 13 / 1 | 71 / 60 | 0.0624 (0.0750) | 0.059, 0.062, 0.062, 0.065 | 0.171 | 953 | 41m 48s | 166.7 | 0 | P22, the Threadripper's platform check (H=71 legacy, seed 12345): 0.0624 against phantom 0.0610, simbox2 0.0614, simbox3 0.0641; hit on all four clauses; first run on zenith2alpha (64 threads, 251 GB), live run on /fast |
| `20261024_061705_lean_24_none_h300_k42_w24h_m1_n600_fx_s23456` | zenith2alpha | 42 / 42 | 300 / 240 | 0.3524 (0.1539) | 0.351, 0.351, 0.354, 0.353 | 0.191 | 1101 | 3h 16m | 156.5 | 0 | P23: P21's seed-23456 replicate on zenith2alpha, 24 h warmup, window 26-30 h: 0.3524 against P21's 0.3354 (1.051x) and E27b's 0.334 at 13 h; flat (quarters 0.351-0.354); relays 0.4002, +3% over hours 20-30; sp_r precision 1.00, recall 0.109, 29 of 40 heavy users exposed; wall 3 h 16 m |
| `20261024_063655_lean_24_none_h300_k21_w6h_m2_n600_s34567` | simbox3 | 42 / 21 | 300 / 243 | 0.1812 (0.0819) | 0.183, 0.182, 0.179, 0.180 | 0.204 | 1086 | 3h 9m | 79.6 | 0 | simbox3 filler: tail 6 h, third seed (34567): 0.1812 against 0.1946 (12345) and 0.1763 (23456), mean 0.1840; flat (quarters 0.179-0.183); E10 addendum |
| `20261024_072708_lean_legacy_none_h71_k1_s12345` | phantom | 13 / 1 | 71 / 60 | 0.0628 (0.0749) | 0.062, 0.065, 0.060, 0.064 | 0.208 | 1086 | 43m 26s | 19.7 | 0 | P25: the ten-patch monerod-sim (b8d6fbb6, --sim-uniform-whitelist-pick present, off) on the H=71 legacy cell: 0.0628 against 0.0610 on the nine-patch binary; all checks; no daemon logs the flag; hit on all clauses |
| `20261024_094257_lean_24_none_h300_k42_w13h_m1_n600_up_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.3207 (0.1531) | 0.325, 0.320, 0.319, 0.318 | 0.209 | 1101 | 2h 15m | 157.0 | 0 | P24: E27's cell with --sim-uniform-whitelist-pick on every daemon (open question 10's probe): 0.3207 against E27's 0.3369 (-5%), 2.09x the model; the recency bias inside the 20-candidate pick is not the cause of the 2.2x; see E35 |
| `20261024_144444_lean_24_none_h300_k42_w13h_m1_n600_up_wc0_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.1577 (0.1531) | 0.156, 0.158, 0.158, 0.159 | 0.179 | 1096 | 2h 28m | 157.6 | 0 | P26 (E36): open question 10, the white-list candidate cap lifted (sim-whitelist-candidates 0) with the uniform draw (P24's flag) on E27's spread-fleet cell; light 0.1577 = 1.03x the subnet ceiling 0.1531 (E27 0.3369, P24 0.3207); eleven-patch binary |
| `20261024_171548_lean_24_none_h300_k42_w13h_m1_n600_wc0_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.1705 (0.1531) | 0.174, 0.170, 0.169, 0.169 | 0.190 | 1098 | 2h 15m | 154.3 | 0 | P27 (E37): open question 10, the candidate cap lifted (sim-whitelist-candidates 0) with the stock cubic draw kept, on E27's spread-fleet cell; light 0.1705 = 1.11x the ceiling (P26 with the uniform draw 0.1577); eleven-patch binary |
| `20261024_193434_lean_24_none_h300_k42_w13h_m1_n600_up_wc0_s23456` | zenith2alpha | 42 / 42 | 300 / 240 | 0.1557 (0.1539) | 0.154, 0.157, 0.156, 0.156 | 0.200 | 1097 | 2h 15m | 156.4 | 0 | P28 (E38): P26 at seed 23456 (cap lifted, uniform draw); light 0.1557 = 1.01x the ceiling 0.1539 (P26 0.1577); eleven-patch binary |
| `20261025_003506_lean_24_none_h300_k42_w24h_m1_n600_fx_up_wc0_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.1655 (0.1531) | 0.168, 0.167, 0.164, 0.163 | 0.212 | 1102 | 3h 17m | 157.5 | 0 | P29 (E39): the 24 h spread fleet (42 spies in 42 /24s) with the 20-candidate cap lifted and the uniform white-list draw, fixed RandomX seed, window 26-30 h, seed 12345; light 0.1655 = 1.08x the 0.1531 ceiling (13 h cells 1.01-1.03x), quarters 0.168-0.163 (-3%), relays 0.1635, users 0.1787; start-order quarters 0.159/0.146/0.174/0.174 (latest 1.10x earliest); sp_r recall 0.187, 31 of 40 exposed; both flag lines in all 382 logs; wall 3 h 18 m |
| `20261025_032553_lean_24_none_h300_k42_w13h_m1_n600_up_wc0_s34567` | simbox3 | 42 / 42 | 300 / 243 | 0.1482 (0.1523) | 0.148, 0.148, 0.148, 0.148 | 0.192 | 1088 | 4h 26m | 79.1 | 0 | P30 (E41): P26 at a third seed (34567) on simbox3's eleven-patch binary (sha 14852a861c75); light 0.1482 = 0.97x this seed's 0.1523 ceiling (243 honest /24s), quarters 0.1481-0.1485 (flat to 0.3%), relays 0.147, users 0.1521; start-order quarters 0.143/0.149/0.143/0.154 (latest 1.08x earliest); sp_r recall 0.146, 39 of 40 exposed; both flag lines in all 382 logs; three seeds 0.1577/0.1557/0.1482, mean 0.1539, spread 0.0095, mean 1.005x the ceiling; wall 4 h 27 m |
| `20261025_035537_lean_24_half_h300_k42_w13h_m1_n600_up_wc0_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.0771 (0.1531) | 0.080, 0.077, 0.075, 0.077 | 0.200 | 1097 | 2h 17m | 157.6 | 0 | P31 (E40): E29's cell (the full 42-/24 ban list on half the honest nodes: 117 of 233 relays, 20 of 40 users) with the 20-candidate cap lifted and the uniform draw, 13 h warmup, window 15-19 h, seed 12345; light 0.0771 = 0.49x the cap-lifted no-list cell (P26 0.1577; E29 under the stock rule 0.55x) and 1.01x the half-list model 0.0765; adopters 0.0000, non-adopters 0.1539 = 1.005x the ceiling (E29 +10%); users 0.0772, 15 of 40 exposed (all among the 20 non-adopters), sp_r recall 0.069 (P26 0.173); quarters 0.080-0.075; both flag lines in all 382 logs; wall 2 h 18 m |
| `20261025_102213_lean_24_half_h300_k42_w13h_m1_n600_up_wc0_s23456` | zenith2alpha | 42 / 42 | 300 / 240 | 0.0764 (0.1539) | 0.077, 0.076, 0.076, 0.076 | 0.189 | 1097 | 2h 18m | 157.7 | 0 | P32 (E42): P31 at seed 23456 (the full 42-/24 ban list on half the nodes with the cap lifted and the uniform draw), 13 h warmup, window 15-19 h; light 0.0764 = 1.00x the half-list model 0.0767 (P31 0.0771 = 1.01x) and 0.49x the cap-lifted no-list cell at this seed (P28 0.1557); adopters 0.0000, non-adopters 0.1554 = 1.01x the ceiling; users 0.0728, 17 of 40 exposed (all non-adopters), sp_r recall 0.066; quarters 0.0775-0.0759 (2% span); both flag lines in all 382 logs; eleven-patch binary; wall 2 h 19 m |
| `20261025_103748_lean_24_half_h300_k42_w13h_m1_n600_up_wc0_s34567` | simbox3 | 42 / 42 | 300 / 243 | 0.0792 (0.1523) | 0.079, 0.077, 0.081, 0.080 | 0.204 | 1087 | 4h 33m | 79.0 | 0 | P33 (E44): P31 at a third seed (34567) on simbox3's twelve-patch binary with the twelfth flag off (the full 42-/24 ban list on half the nodes with the cap lifted and the uniform draw), 13 h warmup, window 15-19 h; light 0.0792 = 1.04x the half-list model 0.0759 and 0.53x the cap-lifted no-list cell at this seed (P30 0.1482); adopters 0.0000, non-adopters 0.1575 = 1.03x the ceiling; users 0.0723; quarters 0.0791-0.0809 (4.5% span); both flag lines in all 382 logs, the twelfth in none; three seeds 0.0771/0.0764/0.0792; wall 4 h 35 m |
| `20261025_124316_lean_24_none_h300_k42_w13h_m1_n600_rc_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.1657 (0.1531) | 0.170, 0.167, 0.164, 0.163 | 0.196 | 1095 | 2h 15m | 152.3 | 0 | P34 (E43): the twelfth patch, 20 white-list candidates drawn at random from the deduplicated list instead of the 20 newest, stock cubic draw kept, spread fleet seed 12345, 13 h warmup, window 15-19 h; light 0.1657 = 1.08x the ceiling, the same as the cap lifted with the cubic draw (P27 0.1705) and 0.49x the stock cell (E27 0.3369); relays 0.166, users 0.1623, start-order quarters 0.148/0.149/0.173/0.190 (latest 1.28x earliest, P27 1.28x); sp_r recall 0.135, 31 of 40 exposed; the twelfth patch's line in all 382 logs, the other two in none; Monte Carlo said 1.53x; wall 2 h 16 m |
| `20261025_151635_lean_24_none_h300_k42_w13h_m1_n600_rc_s23456` | simbox3 | 42 / 42 | 300 / 240 | 0.1716 (0.1539) | 0.168, 0.171, 0.172, 0.175 | 0.192 | 1097 | 4h 30m | 79.2 | 0 | P35 (E47): P34 at seed 23456 on simbox3 (the twelfth patch, 20 random /24 candidates with the stock cubic draw); light 0.1716 = 1.12x this seed's 0.1539 ceiling, within 0.006 of P34's 0.1657; relays 0.1784, users 0.1376; start-order gradient 1.15x (P34 1.28x); recall 0.152, 32 of 40 exposed; the twelfth line in all 382 logs; six of six; two seeds mean 1.10x, P27's 1.11x; wall 4 h 32 m |
| `20261025_151639_lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.1616 (0.1531) | 0.165, 0.163, 0.159, 0.159 | 0.198 | 1099 | 2h 16m | 154.3 | 0 | P36 (E45): the stock rule with the white list trimmed to its 70 newest entries (--sim-white-peerlist-limit 70, the thirteenth patch; mainnet's 1000 of ~4600 scaled to the lab's 342) and 12 probe relays dumping lists; light 0.1616 = 1.06x the ceiling against E27's untrimmed 0.3369 (2.20x): the trim alone removes the stock multiplier; probes' white lists exactly 70 entries, spies 8.5-10.7% of them (pool 12.3%), rank 0.35-0.49; relays 0.1666, users 0.1362, start-order gradient gone (1.05x); recall 0.135, 30 of 40 exposed; three of five clauses (the 0.28-0.50 share clause missed far below); wall 2 h 18 m |
| `20261025_173648_lean_24_none_h300_k42_w13h_p3_m1_n600_up_wl70_wc0_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.1619 (0.1531) | 0.164, 0.163, 0.162, 0.159 | 0.179 | 1097 | 2h 16m | 152.6 | 0 | P37 (E46): the cap lifted with the uniform draw and the white list trimmed to 70 entries (P26 plus the thirteenth patch's limit, probes); light 0.1619 = 1.06x the ceiling, P37/P36 = 1.00 (untrimmed P26/E27 0.47): the fix is a no-op once the list is trimmed; probes' lists 70 entries, spies 9.3-10.2%; relays 0.1644, users 0.1491; recall 0.134, 32 of 40 exposed; four of five (the spies' share of list entries clause missed: below 0.15, not above); wall 2 h 17 m |
| `20261025_204207_lean_24_none_h300_k42_w13h_p3_m1_n600_to1h1h_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.3512 (0.1531) | 0.346, 0.352, 0.352, 0.354 | 0.207 | 575 | 2h 15m | 153.2 | 1 | P38 as run: 1 h/1 h turnover reached only the 40 users (reachable nodes set hide-my-port false and are kept up as pinned); exit 1 from 15 user agents stopped by Shadow at the end (fixed in 5115b02b); window data complete; light 0.3512 |
| `20261025_204615_lean_24_none_h300_k42_w13h_p3_m1_n600_wl140_s12345` | simbox3 | 42 / 42 | 300 / 242 | 0.1640 (0.1531) | 0.165, 0.164, 0.164, 0.163 | 0.201 | 1096 | 4h 32m | 79.4 | 0 | P40, the trim sweep's 140 point (stock rule, white list limited to 140): light 0.164, 1.07x the ceiling, flat with the 70 point's 1.06x - the multiplier needs a list holding nearly every /24. Two of four: (a) missed below 0.18; (b) hit (white lists at the 140 limit, spies 6.5-10.4% of entries, mean 8.8%, rank 0.48); (c) n/a; (d) wall 274 m. E49. |
| `20261026_012322_lean_24_none_h300_k42_w13h_p3_m1_n600_wl35_s12345` | simbox3 | 42 / 42 | 300 / 242 | 0.1520 (0.1531) | 0.150, 0.153, 0.153, 0.152 | 0.198 | 1097 | 4h 33m | 79.4 | 0 | P41, the trim sweep's 35 point (stock, white list limited to 35): light 0.152 = 0.99x the ceiling - the sweep closes flat at the subnet share on every capped reading. Three of three: (a) 0.152 hit; (b) every probe exactly 35 entries, spies 3.0/35 below pool share and, notably, the freshest entries in the list (60 s vs honest 146 s) - freshness buys nothing when nothing is cut; (c) wall 275 m. E50; run 89. |
| `20261026_031725_lean_24_none_h71_k1_p2_m13_sr60_ud_s12345` | zenith2alpha | 13 / 1 | 71 / 60 | 0.0179 (0.0181) | 0.024, 0.020, 0.017, 0.011 | 0.204 | 847 | 46m 26s | 195.2 | 0 | OQ13 mechanism smoke, no prediction: the v1 re-handshake design. Exit 0, 47 m, agents swept cleanly (50/71 per sweep, identity and chain state learned from the daemon), but the spies' white entries' last_seen never moved (median age 20,288 s vs honest 18,586 s at the end): the ping-back's append_with_peer_white preserves existing timestamps (trust_last_seen=false). Superseded by v2 (rotating front ports). Not comparable to the h300 cells (6 h, 71 reachable, exposure window empty). |
| `20261026_040527_lean_24_none_h300_k42_w13h_p3_m1_n600_tor1h1h_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.3936 (0.1531) | 0.391, 0.411, 0.390, 0.383 | 0.188 | 584 | 3h 38m | 158.1 | 0 | P42, the relay-churn cell (tor1h1h, stock): exit 0 (5115b02b holds), h 2078, wall 219 m. Light 0.3936 = 1.64x the online-/24 ceiling (~0.24); absolute exposure rises over the no-churn 0.3369. Four of four: (a) hit; (b) hit; (c) hit - churn_cost session counts equal the config (relays 9.7 mean, 2267 sessions/233 nodes); (e) hit. Baselines: restart fill 1.6 m med / 5.0 p90, 2.85 connect + 1.77 handshake failures per relay-hour, 32/2267 unfilled. First precision below 1.0: sp 0.859. E51; run 91. |
| `20261026_060153_lean_24_none_h71_k1_p2_m13_sr60_ud_s12345` | simbox3 | 13 / 1 | 71 / 60 | 0.2299 (0.0181) | 0.208, 0.237, 0.230, 0.248 | 0.239 | 962 | 1h 27m | 86.7 | 0 | OQ13 mechanism smoke #2, no prediction: v2 (rotating front ends). Exit 0, 88 m. The mechanism works: light 0.2299 = 12.7x the cell's 0.0181 ceiling (v1 read 0.0179); relays/observers hold 12-13 accumulated front entries, freshest ~102 s against honest ~19,600 s, rank 0.10-0.15; fresh front entries reach the unreachable users via gossip + gray-list dials. Gates P44/P45. |
| `20261026_073911_lean_24_none_h300_k42_w13h_p3_m1_n600_sr300_ud_s12345` | simbox3 | 42 / 42 | 300 / 242 | 0.9083 (0.1531) | 0.852, 0.893, 0.922, 0.947 | 0.265 | 1105 | 4h 29m | 80.2 | 0 | P44, the active adversary on the spread fleet (v2 rotating fronts, stock rule): light 0.9083 = 5.93x the ceiling - the eclipse regime, far above the 0.40-0.75 band. Combined recall 0.967 at precision 1.000, 40/40 users exposed, users' p_out median 1.0. Three of four: (a) missed above (the finding); (b) hit; (c) hit (freshest spy rank 0.000 in every list, fronts ~110 s old, 41-42 spy entries per node - evict_host_from_peerlist keeps one entry per host, so the rotation self-cleans: white 341 = 299 honest + 42 fronts, nothing evicted); (d) 271 m. E53; run 93. |
| `20261026_074618_lean_24_none_h300_k42_w13h_p3_m1_n600_up_tor1h1h_wc0_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.3237 (0.1531) | 0.335, 0.327, 0.312, 0.322 | 0.203 | 586 | 3h 30m | 156.1 | 0 | P43, the churn gate's second half (cap lifted + uniform draw, tor1h1h): light 0.3237 = 1.35x the online ceiling, above its 0.17-0.30 band; stock read 0.3936. Clause (c) missed the other way: the lifted cap is CHEAPER than stock (1.37 vs 2.85 connect failures per relay-hour; fill 1.7 vs 1.6 m; 30 vs 32 unfilled) - the recency filter buys nothing at this churn. Two of four: (a) hit (h 2061), (d) hit (211 m); sp precision 0.932. E52; run 92. |
| `20261026_111953_lean_24_none_h300_k42_w13h_p3_m1_n600_sr300_ud_s23456` | zenith2alpha | 42 / 42 | 300 / 240 | 0.9075 (0.1539) | 0.849, 0.891, 0.923, 0.946 | 0.209 | 1127 | 2h 25m | 102.6 | 0 | P45, the active adversary replicate (seed 23456): light 0.9075 against P44's 0.9083 - 0.09% seed spread. Combined recall 0.969 at 0.997, 40/40 users, users p_out median 1.0. Clauses as P44: (a) missed above identically, (b) hit, (c) hit (dumps identical: rank 0.000, 42 entries per node, fronts ~118 s), (d) hit (146 m - tr runs the agent-loaded cell near twice simbox3's pace). E54; run 94. |
| `20261026_123147_lean_24_none_h300_k42_w13h_p3_m1_n600_up_sr300_ud_wc0_s12345` | simbox3 | 42 / 42 | 300 / 242 | 0.5994 (0.1531) | 0.614, 0.632, 0.640, 0.532 | 0.245 | 1105 | 4h 28m | 80.1 | 0 | P46, the uniform draw against the active adversary: light 0.5994 = 3.9x - above the 0.30 reading-rule threshold, nothing in the candidate set survives. The draw cuts the eclipse by a third (0.9083 -> 0.5994) and restores direct attribution to the passive level (sp 0.181 at precision 1.000, 28/40 exposed) but cannot hold the subnet share: the fronts' immortal connections accumulate slots under any draw (users p_out 0.449, reachable 0.615). Two of four: (a) missed above, (b) missed (combined 0.391), (c) hit, (d) hit (269 m). E55; run 95. |
| `20261026_170301_lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_sr300_ud_s12345` | simbox3 | 42 / 42 | 300 / 242 | 0.0248 (0.1531) | 0.027, 0.024, 0.025, 0.024 | 0.219 | 1109 | 4h 40m | 79.2 | 0 | P47, the trim against the adversary: light 0.0248 - the prediction said 0.80-0.95, the truth is the opposite pole. sp 0.003 at precision 1.000, combined 0.004, 1/40 users exposed (the untrimmed adversary: 40/40 at 0.967), p_out 0.000-0.002. The trim forces a fast honest refresh cycle (entry median ages 208-742 s) that outruns the 1800 s rotation; 9-14 fronts evicted (28-33 spy entries, not 42); the adversary's inserts feed the flywheel. Two of four: (a) missed far below, (b) missed below, (c) hit, (d) hit (282 m). E56; run 96. |
| `20261026_221003_lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_sr300_ro60_ud_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.0262 (0.1531) | 0.028, 0.025, 0.025, 0.026 | 0.219 | 1128 | 2h 23m | 58.3 | 0 | P48, the arms race at its tightest (wl70, 60 s rotation): light 0.0262 against P47's 0.0248 - the 30x faster rotation changes nothing. sp/combined 0.002 at precision 1.000, 1/40 users exposed. The front entries effective freshness is bounded by the sweep cadence (300 s), not the rotation; newest-20 held 1-4 spies of 20; evictions continue (26-33 of 70). Two of four, both misses confirming the defense: (a) missed below 0.10 - the trim wins outright; (b) missed below; (c) hit; (d) hit (144 m, min_avail 59.7 GB). E57; run 97. |
| `20261027_114619_lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_sr60_ud_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.0239 (0.1531) | 0.026, 0.023, 0.023, 0.024 | 0.258 | 1129 | 2h 31m | 58.4 | 0 | P49 wl70 + 60s sweeps: 0.0239 - the trim holds; the agent dial floor ~1076s median front age; front-port stem swallow nuance (E59) |
| `20261027_114821_lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_sr300_ud_s23456` | simbox3 | 42 / 42 | 300 / 240 | 0.0261 (0.1539) | 0.029, 0.025, 0.025, 0.025 | 0.229 | 1107 | 4h 36m | 79.5 | 0 | P50 E56 replicate seed 23456: 0.0261 vs 0.0248 - the defense headline on two seeds; 4/4 clauses (E60) |
| `20261027_142035_lean_24_none_h300_k42_w13h_p3_m1_n600_fx_mw25h_ui43200_rs60_bs6_s12345` | zenith2alpha | 42 / 42 | 366 / 295 | 0.2935 (0.1299) | 0.289, 0.294, 0.297, 0.294 | 0.205 | 430 | 4h 44m | 35.2 | 0 | P51 X1a mainnet-rate: 5/5 - reachable-occasional sp precision 0.265 (OQ12), busy 0.843, users 21.6 pct exposed/24h, light 0.2935=1.92x ceiling (E61) |
| `20261028_033917_lean_24_none_h71_k1_p2_m13_x3_s12345` | zenith2alpha | 13 / 1 | 71 / 60 | 0.0151 (0.0181) | 0.025, 0.015, 0.012, 0.010 | 0.221 | 855 | 43m 47s | 132.8 | 0 | X3 smoke (run of the 14-patch binary): mechanism verified - 2140 x3 events, edge2 38 pct virtual (peers dialed-by), edge1 outgoing, users receive relayed stems 107 vs 0 stock; local-pin path unexercised (adopters do not originate txs in this shape); exit 0 wall 44m |
| `20261028_042916_lean_24_none_h300_k42_w13h_p3_m1_n600_x3_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.3409 (0.1531) | 0.340, 0.342, 0.343, 0.338 | 0.217 | 1128 | 2h 24m | 58.8 | 0 | P52 X3a tevador stemmable inbound at full take-up: precision 0.9828 vs 1.000 stock - the cover is real but 15x too thin (71 relayed stems at 40 users vs 1063 own sends; the design throttles compound); light 0.3409 = E27 (outbound untouched); 4 of 6 clauses (E62) |
| `20261028_102612_lean_24_none_h300_k42_w13h_p3_m1_n600_fx_x3_mw25h_ui43200_rs60_bs6_s12345` | simbox3 | 42 / 42 | 366 / 295 | 0.3066 (0.1299) | 0.306, 0.307, 0.304, 0.309 | 0.206 | 431 | 9h 11m | 75.1 | 0 | P53 X3 at mainnet sender rate (X1a + stemmable): 4/6 - sp precision on unreachable users 1.000 (band 0.45-0.92, missed above: the cover is 13 relayed stems at 11 of 40 users against 55 own sends, none forwarded to a spy), recall 0.164, reachable-occasional 0.288, busy 0.773, light 0.3066 (X1a 0.2935; 2.36x the cell model 0.1299), census 13 (band 15-100, missed below); the cover is closed at every rate (E64) |
| `20261028_103134_lean_24_none_h300_k42_w13h_p3_m1_n600_sr300_ud_x3_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.9051 (0.1531) | 0.849, 0.890, 0.921, 0.941 | 0.217 | 1124 | 2h 24m | 54.3 | 0 | P54 X3c v2 adversary through stemmable: 5/5 - light 0.9051 = E53's eclipse (0.9083) unchanged; sp 0.445, combined 0.951 at precision 1.000, 40/40 users; cover collapsed to 17 relayed stems at 1 user (union median 8, virtual slot share 39.8 pct) - the guarantee's blind side confirmed (E63) |
| `20261028_181536_lean_24_none_h300_k42_w13h_p3_m1_n600_sph_sd12_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.0000 (0.1531) | 0.000, 0.000, 0.000, 0.000 | 0.207 | 1096 | 2h 31m | 54.2 | 0 | P56 X3b-hidden OFF control (hidden dialing spies, stock stems): 4/4 - 0 spy stem receipts at 42 spies, light 0.000, sp recall 0.000, spies dialed 59-85 distinct outbound connections each and accepted none; the isolation control holds (E65) |
| `20261028_200039_lean_24_none_h300_k8_w13h_p3_m5_n600_x3_s12345` | simbox3 | 40 / 8 | 300 / 242 | 0.0598 (0.0345) | 0.060, 0.060, 0.060, 0.059 | 0.201 | 1095 | 4h 39m | 79.1 | 0 | P59 X3b-dense (40 spies in 8 /24s, 5 each, relay-dialed, universal adoption): light 0.0598, 187 spy stem receipts all relay-dialed (0 virtual), hop-1 user txs 14, sp precision on users 1.000 / sp_r recall 0.014, 67 relayed stems at 29/40 users, 30,968 x3 events, union median 23, edge-2 virtual 37.5%, wall 281 m on simbox3; E67 |
| `20261028_205441_lean_24_none_h300_k42_w13h_p3_m1_n600_x3_sph_sd12_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.0000 (0.1531) | 0.000, 0.000, 0.000, 0.000 | 0.187 | 1096 | 2h 32m | 53.6 | 0 | P57 X3b-hidden under universal adoption (hidden dialing spies, out-peers 12, --stemmable on the fabric): 78 spy stem receipts, all 78 via virtual slots (virtual_rx_share 1.000), hop-1 0, sp/sp_r recall 0.000, light 0.000, 68 relayed stems at 30/40 users, 30,958 x3 events, union median 24, edge-2 virtual 35.1%; E66 |
| `20261028_233022_lean_24_none_h300_k42_w13h_p3_m1_n600_x3_sph_sd12_sc_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.0000 (0.1531) | 0.000, 0.000, 0.000, 0.000 | 0.209 | 1093 | 2h 34m | 54.3 | 0 | P58 X3b-hidden, the fleet pays alone (hidden dialing spies, out-peers 12, cidrs = spy /24s only): 238 spy stem receipts, all virtual (virtual_rx_share 1.000), 3.05x P57 (78), hop-1 0, sp/sp_r recall 0.000, light 0.000, 0 relayed stems at users, 30,967 x3 events, virtual epochs 64.9%, union median 13, edge-2 virtual 9.1%; E68 |
| `20261029_020725_lean_24_none_h300_k42_w13h_p3_m1_n600_x3_sd12_sc_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.0923 (0.1531) | 0.092, 0.092, 0.093, 0.092 | 0.192 | 1097 | 2h 32m | 54.0 | 0 | P55 X3b-pay (visible dialing spies, out-peers 12, cidrs = spy /24s only, fabric not stemmable): light 0.0923 (band 0.30-0.38; relays p_out 0.081 vs E27 0.325, users 0.137 vs 0.119), 763 spy stem receipts (462 relay-dialed + 301 virtual, virtual_rx_share 0.526), hop-1 user txs 133, sp recall 0.129 / precision 1.000, 0 relayed stems at users, 31/40 users exposed, 30,961 x3 events, union median 13, edge-2 virtual 8.5%; E69 |
| `20261029_102622_lean_24_none_h300_k8_w13h_p3_m5_n600_x3_sph_sd64_s12345` | simbox3 | 40 / 8 | 300 / 242 | 0.0000 (0.0345) | 0.000, 0.000, 0.000, 0.000 | 0.196 | 1098 | 5h 31m | 78.8 | 0 | P61 X3b budget pole, dense (40 hidden spies in 8 /24s, dial 64, universal): 212 spy stem receipts (78% of P60 273 - inside the pre-registered 25% window: dense = spread at this fan-in; band 250-500 missed below like P60 by the same sub-linearity), all virtual (1.000), hop-1 0, all estimator recalls 0.000, light 0.000, 46 relayed stems at 20/40 users, 30,964 x3 events, virtual epochs 96.4%, union median 24 (= P60: honest-dominated, spy /16s displace), edge-2 virtual 37.2%, dial check 77-93 out ids zero inbound; E71 |
| `20261029_103017_lean_24_none_h300_k42_w13h_p3_m1_n600_x3_sph_sd64_s12345` | zenith2alpha | 42 / 42 | 300 / 242 | 0.0000 (0.1531) | 0.000, 0.000, 0.000, 0.000 | 0.208 | 1097 | 2h 59m | 52.8 | 0 | P60 X3b budget pole, spread (42 hidden spies, one per /24, dial 64): 273 spy stem receipts (3.50x E66 sd12 78 for 5.33x budget; band 300-550, missed below by 9%), all virtual (share 1.000), hop-1 0, all estimator recalls 0.000, light 0.000, 52 relayed stems at 24/40 users, 30,966 x3 events, virtual epochs 96.7%, union median 24 (E66 24: the added spy /16s displaced honest ones), edge-2 virtual 37.5%, per spy median 6, dial check 74-92 out ids median 83.5 zero inbound; E70 |
| `20261031_022557_lean_24_none_h300_k9_w13h_p3_m7_n600_s12345` | zenith2alpha | 63 / 9 | 300 / 242 | 0.0633 (0.0382) | 0.065, 0.064, 0.062, 0.062 | 0.191 | 1096 | 2h 27m | 44.9 | 0 | P63 M1 k9 m7 stock (63 addresses, 9 /24s): sp recall 0.0146 precision 1.000, 314 receipts, hop-1 15; corrected read = addresses-per-/24 dose-response; E72 |
| `20261031_022741_lean_24_none_h300_k9_w13h_p3_m1_n600_s12345` | simbox3 | 9 / 9 | 300 / 242 | 0.0853 (0.0382) | 0.085, 0.084, 0.086, 0.087 | 0.195 | 1103 | 4h 36m | 80.3 | 0 | P62 B1 k9 m1 baseline (9 addresses, 9 /24s): light 0.0853 = 2.38x model 0.0359 (above the m-series band), 414 receipts on 9 spies (46 per /24 vs M1 35: per-/24 totals hold as address count varies), hop-1 16; E75 |
| `20261031_045621_lean_24_none_h300_k9_w13h_p3_m7_n600_hpl1_s12345` | zenith2alpha | 63 / 9 | 300 / 242 | 0.0651 (0.0382) | 0.066, 0.065, 0.065, 0.063 | 0.196 | 1082 | 2h 27m | 48.1 | 1 | P64 M2 k9 m7 hpl1: NULL-VALIDATION of the R8 flag after the premise correction (no shared-host entries exist; the cap cannot fire): recall 0.0197 precision 1.000, 296 receipts vs M1 314; reads == M1 within noise = the flag is inert without same-host endpoints, as designed; E73 |
| `20261031_111203_lean_24_none_h300_k42_w13h_p3_m7_n600_s12345` | zenith2alpha | 294 / 42 | 300 / 242 | 0.3467 (0.1531) | 0.346, 0.346, 0.349, 0.346 | 0.201 | 1048 | 2h 42m | 7.1 | 0 | P66 I1 k42 m7 (294 addresses, 42 /24s): light 0.3467 = 2.26x model (band 2.0-2.6 HIT; m1 series 2.0-2.23), 1004 receipts, hop-1 106, recall 0.108 precision 1.000; the addresses-per-/24 axis is near-flat against E27 k42 m1: the /24 cap, not address count, sets the multiplier; E74 |
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

*2026-10-23 20:40, X1 presets at the 6 h warmup, seed replicates (`simbox3` fillers, run while its queue
waited for the 24 h cells).* `core` (113 spies, 1 /24): seed 12345 0.0352 (`phantom`, E14), seed 23456 **0.0428**
(+22%; quarters 0.055, 0.045, 0.039, 0.033 against 0.045, 0.037, 0.032, 0.027). `tail` (42 spies, 21 /24s): seed 12345
0.1946 (`phantom`, E15), seed 23456 **0.1763** (-9%; quarters 0.177, 0.176, 0.177, 0.175 against 0.198, 0.195,
0.195, 0.191). Both cells read the same way as their first seeds: `core` is still inside its drain transient at 6 h (every
quarter falls), which is where a 22% seed spread is expected (E22 puts the transient's size at 7x the model here), and
`tail` is flat from the first quarter. Exposure in the `tail` replicate: `sp_r` precision 1.00, recall 0.067, 21 of 40
twenty-transaction users attributed (seed 12345: 18 of 40). The seed-34567 fillers for both cells are queued behind P16b.
*2026-10-24 06:46, the third seed.* `core` seed 34567 reads **0.0348** (`simbox3`, 197 min, 453 daemons, 79 GB free at the lowest):
-1% against seed 12345's 0.0352, quarters 0.046, 0.0371, 0.0305, 0.0265 against 0.045, 0.037, 0.032, 0.027, so the seed-23456 read
(0.0428) is the outlier of the three and the 6 h `core` cell's seed spread is 0.0348-0.0428 (mean 0.0376, every quarter falling in all
three). Exposure: `sp_r` precision 1.00, recall 0.009, 3 of 39 twenty-transaction users attributed (0-3 of 40 in the other `core` cells).
Relays show the drain transient's late rise with its start-order gradient (0.055 to 0.135 across the quarters at hour 6), as E16 described.
The `tail` seed-34567 filler started at 06:36 and is the last cell in `simbox3`'s queue.
*2026-10-24 09:55, the third `tail` seed.* `tail` seed 34567 reads **0.1812** (`simbox3`, 189 min, 384 daemons, 81 GB free at the lowest):
-7% against seed 12345's 0.1946 and +3% against seed 23456's 0.1763, quarters 0.1833, 0.1825, 0.1789, 0.1801 (flat, as both earlier seeds),
so the 6 h `tail` cell's three seeds span 0.176-0.195 (mean 0.1840, +/-5%), 2.2x the subnet model's 0.0819: the same +/-5% seed band E34 finds
for the spread fleet at 24 h, and the number to quote for this cell. Exposure: `sp_r` precision 1.00, recall 0.043, 17 of 39 twenty-transaction
users attributed (seeds 12345 and 23456: 18 and 21 of 40). Relays 0.2062 (1.14x light) with the start-order gradient at hour 10 (0.145 to 0.294
across the quarters, 1.8x to 3.6x the ceiling), as in every `24` cell since E16. `simbox3`'s queue is empty; it keeps the nine-patch binary.

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

**(b) The seed replicate** (P15; `lean_legacy_none_h300_k21_w13h_m2_n600_s23456`, `simbox2`, 18:12-20:47, 153 min, exit 0,
lowest free RAM 12.7 GiB, 1,097 stem txs, 0.193 fluff per hop). Light-node share **0.2826** (seed 12345: 0.2857, a 1% spread),
by quarter 0.2851, 0.2835, 0.2829, 0.2791 (Q4 2% below Q1). Relays **0.319** (1.13x light), users 0.0868, observers 0.2007,
miners 0.1428. Its `24` partner at the same seed and box is E21's 0.1626, so the `24`/`legacy` ratio is **0.575**: stock dedup
removes 42.5% of this fleet's light slots at seed 23456, 41.8% at seed 12345. The relay curve has E23's shape: all relays 0.159
at hour 2, 0.269 at hour 3, 0.299 at hour 4, then 0.31-0.33 from hour 5 to 19 with no trend (hour 19: 0.318); the earliest-started
quarter sits at 0.17-0.20 and the latest at 0.46-0.48 for the whole 14 hours. Estimators: `sp_r` 92 guesses, 92 correct
(precision 1.00, recall 0.089), **24 of 40** twenty-transaction users exposed (seed 12345: 23 of 40); `combined` exposes all 5
busy reachable nodes. Both seeds now agree on every number E23 rests on: the old rule gives this fleet 1.7x what stock gives it,
the excess is 2.3x the `legacy` model, and it is stationary.

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

### E25. The full ban list on half the nodes, `tail`: adopters at zero, the other half carries 12% more (2026-10-23 15:36-18:12, `simbox2`)

Prediction P14 (filed and committed 15:33; the run started 15:36). `lean_24_half_h300_k21_w13h_m2_n600_s12345`: the `tail` layout
(42 spies in 21 /24s) under `24`, 13 h warmup, window 15-19 h, seed 12345, with the ban list naming all 21 spy /24s on 165 of the
340 honest nodes: 117 relays (the `relay-r-a` half), 24 medium nodes, 20 users and 4 observers adopt; 116 relays, 24 medium, 20 users,
4 observers, the 5 miners and the seeds do not. 155 min wall, exit 0, lowest free RAM 12.6 GiB, 1,095 stem txs, 0.193 fluff per hop.
Partners on the same seed: no list 0.1662 (E19, `phantom`); the list naming 10 of the 21 /24s on the same 165 nodes 0.1309 (E19, `simbox2`).

**Shares.** Light-node share **0.0928**, by quarter 0.0913, 0.0943, 0.0945, 0.0912: flat. Adopters (165 nodes) **0.0000**. The
scorer's non-adopter group (175 nodes, slot-weighted, with the 5 miners' 500 slots at 0.1244) 0.1537. Relays 0.1058, users 0.0268,
observers 0.0450, medium 0.0424, miners 0.1244. Because every adopter is at zero, the non-adopters' own shares follow by class:
relays 0.1058 x 233/116 = **0.213** (no list: 0.188), users 0.0268 x 40/20 = **0.054** (0.048), observers 0.090 (0.122), medium
0.085, and the non-adopting light nodes together 0.0928 x 281/140 = **0.186** against 0.1662 without the list. The other half carries
**12% more** spy share than in the no-list cell: the same direction as `core`'s 3.4x (E22b), at a far smaller size.

| Cell (seed 12345, 13 h warmup) | Light | Adopters | Scorer's non-adopters | Relays | Users | `sp_r` recall (= ceiling) | 20+-tx users exposed |
|---|---|---|---|---|---|---|---|
| No list (E19) | 0.1662 | - | 0.1662 | 0.1881 | 0.0478 | 0.059 | 18 of 40 |
| List naming 10 of 21 /24s, half the nodes (E19) | 0.1309 | 0.0777 | 0.1398 | 0.1472 | 0.0474 | 0.050 | 20 of 40 |
| List naming all 21 /24s, half the nodes (this run) | 0.0928 | 0.0000 | 0.1537 | 0.1058 | 0.0268 | 0.022 | 7 of 40 |

**The relay curve** (all 233 relays, adopters included at zero, so the non-adopting relays read about twice these values;
`spy_share_vs_time.txt` in the run's folder): 0.064 at hour 2, 0.128 at 3.5, 0.118 at 5, 0.115 at 8, 0.110 at 12, 0.103 at 15,
0.105 at 19. The non-adopting relays therefore go from about 0.26 at the drain peak to 0.21 at hour 19, an 18% fall over hours 3.5-19
against the no-list cell's 12% over hours 8-19.
**Estimators** (40 unreachable users, 1,031 txs): `sp_r` 23 guesses, 23 correct: precision **1.000**, recall **0.022**, equal to its
ceiling (23 of 1,030); **7 of 40** senders with 20 or more txs exposed, all of them necessarily among the 20 non-adopting users (7 of
20, 35%, against 18 of 40, 45%, without the list). The 5 busy reachable nodes (64 txs): `sp` 4 of 21 correct (precision 0.19);
`combined` exposes 2 of the 4 with 10-19 txs and the one with 5-9. Medians: unreachable nodes' spy share of stem peers 0.0 (37.5%
ever had one), of outbound peers 0.0 (47.5%); reachable nodes 0.0 and 0.009.
**Score (P14).** Light 0.0928 in 0.08-0.12: **hit**. Adopters 0.0000, at most 0.005: **hit**. Non-adopters 0.1537 against 0.17-0.24:
**miss, below**, as the clause was written (it named the scorer's slot-weighted group, as E22b did); the quantity the clause was about,
the non-adopting light nodes, reads 0.186, inside the range. Relays 1.14x light in 1.0-1.25: hit. Exposure 7 of 40 in 5-12: **hit**.
`sp_r` precision 1.00 and recall at its ceiling: hit.
**What this means.** Open question 7's pair is complete for `tail` at 13 h: naming 10 of the 21 spy /24s on half the nodes takes the
fleet from 0.166 to 0.131 light (-21%), naming all 21 takes it to 0.093 (-44%), and the users who adopt are not exposed at all
(precision-1 attribution needs a spy first hop, and adopters have none). The list's cost to non-adopters is real but small, +12%,
against +240% in `core`, where the list on half the nodes left the spies' 113 IPs competing for the other half's single slot. For X1:
with the stock rule and a complete list on half the network, a 2-per-/24 fleet of 42 attributes 7 of 40 twenty-transaction users
within 4 h instead of 18, all of them non-adopters; what it does to the half that adopts is nothing.

### E26. One spy per /24 at steady state: the lock-in is stationary at 2.3x the ceiling (2026-10-23 17:55-21:38, `phantom`)

Prediction P16(a) (filed and committed 18:05; the run started 17:55 on the cell generated earlier, the prediction before the first
simulated hour). `lean_24_none_h300_k21_w24h_m1_n600_fx_s12345`: the `tail` layout at **1 spy per /24** (21 spies in 21 /24s,
`--spy-node0 600`, 432 daemons), stock `24` selection, **24 h warmup**, window 26-30 h, fixed RandomX seed (the cell passes block
2112), seed 12345. Its 13 h partner is E24a (0.1978 at hours 15-19). 222 min wall, exit 0, lowest free RAM 10.6 GiB, 1,109 stem
txs, 0.203 fluff per hop.

**Shares.** Light-node share **0.1911**, by quarter 0.1911, 0.1889, 0.1920, 0.1922: flat (Q4 0.6% above Q1). Relays **0.2187**
(1.14x light), users 0.0522, observers 0.0808, medium 0.0917, miners 0.1356. Ceiling 0.0822, so **2.32x** at 26-30 h against
2.41x at 15-19 h: thirteen more simulated hours took 3% off the light share.

**The relay curve** (all 233 relays and by start-order quarter; full curve in the run's folder):

| Sim hour | 2 | 3 | 4 | 6 | 8 | 12 | 16 | 20 | 24 | 28 | 30 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| All relays | 0.103 | 0.165 | 0.184 | 0.195 | 0.193 | 0.215 | 0.211 | 0.218 | 0.219 | 0.218 | 0.220 |
| Earliest-started quarter | 0.103 | 0.105 | 0.104 | 0.086 | 0.098 | 0.111 | 0.105 | 0.111 | 0.128 | 0.128 | 0.129 |
| Latest-started quarter | 0.098 | 0.247 | 0.297 | 0.318 | 0.320 | 0.336 | 0.331 | 0.323 | 0.333 | 0.313 | 0.325 |

At hour 2 all four quarters sit at 0.10, a little above the ceiling. The gradient forms between hours 2 and 6 and then nothing
relaxes: from hour 10 to hour 30 all relays read 0.205-0.220, the earliest-started quarter 0.09-0.13 (drifting up, not down), the
latest 0.31-0.34. Twenty hours past the gray-list drain the early starters have not shed a single spy slot on average. In `core`
the same twenty hours take the relays from 7x the model to the model (E22c).

**Estimators** (40 unreachable users, 1,036 txs): `sp_r` 56 guesses, 56 correct (precision **1.000**, recall 0.054), **16 of 40**
twenty-transaction users exposed; the 5 busy reachable nodes: `sp` 10 of 22 correct.

**Score (P16a).** Light 0.1911 in 0.18-0.22: hit. Flat: hit. Relays 0.2187 in 0.20-0.26: hit. Users 0.0522 in 0.05-0.08: hit.
Lowest free RAM 10.6 GiB above 8: hit. Five of five.

**What this means.** The steady state of a 21-/24 fleet under the stock rule is set within six hours of the drain and does not
move afterwards, at 1 spy per /24 as at 2 (E22a, 0.1572 at 24 h). The question left for P16b is whether 8 per /24 settles below
these two once its larger drain has passed, and for P17 whether the excess follows the candidate count (42 /24s at 1 each).

### E27. The same 42 spies in 42 /24s: the excess is a multiplier on the ceiling, 2.2x, and 27 of 40 users are exposed (2026-10-23 20:54-23:30, `simbox2`)

Prediction P17 (filed and committed 20:54, `dda6ddcc`; the run started 20:54). `lean_24_none_h300_k42_w13h_m1_n600_s12345`:
`tail`'s 42 spies spread over **42 /24s at 1 spy each** (`--spy-subnets 42 --spies-per-subnet 1 --spy-node0 600`, 384 daemons),
stock `24` selection, 13 h warmup, window 15-19 h, seed 12345, stock RandomX. The run's `model` line: 42 spies in 42 /24s, 300 honest
reachable in 242 /24s, `24` **0.1531** (`legacy` 0.1238). 154 min wall, exit 0, lowest free RAM 12.5 GiB, 1,098 stem txs, 0.214
fluff per hop.

**Shares.** Light-node share **0.3369**, by quarter 0.3387, 0.3375, 0.3371, 0.3344: flat (Q4 1.3% below Q1). Relays **0.3746**
(1.11x light), users **0.133**, observers 0.256, medium 0.2168, miners 0.2725. Against the ceiling: **2.20x**. The stock-rule
`tail` family at 13 h, all with 300 honest reachable in 242 /24s:

| Cell | Spies | Spy /24s | Ceiling | Light | Light / ceiling | Users | 20+-tx users exposed |
|---|---|---|---|---|---|---|---|
| E19, 2 per /24 | 42 | 21 | 0.0822 | 0.1662 | 2.02x | 0.0478 | 18 of 40 |
| E24a, 1 per /24 | 21 | 21 | 0.0822 | 0.1978 | 2.41x | 0.0556 | 17 of 40 |
| E24, 8 per /24 | 168 | 21 | 0.0822 | 0.1749 | 2.13x | 0.0545 | 17 of 40 |
| **this run, 1 per /24** | 42 | **42** | **0.1531** | **0.3369** | **2.20x** | **0.133** | **27 of 40** |
| E23, `legacy`, 2 per /24 | 42 | 21 | 0.1221 | 0.2857 | 2.34x | 0.0747 | 23 of 40 |

Doubling the /24 count at a fixed spy count doubles the light share (0.166 to 0.337, 2.03x) and nearly triples the users' share
(0.048 to 0.133). The ratio to the ceiling stays where it has been for every cell of this family, 2.0-2.4x: the excess is a
multiplier on the model, not a fixed increment (the additive reading put this cell at 0.27) and not a saturating lock-in.

**The relay curve** (all 233 relays and by start-order quarter; full curve in the run's folder):

| Sim hour | 2 | 3 | 4 | 5 | 6 | 8 | 10 | 12 | 15 | 17 | 19 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| All relays | 0.187 | 0.273 | 0.325 | 0.359 | 0.363 | 0.373 | 0.386 | 0.379 | 0.377 | 0.384 | 0.370 |
| Earliest-started quarter | 0.225 | 0.217 | 0.227 | 0.238 | 0.247 | 0.234 | 0.228 | 0.236 | 0.238 | 0.247 | 0.226 |
| Latest-started quarter | 0.169 | 0.316 | 0.416 | 0.471 | 0.492 | 0.516 | 0.540 | 0.525 | 0.505 | 0.530 | 0.517 |

Hour 2 sits at 0.19, already above the 0.153 ceiling (the early gray-list picks are spy-rich, as in E23). The share settles by hour 5
and reads 0.36-0.39 to hour 19. The start-order gradient is the family's: the earliest-started quarter 0.22-0.25 for the whole
run, 1.5x the ceiling, the latest 0.50-0.54. P17 said the latest quarter would pass 0.6 and it did not: at 42 /24s the late starters
hold 6 of 12 slots on spies, the same 6 as at 21 /24s under `legacy` (0.46-0.49) and more than the 4 at 21 /24s under `24`
(0.31-0.34), so the latest quarter scales less than proportionally even as the fleet average scales in proportion.

**Estimators** (40 unreachable users, 1,033 txs): `sp_r` **130 guesses, 130 correct** (precision 1.000, recall **0.126**, equal to its
ceiling: 130 of 1,031 user txs were stemmed straight to a spy), **27 of 40** twenty-transaction users exposed within the 4 h window
(`tail` at 2 per /24: 18 of 40; `legacy` `tail`: 23 of 40). The 5 busy reachable nodes (65 txs): `sp` 7 of 15 correct, `combined`
exposes none of them at precision above 0.5.

**Score (P17).** Light 0.3369 in 0.30-0.40: hit. Flat: hit. Relays 1.11x light in 1.05-1.25: hit. Users 0.133 in 0.08-0.14: hit.
Relay curve stationary from hour 5: hit. Latest-started quarter above 0.6: **miss** (0.50-0.54). Five of six.

**What this means.** (1) The candidate-count reading is confirmed in the form that matters: under the stock rule a spy operator's
light-node share is about 2.2x the subnet model's prediction for their /24 count, so the lever is the number of /24s, not the number
of IPs. 42 IPs in 21 /24s read 0.166; the same 42 IPs in 42 /24s read 0.337 and attribute 27 of 40 users within 4 h at precision 1.
(2) Stock dedup's defence against a fleet is therefore its cost in /24s: it halves what a 2-per-/24 fleet gets (E23), and gives a
1-per-/24 fleet nothing to lose. A 42-/24 ban list for this fleet is 42 entries, which is the size of question for open question 7.
(3) The excess over the model is a property of the stock rule's recency selection against a static white list, not of the layout:
2.0-2.4x across five layouts and two rules. Why 2.2 and not 1 is open question 10. (4) For X1: this is the worst-case `tail`
layout at 42 spies, and the first cell in which the users' own share passes 0.1.

**(b) The seed replicate** (P19; `lean_24_none_h300_k42_w13h_m1_n600_s23456`, `simbox2`, 2026-10-23 23:36 to 10-24 02:10, 152 min,
exit 0, lowest free RAM 12.5 GiB, 1,097 stem txs, 0.197 fluff per hop; this seed's layout has 300 honest reachable in 240 /24s,
ceiling 0.1539). Light-node share **0.334** (seed 12345: 0.3369, a 1% spread), by quarter 0.3278, 0.3344, 0.3378, 0.3358 (Q4 2.4%
above Q1), **2.17x** the ceiling. Relays **0.3772** (1.13x light), observers 0.2291, miners 0.2459. Users **0.1033** against 0.133 at
the first seed: the users' share has a 25% seed spread where the light nodes' has 1%, which is the small-number effect of 40 users
with 12 slots each against 281 light nodes, and the reason user-level numbers in this journal are quoted as ranges. Relay curve:
0.273 at hour 3, 0.341 at 5, 0.36-0.38 from hour 8 to 19; earliest-started quarter 0.21-0.24, latest 0.48-0.53. Estimators: `sp_r`
102 guesses, 102 correct (precision 1.000, recall 0.099), **26 of 40** users exposed (seed 12345: 27 of 40). E27's 2.2x multiplier
and its 26-27 of 40 exposed stand at two seeds.

### E28. The 42-/24 layout under the old rule: the /24 layout does not matter where the selection ignores it, and stock dedup now gives the fleet more (2026-10-23 21:44 to 2026-10-24 00:20, `phantom`)

Prediction P18 (filed and committed 21:43-21:44, `b43ded19`; the run started 21:44). `lean_legacy_none_h300_k42_w13h_m1_n600_s12345`:
E27's layout (42 spies in 42 /24s at 1 each, 384 daemons) under v0.18.4.2's selection (`--sim-subnet-dedup=legacy`), 13 h warmup,
window 15-19 h, seed 12345, stock RandomX. The run's `model` line: `legacy` **0.1237** (`24` 0.1531). 154 min wall, exit 0, lowest
free RAM 10.5 GiB, 1,100 stem txs, 0.199 fluff per hop.

**Shares.** Light-node share **0.2984**, by quarter 0.2991, 0.2959, 0.2970, 0.3016: flat (Q4 0.8% above Q1). Relays **0.3369**
(1.13x light), users 0.0981, observers 0.1791, medium 0.1657, miners 0.2561. Against its model: **2.41x**. E23's cell, the same
42 IPs in 21 /24s under the same rule, read 0.2857 and 0.2826 (2.34x and 2.31x): the /24 layout moved the old rule's result by 4%,
which is at the edge of the family's seed spread. The two rules at the two layouts, seed 12345:

| Layout | `legacy` light (model) | `24` light (ceiling) | `24` / `legacy` | Models' ratio |
|---|---|---|---|---|
| 42 spies in 21 /24s (E23, E19) | 0.2857 (0.1221) | 0.1662 (0.0822) | **0.58** | 0.67 |
| 42 spies in 42 /24s (this run, E27) | 0.2984 (0.1237) | 0.3369 (0.1531) | **1.13** | 1.24 |

**The relay curve** (all 233 relays and by start-order quarter; full curve in the run's folder): 0.288 at hour 3, 0.316 at 4, 0.330
at 5, then 0.33-0.35 to hour 19 (hour 19: 0.340); earliest-started quarter 0.20-0.22 throughout, latest 0.46-0.50. The same shape
and the same gradient as E23 and E27.

**Estimators** (40 unreachable users, 1,033 txs): `sp_r` 72 guesses, 72 correct (precision 1.000, recall 0.070), **24 of 40**
twenty-transaction users exposed (E27, stock rule, same layout: 27 of 40; E23, same rule, 21 /24s: 23 of 40). The 5 busy reachable
nodes (67 txs): `sp` 15 of 21 correct (precision 0.71, recall 0.22).

**Score (P18).** Light 0.2984 in 0.27-0.32: hit. Flat: hit. Relays 1.13x light in 1.05-1.25: hit. Users 0.0981 in 0.07-0.10: hit.
Four of four.

**What this means.** (1) Under `legacy` the candidates are IPs and the layout of those IPs across /24s is nearly irrelevant: 42 IPs
read 0.29-0.30 whether in 21 /24s or 42. Under `24` the candidates are /24s and the same move doubles the share. The candidate-count
reading now has both halves. (2) The stock rule's dedup is not a defence against a 1-per-/24 fleet; it is a **subsidy**. At one
candidate per /24, every spy /24 counts once, as does every honest /24, and the 300 honest reachable IPs sit in 242 /24s: the
honest side loses 19% of its weight and the spies lose none. The models say 1.24x, the cells say 1.13x. Any operator who already
spreads one IP per /24 gained slots from #9939; a fleet that packs /24s lost 42%. (3) For open question 7: the stock rule leaves
the ban list as the only defence against the spread layout, and that list has one entry per spy. P20 measures it.

### E29. The full ban list on half the nodes against the spread fleet: adopters at zero, the other half carries 10% more, 15 of 40 exposed (2026-10-24 00:26-03:02, `phantom`)

Prediction P20 (filed and committed 00:26, `5f19ce9b`; the run started 00:26). `lean_24_half_h300_k42_w13h_m1_n600_s12345`: E27's
spread fleet (42 spies in 42 /24s) with the ban list naming all 42 spy /24s on half the honest nodes (`--list half --ban-coverage
1.0`, 165 adopters, 175 non-adopters, the same seeded half as E25), stock `24`, 13 h warmup, window 15-19 h, seed 12345. 155 min
wall, exit 0, lowest free RAM 10.6 GiB, 1,095 stem txs, 0.207 fluff per hop, loop rate 0.059.

**Shares.** Light-node share **0.184** (no list, E27: 0.3369; **0.55x**), by quarter 0.1869, 0.1845, 0.1827, 0.1821: flat (Q4 2.6%
below Q1). Adopters (165 nodes) **0.0000**. The scorer's non-adopter group (175 nodes, slot-weighted, with the 5 miners' 500 slots at
0.2618) 0.3156. Relays 0.2088, users 0.0528, observers 0.1206, medium 0.1064. With every adopter at zero the non-adopters' own
shares follow by class: relays 0.2088 x 233/116 = **0.419** (no list: 0.3746, +12%), users 0.0528 x 40/20 = **0.106** (0.133 and
0.103 at the two seeds), observers 0.241 (0.256), and the non-adopting light nodes together 0.184 x 281/140 = **0.369** against
0.3369 without the list: **+10%**. The two ban-list cells side by side:

| Fleet (seed 12345, 13 h, full list on half the nodes) | Light, no list | Light, list | Ratio | Non-adopting light nodes | Exposed, no list | Exposed, list |
|---|---|---|---|---|---|---|
| `tail`, 42 spies in 21 /24s (E19, E25) | 0.1662 | 0.0928 | 0.56 | 0.186 (+12%) | 18 of 40 | 7 of 40 |
| spread, 42 spies in 42 /24s (E27, this run) | 0.3369 | 0.184 | 0.55 | 0.369 (+10%) | 27 of 40 | 15 of 40 |

**The relay curve** (all 233 relays, adopters included at zero, so the non-adopting relays read about twice these values): 0.164 at
hour 3, 0.192 at 5, 0.206 at 8, 0.21 from hour 8 to 19 (hour 19: 0.207); the start-order gradient is there (earliest quarter 0.11,
latest 0.29) and nothing relaxes. The non-adopting relays sit near 0.41-0.42 from hour 8 on.

**Estimators** (40 unreachable users, 1,033 txs): `sp_r` 52 guesses, 52 correct (precision **1.000**, recall 0.050, at its ceiling),
**15 of 40** twenty-transaction users exposed, necessarily all among the 20 non-adopting users (15 of 20, 75%; E27: 27 of 40, 68%).
The list protects the adopting users completely and leaves the non-adopting users slightly worse off than before.

**Score (P20).** Light 0.184 in 0.17-0.21: hit. Adopters 0.0000 at most 0.005: hit. Non-adopting light nodes 0.369 in 0.34-0.42: hit.
Users 0.0528 in 0.05-0.09: hit. `sp_r` precision 1: hit. Exposed 15 of 40 in 9-16, all non-adopters: hit. Relays 1.13x light in
1.05-1.25: hit. Flat: hit. Eight of eight.

**What this means.** (1) The ban list's effect does not depend on the fleet's layout: on half the nodes it removes 44-45% of the
fleet's light-node slots whether the fleet packs /24s or spreads them, because adopters go to exactly zero and non-adopters pick up
10-12% more. Its cost is one entry per spy /24, which for the spread fleet is one per spy. (2) For open question 7 the answer at
coverage 1.0 is now measured on both presets: adopters are fully protected, non-adopters are not protected at all, and the network
total falls by the adopters' share less the 10-12% refill. A list on half the network halves the exposed users and no more. (3) The
spread fleet with the list on half the nodes (0.184) still beats the packed fleet without any list (0.166): against a spreading
operator, half the network adopting a complete list recovers only what the stock rule's /24 counting gave away (E28).

### E30. Eight spies per /24 at 26-30 h: below the 2-per-/24 cell, but still draining after thirty hours (2026-10-23 20:19 to 2026-10-24 03:16, `simbox3`)

Prediction P16(b) (filed and committed 18:05; the run started 20:19). `lean_24_none_h300_k21_w24h_m8_n600_fx_s12345`: the `tail`
layout at **8 spies per /24** (168 spies in 21 /24s, 508 daemons), stock `24` selection, **24 h warmup**, window 26-30 h, fixed
RandomX seed, seed 12345. Its 13 h partner is E24 (0.1749 at hours 15-19, falling). 413 min wall, exit 0, lowest free RAM 75.6 GiB
on the 100 GB box, 1,079 stem txs, 0.19 fluff per hop.

**Shares.** Light-node share **0.1497**, by quarter 0.1531, 0.1514, 0.1497, 0.1448: **not flat**, Q4 is 5.4% below Q1. Relays
**0.1677** (1.12x light), users 0.0417, observers 0.1642, medium 0.0942, miners 0.0871. Against the 0.0822 ceiling: 1.82x at 26-30 h,
against 2.13x at 15-19 h. The spies-per-/24 series at the 24 h warmup, all 21 /24s, stock rule:

| Spies per /24 | Spies | Light at 26-30 h | Light / ceiling | Light at 15-19 h | Relay curve, hours 20-30 | Exposed |
|---|---|---|---|---|---|---|
| 1 (E26) | 21 | 0.1911 | 2.32x | 0.1978 | flat, 0.218-0.220 | 16 of 40 |
| 2 (E22a) | 42 | 0.1572 | 1.91x | 0.1662 | about -5% | - |
| 8 (this run) | 168 | **0.1497** | **1.82x** | 0.1749 | **0.181 to 0.155, -14%** | 16 of 39 |

**The relay curve** (all 233 relays and by start-order quarter; full curve in the run's folder): 0.127 at hour 2, 0.180 at 3, a peak
of **0.394 at hour 4** (the gray-list drain of 168 spies; `core`'s 113 spies peaked at the same hour), then 0.323 at 6, 0.274 at 8,
0.245 at 10, 0.222 at 12, 0.199 at 16, 0.181 at 20, 0.183 at 24, 0.172 at 26, 0.163 at 28, **0.155 at 30**. The fall from hour 20 to
30 is 14%; the last four hours fall 10%. The start-order quarters are much closer than in the 1- and 2-per-/24 cells: at hour 30 the
earliest 0.099, the latest 0.200 (2.0x; E26 at the same hour: 0.129 and 0.325, 2.5x).

**Estimators** (40 unreachable users, 1,007 txs; one user fell to 10-19 txs): `sp_r` 46 guesses, 46 correct (precision 1.000,
recall 0.046), **16 of 39** twenty-transaction users exposed; the 5 busy reachable nodes: `sp` 8 of 15 correct.

**Score (P16b).** Light 0.1497 in 0.10-0.15: **hit, by 0.0003**, and the cell is not at steady state, so the number this clause
was about (the steady state) is lower still: the direction is right. Relays 0.1677 in 0.11-0.17: hit. Relay curve flat over hours
20-30 within 10%: **miss** (-14%). Free RAM above 60 GB: hit. Three of four, with the flatness miss qualifying the first hit.

**What this means.** (1) The spies-per-/24 question (E22, E24, P13, P16) resolves into two effects. Packing more spies into the same
/24s does lower the fleet's steady-state share under the stock rule, 2.32x the ceiling at 1 per /24, 1.91x at 2, at most 1.82x at 8,
so E22's dilution is real; but it is small next to the /24 count (E27: doubling the /24s doubles the share), and most of the 1-to-8
gap at any fixed hour is the drain transient, which scales with the spy count: 168 spies take more than thirty hours to shed,
where 21 settle in six. (2) The cell that "stays stationary" and the cell that "decays like `core`" are the same rule at different
spy densities: with many spy IPs behind each candidate /24 the early spy-rich picks keep being replaced by other spies in the same
/24 as connections churn, which is the `core` behaviour in miniature, and the decay toward the ceiling is slow because every
replacement draw still sees 21 spy /24s. (3) For the operator the lesson of E27 stands unchanged: IPs per /24 cost money and buy a
smaller share per IP; /24s buy share in proportion. (4) The 8-per-/24 steady state is not measured; a longer cell would need a
third day of simulated time (about 11 h wall on `simbox3`) and is not queued: the question it answers is second order.

### E31. The Threadripper reads 0.0624 on the H=71 `legacy` cell: validated (2026-10-24 05:28-06:12, `zenith2alpha`)

**Cell.** `lean_legacy_none_h71_k1_s12345` (13 spies in one /24, 71 honest reachable in 60 /24s, 40 users, `legacy` selection, 6 h,
124 daemons), the platform check that validated `simbox2` (E6) and `simbox3` (P6a). First run on `zenith2alpha` (192.168.1.33: Threadripper
3970X, 64 threads, 251 GB, Ubuntu 24.04.5), a fresh `setup.sh --clean --sim-binary` build (`monerod-sim` sha256 `bb53709e...`, provenance
equal to phantom's apart from `built:`), live run on the Optane `/fast`, KSM at the box's existing 10000 pages / 20 ms, Shadow on 32 workers
(the physical cores). Wall 41 min 48 s (43 min to the driver's DONE), exit 0, all five checks, 124 nodes at 100% sync, height 1676, 0 failed
processes, lowest free RAM 170.7 GB.

**Reading (P22).** Light-node outbound share **0.0624** (phantom 0.0610, simbox2 0.0614, simbox3 0.0641; the `legacy` model's one-spy-slot
ceiling 0.075), by quarter 0.059, 0.0625, 0.0624, 0.0651. Relays 0.077-0.083 over the first three hours, then noisy on 50-57 slots
(0.039-0.083), as on the other boxes at this size. The spies saw all 953 txs; `sp_r` precision 1.00, recall 0.087 (ground truth: 78 of 897
user txs stemmed straight to a spy), 26 of 35 twenty-transaction senders and 5 of 5 ten-to-nineteen exposed in the 4 h window.
**P22 hit on all four clauses** (section 5). The box takes the lab's headline cells from here.

**Not pre-registered.** The wall time equals phantom's (43 min on 16 workers) despite twice the workers: at 124 daemons Shadow's wall is set
by its serial per-round path, not by cores. The Threadripper's gain for this lab is RAM and daemon count (a 508-daemon cell left 75 GB free
on simbox3's 100 GB), not speed per cell; the driver still runs one cell at a time, so two or three cells side by side there is a driver
change, not a Shadow one.

**Register.** `20261024_052857_lean_legacy_none_h71_k1_s12345`, box `zenith2alpha`; estimators and `spy_share_vs_time.txt` in the run's
folder; events in `logs/queue_events_tr_through_20261024.events`.

### E32. The spread fleet's 24 h steady state: 0.3354, E27's number, with relays still creeping and 33 of 40 users exposed (2026-10-24 03:31-07:19, `phantom`)

**Cell.** `lean_24_none_h300_k42_w24h_m1_n600_fx_s12345` (P21): E27's spread fleet, 42 spies in 42 /24s at 1 each, 300 honest reachable in 242 /24s,
40 users, `24` selection, no list, 384 daemons, **24 h warmup**, window 26-30 h, fixed RandomX seed, seed 12345. Wall 3 h 45 m on 16 workers,
exit 0, all checks, 382 nodes at 100% sync, height 2398, lowest free RAM 10.6 GB (the 32 GB box's floor for this size).

**Reading.** Light-node outbound share **0.3354** (E27 at 13 h: 0.3369; E27b, seed 23456: 0.334), 2.19x the subnet model's 0.1531, by quarter
0.3308, 0.3329, 0.3366, 0.3411 (+3% across the window). By class: users 0.1272, observers 0.2005, relays 0.3758 (1.12x light), miners 0.2677,
seeds 0.1299. The relays' curve from hour 10 to 30: 0.358, 0.351, 0.350 (h20), 0.365 (h26), 0.375 (h28), 0.386 (h30), a 10% rise over the
last ten hours, with the start-order gradient of E21 intact and widening: by start-order quarter at hour 30, 0.240, 0.326, 0.429, 0.549
(the latest-started relays at 3.6x the ceiling, the earliest at 1.6x). Exposure: the spies saw all 1100 txs; `sp_r` precision 1.00, recall
0.134, **33 of 40** twenty-transaction users attributed (E27: 27 of 40; E27b: about 20).

**P21: five of seven clauses hit.** Share, flatness by quarter, relays 1.05-1.2x light, users 0.09-0.15, `sp_r` precision and the 10 GB floor
hit; the relays' flatness over hours 10-30 (within 5%) missed by a 10% rise, and 22-30 exposed users missed high at 33. What it settles: the
spread fleet's 2.2x over the model is a steady state of the light nodes (the three reads at 13 h, 13 h/seed 23456 and 26-30 h agree to 1%),
so E27's number can be quoted as such. What it adds: the relays are not stationary even at 30 h, the latest-started ones still rising, which is
the recency lock-in of E21 continuing to feed on itself; and the exposure count at a fixed share spans 20-33 of 40 across seeds and windows,
the least stable number in this family (a 4 h window over 40 users is small; it should be reported as a range, not a point).

**Register.** `20261024_033150_lean_24_none_h300_k42_w24h_m1_n600_fx_s12345`, box `phantom`; estimators and `spy_share_vs_time.txt` in the
run's folder; events in `logs/queue_events_phantom_through_20261024.events` (phantom's `~/queue/x0_queue.events`, now a real file).

### E33. The ten-patch binary passes its flag-off check on phantom: 0.0628 (2026-10-24 07:27-08:11, `phantom`)

`lean_legacy_none_h71_k1_s12345` (P25) on `phantom`'s `monerod-sim` rebuilt from all ten vendored patches (`patches/monero-sim-uniform-whitelist-pick.patch`
added that morning, sha256 `b8d6fbb6...`), the flag off as in every cell without `_up`. Light-node share **0.0628** (this box on the nine-patch binary:
0.0610; simbox2 0.0614, simbox3 0.0641, zenith2alpha 0.0624), by quarter 0.0622, 0.065, 0.0597, 0.064; users 0.0597, observers 0.0725, relays 0.0735.
Exit 0, all five checks, 124 nodes at 100% sync, wall 44 min, lowest free RAM 20.2 GB. The archive holds all 124 daemons' outputs: every one logs the
subnet-dedup patch's startup line, none the uniform-pick line, so the flag was off everywhere. `sp_r` precision 1.00, recall 0.072, 23 of 40
twenty-transaction users attributed (E31 on the Threadripper: 26 of 35). **P25 hit on all clauses**: the new patch leaves the flag-off path where it was,
within the spread the same cell shows across boxes and binaries, and the `_up` probe (P24) may be read. Register
`20261024_072708_lean_legacy_none_h71_k1_s12345`, box `phantom`.

### E34. The spread fleet's 24 h steady state at a second seed: 0.3524, 5% above P21 and 5.5% above the same seed's 13 h read (2026-10-24 06:17-09:36, `zenith2alpha`)

**Cell.** `lean_24_none_h300_k42_w24h_m1_n600_fx_s23456` (P23): P21's cell at seed 23456 (E27's spread fleet, 42 spies in 42 /24s at 1 each,
300 honest reachable in 240 /24s, 40 users, `24` selection, no list, 384 daemons, 24 h warmup, window 26-30 h, fixed RandomX seed), the first
cell generated on the control box with `make_cell.sh` (md5 `93e4bfa5`), run on the Threadripper with Shadow at 32 workers. Wall 3 h 16 m, exit 0,
all checks, 382 nodes at 100% sync, height 2396, lowest free RAM 160 GB.

**Reading.** Light-node outbound share **0.3524** (P21, seed 12345: 0.3354; E27b, this seed at 13 h: 0.334; E27: 0.3369), 2.29x the subnet
model's 0.1539, by quarter 0.3512, 0.3515, 0.3540, 0.3527 (+0.4% across the window, the flattest 24 h read so far). By class: users 0.1046,
observers 0.1968, relays 0.4002 (1.14x light), miners 0.2519, seeds 0.0763. The relays' curve: 0.387 (h10), 0.394 (h20), 0.398 (h26),
0.399 (h28), 0.408 (h30), +5% over hours 10-30 and +3% over hours 20-30 (P21: +10% over 20-30). By start-order quarter at hour 30: 0.236,
0.339, 0.452, 0.602 (P21: 0.240, 0.326, 0.429, 0.549): the earliest-started relays at 1.5x the ceiling in both seeds, the latest-started at
3.9x here against 3.6x. Exposure: the spies saw all 1101 txs; `sp_r` precision 1.00, recall 0.109, **29 of 40** twenty-transaction users
attributed (P21: 33; E27: 27; E27b: about 20).

**P23: four of seven clauses hit.** Flatness by quarter, relays 1.05-1.2x light, users 0.09-0.15 and 20-30 exposed hit. The share missed
0.31-0.35 by 0.002 and its ratio to P21, 1.051x, missed the 0.95-1.05x band by 0.001x; the wall, 3 h 16 m, missed "under 2.5 h". The filed
reading of a share outside the range ("the spread fleet has no seed-stable steady state") claims more than a 0.7% overshoot supports. What
the two seeds show: the 24 h steady state is seed-sensitive at the 5% level (0.335 and 0.352), the same spread the 13 h reads had (0.334,
0.337) but not the same ordering, since seed 23456 moved +5.5% from 13 h to 26-30 h while seed 12345 moved -0.4%. So E27's 2.2x stands as
the family's value with a +/-3% seed band around 0.344, and "steady state" means light nodes flat within any one window while the relays'
lock-in (E21) adds a few percent per ten hours. The between-seed difference sits in the relays (0.376 to 0.400, +6.5%), not the users
(0.127 to 0.105) or the observers (0.201 to 0.197). The wall clause: 32 Shadow workers on the Threadripper gained 13% over phantom's 16
(3 h 16 m against 3 h 45 m); Shadow does not scale with workers at this size, so the box's value to the lab is its 250 GB (160 GB free
during this run), bigger cells rather than faster ones.

**Register.** `20261024_061705_lean_24_none_h300_k42_w24h_m1_n600_fx_s23456`, box `zenith2alpha`; estimators and `spy_share_vs_time.txt` in
the run's folder; events in `logs/queue_events_tr_through_20261024.events`.

### E35. A uniform white-list pick leaves the spread fleet at 2.1x: the cubic recency draw is not the cause of the multiplier (2026-10-24 09:42-12:01, `zenith2alpha`)

**Cell.** `lean_24_none_h300_k42_w13h_m1_n600_up_s12345` (P24): E27's cell line for line (42 spies in 42 /24s at 1 each, 300 honest reachable
in 242 /24s, 40 users, `24` selection, no list, 384 daemons, 13 h warmup, window 15-19 h, seed 12345) plus `sim-uniform-whitelist-pick: true`
in `daemon_defaults`, on the ten-patch `monerod-sim` (sha256 `9cae7db31344...`). The flag replaces the stock `24` path's white-list draw,
`get_random_index_with_fixed_probability(filtered.size() - 1)` (cubic, newest-first) in `make_new_connection_from_peerlist`, with
`crypto::rand_idx(filtered.size())` over the same candidates (the stock path builds `filtered` as one random IP per unconnected /24 from the
white list in `last_seen` order, at most 20; `legacy` branches to its own function and is untouched). 382 of the 385 host logs carry the
startup line (the other three hosts run no daemon). Wall 2 h 15 m with Shadow at 32 workers, exit 0, all checks, height 2076, lowest free RAM
161 GB.

**Reading.** Light-node outbound share **0.3207** (E27, stock pick: 0.3369; E27b, seed 23456: 0.334), **2.09x** the subnet model's 0.1531,
by quarter 0.3253, 0.3204, 0.3191, 0.3182 (-2% across the window). By class: users 0.1030 (E27 0.133), observers 0.1999, relays 0.3622
(1.13x light; E27 0.3746), miners 0.2473, seeds 0.1506. The start-order gradient is intact: relays by start-order quarter over hours 15-19
read 0.19-0.21, 0.30-0.32, 0.39-0.43, 0.52-0.54 (E27: 0.23-0.25, 0.34-0.35, 0.40-0.43, 0.50-0.53), the latest-started quarter at 2.6x the
earliest and 3.5x the ceiling. Exposure: `sp_r` precision 1.00, recall 0.101, **28 of 40** twenty-transaction users attributed (E27: 27).

**P24: one of five clauses hit** (the flag line in every daemon's log). Share 0.3207 against 0.13-0.19, the gradient 2.6x against "at most
1.3x", 28 exposed against "at most 20", wall 2 h 15 m against "under 1.5 h". The filed branch for 0.28 and above applies: **the recency bias
of the pick itself is not the cause of the 2.2x**, and its whole contribution is the 5% between 0.3369 and 0.3207, inside the family's seed
band (E34). What this leaves for open question 10: everything upstream of the draw. The stock path hands the draw at most 20 candidates, one
per unconnected /24, taken in `last_seen` order from the white list, so a uniform draw over those 20 is still a draw over the 20 *newest*
/24s; E21 found the spies' mean `last_seen` rank at the 0.39 percentile of the relays' lists (newer than the middle), and their presence
among the 20 newest, not the cubic weighting within the 20, is where the excess must sit. The gradient points the same way: a relay that
started later met the spies later, so they are newer in its list. E21's Monte Carlo of the rule (0.190 per slot) folded both effects
together; it should be rerun with the pick made uniform over its 20 to see whether it predicts this 0.32, which would close the loop on the
mechanism without another cell. The next sim probe is the cap itself: a `--sim-*` flag that raises the 20-candidate limit (to the whole
deduplicated white list, so that `last_seen` order no longer selects who is drawable) should take the multiplier to 1 if this reading is
right; a `print_pl`-seeded list (open question 8) tests the age structure from the other side.

**Register.** `20261024_094257_lean_24_none_h300_k42_w13h_m1_n600_up_s12345`, box `zenith2alpha`; estimators and `spy_share_vs_time.txt` in
the run's folder; events in `logs/queue_events_tr_through_20261024.events`.

*2026-10-24 14:41, the Monte Carlo rerun (`adhoc/recency_model.py`, modes added; `recency_relays.py <archive> 24,24u,24all`) over E21's 540 relay
white lists after hour 3:* stock draw 0.1905 per slot, uniform over the same 20 **0.2172**, uniform over every unconnected /24 **0.0796** against the
cell's 0.0822 ceiling. The model agrees with the sim that the draw's shape barely matters (it puts the uniform draw 14% above the cubic where the sim
read 5% below, both small) and says the cap is the whole multiplier: with every /24 drawable, the spies get their subnet share and no more. P26 tests
that in the sim.

### E36. The candidate cap was the multiplier: with every /24 drawable the spread fleet reads 0.1577, 1.03x the subnet ceiling and the gradient is gone, but exposed users rise from 28 to 37 of 40 (2026-10-24 14:44-17:15, `zenith2alpha`)

**Cell.** `lean_24_none_h300_k42_w13h_m1_n600_up_wc0_s12345` (P26): P24's cell line for line (E27's spread fleet: 42 spies in 42 /24s at 1 each,
300 honest reachable in 242 /24s, 40 users, `24` selection, no list, 384 daemons, 13 h warmup, window 15-19 h, seed 12345,
`sim-uniform-whitelist-pick: true`) plus `sim-whitelist-candidates: 0` in `daemon_defaults`, on the eleven-patch `monerod-sim` (sha256
`8d8255edb4ea...`). The new flag replaces the stock `24` path's `limit = use_white_list ? 20 : max` on the subnet-deduplicated,
`last_seen`-ordered candidate list in `make_new_connection_from_peerlist` with no cap, so together with P24's flag the pick is a uniform draw
over every unconnected /24 in the white list: the subnet model's assumption made literal. All 382 daemon logs carry both startup lines. Wall
2 h 28 m (Shadow at 32 workers), exit 0, all checks, 382 nodes at 100% sync, height 2085, lowest free RAM 161 GB.

**Reading.** Light-node outbound share **0.1577**, **1.03x** the subnet model's 0.1531 (E27, stock: 0.3369 = 2.20x; P24, the uniform draw with the
cap kept: 0.3207 = 2.09x; the Monte Carlo for this configuration: 0.0796 against its 0.0822 ceiling = 0.97x), by quarter 0.1561, 0.1579, 0.1575,
0.1591 (flat, +2%). By class: relays **0.1562** (P24 0.3622), users **0.1647** (P24 0.1030, E27 0.133), observers 0.1649 (P24 0.1999), medium
0.161, miners 0.175 (P24 0.2473), seeds 0.0572 (P24 0.1506). The start-order gradient is gone: relays by start-order quarter over hours 15-19
read 0.1256, 0.1755, 0.1636, 0.1583 (P24: 0.21, 0.30, 0.42, 0.53), the latest-started quarter 1.26x the earliest, and what spread remains is
not monotone: the earliest-started quarter sits 18% below the ceiling (0.111-0.137 by half hour) and the other three at 1.03-1.15x. Over the
whole run the relays' share falls from 0.40 in the first half hour to the ceiling by hour 6 and stays there (P24's rose from 0.19 at hour 2 to
0.37 by hour 15). Exposure: `sp_r` precision 1.00, recall **0.173** (P24 0.101), **37 of 40** twenty-transaction users attributed (E27 27, P24
28); the combined estimator 37 of 40 and 5 of 5 busy senders. Stem-peer spy share: users' median 0.157, and every user had a spy stem peer at
some point in the window (P24: 0.094, and 82.5% of users); relays 0.146 (P24 0.292).

**P26: five of six clauses hit.** Share 0.1577 in 0.13-0.19 (hit), gradient 1.26x against "at most 1.3x" (hit, at the edge), the flag line in
all 382 logs (hit), relays 0.1562 = 1.02x against "within 1.25x" (hit), wall 2 h 28 m against "under 2.5 h" (hit, by two minutes); **37 of 40
users exposed against "at most 20" (missed, and in the wrong direction)**. The filed reading holds for the multiplier: **the cap of 20
candidates is the whole 2.2x.** The stock `24` path draws from the 20 newest unconnected /24s by `last_seen`; the spies are newer than the
middle of the relays' lists (E21), and a relay that started later met them later, so they are newer still in its list: that is the gradient.
With every unconnected /24 drawable the draw's shape no longer matters (P24 showed that for the cubic weighting) and each class lands on its
subnet share. The Monte Carlo over E21's lists predicted this to within 6% (0.97x against 1.03x), so the mechanism is closed from both sides.

The exposure miss is the finding the prediction did not anticipate, and for senders it matters more than the aggregate. The "light" share is
233 relays, 40 users and 8 observers, so it is a relay number. The stock rule's excess sat on the relays (2.4x the ceiling) while the users sat
*below* it (0.103 in P24, 0.133 in E27: 0.67-0.87x), and the recency lock-in made a user's spy share persistent, so 17.5% of the users never
had a spy stem peer in the four-hour window and only 28 of 40 were attributed. Lifting the cap moves both classes to the ceiling, relays down
2.3x and users up 1.6x, every user meets a spy at some point, and the exposure follows the users' own share: with ~25 transactions each at
p = 0.16, independence gives 39 of 40 exposed (37 seen); at P24's 0.10 it gives 37, and 28 were seen, the lock-in's protection. For the test
plan this splits open question 10 in two. The relay-side multiplier is explained and would vanish under any candidate rule that does not
favour the newest /24s. The sender-side exposure in the stock client is *lower* than the subnet model says, because the same lock-in that
concentrates spies on late-started relays spares a fraction of users entirely, and a change that makes the pick uniform raises the users'
exposure to the model's level. Which of the two the defense work should optimise is the owner's call (open question 10, dated line). Not
explained yet: why the stock rule puts users at 0.67-0.87x of the ceiling rather than at it (E21 measured the spies' `last_seen` rank on
relays' lists only), and the earliest-started relays' 0.82x here. One seed so far; the family replicated to 1% at a second seed (E27b), and
this result needs the same before anything is claimed.

**Register.** `20261024_144444_lean_24_none_h300_k42_w13h_m1_n600_up_wc0_s12345`, box `zenith2alpha`; estimators and `spy_share_vs_time.txt` in
the run's folder; events in `logs/queue_events_tr_through_20261024.events`. P27 (the cap lifted, the stock cubic draw kept) runs on the same box.

### E37. The cubic draw over the full list adds 8%, not 51%: with the cap lifted and the stock draw kept the spread fleet reads 0.1705, 1.11x the ceiling, a faint monotone gradient (1.28x) remaining (2026-10-24 17:15-19:34, `zenith2alpha`)

**Cell.** `lean_24_none_h300_k42_w13h_m1_n600_wc0_s12345` (P27): E27's cell line for line plus `sim-whitelist-candidates: 0` in `daemon_defaults`,
the stock cubic `get_random_index_with_fixed_probability` draw kept, on the eleven-patch binary (`8d8255edb4ea...`). All 382 daemon logs carry the
candidates line and none the uniform-pick line. Wall 2 h 15 m at 32 workers, exit 0, all checks, 382 nodes at 100% sync, height 2096, lowest free
RAM 158 GB.

**Reading.** Light-node outbound share **0.1705**, **1.11x** the ceiling 0.1531 (E27, stock: 0.3369 = 2.20x; P26, the cap lifted with the uniform
draw: 0.1577 = 1.03x; the Monte Carlo's `24allc` mode for this case: 0.1242 = 1.51x), by quarter 0.1742, 0.1704, 0.1692, 0.1688 (-3%). By class:
relays **0.1756** (1.15x; P26 0.1562), users **0.1406** (0.92x; P26 0.1647), observers 0.1719, medium 0.1547, miners 0.2086, seeds 0.1299. Relays by
start-order quarter over hours 15-19: 0.1549, 0.1756, 0.1780, 0.1977, monotone, the latest-started quarter **1.28x** the earliest (E27 3.5x, P24 2.6x,
P26 1.26x but not monotone). The relays' share over the run: 0.27 in hour 1, 0.26 at hour 3, 0.21 at hour 6, 0.19 at hour 8, 0.18 from hour 12 on
(P26 had reached the ceiling by hour 6). Exposure: `sp_r` precision 1.00, recall 0.139 (P26 0.173, P24 0.101), **28 of 40** users attributed (P26 37,
P24 28, E27 27); the users' stem-peer share median 0.125, and 90% of the users ever had a spy stem peer in the window (P26 100%, P24 82.5%): the
exposure count stays at the stock cells' level although the users' share is near the ceiling, because a tenth of the users never meet a spy, the
trace of lock-in the cubic draw keeps.

**P27: two of five clauses hit** (the flag line in every log; wall 2 h 15 m under 2.5 h). Share 0.1705 against 0.19-0.28 (missed, low), the gradient
1.28x against "1.3-2.5x" (missed, just under), 28 exposed against 20-27 (missed by one, high). The filed branch for "below 0.19" applies: **the cubic
draw over the full list is nearly as good as uniform; the cap did the work.** Against the uniform draw the cubic one adds 8% to the aggregate (1.11x
against 1.03x), 12% to the relays, and leaves a faint but monotone start-order gradient where the uniform draw left none: a trace of the recency bias
survives when the newest /24s are merely favoured rather than the only ones drawable. The Monte Carlo overstated this trace six-fold (1.51x
predicted). The likely reason is in how the model draws: it weights the full `last_seen`-ordered list cubically for each slot without removing the
/24s the node then connects to, so the same newest few entries take the mass for every slot; in the client the newest /24 that is drawn becomes
connected and leaves the candidate set, so the cubic mass moves down the list with each slot filled, and over 12 slots the draw is spread across the
top few dozen entries rather than the top few. Where the cap selects the drawable set that shortcut did not matter (the `24` mode reproduced E27
and the `24all` mode P26); where the draw's shape is the only bias it does. Noted in open question 10; the model is not corrected unless the draw's
shape is studied again.

**Register.** `20261024_171548_lean_24_none_h300_k42_w13h_m1_n600_wc0_s12345`, box `zenith2alpha`; estimators and `spy_share_vs_time.txt` in the
run's folder; events in `logs/queue_events_tr_through_20261024.events`.

### E38. P26 replicates at a second seed: 0.1557, 1.01x the ceiling, no gradient; the earliest-started relays' dip was noise, and across the family the stock rule holds users at 0.75x the ceiling (2026-10-24 19:34-21:53, `zenith2alpha`)

**Cell.** `lean_24_none_h300_k42_w13h_m1_n600_up_wc0_s23456` (P28): P26's cell with `simulation_seed: 23456` (E27b's and E34's seed), the only
differing line; eleven-patch binary; 382 logs with both flag lines. Wall 2 h 15 m, exit 0, all checks, 382 nodes at 100% sync, height 2077, lowest
free RAM 160 GB.

**Reading.** Light-node outbound share **0.1557**, **1.01x** this seed's ceiling 0.1539 (240 honest /24s at this seed; P26 0.1577 = 1.03x; E27b, the
stock rule at this seed, 0.334), by quarter 0.1545, 0.1566, 0.1556, 0.1558 (flat). By class: relays **0.1579** (1.03x), users **0.1391** (0.90x; P26
0.1647, P27 0.1406), observers 0.1731, medium 0.1613, miners 0.1627, seeds 0.0729. Relays by start-order quarter over hours 15-19: 0.1558, 0.1627,
0.1494, 0.1597, the latest 1.02x the earliest and 9% between the highest and lowest quarter; the earliest-started quarter sits at 1.01x the ceiling
(P26: 0.82x). Exposure: `sp_r` recall 0.154, precision 1.00, **35 of 40** users attributed (P26 37; the stock cells 27-28); every user had a spy stem
peer at some point in the window.

**P28: three of five lettered clauses hit, and the exposure half of a fourth.** (a) 0.1557 in 0.145-0.170 (hit); (b) relays 1.03x and the gradient
1.02x (hit); (c) both lines in all 382 logs (hit); (d) 35 of 40 exposed against "at least 32" (hit) but the users' share 0.1391 against 0.14-0.19
(missed by 0.001; a miss); (e) the earliest-started quarter 1.01x against 0.75-0.95x (missed: P26's dip was seed noise, which is what the clause was
there to find out). Wall 2 h 15 m under 2.75 h. The aggregate replicates to 1.3% (0.1577 and 0.1557) and both seeds sit within 3% of their ceilings:
**with every unconnected /24 drawable the spread fleet gets its subnet share and no more, at both seeds.** The users' side is as noisy as the family's
25% user-level band said: 0.165 and 0.139 at the two seeds, straddling the ceiling, with 37 and 35 of 40 exposed.

**Users across the family** (the `user` line of each run's `x0_calibration.txt`): under the stock rule the users read 0.133 (E27), 0.103 (E27b), 0.127
(E32, 24 h), 0.105 (E34, 24 h) and 0.103 (P24, the uniform draw with the cap), mean 0.114 = **0.75x** the ceiling, across five cells at two seeds and
two warmups, with 27-28 of 40 exposed, while the relays read 0.36-0.40 (2.4-2.6x). With the cap lifted the users read 0.165, 0.141 and 0.139, mean
0.148 = 0.97x, with 37, 28 and 35 exposed, and the relays 0.156-0.176. What E36 saw at one seed holds across the family: the stock rule keeps the
users below their subnet share while it puts the relays at 2.4x it, and lifting the cap puts both at the ceiling. Why the users sit low under the
stock rule is open question 10 (d); the sender-side policy reading (E36) stands.

**Register.** `20261024_193434_lean_24_none_h300_k42_w13h_m1_n600_up_wc0_s23456`, box `zenith2alpha`; estimators and `spy_share_vs_time.txt` in the
run's folder; events in `logs/queue_events_tr_through_20261024.events`. P29 (the 24 h steady state with the cap lifted) started 00:35 on the same box.

### E39. The cap-lifted spread fleet at 24 h: 0.1655, 1.08x the ceiling, nothing accumulates over the day; on the senders' side the cap's removal shows in recall (0.187), not in the count of exposed users (2026-10-25 00:35-03:55, `zenith2alpha`)

**Cell.** `lean_24_none_h300_k42_w24h_m1_n600_fx_up_wc0_s12345` (P29): E32's cell, the spread fleet (42 spies in 42 /24s, 300 honest reachable
in 242 /24s, 40 users) at a 24 h warmup with the fixed RandomX seed, stop 30 h, window 26-30 h, seed 12345, plus `sim-uniform-whitelist-pick: true`
and `sim-whitelist-candidates: 0`, the only differing lines; eleven-patch binary (sha `8d8255edb4ea`), both flag lines in all 382 daemon logs. Wall
3 h 18 m, exit 0, all checks passed, 382 nodes at 100% sync, height 2390 (854 blocks in 29.94 h, mean interval 2.1 min), lowest free RAM about
160 GB, 1,102 stem txs, 0.212 fluff per hop, loop rate 0.049.

**Reading.** Light-node outbound share **0.1655**, **1.08x** the subnet model's 0.1531 (the 13 h cells: P26 0.1577 = 1.03x, P28 0.1557 = 1.01x;
the stock rule at 24 h: E32 0.3354 = 2.19x, E34 0.3524), by quarter 0.1682, 0.1668, 0.1642, 0.1630 (falling 3.2% across the window). By class:
relays **0.1635** (1.07x), users **0.1787** (1.17x; P26 0.165, P28 0.139; E32 0.127), observers 0.1576, medium 0.1686, miners 0.152, seeds 0.0832.
Relays by start-order quarter over hours 26-30: 0.1586, 0.1458, 0.1735, 0.1741, the latest 1.10x the earliest and 19% between the highest and
lowest quarter, in no start-order sequence (the second quarter is the lowest). Over the whole run the relays' share reads 0.36 in the first half
hour and 0.18 by hour 2 (means 0.245 over hours 0-3, 0.186 over 3-6), then 0.165 over hours 6-12, 0.151 over 12-18, 0.158 over 18-24 and 0.163
over 26-30; the highest half hour from hour 6 on is 0.1743 (hour 6.5) and the lowest 0.1452 (hour 15): the share reaches the ceiling by hour 6
and wanders within 8% of it for the next 24 hours with no trend, where the stock rule sat at 2.2x (E32) or rose 5% (E34). Exposure: `sp_r`
recall **0.187** [0.14, 0.23], precision 1.00, **31 of 40** twenty-transaction users attributed (combined estimator 31 of 40, 2 of 4 and 1 of 1 busy
senders); the stock 24 h cells read 33 of 40 at recall 0.134 (E32) and 29 of 40 at 0.109 (E34), the 13 h cap-lifted cells 37 and 35 at 0.173 and
0.154. Stem-peer spy share: users' median 0.157 and every user had a spy stem peer in the window; reachable nodes 0.149. Outbound-peer spy share:
users 0.176, reachable 0.158.

**P29: four of five lettered clauses hit, and the wall.** (a) 0.1655 in 0.145-0.170 (hit, near the top); (b) relays 1.07x and the gradient 1.10x
(hit); (c) both lines in all 382 logs (hit); (d) users 0.1787 in 0.12-0.19 and 31 of 40 exposed against at least 30 (hit, both at the edge); (e) no
half hour from hour 6 on above 0.19 (highest 0.1743; hit) but the four quarters span 3.2% against "within 3%" (0.1682 to 0.1630; missed by 0.2
points, and the drift, such as it is, is downward). Wall 3 h 18 m under 3.5 h. **Nothing accumulates in the lists over a day once every /24 is
drawable**: the 24 h read sits 5% above the 13 h reads, inside the family's 5% seed band at this warmup (E32 against E34), so 1.0-1.1x the ceiling
is the cap-lifted fleet's number at both warmups and two seeds, against 2.2x under the stock rule. On the senders' side the picture sharpens: the
users read their highest cap-lifted share (0.179) and the attribution recall is 0.187, 1.4-1.7x the stock 24 h cells' 0.134 and 0.109, while the
count of exposed heavy users (31) sits between the stock cells' 33 and 29. The count saturates for twenty-transaction senders (each has twenty
chances); recall is the metric that moves, and it moves against the senders when the cap goes. This is the sender-side cost in open question 10 (e),
now measured at 24 h.

**Register.** `20261025_003506_lean_24_none_h300_k42_w24h_m1_n600_fx_up_wc0_s12345`, box `zenith2alpha` (run 77); estimators and
`spy_share_vs_time.txt` in the run's folder; events in `logs/queue_events_tr_through_20261024.events`. The archive moved to the array at 04:15
(2,624 regular files both sides, dry-run clean, the `/fast` copy deleted). P31 (E29's half list with the cap lifted) started 03:55 on the same
box as this run ended; P30 (P26 at a third seed) has run on `simbox3` since 03:25.

### E40. The half ban list with the cap lifted: 0.0771, 0.49x the no-list cell and 1.01x the half-list model; adopters at zero and the non-adopters at exactly their ceiling, where the stock rule charged them 10% (2026-10-25 03:55-06:15, `zenith2alpha`)

**Cell.** `lean_24_half_h300_k42_w13h_m1_n600_up_wc0_s12345` (P31): E29's cell, the spread fleet (42 spies in 42 /24s, 300 honest reachable in
242 /24s, 40 users) with the full 42-entry ban list on half the honest nodes (117 of the 233 relays, 20 of the 40 users, 24 of the 48 medium nodes
and 4 of the 8 observers: 165 adopters, 175 non-adopters, the same seeded half as E25 and E29; the 42-line list byte-identical to E29's), stock `24`
dedup, 13 h warmup, window 15-19 h, seed 12345, plus `sim-uniform-whitelist-pick: true` and `sim-whitelist-candidates: 0`. Eleven-patch binary
(sha `8d8255edb4ea`), both flag lines in all 382 daemon logs. Wall 2 h 18 m, exit 0, all checks passed, 382 nodes at 100% sync, height 2069
(533 blocks in 18.95 h), lowest free RAM about 161 GB, 1,097 stem txs, 0.200 fluff per hop, loop rate 0.056.

**Reading.** Light-node outbound share **0.0771** (the same list under the stock rule, E29: 0.184; no list with the cap lifted, P26: 0.1577, so
**0.49x** the no-list cell against E29's 0.55x), by quarter 0.0804, 0.0769, 0.0748, 0.0768 (a 7.5% span, no trend after the first quarter). The
half-list model, adopters at zero and non-adopters at the subnet ceiling, gives the light nodes 0.1531 x 140/281 = 0.0763; the read is **1.01x**
that. Adopters (165 nodes) **0.0000** out and 0.0000 in. The scorer's non-adopter group (175 nodes, slot-weighted, with the five miners' 500 slots
at 0.1488) **0.1539 = 1.005x the ceiling**; the non-adopting light nodes together 0.0771 x 281/140 = 0.1547, 0.98x what they carried with no list
(P26 0.1577; E29 under the stock rule: +10%). By class, with the adopters' zeros scaled out: relays 0.0766, so the 116 non-adopting relays' own
share 0.1539 (1.005x the ceiling; P26 0.1562); users 0.0772, so the 20 non-adopting users 0.1544 (P26 0.1647); medium 0.081 (0.162 own); observers
0.0919 (0.184 own, four nodes); miners 0.1488 (no adopters; P26 0.175); seeds 0.1052. Relays by start-order quarter over hours 15-19: 0.0849,
0.0752, 0.0716, 0.0755, the latest 0.89x the earliest; the quarters mix adopters at zero with non-adopters, so they read the adopter fraction of
each quarter as much as any list effect, and the start-order reading is not clean in a `half` cell. Over the whole run the relays' share reads
0.176 in the first half hour and 0.098 by hour 2 (means 0.127 over hours 0-3, 0.099 over 3-6, 0.082 over 6-12, 0.083 over 12-15, 0.077 over
15-19): a 7% ease from hours 6-12 to the window, where P26 was flat from hour 6. Exposure: `sp_r` recall **0.069** [0.04, 0.10] (P26 0.173),
precision 1.00, **15 of 40** twenty-transaction users attributed (E29 15, P26 37); 20 of the 40 users never had a spy stem peer in the window,
which are the 20 adopters, so the 15 exposed are 15 of the 20 non-adopting users (E29 also 15 of 20; P26 37 of 40). Adopters' txs are never
stemmed straight to a spy, so the recall over all user txs is half the non-adopting users' own rate, 0.138 against P26's 0.173 (0.80x). Busy
senders: `sp_r` 0 of 5, combined 3 of 5. Stem-peer spy share: non-adopting users' median 0.157... (the 40-user median 0.02 straddles the two
halves); 49% of reachable nodes ever had a spy stem peer (the non-adopting share of them is 52%).
*Correction, 2026-10-25 06:55:* the stem-peer sentence above carries a number that was not computed. The scorer gives the 40 users' median
stem-peer spy share as 0.02 and their median outbound spy share as 0.03, both medians falling between the adopting half at zero and the
non-adopting half; no per-half median was computed, and "0.157..." should be read as struck.

**P31: four of five lettered clauses hit, and the wall.** (a) 0.0771 in 0.070-0.100 (hit); (b) adopters 0.0000, the non-adopting relays' own share
1.005x the ceiling in 0.92-1.24x, the relays' class share 0.0766 in 0.070-0.095 (hit); (c) both lines in all 382 logs (hit); (d) users 0.0772 in
0.06-0.10 and 15 of 40 exposed in 14-20, all among the non-adopters (hit); (e) the latest-started relay quarter 0.89x the earliest (hit) but the four
quarters span 7.5% against "within 3%" (0.0804 to 0.0748; missed: at a share of 0.08 a half hour carries about 230 spy slots and the quarter-to-quarter
noise is 4-5%, so a 3% clause copied from the 0.16 cells was too tight for this level; later flatness clauses should scale with the share). Wall 2 h
18 m under 3 h. **The list's benefit survives the cap's removal, and the non-adopters' penalty does not.** Under the stock rule the half list took
the spread fleet from 0.3369 to 0.184 (0.55x) and the non-adopters carried 10% more than without it; with every /24 drawable the same list takes
the fleet from 0.1577 to 0.0771 (0.49x), the adopters read zero and the non-adopters read their subnet share and nothing more (1.005x; 0.98x their
no-list read). The list removes the adopters' half of the spies' slots and moves none of it onto the non-adopters, and the subnet model's half-list
number is read to 1%. For the senders: adopting users are untouched (no spy stem peer at all in the window), non-adopting users are exposed at the
same 15 of 20 as under the stock rule, and the recall over all user txs is 0.069 (P26 0.173). Open question 10 (e) now has both halves: the stock
rule's cap gives the spies 2.2x on the relays and holds the users at 0.75x; lifting it puts both at 1.0x, and the list then does exactly its half.

**Register.** `20261025_035537_lean_24_half_h300_k42_w13h_m1_n600_up_wc0_s12345`, box `zenith2alpha` (run 78); estimators and
`spy_share_vs_time.txt` in the run's folder; events in `logs/queue_events_tr_through_20261024.events` (through the 06:15 `QUEUE EMPTY`). The archive
moved to the array at 06:45 (2,624 regular files both sides, dry-run clean, the `/fast` copy deleted). The Threadripper's queue is empty; P30 (P26
at a third seed) still runs on `simbox3`.

### E41. P26 at a third seed, on simbox3's rebuilt binary: 0.1482, 0.97x the ceiling and flat to 0.3%; three seeds give 1.005x with a 6% spread, the users at 0.99x with 35-39 of 40 exposed (2026-10-25 03:25-07:56, `simbox3`)

**Cell.** `lean_24_none_h300_k42_w13h_m1_n600_up_wc0_s34567` (P30): P28's cell with `simulation_seed: 34567`, the only differing line; the first
cell on `simbox3`'s eleven-patch binary (sha `14852a861c75`, built 00:46 with `run_install_sim.sh`; provenance equal to zenith2alpha's apart from
the binary's sha and `built:`, the eleven patch hashes the same), both flag lines in all 382 daemon logs. Wall 4 h 27 m (the box's 40 vCPUs against
zenith2alpha's 2 h 15-31 m), exit 0, all checks passed, 382 nodes at 100% sync, height 2062 (526 blocks in 18.87 h), lowest free RAM 81 GB,
1,088 stem txs, 0.192 fluff per hop, loop rate 0.054.

**Reading.** Light-node outbound share **0.1482**, **0.97x** this seed's ceiling 0.1523 (243 honest /24s; P26 1.03x, P28 1.01x), by quarter
0.1481, 0.1485, 0.1480, 0.1483 (a 0.3% span, the flattest window in the family). By class: relays **0.147** (0.965x), users **0.1521** (1.00x;
P26 0.165, P28 0.139), observers 0.1648, medium 0.1385, miners 0.1808, seeds 0.0911. Relays by start-order quarter over hours 15-19: 0.1428,
0.1494, 0.1428, 0.1539, the latest 1.08x the earliest and 8% between the highest and lowest, in no order. Over the whole run the relays' share
reads 0.355 in the first half hour and 0.19 by hour 2 (means 0.248 over hours 0-3, 0.188 over 3-6, 0.156 over 6-12, 0.146 over 12-15, 0.147
over 15-19): at the ceiling from hour 6, as P26 and P29. Exposure: `sp_r` recall **0.146** [0.11, 0.18], precision 1.00, **39 of 40** users
attributed (38 of the 39 twenty-transaction users and the one user with 10-19 txs; P26 37, P28 35); every user had a spy stem peer in the window.
Stem-peer spy share: users' median 0.135, reachable nodes 0.13; outbound-peer spy share 0.148 and 0.14.

**P30: five of five clauses hit, and the wall.** (a) 0.1482 in 0.145-0.170 (hit, at the low edge); (b) relays 0.965x and the gradient 1.08x (hit);
(c) both lines in all 382 logs (hit); (d) users 0.1521 in 0.12-0.19 and 39 of 40 exposed (hit); (e) the three-seed mean 0.1539 in 0.150-0.165 and
the spread 0.0095 against "at most 0.010" (hit, at the edge). Wall 4 h 27 m under 6 h. The rebuilt binary passes its gate: a cap-lifted cell on
`simbox3` reads what zenith2alpha's read at two other seeds. **Three seeds, two boxes, one number:** with the 20-candidate cap lifted and the
draw uniform the spread fleet reads its subnet share, 0.1577, 0.1557 and 0.1482 against ceilings of 0.1531, 0.1539 and 0.1523 (1.03x, 1.01x,
0.97x; mean **1.005x**, the seeds spread 6% of the mean), against 2.20x and 2.17x under the stock rule at the first two seeds (E27, E27b), and
0.1655 (1.08x) at a 24 h warmup (E39). The third seed is the lowest and the flattest. The users' side closes with it: 0.165, 0.139 and 0.152,
mean 0.152 = **0.99x** the ceiling, with 37, 35 and 39 of 40 exposed and recall 0.173, 0.154 and 0.146, against 0.75x and 26-28 of 40 under the
stock rule (E38).

**Register.** `20261025_032553_lean_24_none_h300_k42_w13h_m1_n600_up_wc0_s34567`, box `simbox3` (run 79); estimators and `spy_share_vs_time.txt`
in the run's folder; events in `logs/queue_events_simbox3_through_20261025.events`. The archive moved to the array over ssh at 08:30 (2,624 regular
files both sides, dry-run clean, the local copy deleted; `simbox3` 91 GB free). Both boxes are idle with nothing queued.

### E42. The half list with the cap lifted at a second seed: 0.0764, 1.00x the half-list model and 0.49x the no-list cell again; two seeds, one number (2026-10-25 10:22-12:43, `zenith2alpha`)

**Cell.** `lean_24_half_h300_k42_w13h_m1_n600_up_wc0_s23456` (P32): P31's cell with `simulation_seed: 23456`, the only differing line (the 42-line
list and the 165-node adopter set identical, checked at generation); eleven-patch binary (sha `8d8255edb4ea`; the twelve-patch build installed at
10:29, seven minutes into this run, which kept the old inode), both flag lines in all 382 daemon logs and the twelfth patch's line in none. Wall
2 h 19 m, exit 0, all checks passed, 382 nodes at 100% sync, height 2065 (529 blocks in 18.80 h), lowest free RAM about 161 GB, 1,097 stem txs,
0.189 fluff per hop.

**Reading.** Light-node outbound share **0.0764** (P31 0.0771), by quarter 0.0775, 0.0760, 0.0759, 0.0762 (a 2.1% span). The half-list model at
this seed, 0.1539 x 140/281 = 0.0767: **1.00x**. Against the cap-lifted no-list cell at this seed (P28 0.1557): **0.49x** (P31 against P26: 0.49x;
E29 under the stock rule: 0.55x). Adopters (165 nodes) **0.0000**; the scorer's non-adopter group (175 nodes, slot-weighted with the miners)
**0.1554 = 1.01x the ceiling**; the non-adopting light nodes together 0.0764 x 281/140 = 0.1533, 0.98x their no-list read (P28 0.1557). By class
with the adopters' zeros scaled out: relays 0.0773 (the 116 non-adopting relays 0.1553, 1.01x the ceiling), users 0.0728 (the 20 non-adopting users
0.1456; P28 0.1391), medium 0.0801, observers 0.066, miners 0.1673, seeds 0.098. Relays by start-order quarter over hours 15-19: 0.0752, 0.0777,
0.0756, 0.0769, the latest 1.02x the earliest. Over the run: 0.169 in the first half hour, 0.091 by hour 2, means 0.122 over hours 0-3, 0.096
over 3-6, 0.088 over 6-12, 0.080 over 12-15, 0.076 over 15-19 (P31: 0.082, 0.083, 0.077): the same slow ease into the window. Exposure: `sp_r`
recall **0.066** [0.04, 0.10] (P31 0.069; P28 with no list 0.154), precision 1.00, **17 of 40** users attributed (P31 15; P28 35); 19 of the 40
users ever had a spy stem peer in the window, all non-adopters (the 20 adopters none), so 17 of the 20 non-adopting users are exposed (P31 15 of
20). Busy senders: `sp_r` 0 of 5, combined 4 of 5.

**P32: five of five clauses hit, and the wall.** (a) 0.0764 in 0.070-0.095 (hit); (b) adopters 0.0000 and the non-adopting relays 1.01x in
0.92-1.10x (hit); (c) both lines in all 382 logs (hit); (d) users 0.0728 in 0.06-0.10 and 17 of 40 exposed in 12-20, all non-adopters (hit); (e) the
quarters span 2.1% against 8% and the start-order quarter 1.02x in 0.7-1.3x (hit). Wall 2 h 19 m under 3 h. **Two seeds, one number:** with every
/24 drawable, the full ban list on half the nodes reads the half-list model to 1% at both seeds (0.0771 against 0.0763, 0.0764 against 0.0767),
0.49x the no-list cell at both, with the adopters at zero and the non-adopters at 1.005x and 1.01x their subnet share. The stock rule's 0.55x
with the non-adopters' +10% (E29) was the cap's doing, like the relays' 2.2x. P33, the third seed, runs on `simbox3`.

**Register.** `20261025_102213_lean_24_half_h300_k42_w13h_m1_n600_up_wc0_s23456`, box `zenith2alpha` (run 80); estimators and
`spy_share_vs_time.txt` in the run's folder; events in `logs/queue_events_tr_through_20261024.events`. The archive moved to the array at 12:50
(2,624 regular files both sides, dry-run clean with P34's live run excluded, the `/fast` copy deleted). P34 (the twelfth patch, seed 12345) started
12:43 on the same box as this run ended.

### E43. The twelfth patch: 20 random /24 candidates with the stock cubic draw read 0.1657, 1.08x the ceiling, the same as the lifted cap with the same draw; a bounded random sample is worth what lifting the cap is worth (2026-10-25 12:43-15:01, `zenith2alpha`)

**Cell.** `lean_24_none_h300_k42_w13h_m1_n600_rc_s12345` (P34): E27's stock spread-fleet cell plus `sim-random-whitelist-candidates: true`, the only
differing line; the stock cap of 20 candidates and the stock cubic draw kept. Twelve-patch binary (sha `7534279c`); the twelfth patch's start-up
line in all 382 daemon logs, the uniform-pick and candidates-0 lines in none. Wall 2 h 16 m, exit 0, all checks passed, 382 nodes at 100% sync,
height 2069 (533 blocks in 18.93 h), lowest free RAM 156 GB, 1,095 stem txs, 0.196 fluff per hop.

**Reading.** Light-node outbound share **0.1657**, **1.08x** the 0.1531 ceiling (stock, E27: 0.3369 = 2.20x; the cap lifted with the cubic draw,
P27: 0.1705 = 1.11x; the cap lifted with the uniform draw, P26: 0.1577 = 1.03x), by quarter 0.1695, 0.1670, 0.1636, 0.1628 (a 4.1% span, easing).
By class: relays **0.166** (1.08x), users **0.1623** (1.06x; P27 0.1406, P26 0.165), observers 0.1713, medium 0.1547, miners 0.1654, seeds 0.1137.
Relays by start-order quarter over hours 15-19: 0.1481, 0.1493, 0.1731, 0.1900, the latest **1.28x** the earliest and monotone from the second
quarter on: P27's residual gradient exactly (1.28x), where the uniform-draw cells have none (1.02-1.10x). The cubic draw's preference for the
newest of the 20 leaves it, whichever 20 they are. Over the run: 0.365 in the first half hour, 0.17 by hour 2, means 0.244 over hours 0-3, 0.225
over 3-6, 0.182 over 6-12, 0.168 over 12-15, 0.165 over 15-19, a slower settle than the uniform-draw cells (at the ceiling by hour 6) and still
easing 2% into the window. Exposure: `sp_r` recall **0.135** [0.10, 0.17], precision 1.00, **31 of 40** users attributed (P27 28, P26 37; stock
27-28); 97.5% of users had a spy stem peer in the window, all had a spy outbound peer; stem-peer medians 0.16 for users and reachable nodes alike,
outbound 0.172 and 0.163.

**P34: six of six clauses hit, and the wall.** (a) 0.1657 in 0.160-0.210 (hit); (b) relays 1.08x in 1.0-1.45x and the gradient 1.28x under 1.4x
(hit); (c) the twelfth line in all 382 logs and the other two in none (hit); (d) users 0.1623 in 0.10-0.19 and 31 of 40 exposed in 28-38 (hit);
(e) the quarters 4.1% apart under 5% (hit); (f) within 0.005 of P27's 0.1705 against 0.025 (hit). Wall 2 h 16 m under 3 h. **A bounded random
sample is worth exactly what lifting the cap is worth with the same draw**: 1.08x against 1.11x, the same residual gradient, the same users'
share within the seed band. So a defense can keep a bounded candidate set; what stays above the ceiling (8-11%) is the cubic draw's recency
preference, which the uniform draw removes (P26/P28/P30, 1.005x) and which an adversary that keeps itself newest could exploit (plan section 7,
threat 3). The Monte Carlo's 1.53x was wrong for the reason E37 gave for its 1.51x: its lists come from the stock regime and overstate the spies'
recency edge once the rule changes; the model is retired for predicting changed rules. The completion of this line, the random sample with the
uniform draw (`_rc_up`), is deferred behind the review's items 1-3 (plan section 7). P35, this cell at seed 23456, is queued on `simbox3`.

**Register.** `20261025_124316_lean_24_none_h300_k42_w13h_m1_n600_rc_s12345`, box `zenith2alpha` (run 81); estimators and `spy_share_vs_time.txt`
in the run's folder; events in `logs/queue_events_tr_through_20261024.events` (through the 15:01 `QUEUE EMPTY`). The archive moved to the array at
15:10 (2,624 regular files both sides, dry-run clean, the `/fast` copy deleted). The Threadripper rebuilt with the thirteenth patch at 15:09.

### E44. The half list with the cap lifted at a third seed, on simbox3: 0.0792, 1.04x the half-list model and 0.53x the no-list cell; three seeds read the model at 1.00-1.04x (2026-10-25 10:37-15:16, `simbox3`)

**Cell.** `lean_24_half_h300_k42_w13h_m1_n600_up_wc0_s34567` (P33): P31's cell with `simulation_seed: 34567`, the 165 ban-list paths rewritten
for simbox3's account (md5 `0252e259` as generated, `e3407251` as run), the 42-line list and the adopter set identical; the first cell on
simbox3's twelve-patch binary (sha `7a7a32b3`) with the twelfth flag off: its line in no log, the two cap-lifted lines in all 382. Wall 4 h 35 m,
exit 0, all checks passed, 382 nodes at 100% sync, height 2088 (552 blocks in 18.87 h), lowest free RAM 81 GB, 1,087 stem txs, 0.204 fluff
per hop.

**Reading.** Light-node outbound share **0.0792**, by quarter 0.0791, 0.0774, 0.0809, 0.0795 (a 4.5% span). The half-list model at this seed,
0.1523 x 140/281 = 0.0759: **1.04x** (P31 1.01x, P32 1.00x). Against the cap-lifted no-list cell at this seed (P30 0.1482): **0.53x** (P31 and
P32 0.49x). Adopters (165 nodes) **0.0000**; the scorer's non-adopter group **0.1575 = 1.03x the ceiling**; the non-adopting light nodes together
0.0792 x 281/140 = 0.159, 1.07x their no-list read (P30 0.1482, the lowest of the three no-list seeds). By class with the adopters' zeros scaled
out: relays 0.0795 (the 116 non-adopting relays 0.1597, 1.05x), users 0.0723 (the 20 non-adopting users 0.1446; P30 0.1521), medium 0.0782,
observers 0.1066, miners 0.1649, seeds 0.0807. Relays by start-order quarter over hours 15-19: 0.0842, 0.0758, 0.0807, 0.0784, the latest 0.93x
the earliest. Over the run: means 0.132 over hours 0-3, 0.090 over 3-6, 0.075 over 6-12, 0.077 over 12-15, 0.080 over 15-19, flat from hour 6
(P31 and P32 eased 7% into the window). Exposure: `sp_r` recall **0.071** [0.04, 0.11] (P31 0.069, P32 0.066), precision 1.00, **17 of 40**
users attributed (17 of the 39 twenty-transaction users, 0 of the one with 10-19); 20 of the 40 users ever had a spy stem peer, the
non-adopters, so 17 of the 20 non-adopting users are exposed (P31 15, P32 17). Busy senders: `sp_r` 0 of 5, combined 5 of 5.

**P33: five of five clauses hit, and the wall.** (a) 0.0792 in 0.070-0.095 (hit); (b) adopters 0.0000 and the non-adopting relays 1.05x in
0.92-1.10x (hit); (c) both flag lines in all 382 logs and the twelfth in none (hit); (d) users 0.0723 in 0.06-0.10 and 17 of 40 exposed in
12-20, all non-adopters (hit); (e) the quarters 4.5% apart under 8% and the start-order quarter 0.93x in 0.7-1.3x (hit). Wall 4 h 35 m under
6 h. **Three seeds, two boxes:** the full list on half the nodes with every /24 drawable reads 0.0771, 0.0764 and 0.0792 against half-list
models of 0.0763, 0.0767 and 0.0759 (1.01x, 1.00x, 1.04x; mean 1.02x), 0.49x, 0.49x and 0.53x the no-list cell at the same seed, with the
adopters at zero and the non-adopters at 1.005x, 1.01x and 1.03x their subnet share every time. The half-list line is closed at three seeds,
and the twelve-patch build passes its flag-off check (this cell reads like P31 and P32).

**Register.** `20261025_103748_lean_24_half_h300_k42_w13h_m1_n600_up_wc0_s34567`, box `simbox3` (run 82); estimators and
`spy_share_vs_time.txt` in the run's folder; events in `logs/queue_events_simbox3_through_20261025.events`. The archive moved to the array
over ssh at 20:41 (2,624 regular files both sides, dry-run clean, the local copy deleted). P35 (the twelfth patch at seed 23456) started
15:16 on the same box as this run ended.

### E45. The stock rule with the white list trimmed to its 70 newest entries reads 0.1616, 1.06x the ceiling: the trim alone removes the 2.2x, because a recency-trimmed list holds the spies below their pool share (2026-10-25 15:16-17:36, `zenith2alpha`)

**Cell.** `lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_s12345` (P36): E27's stock spread-fleet cell plus `sim-white-peerlist-limit: 70` (the
thirteenth patch; mainnet's 1,000 entries of ~4,600 reachable, 0.22, scaled to the lab's 342) and `--probe 3` (twelve relays, three at the head
and three at the tail of each start order, dumping their white and gray lists every 30 s and logging `net.p2p` at DEBUG; the eight observers dump
too), the only differences; thirteen-patch binary (sha `ab6646d7`), the thirteenth patch's start-up line in all 382 daemon logs. Wall 2 h 18 m,
exit 0, all checks passed, 382 nodes at 100% sync, height 2071 (535 blocks in 18.92 h), lowest free RAM 158 GB, 1,099 stem txs, 0.198 fluff per
hop.

**Reading.** Light-node outbound share **0.1616**, **1.06x** the 0.1531 ceiling, against E27's untrimmed **0.3369 = 2.20x** with the same rule, the
same seed and the same fleet; by quarter 0.1654, 0.1632, 0.1589, 0.1594 (a 4.1% span). By class: relays **0.1666** (1.09x; E27 0.3746), users
**0.1362** (0.89x; E27 0.133), observers 0.1423, medium 0.1075, miners 0.2046, seeds 0.0493. Relays by start-order quarter over hours 15-19:
0.1732, 0.1463, 0.1573, 0.1814, the latest 1.05x the earliest and in no order: the stock family's gradient (earliest about 1.5x, latest about 3.5x)
is gone. Over the run: means 0.248 over hours 0-3, 0.161 over 3-6, 0.165 over 6-12, 0.168 over 12-15, 0.165 over 15-19: at the ceiling by hour
3 and flat. **The lists** (four probe relays, every dump after hour 1): the white list holds exactly 70 entries in every dump (67-68 /24s), the
spies are **8.5-10.7%** of its entries against their 12.3% of the pool's IPs (42 of 342) and 14.8% of its /24s, and their mean rank percentile
by `last_seen` is 0.38-0.49 (E21's untrimmed lists: 0.39); the gray lists hold about 266 entries with the spies at 12.7-13.3%, their pool share.
Exposure: `sp_r` recall **0.135** [0.10, 0.17] (the cap-lifted untrimmed cells 0.146-0.173, the stock 24 h cells 0.134 and 0.109), precision
1.00, **30 of 40** users attributed (E27 27); 92.5% of users had a spy stem peer in the window; stem-peer median 0.118, outbound 0.143.

**P36: three of five clauses hit, and the wall.** (a) 0.1616 against 0.28-0.50 (missed, far below); (b) 0.48x E27 against "at least 0.9x"
(missed); (c) the lists at most 70 entries in every dump after hour 1 and the spies' rank below 0.5 (hit); (d) the thirteenth line in all 382
logs (hit); (e) users 0.1362 in 0.08-0.16 and 30 of 40 exposed in 22-34 (hit). Wall 2 h 18 m under 3 h. The prediction read the trim as "drop
honest entries first, keep the spies, keep the multiplier"; the opposite happened. **The mechanism, from the dumps:** a white-list entry's
`last_seen` is refreshed by a connection in either direction. An honest relay is refreshed in a peer's list when the peer dials it and when it
dials the peer; a spy, which never dials, is refreshed only through the peer's own spy outbound slots, two or so of twelve. A list trimmed to its
70 newest entries therefore holds the peers the node has connected with recently, on both sides, and the spies are a smaller share of those
than of the pool. The untrimmed list holds hundreds of gossip-learned honest entries the node never connects to and never refreshes, and
against those the spies look new (rank 0.39); the 20-newest cap then over-draws them. **The 2.2x is a property of a white list that holds far
more peers than the node ever connects to.** Trimmed to a fifth of the pool by recency, the stock pick draws the spies at their share with no
change to the rule. For transfer: mainnet's lists are trimmed (1,000 of ~4,600 reachable), and a mainnet relay takes 60-90 inbound connections,
so its list should look like P36's, not E27's, unless gossip keeps re-inserting fresh spy entries; the dump (open question 8) decides, and the
sweep at 140 and 35 entries (P40, P41) locates the threshold in the lab.

**Register.** `20261025_151639_lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_s12345`, box `zenith2alpha` (run 83); estimators and
`spy_share_vs_time.txt` in the run's folder; events in `logs/queue_events_tr_through_20261024.events`. The archive moved to the array at 20:50
(2,636 regular files both sides with the probe dumps, dry-run clean, the `/fast` copy deleted). P37 started 17:36 on the same box as this run ended.

### E46. The cap lifted with the white list trimmed: 0.1619, the same 1.06x as the stock rule with the trim; the candidate-set fix is a no-op once the list is trimmed (2026-10-25 17:36-19:56, `zenith2alpha`)

**Cell.** `lean_24_none_h300_k42_w13h_p3_m1_n600_up_wl70_wc0_s12345` (P37): P26's cell (the cap lifted, the uniform draw) plus the same limit
and probes as P36; against P36 the two flag lines are the only difference. Thirteen-patch binary; all three `--sim-*` lines in all 382 logs. Wall
2 h 17 m, exit 0, all checks passed, 382 nodes at 100% sync, height 2077 (541 blocks in 18.90 h), lowest free RAM 156 GB, 1,097 stem txs, 0.179
fluff per hop.

**Reading.** Light-node outbound share **0.1619** (P36 0.1616; P26 untrimmed 0.1577), **1.06x** the ceiling; **P37/P36 = 1.00** against the
untrimmed pair's 0.47 (P26/E27). By quarter 0.1635, 0.1634, 0.1619, 0.1588 (3.0%). By class: relays 0.1644, users 0.1491 (P36 0.1362),
observers 0.1493, medium 0.1014, miners 0.2435, seeds 0.0177. Relays by start-order quarter: 0.1607, 0.1619, 0.1777, 0.1605, the latest 1.00x the
earliest. Over the run: 0.250 over hours 0-3, 0.167 over 3-6, then 0.165-0.167, flat. The lists: 70 entries in every dump, the spies 9.3-10.2%
of them at rank 0.35-0.44, the gray lists 266 entries at 13%. Exposure: recall **0.134** [0.10, 0.17], precision 1.00, **32 of 40** exposed; every
user had a spy stem peer; stem-peer median 0.136, outbound 0.148.

**P37: four of five clauses hit, and the wall.** (a) 0.1619 in 0.16-0.30 (hit, at the floor; the reading rule's "at or below 0.17, the fix
survives a trimmed list" holds); (b) relays and users within 25% (1.10x; hit); (c) the lists at most 70 entries (hit) but the spies' share of
the entries 0.093-0.102 against "above 0.15" (missed: below the pool's share, not above it); (d) the three lines in all 382 logs (hit); (e) the
quarters 3.0% apart (hit). Wall 2 h 17 m under 3 h. Read with E45: **with a recency-trimmed list the stock pick already draws the spies at
their share, so the candidate-set change has nothing left to fix** (1.06x and 1.06x). The 1.06x residual at both sits inside the cap-lifted
family's seed band (0.97-1.08x).

**Register.** `20261025_173648_lean_24_none_h300_k42_w13h_p3_m1_n600_up_wl70_wc0_s12345`, box `zenith2alpha` (run 84); estimators and
`spy_share_vs_time.txt` in the run's folder; events in `logs/queue_events_tr_through_20261024.events` (through the 19:56 `QUEUE EMPTY`). The
archive moved to the array at 20:50 (2,636 regular files both sides, dry-run clean, the `/fast` copy deleted). P38 (the turnover baseline)
started 20:42 on the same box.

### E47. The twelfth patch at a second seed: 0.1716, 1.12x; two seeds give 1.10x, the lifted cap's number with the same draw (2026-10-25 15:16-19:51, `simbox3`)

**Cell.** `lean_24_none_h300_k42_w13h_m1_n600_rc_s23456` (P35): P34's cell with `simulation_seed: 23456`, the only differing line; simbox3's
twelve-patch binary (sha `7a7a32b3`), the twelfth patch's line in all 382 logs and the other two in none. Wall 4 h 32 m, exit 0, all checks
passed, 382 nodes at 100% sync, height 2075 (539 blocks in 18.87 h), lowest free RAM 81 GB, 1,097 stem txs, 0.192 fluff per hop.

**Reading.** Light-node outbound share **0.1716**, **1.12x** this seed's ceiling 0.1539 (P34 at seed 12345: 0.1657 = 1.08x; the cap lifted with
the cubic draw, P27: 1.11x), by quarter 0.1676, 0.1711, 0.1725, 0.1750 (4.4%, rising). By class: relays **0.1784** (1.16x), users **0.1376**
(0.89x; P34 0.1623), observers 0.1466, medium 0.1679, miners 0.1756, seeds 0.1081. Relays by start-order quarter over hours 15-19: 0.1572,
0.1771, 0.1975, 0.1814, the latest 1.15x the earliest and 26% between the highest and lowest (P34: 1.28x, monotone): the cubic draw's residual
again. Over the run: 0.238 over hours 0-3, 0.215 over 3-6, 0.186 over 6-12, 0.173 over 12-15, 0.178 over 15-19, P34's slow settle. Exposure:
`sp_r` recall **0.152** [0.11, 0.20] (P34 0.135), precision 1.00, **32 of 40** exposed (P34 31); 92.5% of users had a spy stem peer; stem-peer
median 0.106, outbound 0.12.

**P35: six of six clauses hit, and the wall.** (a) 0.1716 in 0.160-0.210 (hit); (b) relays 1.16x in 1.0-1.45x and the gradient 1.15x under 1.4x
(hit); (c) the twelfth line in all 382 logs and the others in none (hit); (d) users 0.1376 in 0.10-0.19 and 32 of 40 exposed in 28-38 (hit); (e)
the quarters 4.4% apart under 5% (hit); (f) within 0.006 of P34 against 0.015 (hit). Wall 4 h 32 m under 6 h. **Two seeds, two boxes:** the
random sample of 20 with the cubic draw reads 1.08x and 1.12x (mean **1.10x**) with a residual start-order gradient of 1.28x and 1.15x, which is
the lifted cap with the cubic draw (P27: 1.11x, 1.28x). The twelfth patch's line is closed at two seeds: a bounded random sample is worth what
lifting the cap is worth, and both are worth nothing once the list is trimmed (E45, E46).

**Register.** `20261025_151635_lean_24_none_h300_k42_w13h_m1_n600_rc_s23456`, box `simbox3` (run 85); estimators and `spy_share_vs_time.txt`
in the run's folder; events in `logs/queue_events_simbox3_through_20261025.events` (through the 19:51 `QUEUE EMPTY`). The archive moved to the
array over ssh at 20:48 (2,624 regular files both sides, dry-run clean, the local copy deleted). simbox3 was rebuilt with the thirteen patches
at 20:42 (sha `c1a4e670`) and started P40 (the trim sweep at 140) at 20:46.

### E48. P38 as run: the turnover reached only the users; the relays read E27's stock number, and the run exited 1 at its end-of-run cleanup (2026-10-25 20:42-23:00, `zenith2alpha`)

**Cell.** `lean_24_none_h300_k42_w13h_p3_m1_n600_to1h1h_s12345` (P38, md5 `c7666148`): E27's stock spread-fleet cell plus `general.turnover`
(1 h online, 1 h offline, exponential, fraction 1.0) and the twelve probe relays; the thirteen-patch binary (sha `ab6646d7`), none of the
three rule flags in any of the 382 logs. **As run, only the 40 users cycled** (7-16 daemon sessions each, 412 in all). The generator keeps a
daemon with `hide-my-port: false` up as a pinned supernode (`is_pinned_reachable` in `src/agent/user_agents.rs`), and every reachable node in
the lean cells sets it; the generator's log said "40 node(s) cycle", which nobody read before the run. Wall 2 h 15 m. Shadow ran all 19 sim
hours and the run **exited 1**: 15 of the 40 user agents were still running at the end. Each got its cleanup signal at 68,280 s with its own
daemon offline (13 of the 15) or just restarted, so every wallet call blocked for its 180 s timeout and the cleanup overran the 120 s margin.
The window's data are complete: all 382 daemons logged to the end, nodes at height 1,993-1,995 at hour 19, lowest free RAM 157 GB, 575 stem
txs (E27 1,098), 0.207 fluff per hop. The generator now gives a cycling agent no end-of-run signal (`5115b02b`; its dry run on P42's cell has
all 40 user agents expected running).

**Reading.** Light-node share **0.3512**, 1.04x E27's 0.3369 and 2.29x the ceiling 0.1531, by quarter 0.3458, 0.3518, 0.3523, 0.3544. By
class: relays **0.3774** (E27 0.3746), users **0.1083** (E27 0.133), observers 0.2643, medium 0.2106, miners 0.2656, seeds 0.0662. Relays by
start-order quarter over hours 15-19: about 0.23, 0.33, 0.43, 0.52 (E27 0.22-0.25 and 0.50-0.54), the stock family's gradient unchanged; the
relay curve is flat at 0.37-0.38 from hour 9. With no relay churn the relays' lists are E27's, and the users' churn moves the relays by under
1%. Exposure: the users' daemons were up about half the time and sent half E27's transactions; `sp_r` recall **0.096** [0.06, 0.15] at
precision **0.82** (49 of 60 guesses correct; E27 0.126 at 1.000), 18 of the 36 sending users exposed (E27 27 of 40), the users' median
outbound spy share 0.097. The eleven wrong guesses are new; E27 had none, and they are not traced.

**Churn cost** (`churn_cost.py`'s first run on restarting daemons; `churn_cost.txt` in the run's folder). The users' sessions split at the
start-up banner into 412, the config's count: median time to 12 outbound peers **1.0 min** on the first session and **1.1 min** after a
restart (p90 4.3 min), 6 sessions never filled. The relays ran one session each: **1.7 min** median and 5.9 min p90 to 12 outbound (P36
without turnover: 2.3 and 6.0). Handshake failures 1.85 per relay-hour (P36 0.37); outbound connect failures zero, as no reachable peer ever
went offline. These are a no-relay-churn baseline, not the cost the cell was filed to measure.

**P38: two of four scorable clauses hit, and both are the parts the defect did not touch.** (a) exit 0: **missed** (exit 1, the cleanup);
height 1,900 by hour 19 hit (1,993). (b) light-node share 0.20-0.45: 0.3512, hit, but on a cell without relay churn, so the band's reasoning
(stale entries diluting the recency edge) is not tested. (c) each probe relay restarts at least three times: **missed** (no relay restarted).
(d) the cost scorer's baseline numbers: reported above, for users only. (e) wall under 4 h: hit (2 h 15 m). P42, queued 23:16, is the cell P38
meant.

**Register.** `20261025_204207_lean_24_none_h300_k42_w13h_p3_m1_n600_to1h1h_s12345`, box `zenith2alpha` (run 86); estimators,
`spy_share_vs_time.txt` and `churn_cost.{txt,json}` in the run's folder; events in `logs/queue_events_tr_through_20261024.events`. The
archive moved to the array at 23:18 (3,748 regular files both sides, dry-run clean, the `/fast` copy deleted). P39 (the same defect) was
stopped a minute in; its 251-file directory moved to the array as a record.

### E49. P40, the trim sweep's upper point: the stock rule at a 140-entry white list reads the ceiling, flat with the 70 point (2026-10-25 20:46 - 2026-10-26 01:23, `simbox3`)

`20261025_204615_lean_24_none_h300_k42_w13h_p3_m1_n600_wl140_s12345`, run 87 (exit 0, wall 274 m, 1,096 stem txs): light **0.1640** = **1.07x** the 0.1531 ceiling, window quarters 0.163-0.165. The sweep asked where between 70 entries (1.06x, E45) and unlimited (2.20x, E27) the multiplier returns; at 140 of 342 reachable (0.41 of the pool) it has not: **the stock-rule multiplier needs a white list that holds (nearly) every /24**, and mainnet's 0.22-of-pool lists sit in the flat region unless the dump (open question 8) says otherwise. The probes' white lists hold exactly the 140 limit after hour 1, the spies at 6.5-10.4% of entries (mean 8.8%, pool share 12.3%) at mean rank percentile 0.48, gray ~199 at 14.8% — the trim keeps the spies below their pool share, as at 70, as E45's mechanism reads (a `last_seen` trim keeps the recently connected; the spies are a minority of those). Sender side: sp precision 1.000 at recall 0.118 (ground truth 122/1,029 = 0.119), combined 0.120 at 0.932; 34 of 40 users exposed to sp_r at 20+ txs (35 of 40 to combined); p_stem medians 0.132 (unreachable) and 0.140 (reachable). P41 (35 entries, running) reads the sweep's far side under the filed reading rule (the limit at which the share leaves the ceiling, against mainnet's 0.22 of the pool).

### E50. P41, the trim sweep's lower point: at 35 entries the stock rule reads exactly the subnet share (2026-10-26 01:23-06:01, `simbox3`)

`20261026_012322_lean_24_none_h300_k42_w13h_p3_m1_n600_wl35_s12345`, run 89 (exit 0, wall 275 m, 1,097 stem txs): light **0.152 = 0.99x** the 0.1531 ceiling. The sweep closes: **35 entries 0.99x, 70 1.06x (E45), 140 1.07x (E49), unlimited 2.20x (E27)** — every capped reading is flat at the ceiling, so the multiplier's threshold sits between 0.41 of the pool and the whole network, and with mainnet's lists at 0.22 of the pool the lab's 2.2x does not transfer unless the dump (open question 8) shows mainnet's lists behaving otherwise. The dumps carry a negative control for the cap mechanism: with 35 entries and about 12 connected there is no newest-20 cut to exploit — every unconnected entry is a candidate — and the constant re-dialing keeps the spies' own entries the freshest in the lists (median age 60 s against the honest 146 s; spies 3.0 of 35 entries, 8.6% against the 12.3% pool share, rank 0.29), yet the share sits at the pool share: freshness buys nothing when nothing is cut. Sender side: sp precision 1.000 at recall 0.144 (combined 0.147 at 0.956); p_out medians 0.137-0.138.

### E51. P42, the relay-churn cell: hourly relay cycling raises the absolute exposure to 0.3936 and the honest cost stays small (2026-10-26 04:05-07:46, `zenith2alpha`)

`20261026_040527_lean_24_none_h300_k42_w13h_p3_m1_n600_tor1h1h_s12345`, run 91 (exit 0 — the `5115b02b` fix holds — wall 219 m, chain height 2,078, 584 stem txs): light **0.3936 = 1.64x** the online-/24 ceiling of about 0.24, inside its 0.25-0.55 clause, against the no-churn stock 0.3369 = 2.20x the whole-network ceiling. With half the honest reachable offline at any moment the spies' share of the online /24s roughly doubles, and the absolute exposure RISES (0.337 to 0.394) even as the multiplier falls: churn is not a defense against the spread fleet, it is a small amplifier. p_out medians: the reachable 0.424, the users 0.107. First precision below 1.0: sp 0.859 at recall 0.140 (combined 0.142 at 0.860) — restarts blur the stem attribution. The honest cost, `churn_cost`'s first run against real restarts (clause (c): the scorer's session counts equal the config exactly — relays 2,267 sessions over 233 nodes, mean 9.7 against the config's 9.7; mediums 10.0, observers 9.3, users 10.3; miners, seeds and spies one each): a restarted relay refills 12 outbound slots in **1.6 m median / 5.0 m p90** (cold start 1.9/6.0 — the surviving peer list helps), 32 of 2,267 sessions unfilled (1.4%), and 2.85 connect-failures plus 1.77 handshake-failures per relay-hour (back-ping failures 4.64, counted separately). Mediums refill in 1.6/5.0, observers 2.0/6.1, users 2.1/5.5. The churn assumption's stress case held: the network ran 19 sim-hours with hourly relay restarts and no liveness failure.

### E52. P43, the churn gate's second half: the cap lifted under churn reads 0.3237, and the recency filter buys nothing (2026-10-26 07:46-11:19, `zenith2alpha`)

`20261026_074618_lean_24_none_h300_k42_w13h_p3_m1_n600_up_tor1h1h_wc0_s12345`, run 92 (exit 0, wall 211 m, height 2,061, 586 stem txs): light **0.3237 = 1.35x** the online-/24 ceiling, above its 0.17-0.30 band; the stock rule under the same churn read 0.3936 (E51). The clause that gates the candidate rules, (c), **missed decisively in the other direction**: the lifted cap costs LESS than the stock rule at 1 h/1 h relay churn — 1.37 against 2.85 connect-failures per relay-hour (0.48x, where the clause asked for at least 1.5x), restart fill 1.7 m median against 1.6 m (1.06x, asked 1.2x), unfilled sessions 30 against 32. The newest-20 recency filter concentrates dials on the fresh — under churn, the always-fresh spies — and pays for it in failed attempts; drawing from the whole list is cheaper. (a) hit (height 2,061); (d) hit (211 m); two of four. Two further readings: the online-/24 ceiling UNDERCOUNTS under churn even for the uniform draw (always-on is an advantage the model ignores — every honest session end frees a slot the redraw gives disproportionately to whoever is reliably dialable, and the spies never cycle); and precision degrades with churn under this rule too (sp 0.932 at recall 0.339, against 1.000 without churn). The churn gate's answer for the plan review: **the honest-cost objection to the candidate rules is empty at this churn point** — neither new rule is costlier than stock, the lifted cap is cheaper, and what churn changes is the exposure scale (both rules read above their no-churn numbers), not the rule comparison. Deeper churn sweeps (2 h/2 h, 30 m/30 m) only if the recommendation is contested at other rates.

### E53. P44, the active adversary on the spread fleet: 0.9083 — the eclipse regime, 96.7% of user transactions attributed (2026-10-26 07:39-12:11, `simbox3`)

`20261026_073911_lean_24_none_h300_k42_w13h_p3_m1_n600_sr300_ud_s12345`, run 93 (exit 0, wall 271 m, 1,105 stem txs): light **0.9083 = 5.93x** the 0.1531 ceiling, far above the 0.40-0.75 clause — the saturation the clause's reading rule reserved: the capture is eclipse-shaped. **Combined recall 0.967 at precision 1.000 — 40 of 40 users exposed** — and the users' outbound-peer share reads a median of 1.0 (the reachable 0.958): the spies hold essentially the whole outbound mix. sp direct recall 0.468 (the passive cells read 0.118-0.144). The dumps carry the mechanism: monerod's `evict_host_from_peerlist` keeps ONE entry per host, so the port rotation replaces instead of accumulating — every honest node's white list is 341 entries = 299 honest (median age ~16.7 h, static) + 42 spy fronts (median age ~110 s, refreshed by the nodes' own connections to them), nothing evicted, no flooding; and the newest entry in EVERY list, relays, observers and users alike, is a spy front (freshest-spy rank 0.000). The newest-20 candidate cut is therefore all-spy under the stock rule — and would be under any rule that keeps a newest cut. The 0.75x user protection did not erode; it inverted (users' p_out median 1.0 against the passive stock's 0.75x-equivalent), through the gray-list route (gossip plus the users' own gray dials). Three of four: (a) missed above — the finding; (b) hit; (c) hit on all three dump checks; (d) hit (271 m). The defense question changes shape: the candidate set's survivor is the uniform draw (P46, filed below), and the trim is the adversary's amplifier (P47).

### E54. P45 replicates P44: the eclipse regime is seed-stable (2026-10-26 11:19-13:47, `zenith2alpha`)

`20261026_111953_lean_24_none_h300_k42_w13h_p3_m1_n600_sr300_ud_s23456`, run 94 (exit 0, wall 146 m — tr runs the agent-loaded cell at near twice simbox3's pace — 1,127 stem txs): light **0.9075** against P44's 0.9083, a 0.09% seed spread. Combined recall 0.969 at precision 0.997 (P44: 0.967/1.000), 40/40 users exposed, the users' p_out median 1.0, the reachable 0.908. The dumps replicate exactly: white 341-342 = 299 honest + 42 spy entries (40-41 fronts), front ages 114-122 s against the honest ~60,000 s, freshest-spy rank 0.000 in every list. The clause tally matches P44's — (a) missed above identically, (b) hit, (c) hit, (d) hit — and the replicate tolerance reads 0.0008 against its 0.05: no seed effect anywhere. The eclipse regime is a property of the adversary, not the seed.

### E55. P46, the uniform draw against the adversary: a third of the eclipse removed, the subnet share not held (2026-10-26 12:31-17:02, `simbox3`)

`20261026_123147_lean_24_none_h300_k42_w13h_p3_m1_n600_up_sr300_ud_wc0_s12345`, run 95 (exit 0, wall 269 m, 1,105 stem txs): light **0.5994 = 3.9x** the 0.1531 ceiling — above the 0.13-0.20 clause and above the 0.30 reading-rule threshold: **nothing in the candidate set survives the active adversary.** The draw does what it can: direct stem attribution returns to the passive level (sp recall 0.181 at precision 1.000, against the passive cells' 0.118-0.144; 28 of 40 users exposed, not 40 of 40) and the eclipse is cut by a third (0.9083 to 0.5994). What it cannot do is hold the subnet share, because the adversary's residual advantage is structural, not recency: the fronts accept and hold every connection while honest peers churn their own, so the outbound mixes accumulate spy slots under any draw (the users' p_out median 0.449, the reachable 0.615, at run end). The dumps read as P44's — 42 spy entries per node, fronts ~118 s, one entry per host — present and fresh everywhere; the draw simply stopped letting them monopolize the candidate cut. The recommendation reverts to the list defenses (the ban list line, E29/E40), and the implication for new defense work is that the responder-hold advantage — immortal connections — is what a fix must attack; no peer-selection rule in the candidate set does. Two of four: (a) missed above; (b) missed (combined 0.391 at 0.993 against the 0.25 clause); (c) hit; (d) hit.

### E56. P47, the trim against the adversary: 0.0248 — the trim is the defense, not the amplifier (2026-10-26 17:03-21:48, `simbox3`)

`20261026_170301_lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_sr300_ud_s12345`, run 96 (exit 0, wall 282 m, 1,109 stem txs): light **0.0248 = 0.16x** the ceiling — the clause said 0.80-0.95, and the truth is the opposite pole, stronger than any defense measured in this program: sp recall 0.003 at precision 1.000, combined 0.004, **1 of 40 users exposed** (the untrimmed adversary: 40 of 40 at 0.967), p_out medians 0.000-0.002. The mechanism (the dumps): a trimmed list forces the honest network into a fast refresh cycle — every entry ages out unless recently connected, so disconnects force redraws, redraws reconnect honest peers, and the honest entries' median age lands at 208-742 s against the fronts' rotation spread of 0-1800 s. The honest cycle outruns the rotation: 9-14 of the 42 fronts age past the horizon and are evicted outright (28-33 spy entries survive, against the clause's at least 40), and in the newest-20 candidate cut the honest entries outrank most fronts, so the draw keeps serving honest peers. The adversary's own inserts feed the flywheel: every front insert evicts an honest entry, forcing the honest redraw that refreshes the network. The reading rule's amplifier branch is dead — **the white-list trim is the surviving defense against the active adversary, and its strength is proportional to the adversary's rotation period**: the trim converts the adversary's dialing budget into the network's refresh rate. P48 (the same cell with a 60 s rotation) measures the arms race at its tightest. (a) missed far below; (b) missed below (the fronts evicted); (c) hit; (d) hit (282 m). Two of four — and both misses are the finding.

### E57. P48, the arms race at its tightest: a 30x faster rotation moves nothing — the trim's protection is absolute at this budget (2026-10-26 22:10-2026-10-27 00:36, `zenith2alpha`)

`20261026_221003_lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_sr300_ro60_ud_s12345`, run 97 (exit 0, wall 144 m, min_avail 59.7 GB — the fast rotation costs memory — 1,128 stem txs): light **0.0262** against P47's 0.0248. Rotating the front ports every 60 s, thirty times faster, changed the share by 6% — far below the 0.10 floor: **the trim wins outright at this dialing budget, not merely asymmetrically.** sp and combined recall 0.002 at precision 1.000, 1 of 40 users exposed, p_out medians 0.000-0.002. The dumps carry the why: a front entry's effective freshness at each honest node is bounded by the SWEEP cadence (300 s — the rate at which dials actually reach each node), not the rotation period; measured spy ages 314-888 s against honest 151-917 s; the newest-20 candidate cut held only 1-4 spies of 20 at run end; evictions continued (26-33 spy entries of 70). To beat the trim the adversary must out-refresh the honest cycle per node — sweep every node faster than about 150 s — a cost curve the lab has now measured at both ends. (a) missed below (the trim-wins branch of the reading rule); (b) missed below again; (c) hit; (d) hit (144 m). Two of four, both misses confirming the defense. **The OQ13 arc is complete**: five adversary cells and two rotation points — the trim is the defense, its strength prices the adversary's dialing budget, and at 42 spies against 342 reachable that budget does not exist.

### E58. N4 from the existing logs: the fluff epoch does not expose the originator — the channel is real, redundant, and undetectable (2026-10-27 11:55-12:25, `zenith2alpha`)

No new cell: `docs/spy_journal/adhoc/n4_fluff_epoch.py` over four archives on the array (E27/E28 passive at both seeds, E53 the untrimmed adversary, E56 the trimmed one; the jsons sit alongside; ~150x mainnet's sender rate, so this is the leak's ceiling). The plan's mechanism (20261018 section 2.3 point 4) is real: passively, **every own tx sent during the origin's fluff epoch was stemmed** (209/209 and 207/207) — in a fluff epoch a node stems only its own. But it buys the spy nothing new: with oracle-perfect mode knowledge the fluff-epoch attribution adds **zero transactions beyond the first-stem-hop exposure sp already reads — 0, 1, 0 and 0 beyond first-hop of ~1,000 txs per run** — because an origin's own stems are first-hop by definition; the channel is a subset of the measured one. The proposed detection (a peer that fluffs a tx "nobody else has fluffed yet" is in fluff mode) carries no information at relay density: the 630 s post-cue window sits in true fluff epochs **0.21-0.23 of the time against the 20 % stock prior** (45,776 cues; first fluffs are handed over by well-connected relays and miners — 24.5k and 13.6k of them — not by fluff originators), and the attack as specified reads **precision 0.065 / 0.047, ~700 false attributions against 49 / 33 correct**. Under the untrimmed adversary the fluff channel lights up — the sender itself fluffs first for **56 %** of txs (passive 0.2-0.3 %; stems that die inside the fleet leave the origin's own 39 s embargo the first timer) and the same cue attack reads 0.806 precision naming 40 of 40 users — but it is the stem eclipse in another hat: under the wl70 trim it collapses with the stems (**sender-first 8.9 %, precision 0.378, 1 of 40 users**). First fluffer, passively: a relay 76-85 %, a spy 15-23 %, the sender 0.2-0.3 %. (Under the adversary 7 of 224 fluff-epoch own txs went unstemmed — no stem peer under the eclipse — a leak of the same subset.) Verdict: **N4 closed, no monerod change needed** — the plan's mitigations (hold local txs to the next stem epoch; stem a share during fluff epochs) answer a leak that does not exist independent of stem exposure, and at mainnet rates it can only be smaller.

Re-derived 2026-10-28 (the five-day review, R6c): the cue-level first-fluffer counts now have a
committed script and outputs (`adhoc/n4_cue_fluffers.py`, `n4_cue_fluffers_e27.json`,
`n4_cue_fluffers_e28.json`) — e27 reads 24,490 relay and 13,643 miner cues of 45,776 (e28:
25,663 and 12,399 of 45,839): the quoted 24.5k / 13.6k stand.

### E59. P49, the sweep budget at its tightest setting: the trim holds at 0.0239 — and the lab's arms-race axis saturates an order of magnitude above mainnet's cut (2026-10-27 11:46-14:20, `zenith2alpha`)

`20261027_114619_lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_sr60_ud_s12345`, run 98 (exit 0, wall 152 m, min_avail 59.8 GB, 1,129 stem txs): light **0.0239 = 0.16x** the ceiling, against 0.0248 (E56, 300 s sweeps) and 0.0262 (E57, 300 s + 60 s rotation). sp recall 0.0047 at precision 1.000, combined 0.0103 at 0.846, **1 of 40 users exposed**. The dumps carry the real finding: **front entry ages 762-1,284 s (median 1,076 s) against the configured 60 s sweep** — the agent's dial pipeline through Shadow cannot deliver a per-target refresh faster than ~10-20 minutes, and at the 60 s setting it thrashes (E57's configured 300 s delivered a *faster* effective sweep, 314-888 s). Spy entries **24-34 (median 28) of 70** — clause (b) missed below a third time: even fronts swept as fast as the lab allows do not accumulate; the newest-20 cut held 3-7 spies (median 5, against E57's 1-4). Honest ages were NOT compressed (median 919 s, p10 2,446 s, against E57's 151-917 s): the flywheel signature is absent because the adversary's effective insert rate never rose — the honest cycle meets whatever rate the lab can deliver and stays ahead of it. Clause (a) landed in the flywheel band (< 0.05) with the saturation caveat; the honest reading is **the trim wins at every sweep rate the lab can deliver**, and the sub-10-minute regime — which a real fleet could run, and where mainnet's own cut already lives (OQ8: minutes-fresh, 1.4-8.8 m) — is closed to this lab (the agent would need a compiled dialer or a parallel dial path). Also understood this run, retroactively for E53-E57: `first_hop_spy`'s cap (0.999 in E53, 0.094 here) counts stems into the AGENT's front ports, which are not relays and swallow them — 9 of 112 cap txs here ever reached a spy daemon; the rest died at fronts, the origin's own embargo fired, and the tx fluffed from the origin (E58's 56 % sender-first). The spy-daemon observations the program reports (sp/combined/exposure, light share) are unaffected. (a) hit the low band; (b) missed below; (c) missed both halves; (d) hit (152 m). Two of four.

### E60. P50, the defense headline's second seed: 0.0261 — the trim's win replicates, four clauses of four (2026-10-27 11:48-16:29, `simbox3`)

`20261027_114821_lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_sr300_ud_s23456`, run 99 (exit 0, wall 278 m, min_avail 81.4 GB, 1,107 stem txs): light **0.0261** against E56's 0.0248 — 0.0013 absolute, 5 % relative (the untrimmed pair replicated to 0.09 %; at these shares one exposed user-transaction is ~0.001 of light share, so the spread is a single exposure event, not a mechanism shift). sp recall 0.0019 at precision 1.000, combined 0.0048 at 1.000, **1 of 40 users exposed**. The dumps: spy entries **25-32 (median 29) of 70**, the same band as E56/E57/P49 (24-34); the newest-20 cut held 3-7 spies (median 5) — identical to P49's composition at a 5x faster sweep, one more sign the sweep rate stopped mattering; honest entry ages median ~918 s with the connected tail ~30 s (p90) and the stale half ~2,500 s (p10) — the trim's steady state, the same shape P49 read. (The honest-age figures here and in E59 come from this session's `read_dumps.py`, whose per-user medians are not directly comparable to the narrower ranges quoted in E56/E57 — same mechanism, computed uniformly from here on.) The program's headline defense number now stands on two seeds: **0.0248 / 0.0261, one user of forty exposed, at sweep rates from 300 s down to the lab's floor.** (a) hit (inside ±0.05); (b) hit (1 of 40, sp 0.0019 at 1.000); (c) hit (the entry counts and freshness shape; ages re-based per the note); (d) hit (278 m). Four of four.

### E61. P51, X1a: who is deanonymized today, at mainnet's rate — five clauses of five, and the reachable classes priced (2026-10-27 14:20-19:12, `zenith2alpha`)

`20261027_142035_lean_24_none_h300_k42_w13h_p3_m1_n600_fx_mw25h_ui43200_rs60_bs6_s12345`, run 100 (exit 0, wall 285 m, min_avail 36.1 GB — the 66 extra wallets — 430 stem txs, fluff per hop 0.205): light **0.2935 = 1.92x** the ceiling — the passive stock multiplier (finding 1: 2.20x at lab rate) transfers to mainnet's sender rate. The class table (sp, passive fleet, stock rule, 24 h of activity):

- **unreachable** (37 senders, 55 txs): recall **0.1455 at precision 1.0000** — 98% of its 0.148 first-hop cap; **8 of 37 users (21.6%) had at least one tx attributed in 24 h**.
- **reachable occasional** (49 senders, 147 txs): **precision 0.2651** — OQ12's number, mid-band: relayed-stem cover buries three of four spy guesses, but 38.8% of the class's own txs are attributed (its first-hop cap is 0.388 and sp realizes it fully), and via sp-or-fluff **38 of 49 (77.6%) had at least one tx exposed in 24 h**.
- **busy** (22 senders, 228 txs): **precision 0.8431**, recall 0.1886, **19 of 22 (86%) exposed at least one tx in 24 h** — the plan's "high precision for busy nodes" lands at mainnet rate.

The mechanism split: reachability itself DOUBLES per-tx first-hop exposure (caps 0.388/0.189 against the users' 0.148 — more connections, more draws, spy stem peers more often) while relayed stems dilute attribution 4x for occasional senders (0.27 against 1.00) and barely at all for busy ones (their own volume dominates their neighbourhood's). Today's network, then: unreachable senders are attributable one tx at a time at certainty; occasional reachable senders are noisy per observation (one guess in four) but exposed nearly as often; busy reachable nodes are attributable almost as cleanly as unreachable ones. (a) 1.000/0.146 hit; (b) 0.265 hit; (c) 0.843 hit; (d) 0.216 and 0.864 hit; (e) 285 m hit — **five of five, the program's first perfect pre-registration, on the plan's own section 2.3 class model.**

Corrected 2026-10-28 (the five-day review, R1/R2): the multiplier line divided by the
standard cell's 0.1531 ceiling — this run's own calibration model is 0.1299 (`meta.json`
`model_out`, 366 honest reachable in 295 /24s), so light 0.2935 reads **2.26x**, not 1.92x;
the transfer claim is stronger than written. The reachable exposure line misread its table:
38/47 (2-4 txs) + 1/2 (1 tx) is **39 of 49 = 79.6 %**, not 38 of 49 (77.6 %). Neither number
was a pre-registered clause; five-of-five stands.

### E62. P52, X3a: tevador's stemmable inbound stems work exactly as specified — and their cover is 15x too thin to matter (2026-10-28 04:29-06:57, `zenith2alpha`)

`20261028_042916_lean_24_none_h300_k42_w13h_p3_m1_n600_x3_s12345`, run 102 (exit 0, wall 145 m, 1,128 stem txs): light **0.3409** (E27's 0.337 — the outbound draw untouched, as designed); sp recall 0.1072 at precision **0.9828** against 1.000 stock — the precision band was 0.25-0.60, and the reading rule's ceiling was 0.6: **the cover is too thin at this topology, by a wide margin.** The census carries the why: **71 relayed stems reached all 40 users together, against 1,063 own sends** (~1.8 per user against ~27 own) — the dilution arithmetic gives ~0.94-0.98, and 0.983 measured; for the plan's ~0.3 the user would need to forward ~2.3 relayed stems per own tx, ~15x what the mechanism delivers. The bottleneck is the design's own throttles compounding: one edge-2 slot per epoch, virtual only ~38% of epochs, one connection of ~12 virtual slots — and users hold few of those, since relays' mutual connections dominate every inbound pool. 30,961 `x3` events: the mechanism is not failing, it is faithfully delivering a trickle. At mainnet sender rates the ratio improves (users send ~2 txs/day, not 27 per 4 h) but the network's stem volume scales down with it; scaling these flows to X1a's rate gives ~0.3 relayed stems per user-day against ~2 own — precision ~0.85-0.9, still far above the model. **The proposal's precision-cover rationale does not survive its own throttles.** What survives: the structural guarantee (an inbound-only adversary can never sit on stem edge 1 — tevador's own observation, now built and load-bearing) and the /16 inbound deduplication. Making the cover real needs more stem volume onto virtual connections — more virtual slots, or both edges virtual-eligible — which trades directly against the guarantee. (a) hit; (b) missed above; (c) hit; (d) hit (24 of 40 users exposed); (e) missed below (71 against 200-4,000 — the h71 smoke's 107 scaled DOWN, not up: more competition for the virtual slots); (f) hit (145 m). Four of six, both misses the same finding.

Corrected 2026-10-28 (the five-day review, R3): the closing arithmetic conflated two ratios —
1,063:71 is the own:cover ratio (how far dilution is from parity), while the scale-up the
plan's ~0.3 precision needs is ~2.3 relayed stems per own tx against the delivered 0.067,
~34x, not 15x; and the plain dilution arithmetic gives 0.937 (1,063 of 1,134), with 0.983 the
measured per-user value. The verdict is unmoved: every form of the number sits far above the
0.6 reading-rule ceiling.

Re-derived 2026-10-28 (the five-day review, R6a): the cover census now has a committed script and
outputs (`adhoc/x3_census.py`, `x3_census_run102.json`, `x3_census_smoke.json`), and it corrects
the census while confirming its scale. Confirmed: **30,961 x3 events** exactly; the edge-2 slot
carried a virtual connection in 35 % of the two-stem epochs (44 % of the epochs where the join to
the epoch's x3 event is legible — the quoted ~38 % was this slot reading, not the 94 % candidate
share). Corrected: **67 relayed stems reached 25 of the 40 users** (per-user 1-5, median 2), not
71 across all 40; the smoke's census reads 100 receipts at 23 users, not 107. The dilution
arithmetic moves to 1,063 own against 67 relayed (0.941 plain), and per-user cover is thinner
than written: the verdict only strengthens.

### E63. P54, X3c: the stemmable feature does not touch the outbound-capture eclipse — five of five (2026-10-28 10:31-12:58, `zenith2alpha`)

`20261028_103134_lean_24_none_h300_k42_w13h_p3_m1_n600_sr300_ud_x3_s12345` (the queued cell; P54's
prediction text has the tags swapped — corrected under its block), run 103 (exit 0, wall 145 m,
min_avail 55.7 GB, 1,124 stem txs): light **0.9051** against E53's 0.9083 — a 0.35 % difference:
**X3 is irrelevant to the front-port eclipse, exactly as the guarantee's structure predicts.** The
quarters rise 0.849 → 0.941 (the eclipse deepening through the window, E53's shape). sp recall
**0.445** at precision 1.000, combined **0.951 at 1.000**, **40 of 40 users exposed** (combined;
sp_r 39/40) — E53's regime intact (0.468/0.967/40). The ground-truth first-hop cap reads 0.977:
under the eclipse nearly every user transaction stems straight into the fleet on hop 1, the path
the stemmable design never touches (edge 1 is real-outgoing and the adversary owns the outbound
draw). The census carries the guarantee's collapse as cover: **17 relayed stems reached ONE user**
(user-034; X3a: 67 at 25 users) — the eclipse kills the honest-to-honest connections the virtual
pool feeds on (union median 8 against X3a's 22, virtual slot share 39.8 %, 30,965 x3 events: the
mechanism kept running and had nothing honest to carry). Embargo 0.70, mean hops 1.06 — the
front-swallow signature E59 described. (a) 0.9051 hit; (b) 0.445/0.951 at 1.000 hit; (c) 40/40
hit; (d) 17, hit inside 0-30; (e) 145 m hit — **five of five. Reading rule confirmed: X3's
guarantee has its blind side exactly where this program's adversary lives.** The proposal's
residual value is the inbound-only guarantee and the /16 dedup (E62); against the documented
mainnet architecture — the rotating front end — it offers nothing, and the cover it does add dies
first under the attack.

### E64. P53, X3 at mainnet sender rate: the cover is closed at every rate — precision 1.000, four of six (2026-10-28 10:26-19:48, `simbox3`)

`20261028_102612_lean_24_none_h300_k42_w13h_p3_m1_n600_fx_x3_mw25h_ui43200_rs60_bs6_s12345`, run 104
(exit 0, wall 553 m, min_avail 76.9 GB, 426 txs created and in blocks, 431 stem txs): X1a's
mainnet-rate cell (40 unreachable users at ~2 tx/day, 60 occasional and 6 busy reachable senders,
40 h stop) with the relay fabric running tevador's stemmable inbound stems. **sp precision on
unreachable users 1.000** (recall 0.164, 9 of 55 txs, CI [0.06, 0.27]) against the band 0.45-0.92
and X1a's 1.000: at mainnet rate the cover does not exist as attribution noise. The census says
why: **13 relayed stems reached 11 of the 40 users over the 24 h window, against 55 own sends**
(0.33 relayed per user-day against 1.4 own — E62's scale-down guess of ~0.3 was right); the
plain dilution would be 0.81 if every relayed stem a user forwarded went to a spy, but a user's
stem peers are spies 7.3 % of the time (p_stem 0.073, p_out 0.073), so the expected count of
wrong guesses is about one and the measured count is zero. The two estimate routes P53 was filed
to arbitrate (0.67 and 0.87) both overestimated: the first assumed the cover scales with the
network's stem volume, the second with the users' own rate, and neither accounted for the
forward-to-a-spy factor. The mechanism ran at full strength the whole 40 h — **66,485 x3
events**, virtual candidates in 93.1 % of epochs, union median 21 (X3a 22), the edge-2 slot
virtual in 28.4 % of two-stem epochs (42 % of the join-legible ones; 29,897 join misses of 91,773,
the longer run's share) — and delivered 13 stems to users. The other classes read as X1a within
their intervals: reachable-occasional sp precision **0.288** [0.20, 0.38] (X1a 0.265; recall 0.408
at the first-hop cap 0.411), busy **0.773** [0.66, 0.86] (X1a 0.843; recall 0.223 at the cap);
exposure in 24 h: unreachable **8 of 37** (21.6 %, X1a's exact figure: 5 of 18 at 2-4 txs, 3 of 19
at 1), occasional 39 of 49 by the combined estimator (80 %; X1a 78 %), busy 17 of 22 (77 %; X1a
86 %). Light **0.3066** against X1a's 0.2935, flat by quarter (0.306, 0.307, 0.304, 0.309): 2.36x
the run's own model 0.1299 (X1a 2.26x) — the passive multiplier is untouched, as in X3a. Spy-side
census (`spy_stem_receipts.json`): 386 stem receipts at the 42 spies, every one relay-dialed, 283
distinct txs (66 % of all), 120 at hop 1 (9 from users = the 9 sp_r hits), 0 of 146 receipts from
adopters through a virtual slot — the fleet never touches the gated channel. Class-read note (the
five-day review, R9): the estimator's classes are blocked-ports plus a ≥5-tx threshold, so the busy
row's 22 senders include the 5 miner wallets. (a) 1.000, missed above; (b) 0.164 hit; (c) 0.288
hit; (d) 0.3066 hit; (e) 13, missed below (15-100); (f) 553 m hit — **four of six, both misses
the same finding, as in E62.** Reading rule: above 0.85 at mainnet rate closes X3's cover story
at every rate; what survives of the proposal is the structural guarantee (an inbound-only
adversary never sits on edge 1) and the /16 inbound deduplication, and the adversary-side cells
X3b (P55-P59, the dialing fleet) now measure what those two are worth. Artifacts: the estimator and
both censuses ran manually on simbox3 (the driver scores calibration only) and sit in run 104's
folder with the register files.

### E65. P56, X3b-hidden OFF: the isolation control holds — a hidden dialing fleet receives nothing, four of four (2026-10-28 18:15-20:51, `zenith2alpha`)

`20261028_181536_lean_24_none_h300_k42_w13h_p3_m1_n600_sph_sd12_s12345`, run 105 (exit 0, wall 153 m,
min_avail 55.5 GB, 1,096 txs created, 1,087 in blocks): E27's spread fleet with the spies hidden
(hide-my-port) and dialing (`--spy-dial 12`, no exclusive node), stock stem selection, no X3. The
first cell of the program in which the spies dial. **Zero stem receipts at the 42 spies** over the
window (`spy_stem_receipts.json`: 0 of 1,096 stem txs seen as stems by any spy; the estimator's
header line "1096 seen by a spy" counts fluff receipts); **light share 0.000** in every quarter
against the cell's 0.1531 ceiling — a spy in no white list holds no outbound slot anywhere, and
p_out reads 0.0 for all 340 honest nodes; **sp and sp_r recall 0.000** on 1,032 user txs; the
first-fluff estimator makes 1,089 guesses and gets none right (a hidden spy's fluffs all arrive on
the connections it dialed, from relays). The dial check: every spy's rx events sit on connections
it dialed — **59 to 85 distinct outbound connection ids per spy over the run (median 68), zero
inbound** — so the spies found peers through the seeds and kept dialing as peers churned; the
census counts distinct ids, not the concurrent 12, which the spies' default log level does not
expose (the clause's "holds 10-12" is read as "dialed and held outbound connections throughout",
the mechanism the clause exists to check). Stock Dandelion++ stems only on outgoing connections
(source-verified 2026-10-26), and the measurement agrees exactly: an adversary that is never
dialed sees no stem at all. (a) 0 hit; (b) 0.000/0.000 hit; (c) hit on the dial reading; (d) 153
m hit — **four of four.** This is the floor P57 and P58 measure up from: every stem a hidden spy
receives in those cells is X3's doing. Archive on the array (2,636 files, itemize zero), local
copy removed.

### E66. P57, X3b-hidden under universal adoption: the virtual slot is the hidden fleet's only way in — 78 stems, every one virtual, none at hop 1, five of five (2026-10-28 20:54-23:30, `zenith2alpha`)

`20261028_205441_lean_24_none_h300_k42_w13h_p3_m1_n600_x3_sph_sd12_s12345`, run 106 (exit 0, wall 153 m,
min_avail 54.9 GB, 1,096 txs created, 1,090 in blocks): E65's hidden dialing fleet (hide-my-port,
`--spy-dial 12`, no exclusive node) with the whole fabric running tevador's stemmable inbound stems
(`--stemmable`, 289 adopters). **78 stem receipts at the 42 spies** (`spy_stem_receipts.json`: 72
distinct txs, 6.6 % of the 1,096) against E65's 0 under stock selection and the filing's 30-150
(center ~70); **every one of the 78 joins to the sender's latest x3 virtual list**
(`virtual_rx_share` 1.000, no join misses), and every one sits on a connection the spy dialed
(`dir=out` at the spy, inbound at the relay: the virtual slot, as designed). **Hop-1 receipts 0**
(0 of 1,033 user txs; sp_r recall 0.000): edge 1 stays real-outgoing-only and a hidden spy never
holds one, so the guarantee reads exactly at the spy. The 72 txs the fleet did see arrive at hop 2
or later and carry no origin: the sp estimator attributes all 72 to the forwarding relay
(precision 0.000), the first-fluff and combined estimators get 0 of 1,078 and 1,079 guesses.
**Light 0.000** in every quarter (p_out 0.0 on all 340 honest nodes: a hidden spy still holds no
outbound slot anywhere); what X3 adds shows up in p_stem instead — a spy sits in a reachable
node's stem-peer set at some epoch for 52.3 % of the 300 relays, at a median per-node share of
0.018 (E65: 0.0 and 0.0). The mechanism ran as in X3a: **30,958 x3 events** (X3a 30,961), virtual
candidates in 95.7 % of epochs, union median 24 (X3a 22; the spies' ~504 inbound connections in 42
/16s now sit in the lists), the edge-2 slot virtual in 35.1 % of two-stem epochs (X3a 35.3 %); and
the users' cover held, **68 relayed stems at 30 of 40 users** (X3a 67 at 25) against 1,033 own
sends. The spies and the users drew comparably from the same pool (78 against 68, at ~504 against
~480 inbound connections), the filing's analogue. Per spy: median 1 receipt, max 9, 15 of 42 got
none; the dial check reads as E65 (53-83 distinct outbound connection ids per spy, median 67,
zero inbound). Against the relay-dialed fleet in X3a (885 receipts, 637 txs = 56 %, 127 at hop 1),
the hidden fleet at the same dial budget gets a ninth of the receipts, a tenth of the txs and none
at hop 1. (a) 78 at 1.000 hit; (b) 0 and 0.000 hit; (c) 0.000 hit; (d) 68 hit; (e) 153 m hit —
**five of five.** Reading: X3 opens to an adversary that stock Dandelion++ shuts out entirely
(E65) a channel worth ~7 % of stem txs at hop 2 or later, priced at an ordinary node's dial
budget and carrying no attribution at this fleet size; the structural guarantee holds at the spy.
What the fleet gets when it pays alone (P58, spy-only virtual lists) is running. Artifacts: the
estimator and both censuses ran manually on tr and sit in run 106's folder with the register files. Archive on the array (2,636 files, itemize zero),
local copy removed.

### E67. P59, X3b-dense: the real fleet's layout at 8 /24s — the excess is 1.73x, receipts scale per /24 not per spy, one of five (2026-10-28 20:00-00:45, `simbox3`)

`20261028_200039_lean_24_none_h300_k8_w13h_p3_m5_n600_x3_s12345`, run 107 (exit 0, wall 281 m on the
shared VM, min_avail 81.0 GB, 1,095 txs created, 1,022 in blocks): 40 spies in 8 /24s (5 each, in 8
/16s), OQ8's identified shape, relay-dialed as in every cell through X3a (each spy holds one
outbound connection, its seed, and 19-55 inbound, median 31.5), the fabric adopting X3 (289
adopters). The program's first k8 cell. **Light 0.0598 against the run's own ceiling 0.0345 =
1.73x** (quarters flat), against the clause's 1.8-3.5x and the k21/k42 series' 2.02x (E19), 2.20x
(E27), 2.23x (X3a, 0.3409 on 0.1531): the absolute figure sits inside the 0.058-0.112 the
filing quoted from an assumed ~0.032 ceiling, but the clause reads the ratio, and the ratio is
under. **187 stem receipts at the 40 spies**, every one relay-dialed (`dir=in`, 0 of 164 from
adopters virtual — the baseline census's reading holds: a relay-dialed fleet never occupies a
virtual slot, so this cell cannot test the /16 bucketing), 177 distinct txs (16.2 %), **14 at hop 1
from users** against 15-50; sp precision on users **1.000** (14 of 14), **sp_r recall 0.014** [0.00,
0.03] against 0.02-0.07 and X3a's 0.107 (114 hop-1 user txs of 1,063); 6 of 40 users exposed in the
4 h window (X3a 27 of 40 under E27's layout). The per-/24 arithmetic is the finding: X3a's 42 /24s
drew 885 receipts = 21.1 per /24, this cell's 8 /24s drew 187 = 23.4 per /24 — **the receipts
scale with the number of /24s, not with the number of spies** (per spy 21 against 4.7), and hop-1
user txs the same way (2.7 against 1.75 per /24): under the `24` ceiling a /24 holds one outbound
slot at a node whatever it packs into it, so the fleet's five-per-/24 packing buys it nothing a
single spy per /24 would not get. Light per /24 is level too (0.0598 / 8 = 0.0075; X3a 0.3409 / 42 =
0.0081), and the multiplier's shortfall (1.73 against 2.2) is the single-/24 core's drain the
filing's reading rule names: a /24's slot is one slot, and five spies behind it share the reach the
k21/k42 series gave each spy its own /24 for. The mechanism ran as before: **30,968 x3 events**
(X3a 30,961), virtual candidates in 94.3 % of epochs, union median 23 (X3a 22), the edge-2 slot
virtual in 37.5 % (X3a 35.3 %); the users' cover unchanged, **67 relayed stems at 29 of 40 users**
(X3a 67 at 25) against 1,031 own sends — the cover is the honest fabric's inbound, independent of
the fleet's layout, as filed. Per spy: median 3.5 receipts, max 21, 5 of 40 got none; the p_out
census reads the dense fleet in 94 % of relays' outbound sets at some window at a median share of
0.053, and in 75 % of users' at 0.006 (E27's spread fleet: nearly every node, at ~0.3). Wall 281 m:
the clause was filed for `zenith2alpha` (153 m for this shape) and the cell moved to `simbox3`
at 20:05, where P53's 40 h cell took 553 m; the box, not the cell. (a) 1.73x missed below; (b) 187
hit, hop-1 14 missed by one; (c) 67 hit; (d) precision 1.000 hit, sp_r recall 0.014 missed
below; (e) 281 m missed — **one of five, with the three substantive misses all on the low side
and the same mechanism.** Reading: the real fleet's layout earns less than the spread layout the
program measured it by — per /24 the same, per spy a fifth — so OQ8's dense-fleet passive number
is ~1.7x its own `24` ceiling, not 2.2x, and the fleet's 42 /24s on mainnet are what its 240-odd
addresses are worth under the dedup rule. The bucketing question moves to the dialing-fleet
budget pole (dense against spread, hidden, `--spy-dial 64`), filed after P58 reads. Artifacts:
the estimator and both censuses ran manually on simbox3 and sit in run 107's folder. Archive on
the array (2,626 files, itemize zero), local copy removed.

### E68. P58, X3b-hidden with the fleet paying alone: three times the stems of universal adoption, still none at hop 1, and the users' cover is gone — five of five (2026-10-28 23:30-02:07, `zenith2alpha`)

`20261028_233022_lean_24_none_h300_k42_w13h_p3_m1_n600_x3_sph_sd12_sc_s12345`, run 108 (exit 0, wall 154
m, min_avail 55.6 GB, 1,093 txs created, 995 in blocks): E66's cell with the cidrs file naming only the 42 spy
/24s, so a relay's virtual list holds spies and nothing else. **238 stem receipts at the 42 spies**
(`spy_stem_receipts.json`: 204 distinct txs, 18.7 % of the 1,093) against E66's 78 under universal
adoption — **3.05x** — and the filing's 80-300; **every one virtual** (`virtual_rx_share` 1.000) and
on a spy-dialed connection; per spy median 4.5, max 17, one of 42 got none. **Hop-1 receipts 0**
(0 of 1,028 user txs; sp and sp_r recall 0.000; the first-fluff and combined estimators 0 of 1,079
and 1,081): the guarantee holds at the spy when the fleet is the only thing stemmable. **Light
0.000** in every quarter, p_out 0.0 on all 340 honest nodes; the spies' presence is in the relays'
stem-peer sets alone — a spy in 66.7 % of relays' sets at some epoch, median per-node share 0.040
(E66: 52.3 % and 0.018). The x3 census shows the sparse list at work: **30,967 x3 events** (E66
30,958) but a virtual candidate in only 64.9 % of epochs (E66 95.7 %), union median 13 (E66 24),
and the edge-2 slot virtual in 9.1 % of two-stem epochs (E66 35.1 %; 20,440 of 40,541 epochs are
join misses here against 10,916 in E66, so the legible share is 18 %) — fewer virtual draws, every
one of them a spy, and the spies' total goes up 3x. **Relayed stems at users 0** (E66 68, X3a 67):
with nothing honest in any virtual list the users never receive a relayed stem, so the cover that
X3's universal adoption gave them (and E64 found too thin at mainnet rate) is absent by construction;
no user forwards a stem, the sp estimator makes no guess on a user (precision on users is undefined
on zero guesses, read as the clause's intent — no user is ever attributed), and 0 of 40 are
exposed. Dial check as E65/E66: 58-78 distinct outbound connection ids per spy (median 69), zero
inbound. (a) 238 at 1.000 hit (3.05x E66's measured 78, at the edge of the 1.5-3x the band was
built from); (b) 0 hit; (c) 0 relayed and no user guess, hit; (d) 0.000 hit; (e) 154 m hit —
**five of five.** Reading, the design's "who pays" answer as filed: a fleet that pays alone gets
three times the hop-2+ stems of universal adoption and the users get none of the cover — but the
stems it gets are still worth nothing for attribution at this fleet size (recall 0.000 on every
estimator, as in E66), because edge 1 is never virtual. Together E65-E68 read: stock Dandelion++
gives a hidden fleet nothing (E65); X3 gives it 7 % of stem txs at hop 2+ under universal adoption
(E66) and 19 % when it pays alone (E68), at an ordinary node's dial budget, none at hop 1; and the
relay-dialed fleet's take scales per /24 (E67). What a larger dial budget buys the hidden fleet is
the budget pole, filed next. Artifacts: the estimator and both censuses ran manually on tr and sit
in run 108's folder with the register files. Archive on the array (2,636 files, itemize zero), local copy
removed.

### E69. P55, X3b-pay with a dialing fleet: payment buys the virtual channel by spending the passive one — three of five (2026-10-29 02:07-04:43, `zenith2alpha`)

`20261029_020725_lean_24_none_h300_k42_w13h_p3_m1_n600_x3_sd12_sc_s12345`, run 109 (exit 0, wall 153 m,
min_avail 55.3 GB, 1,097 txs created, 1,046 in blocks): X3a's spread cell with the cidrs naming only the
42 spy /24s and the fleet dialing (visible, `--spy-dial 12`). **Light 0.0923**, flat by quarter (0.0917,
0.0919, 0.0935, 0.0920), against the clause's 0.30-0.38 and E27/X3a's 0.337/0.3409 — a miss, and the
census names the mechanism: the relays' own outbound slots hold a spy at a median share of **0.081**
(E27 0.325, X3a 0.315; ever 0.933 against 1.0), while the users' share actually rose (0.137 against
E27's 0.119). Dialing moves the spy from the relay's outbound side to its inbound side — the passive
white-list channel is a channel for a fleet that sits still and gets dialed, and the spies now hold
15-43 distinct outbound connection ids each (median 33) against 14-72 inbound (median 43). The fleet's
stem take: **763 receipts** (525 distinct txs, 47.9 %), split **462 relay-dialed + 301 virtual**
(`virtual_rx_share` 0.526) — against the clause's 1,000-1,400 at a 0.05-0.20 virtual share, and against
X3a's 885 receipts and 637 txs for the same fleet sitting still without paying: the residual relay-dialed
channel fell to half (885 to 462) and the new virtual one (301) does not make the difference up. The
x3 census reads like E68's sparse list — virtual candidates in 59.9 % of epochs, union median 13, the
edge-2 slot virtual in 8.5 % of two-stem epochs — except the spies hold the real outgoing edges too, so
edge 2 is a spy either way. **The first hop is exactly as exposed as stock: 143 hop-1 stem txs, 133 of
them user txs** (E27 130, X3a 114), sp recall on users **0.129** [0.09, 0.17] at precision **1.000**
(133 of 133; busy 10 of 64 at 0.156), **31 of 40 users exposed** by sp_r over the window (E27 27 of 40;
busy 3 of 5 by combined). And the users received **0 relayed stems** (X3a 67, E66 68): nothing honest is
stemmable, so the cover the fleet pays for goes to the fleet — and is worth less than what it gave up.
(a) 0.0923 missed below; (b) 0 relayed and precision 1.000 hit (the cidrs gate holds — the census shows
no honest relayed stem); (c) 763 at 0.526 missed on both halves; (d) 133 and 0.129 hit; (e) 153 m hit —
**three of five, both misses the same mechanism: the direction swap.** Reading, the payment pole's answer
sharper than filed: fleet-only payment hands the fleet the virtual channel (301 hop-2+ receipts, none at
hop 1, the guarantee intact) and the users nothing, at the price of the passive channel itself — a
visible fleet that dials to qualify for the slots ends the window with 14 % fewer receipts and 18 % fewer
txs than the same fleet sitting still got for free in X3a. The white-list refresh the filing feared above
0.38 does not happen (OQ13 (b)'s v1 effect, now measured in the wrong direction to matter). E65-E69
close X3b: stock gives a hidden fleet nothing; X3 gives a hidden fleet 7 % of stem txs (universal) or 19 %
(paying alone), a visible dialing fleet 48 % but at a net loss against sitting still; nothing buys hop 1;
the relay-dialed take scales per /24 (E67); the users' cover exists only when honest connections are
stemmable, and is thin at mainnet rate (E64). Artifacts: the estimator and both censuses ran manually on
tr and sit in run 109's folder with the register files. Archive on the array (2,636 files, itemize zero),
local copy removed.

### E70. P60, the budget pole's spread leg: 64 dials buy 3.5x the stems of 12, sub-linear in the budget, still nothing attributable — four of five (2026-10-29 10:30-13:34, `zenith2alpha`)

`20261029_103017_lean_24_none_h300_k42_w13h_p3_m1_n600_x3_sph_sd64_s12345`, run 110 (exit 0, wall 180 m,
min_avail 54.1 GB, 1,097 txs created, 1,008 in blocks): E66's cell with the dial budget 64 instead of
12 — 42 hidden spies, one per /24, ~9 spy inbound connections per relay against E66's ~1.7.
**273 stem receipts at the 42 spies** (221 distinct txs, 20.1 % of the 1,097) against the clause's
300-550 — **3.50x E66's 78 for a 5.33x budget**: linear-in-connections would be 416, so the connection
beyond the first in a /16 buys a discounted share, the discount the pole was filed to measure. Every
receipt is virtual (`virtual_rx_share` 1.000, all on spy-dialed connections) and **hop-1 stays 0**
(sp, sp_r, first-fluff and combined recall all 0.000 on 1,033 user txs; **0 of 40 users exposed**).
**Light 0.000** in every quarter (0.0, 0.0, 0.0, 0.0), p_out 0.0 on all 340 honest nodes;
the spies' presence is now nearly universal in the relays' stem-peer sets — a spy in 91.3 % of relays'
sets at some epoch at a median share of 0.080 (E66 52.3 % and 0.018) — and it still attributes
nothing. The x3 census carries the mechanism: **30,966 x3 events**, virtual candidates in 96.7 % of
epochs, **union median 24 — unchanged from E66's 24 at a fifth of the fan-in**: the ~5x more spy /16s
did not grow the union, they displaced honest /16s in the /16-deduped draw, and the edge-2 slot went
virtual in 37.5 % of two-stem epochs (E66 35.1 %). The users' cover thinned a little, as the clause
anticipated: **52 relayed stems at 24 of 40 users** (E66 68 at 30) against 1,033 own sends. Per spy:
median 6, max 23, 1 of 42 got none; the dial check reads 74-92 distinct outbound connection ids
(median 83.5; E66 53-83), zero inbound. (a) 273 missed below by 9 % of the floor; (b) 0 and 0.000
hit; (c) 0.000 hit; (d) 52 hit; (e) 180 m hit — **four of five.** Reading: at a large budget the
hidden fleet's take is real (a fifth of stem txs pass a spy at hop 2+) but bounded by the /16 count,
not the connection count — the same shape E67 measured for the relay-dialed fleet, now on the virtual
side. P61 (the same fan-in in 8 /16s, running on simbox3) reads whether the bound is per-/16 or
per-list. Artifacts: the estimator and both censuses ran manually on tr and sit in run 110's folder
with the register files. Archive on the array (2,636 files, itemize zero), local copy removed.

### E71. P61, the budget pole's dense leg: 8 /16s draw what 42 draw at the same fan-in — the /16 count is spent, and the budget pole closes X3b — four of five (2026-10-29 10:26-16:03, `simbox3`)

`20261029_102622_lean_24_none_h300_k8_w13h_p3_m5_n600_x3_sph_sd64_s12345`, run 111 (exit 0, wall 332 m on
the shared VM, min_avail 80.7 GB, 1,098 txs created, 1,089 in blocks): P59's layout (40 spies in 8 /24s,
5 each) hidden and dialing 64 — the same ~9 spy inbound connections per relay as E70's spread cell,
concentrated into 8 /16s. **212 stem receipts at the 40 spies** (191 distinct txs, 17.4 % of the 1,098)
against the clause's 250-500 — **78 % of E70's 273, inside the pre-registered 25 % equivalence window:
dense = spread at this budget.** The /16 count between 8 and 42 does not matter once each relay sees ~9
spy inbounds — with ~9 draws, spread lands ~8-9 distinct spy /16s of its 42 and dense saturates its 8:
both arrive at the same occupancy, exactly the "first connection per /16 buys the slot, the rest buy
nothing" rule. Every receipt is virtual (`virtual_rx_share` 1.000, all on spy-dialed connections);
**hop-1 0**, every estimator's recall 0.000 on 1,032 user txs, **0 of 40 users exposed** (the busy row's
1 of 66 by the combined estimator is noise). **Light 0.000** in every quarter (0.0, 0.0, 0.0, 0.0);
a spy sat in 87.7 % of relays' stem-peer sets at some epoch at a median share of 0.060 (E70 91.3 % and
0.080). The censuses are near-identical to E70's — **30,964 x3 events** (E70 30,966), virtual candidates
in 96.4 % of epochs, **union median 24, the same as E70's at 42 /16s**: the union is honest-dominated
and the fleet's /16s displace honest ones by the same ~8 whichever layout delivers them — the edge-2
slot went virtual in 37.2 % of two-stem epochs (E70 37.5 %). The users' cover thinned a step further,
**46 relayed stems at 20 of 40 users** (E66 68 at 30, E70 52 at 24) against 1,032 own sends. Per spy:
median 5, max 11 (E70's max 23: the dense ceiling per spy is lower — 8 shared /16s), 1 of 40 got none;
the dial check reads 77-93 distinct outbound connection ids (median 85), zero inbound. (a) 212 missed
below by 15 % — the same sub-linearity that took E70 under its band; (b) 0 and 0.000 hit; (c) 0.000
hit; (d) 46 hit; (e) 332 m hit — **four of five.** Reading, the pole's answer joined with E67 and E70:
**one slot per prefix, on every axis the fleet can push** — spies per /24 (E67: relay-dialed receipts
per /24 level at 21-23 whether the /24 holds 1 or 5 spies), connections per spy (E70: 3.50x receipts
for 5.33x budget), /16s fielded (here: 0.78x receipts for 5.25x the /16 count, inside the equivalence
window) — every unit beyond the first per prefix buys a discounted share, and none of it reaches hop 1
or an attribution. That closes X3b end to end: the lab has now measured the adversary's side of
tevador's proposal on every axis its design note named. Artifacts: the estimator and both censuses ran
manually on simbox3 and sit in run 111's folder with the register files. Archive on
the array (2,626 files, itemize zero), local copy removed.

### E72-E75. The per-host series, read after the premise correction: the /24 cap sets everything, the R8 flag is provably inert without shared hosts, and the addresses-per-/24 axis is flat (2026-10-31 runs, scored 2026-11-07 post-switchover)

Four cells, runs 112-115, scored together after the reorganization switchover (the smoke assertion of 10-31 had caught that m-daemons get distinct addresses, so the gray-pump arms were pulled and the survivors read as the addresses-per-/24 dose-response):

**E72 (P63, run 112, M1 k9 m7, 63 addresses in 9 /24s):** light 0.0633 = 1.66x model 0.0382 (the filing's 1.7-2.4x band held at its floor); sp recall 0.0146 at precision 1.000 (15/1029), 314 receipts, hop-1 15. **E75 (P62, run 115, B1 k9 m1, 9 addresses):** light 0.0853 = 2.24x model (above the filing's 1.5-2.2x band by its own ceiling), 414 receipts on 9 spies, hop-1 16, recall 0.0155 (16/1032), precision 1.000. The dose-response between them is the finding: **per-/24 receipts are level (B1 46, M1 35) while per-address exposure dilutes 1 -> 1/7** — seven addresses per /24 buy nothing the /24's single slot does not already price, the same rule E67/E70/E71 established on every other axis. The B1 > M1 light (2.24x vs 1.66x) adds the dilution's second face: one address per /24 concentrates the slot wins that seven addresses split.

**E73 (P64, run 113, M2 k9 m7 hpl1):** the NULL-VALIDATION of the R8 per-host cap: light 0.0651 vs M1 0.0633, receipts 296 vs 314, recall 0.0197 vs 0.0146 — identical within run noise, exactly as predicted after the correction (no shared-host endpoints exist for the cap to bite). The flag is provably inert without same-host entries: the R8 patch's off-by-default safety demonstrated end to end. The cap's real test waits on the same-IP generator feature.

**E74 (P66, run 114, I1 k42 m7, 294 addresses in 42 /24s):** light 0.3467 = 2.26x model 0.1531 (band 2.0-2.6 HIT; the m1 series read 2.02-2.23), 1,004 receipts, hop-1 user txs 106 (band 100-150 HIT), recall 0.108 at precision 1.000 — within noise of X3a's k42 m1 (885 receipts, 114 hop-1, recall 0.107). Sevenfold addressing moved the multiplier by at most a few percent: **the /24 cap, not address count, sets the fleet's passive position.** For the real fleet (~216 addresses per /24), this closes the last layout axis the lab could measure without same-IP endpoints.

Together: the passive defense surface reduces to the /24 slot and the 20-newest candidate cut (Finding 1), both already addressed by measured rules; what the port front buys is NOT list position (stock white is one-per-host and addresses dilute within /24s) — it is the gray-side pump and endpoint count for gossip spread, which the per-host cap (R8, inert until same-IP modeling exists) and the id-consistency rules (R9, series re-enabled 2026-11-07 after its patch was regenerated complete) respectively target.

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

*Outcome, 2026-10-23 18:30 (E25):* light **0.0928** in 0.08-0.12: **hit**; adopters 0.0000: hit; the scorer's non-adopter group 0.1537
against 0.17-0.24: **miss, below** (the clause named the slot-weighted group; the non-adopting light nodes read 0.186, inside); relays
1.14x light: hit; 7 of 40 exposed in 5-12: hit; `sp_r` precision 1.000, recall 0.022 at its ceiling: hit.

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

*Outcome (a), 2026-10-23 21:40:* light **0.1911**, inside 0.18-0.22: hit. Flat: hit (Q4 0.6% above Q1). Relays 0.2187, inside
0.20-0.26: hit. Users 0.0522, inside 0.05-0.08: hit. Lowest free RAM 10.6 GiB: hit. The 13 h cell's 0.1978 fell 3% in thirteen more
hours and the relay curve is flat from hour 10 to 30 (E26). (b) is running on `simbox3` (started 20:19).

*Outcome (b), 2026-10-24 03:31:* light **0.1497**, inside 0.10-0.15 by 0.0003: hit as written, but the cell is still draining
(Q4 5.4% below Q1; relays 0.181 at hour 20, 0.155 at hour 30). Relays 0.1677, inside 0.11-0.17: hit. Relay curve flat over hours
20-30 within 10%: **miss** (-14%). Free RAM 75.6 GiB above 60: hit. Three of four. The dilution is real but small (1.82x the ceiling
at most, against 1.91x at 2 per /24 and 2.32x at 1); the 1-to-8 gap at a fixed hour is mostly the drain transient, which scales with
the spy count (E30).

**P15, filed 2026-10-23 15:35, before the cell is queued (E23's seed spread).** `lean_legacy_none_h300_k21_w13h_m2_n600_s23456` on
`simbox2`: E23's cell at the other seed and on the other box, as E21 did for the `24` cell (0.1626 against E19's 0.1662, a 2%
spread). Light-node share **0.26-0.31**, flat by quarter (Q4 within 10% of Q1), relays 1.05-1.25x light; the `24`/`legacy` ratio for
the seed-23456 pair (0.1626 over this read) **0.52-0.63**. Prior 65%. Below 0.26 means E23's 2.34x was the high end of its seed
spread and the 42% claim weakens toward the models' 33%; above 0.31 strengthens it.

*Outcome, 2026-10-23 20:55:* light **0.2826**, inside 0.26-0.31: hit. Flat: hit (Q4 2% below Q1). Relays 1.13x light, inside
1.05-1.25: hit. `24`/`legacy` ratio 0.1626/0.2826 = **0.575**, inside 0.52-0.63: hit. All four clauses hit; the seed spread of
the `legacy` `tail` cell is 1% (0.2857, 0.2826) and the 42% dedup claim stands at both seeds (E23b).

**P17, filed 2026-10-23 20:55, before the cell is queued (does the excess scale with the candidate count?).**
`lean_24_none_h300_k42_w13h_m1_n600_s12345` on `simbox2`: the `tail` layout with **42 spy /24s at 1 spy each** (42 spies, the
same spy count as `tail`, twice its /24s; 384 daemons), stock `24` selection, 13 h warmup, window 15-19 h, seed 12345, stock
RandomX. Its `24` ceiling by hand is 42/(242+42) = 0.148, scaled by the Monte Carlo's 0.0822/0.0798 about **0.152**; the run's own
`model` line supersedes this. The reading E23 and E24 arrived at, not pre-registered until now: the excess over the model follows
the number of distinct candidates the selection sees (21 /24s under `24`: 2.0x the ceiling at 2 per /24 and 2.4x at 1 per /24;
42 IPs under `legacy`: 2.34x its model). If so, 42 candidates under `24` give 2.3-2.4x of 0.152: light **0.30-0.40**, flat by quarter
(Q4 within 10% of Q1), relays 1.05-1.25x light, users 0.08-0.14, and the relay curve stationary from hour 5 with the start-order
gradient (latest-started quarter above 0.6). Below 0.30 means the excess does not scale with the candidate count in proportion
(the additive reading, a fixed 0.12 over the ceiling as in E24a, puts it at 0.27; a saturating lock-in below that); above 0.40
means more than proportional. Prior 50%. Exposure recorded, not predicted (precision 1 at the ceiling expected). Lowest free RAM on
`simbox2` above 12 GB.

*Outcome, 2026-10-23 23:33:* light **0.3369**, inside 0.30-0.40: hit (2.20x the run's 0.1531 ceiling). Flat: hit (Q4 1.3% below
Q1). Relays 1.11x light: hit. Users 0.133, inside 0.08-0.14: hit. Relay curve stationary from hour 5: hit. Latest-started quarter
above 0.6: **miss** (0.50-0.54). Five of six; the candidate-count reading holds as a multiplier on the ceiling, and the additive
reading (0.27) is refuted (E27).

**P18, filed 2026-10-23 21:43, before the cell is queued (P17's `legacy` control).** `lean_legacy_none_h300_k42_w13h_m1_n600_s12345`
on `phantom`: P17's layout (42 spies in 42 /24s at 1 each) under v0.18.4.2's selection, 13 h warmup, window 15-19 h, seed 12345. Under
`legacy` every IP is its own candidate, so this cell shows the selection the same 42 candidates as E23's `tail` cell (42 IPs in 21
/24s, 0.2857 and 0.2826); its model is the same too (42 spy IPs against 300 honest, about 0.122; the run's `model` line supersedes).
If the excess follows the candidate count, the /24 layout does not matter under `legacy` and this reads as E23 did: light
**0.27-0.32** (the top is a little above E23's because the old rule's /24 skip after a pick, which removed a spy's co-/24 partner
in `tail`, has nothing to remove here), flat by quarter, relays 1.05-1.25x light, users 0.07-0.10. Below 0.27 means the /24 layout
matters even where the selection ignores it (list dynamics by /24); above 0.32 means the skip cost `tail`'s spies more than the
model says. Prior 60%. Paired with P17 this separates the two rules at a fixed layout: P17's read over this one is the `24`/`legacy`
ratio at 42 /24s, against 0.58 at 21 /24s. Lowest free RAM on `phantom` above 10 GB.

*Outcome, 2026-10-24 00:26:* light **0.2984**, inside 0.27-0.32: hit (2.41x the run's 0.1237 model; E23's 21-/24 layout read
0.2857 under the same rule, a 4% move). Flat: hit (Q4 0.8% above Q1). Relays 1.13x light: hit. Users 0.0981, inside 0.07-0.10: hit.
Four of four. The `24`/`legacy` ratio at 42 /24s is **1.13** (E27 over this run), against 0.58 at 21 /24s: stock dedup gives the
spread fleet more slots than the old rule did (E28).

**P19, filed 2026-10-23 23:35, before the cell is queued (E27's seed spread).** `lean_24_none_h300_k42_w13h_m1_n600_s23456` on
`simbox2`: E27's cell at seed 23456 (same box). The family's seed spreads so far are 1-2% (E21: 0.1626 against 0.1662; E23b: 0.2826
against 0.2857). Light-node share **0.32-0.36**, flat by quarter, relays 1.05-1.2x light, users 0.11-0.15, `sp_r` precision 1 at
its ceiling, 23-31 of 40 users exposed. Prior 70%. Below 0.32 or above 0.36 means this layout's seed spread is larger than the
family's, and E27's 2.20x needs the third seed before it is quoted.

*Outcome, 2026-10-24 02:14:* light **0.334**, inside 0.32-0.36: hit (1% below seed 12345). Flat: hit (Q4 2.4% above Q1). Relays
1.13x light: hit. Users **0.1033, below 0.11-0.15: miss** (the users' seed spread is 25%, the light nodes' 1%; E27b). `sp_r`
precision 1 at its ceiling: hit. Exposed 26 of 40, inside 9-31: hit. Five of six; E27's multiplier is quotable at two seeds.

**P20, filed 2026-10-24 00:26, before the cell is queued (the full ban list against the spread fleet; open question 7 at 42 /24s).**
`lean_24_half_h300_k42_w13h_m1_n600_s12345` on `phantom`: E27's cell with the ban list naming all 42 spy /24s (`--list half
--ban-coverage 1.0`; 42 entries, 165 adopters, the same half of the honest nodes as E25's cell by the same seeded draw; the
tie-break of open question 9 does not arise at coverage 1.0), stock `24`, 13 h warmup, window 15-19 h, seed 12345. E25 is the
template: on the 21-/24 fleet the full list took light from 0.1662 to 0.0928 (0.56x), adopters to 0.000, the non-adopting light
nodes to 1.12x the no-list cell, and the exposed users from 18 to 7 of 40, all non-adopters. Here: light **0.17-0.21** (0.50-0.62x
E27's 0.3369), adopters 0.000-0.005, **non-adopting light nodes** (users, relays and observers without the list; not the scorer's
slot-weighted non-adopter group, which the five 100-peer miners drag down, the P14 lesson) 0.34-0.42, users 0.05-0.09, `sp_r`
precision 1, exposed users 9-16 of 40 and all of them non-adopters, relays 1.05-1.25x light, flat by quarter. Prior 65%. Light
below 0.17 means the list does more against the spread fleet than against the packed one (the non-adopters' slots are not
refilled by spies to the same degree); above 0.21 means the non-adopters absorb more than +25%. Lowest free RAM on `phantom`
above 10 GB.

*Outcome, 2026-10-24 03:08:* light **0.184**, inside 0.17-0.21 (0.55x E27): hit. Adopters 0.0000: hit. Non-adopting light nodes
0.369, inside 0.34-0.42 (+10%): hit. Users 0.0528: hit. `sp_r` precision 1: hit. Exposed **15 of 40**, inside 9-16, all non-adopters:
hit. Relays 1.13x light: hit. Flat: hit. Lowest free RAM 10.6 GiB: hit. Eight of eight (E29): the list's effect is the same 0.55x on
the spread fleet as on the packed one.

**P21, filed 2026-10-24 03:31, before the cell is queued (the spread fleet's steady state).** `lean_24_none_h300_k42_w24h_m1_n600_fx_s12345`
on `phantom`: E27's cell (42 spies in 42 /24s at 1 each, 384 daemons) with a **24 h warmup**, window 26-30 h, fixed RandomX seed,
seed 12345. The 21-/24 family moved -3% (1 per /24, E26) and -5% (2 per /24, E22a) from the 13 h window to the 24 h one, with flat
curves from hour 10. Light-node share **0.31-0.35** (0.92-1.04x E27's 0.3369), by quarter flat (Q4 within 5% of Q1), relays
1.05-1.2x light and flat from hour 10 to 30 within 5%, users 0.09-0.15, `sp_r` precision 1 at its ceiling, 22-30 of 40 users
exposed. Prior 70%. Below 0.31 means the spread fleet's excess relaxes where the packed fleets' did not; above 0.35 means it still
grows after 19 h. Lowest free RAM on `phantom` above 10 GB; about 4 h wall.

*Outcome, 2026-10-24 07:29:* **five of seven.** Light **0.3354** (hit), quarters 0.3308-0.3411 (+3%, hit), relays 0.3758 = 1.12x light (hit) but
0.350 at hour 20 to 0.386 at hour 30 (+10%, the flatness clause missed), users 0.1272 (hit), `sp_r` precision 1.00 (hit), 33 of 40 exposed
(missed high), lowest free RAM 10.6 GB (hit). Wall 3 h 45 m. E32.

**P22, filed 2026-10-24 05:15, before the cell is queued (the Threadripper's platform check).** `lean_legacy_none_h71_k1_s12345`
on `zenith2alpha` (192.168.1.33: Threadripper 3970X, 64 threads, 251 GB, Ubuntu 24.04.5, a fresh `setup.sh --clean --sim-binary` build,
live run on the Optane `/fast`), the cell that validated `simbox2` and `simbox3`: phantom 0.0610, simbox2 0.0614, simbox3 0.0641. Light-node
share **0.055-0.066**, all success checks pass (exit 0, no failed process, every daemon at the same height), wall under 45 min (phantom took 43 min
on 32 threads, the simbox3 VM 79 min), `monerod-sim` provenance equal to phantom's line for line apart from `built:` and the hashes of the
binary itself. Prior 85%. Outside the range, or a provenance line that differs, means a platform effect and no headline cell runs there until it is understood.

*Outcome, 2026-10-24 06:17:* **hit on all four clauses.** Light-node share **0.0624** (the driver's `light_out_share`; phantom 0.0610, simbox2
0.0614, simbox3 0.0641), inside 0.055-0.066; Shadow wall 41 min 48 s (43 min with the driver's scoring), under 45; all five success checks
pass, 124 nodes online at 100% sync, height 1676, 0 failed processes and no panic in the Shadow log; `monerod-sim` provenance equal to
phantom's apart from `built:` (sha256 `bb53709e...`, 9 patches). `zenith2alpha` is validated and takes the lab's headline cells from here.
Estimators and the register entry in E31.

**P23, filed 2026-10-24 06:17, before the cell is queued (P21's seed replicate on the Threadripper).** `lean_24_none_h300_k42_w24h_m1_n600_fx_s23456`
on `zenith2alpha` (md5 `93e4bfa5`; the first cell generated on the control box, with `make_cell.sh`): E27's spread fleet (42 spies in 42 /24s at
1 each, 384 daemons) at a 24 h warmup, seed 23456, window 26-30 h. E27b replicated E27 to 1% at this seed (0.334 against 0.3369). Light-node
share **0.31-0.35** (P21's range) and **0.95-1.05x P21's value** once P21 lands (~07:30); by quarter flat (Q4 within 5% of Q1); relays 1.05-1.2x
light; users 0.09-0.15; 20-30 of 40 users exposed (wider than P21's 22-30: E27b's user clause missed on a 25% user-level seed spread). Prior 75%.
Wall under 2.5 h (phantom's P21 takes ~4 h on 16 workers; this box runs 32). Both inside 0.31-0.35 but outside 0.95-1.05x of each other means
the 24 h steady state is seed-sensitive at the few-percent level; either outside the range means the spread fleet has no seed-stable steady state.
*Outcome, 2026-10-24 09:46:* **four of seven.** Light **0.3524** (0.31-0.35 missed by 0.002; 1.051x P21's 0.3354, the 0.95-1.05x band
missed by 0.001x), quarters 0.3512-0.3527 (+0.4%, hit), relays 0.4002 = 1.14x light (hit), users 0.1046 (hit), 29 of 40 exposed (hit), lowest
free RAM 160 GB, wall 3 h 16 m with Shadow at 32 workers (under 2.5 h missed: twice phantom's workers gained 13%). Read as seed sensitivity
at the 5% level rather than the filed "no seed-stable steady state". E34.

**P24, filed 2026-10-24 06:24, before the cell is queued (open question 10's probe: the white-list pick made uniform).**
`lean_24_none_h300_k42_w13h_m1_n600_up_s12345` on `zenith2alpha` after P23 (md5 `33ca7b5b`; E27's cell plus `--sim-uniform-whitelist-pick`
on every daemon, the only differing line): the spread fleet (42 spies in 42 /24s, 384 daemons) at a 13 h warmup, window 15-19 h, seed 12345.
E27 read **0.3369**, 2.20x the subnet model's 0.1531, with a start-order gradient (earliest-started relays ~1.5x the ceiling, latest ~3.5x)
that E21 traced to monero's recency-biased white-list pick (`get_random_index_with_fixed_probability`, a cubic draw). The patch replaces that
draw with a uniform one over the same candidates. If E21's reading is right: (a) light-node share **0.13-0.19** (0.85-1.25x the ceiling);
(b) the gradient is gone: in `spy_share_vs_time` the latest-started quarter of relays reads at most 1.3x the earliest-started one over
hours 15-19; (c) every daemon's log has the `--sim-uniform-whitelist-pick` line; (d) at most 20 of 40 users exposed (E27: 27). Prior 60%.
At or above 0.28 (1.8x) the recency pick is not the cause and open question 10 goes back to the lists' age structure and the cap of 20;
0.19-0.28 means it is part of the cause. Wall under 1.5 h there (E27 took ~2.5 h on phantom).
*Outcome, 2026-10-24 13:58:* **one of five.** Light **0.3207** (2.09x the ceiling; 0.13-0.19 missed, the 0.28-and-above branch applies),
gradient intact (latest-started relays 2.6x the earliest over hours 15-19; "at most 1.3x" missed), flag line in all 382 daemon logs (hit),
28 of 40 exposed ("at most 20" missed), wall 2 h 15 m ("under 1.5 h" missed). The recency bias of the draw is not the cause; see E35.

**P25, filed 2026-10-24 06:24, before the cell is queued (the rebuilt binary's flag-off check).** `lean_legacy_none_h71_k1_s12345` on `phantom`
after P21, with `monerod-sim` rebuilt from all ten patches and the new flag **off** (as every cell without `_up` has it): light-node share
**0.055-0.066** (phantom read 0.0610 on the nine-patch binary; the four boxes' same-seed reads span 0.061-0.064, so bit-equality is not a
test Shadow offers), all five checks, wall under 50 min, the run's `binary_provenance.txt` lists ten patches, and no daemon logs the
uniform-pick line. Prior 90%: the flag-off path is unchanged by inspection; this is the platform-range check every binary change has had
(P9/E20, P22/E31). Outside the range means the build, not the flag, changed something, and no `_up` cell is read until that is understood.

*Outcome, 2026-10-24 08:14:* **hit on all clauses.** Light **0.0628** (nine-patch binary on the same box: 0.0610; the four-box spread 0.061-0.064),
quarters 0.0622, 0.065, 0.0597, 0.064; all five checks, 124 nodes at 100% sync; wall 44 min; the run's `binary_provenance.txt` lists ten patches
(`monerod-sim` sha256 `b8d6fbb6...`); 124 daemon outputs in the archive, all with the dedup patch's startup line, none with the uniform-pick line. E33.

**P26, filed 2026-10-24 14:41, before the cell is queued (open question 10: the candidate cap lifted and the draw uniform).**
`lean_24_none_h300_k42_w13h_m1_n600_up_wc0_s12345` on `zenith2alpha` (md5 `1c7d3c44`; P24's cell plus `sim-whitelist-candidates: 0`, the only
differing line), on the eleven-patch binary (`patches/monero-sim-whitelist-candidates.patch`: `--sim-whitelist-candidates N` replaces the stock
path's cap of 20 on the subnet-deduplicated, `last_seen`-ordered white-list candidates; 0 = every unconnected /24 is a candidate). With the cap
lifted and the draw uniform (P24's flag) the pick is uniform over every unconnected /24 in the relay's white list: the subnet model's assumption
made literal. The Monte Carlo over E21's 540 relay lists gives, per slot, 0.1905 for the stock draw (2.3x that cell's 0.0822 ceiling), 0.2172
for the uniform draw over the same 20, and **0.0796 (0.97x)** with the cap lifted. If E35's reading is right: (a) light-node share **0.13-0.19**
(0.85-1.25x the ceiling 0.1531; E27 0.3369, P24 0.3207); (b) the start-order gradient gone, the latest-started quarter of relays at most 1.3x
the earliest over hours 15-19 (P24: 2.6x); (c) every daemon log carries the `--sim-whitelist-candidates 0` line; (d) at most 20 of 40 users
exposed (E27 27, P24 28); (e) relays within 1.25x the ceiling. Prior 70%. At or above 0.28 the cap is not the mechanism either and the excess
must sit in the lists' composition (which /24s are in the white list at all, open question 8); 0.19-0.28 means the cap is part of it and
something else remains. Wall under 2.5 h (P24 took 2 h 15 m).
*Outcome, 2026-10-24 18:40:* **five of six.** Light **0.1577** (1.03x the ceiling; 0.13-0.19 hit), gradient gone (latest-started quarter 1.26x
the earliest over hours 15-19; "at most 1.3x" hit, though the earliest quarter sits 18% below the ceiling and the second 1.40x above it), both
flag lines in all 382 daemon logs (hit), relays 0.1562 = 1.02x (hit), wall 2 h 28 m ("under 2.5 h" hit by two minutes); **37 of 40 users exposed
("at most 20" missed)**: the users' own share rose from 0.103 to 0.165 while the relay-dominated aggregate fell. The cap is the multiplier; the
exposure clause was wrong about what exposure follows. See E36.

**P27, filed 2026-10-24 14:42, before the cell is queued (the cap lifted, the stock draw kept).** `lean_24_none_h300_k42_w13h_m1_n600_wc0_s12345`
on `zenith2alpha` behind P26 (md5 `3ac6e34d`; E27's cell plus `sim-whitelist-candidates: 0`, the only differing line): every unconnected /24 is a
candidate but the draw stays the stock cubic one, which over a long `last_seen`-ordered list concentrates on its newest few. The Monte Carlo over
E21's relay lists (mode `24allc`) gives **0.1242 per slot, 1.51x** the ceiling, against 2.3x with the cap and 0.97x with the cap lifted and the draw
uniform. The pair P26/P27 separates the two halves of the stock rule: the cap (which 20 are drawable) and the draw's shape over whatever is
drawable. Light-node share **0.19-0.28** (1.25-1.8x the 0.1531 ceiling); the gradient reduced but present (latest-started quarter 1.3-2.5x the
earliest); flag line in every daemon log; 20-27 of 40 users exposed. Prior 60%. Below 0.19 means the cubic draw over the full list is as good as
uniform and only the cap mattered; at or above 0.28 means the draw over a long list recovers the whole excess by itself. Wall under 2.5 h.
*Outcome, 2026-10-25 00:50:* **two of five.** Light **0.1705** (1.11x; 0.19-0.28 missed low, the below-0.19 branch applies: the cap did the work),
gradient 1.28x ("1.3-2.5x" missed, just under, though monotone), flag line in all 382 logs (hit), 28 of 40 exposed ("20-27" missed by one), wall
2 h 15 m (hit). The cubic draw over the full list adds 8% and a faint gradient; the Monte Carlo's 1.51x for this case overstated it six-fold. See E37.

**P28, filed 2026-10-24 18:45, before the cell is queued (P26 at a second seed).** `lean_24_none_h300_k42_w13h_m1_n600_up_wc0_s23456` on
`zenith2alpha` behind P27 (md5 `975cee8e`; P26's cell with `simulation_seed: 23456`, the only differing line). E36's reading rests on one seed;
the family's seed band is about 5% on the aggregate (E27 0.3369 and E27b 0.334 at this seed; E34) and about 25% at the user level (P19). If E36
holds: (a) light-node share **0.145-0.170** (0.95-1.11x the ceiling 0.1531; P26 0.1577); (b) relays within 1.15x the ceiling and the latest-started
quarter at most 1.3x the earliest over hours 15-19; (c) both flag lines in every daemon log; (d) users' share **0.14-0.19** and **at least 32 of
40** users exposed (P26 0.1647 and 37; the stock cell 27-28), the exposure reading of E36; (e) the earliest-started quarter of relays again below
the ceiling, 0.75-0.95x (P26 0.82x; this clause asks whether that is structure or noise, prior 55% on its own). Prior 75% on (a)-(d). An aggregate
below 0.13 or above 0.19 means E36's 1.03x does not hold across seeds and the Monte Carlo's agreement was luck; fewer than 28 exposed means the
exposure rise was seed noise. Wall under 2.75 h.
*Outcome, 2026-10-25 00:50:* **three of five lettered clauses, plus the exposure half of (d).** Light **0.1557** (1.01x the seed's ceiling
0.1539; hit), relays 1.03x and gradient 1.02x (hit), both flag lines in all 382 logs (hit), 35 of 40 exposed (hit) but users 0.1391 against 0.14-0.19
(missed by 0.001), the earliest-started quarter 1.01x against 0.75-0.95x (missed: P26's dip was noise). Wall 2 h 15 m. P26 replicates to 1.3%. See E38.

**P29, filed 2026-10-25 00:40, before the cell is queued (the 24 h steady state with the cap lifted).** `lean_24_none_h300_k42_w24h_m1_n600_fx_up_wc0_s12345`
on `zenith2alpha` (md5 `527a8a60`; E32's cell, the 24 h spread fleet at seed 12345 with the fixed RandomX seed, plus `sim-uniform-whitelist-pick: true`
and `sim-whitelist-candidates: 0`, the only differing lines; window hours 26-30). Under the stock rule the 24 h read was flat at this seed (E32 0.3354
against E27 0.3369) and 5% up at seed 23456 (E34 0.3524 against E27b 0.334), the late-started relays' lists ageing into a deeper gradient. With the cap
lifted there is no gradient to deepen (E36, P28), so the day-old network should read what the 13 h cells read: (a) light-node share **0.145-0.170**
(P26 0.1577, P28 0.1557); (b) relays within 1.15x the ceiling and the latest-started quarter at most 1.3x the earliest over hours 26-30; (c) both flag
lines in every daemon log; (d) users' share 0.12-0.19 and at least 30 of 40 users exposed (P26 0.165 and 37, P28 0.139); (e) no drift: the four
quarters of the window within 3% of one another and no half hour between hours 6 and 30 above 0.19 in `spy_share_vs_time`. Prior 80%. Above 0.19
means something accumulates in the lists over a day that the 13 h cells did not show, even with every /24 drawable; below 0.13 means the longer
warmup lets the spies fall out of the lists. Wall under 3.5 h (P23's 24 h cell took 3 h 16 m at 32 workers).
*Outcome, 2026-10-25 04:20:* **four of five lettered clauses, and the wall.** Light **0.1655** (1.08x; hit), relays 1.07x and gradient 1.10x (hit), both
flag lines in all 382 logs (hit), users 0.1787 and 31 of 40 exposed (hit, at the edge), no half hour above 0.19 (highest 0.1743; hit) but the quarters span
3.2% against 3% (0.1682 to 0.1630, falling; missed by 0.2 points). Wall 3 h 18 m. Nothing accumulates over the day; recall 0.187 against the stock 24 h
cells' 0.134 and 0.109. See E39.

**P30, filed 2026-10-25 03:30, before the cell is queued (P26 at a third seed, and the first cell on simbox3's eleven-patch binary).**
`lean_24_none_h300_k42_w13h_m1_n600_up_wc0_s34567` on `simbox3` (md5 `e6e99b47`; P28's cell with `simulation_seed: 34567`, the only differing
line; the seed of the X0 replicates and of E10's third `tail` read). P26 (0.1577) and P28 (0.1557) sit 1.3% apart; a third seed fixes the band
of the cap-lifted spread fleet and doubles as the gate for simbox3's rebuilt binary (eleven patches, built 00:46, sha `14852a861c75`, provenance
equal to zenith2alpha's apart from `built:`). (a) light-node share **0.145-0.170**; (b) relays within 1.15x the seed's ceiling and the latest-started
quarter at most 1.3x the earliest over hours 15-19; (c) both flag lines in every daemon log; (d) users' share 0.12-0.19 and at least 30 of 40
users exposed (P26 0.165 and 37, P28 0.139 and 35); (e) the three-seed mean in 0.150-0.165 and the spread (largest minus smallest) at most 0.010.
Prior 80%. Outside 0.13-0.19 means either the 1.0x reading is seed-fragile or the simbox3 build differs in a way the provenance does not show
(then rerun the cell on zenith2alpha before reading anything into it). Wall under 6 h (simbox3's 40 vCPUs took 7 h for E30's 30 h cell; a 19 h
cell should take about 4.5 h; the stock 13 h cells took 2.5 h on phantom's 32).
*Outcome, 2026-10-25 08:40:* **five of five clauses, and the wall.** Light **0.1482** (0.97x this seed's 0.1523; hit, at the low edge), relays 0.965x and
gradient 1.08x (hit), both flag lines in all 382 logs (hit), users 0.1521 and 39 of 40 exposed (hit), three-seed mean 0.1539 and spread 0.0095 (hit, the
spread at the edge). Wall 4 h 27 m. The rebuilt binary passes its gate. See E41.

**P32, filed 2026-10-25 09:00, before the cell is queued (P31 at a second seed).** `lean_24_half_h300_k42_w13h_m1_n600_up_wc0_s23456` on
`zenith2alpha` (md5 `75763cc9`; P31's cell with `simulation_seed: 23456`, the only differing line apart from the ban-list file's name; the 42-line
list and the 165-node adopter set are identical to P31's, checked). P31's 0.49x and "non-adopters at exactly their ceiling" rest on one seed; the
family's seed band is about 5% on aggregates (E27/E27b, P26/P28) and about 25% at the user level. At this seed the fleet's ceiling is 0.1539 (240
honest /24s), so the half-list model gives the light nodes 0.1539 x 140/281 = 0.0767. (a) light-node share **0.070-0.095** (P31 0.0771); (b)
adopters at **0.000** and the non-adopting relays' own share 0.92-1.10x the ceiling (P31 1.005x); (c) both flag lines in every daemon log; (d)
users' share 0.06-0.10 and **12-20 of 40** users exposed, all among the 20 non-adopters (P31 15); (e) the four quarters of the window within 8%
(P31 7.5%; the 3% clause of P31 was too tight for this share level, E40) and the latest-started relay quarter 0.7-1.3x the earliest (P31 0.89x; the
quarters mix adopters and non-adopters). Prior 80%. Wall under 3 h (P31 2 h 18 m). The twelfth patch (20 random /24 candidates in place of the 20
newest) is being written while this runs; its cell will be filed separately and queued behind this one.
*Correction, 2026-10-25 10:23:* this prediction was filed at about 10:20 UTC (commit `1b2002a3`), not 09:00: the time above was written from
an assumed elapsed time, not from the clock. The order holds: the commit preceded the cell's start at 10:22.
*Outcome, 2026-10-25 12:51:* **five of five clauses, and the wall.** Light **0.0764** (1.00x the half-list model 0.0767, 0.49x P28; hit), adopters 0.0000 and
the non-adopting relays 1.01x (hit), both flag lines in all 382 logs (hit), users 0.0728 and 17 of 40 exposed, all non-adopters (hit), quarters 2.1% apart and
the start-order quarter 1.02x (hit). Wall 2 h 19 m. See E42.

**P33, filed 2026-10-25 10:35, before the cell is queued (P31 at a third seed, on simbox3).** `lean_24_half_h300_k42_w13h_m1_n600_up_wc0_s34567`
on `simbox3` (md5 `0252e259` as generated; `e3407251` as copied to simbox3, where the 165 `ban-list:` paths are rewritten from this clone's
`/home/antiproxy/monerosim/` to that account's `/home/lever65/monerosim/`, the only change; P31's cell with `simulation_seed: 34567` otherwise, the
42-line list and the 165-node adopter set identical). The user asked for the idle box to be used; a third seed of the half list costs no code and
gives the half-list family what the no-list family has (P26/P28/P30). It runs on simbox3's twelve-patch binary with the twelfth flag off, so it is
also that build's flag-off check. At this seed the ceiling is 0.1523 (243 honest /24s) and the half-list model gives 0.1523 x 140/281 = 0.0759.
(a) light-node share **0.070-0.095** (P31 0.0771); (b) adopters at **0.000** and the non-adopting relays' own share 0.92-1.10x the ceiling (P31
1.005x); (c) both flag lines in every daemon log and the twelfth patch's start-up line in none; (d) users' share 0.06-0.10 and **12-20 of 40** users
exposed, all among the 20 non-adopters (P31 15); (e) the four quarters within 8% and the latest-started relay quarter 0.7-1.3x the earliest.
Prior 80%. Wall under 6 h (P30 took 4 h 27 m on this box).
*Outcome, 2026-10-25 20:44:* **five of five clauses, and the wall.** Light **0.0792** (1.04x the half-list model 0.0759, 0.53x P30; hit), adopters 0.0000
and the non-adopting relays 1.05x (hit), both flag lines in all 382 logs and the twelfth in none (hit), users 0.0723 and 17 of 40 exposed, all non-adopters
(hit), quarters 4.5% apart and the start-order quarter 0.93x (hit). Wall 4 h 35 m. Three seeds: 1.00-1.04x the model, 0.49-0.53x the no-list cell. See E44.

**P34, filed 2026-10-25 10:39, before the cell is queued (the twelfth patch: 20 random /24 candidates in place of the 20 newest, the stock cubic
draw kept).** `lean_24_none_h300_k42_w13h_m1_n600_rc_s12345` on `zenith2alpha` behind P32 (md5 `14d453a7`; E27's stock spread-fleet cell plus
`sim-random-whitelist-candidates: true`, the only differing line; the cap of 20 and the cubic draw are stock). The question is whether a bounded
candidate set drawn at random, the cheapest realistic change to the stock rule, does what lifting the cap did. The Monte Carlo over E21's 540 relay
lists (`recency_relays.py`, modes added 2026-10-25) gives, per slot against that cell's 0.0822 ceiling: stock 0.1912 (2.33x), the same 20 drawn
uniformly 0.2172, every unconnected /24 drawn uniformly 0.0808 (0.98x), every unconnected /24 with the cubic draw 0.1246 (1.52x), **20 random /24s
with the cubic draw 0.1256 (1.53x)**, 20 random /24s drawn uniformly 0.0797 (0.97x). The model puts the random sample with the cubic draw exactly
where it puts the cap lifted with the cubic draw, and for that case the model said 1.51x where the sim read 1.11x (P27, 0.1705): its lists come from
the stock regime and overstate the spies' recency edge once the rule changes. So the prediction leans on P27, with the model's number as the upper
reference: (a) light-node share **0.160-0.210** (1.05-1.37x the 0.1531 ceiling; point estimate 0.175); (b) relays 1.0-1.45x the ceiling and the
latest-started quarter at most 1.4x the earliest over hours 15-19 (stock: 3.5x against 1.5x; cap lifted: 1.02-1.26x); (c) the twelfth patch's
start-up line in every daemon log and neither of the other two `--sim-*` lines in any; (d) users' share 0.10-0.19 and 28-38 of 40 users exposed;
(e) the four quarters within 5%; (f) within 0.025 of P27's 0.1705 at the same seed (0.145-0.196), the clause that says the random sample is worth
what the lifted cap is worth. Prior 65% on (a), 70% on (f). Above 0.215 means the model is right and a random sample does not remove the recency
edge, because the newest of any 20 is still a spy often enough; at or below 0.160 the sample alone reaches the ceiling and the draw's shape is worth
nothing here. Wall under 3 h.
*Outcome, 2026-10-25 15:13:* **six of six clauses, and the wall.** Light **0.1657** (1.08x; hit), relays 1.08x and gradient 1.28x (hit), the twelfth
line in all 382 logs and the others in none (hit), users 0.1623 and 31 of 40 exposed (hit), quarters 4.1% apart (hit), within 0.005 of P27 (hit). Wall
2 h 16 m. The random sample is worth what the lifted cap is worth; the Monte Carlo's 1.53x was wrong again. See E43.

**P35, filed 2026-10-25 10:39, before the cell is queued (P34 at a second seed, on simbox3).** `lean_24_none_h300_k42_w13h_m1_n600_rc_s23456` on
`simbox3` behind P33 (md5 `ed53b8cb`; P34's cell with `simulation_seed: 23456`, the only differing line; this seed's ceiling 0.1539). The same
clauses as P34 with the seed's ceiling, (f) replaced by: within 0.015 of P34's read (the family's 5% seed band). Prior 65%. Wall under 6 h.
*Outcome, 2026-10-25 20:49:* **six of six clauses, and the wall.** Light **0.1716** (1.12x; hit), relays 1.16x and gradient 1.15x (hit), the twelfth line in all
382 logs and the others in none (hit), users 0.1376 and 32 of 40 exposed (hit), quarters 4.4% apart (hit), within 0.006 of P34 (hit). Wall 4 h 32 m. Two
seeds 1.10x: the random sample equals the lifted cap with the same draw. See E47.

**P36, filed 2026-10-25 15:16, before the cell is queued (the stock rule with the white list trimmed to the lab's ratio; the plan review's item 1,
lab half).** `lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_s12345` on `zenith2alpha` (md5 `b432abe4`; E27's stock spread-fleet cell plus
`sim-white-peerlist-limit: 70` and `--probe 3`, twelve relays at the head and tail of each start order dumping their peer lists every 30 s with
`net.p2p` at DEBUG, the only differences; thirteen-patch binary, sha `ab6646d7`). Why 70: mainnet's white list holds 1,000 entries against
about 4,600 reachable nodes (0.22), and the lab has 342 reachable, so 70 keeps that fraction; the gray list's 5,000 is left stock because it
binds in neither place at the lab's size (and on mainnet only through the fleet's 16,000 port instances, a separate question). Mechanism: the
white list is trimmed oldest-`last_seen` first, so each relay's list holds its 70 most recently seen peers and the stock pick's 20-newest cap
draws from those. Under the stock rule the spies sit at rank 0.39 of the untrimmed lists (E21), so the trim should drop honest entries before
spies and the multiplier should hold or rise. (a) light-node share **0.28-0.50** (point estimate 0.37; E27 untrimmed 0.3369); (b) the ratio to
E27 at least 0.9x; (c) in every probe dump after hour 1 the white list holds at most 70 entries (the limit binds: 342 reachable > 70) and the
spies' mean rank percentile in it is below 0.5 (E21 0.39); (d) the thirteenth patch's start-up line in all 382 daemon logs; (e) users 0.08-0.16
and 22-34 of 40 exposed (E27 0.133 and 27). Prior 60% on (a), 75% on (b). Below 0.28 means a recency trim drops spies as readily as honest
entries and the stock multiplier is a whole-list effect; above 0.50 means a trimmed list concentrates the spies further, and mainnet's capped
lists would make today's exposure worse than the lab's 2.2x. Wall under 3 h.
*Outcome, 2026-10-25 20:49:* **three of five clauses, and the wall.** Light **0.1616** against 0.28-0.50 (missed, far below: 1.06x the ceiling, 0.48x E27),
the ratio to E27 missed, the lists at 70 entries with the spies at rank 0.38-0.49 (hit), the thirteenth line in all 382 logs (hit), users 0.1362 and 30
of 40 exposed (hit). Wall 2 h 18 m. The trim alone removes the multiplier; the spies are under-represented in a recency-trimmed list. See E45.

**P37, filed 2026-10-25 15:16, before the cell is queued (the cap lifted and the uniform draw with the white list trimmed; the transfer test for
the fix).** `lean_24_none_h300_k42_w13h_p3_m1_n600_up_wl70_wc0_s12345` on `zenith2alpha` behind P36 (md5 `f248109b`; P26's cell plus the same
limit and probes, the only differences; against P36 the two flag lines are the only difference). With every unconnected /24 of the trimmed list
drawable, the share is the spies' fraction of the 70 newest entries' /24s; if the spies' rank advantage carries into the top fifth of the list,
that fraction exceeds their 0.148 of the pool's /24s. (a) light-node share **0.16-0.30** (P26 untrimmed 0.1577 = 1.03x; point estimate about
0.21, 1.4x); (b) relays and users within 25% of each other (no class-specific lock-in); (c) the probes' lists at most 70 entries and the spies'
share of their entries above 0.15 (their share of the pool's IPs is 42 of 342 = 0.123, of its /24s 0.148); (d) both flag lines and the
thirteenth patch's line in all 382 logs; (e) the four quarters within 5%. Prior 50% on (a). Wall under 3 h. Reading rule: the pair is read as
P37/P36 against the untrimmed 0.47 (P26/E27). At or below 0.17 (1.1x) the fix survives a trimmed list in the lab and the question passes to
the mainnet dump (open question 8); above 0.23 (1.5x) the fix's benefit depends on the list holding everyone, and the recommendation needs a
list-management change (N2, or a per-/24 cap on entries) beside it.
*Outcome, 2026-10-25 20:49:* **four of five clauses, and the wall.** Light **0.1619** in 0.16-0.30 (hit, at the floor: 1.06x, P37/P36 = 1.00), relays and
users within 25% (hit), the lists at 70 entries (hit) but the spies' share of them 0.09-0.10 against "above 0.15" (missed, below the pool's share), the
three lines in all 382 logs (hit), quarters 3.0% apart (hit). Wall 2 h 17 m. With the trim the stock pick already draws the spies at their share. See E46.

**P38, filed 2026-10-25 20:42, before the cell is queued (the stock rule under peer turnover; the plan review's item 3, the honest-cost
baseline).** `lean_24_none_h300_k42_w13h_p3_m1_n600_to1h1h_s12345` on `zenith2alpha` (md5 `c7666148`; E27's stock spread-fleet cell plus
`general.turnover` (mean online session 1 h, mean offline gap 1 h, both exponential, fraction 1.0: every relay, user, medium node and observer
cycles, restarting on its own data dir; miners and seeds stay up) and the twelve probe relays, the only differences; thirteen-patch binary).
Read for connectivity cost, not exposure: the users' daemons cycle too, so their transaction counts fall (the X0 pilot with this turnover saw
about 10x fewer), and the exposure numbers are reported but not scored. Clauses: (a) exit 0 and the chain reaches height 1,900 by hour 19
(the always-on miners keep producing); (b) light-node share over the window **0.20-0.45** (E27 without turnover 0.3369; stale entries dilute
the recency edge, by how much is the question); (c) each probe relay restarts at least three times in 19 h (about nine sessions expected);
(d) the new cost scorer reports, per relay session, the time from start to 12 outbound connections and the failed dials per relay-hour from
the probes' DEBUG logs: baseline numbers, nothing predicted; (e) wall under 4 h. Prior 55% on (b).

**P39, filed 2026-10-25 20:42, before the cell is queued (the cap lifted and the uniform draw under peer turnover; the honest cost of
removing the recency filter).** `lean_24_none_h300_k42_w13h_p3_m1_n600_up_to1h1h_wc0_s12345` on `zenith2alpha` behind P38 (md5
`f9df10fb`; P38's cell plus the two flag lines, the only difference). The 20-newest cap is a liveness filter where peers churn; with every
unconnected /24 drawable the pick lands on offline entries more often, which should show as failed dials and slower slot filling, not as
spy share. (a) exit 0 and height 1,900 by hour 19; (b) light-node share **0.12-0.22** (P26 without turnover 0.1577); (c) against P38, failed
dials per relay-hour at least 1.5x and the median time from a session's start to 12 outbound connections at least 1.2x; (d) wall under 4 h.
Prior 65% on (c). A (c) miss means the recency filter buys nothing measurable at this churn and the new rules cost nothing here; a (c) hit
puts a number on what the cubic draw's recency preference is for, which the recommendation then has to weigh.
*Note, 2026-10-25 23:16:* P38's cell ran with only the 40 users cycling. The generator keeps any daemon with `hide-my-port: false` up as a
pinned supernode, and every reachable node in the lean cells sets it (`make_lean.py --turnover`'s help said "non-pinned"; the clauses above
assumed every relay cycled). P38's outcome is under E48; P42 is the cell P38 meant. *Outcome, 2026-10-25 23:19:* **two of four scorable clauses**: (a) exit 1 (missed; height 1,993, hit), (b) 0.3512 (hit, on
a cell without relay churn), (c) no relay restarted (missed), (e) wall 2 h 15 m (hit); (d) reported for the users only. See E48. *Withdrawn, 2026-10-25 23:16:* P39 started at 23:12 and the
agent stopped it at 23:13, the same defect making its (c) untestable; P43 carries its clauses on the intended cell.

**P40, filed 2026-10-25 20:42, before the cell is queued (the stock rule with the white list trimmed to 140 entries; the trim sweep's
upper point).** `lean_24_none_h300_k42_w13h_p3_m1_n600_wl140_s12345` on `simbox3` (md5 `b90cce1f`; P36's cell with the limit at 140, the
only difference). P36 read 0.1616 at 70, 1.06x the ceiling against 2.20x with no limit (342 entries hold everyone), so the multiplier
appears somewhere between 70 and 342. (a) light-node share **0.18-0.32** (1.2-2.1x); (b) the probes' white lists hold at most 140 entries
after hour 1; (c) the stock-rule family's start-order gradient present if (a) is above 0.22 (the latest-started quarter above 1.3x the
earliest); (d) wall under 6 h. Prior 50% on (a). At or below 0.17 the multiplier needs nearly the whole network in the list, and mainnet's
capped lists make the lab's 2.2x a lab artefact; above 0.32 the multiplier is already full at 140 and the trim's effect is a threshold near
the candidate cap's size. *Outcome, 2026-10-26 04:25:* **two of four**: (a) **0.1640**, missed below 0.18 (1.07x the ceiling, flat with the 70 point's 1.06x — at 0.41 of the pool the multiplier is already gone, so it needs a list holding nearly every /24); (b) hit (the probes' white lists exactly 140 after hour 1, the spies 6.5-10.4% of entries, mean 8.8%, at rank 0.48; gray ~199 at 14.8%); (c) does not apply; (d) hit (274 m). E49; run 87.

**P41, filed 2026-10-25 20:42, before the cell is queued (the stock rule with the white list trimmed to 35 entries; the trim sweep's lower
point).** `lean_24_none_h300_k42_w13h_p3_m1_n600_wl35_s12345` on `simbox3` behind P40 (md5 `460f0c7d`; the limit at 35, the only
difference from P36). With 35 entries and about 12 connected, the white list offers fewer than the cap's 20 unconnected /24s, so the stock
pick draws every unconnected entry and falls back to the gray list more often. (a) light-node share **0.13-0.19** (0.85-1.25x); (b) the
probes' lists at most 35 entries; (c) wall under 6 h. Prior 65% on (a). Reading rule for the sweep (35, 70, 140, unlimited): the limit at
which the share leaves the ceiling, against mainnet's 1,000 of ~4,600 reachable (0.22 of the pool; the lab's 70). *Outcome, 2026-10-26 07:36:* **three of three**: (a) **0.152**, hit (0.99x the ceiling); (b) hit (every probe exactly 35 entries after hour 1; the spies 3.0 of 35, below their pool share, and the freshest entries in the list); (c) hit (275 m). E50; run 89.

**P42, filed 2026-10-25 23:16, before the cell is queued (P38's intended cell: the stock rule with the reachable honest nodes cycling as well).**
`lean_24_none_h300_k42_w13h_p3_m1_n600_tor1h1h_s12345` on `zenith2alpha` (md5 `a6af1793`; P38's cell plus `turnover: true` on the 233 relays,
48 medium nodes and 8 observers, the only difference; `make_lean.py --turnover-reachable`, generator at `5115b02b`). The generator's dry run
gives the relays 5-16 daemon sessions (mean 9.7), the medium nodes 6-16, the observers 5-13, the users 7-16, and the miners, seeds and 42 spies
one each. About half the honest reachable nodes are offline at any moment while every spy stays up, so the spies' share of the online /24s
roughly doubles (about 42 of 178 against 42 of 274; a ceiling near 0.24 if the outbound share follows the online /24s), which P38's band did not
allow for. A stress case: the lab's churn assumption has relays mostly up. (a) exit 0 and the chain at height 1,900 by hour 19; (b) light-node
share **0.25-0.55** (the online-/24 ceiling of about 0.24 times 1.0-2.2); (c) `churn_cost.py` finds each probe relay's sessions in its log (its
session count from the start-up banner equal to the config's), the first test of its session split on restarting relays; (d) baseline numbers,
nothing predicted: per relay session the time from start to 12 outbound connections, and failed dials per relay-hour by class; (e) wall under
4 h. Prior 50% on (b).
 *Outcome, 2026-10-26 08:06:* **four of four** ((d) a baseline, not predicted): (a) hit (exit 0; height 2,078 by hour 19); (b) **0.3936**, hit (1.64x the online ceiling); (c) hit — `churn_cost`'s session counts equal the config's (relays mean 9.7; its first run against real restarts); (d) the baselines: restart fill 1.6 m median / 5.0 m p90, 2.85 connect + 1.77 handshake failures per relay-hour, 32 of 2,267 sessions unfilled; (e) hit (219 m). E51; run 91.

**P43, filed 2026-10-25 23:16, before the cell is queued (P39's intended cell: the cap lifted and the uniform draw with the reachable nodes
cycling).** `lean_24_none_h300_k42_w13h_p3_m1_n600_up_tor1h1h_wc0_s12345` on `zenith2alpha` behind P42 (md5 `395466ca`; P42's cell plus the
two flag lines, the only difference). P39's clauses carried over, the share band moved for the online-/24 ceiling: (a) exit 0 and height 1,900
by hour 19; (b) light-node share **0.17-0.30** (near the online-/24 ceiling, as the lifted cap reads the ceiling without churn); (c) against
P42, failed dials per relay-hour at least 1.5x and the median time from a session's start to 12 outbound connections at least 1.2x (P39's
clause unchanged); (d) wall under 4 h. Prior 65% on (c), 55% on (b). P39's reading rule stands: a (c) miss means the recency filter buys
nothing measurable at this churn, a (c) hit puts a number on what it buys. *Outcome, 2026-10-26 11:40:* **two of four**: (a) hit (exit 0; height 2,061); (b) **0.3237**, missed above (1.35x the online ceiling — the ceiling model undercounts under churn); (c) **missed in the other direction** — the lifted cap is cheaper, not costlier: 1.37 against 2.85 connect-failures per relay-hour and fill 1.7 m against 1.6 m, so the recency filter buys nothing measurable at this churn; (d) hit (211 m). E52; run 92.

**P31, filed 2026-10-25 03:30, before the cell is queued (the half ban list with the cap lifted).** `lean_24_half_h300_k42_w13h_m1_n600_up_wc0_s12345`
on `zenith2alpha` behind P29 (md5 `49e10cf7`; E29's cell, the full 42-/24 list on half the honest nodes, 165 adopters and 175 non-adopters with
20 of the 40 users adopting, plus `sim-uniform-whitelist-pick: true` and `sim-whitelist-candidates: 0`, the only differing lines apart from the
ban-list file's name and path; the 42-line list itself is byte-identical to E29's). The question is whether the list's benefit survives once the
multiplier is gone. Under the stock rule the list halved the light share (E29: 0.184 against 0.3369, 0.55x) and the non-adopters carried 10% more
than without it. With the cap lifted the no-list cell reads the ceiling (P26 0.1577, P28 0.1557), and under the subnet model the adopters read zero
and the non-adopters their own ceiling, so the aggregate should be the non-adopting half of P26: (a) light-node share **0.070-0.100** (0.45-0.63x
P26's 0.1577; 0.079 if the non-adopters carry nothing extra, 0.086 if they carry E29's +10%); (b) adopters (165 nodes) at **0.000** and the
non-adopting relays' own share 0.92-1.24x the ceiling (the relays' class share 0.070-0.095); (c) both flag lines in every daemon log; (d) users'
share 0.06-0.10 (the 20 non-adopting users at P26's 0.165 give 0.082) and **14-20 of 40** users exposed (E29 15 of 40 under the stock rule with
the non-adopting users at 0.106; P26 37 of 40 with no list), the exposed ones expected among the non-adopters; (e) flat: the four quarters of the
window within 3% and the latest-started relay quarter at most 1.3x the earliest. Prior 75% on (a)-(c), 65% on (d). Above 0.11 means the list pushes
the spies' slots onto the non-adopters beyond their own ceiling, which the subnet model does not allow; below 0.06 means the adopters' bans drain
the spies from the non-adopters' lists as well (the adopters passing on fewer spy addresses). Either way the list's ratio to its no-list cell is the
number to carry forward against E29's 0.55x. Wall under 3 h (P26 2 h 31 m, P28 2 h 15 m on this box).
*Outcome, 2026-10-25 06:50:* **four of five lettered clauses, and the wall.** Light **0.0771** (0.49x P26, 1.01x the half-list model; hit), adopters 0.0000
and the non-adopting relays 1.005x the ceiling (hit), both flag lines in all 382 logs (hit), users 0.0772 and 15 of 40 exposed, all non-adopters (hit), the
start-order quarter 0.89x (hit) but the window's quarters span 7.5% against 3% (missed: the clause was too tight for a 0.08 share). Wall 2 h 18 m. See E40.

**P44, filed 2026-10-26 07:36, before the cell is queued (the stock rule under the OQ13 active adversary; E27's spread fleet, seed 12345).**
`lean_24_none_h300_k42_w13h_p3_m1_n600_sr300_ud_s12345` on `simbox3` (E27's cell plus `--spy-refresh 300 --user-dumps --probe 3`: every spy also runs `agents.spy_refresh` v2 — front ports 18090..18153, rotation 1800 s, the daemon's identity and chain served on each). The smoke read 12.7x its ceiling on a 1-spy-/24 cell; the spread fleet's 42 spy /24s can hold the whole newest-20 cut. (a) light-node share **0.40-0.75** (2.6-4.9x the 0.1531 ceiling; the passive stock read 0.3369, the capped cells 1.06x); (b) the users' share **at or above 0.9x the ceiling** (the stock users sat at 0.75x; the smoke's front entries reached the unreachable users through gray-list dials, so the accidental protection should not survive); (c) the probes' freshest spy entry at most 3600 s old (two rotations) in every dump, at least 10 spy entries per probe (the accumulated fronts), freshest spy rank at most 0.15; (d) wall under 8 h (the smoke's wall doubled under the responder load). Prior 55% on (a). Reading rule: at or below 0.34 the stock lock-in defends even against the newest entries; at or above 0.75 the capture saturates toward the eclipse regime and the defense question changes shape. *Outcome, 2026-10-26 12:31:* **three of four, and the miss is the result**: (a) **0.9083**, missed far above (5.93x; the eclipse regime the reading rule reserved); (b) hit, inverted — 40/40 users exposed, combined recall 0.967 at precision 1.000, users' p_out median 1.0; (c) hit (freshest spy rank 0.000 everywhere, fronts ~110 s, 41-42 spy entries per node, white 341 with nothing evicted); (d) hit (271 m). E53; run 93.

**P45, filed 2026-10-26 07:36, before the cell is queued (P44 at seed 23456).** `lean_24_none_h300_k42_w13h_p3_m1_n600_sr300_ud_s23456` on `simbox3` behind P44; clauses (a)-(d) as P44, read as the replicate (P26/P28 spread ±1% at two seeds; a miss beyond ±0.05 on (a) is a seed effect to investigate, not noise). *Outcome, 2026-10-26 14:05:* replicated to 0.09%: (a) **0.9075**, missed above identically; (b) hit (40/40, combined 0.969 at 0.997); (c) hit (the dumps identical: rank 0.000, 42 spy entries per node, fronts ~118 s); (d) hit (146 m). E54; run 94.

**P46, filed 2026-10-26 12:31, before the cell is queued (the uniform draw against the active adversary).** `lean_24_none_h300_k42_w13h_p3_m1_n600_up_sr300_ud_wc0_s12345` on `simbox3` (P44's cell plus `--uniform-pick --wl-cands 0`: the draw is uniform over every unconnected subnet-deduplicated /24 — no newest cut). With the fronts the newest entries in every list (E53), any newest-cut rule draws only spies; the uniform draw ignores recency, and the spies' share of the candidate /24s is their pool share (42 of 341). (a) light-node share **0.13-0.20** (0.85-1.3x the 0.1531 ceiling); (b) combined recall at or below 0.25 (against P44's 0.967) and the users' exposure returning toward the passive level; (c) the dump checks as P44 — fronts present, fresh and rank ~0, but no longer concentrated by the draw; (d) wall under 6 h. Prior 60% on (a). Reading rule: at or below 0.20 the uniform draw is the candidate set's survivor against the active adversary; above 0.30 nothing in the set survives and the recommendation reverts to the list defenses (the ban list, E29/E40). *Outcome, 2026-10-26 17:22:* **two of four**: (a) **0.5994**, missed above (3.9x; above the 0.30 reading-rule threshold — nothing in the set survives); (b) missed (combined recall 0.391 at 0.993, against 0.25); (c) hit (the fronts present and fresh everywhere, ~118 s, 42 per node); (d) hit (269 m). E55; run 95.

**P47, filed 2026-10-26 12:31, before the cell is queued (the trim against the active adversary).** `lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_sr300_ud_s12345` on `simbox3` behind P46 (P44's cell plus `--white-limit 70`: the white list trimmed to its 70 newest). E45 and E49 showed the trim reads the ceiling for a passive fleet; for an active one the trim keeps the newest — and the newest are the fronts: 42 of the 70 entries are spies (60% of the list against their 12.3% pool share) and every newest-20 cut is still all-spy. (a) light-node share **0.80-0.95** (at or above P44's 0.9083 within noise); (b) the probes' white lists exactly 70 with at least 40 spy entries; (c) dump checks as P44; (d) wall under 6 h. Prior 55% on (a). Reading rule: at or above 0.80 the trim is the adversary's amplifier — the flat-at-ceiling result is a property of a passive fleet only, and mainnet's capped lists would hand the active fleet a majority for free. *Outcome, 2026-10-26 22:09:* **two of four, both misses the finding**: (a) **0.0248**, missed far below (0.16x — the trim is the defense, not the amplifier); (b) missed below (the fronts evicted: 28-33 spy entries of 70, not at least 40); (c) hit (the surviving fronts fresh, 95-131 s); (d) hit (282 m). E56; run 96.

**P48, filed 2026-10-26 22:09, before the cell is queued (the arms race at its tightest: wl70 with a 60 s rotation).** `lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_sr300_ro60_ud_s12345` on `zenith2alpha` (P47's cell with the rotation at 60 s — 30x the insert rate, the fronts' ages then at or below the honest refresh cycle's 208-742 s). (a) light-node share, deliberately wide, **0.10-0.75**: below 0.10 the trim wins outright at any rotation; 0.10-0.45 a budget equilibrium (the trim prices the eclipse); above 0.45 the fast rotation restores it and the trim's protection is only budget-asymmetric. (b) the probes' spy entries at least 35 of 70 (the fast rotation should stop the evictions); (c) dump checks as P47; (d) wall under 6 h. Prior a third on each band of (a). Reading rule: this locates the defense on the dialing-budget axis — the number the mainnet recommendation needs. *Outcome, 2026-10-27 00:52:* **two of four, both misses confirming the defense**: (a) **0.0262**, missed below 0.10 (the trim wins outright at any measured rotation); (b) missed below (26-33 spy entries of 70, the evictions continue); (c) hit; (d) hit (144 m). E57; run 97.

**P49, filed 2026-10-27 11:45, before the cell is queued (the sweep budget decoupled: wl70 with 60 s sweeps).** `lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_sr60_ud_s12345` on `zenith2alpha` (E57's cell with the sweep at 60 s and the rotation back at the 1800 s default — the two dials now decoupled in the tooling; E57's closing line: to beat the trim the adversary must sweep each node faster than the ~150 s honest refresh cycle). At 60 s every front entry is at all times fresher than essentially every honest entry (E57 measured honest ages 151-917 s), so the newest-20 cut should flip spyward — unless the flywheel scales: every front insert evicts an honest entry and forces the redraw that refreshes it (E56), so 5x the inserts is also 5x the forced honest refresh. The two live hypotheses; the cell decides. (a) light-node share, three bands: below 0.05 the flywheel scales and the trim's protection is budget-independent; 0.05-0.45 a budget equilibrium (the trim prices the eclipse); above 0.45 the sweep cracks it and the trim is only budget-asymmetric. Prior 30/40/30. (b) the probes' spy entries at least 40 of 70 (fronts that never age past the horizon should stop being evicted — against E56/E57's 26-33); (c) the dumps: front ages at or below ~120 s, and the honest entry ages compressed against E57's 151-917 s (the flywheel signature — this clause separates the hypotheses whatever (a) does); (d) wall under 6 h (E57 ran 144 m at sr300; the 5x dial rate is agent-side, watch memory). Reading rule: the band locates the defense on the sweep-budget axis — the number the mainnet recommendation needs, because mainnet's newest-20 cut is minutes-fresh (1.4-8.8 m, OQ8), so a band win at 60 s sweeps is a live mainnet threat, not a lab artifact. *Outcome, 2026-10-27 14:20:* **two of four**: (a) **0.0239**, inside the flywheel band (< 0.05) — but the cell also found the axis saturates: the configured 60 s sweep delivered a ~1,076 s median front age (the agent's dial floor), so the band verdict holds at the lab's deliverable maximum, not at a true 60 s sweep; (b) missed below (24-34 spy entries of 70); (c) missed both halves (fronts 762-1,284 s, honest ages not compressed); (d) hit (152 m). E59; run 98.

**P50, filed 2026-10-27 11:45, before the cell is queued (the defense headline's second seed).** `lean_24_none_h300_k42_w13h_p3_m1_n600_wl70_sr300_ud_s23456` on `simbox3` — E56's cell at seed 23456, the replicate of the program's headline defense number (one seed so far; the untrimmed adversary pair replicated to 0.09% across two seeds, P44/P45). (a) light share 0.0248 within ±0.05 (a miss beyond that is a seed effect to investigate, not noise — the P26/P28 rule); (b) 1-2 of 40 users exposed, sp recall at or below 0.01 at precision 1.000; (c) dump checks as E56 (roughly 28-33 spy entries of 70, surviving fronts fresh 95-131 s, honest ages 208-742 s); (d) wall under 6 h. Reading rule: none — this is variance, not mechanism. *Outcome, 2026-10-27 16:29:* **four of four**: (a) **0.0261**, 0.0013 above E56 — a single exposure event of spread; (b) hit (1 of 40 users, sp 0.0019 at precision 1.000); (c) hit (spy entries 25-32 of 70, cut 3-7 spies, the steady-state age shape); (d) hit (278 m). E60; run 99.

**P51, filed 2026-10-27 12:20, before the cell is queued (X1a: who is deanonymized today, at mainnet's rate).** `lean_24_none_h300_k42_w13h_p3_m1_n600_fx_mw25h_ui43200_rs60_bs6_s12345` on `zenith2alpha` behind P49 — E27's shape with the sender population and rates rebuilt to mainnet: the 40 users at 43200 s (~2 tx/day, the unreachable anchor), 60 reachable home senders (`sender-a-*`, hide-my-port false, wallets) at 18000 s (~4/day — the occasional class OQ12 has n = 0 for), 6 busy at 3600 s (1/h); ~530 txs over 24 h of activity ≈ 0.7x mainnet's network rate; stock rule, passive fleet, 40 h stop with the fixed RandomX seed (the w24h fx cells' proven territory). E58 killed the fluff-epoch channel, so the read is the sp estimator alone. (a) unreachable: sp precision 1.00 ± 0.02, sp_r recall 0.08-0.18 (E27's 0.118-0.144 is the prior); (b) occasional reachable: sp precision **0.05-0.45** — the number OQ12 exists for: the sender's own ~4 txs against the relayed stems a reachable node hands spies (the plan section 2.3 says "low"; the cell prices it); (c) busy: precision 0.45-0.90 (the plan: "high precision for busy nodes"); (d) P(at least one exposed tx in 24 h): unreachable 0.05-0.40 (2 txs at recall ~0.12), busy 0.6-1.0 (24 txs); (e) wall under 8 h (40 h of sim at E57's 144 m per 19 h, minus the ~2x lighter tx load). Reading rule: (b) is OQ12's number — below 0.15 and today's reachable home nodes are buried by relayed-stem cover, no address-book defense needed for them; above 0.45 they are as exposed as unreachable nodes and the defenses transfer. *Outcome, 2026-10-27 19:12:* **five of five**: (a) precision 1.0000, recall 0.1455; (b) **0.2651** — the middle: neither buried nor bare, one spy guess in four right; (c) 0.8431; (d) 8/37 users (21.6%) and 19/22 busy (86%) exposed in 24 h; (e) 285 m. E61; run 100.

**P52, filed 2026-10-28 04:50, before the cell is queued (X3a: tevador's stemmable inbound stems at full take-up, passive fleet).** `lean_24_none_h300_k42_w13h_p3_m1_n600_x3_s12345` on `zenith2alpha` — E27's cell (stock rule, lab-rate users, 42 passive spies) with `--stemmable`: the relay fabric adopts (relays/mediums/observers; every inbound connection counts as stemmable — the universal-PoW upper bound). The smoke (run 101, the 14-patch binary's first run) verified the mechanism: 2,140 `x3` events, edge 2 carrying virtual connections 38% of the time, edge 1 staying on outgoing, and — the point of the proposal — **users receiving relayed stems for the first time: 107 against 0 in the stock smoke**. The cover channel exists. (a) light share 0.28-0.38 (the patch touches stem selection, not the outbound draw; E27 read 0.337); (b) **sp precision on unreachable users 0.25-0.60** — the plan's full-take-up model says ~0.3 (p+q-pq); center 0.45; against 1.000 stock (E27/E61) this number is the cell's whole purpose; (c) sp recall on users 0.10-0.16 (the first hop still rides real outgoing connections — tevador's guarantee; recall should not move); (d) 20-32 of 40 users with at least one sp_r exposure (E27: 27); (e) the cover census: 200-4,000 stem receipts at users over the window; (f) wall under 6 h (the per-epoch connection walks are the only added cost). Reading rule: (b) at or below 0.35 and X3 is a real precision defense for unreachable senders at zero protocol cost to them (the PoW cost is the deployability question, not measured here); at or above 0.6 the cover is too thin at this topology and X3's value is confined to its subnet-deduplication hardening; (c) out of band would mean the mechanism leaks exposure somewhere unexpected — read the `x3` events before believing it. *Outcome, 2026-10-28 06:57:* **four of six**: (a) **0.3409** hit; (b) **0.9828**, missed above — the cover is real but 15x too thin (71 relayed stems at the 40 users against 1,063 own sends; the design's throttles compound); (c) 0.1072 hit; (d) 24/40 hit; (e) 71, missed below; (f) 145 m hit. E62; run 102.

Corrected 2026-10-28 (review R6a): the smoke census re-read from the archive gives **100**
relayed-stem receipts at 23 of the 40 users against 0 in stock — the "107" was close but counted
differently; the canonical count is `adhoc/x3_census_smoke.json`.

**P53, filed 2026-10-28 07:45, before the cell is queued (X3 at mainnet sender rate — the parameter that matters, on `simbox3`).** `lean_24_none_h300_k42_w13h_p3_m1_n600_fx_x3_mw25h_ui43200_rs60_bs6_s12345` — X1a's cell with `--stemmable`. E62 closed the lab-rate ceiling by volume arithmetic (users would need to receive 2,400 of the 510 virtual sends; no design knob does that), but at mainnet sender rates the two back-of-envelope routes disagree — cover ratio ~0.15 (precision ~0.87) against ~0.5 (~0.67) — which is exactly why the rate point is run, not argued. (a) **sp precision on unreachable users 0.45-0.92** (center 0.75, against X1a's 1.000); (b) sp recall 0.08-0.18 (X1a 0.1455 — the first hop is untouched); (c) reachable-occasional precision 0.15-0.30 (X1a 0.265, diluted further); (d) light 0.24-0.34 (X1a 0.2935); (e) the cover census: 15-100 relayed stems at the users over 24 h (against X1a's ~55 own user txs); (f) wall under 12 h on simbox3. Reading rule: (a) below 0.55 and the cover is real at mainnet rates — the sweep proceeds to the design knobs (mixed-edge count, virtual cap, each a small patch variant); above 0.85 and X3's cover is closed at every rate, its surviving value the edge-1 guarantee and the /16 dedup. *Outcome, 2026-10-28 19:48:* **four of six**: (a) **1.000**, missed above — the cover at mainnet rate is 13 relayed stems at 11 of 40 users against 55 own sends, and none of the 13 was forwarded to a spy; (b) 0.164 hit; (c) 0.288 hit; (d) 0.3066 hit (2.36x the cell's own 0.1299; X1a 2.26x); (e) 13, missed below; (f) 553 m hit. Reading rule's upper branch: the cover is closed at every rate. E64; run 104.

**P54, filed 2026-10-28 07:45, before the cell is queued (X3c: the v2 adversary through stemmable inbound stems — the guarantee's blind side, on `zenith2alpha`).** `lean_24_none_h300_k42_w13h_p3_m1_n600_x3_sr300_ud_s12345` — E53's cell (stock rule, the front-port adversary at 300 s sweeps) with `--stemmable`: the relay fabric adopts while the adversary attacks the outbound draw. X3 touches stem selection only; nothing in it defends the draw, so the prediction is the eclipse rides straight through edge 1. (a) light 0.85-0.95 (E53: 0.9083); (b) sp recall 0.35-0.55 and combined 0.90-0.98 at precision near 1 (E53: 0.468/0.967); (c) 38-40 of 40 users exposed (E53: 40); (d) the cover census at users 0-30 (honest-to-honest connections collapse under the eclipse, so the trickle X3a measured shrinks further); (e) wall under 6 h. Reading rule: (a) inside band confirms X3 is irrelevant to the outbound-capture vector — the one this program's adversary occupies — and the proposal's guarantee has the blind side exactly where the real attack lives; below 0.80 would mean the mixed edge dilutes the spy stem monopoly, a real surprise worth chasing.

Corrected 2026-10-28 (the five-day review, R8): the queued cell is
`lean_24_none_h300_k42_w13h_p3_m1_n600_sr300_ud_x3_s12345` — make_lean's tag order puts
`_x3` last; the name above was the failed first launch's guess. Started 10:31, after this filing.

*Outcome, 2026-10-28 12:58:* **five of five**: (a) **0.9051** hit; (b) sp 0.445 / combined 0.951
at precision 1.000 hit; (c) 40/40 hit; (d) 17 relayed stems at one user, hit inside 0-30; (e)
145 m hit. E63; run 103.

**P55, filed 2026-10-28 18:15, before the cell is queued (X3b-pay: the fleet pays and nobody else adopts — the payment pole, on `zenith2alpha`).** `lean_24_none_h300_k42_w13h_p3_m1_n600_x3_sd12_sc_s12345` (md5 9196215d) — X3a's spread cell with two changes. The cidrs file names only the 42 spy /24s (the honest fabric's inbound connections are not stemmable; the fleet's are). And the spies DIAL (`--spy-dial 12`: no exclusive node, `out-peers 12` filled from the harness's seed list), because the baseline census (`adhoc/spy_stem_receipts.py` on runs 46, 63, 102) found that the lab's fleet has never held a connection an X3 virtual slot can carry: every spy stem receipt in E19, E27 and X3a is `dir=in` — the relay dialed the spy — and 0 of X3a's 672 receipts from adopters arrived through a virtual slot. The spies stay in the white lists (hide-my-port false), so they hold both channels: real outgoing at the relays (edges 1 and 2, as before) and ~1.7 inbound connections per reachable honest node (42 x 12 over 300) that the cidrs make virtual-eligible with no honest competition for the slots. (a) light 0.30-0.38 (E27 0.337, X3a 0.3409: the outbound draw is untouched; above 0.38 would be the dialing spies refreshing their own white-list entries at the relays they dial — OQ13 (b)'s v1 effect, which the h71 smoke did not show); (b) relayed stems at users **0-5** and sp precision on users at or above 0.98 (X3a: 67 and 0.9828 — the users' connections are no longer stemmable, so the cover the fleet pays for goes to the fleet, not the users); (c) spy stem receipts 1,000-1,400 with `virtual_rx_share` 0.05-0.20 (E27 1,031; X3a 885 — in X3a the honest virtual slots displaced the spies from edge 2 in 35 % of epochs; here the virtual side is all-spy, ~1.7 slots in a union of ~14); (d) hop-1 user txs 100-150 and sp recall 0.10-0.15 (E27 130, X3a 114: edge 1 is real-outgoing-only, so paying cannot buy the first hop); (e) wall under 4 h (X3a 145 m). Reading rule: (b) with (d) is the pole's answer — fleet-only payment hands the fleet hop-2 receipts and the users nothing, and leaves the first hop exactly as exposed as stock; a (b) precision below 0.95 means the cidrs gate leaks (read the census's relayed stems before believing it); (c) above 1,400 together with (a) above 0.38 is the white-list refresh, not X3. *Outcome, 2026-10-29 04:43:* **three of five**: (a) light **0.0923** (missed below 0.30-0.38; relays' p_out 0.081 against X3a 0.315 — the direction swap); (b) 0 relayed stems at users, precision **1.000** — hit; (c) **763** receipts at `virtual_rx_share` **0.526** (462 relay-dialed + 301 virtual; missed on both halves, and 885 in X3a sitting still); (d) hop-1 user txs **133**, sp recall **0.129** — hit; (e) 153 m hit. Payment buys the virtual channel by spending the passive one. E69; run 109.

**P56, filed 2026-10-28 18:15, before the cell is queued (X3b-hidden OFF: the isolation control, on `zenith2alpha`).** `lean_24_none_h300_k42_w13h_p3_m1_n600_sph_sd12_s12345` (md5 ecb851c9) — the spread fleet with hidden dialing spies (hide-my-port true, out-peers 12, no exclusive node) under STOCK stem selection, no X3. A hidden spy advertises no port, enters no white list and is never dialed: every connection it holds is inbound at the honest side, and stock Dandelion++ stems only on outgoing connections. (a) spy stem receipts **0-5**, hop-1 0; (b) light share 0.000-0.010 and sp recall at or below 0.01 (the spies hold no outbound slot anywhere); (c) each spy holds 10-12 outbound connections through the window (the dial check, from the spies' bitmonero connection tokens — `analysis/topology_metrics.py` — or their txrelay fluff receipts' `dir=out`; the spies must have found peers through the seeds, or (a) is trivially zero); (d) wall under 4 h. Reading rule: (c) must pass before (a) means anything; a nonzero (a) with (c) passing is a stock stem onto an inbound connection — read txrelay_check's stem paths before believing it. *Outcome, 2026-10-28 20:51:* **four of four**: (a) **0** stem receipts at the 42 spies; (b) light 0.000, sp recall 0.000; (c) hit on the dial reading — 59-85 distinct outbound connections per spy over the window (median 68), zero inbound; the concurrent count is not what the census measures, see E65; (d) 153 m. E65; run 105.

**P57, filed 2026-10-28 18:15, before the cell is queued (X3b-hidden under universal adoption, on `zenith2alpha`).** `lean_24_none_h300_k42_w13h_p3_m1_n600_x3_sph_sd12_s12345` (md5 f66adf91) — P56 with `--stemmable` on the fabric, every inbound connection stemmable. Every stem a hidden spy receives now arrives through a virtual slot, and the fleet's ~504 inbound connections in 42 /16s compete with the honest fabric's own inbound /16s for the capped list (X3a: union median 22, virtual slot share 35 %). The analogue is X3a's users: 40 unreachable nodes with ~480 inbound-at-relay connections drew 67 relayed stems over the window. (a) spy stem receipts **30-150** (center ~70), with `virtual_rx_share` at or above 0.95 (every receipt joins to the sender's latest x3 virtual list; the remainder is join misses); (b) hop-1 receipts **0** and sp_r recall 0.00 (edge 1 is real-outgoing-only and local transactions always use it — the guarantee, read at the spy); (c) light 0.000-0.010; (d) relayed stems at users 30-120 (X3a 67; the spies now compete for the same slots); (e) wall under 4 h. Reading rule: (a) prices the inbound-only re-entry at an ordinary node's dial budget; a nonzero (b) falsifies the guarantee as built — read the sender's x3 events before believing it; (a) above 150 means the virtual draw favors the spies' /16 spread over the honest fabric's (read the union sizes). *Outcome, 2026-10-28 23:30:* **five of five**: (a) **78** receipts, `virtual_rx_share` **1.000**; (b) hop-1 **0**, sp_r recall 0.000; (c) light 0.000; (d) 68 relayed stems at 30 of 40 users; (e) 153 m. The fleet gets a ninth of X3a's relay-dialed receipts and none at hop 1. E66; run 106.

**P58, filed 2026-10-28 18:15, before the cell is queued (X3b-hidden, the fleet pays, on `zenith2alpha`).** `lean_24_none_h300_k42_w13h_p3_m1_n600_x3_sph_sd12_sc_s12345` (md5 0213614f) — P57 with the cidrs file naming only the spy /24s: the virtual list at every adopter is spy-only (~1.7 entries, no cap pressure), the union ~14 against X3a's 22. (a) spy stem receipts **80-300**, 1.5-3x P57's (the sparse all-spy list wins edge 2 in ~12 % of epochs against ~6 % under competition), `virtual_rx_share` at or above 0.95; (b) hop-1 **0**; (c) relayed stems at users 0-5 and sp precision on users at or above 0.98 (nothing honest is stemmable); (d) light 0.000-0.010; (e) wall under 4 h. Reading rule: (a) against P57's (a) is the design's "who pays" answer — a fleet that pays alone gets MORE hop-2 stems than under universal adoption, and the users get none; (a) at or below P57's means the capped draw does not favor a sparse list (read the x3 union sizes). *Outcome, 2026-10-29 02:07:* **five of five**: (a) **238** receipts, 3.05x P57's measured 78, `virtual_rx_share` **1.000**; (b) hop-1 **0**; (c) relayed stems at users **0**, no user ever attributed (zero sp guesses on users); (d) light 0.000; (e) 154 m. The sparse list wins edge 2 in 9.1 % of epochs (P57 35.1 %) with union median 13 (P57 24), every win a spy. E68; run 108.

**P59, filed 2026-10-28 18:15, before the cell is queued (X3b-dense: the real fleet's layout, relay-dialed, universal adoption, on `zenith2alpha`).** `lean_24_none_h300_k8_w13h_p3_m5_n600_x3_s12345` (md5 6bf3ff38) — 40 spies in 8 /24s (5 each, in 8 /16s; the generator's uniform count stands in for the fleet's 5-6 — 42 would need 7 or 6 /24s), OQ8's identified shape, the fleet relay-dialed as in every cell through X3a, the fabric adopting. The `24` ceiling for 8 spy /24s against 242 honest is ~0.032 (quote the run's own `model_out`, R1). The baseline census settles what this cell can read: a relay-dialed fleet never occupies a virtual slot (0 of 672 in X3a), so the /16 bucketing cannot bite here; the cell reads whether the passive multiplier survives X3 at the real fleet's layout, and it is the program's first k8 cell (the dense-fleet passive number OQ8's identification never had). (a) light **1.8-3.5x the run's own ceiling** (~0.058-0.112; E19 2.02x, E24 2.13x, E27 2.20x, X3a 2.23x; the single-/24 core sits higher and drains); (b) spy stem receipts 150-450 and hop-1 user txs 15-50 (E19: 622 and 61 at light 0.166; the receipts scale with the fleet's outgoing share); (c) relayed stems at users 30-120 (X3a 67: the cover is the honest fabric's inbound, independent of the fleet's layout); (d) sp precision on users 0.85-1.00, sp_r recall 0.02-0.07 (E19 0.059 at 21 /24s); (e) wall under 4 h. Reading rule: (a) outside 1.8-3.5x is a layout effect of 5-per-/24 that the k21/k42 series did not show (compare the single-/24 core's drain, E10/E22c); the bucketing question moves to the dialing-fleet budget pole — dense against spread, hidden, at a large dial budget (`--spy-dial 64`) — filed after P56-P58 read. Queue order on `zenith2alpha`: P56, P57, P58, P55, P59 (the two cidrs cells carry an absolute path under `/home/antiproxy`, so they stay on tr; P56 and P59 can move to `simbox3` after its rebuild). Filed before E64: P53 (mainnet-rate X3) and these (adversary strategies) are independent axes, and tr sat idle with the R7-fixed binary. *Outcome, 2026-10-29 00:45:* **one of five**: (a) light 0.0598 = **1.73x** the run's own 0.0345 (missed below 1.8x; inside the quoted absolute 0.058-0.112, which assumed ~0.032); (b) **187** receipts hit, hop-1 user txs **14** (missed by one); (c) 67 hit; (d) precision 1.000 hit, sp_r recall **0.014** (missed below); (e) 281 m on `simbox3` (missed; the clause was filed for tr). Receipts per /24 equal X3a's (23.4 against 21.1): the fleet earns per /24, not per spy. E67; run 107.

**P60, filed 2026-10-29 10:30, before the cell is queued (X3b budget pole, spread: the hidden fleet at a large dial budget, universal adoption, on `zenith2alpha`).** `lean_24_none_h300_k42_w13h_p3_m1_n600_x3_sph_sd64_s12345` (md5 ae24a2aa) — E66's cell with the dial budget 64 instead of the stock 12: 42 hidden spies, one per /24, each dialing 64 out-peers, ~2,688 spy inbound connections at the fabric, ~9 per relay against E66's ~1.7. The one-IP-many-CPU end of the strategy axis (x3b_design: few /16s with many connections vs many /16s at a small budget). The relay's /16-dedup virtual list sees the spies' /16s rise from ~1-2 entries to ~8-9 of the union: the pole's question is what a connection buys beyond the first per /16, and where the cap-12 stops it. (a) spy stem receipts **300-550** (E66 78 at sd12; the /16 occupancy of the union rises ~4-5x and the receipts with it; the linear-in-connections guess is 78 x 5.3 = 413), `virtual_rx_share` at or above 0.95 (isolation, as E66: a hidden spy's every stem is virtual; the dial check reads many distinct outbound ids per spy, zero inbound); (b) hop-1 receipts **0** and sp_r recall 0.000 (a nonzero falsifies the guarantee as built); (c) light 0.000-0.010; (d) relayed stems at users 30-120 (E66 68, X3a 67: the added spy /16s crowd the virtual list a little); (e) wall under 4 h. Reading rule: (a) against E66's 78 prices the marginal connection at a fixed /16 count — at or below ~150 the cap protects (the /16 occupancy saturated; read the union median and the edge-2 virtual share), above ~550 the draw favors the spies super-linearly (read the census's join misses before believing it). *Outcome, 2026-10-29 13:34:* **four of five**: (a) **273** receipts, 3.50x E66's 78 for a 5.33x budget (missed below the 300 floor by 9 %; linear would be 416 — the second-and-later connection per /16 buys a discounted share), `virtual_rx_share` **1.000**; (b) hop-1 **0**, every estimator's recall 0.000, 0 of 40 users exposed; (c) light 0.000; (d) 52 relayed stems at 24 of 40 users (E66 68 at 30 — thinned, as anticipated); (e) 180 m. Union median 24 at 5x the fan-in: spy /16s displaced honest ones. E70; run 110.

**P61, filed 2026-10-29 10:30, before the cell is queued (X3b budget pole, dense: the real fleet's layout at a large dial budget, hidden, universal adoption, on `simbox3`).** `lean_24_none_h300_k8_w13h_p3_m5_n600_x3_sph_sd64_s12345` (md5 be2f27ed) — P59's layout (40 spies in 8 /24s, 5 each, in 8 /16s) hidden and dialing 64: ~2,560 spy inbound connections, the same ~9-per-relay fan-in as P60 concentrated into 8 /16s. The two cells hold the fan-in fixed and move the /16 count — the /16 bucketing question E67 could not test (a relay-dialed fleet never occupies a virtual slot; here every spy connection is inbound at the relay and stemmable). The /16-deduped draw caps the fleet at 8 /16s whatever the fan-in, against P60's ~8-9 at 42 /16s. (a) spy stem receipts **250-500**, within ~25 % of P60's measured the same day (presence, not fan-in, wins a /16 a slot — if so, dense = spread at this budget), `virtual_rx_share` at or above 0.95; (b) hop-1 **0**, sp_r recall 0.000; (c) light 0.000-0.010; (d) relayed stems at users 30-120; (e) wall under 6 h (P59's shape took 281 m on this shared box). Reading rule: (a) against P60's is the bucketing answer at a large budget — at or near P60's means the /16 count is already spent at ~9 inbound per relay (the first connection per /16 buys the slot, the rest buy nothing); at half or less means the draw or the honest competition holds the dense fleet's /16s out (read the union medians side by side). *Outcome, 2026-10-29 16:03:* **four of five**: (a) **212** receipts — 78 % of E70's 273, inside the pre-registered 25 % window (dense = spread at this fan-in; the band 250-500 missed below by the same sub-linearity as E70's); `virtual_rx_share` **1.000**; (b) hop-1 **0**, every recall 0.000, 0 of 40 users exposed; (c) light 0.000; (d) 46 relayed stems at 20 of 40 users; (e) 332 m. Union median 24 = E70's at 5.25x the /16 count. One slot per prefix, on every axis. E71; run 111.



**Correction to P62-P67, 2026-10-31 05:10, after M1's smoke assertions.** The smoke (estimator header 63 spies; observer dump 362 endpoints on 362 distinct IPs, ZERO multi-port IPs) falsified the series' modeling premise: the harness assigns every spy daemon its own IP within the node's /24, so `--spies-per-subnet 7` means seven addresses per /24, not seven ports on one address. The port-multiplication pump the gray cap targets cannot occur in these cells: M2/M3/I2 (`_hpl`) can never fire and are pulled (M2, already started, completes as a free null-validation of the R8 flag — identical light to M1 is the expected read); I1 (k42 m7: 294 addresses in 42 /24s) and B1 (k9 m1) stand as the many-ADDRESSES-per-/24 dose-response against E27's one-address /24s — a real and previously unmeasured axis (the true fleet: ~216 addresses per /24). The port-front modeling needs a generator feature (multiple daemons on one IP, distinct ports) before the cap can be tested as filed; queued for re-planning. The id-consistency S-cells are unaffected — a shared id across many addresses is precisely the crawl fleet's shape.

**P62, filed 2026-10-31 02:25, before the cell is queued (per-host series, the no-ports baseline, on `simbox3`). *Outcome, 2026-11-07:* light 0.0853 = **2.24x** (band 1.5-2.2, missed above); receipts **414** (band 60-250, missed above — per-/24 concentration), hop-1 16 hit, precision 1.000. E75; run 115.** `lean_24_none_h300_k9_w13h_p3_m1_n600_s12345` (md5 ca7ae836) — the real fleet's /24 count (9) with ONE port per spy IP: the port-multiplier axis held at 1, the R8 binary's flag off. This is the floor the m7 cells measure their premium against. (a) light 1.5-2.2x the cell's model (~0.054-0.079 on 0.0359); (b) spy stem receipts 60-250, hop-1 user txs 8-25 (E67's k8 with the m5 front read 187 and 14), sp precision on users at or above 0.95; (c) wall under 6 h on the shared box. Reading rule: with (P63) it prices the port premium at k9 — the m7/m1 light ratio is the pump's product.

**P63, filed 2026-10-31 02:25, before the cell is queued (per-host series, the pump at full strength, the smoke cell, on `zenith2alpha`). *Outcome, 2026-11-07:* light 0.0633 = **1.66x** hit at the band floor; receipts **314** hit (150-350); hop-1 15 hit; the smoke assertions revealed the premise error (63 addresses, not 63 ports) — see the 10-31 correction. E72; run 112.** `lean_24_none_h300_k9_w13h_p3_m7_n600_s12345` (md5 802776b1) — 63 spy endpoints on 9 IPs, 7 ports each (the real front's median), stock rules: white is one-per-host (stock, appendix A) and the 7 ports rotate each host's single white slot through gray-list probes. (a) light 1.7-2.4x model (0.061-0.086), at or above E67's 1.73x at 5 ports, and at or above 1.1x P62's measured (the port premium); (b) spy stem receipts 150-350, hop-1 user txs 10-30; (c) SMOKE assertions before the series is trusted: the estimator header reads 63 spies logging on 9 distinct addresses, and the peerlist dumps show 7 distinct ports per spy IP; (d) wall under 4 h. Reading rule: (a) vs P62's is the pump's price; (a) vs E67's 1.73x checks the dose-response (5 ports -> 7).

**P64, filed 2026-10-31 02:25, before the cell is queued (per-host series, the treatment: gray capped at 1 per host, on `zenith2alpha`). *Outcome, 2026-11-07:* **null-validation** after the correction: light 0.0651 vs M1 0.0633, receipts 296 vs 314 — the R8 flag is inert without shared-host endpoints, as designed. E73; run 113.** `lean_24_none_h300_k9_w13h_p3_m7_n600_hpl1_s12345` (md5 a81ed38d) — P63's cell with `--sim-peerlist-ports-per-host 1`: a host's gray entries capped at 1 (newest kept) and all same-host gray erased when any of its ports promotes to white — the rotation reservoir cannot refill while the host holds its white slot. (a) light 0.9-1.1x P62's measured (the premium removed; the cap's predicted landing is the no-ports floor, NOT zero — the host keeps its single legitimate slot); (b) spy stem receipts within 30 % of P62's, hop-1 user txs 8-25; (c) the fleet's share of honest white lists (peerlist dumps) at or below P62's + 10 %; (d) wall under 4 h. Reading rule: P64 at P62's level = the cap removes the premium cleanly; P64 at P63's level = the multiplier at k9 was never the pump (read the 20-newest cut, Finding 1).

**P65, filed 2026-10-31 02:25, before the cell is queued (per-host series, the half-dose: gray capped at 2, on `zenith2alpha`).** `lean_24_none_h300_k9_w13h_p3_m7_n600_hpl2_s12345` (md5 0318c4e5) — P64 with N=2: the gray reservoir refills to 2 between promotions, but the promote-erase still empties it on every promotion. (a) light between P64's and P63's, 0.8-1.0x P63's; (b) receipts 120-320; (c) wall under 4 h. Reading rule: P65 at P64's level means the promote-erase does the work and the cap value is secondary; P65 at P63's level means a 2-deep reservoir fully reconstitutes the pump (N=1 is then the only effective setting — the upstream N choice).

**P66, filed 2026-10-31 02:25, before the cell is queued (per-host series, the standard layout with ports, on `zenith2alpha`). *Outcome, 2026-11-07:* light 0.3467 = **2.26x** hit (2.0-2.6); receipts **1,004** hit; hop-1 **106** hit; within noise of k42 m1 — the addresses-per-/24 axis is flat. E74; run 114.** `lean_24_none_h300_k42_w13h_p3_m7_n600_s12345` (md5 0e497744) — the lab's standard 42-/24 spread at 7 ports per IP (294 endpoints on 42 addresses), stock rules: the pump superimposed on the k42 series' measured 2.02-2.23x multiplier (E19/E27/X3a, all m1). (a) light 2.0-2.6x model 0.1531 (0.31-0.40); (b) spy stem receipts 900-1,400, hop-1 user txs 100-150 (X3a 885 and 114 at m1); (c) wall under 4 h at 640 agents (the series' largest cell). Reading rule: (a) above 2.23x means the pump adds freshness on top of the m1 multiplier; at the m1 band means the multiplier saturates.

**P67, filed 2026-10-31 02:25, before the cell is queued (per-host series, the decomposition at scale, on `zenith2alpha`).** `lean_24_none_h300_k42_w13h_p3_m7_n600_hpl1_s12345` (md5 62edc87a) — P66 with the cap at 1: the series' central question. (a) light 0.75-1.0x P66's measured — at ~1.0 the 2.2x multiplier is intrinsic to the 20-newest candidate cut (Finding 1's mechanism: spy entries refreshed whenever a node dials them, E21/E35) and the cap defends list occupancy and freshness, not the multiplier; at ~0.75 the port pump carries a quarter of the multiplier and the cap bites at scale; (b) receipts 700-1,200, hop-1 user txs 90-150; (c) the fleet's white-list share at or below X3a's measured + 10 %; (d) wall under 4 h. Reading rule: this cell decides the upstream note's framing — list-hygiene defense (occupancy, freshness laundering) versus multiplier defense.

**P68, filed 2026-11-07 (id-consistency trio, the real fleet under today's rules, on `zenith2alpha`).** `lean_24_none_h300_k42_w13h_p3_m7_n600_sid_s12345` (md5 a430ffc4) — I1's cell with `--sim-shared-spy-id`: all 294 spy endpoints present one fixed backing id, the crawl fleet's shape (12,368 endpoints, shared-id signature). Under stock rules nothing checks id consistency. (a) light within noise of I1's 0.3467 (the shared id changes nothing in stock selection); (b) spy stem receipts 850-1,200 (I1 read 1,004), hop-1 user txs 90-150 (I1 106); (c) sp precision on users at or above 0.95, recall 0.08-0.13. Reading rule: (a) is the control — a shared id must be invisible to stock monerod; any deviation indicts the fleet-mode flag itself.

**P69, filed 2026-11-07 (the headline: shared id under enforcement, on `zenith2alpha`).** `lean_24_none_h300_k42_w13h_p3_m7_n600_idc24_sid_s12345` (md5 b0de8514) — P68's cell with `--sim-enforce-id-consistency 24`: R1 (a shared id keeps white standing only at its freshest directly-observed address; older ones demoted) + R2 (self-advertisement contradiction) + egress hygiene, direct evidence only, 24 h grace. (a) light collapses to 0.004-0.05 (one id's legitimate single-slot share; a 10-80x drop from I1's 0.3467); (b) spy stem receipts 50-350 and hop-1 user txs 5-40 (slot loss compounds both); (c) sp recall on users 0.005-0.04 at precision 1.000 (the estimator keeps its precision but loses its reach); (d) honest connectivity within the Finding 5 tolerance (failed dials, refill). Reading rule: (a) above 0.10 means the demotion races the pump's re-promotion faster than expected — read the probe nodes' white lists for the fleet's surviving entries; below 0.004 would mean honest collateral (read honest occupancy first).

**P70, filed 2026-11-07 (the evasion bound: per-endpoint ids under enforcement, on `zenith2alpha`).** `lean_24_none_h300_k42_w13h_p3_m7_n600_idc24_s12345` (md5 62ce428b) — I1's cell with enforcement on and NO shared id: 294 honest-consistent identities, the design's honest bound. (a) light within noise of I1's 0.3467 (enforcement is inert against per-endpoint ids — by design, the bound the spec states); (b) receipts/hop-1 within 15 % of I1's; (c) honest connectivity clean. Reading rule: P70 == I1 completes the story — the defense collapses shared-id fronts (P69) and provably costs a consistent fleet nothing (P70); the residual exposure is priced by the escalation layers (signed bindings, per-identity work), not this one.
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
   *2026-10-25 15:13, from the plan review (plan section 7, threat 1):* ranked the top threat to the whole cap finding. The owner's action: a
   `print_pl` dump from a long-running mainnet node, read for the spies' rank in `last_seen` order and their share of the 20 newest /24s. The lab's
   counterpart: the thirteenth patch, `--sim-white-peerlist-limit N` / `--sim-gray-peerlist-limit N` (runtime limits in place of the compile-time
   1000 / 5000, trimmed oldest-`last_seen` first; built on zenith2alpha 15:09, sha `ab6646d7`), and `make_lean.py --white-limit N` (`_wlN`); the stock
   and cap-lifted spread-fleet cells at N about 70 (mainnet's 1,000 of ~4,600 reachable, scaled to the lab's 342) are the next cells to file.
   *2026-10-25 20:49, from E45 and E46 (P36, P37).* The lab half ran: with the white list trimmed to 70 entries the stock rule reads **1.06x** the
   ceiling (0.1616 against E27's 0.3369) and the cap-lifted rule **1.06x** (0.1619): the trim alone removes the 2.2x, and the probes' trimmed lists hold
   the spies at 8.5-10.7% of their entries, below the 12.3% pool share, at rank 0.35-0.49. Mechanism (E45): entries are refreshed by connections in
   either direction; honest relays are refreshed by inbound dials too, spies only through a node's own spy slots, so a recency trim keeps the recently
   connected peers and the spies are a minority of those; the untrimmed list's hundreds of never-refreshed honest entries are what made the spies look
   new. **The 2.2x is a property of a white list that holds the whole network.** The dump now decides between two readings of mainnet: lists like
   P36's (today's exposure near the subnet share; the candidate-rule fixes have nothing to fix) or like E27's. The sweep at 140 and 35 entries (P40,
   P41, `simbox3`) locates the lab's threshold. The dump request stands, read for the list's size, the spies' share of its entries and their rank.
   *2026-10-26 04:25, from E49 (P40).* The sweep's 140 point reads 1.07x, flat with the 70 point's 1.06x: the threshold sits above 0.41 of the pool, so the stock-rule multiplier requires a list that holds (nearly) the whole network. P41 (35) runs; the dump still decides which side of the lab's flat region mainnet's lists behave like.
   *2026-10-27 11:07, the owner's dump, two nodes* (`192.168.1.76`, 21 d up, v0.18.5.3; `xmrchain`, 5 d up, v0.18.1.0; raw JSON local-only on the control box at `~/monerosim_local/mainnet_pl/`, deliberately outside the repo): mainnet's trim is real and identical on both — **white exactly 1000, gray 5000 (the caps), every white entry under 12.3 h, median ~6 h** — and the two lists overlap only 19%, so this is the network's steady state, not one node's habit. The newest-20 candidate cut is minutes-fresh on both (1.4-5.6 m and 8.3-8.8 m): mainnet's honest network keeps a minutes-fresh pool at the top of every list — the same mechanism the lab's wl70 measured; the lab's whole-list minutes-median was a small-network artifact, but the defensive quantity (the top cut) matches. Honest connections live long (xmrchain: median 10.4 h, p90 84.5 h, max 4.6 d), so a node frees an outbound slot roughly every 20-30 min. Transfer verdict against E56/E57: **the trim's protection on mainnet is the minutes-fresh top cut, and a front adversary sweeping every 300 s ties that cut rather than dominating it** — the race is genuinely contested (the lab's wl70 honest cycle outran the sweep outright; mainnet's does not), and with connections living ~10 h each spy slot win persists. The E45/E46 flat-region reading for a passive fleet stands. The identification half (the spy /24 share of the freshest candidates) still needs the real known-spy list — the repo's fixture is synthetic; the owner's ProbeLab/crawl list completes it.
   *2026-10-27 11:21, the identification, from the 2026-09-23 crawl* (`nodes.jsonl`, 18,026 reachable, 12,368 carrying the peer-id-mismatch front-end fingerprint, 12,362 of them in EIGHT dense /24s — one operator's fleet, the X0 preset's "9 dense /24s" confirmed against live data; raw crawl local-only beside the dumps). Joined against the two dumps: **node 1 (21 d up): 152 of 1000 white entries in the spy /24s (15.2%, the pool share), 8 of the 8 live /24s present, median rank 580 of 1000 — the stale half — and 3 of the newest-20 cut.** **xmrchain (5 d up): zero spy entries** — with eight /24s of ~2,000 addresses each, a healthy five-day node holding none means the fleet rotated its addresses within the five weeks since the crawl. So the passive-fleet transfer is now measured on mainnet itself: the spies sit at their pool share in the stale half of a long-running node's list (E45's mechanism, confirmed in the wild), the minutes-fresh cut is honest-dominated (85%), and the real adversary's infrastructure already demonstrates a third dial the lab's cells did not price — wholesale IP//24 rotation on ~week timescales, on top of port rotation and sweep rate. Open question 8 is CLOSED: mainnet's capped lists are like the lab's trimmed cells (the flat region for a passive fleet), with the active-adversary race contested at minutes vs minutes (the 11:07 note) and the defense's remaining unknowns being the fleet's current addresses and its willingness to spend the sweep budget.
   *2026-10-26 04:21, correction to E45's mechanism line above:* "refreshed by connections in either direction" is wrong for existing white entries — an inbound dial inserts a fresh entry at the dialer's advertised address or promotes a gray one; it never updates an existing white entry's `last_seen` (`append_with_peer_white`'s `trust_last_seen=false` guard; only the node's own outbound connections refresh, `set_peer_just_seen`). The E45/E49 numbers stand; the mechanism sentence does not. Traced in open question 13 (b).
   *2026-10-26 07:36, from E50 (P41): the sweep is closed — 0.99x at 35, 1.06x at 70, 1.07x at 140, 2.20x unlimited. Every capped list reads the ceiling; the multiplier needs a list that holds (nearly) every /24. The owner's mainnet `print_pl` dump remains the decisive item.
   *2026-10-28 18:40, the Monero P2P Observatory (observer.monerodevs.org; the owner flagged it this evening), read as the standing mainnet check of the multiplier.* A Grafana dashboard run from three of the six hardcoded mainnet seeds (named ovhde, node1, node2) plus a crawl vantage, operator unnamed, spy-detection fingerprint withheld, with plain-JSON feeds the panels read over HTTP (now pulled daily by `analysis/mainnet/pull_observer.sh` into `~/monerosim_local/observer/<date>/`, aggregates only; the feed host is discovered from the dashboard at run time, so no address enters the repo). Its `seed_fleet_hist` series — 10-minute rows since 10-15, 13 days — carries, per seed, the flagged fleet's share of the white list and of the seed's live outbound connections, which is this question's number measured continuously on real nodes instead of from two dumps. `adhoc/observer_seed_ratio.py` (output `observer_seed_ratio_20261028.json`): the fleet holds **17.5-22.1 % of the white list and 13.9-15.8 % of outbound** (medians over the 13 days; last 7 days 17.8-23.2 % and 14.3-15.5 %), the per-row **outbound/white ratio 0.69 / 0.86 / 0.78** by seed (p10 ~0.4, p90 ~1.0-1.26); definitive-fingerprint members alone 1.07 / 1.35 / 1.11. The `outbound_share_hist` series (28 days) reads the adversary's share of outbound at a median 10.0-11.8 % per seed, p90 16.7 %. **Reading: mainnet nodes with capped lists show no 2.2x amplification — the fleet's outbound share sits at or below its white-list share — which is what E45/E49/E50 predicted for a trimmed list (0.99-1.07x) and the two 10-27 dumps implied from the list side alone.** Caveats that keep this an addendum, not a closing: seeds are atypical vantages (their white lists are filled by everyone's inbound handshakes, and their selection need not look like a home node's); the observatory's fleet oracle is a withheld fingerprint covering ~2,650 reachable nodes (59 % of the reachable set), far broader than the 10-27 identification's eight dense /24s, so its "fleet" and ours are different sets; and its own measured-vs-replayed outbound panel notes monerod's selection replayed on the lists runs 1.1-2x high against the seeds' real outbound, the opposite sign to the lab's lock-in — a discrepancy worth a read of their method before either model is quoted against the other. The feeds that matter beyond this question: `asn_shares` (the white list under /16 and asmap bucketing — X3's dedup on real lists), `lists_fig` (white vs gray composition; Rucknium's gist measured vs simulated), `fp8_hist` (inbound fan-in: the sweep against the seeds), `estimates_history` (ban-list adoption 21.8 %, surveillance share of listeners 81 %).
9. **The `half` list's tie-break is seeded by the simulation seed** (added 2026-10-23 14:40, from the review).
   `make_lean.py` passes `--seed <simulation seed>` to `spy_ban_list.py`, which orders equally dense /24s by a shuffle
   with that seed. In `tail` every /24 holds 2 spies, so all 21 are ties, and a seed-23456 replicate of the
   `--ban-coverage 0.5` cell bans a different 10 of the 21: a seed replicate would vary the seed and the banned set
   together. Only one such cell has run (`20261023_024332_lean_24_half_h300_k21_w13h_m2_n600_c50_s12345`). Options:
   a constant tie-break seed (later cells then ban a different set from that cell's unless the constant is 12345); a
   separate `--list-seed` defaulting to 12345, which keeps the existing cell's list; or leave it and replicate the
   list rather than the seed. Nothing is changed until a `half` `tail` replicate is queued; the owner's call.

10. **Why 2.2x and not 1x** (added 2026-10-23 23:35, from E27). Under the stock rule every `tail`-family layout reads 2.0-2.4x the
    subnet model (E19 2.02x, E24a 2.41x, E24 2.13x, E26 2.32x at 30 h, E27 2.20x), and `legacy` reads 2.34x its own (E23). The
    multiplier is set within six hours of the gray-list drain, has a start-order gradient (earliest-started relays about 1.5x the
    ceiling, latest about 3.5x), and does not relax in 30 h. E21 traced it to the recency bias over the relays' own white lists,
    which the model leaves out, but no cell has yet varied the thing that would pin it: the white-list cap (20), the recency
    exponent, or the lists' age structure. Candidate probes: a cell with the relays' lists seeded from a long-running node's
    `print_pl` dump (open question 8), or a `--sim-*` flag that flattens the recency pick to uniform, which should take the
    multiplier to 1 if E21's reading is right.
    *2026-10-24 13:58, from E35 (P24).* The uniform-pick flag ran: **0.3207**, 2.09x, gradient intact, 28 of 40 exposed. The cubic weighting
    inside the 20-candidate draw accounts for at most 5% of the share and none of the multiplier. The question narrows to the candidate set:
    the stock `24` path offers the draw the 20 newest-by-`last_seen` /24s not yet connected, and the spies are newer than the middle of the
    relays' lists (E21, rank 0.39). Open: (a) rerun `recency_model.py` with a uniform draw over its 20 to see if it predicts 0.32 from the
    E21 list dumps; (b) a flag that lifts the 20 cap (draw over every unconnected /24 in the white list); (c) why the spies are newer: the
    connection-refreshes-`last_seen` feedback is untested.
    *2026-10-24 14:41:* (a) done: the Monte Carlo gives 0.0796 (0.97x the ceiling) with the cap lifted, 0.2172 with it kept and the draw uniform. (b) built:
    `--sim-whitelist-candidates` (eleventh patch); P26 runs E27's cell with the cap at 0 and the uniform draw, P27 with the cap at 0 and the stock
    draw (Monte Carlo: 0.1242, 1.51x).
    *2026-10-24 18:40, from E36 (P26).* (b) ran: **0.1577, 1.03x the ceiling**, gradient gone, relays 0.156; five of six clauses. The cap of 20
    newest /24s is the whole multiplier (Monte Carlo 0.97x, sim 1.03x). Unforeseen: the users' share went *up* (0.103 -> 0.165) and exposed users
    from 28 to 37 of 40, because the stock rule's lock-in had held users below the ceiling and spared 17.5% of them entirely. Open: (c) untested;
    (d) why users sit at 0.67-0.87x under the stock rule; (e) which number the defense work targets, the relays' multiplier or the senders'
    exposure (owner's call); (f) a second seed of P26. P27 (the cap lifted, the cubic draw) running, due ~19:15.
    *2026-10-25 00:50, from E37 (P27) and E38 (P28).* (f) done: P26 replicates at seed 23456 (**0.1557**, 1.01x; no gradient; the earliest-started
    relays' dip was noise). The draw's shape over the full list is worth 8% and a 1.28x gradient (P27: **0.1705** with the cap lifted and the cubic
    draw kept); the Monte Carlo's 1.51x for that case was wrong because it draws every slot from the same full list without removing the /24s the
    node connects to (E37). Relay side closed: the cap of 20 newest /24s is the multiplier, at two seeds. Sender side: users sit at 0.75x the
    ceiling under the stock rule across five cells and at 0.97x with the cap lifted (E38). Still open: (c) untested; (d) why the users sit low;
    (e) the owner's call. P29 (the 24 h steady state with the cap lifted) running since 00:35.
    *2026-10-25 04:20, from E39 (P29).* (g) done: the 24 h steady state with the cap lifted reads **0.1655** (1.08x), the window's quarters
    falling 3% and no half hour from hour 6 on above 0.1743: nothing accumulates in the lists over a day once every /24 is drawable, and 1.0-1.1x
    the ceiling is the cap-lifted fleet's number at both warmups and two seeds. On the senders' side the users read 0.179 and the attribution
    recall 0.187 (the stock 24 h cells: users 0.127 and 0.105, recall 0.134 and 0.109) with 31 of 40 exposed (stock: 33 and 29): the cap's removal
    shows in recall, not in the count of exposed heavy users, which saturates. (d) and (e) stay open; P31 (E29's half list with the cap lifted)
    running since 03:55 asks whether the list's 0.55x survives without the multiplier, P30 (a third seed) on `simbox3` since 03:25.
    *2026-10-25 06:50, from E40 (P31).* (h) done: E29's half list with the cap lifted reads **0.0771**, 0.49x the cap-lifted no-list cell (E29 under
    the stock rule: 0.55x) and 1.01x the half-list model (0.0763): adopters 0.0000, the non-adopters 1.005x the ceiling and 0.98x their no-list read
    (the stock rule charged them +10%), 15 of 40 users exposed, all non-adopters (E29 also 15; the 20 adopting users never had a spy stem peer),
    recall 0.069 (P26 0.173). The list's benefit survives the cap's removal and the non-adopters' penalty does not. (d) stays open; (e) has both
    halves now: the stock rule's cap gives the spies 2.2x on the relays and holds the users at 0.75x, lifting it puts both at 1.0x, and the list
    then does exactly its half. The Threadripper's queue is empty since 06:15; P30 (a third seed) still runs on `simbox3`.
    *2026-10-25 08:40, from E41 (P30).* (i) done: a third seed (34567, on `simbox3`'s rebuilt binary) reads **0.1482**, 0.97x its ceiling, flat
    to 0.3%; the three seeds 0.1577, 0.1557, 0.1482 give a mean of 1.005x the ceiling with a 6% spread, and the users 0.99x (0.165, 0.139, 0.152)
    with 35-39 of 40 exposed. The cap-lifted number is fixed at both warmups, three seeds and two boxes. (d) stays open. Both boxes idle
    (`simbox3`'s queue empty since 07:56, zenith2alpha's since 06:15); nothing filed.
    *2026-10-25 12:51, from E42 (P32).* (j) done: the half list with the cap lifted at a second seed reads **0.0764**, 1.00x the half-list model and
    0.49x the no-list cell (P31: 1.01x, 0.49x); adopters zero, non-adopters 1.01x their subnet share, 17 of 40 exposed, all non-adopters. The stock
    rule's 0.55x with the non-adopters' +10% was the cap's doing. The twelfth patch (20 random /24 candidates, the cubic draw kept) runs as P34 on
    zenith2alpha since 12:43 and P35 on `simbox3` behind P33; the Monte Carlo puts it at 1.53x, the same as the cap lifted with the cubic draw,
    which the sim read at 1.11x.
    *2026-10-25 15:13, from E43 (P34).* (k) done: 20 random /24 candidates with the cubic draw read **0.1657**, 1.08x, with P27's 1.28x residual
    gradient: a bounded random sample is worth what lifting the cap is worth; the Monte Carlo's 1.53x was wrong again and the model is retired
    for changed rules. The review of the plan (plan section 7, filed today) ranks what gates this finding's transfer to mainnet: the list age
    structure (open question 8), the honest cost of removing recency under churn (open question 11), and an adversary that keeps itself newest
    (open question 13, which also attacks the residual here). No further candidate-rule cell runs until those three are answered; `_rc_up` waits.
    *2026-10-25 20:44, from E44 (P33).* (l) done: the half list with the cap lifted at a third seed reads **0.0792** (1.04x the half-list model,
    0.53x the no-list cell); three seeds 1.00-1.04x and 0.49-0.53x, adopters zero, non-adopters at their share. The half-list line is closed.
    *2026-10-25 20:49, from E45-E47 (P36, P37, P35).* (m) done: the twelfth patch at seed 23456 reads **0.1716**, 1.12x; two seeds 1.10x with the
    residual gradient (1.28x, 1.15x): the random sample equals the lifted cap with the same draw. (n) **With the white list trimmed to 70 entries the
    stock rule itself reads 1.06x and the lifted cap 1.06x** (E45, E46): everything measured under (a)-(m) is a property of a white list that holds the
    whole network, and whether mainnet's trimmed lists carry the multiplier is open question 8's dump. The candidate-rule line stays paused (plan
    section 7); the trim sweep (P40, P41) and the turnover cost cells (P38, P39) run.

11. **The honest cost of the candidate rules is unmeasured** (added 2026-10-25 15:13, from the plan review). X2's cost metrics (time to a full
    outbound set, failed dials, outbound diversity, propagation, outage connectivity) have been scored for no cell. The 20-newest cap is a
    liveness filter where peers churn, and the lab has none, so lifting the cap or sampling candidates at random costs nothing here by
    construction. Needs: a turnover cell (`make_lean.py --turnover 1h,1h`, `general.turnover`, built today; users cycle too, which cuts their
    transactions, so the cell is read for connectivity, not exposure) under the stock rule against `_up_wc0` and `_rc`, and a scorer for time to
    12 outbound slots after each restart and for failed dials from the daemon logs. Neither new rule is recommended before this is read.
    (a) 2026-10-25 23:19: P38's cell cycled only the users (the pinned-reachable exemption; E48). The users' sessions reach 12 outbound
    peers in 1.0-1.1 min median, and the relays' no-churn baseline is 1.7 min median, 5.9 min p90. The relay-churn pair is P42/P43 (queued
    23:16 with `--turnover-reachable`).
    (b) 2026-10-26 08:06, from E51 (P42): the relay-churn baseline is in. A restarted relay refills 12 outbound slots in 1.6 m median / 5.0 m p90 with 2.85 connect + 1.77 handshake failures per relay-hour and 1.4% of sessions unfilled; the exposure under churn reads 0.3936 (1.64x the online ceiling; the no-churn stock read 0.3369). P43 (the cap lifted under the same churn) carries the rule comparison; its clause (c) reads against 2.85 per relay-hour and 1.6 m.
    (c) 2026-10-26 11:40, from E52 (P43): the rule comparison is done — the lifted cap costs less than the stock rule at this churn (1.37 vs 2.85 connect-failures per relay-hour; fill 1.7 vs 1.6 m; 30 vs 32 unfilled sessions). The recency filter buys nothing measurable, and the honest-cost objection to the candidate rules is empty at 1 h/1 h. Exposure under churn: stock 0.3936, lifted 0.3237, both above the online-/24 ceiling the bands assumed — churn raises the water for every rule. The gate is read.
12. **The reachable sender classes are unmeasured** (added 2026-10-25 15:13, from the plan review). The lean cells have no reachable home
    senders (the estimators' reachable row is n = 0) and run users at ~150x mainnet's rate, which decides the relayed-stem cover of reachable
    senders. Needs: a cell with reachable senders at a mainnet-like rate over a 24 h window, and N4 (the fluff-epoch leak) computed from the
    existing relay logs first.
    (a) 2026-10-27 12:25: N4 computed from the existing archives (E58) — the fluff-epoch leak is
    redundant with first-hop stem exposure at every measured adversary strength (oracle adds zero
    txs) and undetectable from first-fluff cues at lab density; X1 needs no fluff-specific instrument
    beyond the txrelay logs it already writes, and alone.
    (b) 2026-10-27 12:20: X1a designed (P51) — E27's shape with the sender population rebuilt to mainnet:
    40 users at ~2 tx/day (43200 s), 60 occasional reachable at ~4/day, 6 busy at 1/h, ~530 txs per 24 h
    of activity (~0.7x mainnet's network rate), 40 h stop with the fixed RandomX seed. Tooling:
    `make_lean --window/--user-interval/--reachable-senders/--busy-senders` (tags `_mw/_ui/_rs/_bs`);
    the estimators need no change — senders class themselves by blocked inbound ports and tx counts.
    (c) 2026-10-27 19:12, from E61 (P51): closed. The class table at mainnet rate: unreachable precision 1.000
    (recall 0.146, 21.6% of users exposed in 24 h); reachable-occasional precision 0.265 with recall 0.388 (its
    first-hop cap — reachability doubles per-tx exposure) and 77.6% exposed in 24 h; busy precision 0.843, 86%
    exposed. The reachability test (sp_r) stays the correct filter for the unreachable class; the 10x-rate variant
    of the plan's X1 arm remains optional, not needed for the class answer.
13. **An adversary that keeps itself newest** (added 2026-10-25 15:13, from the plan review; open question 10 (c) made a cell). Every spy run so
    far is passive variant R. A fleet that re-handshakes with honest nodes periodically keeps its `last_seen` fresh everywhere, which under the
    stock rule makes the 2.2x a floor and removes the users' accidental 0.75x, and under the random-sample rule with the cubic draw still buys
    the newest-of-20 preference (E43's 1.28x residual). Needs: an agent on the py-Levin tooling or a `--sim-*` flag on the variant-R spies that
    dials, handshakes and disconnects on a timer; two seeds under the stock rule, with user-side peer-list dumps so the cell also answers (d).
    (a) 2026-10-26 02:32: the adversary is built — `agents/spy_refresh.py` (`make_lean.py --spy-refresh N`, `_srN`), the build assigned by the
    user to the agent after the 10-25 classifier stops. It is the 10-25 sketch made concrete: per spy, every N sim-seconds it handshakes every
    honest reachable node advertising the spy daemon's own port and peer id (the id from the daemon's own handshake response, the chain state
    from its RPC), so each target's `try_ping` lands on the daemon and `append_with_peer_white` refreshes the spy's white entry. Verified in
    the source (`4f92268d7`): an inbound handshake alone writes nothing, gossip never refreshes `last_seen`, and an unreachable node's spy
    entries refresh only through that node's own connections — so the dial set is the reachable population, and this item's "removes the users'
    accidental 0.75x" is now a prediction to test rather than an assumption (the users' dumps decide). `--user-dumps` (`_ud`) adds the
    user-side peer-list dumps for (d). Generation-validated on the control box; not yet run against a daemon; no cell queued.
    (b) 2026-10-26 04:21, from the first smoke (run 88, `lean_24_none_h71_k1_p2_m13_sr60_ud_s12345`, exit 0, 47 m wall): the v1 design is a no-op. Every handshake and ping-back succeeds (probe logs: NEW CONNECTION -> COMMAND_HANDSHAKE -> `try_ping` -> PING SUCCESS, every sweep, on every spy), but the spies' white entries' `last_seen` never moved: median age 20,288 s at the end against the honest entries' 18,586 s. The source explains it: `try_ping`'s success callback calls `append_with_peer_white(pe)` with the default `trust_last_seen=false`, and the guard preserves an existing entry's timestamp (net_peerlist.h: "do not overwrite the last seen timestamp, incoming peer lists are untrusted"). Only a node's OWN outbound connections refresh timestamps (`set_peer_just_seen`, trust=true). **The threat as this item imagined it — a fleet that re-handshakes to stay newest — does not exist against stock monerod, lab or mainnet.** What the ping path does instead: it INSERTS a fresh white entry (last_seen=now) at the ADVERTISED (socket ip, my_port) whenever that address is not yet white, and the outbound draw's port-dedup keeps only the NEWEST entry per host (`foreach` walks the white list newest-first), so the advertiser's freshest port becomes the host's representative in the newest-20 candidate cut. v2 is therefore a rotating FRONT END: the agent listens on ports 18090..18153, serves the daemon's identity, chain state and white list, and advertises a new port every 1800 s (an inserted entry ages from its insert; only a new port is fresh again, and a node connected to a front port refreshes it via its own timed syncs). Read in the cells: the inserts accumulate (38 ports x 42 spies over 19 h) against the 1000-entry white cap, so the stock-rule cell's lists flood by construction — the adversary distorts the lists it is measured against, which is part of the threat; the probes' dumps carry it.
    (c) 2026-10-26 07:36: smoke #2 (v2, the rotating front ends) passes. Light **0.2299 = 12.7x** the smoke cell's 0.0181 ceiling against v1's 0.0179; the relays' and observers' lists hold 12-13 accumulated front entries, the freshest **~102 s old against the honest entries' ~19,600 s** (a 200x freshness gap), at rank 0.10-0.15 of the newest order. The unreachable users hold fresh front entries too: gossip carries them into the users' gray lists and the users' own gray-list dials promote them to white — a route this item had not considered, and the reason the users' 0.75x protection is not protected from this adversary (P44 (b) reverses the earlier draft). P44/P45 (the spread fleet under v2, two seeds) are filed below and queued on `simbox3`.
    (d) 2026-10-26 12:31, from E53 (P44): the adversary saturates. The lists do not flood — `evict_host_from_peerlist` keeps one entry per host, so the rotation replaces the spy's entry and every list reads 299 honest + 42 fronts, the newest entry in every list a spy front. Every candidate rule with a newest cut is defenseless; the uniform draw is the set's survivor (P46) and the trim the amplifier (P47). P45 replicates at seed 23456.
    (e) 2026-10-26 17:22, from E55 (P46): the candidate set is exhausted. The uniform draw cuts the eclipse to 0.5994 and restores direct attribution (sp 0.181 at 1.000) but cannot hold the subnet share — the fronts' immortal connections accumulate outbound slots under any draw while honest peers churn their own. The recommendation reverts to the list defenses; the responder-hold advantage is what new defense work must attack. P47 (the trim) runs.
    (f) 2026-10-26 22:09, from E56 (P47): the arc's last cell inverts the story. Against the active adversary the trim reads **0.0248** with 1 of 40 users exposed — the strongest defense measured in this program, passive or active. Mechanism: a trimmed list forces a fast honest refresh cycle (entry ages 208-742 s) that outruns the adversary's rotation; fronts age past the horizon and are evicted; the adversary's inserts force the honest redraws that refresh the network. The trim converts dialing budget into refresh rate — its strength is adversary-relative, and P48 (60 s rotation) prices it. Summary of the five adversary cells (light, vs the 0.1531 ceiling): stock 0.9083, cap-lifted-uniform 0.5994, trimmed-70 0.0248; passive: stock 0.3369, trimmed-70 0.1616. The candidate-rule line is closed: every rule is defenseless untrimmed, and the trim — which mainnet already has — is the defense.
    (g) 2026-10-27 00:52, from E57 (P48), the arc's closing word: at a 60 s rotation the share reads 0.0262 against 0.0248 at 1800 s — the budget axis is the sweep cadence (dials per node per second), and at 300 s sweeps the adversary cannot refresh faster than the honest cycle a trimmed list forces. Closing recommendation: of everything measured in this program, only the white-list trim defends against the active adversary, and mainnet already has it (the 1000-entry cap); the open question is whether mainnet's real ratio (1000 of ~4,600) is tight enough to force the lab's fast refresh cycle — a dump question (open question 8), not a simulation one.
    (h) 2026-10-27 14:20, from E59 (P49): the budget axis is closed. Measured: 300 s sweeps 0.0248, and the lab's
    deliverable floor (~1,076 s effective front age at a configured 60 s) 0.0239 — the trim's protection is
    budget-independent across everything Shadow can deliver, because the honest refresh cycle meets the insert
    rate rather than competing at a fixed speed. The regime a real fleet could run (true 1-2 minute sweeps, at
    or below mainnet's minutes-fresh cut) is out of the lab's reach without a compiled dialer, and is bounded
    by OQ8's dump evidence instead: on mainnet the cut itself is 1.4-8.8 m fresh, so the honest side already
    refreshes at the rate the adversary would need to beat. The program's recommendation is final: the
    white-list trim is the defense, passive and active, and the arms race prices out of the lab's range.

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
| 10-23 18:10 | Three registered `simbox3` archives (P6a `20261022_222209_lean_legacy_none_h71_k1_s12345`, the TRIP run `20261022_234237_..._w24h_m113_s12345`, P9's patch test `20261023_035553_..._w18h_fx_s12345`) copied to `phantom`'s pool (`/mnt/ssdpool/monerosim_archives/`, rsync, file counts and bytes verified equal) and then removed from `simbox3` | `simbox3` had 60 GB free with a 7.6 GB filler archive growing and a 508-daemon 30 h cell (P16b, about 15 GB) next; the 45 GB floor would have been crossed. Nothing is lost: the register holds each run's scoring files and the raw archives are on `phantom` | copy them back with rsync from `phantom` | agent |
| 10-23 20:55 | `simbox2` drained at 20:47 (P15 done). Instead of leaving it idle for the handover to the selfish-mining project, P17 was filed and queued there: `lean_24_none_h300_k42_w13h_m1_n600_s12345` (42 spy /24s at 1 spy each, 384 daemons, ~2.5 h), the first direct test of the candidate-count reading that E23 and E24 arrived at | The other project's agent has no key on the control box yet, so the box would sit idle tonight; the cell costs 2.5 h and settles whether the excess scales with the number of distinct candidates. Risk: delays the handover by one cell. Undo: kill the driver by pid; the cell yaml is on both boxes (md5 d4ce41fd) |
| 10-23 21:43 | `phantom` drained at 21:38 (P16a done, E26). P18 filed and queued there: `lean_legacy_none_h300_k42_w13h_m1_n600_s12345`, P17's layout under the old rule (~2.5 h) | Pairs with P17 so the two rules are compared at the 42-/24 layout as E19/E23 compared them at 21; tests whether the /24 layout matters where the selection ignores it. Risk: 2.5 h of the generator box, 27 GB free is enough for 384 daemons. Undo: kill the driver by pid; cell md5 67c4fc98 |
| 10-23 23:35 | `simbox2` drained at 23:30 (P17 done, E27). P19 filed and queued there: the seed-23456 replicate of E27's cell (~2.5 h) | E27 is the strongest single number in the journal (0.337 light, 27 of 40 users exposed) and the family's other headline cells have a seed replicate (E21, E23b); the other project cannot use the box before morning. Risk: the handover slips one more cell. Undo: kill the driver by pid; cell md5 16faa462 on both boxes |
| 10-24 00:26 | `phantom` drained at 00:20 (P18 done, E28). P20 filed and queued there: E27's spread fleet with the full 42-entry ban list on half the nodes (`lean_24_half_h300_k42_w13h_m1_n600_s12345`, ~2.5 h) | E27/E28 leave the ban list as the only defence against a 1-per-/24 fleet (open question 7 at 42 /24s); E25 is the template. Risk: 2.5 h of the generator box, 27 GB free. Undo: kill the driver by pid; cell md5 31fe7669, ban list `banlist_h300_k42_w13h_m1_n600_s12345.txt` (42 lines) |
| 10-24 02:14 | `simbox2` drained at 02:10 (P19 done, E27b) and is left idle: nothing new queued | The user's plan gives the small boxes to the selfish-mining project once their queues drain, and the open questions left (P16b, P20) are running on the other two boxes; a further cell here would only delay the handover. Risk: idle hardware until the other agent has its key. Undo: queue a cell (`~/queue/q.txt`, restart the driver) |
| 10-24 03:08 | `phantom` drained at 03:02 (P20 done, E29) and is left idle until P16b lands (~03:30) | The next cell depends on P16b's reading (whether 8 per /24 settles below 2 per /24 at steady state): if the multiplier holds there too, the spread fleet's 24 h steady state (`k42_w24h_m1_fx`) is the natural headline cell; open question 10's probe needs a monerod-sim flag first. Risk: under an hour idle. Undo: queue a cell |
| 10-24 03:31 | P16b's 16.6 GB archive (`20261023_201931_..._w24h_m8_n600_fx_s12345`) copied from `simbox3` to `phantom`'s pool (`/mnt/ssdpool/monerosim_archives/`, 3,254 files and 16,644,449,296 bytes on both sides) and removed on `simbox3`: 52 GB free became 63 GB | The two seed-34567 fillers add about 10 GB and the 45 GB floor would have been crossed. Risk: none measured (counts and bytes equal). Undo: copy it back |
| 10-24 03:31 | P21 filed and queued on `phantom`: the spread fleet at a 24 h warmup (`lean_24_none_h300_k42_w24h_m1_n600_fx_s12345`, ~4 h) | E27-E29 make the spread fleet the headline layout and its steady state is unmeasured; E30 showed the 21-/24 fleets settle in six hours, so a flat 24 h read would let E27's 2.2x be quoted as a steady state. Risk: 4 h of the generator box. Undo: kill the driver by pid; cell md5 dd1f63eb |
| 10-24 03:46 | Session moves to the control box (user). On `phantom`, `~/queue/` created with the standard driver (`x0_queue.sh`, archives on the ssd pool) and an events symlink to the running driver's log, so all three boxes are watched and driven the same way from `antiproxy@virt9900x`; takeover steps written at the top of `.claude/HANDOFF.md` | The old session's watchers die with it; the drivers and P21 do not. Risk: the symlink points into `/tmp` until P21 finishes (to be replaced by a real copy then). Undo: none needed |
| 10-24 04:10 | The user pushed `feat/spy-relay-log` to `origin` (GitHub), `7612d25f..edf1787b` (36 commits), stamped 04:12 by the user; a fetch from the control box at 04:10 by its clock already read `origin/feat/spy-relay-log` at `edf1787b`. Pushing stays the user's call each time unless they say otherwise: the agent commits and does not push | the user's decision | the pushed commits are public; rewriting `origin` back to `7612d25f` is the user's call only | user |
| 10-24 04:10 | `simbox2` stays drained and idle: nothing is queued there. Its two handover steps, copying its 21 archives (`~/monerosim_archives`) to `phantom`'s pool and writing `~/BOX_HANDOVER.md`, wait for the user's go | the box goes to the selfish-mining project; the user sequences the handover | - | user |
| 10-24 05:04 | The `selfishmining` account on the control box completed from this session at the user's request (the user had made its key): ssh aliases `tr` (lever65@192.168.1.33, `zenith2alpha`: 64 threads, 251 GB, Ubuntu 24.04.5, idle at 05:00) and `box80`-`box82` (the PoW fleet, 192.168.1.80-82); clone of `main` at `4a68cd7a` (GitHub's head, equal to the Threadripper's `/scratch/monerosim_dev/monerosim`) with its three untracked files and its 34 MB `.claude/` (the PoW agent's `HANDOFF.md` of 04:40, campaign dirs 5-9) copied in; venv (`monerosim` 0.1.0, 38 packages); Claude Code 2.1.310 under `~/.local`; `~/.claude` settings, statusline, skills, plugins and frugal copied with `/home/lever65` rewritten in `settings.json` and two plugin manifests; the two memory sets copied to `projects/-home-selfishmining-monerosim/memory` (11 files, the repo key) and `projects/-home-selfishmining/memory` (8, the parent-dir key), paths inside them untouched. Access was the `antiproxy` key, added to `selfishmining`'s `authorized_keys` by the user | the user asked this session to finish the setup so the PoW agent's session can move to the control box, as this one did | remove the `antiproxy` line from `/home/selfishmining/.ssh/authorized_keys`; `rm -rf /home/selfishmining/{monerosim,.claude,.local,.ssh/config}` | user (decision), agent (execution) |
| 10-24 05:15 | The lab's `antiproxy` account on the Threadripper `zenith2alpha` (the PoW project's box, idle; the user created the user with sudo and this box's key) set up from here: clone of the branch at `c821c070` (GitHub's head plus the two local commits, pushed over ssh into a clone with `receive.denyCurrentBranch updateInstead`); live runs on the Optane `/fast/antiproxy/monerosim_archives` (xfs, 548 GB free), finished archives to be moved to `/spinny/readfrom/20261024_monerosim_research_effort/archives` (the ZFS array, 31 TB free; the directory the user gave); KSM left at the other project's setting (run 1, 10000 pages, 20 ms; phantom runs 20000); `setup.sh --clean --sim-binary` started at 05:15 with stdin closed, which died at the first prompt (`read` returns EOF under `set -euo pipefail`; nothing was built; this row first went in with that time blank, corrected 05:17), relaunched at 05:17 as `yes '' | ./setup.sh --clean --sim-binary` under one `setsid nohup`, so every prompt reads an empty answer and takes its default (proceed, install Shadow, no test sim; log `~/setup_sim.log`, the failed one kept as `~/setup_sim.failed_0515.log`); the standard driver installed at `~/queue/x0_queue.sh` with only `REPO`, `S` and `ARCH` rewritten; the H=71 `legacy` validation cell copied from this clone (md5 `8a79b809`, equal to phantom's) and P22 filed. The cell is queued when the build is done | the user's plan moves the lab's big cells here, and nothing runs on the box now; Shadow's many small writes want the fast disk and the array holds the results; a shared kernel knob (KSM) is not changed under another project's feet without a measured need | `sudo deluser --remove-home antiproxy` there, `sudo rm -rf /fast/antiproxy /spinny/readfrom/20261024_monerosim_research_effort/archives` | user (decision), agent (execution) |
| 10-24 05:25 | The `antiproxy` key removed from `/home/selfishmining/.ssh/authorized_keys` on the control box (2 lines to 1; `ssh selfishmining@localhost` from this account now refused): the PoW agent's session is up there and the setup access of 05:00 is no longer needed | the user asked, once that session was running; the per-user separation on the control box is restored | re-add the key line, as the user did at 04:50 | user (decision), agent (execution) |
| 10-24 06:01 | The cell generator moves to the control box. The owner gave `antiproxy` sudo here and ran `setup.sh` plain (its apt dependencies, Shadow, vanilla `monerod`); I ran the `--sim-binary` step alone (`run_install_sim.sh`, 5 jobs, 3 min: `monerod-sim` sha256 `fb7df009...`, 9 patches, `--help` probe passes) and restored phantom's `calibration.json` (md5 `e5276ee0`), which setup had replaced with this box's own (p95 28.2 ms against phantom's 36.7 ms; kept beside it as `calibration.json.virt9900x`). Also copied from phantom: its 1.5 MB chain-snapshot template cache (key `a17488322c7a9c0a`, manifest-keyed, so a cache hit here needs no daemon). `scripts/calibrate.py:_get_core_count` honours `MONEROSIM_CORES` (923 unit tests pass) and `docs/spy_journal/drivers/make_cell.sh` wraps `make_lean.py` with the pin and a calibration md5 check. Verified byte-identical to phantom on two cells (section 2 addendum). An hour of hand-copying binaries and libraries from phantom preceded this and was discarded: the five missing shared libraries were setup.sh's own apt list, which is where this should have started | the user asked whether the generator could run here; the rule's two host inputs are pinnable, so phantom is out of the loop for every cell | generate on phantom again; `git revert` this commit; `rm -rf ~/.monerosim ~/monerosim/{target,sibling_repos}` on the control box | user (decision), agent (execution) |
| 10-24 06:17 | P22 hit on all four clauses (0.0624, 43 min, checks pass, provenance equal apart from `built:`). P23 filed and queued on `zenith2alpha`: P21's seed-23456 replicate (`lean_24_none_h300_k42_w24h_m1_n600_fx_s23456`, md5 `93e4bfa5`, the first cell generated on the control box with `make_cell.sh`, copied with an md5 check) | the Threadripper is validated and idle; P21 lands at ~07:30 and the headline 24 h steady state deserves a second seed as E27 got (E27b); the probe for open question 10 needs a `--sim-*` patch first, which this run leaves time to write. Risk: ~2.5 h of the box. Undo: kill the driver by pid | agent |
| 10-24 06:26 | Open question 10's probe flag written and built: `patches/monero-sim-uniform-whitelist-pick.patch` adds `--sim-uniform-whitelist-pick` (off by default; on, the white-list pick is `crypto::rand_idx` over the same candidates instead of the cubic `get_random_index_with_fixed_probability`; a startup log line names it). Made on the control box from a scratch worktree with the nine vendored patches applied and committed as base; all ten apply in order on a fresh worktree; appended to `setup.sh`'s list; `make_lean.py --uniform-pick` puts it in `daemon_defaults` and tags the name `_up`; 924 unit tests pass. Built here (`monerod-sim` sha256 `1e0edfb3...`, 10 patches, `--help` lists the flag). The probe cell `lean_24_none_h300_k42_w13h_m1_n600_up_s12345` generated with `make_cell.sh` (md5 `33ca7b5b`, one line from E27's cell). P24 (the probe, on `zenith2alpha` after P23) and P25 (the flag-off check, on `phantom` after P21) filed; committed as `6ba2809b` and pushed to both boxes' clones. Rebuilds there only after their running cells end (a mapped binary is not replaced under live daemons); `simbox3` keeps the nine-patch binary until its queue drains | the handoff's next step; E21's reading has never been tested by varying the pick itself | remove the patch from `setup.sh`'s list and rebuild; the flag is off by default, so no existing cell changes | agent |
| 10-24 07:21 | `phantom` drained at 07:19 (P21 done, E32). Its `~/queue/x0_queue.events` symlink replaced by a real copy (109 lines); `monerod-sim` rebuilt there with the ten patches (`run_install_sim.sh`, 12 jobs, ~3 min with ccache; sha256 `b8d6fbb6...`, `--help` lists the flag), then P21 scored | nothing ran on the box; the P25 check needs the new binary | reinstall from the nine-patch list | agent |
| 10-24 07:27 | P25 queued on `phantom` (`lean_legacy_none_h71_k1_s12345`, flag off, the ten-patch binary's platform check, 0.055-0.066, ~45 min) with the standard driver `~/queue/x0_queue.sh` (archives on the ssd pool) | filed at 06:3x and committed before the queue; the old driver `x0_queue2.sh` exited with its queue | kill the driver by pid | agent |
| 10-24 08:14 | `phantom` drained at 08:11 (P25 done, E33) and is left idle: nothing queued | the archive-pool move to the Threadripper's array waits on the user's word about a ZFS child dataset; its first steps (an NFS mount on phantom and a 293 GB copy off its ssd pool) want the box idle, and the next headline cells belong on `zenith2alpha`. Risk: idle hardware until then. Undo: queue a cell | agent |
| 10-24 09:38 | P23 done on `zenith2alpha` at 09:36 (E34, 0.3524). Its `monerod-sim` rebuilt with the ten patches while the two scoring scripts ran (`run_install_sim.sh`, 24 jobs; sha256 `9cae7db31344...`, provenance lists 10 patches, `--help` lists the flag) | nothing of the lab's ran there and the scorers do not touch the binary; P24 needs it | reinstall from the nine-patch list | agent |
| 10-24 09:42 | P24 queued on `zenith2alpha`: `lean_24_none_h300_k42_w13h_m1_n600_up_s12345` (md5 `33ca7b5b` checked on the box before the start; the standard driver; Shadow at 32 workers; the first daemon logs carry the `--sim-uniform-whitelist-pick` line) | filed 06:24 and committed as `6ba2809b`; the box is validated (E31) and its binary carries the flag; E21's recency-pick reading has waited for this test since E21 | kill the driver by pid; the cell leaves no other state | agent |
| 10-24 09:55 | `simbox3` drained at 09:49 (the `tail` seed-34567 filler, E10's third seed, 0.1812) and left idle: nothing queued | its disk is at 49 GB free (the 45 GB floor for the shared VM); its archives go to the Threadripper's array with the pool move, which waits on the user's word; no filed prediction needs its nine-patch binary | queue a cell with the standard driver | agent |
| 10-24 13:53 | Archive pool moved to the Threadripper's array without a ZFS change, at the user's word (any user may do anything there; mixing with the `lever65` identity is fine): `/spinny/readfrom/20261024_monerosim_research_effort` set to mode 2777 (owner kept `lever65`) with `archives/` under it at 2777; `nfs-common` installed and `192.168.1.33:/spinny/readfrom/20261024_monerosim_research_effort` mounted at `/mnt/research` (fstab, `_netdev,nofail`) on `phantom`, `simbox2` and `simbox3`, write-tested from each. NFS squashes clients to uid 1000 and the setgid directory gives new files group 1015, so the Threadripper's `antiproxy` keeps write access. Copies started, detached rsync: phantom's 38 archives (304 GB), simbox3's 5 (40 GB), the Threadripper's two finished runs (13 GB, local). Sources stay until the copies are verified and the user says to delete; simbox2's 21 archives wait for the user's go | the pool sat on phantom's shared 32 GB box; the array has 31 TB free and is on the box that runs the headline cells | unmount and drop the fstab lines; the copies are plain directories | agent |
| 10-24 13:58 | P24 scored (E35, 0.3207: the 0.28-and-above branch, E21's recency-pick reading refuted as the cause of the 2.2x); `zenith2alpha` has been idle since 12:01 and stays idle until the next probe is filed. P24's finish at 12:01 went unnoticed for two hours because its watcher was armed with the events file's line count (9) instead of the terminal-event count (4), so it could never fire; the watcher's argument is the count of DONE/EMPTY lines | nothing queued behind it on purpose: the next probe (the 20-candidate cap, E35) needs a patch and a prediction first | none needed | agent |
| 10-24 14:17 | Pool copies switched from NFS to rsync over ssh into the Threadripper's `antiproxy` account (phantom's, simbox3's and simbox2's `lever65` keys added to its `authorized_keys`; `--chmod=Dugo+rwx,Fugo+rw`): over NFS the 100k-file pool moved at ~5 MB/s although the link does 99 MB/s. simbox2's handover started at the user's word: its 21 archives (172 GB) copying since 14:17, `~/BOX_HANDOVER.md` written there (copy in `docs/spy_journal/BOX_HANDOVER_simbox2.md`) for the selfish-mining agent; the box leaves the lab. Nothing is deleted on any source box until the copies are verified and the user says so | phantom (.22) and simbox2 (.25) go to the selfish-mining project; the lab keeps `zenith2alpha` and `simbox3` | re-copy from the sources, which stay | agent |
| 10-24 14:25 | `phantom`'s handover note written (`~/BOX_HANDOVER.md` there, copy in `docs/spy_journal/BOX_HANDOVER_phantom.md`): the lab's footprint (the 304 GB pool, copying out; `~/.monerosim`; `~/queue`; the old sessions' scratch) against the owner's workstation contents and the real testnet daemon; the 77 GB `archived_runs/` in the clone is the selfish-mining project's own earlier output, not the lab's. The box leaves the lab when the pool copy is verified | the user asked that both .22 and .25 be explained for the selfish-mining agent | none needed | agent |
| 10-24 14:28 | `selfishmining` accounts created on `phantom` (uid 1004) and `simbox2` (uid 1003) at the user's word: passwordless sudo (`/etc/sudoers.d/selfishmining`), empty `~/.ssh/authorized_keys` for the user to fill; nothing of `lever65`'s touched. Both handover notes also placed on the coordinator at `/srv/lab_handover/` (world-readable) for the selfish-mining agent, which runs there | the user chose separate accounts over sharing `lever65`; the agent reads the notes from the box it runs on | `userdel -r selfishmining` on each box; `rm -r /srv/lab_handover` | agent |
| 10-24 14:41 | Open question 10, next probe: `patches/monero-sim-whitelist-candidates.patch` (`--sim-whitelist-candidates N`, default 20 = stock, 0 = no cap; the cap line of the stock `24` path only, `legacy` untouched; startup log line when not 20) made from the ten-patch worktree committed as base; appended to `setup.sh`; `make_lean.py --wl-cands N` (`_wcN`). Built on the control box (`monerod-sim` sha256 `73084f13b316...`, 11 patches, `--help` lists both flags). Cells generated with `make_cell.sh`: `lean_24_none_h300_k42_w13h_m1_n600_up_wc0_s12345` (md5 `1c7d3c44`, P26) and `..._wc0_s12345` (md5 `3ac6e34d`, the cap lifted with the stock cubic draw; the Monte Carlo's `24allc` mode gives 0.1242 = 1.51x, P27 filed 14:42). P26 filed; `zenith2alpha` to be rebuilt and P26 queued | E35 left the cap as the leading candidate and the Monte Carlo (0.0796 with it lifted) says so too | remove the patch from `setup.sh`'s list and rebuild; default 20 changes nothing for existing cells | agent |
| 10-24 14:45 | `zenith2alpha` rebuilt with the eleven patches (`run_install_sim.sh`, 24 jobs; sha256 `8d8255edb4ea...`, provenance 11 patches, `--help` lists both flags); both cells copied with md5 checks; P26 started 14:44 with P27 queued behind it in `q.txt` (the standard driver reads the next line when a cell ends); watcher armed with the terminal-event count (6) | both predictions filed and committed (`d61eefa1`); the box was idle | kill the driver by pid; `q.txt` holds the second cell | agent |
| 10-24 15:48 | Archive copies verified on the Threadripper's array: `simbox3`'s 5 runs (14,185 files; dry-run rsync clean) and `simbox2`'s 21 runs (58,373 files; dry-run clean, `EXIT 0`). Verification is by file count and a dry-run rsync, not by size: the array compresses the daemon logs about 12x (`compression=on`), so `du` there understates by an order of magnitude. Dated verification lines appended to simbox2's handover note (on the box, in `/srv/lab_handover/`, in `docs/spy_journal/`). Sources untouched; deleting them is the owner's call | the handover notes promised the agent a recorded verification before any deletion | none needed | agent |
| 10-24 16:06 | `phantom`'s pool verified on the array (38 runs, 100,813 files both sides, dry-run rsync clean). The archive pool is now `/spinny/readfrom/20261024_monerosim_research_effort/archives/` on the Threadripper: 67 runs, 179,953 files, ~830 GB apparent in ~35 GB of disk. `phantom` leaves the lab: the `phantom` git remote removed from the control-box clone (the owner's checkout is no longer pushed into), its handover note carries the verification (that note's copy went out in `2b3cf087`, whose journal row this is). Source folders on phantom and simbox2 stay until the owner deletes them | the user asked to be told when the copy verified; nothing of the lab's remains to do on .22 | `git remote add phantom ssh://phantom/home/lever65/monerosim` | agent |
| 10-24 18:26 | Source archive folders deleted on the user's word: `phantom:/mnt/ssdpool/monerosim_archives` (38 runs, 100,813 files; `/mnt/ssdpool` 322 -> 18 GB used, 422 GB free) and `simbox2:~/monerosim_archives` (21 runs, 58,373 files; `/` 665 -> 494 GB used, 347 GB free), each `rm -rf` run only after a final dry-run rsync against the array in the same minute listed nothing to send (regular files transferred 0 of 100,813 and 0 of 58,373; `~/queue/final_dryrun.txt` on each box). Dated deletion lines appended to both handover notes (on the boxes, in `/srv/lab_handover/`, in `docs/spy_journal/`). The array is now the only copy of those 59 runs; simbox3's 5 and the Threadripper's own stay local as well | the user said "go ahead and delete the source archives on .22 and .25" after the 16:06 verification | none: the sources are gone; the array copy was verified twice (16:06 and 18:26) | user |
| 10-24 18:40 | P26 scored on `zenith2alpha` (estimators and `spy_share_vs_time` detached there, the six small files fetched, run 74 in the register) and written up as E36: five of six clauses, the cap confirmed as the whole multiplier, the exposure clause missed upward (37 of 40). P26's archive stays on `/fast` until P27 ends (no extra disk traffic under a timed run), then moves to the array. P27 running since 17:15 (68% at 18:32, due ~19:15); E37 when it lands. Then the queue turns to a second seed of P26 (`s23456`, the 1% replication the family has had since E27b) and to the users' side of open question 10 | the cap reading is one cell deep and the exposure finding reverses the policy reading, so it needs a replicate before anything is claimed; the owner decides which number the defense work targets | none | agent |
| 10-24 18:45 | P28 filed: P26 at seed 23456 (`make_cell.sh`, the same arguments with `--seed 23456`; md5 `975cee8e`; the diff against P26's cell is the seed line alone), to run on `zenith2alpha` behind P27 by appending it to `q.txt` (the driver reads the next line when P27 ends, so no idle gap). simbox3 was the alternative but sits at 49 GB free with its 5 local archives still in place (deleting them is the user's call), below the lab's 45 GB floor once a 384-daemon archive lands, and still runs the nine-patch binary | the cap result reverses the policy reading of open question 10 and is one seed deep; the family's replicate practice (E27b) is a second seed before any claim | remove the line from `q.txt` before P27 ends, or stop the driver by pid | agent |
| 10-25 00:40 | Archives *moved*, not copied, from the lab's own boxes (the user, 00:30: "don't you have the ability to move the local archives to the spinny on .33?"): simbox3's five local archives deleted after a final dry-run rsync against the array compared 14,185 regular files and listed none to send (`/` 49 -> 89 GB free; the driver's empty `~/monerosim_archives` recreated); the Threadripper's six `/fast` archives (three not yet on the array: P26, P27, P28) copying to the array under `nice`/`ionice`, to be deleted from `/fast` after the same dry-run check once their scoring has read them. P27 (DONE 19:34, **0.1705**) and P28 (DONE 21:53, **0.1557**) scoring detached on the box; the queue had been empty since 21:53. P29 filed (the 24 h spread fleet with the cap lifted, md5 `527a8a60`) and the driver restarted on it | the box was idle and the move is the standing plan; the deletion half had been waiting on the user's word, which this message gives for the lab's boxes | re-copy from the array (`rsync` back); stop the driver by pid | user, agent |
| 10-25 00:55 | P27 and P28 scored on `zenith2alpha` and written up as E37 and E38 (runs 75 and 76 in the register). P27 missed low (0.1705 against 0.19-0.28): the Monte Carlo's `24allc` mode is wrong for the draw-shape-only case (it never removes connected /24s from the candidate set), left as is and noted in open question 10. The six finished `/fast` archives (P22-P24, P26-P28) deleted after a dry-run rsync against the array that excluded P29's live run folder listed nothing to send; new runs still land on `/fast` and move after scoring | the array copy verified; the moves are the standing plan (00:40 row) | re-copy from the array | agent |
| 10-25 03:30 | P30 filed (P26 at seed 34567, `make_cell.sh` with the same arguments and `--seed 34567`; md5 `e6e99b47`; the seed line alone differs from P28's cell) and queued on `simbox3`, the first cell on its eleven-patch binary (rebuilt 00:46 with `run_install_sim.sh`, `EXIT 0`, sha `14852a861c75`, both `--sim-*` flags in `--help`, eleven patches in the provenance with zenith2alpha's patch hashes); P31 filed (E29's half-list cell with `--uniform-pick --wl-cands 0`; md5 `49e10cf7`; the two flag lines and the ban-list file's name and path the only differences, the 42-line list byte-identical) and appended to zenith2alpha's `q.txt` behind P29, which the driver reads when P29 ends. Both cells copied with md5 checks. The user, 03:20: "proceed with your recommendations" (the third seed on the idle simbox3, the half list on the Threadripper after P29) | the third seed costs no new code and simbox3 is idle; the half list is the defense question that open question 10 reopened (does the list's 0.55x survive without the multiplier?) | remove the line from `q.txt` before P29 ends; stop simbox3's driver by pid | user, agent |
| 10-25 04:20 | P29 scored on `zenith2alpha` (estimators and `spy_share_vs_time` detached under `nice`, P31 already running) and written up as E39 (run 77 in the register; outcome under P29, open question 10 (g), status). Its archive moved to the array: copied under `nice`/`ionice` while the scorer read it, verified by regular-file count (2,624 both sides) and a dry-run rsync that listed nothing to send, then the `/fast` copy deleted (548 GB free; P31's live run is the only folder left there; the array holds 71 runs). The events log snapshot in `logs/` now runs through P31's START | the standing plan (00:40 row): score, register, move the same day | re-copy from the array | agent |
| 10-25 06:50 | P31 scored on `zenith2alpha` (detached estimators and `spy_share_vs_time`, the box otherwise idle) and written up as E40 (run 78 in the register; outcome under P31, open question 10 (h), status). Its archive moved to the array: copied under `nice`/`ionice`, verified by regular-file count (2,624 both sides) and a dry-run rsync that listed nothing to send, then the `/fast` copy deleted (`/fast` holds no run now, 548 GB free; the array holds 72 runs). The events snapshot in `logs/` runs through the 06:15 `QUEUE EMPTY`. Nothing queued on the Threadripper: the user's 03:20 "proceed with your recommendations" covered P30 and P31, and the next cell is a new decision | the standing plan for scoring and moves; queueing a cell the user has not chosen is not | re-copy from the array | agent |
| 10-25 08:40 | P30 scored on `simbox3` (detached estimators and `spy_share_vs_time` there) and written up as E41 (run 79 in the register, box `simbox3`; outcome under P30, open question 10 (i), status). Its archive moved to the array over ssh into `antiproxy@192.168.1.33`: verified by regular-file count (2,624 both sides) and a dry-run rsync that listed nothing to send, then the local copy deleted (`simbox3` 91 GB free; the array holds 73 runs). simbox3's events snapshot added as `logs/queue_events_simbox3_through_20261025.events`. Both boxes idle with nothing queued: the next cells are the user's decision (recommended: the twelfth patch, 20 random /24 candidates in place of the 20 newest, for the Threadripper; P31 at a second seed as a no-code filler) | the standing plan for scoring and moves; queueing beyond the user's go is not | re-copy from the array | agent |
| 10-25 09:00 | *(Correction 10:23: this row was written at about 10:20 and the user's message came between 08:50 and 10:20; the times were assumed, not read from the clock. P32 started 10:22.)* The user: "proceed with the twelfth patch, and queue P31 at seed 23456 meanwhile". P32 filed (P31's cell with `--seed 23456`; md5 `75763cc9`; the seed line alone differs, the list and the adopter set identical) and the Threadripper's driver restarted on it; it runs there rather than on the idle `simbox3` so the replicate shares P31's box and the ban-list paths need no rewriting (`make_cell.sh` writes this clone's absolute paths, which match `zenith2alpha`'s account but not simbox3's). The twelfth patch (`--sim-random-whitelist-candidates`: the N candidates drawn at random from the eligible white list instead of the N newest, the draw among them unchanged) is written next, with a Monte Carlo before its prediction, and built on `zenith2alpha` under `nice` while P32 runs | the user's decision; the replicate pins the 0.49x | remove the line from `q.txt`, or stop the driver by pid | user, agent |
| 10-25 10:35 | The twelfth patch written: `patches/monero-sim-random-whitelist-candidates.patch` (`--sim-random-whitelist-candidates`: the N white-list candidates, N = `--sim-whitelist-candidates`, stock 20, are a uniform random sample of the subnet-deduplicated list instead of its N newest by `last_seen`, put back into `last_seen` order so the draw among them, stock cubic or `--sim-uniform-whitelist-pick`, is unchanged; off = stock), wired into `setup.sh` and `make_lean.py --rand-cands` (`_rc`), with `recency_model.py` modes `24r`/`24ru` (commit `6d54bd32`). Built on `zenith2alpha` at 10:29 (twelve patches, sha `7534279c`, `git apply --check` clean on the eleven-patch tree) while P32 runs, which is safe because the running daemons keep the replaced binary's inode and P32's provenance was captured at its start; the same rebuild started on `simbox3` at 10:34, and P33 (filed above) waits for it so that no daemon starts across the binary swap. The Monte Carlo over E21's relay lists (`recency_relays.py <E21 archive> 24,24u,24all,24allc,24r,24ru`) runs on zenith2alpha (its first launch failed: `python -I` with a bare script name leaves the script's own directory off `sys.path`; relaunched as `./recency_relays.py`). Two `_rc` cells generated and copied with md5 checks (seed 12345 `14d453a7` to zenith2alpha for behind P32, seed 23456 `ed53b8cb` to simbox3 for behind P33); each is E27's stock cell plus the one flag line. Their predictions wait for the Monte Carlo | the user: "proceed with the twelfth patch" and, at 10:30, use the idle .176 | revert `6d54bd32`; rebuild with `run_install_sim.sh` from the previous commit | user, agent |
| 10-25 10:39 | simbox3's twelve-patch rebuild installed at 10:37 (`EXIT 0`, sha `7a7a32b3`, the new flag in `--help`, twelve patches in the provenance) and its driver started on P33 at 10:37. The Monte Carlo for the twelfth patch is in (P34's text): 20 random /24s with the cubic draw 1.53x, the same as the cap lifted with the cubic draw, which the sim read at 1.11x (E37); 20 random /24s drawn uniformly 0.97x. P34 (`_rc` seed 12345, md5 `14d453a7`) and P35 (`_rc` seed 23456, md5 `ed53b8cb`) filed and appended to `q.txt` on zenith2alpha (behind P32) and simbox3 (behind P33); each driver reads its next line when its run ends | the user's "proceed with the twelfth patch"; two seeds in parallel give the patch's answer by about 16:00 | remove the lines from `q.txt` before the running cells end | user, agent |
| 10-25 12:51 | P32 scored on `zenith2alpha` (detached under `nice`, P34 running) and written up as E42 (run 80 in the register; outcome under P32, open question 10 (j), status). Its archive moved to the array: copied under `nice`/`ionice`, verified by regular-file count (2,624 both sides) and a dry-run rsync excluding P34's live run that listed nothing to send, then the `/fast` copy deleted (548 GB free; the array holds 74 runs). The events snapshot in `logs/` runs through P34's START. (Commit `9b280e63` carried the register row, the run folder and the snapshot alone: the journal edit script had stopped on a stray anchor check before writing; this row and E42 are in the next commit) | the standing plan | re-copy from the array | agent |
| 10-25 15:13 | **The plan reviewed against its three questions** at the user's request ("can you do a deep review of the current plan to check that our proposed work will actually answer these questions?", then "proceed with those changes you recommend"): plan section 7 written (per-question assessment, seven ranked threats to validity, a revised order, what is settled), with dated notes at 3.3 (adopters' indirect protection not observed in the lab), 3.4 (the candidate-cap finding and its transfer caveat), X6 (needs the splice spy), 5.4 (order revised) and 6 (#9496 not landed on master at `3fd0f88c2`, checked today: `get_block_complete_entry` still uses `relay_category::all`). Open questions 11-13 added (honest cost under churn, the reachable sender classes, the active-recency adversary) and dated lines under 8 and 10. An independent reviewer with a fresh context read the same documents and reached the same ranking. Standing rule from the review: no further candidate-rule cell (including `_rc_up`) until the list-age, churn-cost and active-recency items are answered | the lab's main finding is a mechanism until its transfer and cost are measured; the recommendation must survive the developers' scrutiny | the section and notes are dated additions; nothing was deleted | user, agent |
| 10-25 15:13 | The thirteenth patch written and built: `patches/monero-sim-peerlist-limits.patch` (`--sim-white-peerlist-limit N`, `--sim-gray-peerlist-limit N`: `peerlist_manager::set_limits` replaces the compile-time 1000 / 5000 in `trim_white_peerlist` / `trim_gray_peerlist`, applied after `init` per zone; 0 = stock), `git apply --check` clean on the twelve-patch tree, wired into `setup.sh`; `make_lean.py --white-limit N` (`_wlN`), `--gray-limit N` (`_glN`) and `--turnover ON,OFF` (`general.turnover`, `_to<ON><OFF>`; a test cell with both passed the generator's Rust validation and was deleted). Commit `d8ba5f3e`; rebuilt on zenith2alpha 15:09 (sha `ab6646d7`, 13 patches, queue empty, nothing live); simbox3's rebuild waits until P35 has started there, so no daemon starts across the swap | the review's items 1 and 3 need both; the patch is the lab half of open question 8 | revert `d8ba5f3e`, rebuild | agent |
| 10-25 15:13 | P34 scored on `zenith2alpha` and written up as E43 (run 81 in the register; outcome under P34, open question 10 (k), status). Archive moved to the array (2,624 regular files both sides, dry-run clean, the `/fast` copy deleted; the array holds 75 runs). The events snapshot in `logs/` runs through the 15:01 `QUEUE EMPTY`. (Commit `6acae24c` carried the register row, the run folder and the snapshot alone: the edit script stopped on an anchor before writing; the review, E43 and these rows are in the next commit) | the standing plan | re-copy from the array | agent |
| 10-25 15:16 | P36 and P37 filed and queued on `zenith2alpha` (the driver restarted on both lines): the stock and the cap-lifted spread-fleet cells with `--white-limit 70 --probe 3` (md5 `b432abe4`, `f248109b`; the limit line and the twelve probe relays' dump and log-level lines the only differences from E27's and P26's cells; the two cells differ from each other by the two flag lines alone). The review's item 1, lab half: does the cap finding survive a white list that cannot hold every peer? | the top-ranked transfer threat; the cells need no new code beyond the thirteenth patch | remove the lines from `q.txt`; stop the driver by pid | agent |
| 10-25 20:42 | Four runs landed while the session was stalled: P33 (simbox3, 15:16, **0.0792**), P36 (zenith2alpha, 17:36, **0.1616**), P35 (simbox3, 19:51, **0.1716**), P37 (zenith2alpha, 19:56, **0.1619**); both queues empty from 19:56. Scoring launched for all four (P33's in hand; its archive moved and deleted, 2,624 files, dry-run clean; run 82). The headline before the write-ups: with the white list trimmed to 70 entries the *stock* rule reads 1.06x the ceiling (P36 missed its 0.28-0.50 clause by a wide margin) and the cap-lifted rule the same 1.06x (P37): the trim alone removes the multiplier in the lab. Next cells filed per the review's items 1 and 3: P38/P39 (turnover, stock and cap-lifted, the cost baseline and its comparison) queued on zenith2alpha; P40/P41 (the trim sweep at 140 and 35) for simbox3 once its thirteen-patch rebuild (started 20:39) installs. The active-recency adversary (open question 13) is not started | the review's order; the trim result makes the sweep the most informative next cell on the transfer question | remove lines from `q.txt`; stop drivers by pid | agent |
| 10-25 20:49 | P36, P37 and P35 scored and written up as E45, E46 and E47 (runs 83-85; outcomes under their predictions; open question 8 and 10 (m), (n)); archives moved to the array (P36 and P37 from `/fast`, 2,636 regular files each with the probe dumps; P35 from simbox3 over ssh, 2,624; all dry-run clean, local copies deleted; the array holds 80 runs). simbox3 rebuilt with the thirteen patches at 20:42 (`EXIT 0`, sha `c1a4e670`, the limit flag in `--help`) and its driver started on P40 and P41 at 20:46. The plan's section 7, threat 1, carries a dated note on the trim result | the standing plan; the trim result reframes the cap finding and makes the sweep and the mainnet dump the decisive items | re-copy from the array; remove lines from `q.txt` | agent |
| 10-25 23:16 | P38 exited 1 at 23:00: 15 cycling user agents missed the end-of-run cleanup with their daemon offline (generator fix `5115b02b`: cycling agents get no end-of-run signal). Its cost read then showed no relay restarted: the generator keeps `hide-my-port: false` daemons up as pinned supernodes and every reachable lean-cell node sets it, so only the 40 users cycled. P39 (the same defect) stopped at 23:13, a minute in. `make_lean.py --turnover-reachable` adds `turnover: true` to the relays, medium nodes and observers (tag `_tor`); P42/P43 filed as the cells P38/P39 meant and queued on zenith2alpha | the cost comparison needs relays that churn; a users-only cell cannot test the liveness filter | remove lines from `q.txt`; stop the driver by pid | agent |
| 10-26 02:32 | The OQ13 adversary built, the build reassigned to this session by the user ("you can build the agent now, as you are a different llm backend"; the 10-25 classifier-stop split — the owner writes it — is superseded). `agents/spy_refresh.py`: a py-Levin dialer on each spy that every interval handshakes every honest reachable node advertising the spy daemon's own port and peer id (learned from the daemon's own handshake response; chain state from its RPC), so each target's `try_ping` lands on the daemon and `append_with_peer_white` refreshes the spy's entry — the mechanism source-verified at `4f92268d7`: an inbound handshake writes nothing by itself, gossip never refreshes `last_seen`, the entry is keyed by socket ip + advertised `my_port`. Unreachable users are excluded from the dial set (their spy entries refresh only through their own connections, the mainnet-faithful reading; the users' 0.75x survival becomes a prediction, not an assumption). `make_lean.py --spy-refresh N` (`_srN`) and `--user-dumps` (`_ud`, user-side peer-list dumps for 10 (d)). Generation-validated on the control box (wrapper args, `expected_final_state: exited 0`, the user dump flags in the resolved config); not run against a daemon; nothing queued. Nothing pushed to `origin` (owner 10-26); lab-box pushes only when cells queue | the plan review's revised order item 2; the user's reassignment | revert the commit; no cell uses the agent without `--spy-refresh` | user, agent |
| 10-26 04:25 | P40 scored on `simbox3` and written up as E49 (run 87 in the register; outcome under P40; open question 8 dated line; status). Archive moved to the array: the copy that failed while tr was down rerun over ssh (log `EXIT 0`), verified by regular-file count (2,636 both sides), the local copy deleted (89 GB free; the array holds 81 runs). The simbox3 events snapshot now extends to P41's start | the standing wrap-up plan | re-copy from the array | agent |
| 10-26 03:17 | tr recovered from the 01:25 hang and its queue restarted: rebooted 02:42, clean `dmesg` (no fs or I/O errors), `/fast` and `/spinny` mounted and healthy, P42's run dir lost empty (no partial to salvage, nothing to move), no lab processes left; P42 requeued unchanged with P43 behind it, both behind the OQ13 smoke cell (`lean_24_none_h71_k1_p2_m13_sr60_ud_s12345`, md5 `eb3363b2`, ~1 h wall) so a defect in `agents/spy_refresh.py` surfaces before the 8 h turnover pair; the branch pushed to tr only (`36734fdd..a0a708e4`; origin untouched, owner 10-26) | the handoff's recovery checklist; fast feedback first | remove lines from `q.txt`; stop the driver by pid; the smoke cell is disposable | agent |
| 10-26 04:21 | OQ13's first smoke (run 88, the 03:17 cell, exit 0, 47 m) scored, registered and read: the re-handshake refresh is a no-op — ping-backs succeed but `append_with_peer_white` preserves existing white entries' `last_seen` (`trust_last_seen=false`; only the node's own outbound connections refresh via `set_peer_just_seen`), so v1 cannot work against any stock monerod. v2 written and compiled: a rotating front end — the agent serves the daemon's identity on ports 18090..18153 and advertises a new port every 1800 s, inserting always-fresh entries that the draw's port-dedup (newest per host) makes the spy host's representative; E45's mechanism line corrected under open question 8. The smoke's archive moved to the array (1,430 regular files both sides, dry-run clean, local deleted). Smoke #2 (same cell file) queues on `simbox3` behind P41; P44/P45 wait for its read | the smoke exists to fail cheaply, and it found the design flaw in one hour | revert v2; the cell file is unchanged | agent |
| 10-26 07:36 | P41 scored on `simbox3` and written up as E50 (run 89; outcome under P41; open question 8's sweep-closing line; status): the trim sweep reads 0.99x at 35, flat with every capped reading, and the dumps add the negative control (the spies freshest in the list yet at their pool share — no cut, no concentration) | the standing wrap-up plan | re-copy from the array | agent |
| 10-26 07:36 | OQ13 smoke #2 read and **passed** (v2's rotating front ends): light 0.2299 = 12.7x the smoke cell's ceiling (v1 read 0.0179), the front entries ~102 s fresh against honest ~19,600 s at rank 0.10-0.15, and fresh entries in the unreachable users' lists via gray-list dials — P44/P45 filed (the spread fleet under v2 at two seeds, clauses (a) 0.40-0.75, (b) users ≥ 0.9x, (c) the dump mechanism checks, (d) wall) and queued on `simbox3`, whose queue was empty since 07:31 | the plan review's revised order item 2; the smoke's pass gates the real cells | remove lines from `q.txt`; stop the driver by pid | agent |
| 10-26 07:39 | P44/P45 queued on `simbox3` after a mis-generation caught at once: the first pair generated with `--warmup 21600` (w6h, E27's 15-19 h window halved) and stopped during the pre-run build (07:38 STOPPED, no run dir created); regenerated at w13h (md5 `3b55a0c0` seed 12345, `56143402` seed 23456) and the queue restarted 07:40. Run 90's estimator copies were fetched through a race with the scorer and repaired; its svt is in place. P41's and the smoke's archives are copying to the array (marker `move_P41_smoke2.done`), verified deletions follow | the predictions were filed against E27's w13h shape; w6h cells would not have answered them | the w6h cell files deleted on simbox3; nothing else to undo | agent |
| 10-26 08:06 | P42 scored on `zenith2alpha` and written up as E51 (run 91; outcome under P42; open question 11 (b); status; churn_cost files in the run dir; tr events snapshot `queue_events_tr_through_20261026b.events`). P41's and the smoke's archives verified on the array (2,636 and 1,430 both sides) and deleted from simbox3. the array. P42's archive moving to the array next | the standing wrap-up plan | re-copy from the array | agent |
| 10-26 11:40 | P43 scored on `zenith2alpha` and written up as E52 (run 92; outcome under P43; open question 11 (c) — the gate is read; churn_cost files in the run dir; events snapshot `...20261026c.events`). P45 moved from simbox3's queue to tr (generated there, md5 `9d1f1ca2`; simbox3's q.txt emptied so P44 ends the box's queue) after P43 finished at 11:19 — both boxes stay busy, the filed queue completes ~8 h earlier. P43's archive moving to the array next | the standing wrap-up plan; the box move is the queue's own scheduling | re-copy from the array | agent |
| 10-26 12:31 | P44 scored on `simbox3` and written up as E53 (run 93; outcome under P44; open question 13 (d); status; events snapshot `...20261026b.events`); its archive moved to the array and the local copy deleted. simbox3 idle since 12:11, so P46 (the uniform draw against the adversary, the candidate set's survivor test) and P47 (the trim against it, the amplifier test) are filed and queued there — the two cells E53's mechanism reading makes the decisive pair | the plan review's item 2 completes with them; an idle box is a wasted read | remove lines from `q.txt`; stop the driver by pid | agent |
| 10-26 14:05 | P45 scored on `zenith2alpha` and written up as E54 (run 94; outcome under P45; status), its archive moved to the array after verification and the local copy deleted; tr idle until the P46/P47 reads decide the next filings (the trim-sweep extension vs second seeds) | the standing wrap-up plan | re-copy from the array | agent |
| 10-26 17:22 | P46 scored on `simbox3` and written up as E55 (run 95; outcome under P46; open question 13 (e) — the candidate set is exhausted; status), its archive moved to the array after verification and the local copy deleted; tr stays idle pending P47, the last cell of the OQ13 arc — the next filings (the X1 line, N4, or replicates) follow its read | the standing wrap-up plan; no cell is filed before the arc's last number is in | re-copy from the array | agent |
| 10-26 22:09 | P47 scored on `simbox3` and written up as E56 (run 96; outcome under P47; open question 13 (f) — the arc's summary table; status), its archive moved after verification. `make_lean.py --spy-rotate N` (`_roN`, the `rotate_period` attribute; `agents.spy_refresh` reads it with the 1800 s default) so the rotation is a cell parameter; P48 filed and queued on the idle tr (generated there, md5 below at queue time) | the trim-defense finding makes the rotation the decisive variable; the arc closes with the arms race priced | revert the two code edits; remove P48 from `q.txt` | agent |
| 10-27 00:52 | P48 scored on `zenith2alpha` and written up as E57 (run 97; outcome under P48; open question 13 (g) — the arc's closing recommendation), its archive moved to the array after verification. Both queues empty; the lab rests until the next filings (X1's design, N4, the consolidated write-up — the owner's calls) | the standing wrap-up plan | re-copy from the array | agent |
| 10-27 11:45 | The owner opened the next phase ("proceed with the next experiments in the order you recommended"). P49 filed and queued on `zenith2alpha` (wl70 + 60 s sweeps, rotation default — the sweep/rotation dials decoupled; (generated there, md5 `6df1131f`; queued 11:46, driver pid 470530); P50 filed and queued on the idle `simbox3` (E56's replicate at seed 23456, md5 `320ddcbe`, queued 11:48, driver pid 549426). The N4 fluff-epoch computation starts from the existing archives while they run; the X1 design follows | the recommended order: P49, then N4 from logs, then X1's design; an idle box takes the cheap replicate | remove both lines from `q.txt`; stop the drivers by pid | agent |
| 10-27 12:25 | N4 computed from the existing archives (E58; `adhoc/n4_fluff_epoch.py`, four archives on the array, jsons alongside) — the fluff epoch is no independent leak: an oracle mode detector adds zero txs beyond first-hop stem exposure, the first-fluff cue is uninformative at relay density (0.21-0.23 vs the 0.20 prior), and under the trim the fluff channel collapses with the stems (56 % sender-first untrimmed -> 8.9 % trimmed, 40/40 users -> 1/40); no monerod change needed. OQ12's N4 precondition met. P49/P50 still running (tr/simbox3) | the recommended order, item 2, read while both cells run | none — read-only over archives | agent |
| 10-27 12:20 | X1a designed (P51; OQ12 (b)): E27's cell with the sender population rebuilt to mainnet — 40 users at ~2 tx/day, 60 occasional reachable at ~4/day, 6 busy at 1/h, ~530 txs per 24 h (~0.7x mainnet's rate), 40 h stop, fx seed. `make_lean` gains `--window/--user-interval/--reachable-senders/--busy-senders` (`_mw/_ui/_rs/_bs`); generation validated on the control box (450 agents, activity spread 16-28 h the harness's standard auto staggering); the estimators class the new senders with no analysis change. The cell queues on tr behind P49 (generated there, md5 `7219f866`, appended to `q.txt` 12:25 — the driver re-reads it before each cell) | the recommended order item 3 — OQ12's n = 0 row is the reachable class, and E58 already dropped the fluff metrics from the read | revert the generator edits; remove the cell from `q.txt` | agent |
| 10-27 14:20 | P49 scored on `zenith2alpha` and written up as E59 (run 98; outcome under P49; open question 13 (h) — the budget axis closed): 0.0239, the trim holds at the lab's deliverable sweep floor (~1,076 s effective front age at a configured 60 s — the agent thrashes below its 300 s setting); the front-port stem-swallow nuance understood retroactively for E53-E57 (first_hop caps count stems into agent fronts, which are not relays; reported spy-daemon numbers unaffected). X1a started on tr at 14:20 automatically (watcher re-armed); P50 still running on simbox3; P49's archive moving to the array after verification | the standing order | re-copy from the array | agent |
| 10-27 16:29 | P50 scored on `simbox3` and written up as E60 (run 99; outcome under P50): the defense headline replicates — 0.0261 against 0.0248, one user of forty exposed, four clauses of four. The box's queue is empty and its driver exited; the archive moves to the tr array after verification. X1a still running on tr (started 14:20, ETA ~19:20) | the standing order | re-copy from the array | agent |
| 10-27 19:12 | X1a scored on `zenith2alpha` and written up as E61 (run 100; outcome under P51; open question 12 (c) closed): five clauses of five — the program's first perfect pre-registration. The reachable classes priced at mainnet rate: occasional 0.265 precision (one guess in four; 78% exposed in 24 h), busy 0.843 (86% exposed); reachability doubles per-tx first-hop exposure while relayed stems dilute attribution 4x for occasional senders. Both queues now empty, all boxes idle; the recommended order is complete (P49/P50/N4/X1a). Archive moving to the array after verification | the standing order | re-copy from the array | agent |
| 10-28 03:07 | X3 build: `patches/monero-sim-stemmable-inbound.patch` (the fourteenth, +313 lines, applies clean on the 13-patch v0.18.5.1 tree) implements tevador's MRL #160 variant for measurement — `--sim-stemmable-inbound` (adoption; the 0.5 MH/s HashWX PoW gate modeled, not implemented) plus `--sim-stemmable-cidrs` (the modeled paid set; empty = every inbound connection). Semantics per his 2026-05-28 comment: stem edge 1 from real outgoing connections only with local transactions pinned to it (`connection_map::sim_two_edge` + the `get_stem` nil-source pin — stock already stems local txs in fluff epochs, `relay_method::local` bypasses the fluff branch), edge 2 from the /16-deduplicated union with the virtual outgoing list (random /24 per /16, random stemmable connection per /24, capped at 12); an `x3` txrelay event logs the virtual list per epoch; flag off = stock byte-for-byte. `make_lean --stemmable` (`_x3`) flags the relay fabric (relays/mediums/observers); generation validated on the control box; commit `079640f8`. Rebuild on tr next, then the smoke cell, then P52 (X3a) | the owner 10-28: "lets run this experiment" (the tevador simulation); the plan's top-rated untested proposal | revert the patch and the setup.sh/make_lean edits; rebuild | user, agent |
| 10-28 04:50 | The 14-patch binary built on tr after two one-line fixes (the `cryptonote::` qualification in net_node.inl; the eaten backslashes in the x3 log line — both traps now in the patch history). The smoke (run 101, exit 0, 44 m) verified the mechanism: 2,140 x3 events, edge 2 at 38% virtual, edge 1 outgoing, and users receiving relayed stems for the first time (107 vs 0 stock) — the cover channel exists; the local-pin path is unexercised in this shape (adopters do not originate transactions), and its edge-1-nil fallthrough to slot 2 is a known corner, harmless in warm steady state. simbox3 rebuilding. P52 (X3a) filed and queued on tr | the owner 10-28: "lets run this experiment" | revert commit and rebuild; remove the cell from `q.txt` | user, agent |
| 10-28 06:57 | X3a scored (E62, run 102; outcome under P52): the cover is 15x too thin — precision 0.9828 against 1.000 stock, 71 relayed stems reaching all users together; the mechanism itself is faithful (30,961 x3 events) and the edge-1 guarantee is structural, but the precision-cover rationale does not survive the design's own throttles at any rate (mainnet-rate scaling gives ~0.85-0.9). Both archives (smoke run 101, X3a run 102) move to the array; boxes idle. Available next: the X3-mainnet-rate confirm cell (low value — the arithmetic is clear), the X3c v2-stack interaction (edge 1 vs the outbound adversary, predicted leak), or back to the standing menu (monthly dump read ~11-27, IP-churn modeling) | the standing wrap-up discipline | re-copy from the array | agent |
| 10-28 07:45 | The owner corrected the E62 read (tevador's post asks for simulations across parameters, not one point) — accepted: E62 is the lab-rate ceiling at shipped defaults, closed by volume arithmetic; the rate point is live, not arguable (two estimate routes straddle 0.67-0.87 precision). P53 (X1a + stemmable, mainnet rate) queued on `simbox3`; P54 (X3c, the v2 adversary through stemmable — the guarantee's blind side) queued on `zenith2alpha`; both boxes idle with the 14-patch binary. The X3b adversary-strategy poles (one-IP-many-CPU via `--sim-stemmable-cidrs`, many-IP-few-CPU) need a spy-side design pass and follow these reads | the owner 10-28: "yes. and what about the .33?" | remove both from `q.txt` | user, agent |
| 10-28 11:20 | The owner commissioned a second-pass review of the five days (E17-E62, patches 6-14; `adhoc/20261028_five_day_review.md`) and then ordered its fixes: nine findings R1-R9, none overturning a conclusion. Applied: E61's ceiling and exposure corrections and E62's ratio correction as dated lines; the register table rebuilt (runs 98-102 were missing; `run_register.py table`, 102 rows); the findings summary's counters and its two Finding-6 numbers fixed in place; the cover census, the cue-fluffer counts and `read_dumps.py` committed as scripts with their outputs re-derived from the array copies (dated lines under E62/E58); the fourteenth patch's CIDR-parser crash fixed (a no-op digit check let a malformed length reach `std::stoi`; apply-checked on the 13-state tree) — both boxes rebuild when their queues empty, inert until an X3b cell passes a cidrs file; P54's cell-name provenance line added. P54/P53 ran undisturbed throughout | the owner 10-28: "proceed to fix these issues and continue with the experimentation" | revert the doc commits; the patch fix is one hunk | user, agent |
| 10-28 13:10 | P54 scored on `zenith2alpha` and written up as E63 (run 103; outcome under P54): five of five — the stemmable feature is irrelevant to the front-port eclipse (light 0.9051 against E53's 0.9083; sp 0.445, combined 0.951 at precision 1.000; 40/40 users) and the cover collapses under the attack (17 relayed stems, one user; union median 8 against X3a's 22) — the guarantee's blind side is where the documented mainnet adversary lives. The estimator ran manually (the driver scores calibration only; the run-90 repair pattern). Archive moving to the array; tr's queue is empty, so the branch pushes and the R7-fixed binary rebuilds before the X3b cells (they pass a cidrs file). X3b predictions file after E64 (P53, `simbox3`, ETA ~20:30) | the standing order | re-copy from the array; revert the rebuild | agent |
| 10-28 18:15 | X3b's design corrected before filing: the baseline census (`adhoc/spy_stem_receipts.py` on runs 46, 63, 102) shows the lab's spy fleet has never held a connection an X3 virtual slot can carry — 100 % of spy stem receipts are relay-dialed (`dir=in`) and 0 of X3a's 672 receipts from adopters came through a virtual slot — so the committed `--spy-hidden` cells as generated would have held no connection to any relay at all (an exclusive-node spy dials only its seed). `make_lean` gains `--spy-dial N` (`_sdN`; `--spy-hidden` now requires it); the five X3b cells regenerated through `make_cell.sh`, the harness expansion checked (hidden spies: hide-my-port, out-peers 12, the seed list, no exclusive node; relays carry the cidrs path; the dense cell lands 40 spies in 8 /16s); P55-P59 filed and queued on `zenith2alpha` (idle, R7 binary) as P56, P57, P58, P55, P59 while P53 runs on `simbox3`. Filed before E64 because the two axes are independent | the handoff's X3b step and the owner's 10-28 design approval; the correction is measured, not argued | ~12 h of tr; remove lines from `q.txt` to undo | agent |
| 10-28 18:40 | The owner's pointer to observer.monerodevs.org read and brought in: OQ8 addendum (the seeds' fleet share of white vs outbound, out/white 0.69-0.86 — no 2.2x on capped mainnet lists, Finding 2's standing check), `adhoc/observer_seed_ratio.py` + its 10-28 output committed, `analysis/mainnet/pull_observer.sh` installed as a daily 06:00 UTC cron on the control box (aggregate feeds only, into `~/monerosim_local/observer/`, feed host discovered at run time) | the owner 10-28: "add the OQ8 addendum and set up the daily feed pull" | ~8 MB/day local; `crontab -e` to remove | user, agent |
| 10-28 19:15 | The owner's hashrate-gating idea (membership or peer weight priced in hashrate) priced on paper against the observatory's counts and the 10-27 difficulty: `docs/20261028_hashrate_gating_arithmetic.md` (script `adhoc/hashrate_admission_arithmetic.py` + its output). Headline: admission cannot keep a EUR 250 k/month fleet out at any price home nodes can pay (w_max 16 kH/s renting, 76-124 owned, against 80-95 % honest drop-out at 10 kH/s), vouchers zero the price, the chain-share ceiling makes fleet weight irrelevant (1 % of the network needs 28 kH/s per spy); weighted selection prices the share (15 % of slots = EUR 4-9 M/month renting) but routes first hops through the pools. Published to GitHub at the owner's ask as a one-file orphan branch (`hashrate-gating`), derived numbers only | the owner 10-28: "put some numbers on ... include both analyses in a single document and post to github" | an orphan branch on origin; delete the branch to unpublish | user, agent |
| 10-28 20:05 | P53 scored on `simbox3` and written up as E64 (run 104; outcome under P53): four of six — sp precision on unreachable users 1.000 against the 0.45-0.92 band, 13 relayed stems at 11 of 40 users in 24 h against 55 own sends, none forwarded to a spy; the cover is closed at every rate (E62 + E64), the proposal's residual value the edge-1 guarantee and the /16 dedup. Estimator + x3_census + spy_stem_receipts run manually; registered with `run_register.py add` on the box (the `~` in the comma-joined --estimators arg does not expand — use $HOME). simbox3 rebuilt with the R7 binary (md5 e9ed436b, exit 0); P59 (dense) moved from tr's queue to simbox3 and started 20:00 so the two boxes split the five X3b cells; P53's archive copying to the array (verify + rm local when the marker lands) | the standing order; the handoff's E64 playbook | re-copy from the array; `q.txt` edits are reversible | agent |
| 10-28 21:30 | P56 scored on `zenith2alpha` as E65 (run 105; outcome under P56): four of four — the hidden dialing fleet receives zero stems and holds zero outbound slots (light 0.000), the floor for P57/P58. Found and fixed the queue driver's relative-path trap (6eb5abae: `x0_queue.sh` cd's into $REPO, so a relative queue file vanished after the first cell and tr reported QUEUE EMPTY with three cells pending at 20:51); tr's driver relaunched 20:54 on P57 with the two remaining cells placed at the path the running copy reads; `spy_stem_receipts.py` gains the per-spy connection-direction census (b6140156) | the standing order | the boxes' driver copies get the fix when idle; re-copy from the array | agent |
| 10-28 23:45 | P57 scored on `zenith2alpha` as E66 (run 106; outcome under P57): five of five — under universal X3 adoption the hidden dialing fleet receives 78 stems, all through virtual slots, none at hop 1, light 0.000, the users' cover intact (68 relayed stems, X3a 67); the driver consumed P58 from the clone's `q.txt` at 23:30 as the 21:30 row intended (P55 remains there) | the standing order | archive to the array; P58 running until ~02:05 | agent |
| 10-29 00:55 | P59 scored on `simbox3` as E67 (run 107; outcome under P59): one of five — the dense fleet (8 /24s, 5 spies each) runs at 1.73x its own ceiling (not 2.2x), hop-1 14 and sp_r recall 0.014 just under their bands, the wall 281 m on the shared VM; receipts per /24 match X3a's (23.4 against 21.1), so the fleet earns per /24, not per spy; the users' cover unchanged (67). simbox3's driver copy patched with the readlink fix and its clone pushed to `44db4a68` while idle; P59's archive moved to the array via tr (2,626 files, itemize zero; local removed 01:40) | the standing order; the filing's reading rule for (a) | the budget pole (`--spy-dial 64`, dense against spread, hidden) is filed after P58 reads | agent |
| 10-29 02:15 | P58 scored on `zenith2alpha` as E68 (run 108; outcome under P58): five of five — the fleet paying alone draws 238 stems (3.05x E66's 78), all virtual, none at hop 1, light 0.000, and the users receive no relayed stem at all; E65-E68 now bracket the hidden fleet's take under stock (0), universal X3 (7 % of stem txs) and pay-alone X3 (19 %), none of it attributable at this fleet size. P55 (the pay cell with a visible dialing fleet) started 02:07 on tr, the last X3b cell | the standing order | the budget pole (`--spy-dial 64`, dense against spread, hidden) is filed after P55 reads; P58's archive moved to the array (2,636 files, itemize zero; local removed) | agent |
| 10-29 10:23 | P55 scored on `zenith2alpha` as E69 (run 109; outcome under P55): three of five — the payment pole's answer: 301 virtual hop-2+ receipts and 462 residual relay-dialed (763 total, below X3a's 885 sitting still), first hop unchanged (133 user txs, recall 0.129, precision 1.000, 31/40 users exposed), 0 relayed stems at users, light 0.0923 with the relays' outbound spy share collapsed to 0.081 (the direction swap; the white-list refresh feared above 0.38 does not happen). E65-E69 close X3b: nothing buys hop 1; the take scales per /24; the users' cover exists only when honest connections are stemmable. tr idle and clean (clone q.txt removed, driver copy patched, /fast empty) and pushed to the E69 commit with simbox3 | the standing order | the budget pole (P60+: `--spy-dial 64`, dense against spread, hidden, universal) files next | agent |
| 10-29 10:26 | The X3b budget pole filed as P60 (spread, 42 /16s, hidden, `--spy-dial 64`, universal; md5 ae24a2aa) and P61 (dense, 8 /16s, same fan-in ~9 spy inbounds per relay, hidden, sd64; md5 be2f27ed) — the axis x3b_design reserved (`--spy-dial 64`, dense against spread, hidden) after P56-P58 read; P55/P59 closed the pay and dense-relay-dialed poles first (E69/E67), leaving the bucketing question only a dialing fleet can answer. P60 queued on `zenith2alpha` (idle, clean at 069c75ba), P61 on `simbox3` (idle at 069c75ba); both drivers launched with absolute queue paths | P59's reading rule and the 10-29 02:15 row | both cells non-`_sc` (no staged file, no absolute path) so the placement is free; score as runs 110/111 | agent |
| 10-29 13:45 | P60 scored on `zenith2alpha` as E70 (run 110; outcome under P60): four of five — the spread hidden fleet at dial 64 draws 273 stems (3.50x E66's 78 for 5.33x budget; sub-linear: the bound is the /16 count, not the connection count), all virtual, none at hop 1, light 0.000, 91 % of relays carry a spy in a stem set at some epoch with zero attribution, the users' cover thinned to 52 relayed stems; union median 24 unchanged at 5x fan-in (spy /16s displaced honest). The first E70 filing script died on its outcome anchor (the phrase ends 'it).' and the regex demanded 'it.'; the journal was untouched and 6ce06b90 carried only the run folder and the register row). P61 (dense, same fan-in) still running on simbox3; the driver-path fix (620b23ac) is on tr only until simbox3 goes idle | the standing order | score P61 as E71 / run 111 on its DONE | agent |
| 10-29 16:17 | P61 scored on `simbox3` as E71 (run 111; outcome under P61): four of five — the dense leg draws 212 receipts = 78 % of E70's spread leg at the same fan-in, inside the equivalence window, so the /16 count is spent and **the budget pole closes X3b** (with E67 and E70: one slot per prefix on every axis — spies per /24, connections per spy, /16s fielded — every unit beyond the first per prefix discounted, nothing at hop 1, nothing attributable); simbox3 pushed to `07b7b7a8` and its driver copy refreshed while idle before scoring; P61's archive moved to the array via tr (2,626 files, itemize zero; local removed 16:45) | the standing order | both boxes idle; findings summary gains the X3b close as its next edit | agent |
| 10-31 02:25 | The per-host series filed as P62-P67 and queued on the R8 binary (both boxes rebuilt: tr 44ed0b11, simbox3 b96f1006; flag verified in --help): B1 k9-m1 baseline (simbox3), M1 k9-m7 stock smoke (tr, first), M2/M3 the gray-cap treatment at N=1/N=2, I1/I2 the k42 decomposition. The engineering closed the same day the spec was corrected (appendix A: stock white is already one-per-host; the defense is gray-side against the 7-ports-per-IP freshness pump; crawl: 12,368 endpoints on 1,941 IPs in 9 /24s across 9 /16s) | the approved spec + plan (docs/superpowers specs+plans, per-host-peerlist-accounting) | score as E72+ per the standing recipe; the M1 smoke assertions gate the rest | agent |
| 10-31 05:01 | M1's smoke assertions caught a premise error before the series wasted itself: m-daemons get distinct IPs (362 endpoints/362 IPs in M1's dump), not shared-IP ports — the gray-pump arms cannot fire. Queues rewritten: tr keeps I1 (the many-addresses-per-/24 read, still novel), drops M3; simbox3 drops I2; M2 completes as a null-validation of the R8 flag. Port-front modeling (same-IP daemons, distinct ports) becomes a generator work item; the S-cells are unaffected (shared id across addresses IS the fleet shape) | the smoke gate did its job | re-file the cap series after the generator supports same-IP daemons | agent |
| 11-07 14:19 | Switchover to main complete (branch archived+deleted; boxes on fresh main clones; binaries rebuilt 15-patch; post-move checks green incl. byte-identical cell regeneration) and the study resumes: E72-E75 score the four stopped cells — the /24 cap sets the passive position on every axis (B1/M1 dose-response, I1 vs k42-m1 flat), the R8 flag is provably inert (M2 null), and the R9 id-consistency patch is re-enabled after regeneration (the committed diff had omitted its untracked new files — found by the re-org agent's series header; the complete 323-line patch is in, 16-patch daemon validation build running on tr) | the owner's proceed | next: R9' binaries on both boxes, P68-P70 filings, S1-S3 queue | agent |
| 11-07 14:23 | P68-P70 filed (the id-consistency trio on the 16-patch series): S1 the shared-id control (a430ffc4), S2 the enforcement headline (b0de8514, predicted light collapse 0.3467 -> 0.004-0.05), S3 the per-endpoint-id bound (62ce428b, predicted == I1). R9' builds running on both boxes (the 16-patch daemon stack compiled clean on tr first: 'Built target daemon'); S-cells queue on tr the moment --help verifies both flags | the owner's proceed | score as E76+ per the standing recipe | agent |
| 11-08 06:15 | S2 (b0de8514) killed at sim-hour 1.4 (~8 h wall) and root-caused: every daemon in the cell carried `--sim-shared-spy-id` — `make_lean --shared-spy-id` wrote the flag into `daemon_defaults` (its own help said "every daemon gets"; my 10-31 error, patterning a spy-modeling flag after the correctly-global `--id-enforce`) — so all 600 daemons shared peer id `0x5350593031303031` and monerod's public-zone self-connection check (`arg.node_data.peer_id == zone.m_config.m_peer_id`, logged only at DEBUG) dropped **every** handshake before `rsp` was filled; clients logged "wrong network `(00000000-…)`" on the never-filled response (server-side WRONG NETWORK count 0 everywhere — ids were never wrong), zero handshakes completed (REMOTE PEERLIST 0), eternal retry storm, 20x crawl. The R9 daemon patch is innocent — its fixed-id line does exactly what it says, the bug was who received the flag. `make_lean` fixed: `_sid` now scopes to the 294 spy hosts only. Cells: S1 a430ffc4 → e1bc05fc, S2 b0de8514 → 07d0d9a3, S3 byte-identical 62ce428b (the anchor proving the edit inert on non-sid cells). P68-P70 stand as filed — the science is unchanged, the cells now actually implement "all 294 spy endpoints present one fixed backing id". New standing rule (also in the study CLAUDE.md): a flag-carrying rebuild requires a small flagged smoke cell with daemon-log review before any real cell queues; first smoke `lean_24_none_h42_k9_p1_m7_n600_idc24_sid_s12345` (dc644293) in flight on tr | S1 (a430ffc4) was equally affected and never ran; S3 was unaffected and is runnable as-is | revert make_lean and regenerate; nothing was scored from the killed run | agent |
| 11-08 06:39 | Flagged smoke PASSED and the trio re-queued: `lean_24_none_h42_k9_p1_m7_n600_idc24_sid_s12345` (dc644293, h42 cell — honest fabric is medium-a/b/c there, not relay-r-*) ran clean in 49 min, exit 0, light 0.1614, stem_txs 1008 (I1 read 1,004), wrong-network peak 6/host over the whole run (baseline band ~15/run from chronic dead-peer re-dials — the same zero-id signature at 1/400th of S2's rate; boot transients are 1/host and baseline-normal), shared-id banner on spies only (spy yes, seed/medium no). Then S2 (07d0d9a3) START 06:39, S1 (e1bc05fc) and S3 (62ce428b) behind it on tr | the mandatory smoke rule's first execution; the fix is runtime-verified, not just generator-verified | kill the driver by pid and remove q.txt lines | agent |
## 8. Files

- Per-run record: `docs/spy_journal/runs/<run_id>/`
- Queue drivers: `docs/spy_journal/drivers/`; queue event logs: `docs/spy_journal/logs/`
- Exploratory scripts as run: `docs/spy_journal/adhoc/`
- Cell generators: `test_configs/x0/make_cells.sh` (the 12 X0 cells),
  `test_configs/x0/make_lean.py` (lean and X1 cells); `scripts/spy_ban_list.py`
- Scorers: `analysis/spy/x0_calibration.py`, `analysis/spy/spy_estimators.py`;
  register: `analysis/spy/run_register.py`
