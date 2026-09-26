//! Honest-node /24 co-location (gap G5). See
//! `docs/superpowers/specs/2026-09-23-mainnet-replica-design.md` §3 "Honest
//! prefix sharing" and §7 G5.
//!
//! monerosim gives every GML node its own /24 (`src/ip/as_manager.rs`), one
//! IP per agent placed there. Mainnet honest nodes are far more concentrated
//! (Kirschner 2026 / S11: 12% of BGP prefixes hold 55% of nodes, ~11 per
//! dense prefix). This module re-targets a fraction of the *already
//! distributed* honest agents onto a handful of shared GML nodes, so their
//! P2P connections collapse under monerod's /24 dedup the way mainnet's do.
//!
//! Runs after [`crate::topology::distribute_agents_across_topology`] and
//! before [`crate::topology::placement::apply_topology_pins`] — pins always
//! win, and never become a co-location target.

use std::collections::{HashMap, HashSet};

use crate::config::{AgentConfig, PrefixSharingConfig};
use crate::ip::as_manager::{get_region_for_node, AsRegion};
use crate::utils::seeded_hash::{finalize_hash, seeded_hash};

/// Fixed iteration order for region grouping — keeps chunking (and its log
/// summary) deterministic regardless of `HashMap` iteration order.
const REGION_ORDER: [AsRegion; 7] = [
    AsRegion::NorthAmerica,
    AsRegion::Europe,
    AsRegion::Asia,
    AsRegion::SouthAmerica,
    AsRegion::Africa,
    AsRegion::Oceania,
    AsRegion::Unknown,
];

/// Re-target a `config.fraction` slice of eligible honest daemons onto shared
/// GML nodes, `config.per_prefix` agents per node, inside each agent's
/// current region.
///
/// `assignments[i]` is the GML node id for `user_agents[i]` (index-parallel),
/// as produced by the base distribution. Eligible = has a local daemon
/// (`AgentConfig::has_local_daemon`), is not a miner, is not a seed host
/// (`attributes.is_seed_node == "true"`), and does not pin `topology_node`
/// (checked directly on the agent's own config, since this runs before pins
/// are applied). Script-only and wallet-only-remote agents have no local
/// daemon and are never eligible.
///
/// Selection is deterministic: eligible ids are sorted by
/// `finalize_hash(seeded_hash(seed, "prefix:" + id))` and the first
/// `round(fraction * eligible.len())` are taken. Selected agents are grouped
/// by the region of their current node (fixed region order, hash order
/// preserved within a region) and chunked into groups of `per_prefix` (the
/// last chunk in a region may be smaller). Each chunk's target node is the
/// *current* node of its first member whose node is not a pin target of any
/// agent in `user_agents`; if every member's current node is pinned, the
/// chunk is left on the first member's node (nothing to gain by moving it).
pub fn apply_prefix_sharing(
    assignments: &mut [u32],
    user_agents: &[(&String, &AgentConfig)],
    total_nodes: usize,
    seed: u64,
    config: &PrefixSharingConfig,
) {
    if total_nodes == 0 || assignments.is_empty() {
        return;
    }

    // Node ids pinned by ANY agent's `topology_node` — never a chunk target.
    let pinned_nodes: HashSet<u32> = user_agents
        .iter()
        .filter_map(|(_, cfg)| cfg.topology_node)
        .collect();

    let mut eligible: Vec<usize> = Vec::new();
    for (i, (_, cfg)) in user_agents.iter().enumerate() {
        if i >= assignments.len() {
            continue;
        }
        if cfg.topology_node.is_some() {
            continue; // pinned agents are never selected
        }
        if cfg.is_miner() {
            continue;
        }
        let is_seed = cfg
            .attributes
            .as_ref()
            .map(|a| a.get("is_seed_node").map_or(false, |v| v == "true"))
            .unwrap_or(false);
        if is_seed {
            continue;
        }
        if !cfg.has_local_daemon() {
            continue; // script-only / remote-daemon agents don't run a local P2P node
        }
        eligible.push(i);
    }

    let n_eligible = eligible.len();
    let frac = config.fraction.clamp(0.0, 1.0);
    let n_selected = ((frac * n_eligible as f64).round() as usize).min(n_eligible);
    if n_selected == 0 {
        return;
    }

    eligible.sort_by_key(|&i| {
        finalize_hash(seeded_hash(seed, &format!("prefix:{}", user_agents[i].0)))
    });
    let selected: Vec<usize> = eligible.into_iter().take(n_selected).collect();

    let per_prefix = (config.per_prefix as usize).max(1);

    // Group selected indices by current region, preserving hash order.
    let mut by_region: HashMap<AsRegion, Vec<usize>> = HashMap::new();
    for &i in &selected {
        let region = get_region_for_node(assignments[i] as usize, total_nodes);
        by_region.entry(region).or_default().push(i);
    }

    let mut chunk_count = 0usize;
    let mut nodes_used: HashSet<u32> = HashSet::new();
    for region in REGION_ORDER {
        let Some(members) = by_region.get(&region) else {
            continue;
        };
        for chunk in members.chunks(per_prefix) {
            chunk_count += 1;
            // Target = the current node of the first member that isn't a pin
            // target; fall back to the first member's node if every member's
            // current node happens to be pinned (leaves the chunk unmoved).
            let target = chunk
                .iter()
                .map(|&m| assignments[m])
                .find(|node| !pinned_nodes.contains(node))
                .unwrap_or_else(|| assignments[chunk[0]]);
            for &member in chunk {
                assignments[member] = target;
            }
            nodes_used.insert(target);
        }
    }

    log::info!(
        "Honest prefix sharing: {} eligible, {} selected (fraction {}), {} chunk(s) of up to \
         {} onto {} shared GML node(s)/24(s)",
        n_eligible,
        n_selected,
        frac,
        chunk_count,
        per_prefix,
        nodes_used.len()
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    fn daemon_cfg(yaml: &str) -> AgentConfig {
        serde_yaml::from_str(yaml).expect("AgentConfig parses")
    }

    fn ps(fraction: f64, per_prefix: u32) -> PrefixSharingConfig {
        PrefixSharingConfig {
            fraction,
            per_prefix,
        }
    }

    /// Build `n` plain relay-like agents ("relay-000".."relay-{n-1}"), each
    /// with a local daemon and no pin/miner/seed markers.
    fn make_relays(n: usize) -> (Vec<String>, Vec<AgentConfig>) {
        let ids: Vec<String> = (0..n).map(|i| format!("relay-{:03}", i)).collect();
        let cfgs: Vec<AgentConfig> = (0..n).map(|_| daemon_cfg("daemon: monerod")).collect();
        (ids, cfgs)
    }

    fn as_refs<'a>(ids: &'a [String], cfgs: &'a [AgentConfig]) -> Vec<(&'a String, &'a AgentConfig)> {
        ids.iter().zip(cfgs.iter()).collect()
    }

    #[test]
    fn absent_config_leaves_assignments_unchanged() {
        // Modeled by fraction 0.0 (the caller's "config absent" branch never
        // invokes this function at all; fraction 0 is the no-op case within it).
        let (ids, cfgs) = make_relays(10);
        let refs = as_refs(&ids, &cfgs);
        let mut assignments: Vec<u32> = (0..10).collect();
        let before = assignments.clone();
        apply_prefix_sharing(&mut assignments, &refs, 1200, 42, &ps(0.0, 11));
        assert_eq!(assignments, before);
    }

    #[test]
    fn fraction_and_per_prefix_produce_expected_chunking() {
        // 100 agents, all placed one-per-node inside NA (node ids 0..99, NA is
        // 0..199 for a 1200-node topology). fraction 0.55 * per_prefix 11 =>
        // 55 moved onto 5 shared nodes of 11; 45 untouched, one-per-node.
        let (ids, cfgs) = make_relays(100);
        let refs = as_refs(&ids, &cfgs);
        let mut assignments: Vec<u32> = (0..100).collect();
        let before = assignments.clone();
        apply_prefix_sharing(&mut assignments, &refs, 1200, 7, &ps(0.55, 11));

        // Count how many distinct original agents now share each final node.
        let mut per_node: HashMap<u32, Vec<usize>> = HashMap::new();
        for (i, &node) in assignments.iter().enumerate() {
            per_node.entry(node).or_default().push(i);
        }
        let shared_nodes: Vec<&Vec<usize>> = per_node.values().filter(|v| v.len() > 1).collect();
        assert_eq!(shared_nodes.len(), 5, "expected 5 shared nodes");
        for group in &shared_nodes {
            assert_eq!(group.len(), 11, "each shared node holds 11 agents");
        }
        let moved_total: usize = shared_nodes.iter().map(|g| g.len()).sum();
        assert_eq!(moved_total, 55);

        // The untouched 45 keep their original one-per-node placement.
        let untouched = per_node.values().filter(|v| v.len() == 1).count();
        assert_eq!(untouched, 45);
        for (i, &node) in assignments.iter().enumerate() {
            if per_node[&node].len() == 1 {
                assert_eq!(node, before[i], "untouched agent must keep its original node");
            }
        }
    }

    #[test]
    fn region_is_preserved() {
        let (ids, cfgs) = make_relays(30);
        let refs = as_refs(&ids, &cfgs);
        // Spread across NA (0..199) and EU (200..499) manually.
        let mut assignments: Vec<u32> = (0..30)
            .map(|i| if i % 2 == 0 { i as u32 } else { 200 + i as u32 })
            .collect();
        let before_regions: Vec<AsRegion> = assignments
            .iter()
            .map(|&n| get_region_for_node(n as usize, 1200))
            .collect();
        apply_prefix_sharing(&mut assignments, &refs, 1200, 99, &ps(1.0, 4));
        let after_regions: Vec<AsRegion> = assignments
            .iter()
            .map(|&n| get_region_for_node(n as usize, 1200))
            .collect();
        assert_eq!(before_regions, after_regions);
    }

    #[test]
    fn pinned_nodes_are_never_targets_and_pinned_agents_never_selected() {
        let mut ids = vec!["pin-agent".to_string()];
        let mut cfgs = vec![daemon_cfg("daemon: monerod\ntopology_node: 3")];
        let (relay_ids, relay_cfgs) = make_relays(9);
        ids.extend(relay_ids);
        cfgs.extend(relay_cfgs);
        let refs = as_refs(&ids, &cfgs);

        // pin-agent pins topology_node 3, but its own *distribution* slot
        // (before apply_topology_pins runs later) is node 0. One relay
        // (overall index 3, "relay-002") happens to be pre-distributed onto
        // node 3 — exactly the pinned node id — so it must never be picked as
        // a chunk target.
        let mut assignments: Vec<u32> = (0..10).collect();
        apply_prefix_sharing(&mut assignments, &refs, 1200, 5, &ps(1.0, 9));

        // pin-agent (index 0) is excluded from selection: unmoved by this pass.
        assert_eq!(assignments[0], 0);
        // No relay (indices 1..=9) ends up on node 3, the pinned target.
        for &node in &assignments[1..] {
            assert_ne!(node, 3, "pinned node 3 must never be a chunk target");
        }
    }

    #[test]
    fn miners_and_seeds_are_never_selected() {
        let mut ids = vec!["miner-a".to_string(), "seed-a".to_string()];
        let mut cfgs = vec![
            daemon_cfg("daemon: monerod\nhashrate: 10"),
            daemon_cfg("daemon: monerod\nattributes:\n  is_seed_node: \"true\""),
        ];
        let (relay_ids, relay_cfgs) = make_relays(8);
        ids.extend(relay_ids);
        cfgs.extend(relay_cfgs);
        let refs = as_refs(&ids, &cfgs);

        let mut assignments: Vec<u32> = (0..10).collect();
        let before = assignments.clone();
        apply_prefix_sharing(&mut assignments, &refs, 1200, 11, &ps(1.0, 4));

        assert_eq!(assignments[0], before[0], "miner untouched");
        assert_eq!(assignments[1], before[1], "seed host untouched");
    }

    #[test]
    fn deterministic_by_seed() {
        let (ids, cfgs) = make_relays(40);
        let refs = as_refs(&ids, &cfgs);

        let mut a1: Vec<u32> = (0..40).collect();
        apply_prefix_sharing(&mut a1, &refs, 1200, 123, &ps(0.5, 4));
        let mut a2: Vec<u32> = (0..40).collect();
        apply_prefix_sharing(&mut a2, &refs, 1200, 123, &ps(0.5, 4));
        assert_eq!(a1, a2, "same seed must reproduce the same result");

        let mut a3: Vec<u32> = (0..40).collect();
        apply_prefix_sharing(&mut a3, &refs, 1200, 456, &ps(0.5, 4));
        assert_ne!(a1, a3, "different seed should (almost certainly) differ");
    }

    #[test]
    fn wallet_only_remote_daemon_agent_is_not_eligible() {
        let mut ids = vec!["remote-user".to_string()];
        let mut cfgs = vec![daemon_cfg(
            "daemon:\n  address: \"auto\"\nwallet: monero-wallet-rpc\n",
        )];
        let (relay_ids, relay_cfgs) = make_relays(8);
        ids.extend(relay_ids);
        cfgs.extend(relay_cfgs);
        let refs = as_refs(&ids, &cfgs);

        let mut assignments: Vec<u32> = (0..9).collect();
        let before = assignments.clone();
        apply_prefix_sharing(&mut assignments, &refs, 1200, 3, &ps(1.0, 4));
        assert_eq!(assignments[0], before[0], "remote-daemon agent untouched");
    }
}
