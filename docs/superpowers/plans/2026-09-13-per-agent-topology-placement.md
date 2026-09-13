# Per-Agent Topology Placement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-agent `topology_node` knob that pins an agent to a chosen GML node id (overriding index-based distribution), so experiments can control an agent's network position and latency — enabling γ>0 selfish-mining runs.

**Architecture:** One optional `AgentConfig` field. A small pure function `apply_topology_pins` overrides the `agent_node_assignments` vector for pinned agents at the single distribution integration point in `process_user_agents`; every downstream consumer (IP allocation, peer overlay, `ShadowHost.network_node_id`) already reads that vector, so the pin propagates with no further change. Validation fails fast on a bad pin.

**Tech Stack:** Rust (serde/serde_yaml config, color_eyre errors), existing GML topology + Shadow config generation. Python selfish apparatus unchanged.

**Spec:** `docs/superpowers/specs/2026-09-13-per-agent-topology-placement-design.md`

## Global Constraints

- Stay on branch `feat/native-mining`; **local only — never push/merge without the user's explicit go.**
- No monerod patch; the Python selfish apparatus and `scripts/selfish_mining_analysis.py` are **not** modified (already γ-ready).
- Run `cargo test` **without** a global `MONEROSIM_SKIP_SIM_BINARY_CHECK=1` (the golden/integration tests set it themselves; the global var breaks `utils::mining::tests::probe_caches_and_handles_missing_binary`).
- The pin targets GML `node.id`; the codebase assumes `node.id == node index` for the synthetic GML. Validation checks existence by `.id`.
- Shared box: scope every process op to `lever65` (`pkill/pgrep -u lever65`); `nice` long runs; never edit `agents/*.py` or `venv/` while a sim is live.

---

## File Structure

- **Modify** `src/config/agent_config.rs` — add the `topology_node: Option<u32>` field to `AgentConfig` (+ a parse test).
- **Create** `src/topology/placement.rs` — `apply_topology_pins` pure function + unit tests (the whole override/validation logic, testable in isolation).
- **Modify** `src/topology/mod.rs` — declare `pub mod placement;`.
- **Modify** `src/agent/user_agents.rs` — call `apply_topology_pins` right after `agent_node_assignments` is built in `process_user_agents`.
- **Create** `tests/fixtures/topology_pins.yaml` + **Create** `tests/orchestrator_topology_pins.rs` — end-to-end integration test (pin reaches the emitted `network_node_id`).
- **Modify** `docs/SELFISH_MINING.md` (§8.4) + `CHANGELOG.md` — document the knob; retract the "no per-agent position knob" claim.
- **(Experiment, Task 5, controller-run)** `test_configs/selfish_phase3/` + optional custom GML + `docs/20260912_selfish_mining_results.md` — first γ-lift probe.

---

## Task 1: Add `topology_node` field to AgentConfig

**Files:**
- Modify: `src/config/agent_config.rs` (add field after `subnet_group`, ~line 218)
- Test: `src/config/agent_config.rs` (new `#[cfg(test)]` module in the same file)

**Interfaces:**
- Produces: `AgentConfig.topology_node: Option<u32>` (default `None`), consumed by Tasks 2–3.

- [ ] **Step 1: Write the failing test.** Add at the end of `src/config/agent_config.rs`:

```rust
#[cfg(test)]
mod topology_node_tests {
    use super::AgentConfig;

    // AgentConfig fields are all Option, so a partial YAML deserializes fine.
    fn parse(yaml: &str) -> AgentConfig {
        serde_yaml::from_str(yaml).expect("AgentConfig parses")
    }

    #[test]
    fn topology_node_parses_when_present() {
        let cfg = parse("script: agents.selfish_bridge\ntopology_node: 12\n");
        assert_eq!(cfg.topology_node, Some(12));
    }

    #[test]
    fn topology_node_defaults_to_none() {
        let cfg = parse("script: agents.selfish_bridge\n");
        assert_eq!(cfg.topology_node, None);
    }
}
```

- [ ] **Step 2: Run it, expect failure** (`topology_node` doesn't exist yet):

Run: `cargo test --lib topology_node_tests`
Expected: FAIL to compile — `no field topology_node on AgentConfig`.

> If `serde_yaml::from_str::<AgentConfig>` fails for a reason unrelated to the new field (e.g. AgentConfig needs surrounding context to deserialize), fall back to loading a minimal full config through `config_loader::load_config` on a temp file and read the agent out of `config.agents`. Do not weaken the assertion.

- [ ] **Step 3: Add the field.** In `struct AgentConfig`, immediately after the `subnet_group` field (~line 218):

```rust
    /// Pin this agent to a specific GML topology node (by node `id`), overriding
    /// the index-based distribution. Its network position — and thus its latency
    /// to every other agent — becomes that of the chosen node. Requires a GML
    /// topology (`network:` GML section). Multiple agents may share a node.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub topology_node: Option<u32>,
```

- [ ] **Step 4: Run the test, expect pass:**

Run: `cargo test --lib topology_node_tests`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit:**

```bash
git add src/config/agent_config.rs
git commit -m "feat(topology): add per-agent topology_node config field"
```

---

## Task 2: `apply_topology_pins` pure function + unit tests

**Files:**
- Create: `src/topology/placement.rs`
- Modify: `src/topology/mod.rs` (add `pub mod placement;`)

**Interfaces:**
- Consumes: `AgentConfig.topology_node` (Task 1).
- Produces: `pub fn apply_topology_pins(assignments: &mut [u32], user_agents: &[(&String, &AgentConfig)], valid_node_ids: &std::collections::HashSet<u32>, using_gml_topology: bool) -> Result<(), String>` — consumed by Task 3.

- [ ] **Step 1: Declare the module.** In `src/topology/mod.rs`, add alongside the other `pub mod` lines:

```rust
pub mod placement;
```

- [ ] **Step 2: Write the failing tests.** Create `src/topology/placement.rs` with ONLY the test module first (so it fails to compile against the missing function), then add the function in Step 4. Full file target:

```rust
//! Per-agent topology placement: override the distributed node assignment for
//! agents that pin `topology_node`. See
//! docs/superpowers/specs/2026-09-13-per-agent-topology-placement-design.md.

use crate::config::AgentConfig;
use std::collections::HashSet;

/// Override `assignments[i]` (the network-node id for `user_agents[i]`) for every
/// agent that sets `topology_node`. `assignments` and `user_agents` are
/// index-parallel. Each pin is validated against `valid_node_ids` (the GML node
/// ids); the first invalid pin returns `Err`. Pinning requires a GML topology.
pub fn apply_topology_pins(
    assignments: &mut [u32],
    user_agents: &[(&String, &AgentConfig)],
    valid_node_ids: &HashSet<u32>,
    using_gml_topology: bool,
) -> Result<(), String> {
    for (i, (agent_id, cfg)) in user_agents.iter().enumerate() {
        let node_id = match cfg.topology_node {
            Some(n) => n,
            None => continue,
        };
        if !using_gml_topology {
            return Err(format!(
                "agent '{agent_id}' sets topology_node={node_id} but this run has \
                 no GML topology (add a `network:` GML section)"
            ));
        }
        if !valid_node_ids.contains(&node_id) {
            return Err(format!(
                "agent '{agent_id}' pins topology_node={node_id}, which is not a \
                 node id in the GML topology"
            ));
        }
        if i < assignments.len() {
            assignments[i] = node_id;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cfg(yaml: &str) -> AgentConfig {
        serde_yaml::from_str(yaml).expect("AgentConfig parses")
    }
    fn ids(v: &[u32]) -> HashSet<u32> {
        v.iter().copied().collect()
    }

    #[test]
    fn no_pins_leaves_assignments_unchanged() {
        let a = "a".to_string();
        let ca = cfg("script: x");
        let agents = vec![(&a, &ca)];
        let mut asg = vec![7u32];
        apply_topology_pins(&mut asg, &agents, &ids(&[0, 1, 2]), true).unwrap();
        assert_eq!(asg, vec![7]);
    }

    #[test]
    fn pin_overrides_only_the_pinned_agent() {
        let (a, b) = ("a".to_string(), "b".to_string());
        let (ca, cb) = (cfg("script: x"), cfg("topology_node: 3"));
        let agents = vec![(&a, &ca), (&b, &cb)];
        let mut asg = vec![10u32, 11u32];
        apply_topology_pins(&mut asg, &agents, &ids(&[0, 1, 2, 3]), true).unwrap();
        assert_eq!(asg, vec![10, 3]);
    }

    #[test]
    fn colocation_is_allowed() {
        let (a, b) = ("a".to_string(), "b".to_string());
        let (ca, cb) = (cfg("topology_node: 2"), cfg("topology_node: 2"));
        let agents = vec![(&a, &ca), (&b, &cb)];
        let mut asg = vec![0u32, 0u32];
        apply_topology_pins(&mut asg, &agents, &ids(&[0, 1, 2]), true).unwrap();
        assert_eq!(asg, vec![2, 2]);
    }

    #[test]
    fn invalid_node_id_errors() {
        let a = "atk".to_string();
        let ca = cfg("topology_node: 99");
        let agents = vec![(&a, &ca)];
        let mut asg = vec![0u32];
        let err = apply_topology_pins(&mut asg, &agents, &ids(&[0, 1, 2]), true).unwrap_err();
        assert!(err.contains("atk") && err.contains("99"), "err was: {err}");
    }

    #[test]
    fn pin_without_gml_errors() {
        let a = "atk".to_string();
        let ca = cfg("topology_node: 1");
        let agents = vec![(&a, &ca)];
        let mut asg: Vec<u32> = vec![];
        let err = apply_topology_pins(&mut asg, &agents, &ids(&[]), false).unwrap_err();
        assert!(err.contains("no GML topology"), "err was: {err}");
    }
}
```

> Note on imports: if `crate::config::AgentConfig` does not resolve, use the path `user_agents.rs` uses for `AgentConfig` (check its `use` lines). If `serde_yaml` is not already a dev-dependency reachable here, it is used throughout the crate (see `agent_config.rs`), so it resolves.

- [ ] **Step 3: Run the tests, expect failure/compile-error** before the function body exists (write the test module first, function second, or observe the first compile fail if you paste both — either way confirm red then green):

Run: `cargo test --lib placement`
Expected: FAIL (missing function) → after full file, PASS.

- [ ] **Step 4: Ensure the function body (above) is present.** Run:

Run: `cargo test --lib placement`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit:**

```bash
git add src/topology/placement.rs src/topology/mod.rs
git commit -m "feat(topology): apply_topology_pins override + validation (unit-tested)"
```

---

## Task 3: Wire into orchestration + end-to-end integration test

**Files:**
- Modify: `src/agent/user_agents.rs` (in `process_user_agents`, after `agent_node_assignments` is built, ~line 467)
- Create: `tests/fixtures/topology_pins.yaml`
- Create: `tests/orchestrator_topology_pins.rs`

**Interfaces:**
- Consumes: `apply_topology_pins` (Task 2), `AgentConfig.topology_node` (Task 1).
- The enclosing fn is `pub fn process_user_agents(ctx: UserAgentProcessContext<'_>) -> color_eyre::eyre::Result<()>`, so errors propagate with `?`.

- [ ] **Step 1: Write the failing integration test.** Create `tests/orchestrator_topology_pins.rs`:

```rust
// tests/orchestrator_topology_pins.rs
use monerosim::{config_loader, orchestrator};
use std::path::Path;
use tempfile::TempDir;

#[test]
fn topology_node_pins_agent_to_gml_node() {
    std::env::set_var("MONEROSIM_SKIP_SIM_BINARY_CHECK", "1");
    let tmp = TempDir::new().unwrap();
    let output_yaml = tmp.path().join("shadow_agents.yaml");
    let shared_dir = tmp.path().join("shared");
    std::fs::create_dir_all(&shared_dir).unwrap();
    std::fs::create_dir_all(tmp.path().join("scripts")).unwrap();

    let mut config = config_loader::load_config(Path::new("tests/fixtures/topology_pins.yaml"))
        .expect("topology_pins fixture loads");
    config.general.shared_dir = shared_dir.to_string_lossy().to_string();

    orchestrator::generate_agent_shadow_config(&config, &output_yaml)
        .expect("orchestrator generates");

    let doc: serde_yaml::Value =
        serde_yaml::from_str(&std::fs::read_to_string(&output_yaml).unwrap()).unwrap();
    let hosts = doc.get("hosts").and_then(|h| h.as_mapping()).expect("hosts mapping");

    let mut checked = 0;
    for (k, v) in hosts {
        let name = k.as_str().unwrap_or("");
        if name.contains("pinned-bridge") {
            let nid = v
                .get("network_node_id")
                .and_then(|n| n.as_u64())
                .expect("pinned host has network_node_id");
            assert_eq!(nid, 5, "pinned-bridge host '{name}' must be at node 5");
            checked += 1;
        }
    }
    assert!(checked > 0, "pinned-bridge host present in generated config");
}
```

- [ ] **Step 2: Create the fixture** `tests/fixtures/topology_pins.yaml`:

```yaml
general:
  stop_time: 10m
  simulation_seed: 12345
  enable_dns_server: true
network:
  path: gml_processing/1200_nodes_caida_with_loops.gml
  peer_mode: Dynamic
agents:
  plain-node:
    daemon: monerod
    start_time: 0s
  pinned-bridge:
    daemon: monerod
    start_time: 0s
    topology_node: 5
```

- [ ] **Step 3: Run the test, expect failure** (pin not wired in yet, so the pinned host is at its distributed node, not 5):

Run: `cargo test --test orchestrator_topology_pins`
Expected: FAIL — `network_node_id` for `pinned-bridge` is not 5 (or the assert fires).

> If it happens to pass by coincidence (the distributor placed it at 5 anyway), change `topology_node` in the fixture to a different existing id (e.g. `900`) and update the test's expected value to match — the point is that the pin, not the distributor, chose it.

- [ ] **Step 4: Wire the override in.** In `src/agent/user_agents.rs`, `process_user_agents`:
  1. Change the assignment binding to be mutable — the `let agent_node_assignments = ...` block that ends ~line 467 becomes `let mut agent_node_assignments`.
  2. Immediately AFTER that block (before `build_peer_topology`, ~line 476), insert:

```rust
    // Per-agent topology pins override the index-based distribution. This must run
    // before build_peer_topology / IP allocation consume agent_node_assignments,
    // since those read the (now-overridden) node ids. See
    // docs/superpowers/specs/2026-09-13-per-agent-topology-placement-design.md.
    let valid_node_ids: std::collections::HashSet<u32> = gml_graph
        .map(|gml| gml.nodes.iter().map(|n| n.id).collect())
        .unwrap_or_default();
    crate::topology::placement::apply_topology_pins(
        &mut agent_node_assignments,
        &user_agents,
        &valid_node_ids,
        using_gml_topology,
    )
    .map_err(color_eyre::eyre::eyre!)?;
```

> `map_err(color_eyre::eyre::eyre!)` may need to be `.map_err(|e| color_eyre::eyre::eyre!(e))?` depending on the eyre version's macro form — use whichever compiles; both turn the `String` into an `eyre::Report`. Confirm `gml_graph` (an `Option<&GmlGraph>`), `using_gml_topology` (a `bool`), and `user_agents` are all in scope at this point — they are used just above at lines 433–460.

- [ ] **Step 5: Run the integration test + the unit tests, expect pass:**

Run: `cargo test --test orchestrator_topology_pins && cargo test --lib placement`
Expected: PASS.

- [ ] **Step 6: Run the full suite to confirm no regression** (the 4 existing goldens must be byte-identical — the override is a no-op when no agent pins):

Run: `cargo test`
Expected: PASS (all, including `orchestrator_selfish/native/quickstart/smoke`).

- [ ] **Step 7: Commit:**

```bash
git add src/agent/user_agents.rs tests/fixtures/topology_pins.yaml tests/orchestrator_topology_pins.rs
git commit -m "feat(topology): apply topology_node pins in orchestration (+ integration test)"
```

---

## Task 4: Documentation + CHANGELOG

**Files:**
- Modify: `docs/SELFISH_MINING.md` (§8.4, the "γ is lifted by fan-out, not topology position" section)
- Modify: `CHANGELOG.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Update `docs/SELFISH_MINING.md` §8.4.** It currently states there is *no* per-agent position knob. Add a paragraph at the end of §8.4 (do not delete the history — the fan-out finding stands):

```markdown
**Update (2026-09-13): a per-agent position knob now exists.** The
`topology_node: <gml node id>` agent attribute pins an agent to a specific GML
node, overriding the index-based distribution (see
`docs/superpowers/specs/2026-09-13-per-agent-topology-placement-design.md`). This
makes γ *addressable*: an experiment can place the attacker's detector and
publisher bridges near a chosen honest subset while the honest finder is far.
Lifting γ is still an empirical exercise — the attacker is reactive, so its block
starts the propagation race late — but the placement lever the earlier text said
was missing is now available. See the phase-3 rows in
`docs/20260912_selfish_mining_results.md`.
```

- [ ] **Step 2: Add a CHANGELOG entry** under the appropriate unreleased/native-mining section:

```markdown
- Per-agent `topology_node` attribute: pin an agent to a specific GML topology
  node id, overriding index-based distribution (enables γ-vs-position
  selfish-mining experiments). Requires a GML topology; validated against the
  GML node ids.
```

- [ ] **Step 3: Commit:**

```bash
git add docs/SELFISH_MINING.md CHANGELOG.md
git commit -m "docs(topology): document topology_node knob; retract 'no position knob' claim"
```

---

## Task 5: First γ-lift experiment (controller-run, empirical)

> **This task is run by the controller after Tasks 1–4 pass, not dispatched as a
> mechanical builder task.** It is empirical: success is measured, and a
> null result is still a documented result (per the spec). Do not run any sim
> while another is live; check `pgrep -u lever65 -x shadow` first.

**Files:**
- Create: `test_configs/selfish_phase3/gamma_lift.yaml` (mirror `test_configs/selfish_phase2/fanout_3.yaml`, add `topology_node` pins)
- Optional Create: a small custom GML with an explicit latency contrast if the stock 1200-node GML's incidental latencies are insufficient
- Modify: `docs/20260912_selfish_mining_results.md` (add a phase-3 section with the run + result)

**Steps:**

- [ ] **Step 1: Design the placement.** Choose GML node ids such that: the attacker's publisher bridges are low-latency to a chosen subset of honest miners; the honest block-finder(s) are high-latency to that subset; the attacker's detector bridge is low-latency to the finder. Inspect candidate node-pair latencies from the GML edges (or author a small custom GML with hand-set latencies — keep node ids `0..N-1`). Pin the attacker's offline miner, detector bridge, publisher bridges, and honest miners with `topology_node`.

- [ ] **Step 2: Write `gamma_lift.yaml`** from `fanout_3.yaml` (3 honest miners + relays + attacker + bridges, α=0.4, `fixed-difficulty: 1200`, small `reaction_delay_ms`), adding the `topology_node` pins from Step 1.

- [ ] **Step 3: Run it** (nice'd, background): `nice -n 10 ./run_sim.sh --config test_configs/selfish_phase3/gamma_lift.yaml --name p3_gamma_lift`.

- [ ] **Step 4: Analyse:** `venv/bin/python scripts/selfish_mining_analysis.py archived_runs/<run>` — read realized γ and attacker share.

- [ ] **Step 5: Document** in `docs/20260912_selfish_mining_results.md`: add a "Phase 3 — γ vs position" section with the config, run-dir, measured γ and share vs the Eyal–Sirer γ curve. **Report honestly:** if γ lifted above the phase-2 ≈0 baseline, state by how much; if not, state that placement at these latencies/overlay was insufficient and what to change next (bigger latency contrast, more/placed publishers, smaller reaction). No overclaiming.

- [ ] **Step 6: Commit:**

```bash
git add test_configs/selfish_phase3/ docs/20260912_selfish_mining_results.md
git commit -m "exp(selfish): phase-3 gamma-vs-position first probe (topology pins)"
```

---

## Self-Review

**Spec coverage:**
- Knob (`topology_node: Option<u32>`) → Task 1. ✓
- Override at the single integration point → Task 3 (`process_user_agents`). ✓
- Downstream auto-follows (no change) → verified by Task 3 Step 6 (goldens unchanged) + the integration test. ✓
- Validation: GML required, node exists, co-location allowed → Task 2 (`apply_topology_pins`, 3 error/allow cases tested) + surfaced in the pipeline by Task 3. ✓
- Testing: unit (config parse) → T1; unit (override + validation) → T2; integration (end-to-end network_node_id) → T3; golden regression (no-op when unpinned) → T3 Step 6. ✓
- Non-goals (per-edge latency, proximity abstraction) → not built. ✓
- Experiment (empirical probe) → Task 5. ✓
- Docs / retract "no position knob" → Task 4. ✓

**Placeholder scan:** No TBD/TODO; every code step has concrete code; validation is concrete (three explicit cases). ✓

**Type consistency:** `apply_topology_pins(&mut [u32], &[(&String, &AgentConfig)], &HashSet<u32>, bool) -> Result<(), String>` is identical in Task 2 (definition), Task 3 (call), and the interfaces blocks. `topology_node: Option<u32>` identical in T1/T2/T3. Enclosing fn return type `color_eyre::eyre::Result<()>` matches the `?` propagation in T3. ✓

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-13-per-agent-topology-placement.md`. Recommended execution: **subagent-driven-development** (fresh subagent per task, review between tasks), Tasks 1–4 as mechanical/builder tasks, Task 5 controller-run (empirical).
