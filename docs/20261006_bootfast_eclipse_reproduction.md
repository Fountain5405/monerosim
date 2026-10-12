# Full-scale reproduction of the 2232-host eclipse run with `--bootfast`

2026-10-06. A rerun of the colleague's 50-hour eclipse simulation, identical except for
the start-up fixes from `docs/20261003_startup_cost.md`, on the same box. Two questions:
how much faster is it, and does the eclipse result reproduce?

## TL;DR

- **Wall time 22.5 h → 15.6 h (1.44x faster, 6.9 h saved).** The whole saving is the
  monerod start-up phase: **7.71 h → 0.63 h**. Burn-in, attacker start-up and the attack
  phase took the same wall time in both runs (within 1.5%).
- **The eclipse reproduces; whether it holds does not.** The target was fully eclipsed
  (12/12 outbound connections to attackers) at sim 21.5 h, against 20.6 h in the
  original. The original stayed fully eclipsed to the end (13/13). In this run the
  target won back about half its connections from ~31 h on and ended at 9/12. The
  original config's other runs vary as much, so this is most likely run-to-run
  variance, not an effect of the start-up fixes; repeat runs would settle it.
- **The monerod both runs used has no whitelist countermeasure,** despite the config name
  `..._10000_whitelist_fix_..._247a1474f_build`. Its source commit 120ddc20c reverts all
  three countermeasure commits. Both are therefore no-countermeasure runs.

## What was run

| | Original | Reproduction |
|---|---|---|
| Run | colleague's `20261004_003742_eclipse_nyx_fakepeer_onboardfirst_10000_whitelist_fix_14_hrs_burn_in_50_hrs_run_247a1474f_build` | `20261006_002913_bootfast_eclipse2232_full50h` |
| Started | 2026-10-04 00:37 UTC | 2026-10-06 00:29 UTC |
| Config | `configs/eclipse/eclipse_nyx_fakepeer_onboardfirst_10000_whitelist_fix_14_hrs_burn_in_50_hrs_run_247a1474f_build.yaml` | byte-identical copy; only the monerod path changed (to a copy of the same binary) |
| Hosts | 2232: 4 miners, 1,199 benign relays, target `relay-4000`, 1,000 fake peers, 20 injectors, eclipse monitor, 6 seeds, DNS | same |
| monerod (1,204 nodes incl. target) | `/home/user/Rucknium/git/monero/build/.../monerod`, `v0.18.5.1-120ddc20c`, sha256 `956b1588…` | byte-identical copy |
| monerod (6 auto-generated seeds) | that account's default, sha256 `74faa25a…` | this account's default, sha256 `8137f392…` (both `v0.18.5.1-release`) |
| Shadow | shadowformonero v0.2.4 | v0.2.5 (one commit on top: the busy-loop clock rule) |
| monerosim | `d8421243` | `81ef1a6e` (agents/ unchanged; generator adds RPC SSL off and the clock knobs) |
| Clock / RPC SSL | Shadow default / monerod default (RSA-4096 cert per start) | `--bootfast` / disabled (now monerosim's default) |
| Workers | 128 (one per physical core, `run_sim.sh` planner) | same, run under `nice -n 10` on an otherwise idle box |

The 1,020 attacker agents start between sim 14.0 h and 17.45 h (the "14 h burn-in").

## Wall time

Wall-clock hours to each phase boundary, from each run's `memory_samples.csv`:

| Phase (sim time) | Original | Reproduction |
|---|---|---|
| monerod start-up (0 → 1.5 h) | 7.71 | **0.63** |
| burn-in (1.5 → 15.7 h) | 2.32 | 2.33 |
| attacker start-up (15.7 → 17.5 h) | 0.50 | 0.49 |
| attack (17.5 → 50 h) | 12.00 | 12.17 |
| **Total Shadow wall** | **22.53** (log: 22:32:00) | **15.62** (log: 15:38:00) |

- Start-up: 1,214 monero processes (1,210 monerod, 4 wallet-rpc) start one after another.
  Averaged over the phase, each start went from ~23 wall-s to ~1.9 wall-s: 12x faster.
- The rest is unchanged, as expected: `--bootfast` only charges clock reads past the
  10,000th in a row, which normal code never reached in the measured runs
  (`docs/20261003_startup_cost.md`).
  The Python fake peers do not run monero's start-up busy-wait, so attacker start-up is
  the same.
- Peak memory 374 GB vs 376 GB; run dir 382 GB vs 383 GB (244 GB `bitmonero.log` at
  `log-level: 1` with no rotation, 140 GB of monerod console copies in
  `shadow.data/hosts/`). Shadow reported 0 failed processes in both runs.
- For a full 50 h run the saving is 31% of wall time. Configs with a shorter attack phase
  gain proportionally more, since the 7 h start-up saving is fixed.

## Eclipse outcome

Target `relay-4000` (unreachable: 0 inbound connections throughout), attacker share of its
outbound connections, from `eclipse_metrics.jsonl`:

| Sim h | Original | Reproduction |
|---|---|---|
| 15 | 0/12 | 0/12 |
| 17 | 2/12 | 2/12 |
| 19 | 7/12 | 6/12 |
| 21 | 12/12 | 11/12 |
| 23–29 | 12/12 | 12/12 |
| 31 | 12/12 | 11/12 |
| 33 | 12/12 | 9/12 |
| 35 | 12/12 | 6/12 |
| 37 | 12/12 | 5/12 |
| 39–47 | 12/12 | 7–9/12 |
| 50 (final) | 13/13 | 9/12 |

| | Original | Reproduction |
|---|---|---|
| Time to full eclipse (monitor's `tte_sim_t`) | 20.55 h (6.6 h after the first attackers start) | 21.50 h (7.5 h after) |
| Polls fully eclipsed after that | 100% | 31% |
| Target white / gray peer list, max | 1,000 / 5,000 | 1,000 / 5,000 |

**Reproduced:** a full eclipse of an unreachable node, reached at the same point in the
attack. **Not reproduced:** the eclipse persisting. Here the attackers' share of the
target's outbound connections fell back to 5–9 of 12 from ~33 h on.

### Is the difference the start-up fixes?

Probably not, but one pair of runs cannot show it:

- Runs are not reproducible outside the Determinism recipe (`docs/CONFIGURATION.md`):
  Shadow's thread scheduling varies between runs. Same-config eclipse runs at 240 hosts
  ended with 4, 6 and 9 attacker connections.
- What changed is confined to start-up: monerod and wallet-rpc starts are cheaper in wall
  time, and the busy-wait still ends at the same simulated time; RPC SSL affects only the
  agents' RPC (plain HTTP either way), not P2P.
- The 6 seed nodes ran different monerod builds of the same version (above). Seeds matter
  mostly for bootstrapping; whether that could shift a target's recovery 30 h later is
  untested.

To separate variance from effect: 2–3 more runs of each arm. At ~15.6 h per `--bootfast`
run that is cheaper than one original run per arm. Two can run at once on this box
(375 GB each of 1 TB), at the cost of half the cores each.

## The binary does not have the whitelist countermeasure

The colleague's monero repo (`/home/user/Rucknium/git/monero`, branch `release-v0.18`):

| Date (UTC) | Commit | Change |
|---|---|---|
| 09-18 | e3b952190 | Raise `P2P_LOCAL_WHITE_PEERLIST_LIMIT` to 10000 |
| 09-19 | 881497150 | Apply `monero-sim-peerlist-dump.patch` |
| 09-22 | ac14c4796 | Try connections from the white list first |
| 09-25 | db2713955 | Consider the full white list when choosing a connection |
| **10-03 01:19–01:21** | e908a9c17, d88f75b52, **120ddc20c** | **Revert all three countermeasure commits** |

The binary at the configured path was built 10-03 01:22 and reports `v0.18.5.1-120ddc20c`:
stock monero P2P behaviour plus the peer-list dump patch. The target's white list never
exceeds stock monero's 1,000 in either run. The config name (`10000_whitelist_fix`,
`247a1474f_build`) predates that rebuild, so it no longer describes the binary. Earlier runs
of the config that did have the countermeasure behave differently:

| Run | monerod | Max white list | Target at the end |
|---|---|---|---|
| `20260925_170012` (25 h) | db2713955 | 1,342 | 2/12 |
| `20260927_233518` (25 h) | unknown ("247a1474f") | 1,000 | 10/12 |
| `20261002_013124` (50 h) | db2713955 | 1,871 | 6/12, never fully eclipsed |
| `20261004_003742` (50 h) | 120ddc20c (reverted) | 1,000 | 13/13 |
| reproduction (50 h) | 120ddc20c (reverted) | 1,000 | 9/12, fully eclipsed 21.5–31 h |

Both countermeasure runs were never fully eclipsed; both no-countermeasure 50 h runs were,
at ~21 h. That fits the countermeasure working, with the same caveat on run count.
When comparing eclipse runs, check `monerod --version` and the target's maximum white-list
size rather than the config name.

## Files

- Run: `archived_runs/20261006_002913_bootfast_eclipse2232_full50h/` (lever65's checkout).
- Config and binary copies, launch log, disk watchdog: `~/bootfast_scale_test/` (lever65).
  The run was launched with `setsid nohup ./run_sim.sh ... --bootfast`, with a watchdog
  that would pause Shadow (`kill -STOP`) below 25 GB free disk; it never fired (465 GB
  free at the end).
- Comparison: `python3 analysis/startup_cost/compare_eclipse_runs.py RUN_DIR [RUN_DIR...]`.
- Start-up phase alone, same config cut to 90 min, attackers removed:
  `20261005_034740_bootfast_eclipse2232_start90m` (sim 1.5 h in ~36 wall-min).
