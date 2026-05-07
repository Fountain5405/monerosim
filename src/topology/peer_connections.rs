//! Peer-topology builders for user agents.
//!
//! Classifies user agents into miners / seed nodes / regular agents,
//! allocates per-agent IPs, and constructs the ring/cross-link
//! `--add-priority-node` connection maps that user-agent processes
//! receive at startup.
//!
//! This is distinct from [`crate::topology::connections`], which builds
//! connection lists for individual agents based on a topology template
//! (Star / Mesh / Ring / DAG); this module operates over the *whole*
//! user-agent set to produce per-agent classification + connection maps
//! consumed by `process_user_agents`.

use crate::config::{AgentConfig, PeerMode};
use crate::gml_parser::GmlGraph;
use crate::ip::{get_agent_ip, AgentType, AsSubnetManager, GlobalIpRegistry};
use std::collections::HashMap;

/// Classification entry for a single user agent during peer-topology
/// construction. Carries enough state to drive ring/cross-link
/// connection maps and later be looked up by index/id from the main
/// emission loop.
pub struct AgentEntry {
    pub index: usize,
    pub is_seed_node: bool,
    pub id: String,
    pub ip: String,
    pub port: u16,
}

/// Output of `build_peer_topology`: classified agent groups, the full
/// IP list, and the precomputed initial-connection maps.
///
/// Ownership: all fields are owned so the result can outlive the
/// borrowed inputs (including `subnet_manager` / `ip_registry`).
pub struct PeerTopology {
    /// All user agents in input order (index matches `user_agents` slice).
    pub agent_info: Vec<AgentEntry>,
    /// Subset of `agent_info`: agents flagged `is_miner`.
    pub miners: Vec<AgentEntry>,
    /// Subset: explicit seed nodes (post-promotion in non-Dynamic modes).
    pub seed_nodes: Vec<AgentEntry>,
    /// Subset: everything else (post-promotion in non-Dynamic modes).
    pub regular_agents: Vec<AgentEntry>,
    /// `IP:PORT` strings for every user agent — fed to topology
    /// generators downstream.
    pub all_agent_ips: Vec<String>,
    /// `agent_id -> [--add-priority-node=…]` for miners.
    pub miner_connections: HashMap<String, Vec<String>>,
    /// `agent_id -> [--add-priority-node=…]` for seed nodes (ring +
    /// cross-link to all miners).
    pub seed_connections: HashMap<String, Vec<String>>,
}

/// Build ring connections among a group of agents.
/// Each agent connects to its predecessor and successor in the ring.
fn build_ring_connections(group: &[AgentEntry], flag: &str) -> HashMap<String, Vec<String>> {
    let mut connections = HashMap::new();
    for (i, entry) in group.iter().enumerate() {
        let mut conns = Vec::new();
        let prev = if i == 0 { group.len() - 1 } else { i - 1 };
        let next = if i == group.len() - 1 { 0 } else { i + 1 };
        if prev < group.len() && group[prev].ip != entry.ip {
            conns.push(format!("{}={}:{}", flag, group[prev].ip, group[prev].port));
        }
        if next < group.len() && group[next].ip != entry.ip {
            conns.push(format!("{}={}:{}", flag, group[next].ip, group[next].port));
        }
        connections.insert(entry.id.clone(), conns);
    }
    connections
}

/// Classify user agents, allocate IPs, promote seed nodes (in
/// Hardcoded/Hybrid modes), and build the initial peer-connection maps.
///
/// Mutates `subnet_manager` / `ip_registry` via `get_agent_ip` and
/// pushes the seed-source IP list onto `seed_agents`.
///
/// # Arguments
/// * `user_agents` - Input agent slice (id, config) in registry order.
/// * `agent_node_assignments` - Pre-computed per-agent network-node IDs.
/// * `peer_mode` - Drives seed-promotion + which group seeds the others.
/// * `gml_graph` - GML topology, if any (used by `get_agent_ip`).
/// * `using_gml_topology` - Whether the GML topology is actually in use.
/// * `subnet_manager` / `ip_registry` - IP allocation state (mutated).
/// * `seed_agents` - Out-parameter receiving `IP:PORT` of seed source.
pub fn build_peer_topology(
    user_agents: &[(&String, &AgentConfig)],
    agent_node_assignments: &[u32],
    peer_mode: &PeerMode,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    seed_agents: &mut Vec<String>,
) -> PeerTopology {
    let mut agent_info: Vec<AgentEntry> = Vec::new();
    let mut all_agent_ips = Vec::new();
    let mut miners: Vec<AgentEntry> = Vec::new();
    let mut seed_nodes: Vec<AgentEntry> = Vec::new();
    let mut regular_agents: Vec<AgentEntry> = Vec::new();

    for (i, (agent_id, agent_config)) in user_agents.iter().enumerate() {
        let is_miner = agent_config.is_miner();
        let is_seed_node = is_miner || agent_config.attributes.as_ref()
            .map(|attrs| attrs.get("is_seed_node").map_or(false, |v| v == "true"))
            .unwrap_or(false);

        let network_node_id = if i < agent_node_assignments.len() {
            agent_node_assignments[i]
        } else {
            0
        };

        let subnet_group = user_agents.iter()
            .find(|(id, _)| id.as_str() == *agent_id)
            .and_then(|(_, config)| config.subnet_group.as_deref());
        let agent_ip = get_agent_ip(AgentType::UserAgent, agent_id, i, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry, subnet_group);
        let agent_port = crate::MONERO_P2P_PORT;

        all_agent_ips.push(format!("{}:{}", agent_ip, agent_port));

        let entry = AgentEntry {
            index: i,
            is_seed_node,
            id: agent_id.to_string(),
            ip: agent_ip.clone(),
            port: agent_port,
        };

        if is_miner {
            miners.push(entry);
        } else if is_seed_node {
            seed_nodes.push(entry);
        } else {
            regular_agents.push(entry);
        }

        agent_info.push(AgentEntry {
            index: i, is_seed_node,
            id: agent_id.to_string(), ip: agent_ip, port: agent_port,
        });
    }

    // Ensure we have exactly 5 seed nodes; if less, promote some regular agents (for Hardcoded/Hybrid modes)
    if !matches!(peer_mode, PeerMode::Dynamic) {
        while seed_nodes.len() < 5 {
            if let Some(mut entry) = regular_agents.pop() {
                entry.is_seed_node = true;
                seed_nodes.push(entry);
            } else if let Some(mut entry) = miners.pop() {
                entry.is_seed_node = true;
                seed_nodes.push(entry);
            } else {
                break;
            }
        }
    }

    // Build seed_agents list from actual miner IPs (Dynamic mode) or promoted seed_nodes
    let seed_source = if matches!(peer_mode, PeerMode::Dynamic) { &miners } else { &seed_nodes };
    for entry in seed_source {
        seed_agents.push(format!("{}:{}", entry.ip, entry.port));
    }

    // Miners connect in Ring among themselves
    let miner_connections = build_ring_connections(&miners, "--add-priority-node");

    // Seed nodes connect to all miners as persistent priority peers, and
    // (in Hardcoded/Hybrid modes) ring-link to each other.
    //
    // We deliberately use --add-priority-node, not --seed-node: a fallback
    // seed IS the bootstrap target for other peers, so it shouldn't be
    // bootstrapping from anyone itself. With --seed-node, monerod connects,
    // exchanges peer list, then disconnects ("pruning seed 0") — the
    // moment its outgoing slot frees up it reconnects, producing a forever
    // before_handshake reconnect loop with that miner.
    let seed_connections = {
        let mut seed_conns = if !matches!(peer_mode, PeerMode::Dynamic) {
            build_ring_connections(&seed_nodes, "--add-priority-node")
        } else {
            HashMap::new()
        };
        for entry in &seed_nodes {
            let conns = seed_conns.entry(entry.id.clone()).or_default();
            for miner in &miners {
                if miner.ip != entry.ip {
                    conns.push(format!("--add-priority-node={}:{}", miner.ip, miner.port));
                }
            }
        }
        seed_conns
    };

    PeerTopology {
        agent_info,
        miners,
        seed_nodes,
        regular_agents,
        all_agent_ips,
        miner_connections,
        seed_connections,
    }
}
