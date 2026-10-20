# Spy-side origin estimators (`analysis/spy/spy_estimators.py`)

Scores what a spy fleet can infer about transaction origins against ground
truth, by sender reachability. It is infrastructure item I3 of the spy-node
test plan (`docs/20261018_spy_node_defenses.md` §5.2) and builds on the relay
log (I1, `docs/TXRELAY_LOG.md`).

## What a run needs

- **Spies on `monerod-sim` with `sim-log-txrelay`** (variant R). Their `rx`
  events are the spies' whole view: which peer IP sent which tx, when, and
  with which stem/fluff flag. Spies are the agents whose id starts with `spy`,
  or those matched by `--spies`.
- **Honest nodes logging too**, for p_stem and the first-hop ceiling. Declare
  the fallback seeds on `monerod-sim` as well (`docs/TXRELAY_LOG.md`).
- **Unreachable senders**, via `reachable_fraction` or `reachable_by_role`.
  Reachability is read from `shadow_agents.yaml`: a non-empty
  `blocked_inbound_ports` means unreachable. It stands in for the spy's
  ping-back test.

Example: `test_configs/spy_estimators_smoke.scenario.yaml`.

```
python3 analysis/spy/spy_estimators.py archived_runs/<run> [--spies 'relay-00[1-5]']
    [--busy-min 5] [--window 600] [--bootstrap 1000] [--json out.json]
```

`--spies` can re-score any run that has relay logs, with some honest nodes
posing as spies.

## Estimators

Each gives one guess per tx, or abstains.

| Name | Guess |
|---|---|
| `sp` | Stem predecessor: the honest peer that first stemmed the tx to any spy. Spy-to-spy stems are skipped, since the fleet colludes. |
| `sp_r` | `sp`, kept only when the guessed node is unreachable. Nobody dials an unreachable node, so every stem it sends is its own (§2.3 point 1). |
| `fs` | First spy: the honest peer that delivered the earliest fluff to any spy. |
| `combined` | `sp` if there is one, else `fs`. |

## Report

- **Recall and precision** per estimator and sender class (`unreachable`;
  `reachable`; `busy` = reachable with at least `--busy-min` txs):
  - recall = correct guesses / txs whose true sender is in the class;
  - precision = correct guesses / guesses that name a node in the class, so
    guesses that name a relay count against `reachable`;
  - 95% bootstrap intervals resample senders, not txs, because a sender's txs
    share its stem peers.
- **First-hop ceiling** (ground truth): the share of each class's txs that the
  origin stemmed straight to a spy. `sp` can't recall more than this.
- **Exposure**: P(a sender has at least one correctly attributed tx), by its
  tx count, for `sp_r` and `combined`.
- **p_stem and p_out** over the activity window (bootstrap end to stop time),
  per honest node, by reachability: the median of node means, and the share of
  nodes that ever had a spy peer.
  - p_stem is the spy share of stem peers, per epoch, from the relay log;
  - p_out is the spy share of outbound peers, per `--window` snapshot of
    `bitmonero.log`, via `analysis/topology_metrics.py`.

  p_stem is a slot share, not a per-tx probability. A node's own txs use one
  of its two stem peers for a whole epoch, so per-tx exposure is
  all-or-nothing per epoch, and with few epochs it can sit well away from
  p_stem.

## Smoke run (2026-10-20)

`archived_runs/20261020_021931_spy_estimators_smoke`:
- 48 daemons, all logging: 6 spies, 16 users (25% reachable), 15 relays (50%
  reachable), 5 miners and 6 seeds;
- 1 h of transactions, 363 txs;
- 9 min 45 s wall time.

This is not a calibrated preset (that is I5/X0). It checks the pipeline.

`txrelay_check.py` on the same run: 363 of 363 origins match the recorded
sender, and no stem hop lacks its receipt.

| Estimator | Class | Recall [95% CI] | Precision [95% CI] |
|---|---|---|---|
| `sp_r` | unreachable (233 txs) | 0.163 [0.10, 0.22] | **1.000** [1.00, 1.00] |
| `sp` | busy reachable (130 txs) | 0.177 [0.10, 0.29] | 0.354 [0.15, 0.57] |
| `fs` | busy reachable | 0.062 [0.03, 0.12] | 0.053 [0.02, 0.10] |
| `combined` | busy reachable | 0.208 [0.13, 0.32] | 0.168 [0.08, 0.27] |

- **sp_r is exact on unreachable senders, as §2.3 predicts.** Its recall
  equals the first-hop ceiling (38/233), with no false positives.
- **For reachable senders, the cover works.** `sp` also reaches its ceiling
  (23/130), but 42 of its 65 guesses name a relay that was only forwarding.
- **First-spy is weak.** It's below 0.07 for both measures, because fluffs
  spread from wherever the stem ended.
- **Slot shares:** p_stem 0.21 (unreachable nodes) and 0.17 (reachable);
  p_out 0.22 and 0.24.
- **Exposure.** 10 of 12 unreachable users had at least one tx attributed by
  `sp_r`. All 12 sent 10 or more.
