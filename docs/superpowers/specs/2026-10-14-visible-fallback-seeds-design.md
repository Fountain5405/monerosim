# Visible fallback seeds: design

Status: approved in conversation 2026-10-14; spec awaiting review.

## Problem

With `general.fallback_seeds: auto` (the default), the Rust orchestrator
injects six daemon-only hosts `monero-seed-001` … `monero-seed-006` at
Shadow-config generation time (`src/agent/fallback_seeds.rs:81-135`). They
run stock `monerod`, start at 0–5 s, and take `daemon_defaults` like any
other daemon.

Users can already choose a seed's binary or options: a host declared under
an exact slot name replaces the injected one (`fallback_seeds.rs:92-108`),
and a scenario can set all six with one range group,
`monero-seed-{001..006}:`. But:

- seeds that are not declared appear in no file the user edits. The scenario
  expander (`scripts/scenario_parser.py`) never mentions seeds, so the
  expanded monerosim YAML lists every host except them. The first file that
  shows them is the generated `shadow_agents.yaml`;
- the stock default is silent. In a network where every other daemon runs a
  modified binary, stock seeds can reject that network's blocks (SoP's
  `version_minor` rule is a hard fork, campaign-7 results §7 item 2), and
  nothing says so.

## Goal

- The expanded monerosim YAML lists every host the run will have, seeds
  included, so they can be read and edited like any other node.
- The scenario file is the place to set seed details, using the existing
  range-group syntax. No new syntax.
- Config generation warns when the seeds run stock `monerod` and the rest of
  the network does not.
- For every existing scenario, the generated Shadow config is unchanged.

## Design

### 1. Expander writes the seeds

New final phase in `expand_scenario` (`scripts/scenario_parser.py:431`),
`_add_fallback_seeds(general, agents)`, called after
`_resolve_auto_agent_values`, immediately before the config dict is built.

- Runs only when the resolved `general.fallback_seeds` is `auto` or absent.
  `custom` and `off` add nothing. PyYAML reads an unquoted `off` as boolean
  `false`; treat `false` as `off`.
- For each slot `i` in 1..=6, named `monero-seed-{i:03}`: if the expanded
  `agents` already has that key (from a group or a singleton), leave it
  exactly as written. Otherwise append
  `{daemon: monerod, start_time: "<i-1>s"}`, the values
  `build_seed_agent` uses (`fallback_seeds.rs:183-220`). The expander does
  not write `attributes`; the orchestrator stamps `is_seed_node` on every
  pinned seed, declared or injected (`mark_as_seed_node`).
- New slots are appended after all other agents.
- Running last keeps every calibration input unchanged. `_count_total_nodes`
  feeds start staggers and the safe transaction interval; adding the seeds
  before it would change those values for every existing scenario.
- The slot count is a module constant `FALLBACK_SEED_SLOTS = 6`, with a
  comment pointing to `MONERO_FALLBACK_SEED_IPS` (`src/lib.rs:209`). The
  Monero source in `sibling_repos/monero` lists the same six mainnet IPs.

### 2. Rust: injector unchanged, new warning

- `prepare_fallback_seeds` keeps injecting undeclared slots. It still serves
  monerosim YAMLs written by hand or by `generate_config.py --agents`. On an
  expanded scenario it finds every slot declared and injects nothing.
- New warning, emitted once from `prepare_fallback_seeds` after the
  effective agents are built (`auto` and `custom` modes), when all of:
  1. at least one seed slot has `daemon: Local("monerod")`;
  2. at least one non-seed agent runs a local daemon;
  3. no non-seed agent has `daemon: Local("monerod")`.

  The message names the stock seeds and the binary (or binaries) the other
  daemons use, and shows the fix:

  ```yaml
  monero-seed-{001..006}:
    daemon: <binary>
    start_time_stagger: 1s
  ```

- Only the `daemon` field is compared. `daemon_phases` binaries are ignored,
  so upgrade configs that start every node on `monerod` do not warn. Agents
  with no daemon or a `Remote` daemon are not counted as non-seed daemons.
- The check is a pure function over `AgentDefinitions` returning the message
  (or `None`), so it can be unit-tested; `prepare_fallback_seeds` logs it
  with `log::warn!`.

### 3. Docs

- `docs/SCENARIO_FORMAT.md` (fallback-seeds section):
  - replace "Seed hosts are not in the expanded config" with: in `auto`
    mode, scenario expansion writes any seed you did not declare into the
    expanded YAML, running stock `monerod`;
  - make the range group the recommended way to set seeds, with
    `start_time_stagger: 1s` (a daemon-only group otherwise defaults to a
    5 s stagger);
  - correct the preflight sentence: generation probes the seed binary only
    for the hard-fork schedule and native-mining flags, not for every flag
    in `daemon_defaults`; mention the new stock-seed warning.
- `docs/FLOW.md:196-208`: the matching sentence.

## Testing

- Python, `scripts/test_scenario_parser.py`:
  - `auto` and absent each add six seeds, `daemon: monerod`,
    `start_time` 0s…5s, after all other agents;
  - a scenario declaring `monero-seed-{001..003}` gets only 004–006 added,
    and its own three untouched;
  - `custom`, `"off"` and boolean `false` add none;
  - every non-seed agent and the `general` section are identical with and
    without the new phase (calibration unchanged).
- Rust:
  - parity: a fixture with the six seeds declared exactly as the expander
    writes them generates byte-identical `shadow_agents.yaml` to the same
    fixture without them (auto injection). This guards the two copies of
    the seed defaults against drift;
  - warning unit tests: fires for all-`monerod-sim` non-seeds with stock
    seeds; silent when any non-seed runs `monerod`, when seeds are
    declared non-stock, when there are no non-seed daemons, and for
    `Remote`-only agents.
- Existing Rust golden tests are unchanged: their fixtures are monerosim
  YAMLs and do not go through scenario expansion.
- Manual end-to-end check: expand `test_configs/mainnet_replica.scenario.yaml`
  and one SoP scenario with the old and new expander, generate both, and
  diff `shadow_agents.yaml`; expect no difference.

## Out of scope

- `generate_config.py --agents` (no scenario; its `--fallback-seeds custom`
  scaffold is unchanged).
- Regenerating checked-in expanded YAMLs under `test_configs/`. They gain
  the seeds on their next regeneration.
- Changing the default seed binary.
