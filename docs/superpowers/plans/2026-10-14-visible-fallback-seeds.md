# Visible Fallback Seeds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In `fallback_seeds: auto` mode the scenario expander writes every undeclared `monero-seed-001..006` into the expanded monerosim YAML, and config generation warns when seeds run stock `monerod` while no other daemon does.

**Architecture:** A last phase in `scripts/scenario_parser.py::expand_scenario` appends the missing seed slots with the exact values the Rust injector uses (`monerod`, `start_time` 0s..5s), so the generated Shadow config is unchanged. The Rust injector (`src/agent/fallback_seeds.rs`) stays as-is for hand-written YAMLs and gains a pure `stock_seed_warning` check logged from `prepare_fallback_seeds`.

**Tech Stack:** Python 3 (pytest, venv at `venv/`), Rust (cargo test).

**Spec:** `docs/superpowers/specs/2026-10-14-visible-fallback-seeds-design.md`

## Global Constraints

- Six slots, named `monero-seed-{i:03}` for i in 1..=6; slot i gets `start_time: "{i-1}s"` and `daemon: monerod`.
- The expander writes no `attributes` for seeds.
- Only `auto` or absent `general.fallback_seeds` adds seeds; `custom`, `"off"` and boolean `false` add none.
- The seed phase runs after `_resolve_auto_agent_values`; no other agent or `general` value may change.
- Generated `shadow_agents.yaml` for existing scenarios must be byte-identical before and after.
- Warning compares only the `daemon` field; `daemon_phases`, no-daemon and `Remote` agents don't count as non-seed daemons.
- No `.sh` edits. Commit locally only; no push.

## Review Focus

1. A scenario that declares seeds with a group (`monero-seed-{001..006}`) must keep its own values; the expander must not overwrite or duplicate them. (Task 1 test `test_seeds_declared_group_untouched`.)
2. Unquoted `fallback_seeds: off` parses as `False` in PyYAML; it must add no seeds. (Task 1 test `test_seeds_not_added_when_off_or_custom`.)
3. A singleton `monero-seed-002:` with a non-stock binary must be kept and the other five filled. (Task 1 test `test_seeds_partial_declaration_fills_missing`.)
4. A network of only script agents plus seeds (no non-seed daemon) must not warn. (Task 2 test `warning_silent_without_non_seed_daemons`.)
5. An upgrade config where everyone starts on `monerod` and moves to another binary via `daemon_phases` must not warn. (Task 2 test `warning_silent_when_a_non_seed_runs_monerod`, which covers the `daemon: monerod` starting binary.)

---

### Task 0: Baseline Shadow configs (before any code change)

**Files:** none in the repo; outputs go to the session scratchpad `$S`.

- [ ] **Step 1: Expand and generate with the current code**

```bash
S=<scratchpad>/seedparity; mkdir -p $S
for n in mainnet_replica_smoke mainnet_replica; do
  venv/bin/python scripts/generate_config.py --from test_configs/$n.scenario.yaml -o $S/$n.before.expanded.yaml
  ./target/release/monerosim --config $S/$n.before.expanded.yaml --output $S/$n.before.out
done
```

Expected: both succeed; `$S/<n>.before.out/shadow_agents.yaml` exists. Record its line count.

### Task 1: Expander writes the seeds

**Files:**
- Modify: `scripts/scenario_parser.py` (new constant + `_add_fallback_seeds`, call in `expand_scenario` before `config['general'] = general`)
- Test: `scripts/test_scenario_parser.py`

**Interfaces:**
- Produces: `FALLBACK_SEED_SLOTS = 6`; `_add_fallback_seeds(general: Dict[str, Any], agents: "OrderedDict[str, Dict[str, Any]]") -> None` (mutates `agents`).

- [ ] **Step 1: Write the failing tests** (append to `scripts/test_scenario_parser.py`)

```python
# ---------------------------------------------------------------------------
# Fallback seeds written into the expanded config (auto mode)
# ---------------------------------------------------------------------------

SEED_IDS = [f"monero-seed-{i:03d}" for i in range(1, 7)]


def _expand_text(text, seed=12345):
    import tempfile, os
    with tempfile.NamedTemporaryFile('w', suffix='.yaml', delete=False) as f:
        f.write(text)
        path = f.name
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return expand_scenario(parse_scenario(path), seed=seed)
    finally:
        os.unlink(path)


def _with_general_line(line):
    return SMALL_SCENARIO.replace("general:\n", f"general:\n  {line}\n", 1)


@pytest.mark.parametrize("line", ["", "fallback_seeds: auto"])
def test_seeds_added_in_auto_mode(line):
    cfg = _expand_text(_with_general_line(line) if line else SMALL_SCENARIO)
    ids = list(cfg['agents'])
    assert ids[-6:] == SEED_IDS
    for i, sid in enumerate(SEED_IDS):
        assert cfg['agents'][sid] == {'daemon': 'monerod', 'start_time': f'{i}s'}


@pytest.mark.parametrize("line", ["fallback_seeds: custom", 'fallback_seeds: "off"', "fallback_seeds: off"])
def test_seeds_not_added_when_off_or_custom(line):
    cfg = _expand_text(_with_general_line(line))
    assert not any(a.startswith("monero-seed-") for a in cfg['agents'])


def test_seeds_partial_declaration_fills_missing():
    text = SMALL_SCENARIO + (
        "  monero-seed-{001..003}:\n    daemon: monerod-sim\n    start_time: 0s\n"
        "    start_time_stagger: 1s\n"
    )
    cfg = _expand_text(text)
    for sid in SEED_IDS[:3]:
        assert cfg['agents'][sid]['daemon'] == 'monerod-sim'
    for i, sid in enumerate(SEED_IDS[3:], start=3):
        assert cfg['agents'][sid] == {'daemon': 'monerod', 'start_time': f'{i}s'}
    assert sum(1 for a in cfg['agents'] if a.startswith("monero-seed-")) == 6


def test_seeds_declared_group_untouched():
    text = SMALL_SCENARIO + (
        "  monero-seed-{001..006}:\n    daemon: monerod-sim\n    start_time: 0s\n"
        "    start_time_stagger: 1s\n"
    )
    cfg = _expand_text(text)
    for i, sid in enumerate(SEED_IDS):
        assert cfg['agents'][sid]['daemon'] == 'monerod-sim'
        assert cfg['agents'][sid]['start_time'] == f'{i}s'


def test_seed_phase_changes_nothing_else():
    with_seeds = _expand_text(SMALL_SCENARIO)
    without = _expand_text(_with_general_line('fallback_seeds: custom'))
    other = {k: v for k, v in with_seeds['agents'].items() if not k.startswith("monero-seed-")}
    assert other == dict(without['agents'])
    g1 = dict(with_seeds['general']); g2 = dict(without['general'])
    g1.pop('fallback_seeds', None); g2.pop('fallback_seeds', None)
    assert g1 == g2
```

Note: the `SMALL_SCENARIO` string must end with the `agents:` block so appended group lines land under `agents:`; if it does not, insert the lines after the `agents:\n` line instead (`text = SMALL_SCENARIO.replace("agents:\n", "agents:\n" + lines, 1)`).

- [ ] **Step 2: Run to verify they fail**

Run: `venv/bin/python -m pytest scripts/test_scenario_parser.py -k seed -v`
Expected: `test_seeds_added_in_auto_mode` and `test_seeds_partial_declaration_fills_missing` FAIL (no seeds added); the others may pass.

- [ ] **Step 3: Implement**

In `scripts/scenario_parser.py`, near the other module constants:

```python
# Fallback seed slots written into the expanded config in `auto` mode. Must
# match MONERO_FALLBACK_SEED_IPS in src/lib.rs (six mainnet IPs) and the
# values build_seed_agent uses in src/agent/fallback_seeds.rs.
FALLBACK_SEED_SLOTS = 6
```

New helper after `expand_scenario`:

```python
def _add_fallback_seeds(general: Dict[str, Any], agents) -> None:
    """Append undeclared monero-seed-NNN slots in `auto` mode.

    Runs last so seeds never enter node-count calibration. Values match the
    Rust injector, so the generated Shadow config is unchanged. PyYAML reads
    an unquoted `off` as False; treat it as off.
    """
    mode = general.get('fallback_seeds', 'auto')
    if mode is False or mode != 'auto':
        return
    for i in range(FALLBACK_SEED_SLOTS):
        agent_id = f"monero-seed-{i + 1:03d}"
        if agent_id not in agents:
            agents[agent_id] = OrderedDict(
                [('daemon', 'monerod'), ('start_time', f"{i}s")]
            )
```

In `expand_scenario`, after the `_resolve_auto_agent_values(...)` call:

```python
    _add_fallback_seeds(general, agents)
```

(If `general` uses an absent key → default `'auto'`; `None` value also counts as absent: use `mode = general.get('fallback_seeds') ; if mode is None: mode = 'auto'`.)

- [ ] **Step 4: Run tests**

Run: `venv/bin/python -m pytest scripts/test_scenario_parser.py -v`
Expected: all PASS (existing tests included; if an existing test asserts exact agent counts/ids for SMALL_SCENARIO, update it to exclude `monero-seed-*` — the seeds are the intended change).

- [ ] **Step 5: Commit**

```bash
git add scripts/scenario_parser.py scripts/test_scenario_parser.py
git commit -m "scenario expansion writes undeclared fallback seeds (auto mode)"
```

### Task 2: Rust stock-seed warning + parity test

**Files:**
- Modify: `src/agent/fallback_seeds.rs` (new `pub fn stock_seed_warning`, call it in `prepare_fallback_seeds`, `#[cfg(test)] mod tests`)
- Create: `tests/fallback_seed_parity.rs`

**Interfaces:**
- Consumes: `build_seed_agent(i) -> AgentConfig`, `fallback_seed_agent_id(n) -> String`, `DaemonConfig::{Local, Remote}`.
- Produces: `pub fn stock_seed_warning(agents: &AgentDefinitions) -> Option<String>`.

- [ ] **Step 1: Write failing unit tests** (bottom of `src/agent/fallback_seeds.rs`)

```rust
#[cfg(test)]
mod tests {
    use super::*;

    fn defs(entries: Vec<(&str, AgentConfig)>) -> AgentDefinitions {
        AgentDefinitions {
            agents: entries.into_iter().map(|(k, v)| (k.to_string(), v)).collect(),
        }
    }

    fn node(binary: &str) -> AgentConfig {
        let mut a = build_seed_agent(0);
        a.attributes = None;
        a.daemon = Some(DaemonConfig::Local(binary.to_string()));
        a
    }

    fn script_only() -> AgentConfig {
        let mut a = build_seed_agent(0);
        a.attributes = None;
        a.daemon = None;
        a.script = Some("agents.simulation_monitor".to_string());
        a
    }

    fn seeds(binary: &str) -> Vec<(String, AgentConfig)> {
        (0..6)
            .map(|i| {
                let mut a = build_seed_agent(i);
                a.daemon = Some(DaemonConfig::Local(binary.to_string()));
                (fallback_seed_agent_id(i + 1), a)
            })
            .collect()
    }

    fn with_seeds(binary: &str, mut rest: Vec<(&str, AgentConfig)>) -> AgentDefinitions {
        let s = seeds(binary);
        let mut d = defs(std::mem::take(&mut rest));
        for (k, v) in s {
            d.agents.insert(k, v);
        }
        d
    }

    #[test]
    fn warning_fires_when_only_seeds_are_stock() {
        let d = with_seeds("monerod", vec![("relay-001", node("monerod-sim")), ("relay-002", node("monerod-sim"))]);
        let msg = stock_seed_warning(&d).expect("should warn");
        assert!(msg.contains("monero-seed-001"));
        assert!(msg.contains("monerod-sim"));
        assert!(msg.contains("monero-seed-{001..006}"));
    }

    #[test]
    fn warning_silent_when_a_non_seed_runs_monerod() {
        let d = with_seeds("monerod", vec![("relay-001", node("monerod-sim")), ("miner-001", node("monerod"))]);
        assert_eq!(stock_seed_warning(&d), None);
    }

    #[test]
    fn warning_silent_when_seeds_are_not_stock() {
        let d = with_seeds("monerod-sim", vec![("relay-001", node("monerod-sim"))]);
        assert_eq!(stock_seed_warning(&d), None);
    }

    #[test]
    fn warning_silent_without_non_seed_daemons() {
        let d = with_seeds("monerod", vec![("simulation-monitor", script_only())]);
        assert_eq!(stock_seed_warning(&d), None);
    }

    #[test]
    fn warning_ignores_remote_daemons() {
        let mut w = script_only();
        w.daemon = Some(DaemonConfig::Remote { address: "auto".to_string(), strategy: None });
        let d = with_seeds("monerod", vec![("wallet-001", w)]);
        assert_eq!(stock_seed_warning(&d), None);
    }
}
```

- [ ] **Step 2: Run to verify they fail**

Run: `cargo test --lib fallback_seeds`
Expected: compile error, `stock_seed_warning` not found.

- [ ] **Step 3: Implement**

In `src/agent/fallback_seeds.rs`:

```rust
/// Warn when the fallback seeds run stock `monerod` but no other daemon
/// does: a network on a modified binary can have its blocks rejected by
/// stock seeds (e.g. SoP's version_minor rule is a hard fork). Compares the
/// `daemon` field only; `daemon_phases` are ignored, so upgrade configs
/// that start everyone on `monerod` stay quiet. `Remote` and daemon-less
/// agents are not counted.
pub fn stock_seed_warning(agents: &AgentDefinitions) -> Option<String> {
    let is_seed = |id: &str| {
        (1..=MONERO_FALLBACK_SEED_IPS.len().max(6)).any(|n| fallback_seed_agent_id(n) == id)
    };
    let local = |cfg: &AgentConfig| match &cfg.daemon {
        Some(DaemonConfig::Local(b)) => Some(b.clone()),
        _ => None,
    };
    let stock_seeds: Vec<&String> = agents
        .agents
        .iter()
        .filter(|(id, cfg)| is_seed(id) && local(cfg).as_deref() == Some("monerod"))
        .map(|(id, _)| id)
        .collect();
    if stock_seeds.is_empty() {
        return None;
    }
    let others: std::collections::BTreeSet<String> = agents
        .agents
        .iter()
        .filter(|(id, _)| !is_seed(id))
        .filter_map(|(_, cfg)| local(cfg))
        .collect();
    if others.is_empty() || others.contains("monerod") {
        return None;
    }
    let binaries = others.into_iter().collect::<Vec<_>>().join(", ");
    let example = others_first(&binaries);
    Some(format!(
        "Fallback seeds {} run stock monerod, but every other daemon runs {}. \
         Stock seeds may reject this network's blocks. To give the seeds the \
         network's binary, declare them in the scenario:\n  \
         monero-seed-{{001..006}}:\n    daemon: {}\n    start_time_stagger: 1s",
        stock_seeds.iter().map(|s| s.as_str()).collect::<Vec<_>>().join(", "),
        binaries,
        example
    ))
}

fn others_first(joined: &str) -> &str {
    joined.split(", ").next().unwrap_or(joined)
}
```

In `prepare_fallback_seeds`, replace the final `match mode { ... }` so the result is checked before returning:

```rust
    let (agents, pinned) = match mode {
        FallbackSeedsMode::Off => unreachable!(),
        FallbackSeedsMode::Auto => prepare_auto(&ips, user_agents, ip_registry),
        FallbackSeedsMode::Custom => prepare_custom(&ips, user_agents, ip_registry),
    };
    if let Some(msg) = stock_seed_warning(&agents) {
        log::warn!("{}", msg);
    }
    (agents, pinned)
```

- [ ] **Step 4: Write the parity integration test** (`tests/fallback_seed_parity.rs`)

```rust
//! The scenario expander writes undeclared fallback seeds into the expanded
//! config with the same values the Rust injector uses. This pins that the
//! two paths generate byte-identical Shadow configs.

use monerosim::{config_loader, orchestrator};
use std::path::Path;
use tempfile::TempDir;

fn generate(yaml_text: &str, tmp: &Path) -> String {
    let cfg_path = tmp.join("cfg.yaml");
    std::fs::write(&cfg_path, yaml_text).unwrap();
    let out = tmp.join("shadow_agents.yaml");
    let shared = tmp.join("shared");
    std::fs::create_dir_all(&shared).unwrap();
    std::fs::create_dir_all(tmp.join("scripts")).unwrap();
    let mut config = config_loader::load_config(&cfg_path).expect("loads");
    config.general.shared_dir = shared.to_string_lossy().to_string();
    config.general.daemon_data_dir = "/tmp".to_string();
    orchestrator::generate_agent_shadow_config(&config, &out).expect("generates");
    std::fs::read_to_string(&out)
        .unwrap()
        .replace(&tmp.to_string_lossy().to_string(), "TMP")
}

#[test]
fn declared_seeds_match_injected_seeds() {
    let base = std::fs::read_to_string("tests/fixtures/quickstart.yaml").unwrap();
    assert!(!base.contains("monero-seed-"), "fixture must rely on auto injection");
    let mut declared = base.clone();
    if !declared.ends_with('\n') {
        declared.push('\n');
    }
    for i in 0..6 {
        declared.push_str(&format!(
            "  monero-seed-{:03}:\n    daemon: monerod\n    start_time: {}s\n",
            i + 1,
            i
        ));
    }
    let a = TempDir::new().unwrap();
    let b = TempDir::new().unwrap();
    let injected = generate(&base, a.path());
    let explicit = generate(&declared, b.path());
    assert!(injected.contains("monero-seed-006"));
    assert_eq!(injected, explicit);
}
```

(`tests/fixtures/quickstart.yaml` ends with the `agents:` block, so appended lines land under `agents:`.)

- [ ] **Step 5: Run Rust tests**

Run: `cargo test --lib fallback_seeds && cargo test --test fallback_seed_parity && cargo test`
Expected: all PASS, goldens unchanged.

- [ ] **Step 6: Commit**

```bash
git add src/agent/fallback_seeds.rs tests/fallback_seed_parity.rs
git commit -m "fallback seeds: warn when only the seeds run stock monerod; parity test"
```

### Task 3: Docs and end-to-end check

**Files:**
- Modify: `docs/SCENARIO_FORMAT.md` (fallback-seeds section, lines ~45-90), `docs/FLOW.md:196-208`

- [ ] **Step 1: Update `docs/SCENARIO_FORMAT.md`**
  - `auto` row: injected hosts are written into the expanded config by scenario expansion.
  - Replace the "Seed hosts are not in the expanded config" paragraph with: in `auto` mode, scenario expansion appends any `monero-seed-NNN` you did not declare to the expanded YAML (`daemon: monerod`, `start_time` 0s–5s), so the expanded file lists every host. Monerosim YAMLs written by hand still get them injected at generation time.
  - Make the recommended example the range group with `start_time: 0s` and `start_time_stagger: 1s`, noting a daemon-only group otherwise staggers by 5 s; keep the per-slot form as an alternative.
  - Replace the preflight bullet: generation probes a seed binary only for the hard-fork schedule and native-mining flags, not every `daemon_defaults` flag; it warns when the seeds run stock `monerod` and no other daemon does.
- [ ] **Step 2: Update `docs/FLOW.md`** fallback-seed section to match (auto seeds written by scenario expansion; injector covers hand-written YAMLs; stock-seed warning).
- [ ] **Step 3: End-to-end parity**

```bash
for n in mainnet_replica_smoke mainnet_replica; do
  venv/bin/python scripts/generate_config.py --from test_configs/$n.scenario.yaml -o $S/$n.after.expanded.yaml
  ./target/release/monerosim --config $S/$n.after.expanded.yaml --output $S/$n.after.out
  grep -c "monero-seed-" $S/$n.after.expanded.yaml
  diff <(sed "s#$S/[^/]*\.\(before\|after\)\.out#OUT#g" $S/$n.before.out/shadow_agents.yaml) \
       <(sed "s#$S/[^/]*\.\(before\|after\)\.out#OUT#g" $S/$n.after.out/shadow_agents.yaml) && echo IDENTICAL
done
```

(Rebuild release first: `cargo build --release`.) Expected: seeds present in expanded YAML (count > 0), `IDENTICAL` for both. Any remaining diff must be only run-specific paths; investigate otherwise.

- [ ] **Step 4: Full test suites**

Run: `cargo test` and `venv/bin/python -m pytest -q`
Expected: all pass (previous baseline: pytest 898 passed, 2 skipped).

- [ ] **Step 5: Commit**

```bash
git add docs/SCENARIO_FORMAT.md docs/FLOW.md
git commit -m "docs: fallback seeds are written into the expanded config; stock-seed warning"
```
