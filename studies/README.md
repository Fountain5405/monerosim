# Studies

Research that uses the simulator lives here, one folder per study. An active
study has a `CLAUDE.md` (how to work on it) and a `STATUS.md`, the only place
that states its current findings. Until its agent finishes the switch-over to
main, it also has `HANDOFF.md` and `SWITCHOVER.md`. A closed study has only a
`STATUS.md`, saying where its results are.

| Study | Folder | State | Account that runs it | Subject |
|---|---|---|---|---|
| Share-or-Perish (SoP) | `sop/` | active; paused for the reorganization | `selfishmining` | MRL #146, a selfish-mining countermeasure |
| Antiproxy | `antiproxy/` | active; stopped 2026-11-01 until switch-over | `antiproxy`, and the owner's `lever65` on one lab box | spy and proxy nodes in Monero's P2P layer, and defences |
| Eclipse | `eclipse/` | closed | none (was the owner's `lever65`) | eclipse-attack replication (2026-09) and its `--bootfast` reproduction (2026-10) |

A study's folder may hold `agents/`, `scripts/`, `patches/`, `configs/`,
`analysis/`, `data/`, `docs/`, `drivers/` and tests, as it needs. Python code
under a study is importable from the repository root, for example
`python3 -m studies.sop.scripts.sop_mdp`.

## What stays in core

A file belongs to the study that changes it. Code that core or several studies
use stays in core, and so does a file the rule does not settle (core uses it
and a study changes it). These core files are the ones the studies lean on
most:

- `agents/`: every agent, including the ones a study changes. Core's Rust code
  and golden tests load the selfish-mining agents (`selfish_miner.py`,
  `selfish_strategy.py`, `selfish_bridge.py`), a core test names
  `agents.eclipse_fakepeer`, and the x0 generator emits `agents.spy_refresh`.
- `scripts/sop_policy.py`: written and changed by SoP, but core's
  `agents/selfish_strategy.py` imports it for the `learned` and
  `param_stubborn` strategies.
- `scripts/selfish_matrix.py`, `scripts/sop_health_check.py`,
  `scripts/selfish_mining_analysis.py` and `scripts/honest_chain_from_log.py`:
  the matrix runner and its checks; `test_configs/matrix/pipeline_smoke.yaml`
  is the runner's own end-to-end smoke.
- `analysis/eclipse/` (used by a core test and the peer-list-dump docs),
  `analysis/topology_metrics.py`, and `analysis/mainnet/` (the mainnet
  observation tools; the antiproxy study's monitor tools are in
  `antiproxy/analysis/mainnet/`).
- The core patches in `patches/`, and every patch's place in `patches/series`.

## Where core still uses study files

The move left these core tests reading study files (before it, both sides
were in core). Each is a follow-up for its study: move the test into the
study, or the file back to core.

- `scripts/test_selfish_matrix.py` and `scripts/test_selfish_configs.py` read
  SoP's matrix specs and base configs in `sop/configs/`.
- `scripts/test_monero_sim_patch.py` pins `sop/patches/monero-sim-pop.patch`.

## Moved files

`MOVES.tsv` lists every file the 2026-11 reorganization moved: old path, new
path, owner and reason, one row per file. Dated docs, journals and run records
keep the paths they were written with; translate them with this table.
