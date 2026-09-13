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
    use crate::config::AgentConfig;

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
