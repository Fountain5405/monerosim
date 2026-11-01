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
- **Tests:** `venv/bin/python -m pytest -q studies/sop agents/test_selfish_miner.py agents/test_selfish_strategy.py scripts/test_selfish_matrix.py`.
- **Daemon:** `./setup.sh --sim-binary`, never beside running lanes.
- **Lane drivers, pool scoring and queues:** `studies/sop/dot-claude/campaign9/`
  is a snapshot of the control box's `.claude/campaign9/` with pre-move paths.
  New drivers go in `studies/sop/drivers/`, in git.

## Conventions

- **Times** in UTC, with the owner's US Eastern time beside them.
- **Commits** end with a `Co-Authored-By:` line naming the model. Messages say
  why and give the measured numbers. Never rebase, squash or force-push.
- **Pushes and tags** each need the owner's go-ahead.
- **Keep the fleet busy:** launch the next logical cell on any free box and
  report it, unless the owner has paused new work.
- **Result docs** start with a status line (current, superseded by X, or
  retracted). Correct claims in place with a dated note; never delete them.
- **Cells** are named by their axis values in axis order. Overlay targets are
  attacker, honest, relays, bridges, all, or an agent name.
- **Spec questions:** read the MRL issue body and comments yourself, and
  reproduce consequences before relaying them to the owner.

## Owner's standing rules

- The control box runs only the Claude instances: no sims, MDP/RL/search
  runs, test suites or Monte Carlo. Parsing logs from the pool is fine.
- phantom and lithium run the owner's Monero stressnet nodes (user `monero`):
  keep at least 8 GiB free; one 72 h lane each, phantom never more than 2; a
  memory guard stops our lane under 8 GiB. Read the nodes' logs only, with
  `sudo -n`, never their monitoring sidecar's config.
- 16 GB lane boxes run one lane each (each mining daemon holds the full
  RandomX dataset, about 2.3 GB).
- tr belongs to the antiproxy study; SoP uses it only as the pool host and
  push relay.
- Never modify the owner's or the `monero` user's files, nor move or delete
  the archive directories on phantom and lithium. Kill by pid, never
  `pkill -f` a broad pattern.

## Pitfalls

- Shadow runs are not bit-reproducible; the attacker-side seed spread is about
  0.05 of share, so one seed cannot resolve a 0.03 effect.
- The capped MDP is a LOWER bound; upper bounds come from `--bound upper`.
- monerod's `hit_score` penalises peers whose height drops, which leads to
  24 h bans in mixed SoP/stock networks; `--sim-no-drop-score` turns it off.
- Hashrate 0 is rejected; use 0.01. Judge chain snapshots by next-block
  difficulty at the tip.
- Lane-box `~/monerosim` trees have been rsync copies whose git HEAD did not
  describe the code; each run's `binary_provenance.txt` records the commit.
- Machine-specific notes (hosts, accounts, push routes) live in
  `CLAUDE.local.md` on the control box, never in git.
