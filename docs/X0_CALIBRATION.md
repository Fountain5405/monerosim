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
| Medium | 48 | out-peers 16, 22 and 28; pinned reachable; turning over |
| Users | 80 | wallets, 1 tx per 300 s; turning over |
| Relays | 260 | turning over |
| Observers | 8 | always-on reachable light nodes with peer-list dumps |
| Seeds | 6 | on `monerod-sim`, logging relays |
| Spies | 48 | 6 /24s × 8 on NA nodes 828-833; each /24 announces through a different seed |

**Ratios kept.** These follow the plan's I5 rule, which asks each preset to
say what it keeps:
- the replica's class shares, and 1 h / 1 h turnover;
- honest reachable at 17% (71 of 407);
- spies at 40% of reachable IPs, in 6 dense spy-only /24s, each in its own
  /16;
- honest prefix sharing of 0.31 × 3 (326 honest /24s).

**Not kept: mainnet's ~3,700 honest /24s against 6 spy /24s.** Here about 60
reachable honest /24s face the spies' 6. Stock /24 dedup therefore leaves the
spies more than on mainnet, so read the dedup cell's "~70% lower" target with
care.

Every daemon runs `monerod-sim` with `sim-log-txrelay`, at `monitor` logging,
so the run yields connection tokens and relay logs for X0, I3 and X1.

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
