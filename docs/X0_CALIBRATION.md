# X0: calibrating the spy lab

Infrastructure and preset for experiment X0 of the spy-node test plan
(`docs/20261018_spy_node_defenses.md` §5.3). X0 asks whether the replica
reproduces measured spy exposure before any defense is tested on it. This
covers part of I4 (`--sim-subnet-dedup`) and the 2024 preset of I5. The
relay log (I1, `docs/TXRELAY_LOG.md`) and the estimators (I3,
`docs/SPY_ESTIMATORS.md`) come first.

## `--sim-subnet-dedup` (patches/monero-sim-subnet-dedup.patch)

This selects how monerod groups outbound candidates. It is built into
`monerod-sim` by `./setup.sh --sim-binary` as the eighth patch.

| Value | Selection |
|---|---|
| `24` (default) | Stock v0.18.5.1 (#9939, shipped in v0.18.4.3). Ports are collapsed. One candidate is taken per /24, and /24s already connected (inbound or outbound) are skipped. If that leaves nothing, all candidates are used. |
| `16` | The same, at /16. |
| `none` | The same with no subnet grouping; ports are still collapsed. |
| `legacy` | v0.18.4.2's `make_new_connection_from_peerlist`, verbatim. Ports are collapsed, and candidates in a /16 already connected are skipped, but each IP is its own candidate. |

The 0.18.4.2 → 0.18.4.3 diff of `src/p2p/` changes only this function, plus
seed lists and a log typo, so `legacy` is the full pre-#9939 behaviour.
Non-default values print a red banner at startup.

**Caveat for `legacy`.** monerosim gives each GML node its own `a.b.0.0/24`,
so in the sim a /16 holds one /24. `legacy` therefore differs from `24` only
by weighting candidates per IP instead of per /24, which is the core of what
#9939 changed. On mainnet, /16s are shared, so the old rule also excluded
honest neighbours, which it can't do here.

### Check (test_configs/subnet_dedup_check.scenario.yaml)

The check network had 40 reachable relays, 2 miners and 6 seeds, plus 12
spies in one /24. Each mode ran for 2 h of sim at two seeds, measured over
the second hour in 10-minute windows with `analysis/spy/subnet_dedup_check.py`.

| Mode | Spy share of honest outbound | Honest nodes with >= 1 spy | Spies per node |
|---|---|---|---|
| `none` | 0.36 / 0.36 | 98% / 98% | mostly 4-6 |
| `legacy` | 0.072 / 0.070 | 87% / 88% | 1 (2-3 in about 5% of windows, from churn) |
| `24` | 0.060 / 0.057 | 61% / 57% | 0-1; up to 5 when the deduplicated list runs empty and monerod falls back to all candidates |

**How spies get into peer lists matters more than the grouping rule.** Two
variants failed before the one above:
- **Spies that dial out** (12 outbound peers each) reach nearly every honest
  node inbound. A connected subnet counts whether the connection is inbound
  or outbound, so their /24 lands in every node's connected-subnet set, and
  both `24` and `legacy` then skip it. The two modes came out the same (0.026
  and 0.019).
- **Listen-only spies** (`out-peers: 0`) are in nobody's peer list. A node is
  white-listed only when it connects to someone, who pings it back. Every
  mode then gave 0.

The spies in the check connect to one seed only (`add-exclusive-node`). The
seed white-lists them and passes them on in every handshake, and no other
honest node gets the spy /24 among its connected subnets. This matches 2024,
when the banned IPs almost never dialed in (Rucknium) yet were in peer lists.
The proxies of the time also poisoned peer lists, which variant R does not.

## The 2024 preset (test_configs/x0/x0_2024.scenario.yaml)

The mainnet replica is scaled to about 400 honest daemons so it fits a 32 GB
box: 457 agents, of which 455 are daemons.

| Class | Count | Notes |
|---|---|---|
| Miners (hubs) | 5 | native mining at 10 h/s each (the `h50` chain snapshot); 100 in / 100 out |
| Medium | 48 | out-peers 16, 22 and 28; pinned reachable |
| Users | 80 | wallets, 1 tx per 300 s |
| Relays | 260 | |
| Observers | 8 | always-on reachable light nodes with peer-list dumps |
| Seeds | 6 | on `monerod-sim`, logging relays |
| Spies | 48 | 6 /24s × 8 on NA nodes 828-833; each /24 announces through a different seed |

**Ratios kept.** These follow the plan's I5 rule, which asks each preset to
say what it keeps:
- the replica's class shares;
- honest reachable at 17% (71 of 407);
- spies at 40% of reachable IPs, in 6 dense spy-only /24s, each in its own
  /16;
- honest prefix sharing of 0.31 × 3 (326 honest /24s).

**Not kept: churn.** The replica turns users, relays and medium nodes over
1 h on / 1 h off, which matches mainnet connection durations (S10). Nobody
knows who churns on mainnet: relay operators mostly stay up, and some users
keep a node up while others sync only to transact. The first experiments
therefore run without churn, and churn rates are a later experiment. With
churn on users, their daemons were offline half the time and wallets stalled
in RPC timeouts: the pilot below made 118 user transactions instead of
~1,200.

**Not kept: mainnet's ~3,700 honest /24s against 6 spy /24s.** Here about 60
reachable honest /24s face the spies' 6. Stock /24 dedup therefore leaves the
spies more than on mainnet, so read the dedup cell's "~70% lower" target with
care.

Every daemon runs `monerod-sim` with `sim-log-txrelay`, at `monitor` logging,
so the run yields connection tokens and relay logs for X0, I3 and X1.

Relays start linearly, one every 30 s from 20 min to 2.5 h, the two relay
groups interleaved. The `auto` (batched) stagger doubles its waves up to 108
relays 5 s apart; at ~5x real time that starts ~100 monerods in a minute, their
256 MB RandomX caches outrun KSM, and the first pilot
(`20261020_130027_x0_legacy_none_s12345`) ran out of RAM at sim 1 h 43 m.
Linear, the second pilot's free RAM stayed above 8.8 GB through the relay
boot.

## Cells (test_configs/x0/make_cells.sh)

The cells are peer selection {`legacy`, `24`} × ban list {none, half} × seeds
{12345, 23456, 34567}, 12 runs in all. For each seed, `make_cells.sh` writes
the expanded configs and `banlist_s<seed>.txt` into `test_configs/x0/cells/`.
That directory is ignored by git, because the configs hold this machine's
absolute ban-list path.

**The ban list.** `scripts/spy_ban_list.py` dry-generates the config into a
scratch directory, reads the spies' IPs, and writes their /24s. Placement
doesn't depend on the seed: all three seeds gave the same 6 /24s.
- **Adopters.** Half of each honest class: 24 medium, 40 users, 130 relays
  and 4 observers.
- **Seeds and miners don't adopt**, so seeds keep gossiping spies, as
  non-adopting infrastructure would.

```
test_configs/x0/make_cells.sh
./run_sim.sh --config test_configs/x0/cells/x0_legacy_none_s12345.yaml --bootfast --ksm
python3 analysis/spy/x0_calibration.py archived_runs/<run>
python3 analysis/spy/x0_calibration.py --compare archived_runs/<run> ...
```

**Prerequisite.** The cells need `monerod-sim` built from this branch, which
adds the relay-log and subnet-dedup patches (`./setup.sh --sim-binary`).

## The report (analysis/spy/x0_calibration.py)

- **Slot shares.** The spy share of honest outbound and inbound slots, per
  5-minute window over the activity window. It is split by class, for the
  light nodes (users, relays and observers, which is what the targets were
  measured on), and for ban-list adopters versus non-adopters.
- **Stems.**
  - **Mean length:** the raw mean, and the mean over paths that ended in a
    fluff epoch.
  - **Fluff probability per hop** (`txrelay_check.py`'s `fluff_per_hop`): the
    number of paths ended by a fluff epoch, divided by all relay hops. Loops
    and missing logs cut paths short, more so in small networks. Paths that
    ended in a fluff epoch averaged 3.0 hops in a 48-daemon smoke, but each
    hop is still a trial with p = 0.2. The implied uncensored mean is 1/p:
    4.5 hops on the spy smoke and 5.0 (p = 0.199) on the relay-log smoke,
    against the target of about 5.
  - **Embargo rate:** the share of stems ended by an embargo timer.
- **Verdict:** PASS or FAIL within 1.5× of each target.

## Pilots

| Run | Churn | Spies | Light outbound share | Fluff per hop | Notes |
|---|---|---|---|---|---|
| `20261020_130027_x0_legacy_none_s12345` | 1 h / 1 h | 48 (40% of reachable) | — | — | out of RAM at sim 1 h 43 m (batched relay waves); stopped |
| `20261020_132230_x0_legacy_none_s12345` | 1 h / 1 h | 48 (40% of reachable) | 0.348 (target 0.15: FAIL) | 0.148 (176 txs) | 1 h 36 m wall; min free RAM 8.9 GB; 26 user agents stuck in RPC timeouts at the end, so Shadow exits 1 |
| `20261020_165536_x0_legacy_none_s12345_nochurn` | none | 48 (40% of reachable) | 0.286 (FAIL) | 0.213 (244 txs): implied 4.7 hops, PASS | 1 h 15 m wall; min free RAM 6.5 GB (KSM at 10000 pages until sim ~1 h, then 20000); exit 0 |
| `20261020_181726_x0_legacy_none_s12345_spies12` | none | 12 (15% of reachable) | 0.132 (PASS) | 0.191 (1,828 txs): implied 5.2 hops, PASS | users at 300 s: 1,822 txs created, 1,798 in blocks; 1 h 53 m wall; min free RAM 7.6 GB; 11 GB archive; exit 0 |

Both pilots ran users at one tx per 3,412 s, not 300 s: `make_cells.sh`
expanded without `--no-safe-tx-interval`, so the generator raised the
interval to this box's calibrated "safe" value and users sent ~2 txs each
(fixed; the cells now hold 300 s). The slot shares don't depend on the tx
rate; the stems are from few transactions.

Turning churn off lowered the outbound share from 0.35 to 0.29, still about
twice the target. With churn, the share (0.35) roughly followed the spies'
share of reachable IPs (0.40), as Kopyciok et al.'s 15.26% outbound followed
their 14.74% of IPs. The 40% figure is from Oct 2024 (#126) while the 15% target is
Apr-May 2024 (Rucknium) and Feb 2025 (Kopyciok), so if the share stays high
without churn, the replica's "2025" spy preset (14.7%, 7 /24s) is the matched
pair to try. It does: 0.29 without churn.

With 12 spies (2 per /24, about 15% of reachable IPs) and no churn, the
light-node outbound share is 0.132 against the 0.15 target, so the share
follows the spies' share of IPs here too. This run is also the first at the
300 s tx interval (1,822 txs, against 236 and 176 in the earlier pilots). The
stems fit Dandelion++: 0.191 fluff per hop (stock 0.2), so the implied
uncensored mean is 5.2 hops. 12.5% of stems end in a loop (8.6% in the
48-spy run). The 12-spy layout is the X0 baseline for the remaining cells.

## Scaling the /24 cells (test_configs/x0/make_lean.py)

**The gap.** The X0 cell puts 6 spy /24s against 69 honest reachable /24s.
The model below puts stock dedup at 0.083 against 0.137 for `legacy`: 40%
lower, where the target is ~70%. Mainnet has 6-9 spy /24s against ~3,700
honest ones (0.2%).

**What sets the share.** Two things:
- *The pool a node picks from.* An unreachable node is in nobody's peer list,
  so the 83% of daemons that are unreachable light nodes don't change it. The
  reachable honest IPs and the spies do. `make_lean.py` builds the replica
  with the unreachable majority cut to 40 users and the reachable honest set
  grown to `--reachable`, with the spies (15% of reachable IPs) in
  `--spy-subnets` /24s. Mainnet's /24 ratio then takes ~600 reachable honest
  daemons and one dense spy /24 of ~106 spies (Rucknium saw 240-254 spies in
  each /24), about 750 daemons instead of ~3,700. Relays start one every 20
  sim-s, so the RandomX caches don't outrun KSM (the same rule as X0's linear
  relay starts).
- *The one-per-subnet cap.* After each pick a node skips every candidate in
  the picked subnet (both rules; in the simulator a /16 holds one /24). So k
  spy /24s can hold at most k of a node's 12 outbound slots, however many
  spies they hold. `legacy` weights a subnet by its IPs, so a dense spy /24
  is almost certain to get its one slot; dedup weights every /24 equally.

`x0_calibration.py` prints a model line for every run: a Monte Carlo of that
rule over the run's own pool (12 slots, every spy assumed to be in every peer
list, no list dynamics, no inbound-connection skip). It is a reference, not a
fit, and it has held so far:

| Cell | Model | Measured |
|---|---|---|
| X0 `legacy/none`, 12 spies in 6 /24s | 0.137 | 0.132 (0.1335 in the capped rerun) |
| X0 `legacy/half`, non-adopters | 0.137 | 0.1375 |
| lean H=71, 13 spies in 1 /24, `legacy` | 0.075 | 0.061 |

The first lean cell is why the model has the cap. A uniform pick over IPs
predicted 0.155 for it, and the cell measured 0.061: a node can hold only one
spy slot, so one dense /24 can't reach X0's 0.13 however many spies it has.
That also means the `legacy` leg of a one-/24 cell is not the 0.15 baseline;
the k=6 cells at H=300 are the `legacy` anchor at a larger honest set.

| Cell | Daemons | Spies / spy /24s | Honest reachable / /24s | Model: `legacy` | Model: `24` |
|---|---|---|---|---|---|
| X0 | 419 | 12 / 6 | 71 / 69 | 0.137 | 0.083 |
| lean H=71 | 124 | 13 / 1 | 71 / 60 | 0.075 | 0.018 |
| lean H=150 | 216 | 26 / 1 | 150 / 125 | 0.073 | 0.009 |
| lean H=300 | 393 | 53 / 1 | 300 / 242 | 0.073 | 0.0045 |
| lean H=300, k=6 | 393 | 53 / 6 | 300 / 242 | 0.136 | 0.026 |
| lean H=600 | 746 | 106 / 1 | 600 / 480 | 0.073 | 0.0024 |

**Sweep.** Each row under `legacy` and `24`, no list, seed 12345. A cell that
lands within ~20% of its model row says the rule and the pool explain the
share, and the model can then be run on mainnet's pool. A `24` cell above its
row means something else sets the share (how spies get into lists, or the
inbound skip), and that, not the size of the replica, is what limits reading
the result against mainnet.

**Results so far** (light-node outbound share, window average and by quarter of
the 4 h window; the report prints the quarters):

| Cell | Model | Window average | By quarter |
|---|---|---|---|
| lean H=71 `legacy` | 0.075 | 0.061 | 0.070, 0.063, 0.060, 0.052 |
| lean H=71 `24` | 0.018 | 0.0212 | 0.032, 0.024, 0.017, 0.014 |
| lean H=150 `legacy` | 0.073 | 0.0679 | 0.069, 0.071, 0.068, 0.064 |
| lean H=150 `24` | 0.0086 | 0.0282 | 0.047, 0.030, 0.022, 0.016 |
| lean H=300 `legacy` | 0.073 | 0.0707 | 0.073, 0.073, 0.070, 0.067 |
| lean H=300 `24` | 0.0045 | 0.0459 | 0.081, 0.046, 0.033, 0.024 |

The model holds for `legacy` (7% off at H=150, the cap again). The `24` cells
don't sit still: the share falls through the window, and at H=150 the average
is 3x the model while the last quarter is 1.9x and still falling. Outbound
connections are not permanent here even without churn: an H=150 relay sees 32
distinct honest peers over the window in 12 slots, so a slot turns over about
every 1.5 h. Connections made at start from the small early peer lists hold
more spies than the steady state, and under `24` they take a few hours to age
out. The cause of the early excess is not isolated. It is not the relay's
start time (the share is flat across relays in start order), and not the
observers' lists (the spies sit mid-pack by `last_seen` there, and 175-entry
lists hold all 26 spies and 149 honest in 125 /24s, the model's pool). Real
selection also takes the 20 most recently seen candidates after the /24 dedup
and picks among them with a cubic bias to the freshest (`get_random_index_with_fixed_probability`);
the model ignores that, and a Monte Carlo of it over the observers' lists
gives no higher a share than the uniform one.

At H=300 the `24` cell is 10x the model on average and 5x in the last quarter,
and the first quarter rises with H (0.032, 0.047, 0.081 at H=71, 150, 300; 13,
26, 53 spies). In the first window 95 of 233 relays hold three or more spy
outbound peers at once, up to five, so the one-per-/24 cap the model rests on
is broken early; by the last window 4 hold two and none more. `legacy` breaks
it too, less: 25 relays hold two or three in the first window. The likely path
is the fallback to undeduplicated candidates (`step == 1`) when a new relay's
small first peer list runs out of /24s, since its 12 slots fill within about 3
sim-s of starting. The relay's list is not dumped, so this is not checked.

So read a `24` cell by its last quarter, not its average, and give it a longer
warmup before the transactions start (`make_lean.py --warmup 21600`; the
default is 3600). `lean_24_none_h150_k1_w6h` tests that: if its last quarter
lands near 0.0086, the model is the steady state and the 4 h cells are still
converging.

**Not covered.** Stems and estimators at these sizes (the cells keep 40 users,
so a few hundred txs), churn, and more than one seed per point.

## Targets and open questions

| Cell | Target | Source |
|---|---|---|
| `legacy`, no list | light-node outbound spy share ~0.15 | Rucknium (Apr-May 2024); Kopyciok et al. 15.26% |
| `legacy`, half | ~0.07 | Kopyciok et al. 7.13% with the list |
| `24`, no list | ~70% below `legacy` | #9939's simulation |
| all | stem length geometric, mean ~5; embargo rate | Dandelion++ |

**Is the 7.13% a per-node or a network figure?** It isn't clear whether it
was measured at a node with the list on, or across a network where some
nodes had it. The half cell reports adopters and non-adopters separately, so
it can be read either way.

**If the targets miss, the knob is how spies get into peer lists.** The
options are:
- the seed-only announcement used here;
- a dial budget, in which spies dial in and accept the self-exclusion that
  comes with it;
- variant P with peer-list poisoning, once its transaction feed exists.

**Cost.** This box ran 500 nodes at 3.5× real time, so expect about 2.5-3 h
of wall time per 8 h cell, roughly 30-36 h for all 12 cells, and about 4 GB
of logs per run.
