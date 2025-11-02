//! Peer connection management.
//!
//! This file handles generation of peer connections based on the selected
//! topology pattern and peer discovery mode (Dynamic, Hardcoded, Hybrid).

use crate::topology::types::Topology;

/// Generate peer connections based on topology template
///
/// # Arguments
/// * `topology` - The network topology template (Star, Mesh, Ring, DAG)
/// * `agent_index` - The index of the current agent
/// * `seed_agents` - List of all available seed nodes
/// * `agent_ip` - The IP address of the current agent
///
/// # Returns
/// A vector of connection strings in the format `--seed-node=IP:PORT`
pub fn generate_topology_connections(
    topology: &Topology,
    agent_index: usize,
    seed_agents: &[String],
    agent_ip: &str,
) -> Vec<String> {
    match topology {
        Topology::Star => {
            // Star topology: all nodes connect to the first seed node (hub)
            if seed_agents.is_empty() {
                vec![]
            } else {
                // Don't connect to self
                if seed_agents[0].starts_with(&format!("{}:", agent_ip)) {
                    vec![]
                } else {
                    vec![format!("--seed-node={}", seed_agents[0])]
                }
            }
        }
        Topology::Mesh => {
            // Mesh topology: connect to all other agents
            let mut connections = Vec::new();
            for seed in seed_agents.iter() {
                // Don't connect to self
                if !seed.starts_with(&format!("{}:", agent_ip)) {
                    connections.push(format!("--seed-node={}", seed));
                }
            }
            connections
        }
        Topology::Ring => {
            // Ring topology: connect to previous and next agents in ring
            let mut connections = Vec::new();
            if !seed_agents.is_empty() {
                let prev_index = if agent_index == 0 { seed_agents.len() - 1 } else { agent_index - 1 };
                let next_index = if agent_index == seed_agents.len() - 1 { 0 } else { agent_index + 1 };

                if prev_index < seed_agents.len() {
                    let prev_seed = &seed_agents[prev_index];
                    // Don't connect to self
                    if !prev_seed.starts_with(&format!("{}:", agent_ip)) {
                        connections.push(format!("--seed-node={}", prev_seed));
                    }
                }
                if next_index < seed_agents.len() {
                    let next_seed = &seed_agents[next_index];
                    // Don't connect to self
                    if !next_seed.starts_with(&format!("{}:", agent_ip)) {
                        connections.push(format!("--seed-node={}", next_seed));
                    }
                }
            }
            connections
        }
        Topology::Dag => {
            // DAG topology: hierarchical connections (original logic)
            let mut connections = Vec::new();
            for (j, seed) in seed_agents.iter().enumerate() {
                if j < agent_index {
                    // Don't connect to self
                    if !seed.starts_with(&format!("{}:", agent_ip)) {
                        connections.push(format!("--seed-node={}", seed));
                    }
                }
            }
            connections
        }
    }
}

/// Generate peer connections for a specific peer mode
///
/// # Arguments
/// * `peer_mode` - The peer discovery mode (Dynamic, Hardcoded, Hybrid)
/// * `topology` - The network topology (Star, Mesh, Ring, DAG)
/// * `agent_index` - The index of the current agent
/// * `agent_ips` - List of all agent IPs with ports
/// * `agent_ip` - The IP address of the current agent
/// * `seed_nodes` - Optional explicit seed nodes from configuration
/// * `miner_ips` - List of miner IPs
///
/// # Returns
/// A vector of connection strings in the format `--seed-node=IP:PORT`
pub fn generate_peer_connections(
    peer_mode: &crate::config_v2::PeerMode,
    topology: &Topology,
    agent_index: usize,
    agent_ips: &[String], 
    agent_ip: &str,
    seed_nodes: &Option<Vec<String>>,
    miner_ips: &[String],
) -> Vec<String> {
    match peer_mode {
        crate::config_v2::PeerMode::Dynamic => {
            // Dynamic mode: Prioritize miners, use selective connections
            if !miner_ips.is_empty() {
                // If there are miners, connect to them preferentially
                let mut connections = Vec::new();
                for miner in miner_ips {
                    // Don't connect to self
                    if !miner.starts_with(&format!("{}:", agent_ip)) {
                        connections.push(format!("--seed-node={}", miner));
                    }
                }
                connections
            } else {
                // If no miners, use the default topology connections
                generate_topology_connections(topology, agent_index, agent_ips, agent_ip)
            }
        }
        crate::config_v2::PeerMode::Hardcoded => {
            // Hardcoded mode: Use the specified topology template
            if let Some(nodes) = seed_nodes {
                if !nodes.is_empty() {
                    // Use explicit seed nodes from config if provided
                    nodes.iter()
                        .filter(|&seed| !seed.starts_with(&format!("{}:", agent_ip)))
                        .map(|seed| format!("--seed-node={}", seed))
                        .collect()
                } else {
                    // Fall back to topology-based connections if no explicit seeds
                    generate_topology_connections(topology, agent_index, agent_ips, agent_ip)
                }
            } else {
                // Fall back to topology-based connections if no seed_nodes section
                generate_topology_connections(topology, agent_index, agent_ips, agent_ip)
            }
        }
        crate::config_v2::PeerMode::Hybrid => {
            // Hybrid mode: Combine explicit seeds with topology-based connections
            let mut connections = Vec::new();
            
            // Add explicit seed nodes if provided
            if let Some(nodes) = seed_nodes {
                for seed in nodes {
                    if !seed.starts_with(&format!("{}:", agent_ip)) {
                        connections.push(format!("--seed-node={}", seed));
                    }
                }
            }
            
            // Add topology-based connections
            connections.extend(generate_topology_connections(topology, agent_index, agent_ips, agent_ip));
            
            // Remove duplicates
            connections.sort();
            connections.dedup();
            
            connections
        }
    }
}
