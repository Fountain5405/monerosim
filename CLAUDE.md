# Monerosim

Monerosim runs Monero networks inside Shadow, a discrete-event network
simulator. A Rust generator (`src/`) turns a YAML config into a Shadow config
that runs real `monerod` and `monero-wallet-rpc` processes plus Python agents
(`agents/`); `run_sim.sh` builds, runs, monitors and archives a run. Research
that uses the simulator lives in `studies/`. The repository is public.

## Where to start an agent

- **Core work** (engine, runner, agents, patches, general configs, reference
  docs): start at the repository root.
- **Study work**: start in `studies/<study>/` and read its `CLAUDE.md` and
  `STATUS.md` first. `studies/README.md` lists the studies, which are active,
  and which account runs each.

## Layout

- `src/`, `tests/`: the Rust generator and orchestrator, and their tests.
- `agents/`: the agent library (miners, users, monitors, DNS, and the
  selfish-mining, eclipse and spy agents). Agents run as
  `python3 -m agents.<name>` from the repository root.
- `scripts/`: runner helpers, analysis tools and their tests.
- `run_sim.sh`, `setup.sh`, `update.sh`, `start_here.sh`: run, install, update.
- `patches/series`: the one list of `monerod-sim` patches, in apply order, with
  each patch's owner and flags. Core patches are in `patches/`; a study's
  patches are in `studies/<study>/patches/`.
- `test_configs/`: general-purpose configs (quickstart, refactor_gate, hf_*,
  native_*, cuprate_*, scale_ladder*, ...). Study configs are in
  `studies/<study>/configs/`.
- `analysis/`, `gml_processing/`, `chain_snapshots/`: shared analysis tools,
  network topologies and chain snapshots.
- `docs/`: reference docs (current) and dated design records. Index:
  `docs/README.md`.
- `studies/`: one folder per study. `studies/MOVES.tsv` maps every path the
  2026-11 reorganization moved, old to new.

## Working rules

- **No long-lived branches.** Commit to main, or to a short branch merged
  within a day. Never rewrite pushed commits (no rebase, squash, amend or
  force-push): result docs cite commit hashes.
- **Never edit or pull in a checkout a campaign is running from.** Agents that
  start late import code at their own start time. Run campaigns from a pinned
  worktree: `git worktree add ../runs/<campaign> <sha>`.
- **Daemon patches change only through `patches/series`**, then rebuild with
  `./setup.sh --sim-binary`. A patch's bytes are its identity: every binary's
  provenance records its sha256. `run_sim.sh` refuses a `monerod-sim` whose
  recorded patches differ from the series
  (override: `MONEROSIM_SKIP_PROVENANCE_CHECK=1`).
- **Current findings live only in each study's `STATUS.md`.** Dated docs
  (`YYYYMMDD_*.md`) are history and use pre-reorganization paths; translate
  them with `studies/MOVES.tsv`.
- **The repo is public.** No credentials, keys, real LAN IPs, internal
  hostnames or `user@host` strings. Machine-specific notes go in
  `CLAUDE.local.md` (gitignored), never in a tracked `CLAUDE.md`.
- **Core does not depend on studies.** A file core uses stays in core; a
  study may use core freely. The few existing exceptions are listed in
  `studies/README.md`.

## Checks

- `cargo test --release` (unit, integration and golden tests; the golden tests
  need `venv/`).
- `venv/bin/python -m pytest -q` (testpaths: agents, scripts, tests, studies).
- `./scripts/smoke_test.sh` (quickstart) for behaviour changes;
  `./scripts/smoke_test.sh refactor_gate` for refactors.
