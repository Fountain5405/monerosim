# SoP study: guide for a fresh agent

The study measures whether Share-or-Perish (SoP), Monero Research Lab issue
#146 (<https://github.com/monero-project/research-lab/issues/146>, tevador),
raises the hashrate a selfish miner needs to profit, and what SoP costs honest
miners. It follows the study's earlier work on selfish mining and on
Publish-or-Perish (MRL #144).

Read `STATUS.md` first: it is the only place that states the current findings.
Until the switch-over to main is finished, `HANDOFF.md` and `SWITCHOVER.md`
describe the move and what is left to do. Paths below are relative to the
repository root; run everything from there.

## Tools

Four tools, each checked against the others:
- Shadow simulations of patched monerod (`monerod-sim`, built from
  `patches/series`; this study's patch is `studies/sop/patches/monero-sim-pop.patch`);
- a race model of the SoP rule (`studies/sop/scripts/sop_race_model.py`);
- an exact MDP for bounds (`studies/sop/scripts/sop_mdp.py`);
- an attacker search over a strategy family written for SoP
  (`studies/sop/scripts/sop_attacker_search.py`), plus a stopped tabular RL
  learner (`studies/sop/scripts/sop_rl.py`).

The attacker itself (`agents/selfish_miner.py`, `agents/selfish_strategy.py`)
and the matrix runner (`scripts/selfish_matrix.py`) are core: core's Rust code
and golden tests load them. Changing them means running core's tests too.

## Commands

All compute runs on a lane box (box80-82, phantom, lithium), never on the
control box.
- **One matrix cell:** `venv/bin/python scripts/selfish_matrix.py studies/sop/configs/matrix/<spec>.yaml --cells <cell>`.
- **MDP:** `venv/bin/python -m studies.sop.scripts.sop_mdp solve --alpha 0.45 --a-max 4 --h-max 4 [--bound upper]`.
  `enumerate` counts the states first; 4/4 caps are 85 M states, 12.4 GB and 18 h.
- **Cross-check:** `venv/bin/python -m studies.sop.scripts.sop_mdp_crosscheck sop|btc ...`
  (needs scipy and pymdptoolbox, which the repo venv lacks).
- **Tests:** `venv/bin/python -m pytest -q studies/sop agents/test_selfish_miner.py agents/test_selfish_strategy.py scripts/test_selfish_matrix.py`,
  on a lane box: `remote_test.sh <box> -q <test files>` rsyncs to `~/monerosim_rl`
  and runs that box's venv (its rsync list predates `studies/`: see
  `studies/sop/SWITCHOVER.md`). The solver cross-check tests need scipy and
  pymdptoolbox: lithium `~/mdpcheck/venv`.
- **Daemon:** `./setup.sh --sim-binary`, never beside running lanes.
- **Lane drivers, pool scoring and queues:** `launch_lane.sh`,
  `rerun_cell.sh <box> <spec> <cell>` (using `run_lane.py` and `check_run.py`),
  `chain_queue.sh <box>` (runs `queues/<box>.txt` in order), `score_pool.sh <spec>`
  and the per-miner analyses in `analysis/`. They live in the control box's
  `.claude/campaign9/`; `studies/sop/dot-claude/campaign9/` is a snapshot with
  pre-move paths that hard-codes `/home/selfishmining/monerosim`. New drivers
  go in `studies/sop/drivers/`, in git.

## Conventions

- **Times** in UTC, with the owner's US Eastern time beside them.
- **Commits** say why and give the measured numbers. Author and committer are
  the owner's identity; no `Co-Authored-By:` or other attribution lines (the
  owner, 2026-11-01). Never rebase, squash or force-push: result docs cite
  commit hashes.
- **Pushes and tags** each need the owner's go-ahead. Pushes go through tr's
  checkout (see `CLAUDE.local.md` on the control box).
- **Keep the fleet busy:** launch the next logical cell on any free box and
  report it, unless the owner has paused new work.
- **Result docs** start with a status line (current, superseded by X, or
  retracted). Correct claims in place with a dated note; never delete them.
- **Cells** are named by their axis values in axis order. Overlay targets are
  attacker, honest, relays, bridges, all, or an agent name.
- **Defaults:** the race model's perish option stays off by default.
- **Spec questions:** read the MRL issue body and comments yourself, and
  reproduce consequences before relaying them to the owner.

## Owner's standing rules

- The control box runs only the Claude instances: no sims, MDP/RL/search
  runs, test suites or Monte Carlo. Parsing logs from the pool is fine.
- phantom and lithium run the owner's Monero stressnet nodes (user `monero`):
  keep at least 8 GiB free; one 72 h lane each, phantom never more than 2; a
  memory guard stops our lane under 8 GiB. Read the nodes' logs only, with
  `sudo -n`, never their monitoring sidecar's config, which holds a hub token.
- 16 GB lane boxes run one lane each (each mining daemon holds the full
  RandomX dataset, about 2.3 GB).
- tr belongs to the antiproxy study; SoP uses it only as the pool host and
  push relay.
- Never modify the owner's or the `monero` user's files, nor move or delete
  the archive directories on phantom and lithium. Kill by pid, never
  `pkill -f` a broad pattern: it matches your own ssh command line.

## Pitfalls

- Shadow runs are not bit-reproducible; the attacker-side seed spread is about
  0.05 of share, so one seed cannot resolve a 0.03 effect.
- The capped MDP is a LOWER bound: at a cap the forced action is legal in the
  full game. Never say the MDP "could not beat the family" (MRL review,
  10-28). Upper bounds come from `--bound upper`.
- monerod P2P timeouts are 5 s. `hit_score` penalises peers whose height
  drops, which leads to 24 h bans in mixed SoP/stock networks;
  `--sim-no-drop-score` turns it off.
- Mining templates are built on the verified tip. Block-relay order (only
  main-chain blocks are relayed) drives the slow-miner cost.
- Rebuilding beside running lanes: a full `setup.sh` fails at step 7 with
  "Text file busy". `simbin_build.sh` rebuilds only `monerod-sim` and installs
  by rename, but carries its own patch list (see `studies/sop/SWITCHOVER.md`).
- Watchers only notify; queue runners keep boxes busy. `pgrep -f` with a
  pattern also matches the shell running it: use `setsid` and record pids.
- Hashrate 0 is rejected; use 0.01. Judge chain snapshots by next-block
  difficulty at the tip (an old h10 snapshot made cells about 10 % fast).
- pymdptoolbox 4.0b3 builds dense n x n arrays in its input check. HiGHS calls
  a fixed-policy LP infeasible unless one redundant flow row is dropped.
  `sop_mdp_crosscheck.py` handles both.
- Lane-box `~/monerosim` trees have been rsync copies whose git HEAD did not
  describe the code; each run's `binary_provenance.txt` records the commit.
- The repo is public: no real LAN IPs, internal hostnames, or anything about
  the stressnet monitoring hub. Machine-specific notes (hosts, accounts, push
  routes) live in `CLAUDE.local.md` on the control box, never in git.
