# Per-Agent Topology Placement — Design (2026-09-13)

## Goal

Add a per-agent knob that pins a chosen agent to a chosen GML topology node, so
an experiment can control an agent's network *position* (and therefore its
latency to other agents). The immediate motivation is to enable **γ>0
selfish-mining experiments** (phase 3): to lift the tie-break advantage γ we must
be able to place the attacker's publisher bridges close (low latency) to a chosen
subset of honest miners while the honest block-finder is far from them. Today
monerosim assigns agents to GML nodes purely by list index, with no per-agent
override, so γ stays ≈0 by construction (documented in
`docs/20260912_selfish_mining_results.md`, §"What the fan-out sweep shows").

This is an **enabling feature**, not a guaranteed result. The knob is small and
deterministic; *demonstrating* γ>0 with it is an empirical probe (see
§6) because the attacker is reactive — it learns of the honest block through its
own bridges and then publishes, so its block always starts the propagation race a
beat late. Placement is the lever that can overcome that; whether a given
placement does is measured, not assumed.

## Background — how placement works today

Verified in the current tree (`b4d2ea1f`):

- **Assignment is index-based, no hook.** `distribute_agents_across_topology`
  (`src/topology/distribution.rs`) returns `Vec<Option<usize>>` indexed by the
  agent's position in the input slice; `distribute_sequential`/`distribute_global`
  choose nodes by loop counter, never by agent id or role. The sole caller is
  `src/agent/user_agents.rs:448`, which maps the result into
  `agent_node_assignments: Vec<u32>` (line 456).
- **That vector *is* the node id.** `agent_node_assignments[i]` is used directly
  as `network_node_id` (`peer_connections.rs:113-114`,
  `user_agents.rs:1587-1588`), and the IP allocator matches it against
  `gml.nodes[..].id` (`src/ip/allocator.rs:71`). The codebase assumes GML
  `node.id == node index` for the synthetic topology (AS `0..N-1`).
- **Latency derives entirely from position.** Inter-node latency is the GML edge
  attribute between the two agents' assigned nodes (`src/gml_parser.rs`,
  `src/orchestrator.rs:111-130`). There is no per-agent latency override; to give
  an agent a specific latency you pin its node.
- **Per-agent Shadow-host customization is already a pattern.** `ShadowHost` is
  built per agent and already carries conditional per-agent fields — e.g.
  `blocked_inbound_ports` for `reachable_fraction`'s synthetic firewall
  (`user_agents.rs:1593-1607`). A per-agent placement field rides the same rails.
- **Existing per-agent knobs:** `subnet_group` (IP /24 clustering),
  `attributes`, `daemon_options`/`wallet_options`. None for position/latency.

**Consequence:** because everything downstream (IP allocation, peer overlay,
`ShadowHost.network_node_id`) reads `agent_node_assignments`, overriding that one
vector for pinned agents makes the pin take effect everywhere. This is a layered
addition at a single integration point, not a rewrite.

## Design — the feature

### The knob

Add one optional field to `AgentConfig` (`src/config/agent_config.rs`):

```rust
/// Pin this agent to a specific GML topology node (by node `id`), overriding
/// the index-based distribution. Its network position — and thus its latency to
/// every other agent — becomes that of the chosen node. Requires a GML topology.
/// Multiple agents may share a node (co-location is already supported).
#[serde(skip_serializing_if = "Option::is_none")]
pub topology_node: Option<u32>,
```

YAML usage:

```yaml
agents:
  attacker-publisher-1:
    script: agents.selfish_bridge
    topology_node: 12        # pin to GML node id 12
```

### Where it applies

In `src/agent/user_agents.rs`, immediately after `agent_node_assignments` is
built (after line 467, before `build_peer_topology` at line 484), add an override
pass:

```
for (i, (agent_id, cfg)) in user_agents.iter().enumerate() {
    if let Some(node_id) = cfg.topology_node {
        // validation below decides whether this errors or applies
        agent_node_assignments[i] = node_id;
    }
}
```

`user_agents: &[(&String, &AgentConfig)]` is index-parallel with
`agent_node_assignments`, so index `i` is the same agent in both. This mirrors the
existing `subnet_group` access idiom (`peer_connections.rs:119-122`). No
downstream change is needed: IP allocation, the peer overlay, and the emitted
`ShadowHost.network_node_id` all already consume `agent_node_assignments[i]`.

### Validation

Fail fast (this is a precision knob for experiments; a silent mis-pin would
invalidate results):

1. **GML required.** If any agent sets `topology_node` while the run is not using
   a GML topology (`using_gml_topology == false` / `gml_graph.is_none()`), return
   a configuration error naming the agent.
2. **Node must exist.** The pinned id must satisfy
   `gml.nodes.iter().any(|n| n.id == node_id)`; otherwise a configuration error
   naming the agent and id, and (helpfully) the valid id range.
3. **Co-location is allowed** (not an error): monerosim already places multiple
   hosts on one GML node, and an attacker cluster *wants* co-located publishers.

Validation runs in the same override pass (or just before it), before any IP is
allocated, so a bad config aborts generation rather than producing a wrong sim.

### Interactions / non-goals

- **Distribution strategy:** pins override the strategy's choice for pinned
  agents only; unpinned agents still distribute as before. Deterministic.
- **`subnet_group`:** orthogonal (IP clustering vs topology position); both may be
  set. `reachable_fraction`/`hidden_fraction`: orthogonal (inbound reachability
  vs position).
- **Non-goal: per-edge latency override.** Latency is a GML property; to get a
  specific latency contrast, pin agents onto a GML that has the desired edges
  (the phase-3 experiment ships a small custom GML — see §6). We are not adding a
  per-agent latency number.
- **Non-goal: higher-level proximity/region abstraction.** `topology_node` (pin
  by id) is the minimal primitive; a friendlier "put these agents near each
  other" layer can come later on top of it.

## Testing

- **Unit (config):** `topology_node` round-trips through YAML parsing (present /
  absent); default is `None`.
- **Unit/integration (override):** given a small GML and two agents, one pinned
  and one not, the pinned agent's `agent_node_assignments` entry equals its
  `topology_node` and the unpinned one keeps the distributed value.
- **Validation:** pinning a non-existent node id errors; pinning without a GML
  topology errors; both error messages name the agent.
- **Golden:** a fixture config with `topology_node` pins produces a deterministic
  Shadow config whose pinned hosts carry the expected `network_node_id`
  (extends the existing `tests/orchestrator_*.rs` golden pattern).

## The γ-lift experiment (phase 3, empirical probe)

The feature's purpose. This section is the *hypothesis and first approach*, not a
guaranteed outcome.

- **Mechanism.** For the attacker's released tie-block to win at some honest
  miner H, it must reach H before the honest finder's block does. The attacker is
  reactive: it hears the honest block via a detector bridge, then (reaction delay)
  publishes through its publisher bridges. So its block is delayed by
  `latency(finder→detector) + reaction` before it even starts spreading. It wins
  at H only where `latency(publisher→H)` beats `latency(finder→H)` by more than
  that delay. γ = the fraction of honest-resolved ties won this way.
- **First approach.** Ship a small **custom GML** with explicit edge latencies
  that create the contrast: attacker publisher node(s) low-latency to a target
  honest subset S, honest finder(s) high-latency to S, and the detector
  low-latency to the finder (hears fast). Place the attacker's offline miner,
  detector, and publishers, plus the honest miners, with `topology_node`. Keep
  `reaction_delay_ms` small. Run and analyse with the existing
  `scripts/selfish_mining_analysis.py` (`realized_gamma`, honest-resolved ties).
- **Success criterion.** Realized γ measurably above the phase-2 ≈0 baseline
  (honest-resolved tie wins clearly beyond small-count noise), with attacker
  share rising toward the corresponding Eyal–Sirer γ curve. If the first config
  does not lift γ, the run is still a result: it documents that placement alone,
  at these latencies/overlay, was insufficient, and what to change (bigger
  contrast, more/again-placed publishers, smaller reaction). No overclaiming.
- **Caveat.** Propagation also depends on the peer *overlay* (who connects to
  whom), not just GML latency, so the first placement may need iteration. This is
  expected and is why the deliverable is "capability + a documented first probe,"
  not "γ>0 guaranteed."

## Global constraints

- Stay on `feat/native-mining`; **local only** — never push/merge without the
  user's explicit go.
- No monerod patch; the selfish apparatus keeps using stock RPCs + `--offline`.
- The Python selfish apparatus and `realized_gamma` analysis do **not** change —
  they are already γ-ready; only topology placement is added.
- Shared box: scope every process op to `lever65`; `nice` long runs; never edit
  `agents/*.py` or `venv/` while a sim is live.
- `cargo test` without a global `MONEROSIM_SKIP_SIM_BINARY_CHECK` (the golden
  tests set it themselves; the global var breaks the probe test).

## Risks

- **γ-lift is empirical.** The feature is deterministic and testable; the
  experiment outcome is not guaranteed on the first config (documented as such).
- **id == index assumption.** The pin targets `node.id`; the codebase assumes
  `node.id == index` for the synthetic GML. The custom experiment GML must keep
  that invariant (ids `0..N-1`), and validation checks existence by `.id`.
- **Determinism.** The override is deterministic; the golden test guards it. (The
  *sim* still uses `native_preemption: true`, ~0.05 share noise — an experiment
  property, not a feature concern.)
