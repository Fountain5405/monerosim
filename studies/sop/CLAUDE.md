# SoP study: guide for a fresh agent

## Purpose

The study measures whether Share-or-Perish (SoP), Monero Research Lab issue
#146 (<https://github.com/monero-project/research-lab/issues/146>, tevador),
raises the hashrate a selfish miner needs to profit, and what SoP costs honest
miners. It follows the study's earlier work on selfish mining and on
Publish-or-Perish (MRL #144).

It uses four tools, each checked against the others:
- Shadow simulations of real, patched monerod (`monerod-sim`);
- a Python race model of the SoP rule (`scripts/sop_race_model.py`);
- an exact MDP for bounds (`scripts/sop_mdp.py`);
- an attacker search over a strategy family written for SoP
  (`scripts/sop_attacker_search.py`), plus a tabular RL learner that was
  stopped (`scripts/sop_rl.py`).

Current findings are in `docs/20261026_sop_attacker_search.md`, items 1-11.
Status and file ownership are in `HANDOFF.md`, next to this file.

## What the results say so far (2026-11-01)

- **Threshold.** SoP raises the profitability threshold from 0.369 to 0.4635
  of hashrate (two honest miners, K=3, w=16, against the strongest attacker
  found). Under SoP the classic Eyal-Sirer miner never earns more than its
  hashrate.
- **Network advantage.** When the honest path is slower than d, SoP still
  beats the stock rule by 0.15-0.2 below alpha 0.45, and only ties it at
  0.45.
- **Slow honest miners lose about twice what they lose under stock.** The
  cause is a lateness cascade along relay chains: monerod relays a block only
  once it is on the relayer's main chain. Raising d to 10 or 20 s does not
  fix it.
- **Partial adoption.** Every partial-adoption step is worse than either end
  for someone. The 24 h peer bans only decide whether the network partitions.
  With the bans removed, the attacker took 0.991 of the single chain. SoP
  needs a flag day. These are 14-node networks; the owner wants the ladder
  rerun at scale.
- **MDP bounds.** At alpha 0.45 the optimal attack lies in [0.45, 0.7265]
  (4/4 caps). The solver matches pymdptoolbox, the HiGHS LP and the published
  SSZ Bitcoin table.

## Commands

All compute runs on a lane box (box80-82, phantom, lithium), never on the
control box. The helpers live in `dot-claude/campaign9/`, a copy of the
control box's `.claude/campaign9/`. They hard-code `/home/selfishmining/monerosim`
and the pre-move repo paths, so check them before use.

- **Matrix spec, one cell:**
  `venv/bin/python scripts/selfish_matrix.py test_configs/matrix/<spec>.yaml --cells <cell>`
  (on a lane box, from `~/monerosim`).
- **Lane driver with gate, pool sync and queue:** `launch_lane.sh` /
  `rerun_cell.sh <box> <spec> <cell>`, which use `run_lane.py` and
  `check_run.py`. `chain_queue.sh <box>` runs `queues/<box>.txt` in order.
- **Score a spec from the pool:** `score_pool.sh <spec>`. Per-miner and
  per-side analyses are in `dot-claude/campaign9/analysis/`: `slow_loss*.py`,
  `slow_forks.py`, `sop_dec_lag.py`, `split_shares_arg.py`.
- **Tests on a lane box:** `remote_test.sh <box> -q <test files>`. It rsyncs to
  `~/monerosim_rl` and runs the box's venv. The solver cross-check tests need
  scipy and pymdptoolbox: lithium `~/mdpcheck/venv`.
- **MDP:**
  - `scripts/sop_mdp.py solve --alpha 0.45 --a-max 4 --h-max 4 [--bound upper]`;
  - `enumerate` counts the states first. 4/4 caps are 85 M states, 12.4 GB
    and 18 h.
- **Cross-check:** `scripts/sop_mdp_crosscheck.py sop|btc ...`.
- **Daemon:**
  - `setup.sh --sim-binary` does a full build;
  - `simbin_build.sh` rebuilds only `monerod-sim` beside running lanes;
  - the patches, in apply order: fakechain-hardforks, sim-mining,
    selfish-relay, peerlist-dump, pop, tail-emission, on monero `v0.18.5.1`
    (`monero.pin`).

## Conventions

- **Times.** Quote them in UTC with the owner's US Eastern time beside them.
- **Commits** end with a `Co-Authored-By:` line naming the model. Messages say
  why and give the measured numbers. Never rebase, squash or force-push:
  result docs cite commit hashes.
- **Owner's go-ahead.** Pushes and tags each need it. Pushes go through tr's
  checkout (see `CLAUDE.local.md` on the control box).
- **Keep the fleet busy:** launch the next logical cell on any free box and
  report it. The exception is when the owner has paused new work, as during
  the 2026-11 repo reorganisation.
- **Result docs.** A dated doc starts with a status line: current,
  superseded by X, or retracted (see X). Correct claims in place, with a
  dated note; do not delete them.
- **Cells.** Spec cells are named by their axis values joined in axis order.
  Overlay targets are attacker, honest, relays, bridges, all, or an agent
  name.
- **Defaults.** The race model's perish option stays off by default.
- **Spec questions.** Read the MRL issue body and comments yourself, and
  reproduce the consequences before relaying them to the owner.

## Rules from the owner (standing)

- **Control box.** It runs only the Claude instances: no sims, MDP/RL/search
  runs, test suites or Monte Carlo there. Parsing logs from the pool is fine.
- **phantom and lithium.** They run the owner's Monero stressnet nodes (user
  `monero`):
  - keep at least 8 GiB free;
  - one 72 h lane each, and phantom never more than 2 (its node was
    OOM-killed under 4);
  - a memory guard stops our lane under 8 GiB.
- **16 GB lane boxes:** one lane each. Each mining daemon holds the full
  RandomX dataset, about 2.3 GB.
- **tr.** It belongs to the antiproxy study. We use it only as the pool host
  and the push relay.
- **Never** modify the owner's or the `monero` user's files. Never move or
  delete the archive directories on phantom and lithium.
- **Stressnet nodes.** Read their logs only, with `sudo -n`, and never their
  monitoring sidecar's config, which holds a hub token.
- **Killing processes.** Kill by pid. Never `pkill -f` a broad pattern: it
  matches your own ssh command line.

## Pitfalls that have bitten

- **Shadow runs are not bit-reproducible.** The same config diverged 10 ms at
  the first block. The attacker-side seed spread is about 0.05 of share, so
  one seed cannot resolve a 0.03 effect.
- **The capped MDP is a LOWER bound.** At a cap the forced action is legal in
  the full game. Never say the MDP "could not beat the family" (MRL review,
  10-28). Upper bounds come from `--bound upper`.
- **monerod P2P.** Timeouts are 5 s. `hit_score` penalises peers whose height
  drops, which leads to 24 h bans in mixed SoP/stock networks.
  `--sim-no-drop-score` turns that off.
- **Mining templates** are built on the verified tip. Block-relay order (only
  main-chain blocks are relayed) drives the slow-miner cost.
- **Rebuilding beside running lanes.** A full `setup.sh` step 7 fails with
  "Text file busy". Use `simbin_build.sh`, which installs by rename.
- **Monitoring.** Watchers only notify; queue runners keep boxes busy.
  `pgrep -f` with a pattern also matches the shell running it. Use `setsid`
  and record pids.
- **Hashrate 0** is rejected; use 0.01.
- **Chain snapshots.** Judge them by next-block difficulty at the tip (an
  old h10 snapshot made cells about 10 % fast).
- **Lane-box checkouts.** Their `~/monerosim` trees are rsync copies
  (`sync_tree.sh`, no `--delete`), so their git HEAD does not describe the
  code. Each run's `binary_provenance.txt` and the queue logs record the
  control-box commit.
- **pymdptoolbox 4.0b3** builds dense n x n arrays in its input check.
  **HiGHS** calls a fixed-policy LP infeasible unless one redundant flow row
  is dropped. `sop_mdp_crosscheck.py` handles both.
- **Repo is public.** Do not commit real LAN IPs, internal hostnames, or
  anything about the stressnet monitoring hub.
