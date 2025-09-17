use crate::config_v2::{Config, AgentDefinitions, Network, PeerMode, Topology};
use crate::gml_parser::{self, GmlGraph, GmlNode, validate_topology, get_autonomous_systems};
use serde_json;
use serde_yaml;
use std::collections::HashMap;
use std::path::Path;

#[derive(serde::Serialize, Debug)]
struct MinerInfo {
    agent_id: String,
    ip_addr: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    wallet_address: Option<String>,
    weight: u32,
}

#[derive(serde::Serialize, Debug)]
struct MinerRegistry {
    miners: Vec<MinerInfo>,
}

#[derive(serde::Serialize, Debug)]
struct AgentInfo {
    id: String,
    ip_addr: String,
    daemon: bool,
    wallet: bool,
    user_script: Option<String>,
    attributes: HashMap<String, String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    wallet_rpc_port: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    daemon_rpc_port: Option<u16>,
}

#[derive(serde::Serialize, Debug)]
struct AgentRegistry {
    agents: Vec<AgentInfo>,
}

// Helper function to find agents by role
fn find_agent_by_role<'a>(agents: &'a [AgentInfo], role: &str) -> Option<&'a AgentInfo> {
    agents.iter().find(|a| a.attributes.get("role") == Some(&role.to_string()))
}


#[derive(serde::Serialize, Debug)]
struct ShadowConfig {
    general: ShadowGeneral,
    network: ShadowNetwork,
    experimental: ShadowExperimental,
    hosts: HashMap<String, ShadowHost>,
}

#[derive(serde::Serialize, Debug)]
struct ShadowGeneral {
    stop_time: String,
    model_unblocked_syscall_latency: bool,
    log_level: String,
}

#[derive(serde::Serialize, Debug)]
struct ShadowExperimental {
    #[serde(skip_serializing_if = "Option::is_none")]
    runahead: Option<String>,
    use_dynamic_runahead: bool,
}

#[derive(serde::Serialize, Debug)]
struct ShadowNetwork {
    graph: ShadowGraph,
}

#[derive(serde::Serialize, Debug)]
struct ShadowGraph {
    #[serde(rename = "type")]
    graph_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    file: Option<ShadowFileSource>,
    #[serde(skip_serializing_if = "Option::is_none")]
    nodes: Option<Vec<ShadowNetworkNode>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    edges: Option<Vec<ShadowNetworkEdge>>,
}

#[derive(serde::Serialize, Debug)]
struct ShadowFileSource {
    path: String,
}

#[derive(serde::Serialize, Debug)]
struct ShadowNetworkNode {
    id: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    bandwidth_down: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    bandwidth_up: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    packet_loss: Option<String>,
}

#[derive(serde::Serialize, Debug)]
struct ShadowNetworkEdge {
    source: u32,
    target: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    latency: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    bandwidth: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    packet_loss: Option<String>,
}

#[derive(serde::Serialize, Debug)]
struct ShadowHost {
    network_node_id: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    ip_addr: Option<String>,
    processes: Vec<ShadowProcess>,
    #[serde(skip_serializing_if = "Option::is_none")]
    bandwidth_down: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    bandwidth_up: Option<String>,
}

#[derive(serde::Serialize, Debug)]
struct ShadowProcess {
    path: String,
    args: String,
    environment: HashMap<String, String>,
    start_time: String,
}

/// Generate a random start time between 1 and 180 seconds
fn generate_random_start_time() -> String {
    use rand::Rng;
    let mut rng = rand::thread_rng();
    let random_seconds = rng.gen_range(1..=180);
    format!("{}s", random_seconds)
}

/// Get AS number from a GML node
fn get_node_as_number(gml_node: &GmlNode) -> Option<String> {
    gml_node.attributes.get("AS").or_else(|| gml_node.attributes.get("as")).cloned()
}

/// Generate peer connections based on topology template
fn generate_topology_connections(
    topology: &Topology,
    agent_index: usize,
    total_agents: usize,
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
                    vec![format!("--add-exclusive-node={}", seed_agents[0])]
                }
            }
        }
        Topology::Mesh => {
            // Mesh topology: connect to all other agents
            let mut connections = Vec::new();
            for seed in seed_agents.iter() {
                // Don't connect to self
                if !seed.starts_with(&format!("{}:", agent_ip)) {
                    connections.push(format!("--add-exclusive-node={}", seed));
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
                        connections.push(format!("--add-exclusive-node={}", prev_seed));
                    }
                }
                if next_index < seed_agents.len() {
                    let next_seed = &seed_agents[next_index];
                    // Don't connect to self
                    if !next_seed.starts_with(&format!("{}:", agent_ip)) {
                        connections.push(format!("--add-exclusive-node={}", next_seed));
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
                        connections.push(format!("--add-exclusive-node={}", seed));
                    }
                }
            }
            connections
        }
    }
}


/// Validate topology configuration
fn validate_topology_config(topology: &Topology, total_agents: usize) -> Result<(), String> {
    match topology {
        Topology::Mesh => {
            // Mesh topology requires reasonable number of agents
            if total_agents > 50 {
                return Err("Mesh topology not recommended for networks with more than 50 agents due to connection overhead".to_string());
            }
        }
        Topology::Ring => {
            // Ring topology requires at least 3 agents for meaningful connections
            if total_agents < 3 {
                return Err("Ring topology requires at least 3 agents".to_string());
            }
        }
        Topology::Star => {
            // Star topology requires at least 2 agents
            if total_agents < 2 {
                return Err("Star topology requires at least 2 agents".to_string());
            }
        }
        Topology::Dag => {
            // DAG is always valid
        }
    }
    Ok(())
}

/// Global IP Registry for centralized IP management across all agent types
#[derive(Debug)]
pub struct GlobalIpRegistry {
    /// Tracks all assigned IP addresses to prevent collisions
    assigned_ips: HashMap<String, String>, // IP -> Agent ID
    /// Subnet allocation for different agent types with adequate spacing
    subnet_allocations: HashMap<AgentType, SubnetAllocation>,
    /// Next available IP counters for each subnet
    subnet_counters: HashMap<String, u8>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum AgentType {
    UserAgent,
    BlockController,
    PureScriptAgent,
}

#[derive(Debug)]
pub struct SubnetAllocation {
    pub base_subnet: String,
    pub start_ip: u8,
    pub end_ip: u8,
    pub spacing: u8, // Minimum spacing between agent types
}

impl GlobalIpRegistry {
    pub fn new() -> Self {
        let mut subnet_allocations = HashMap::new();
        let mut subnet_counters = HashMap::new();

        // Unique IP assignment for each agent to simulate true global distribution
        // Each agent gets a unique IP from different subnets
        subnet_allocations.insert(AgentType::UserAgent, SubnetAllocation {
            base_subnet: "192.168".to_string(), // Base for all user agents
            start_ip: 10,
            end_ip: 254, // Allow full range for unique IPs
            spacing: 0,
        });

        subnet_allocations.insert(AgentType::BlockController, SubnetAllocation {
            base_subnet: "192.168".to_string(), // Same base but different subnet logic
            start_ip: 10,
            end_ip: 254,
            spacing: 0,
        });

        subnet_allocations.insert(AgentType::PureScriptAgent, SubnetAllocation {
            base_subnet: "192.168".to_string(), // Same base but different subnet logic
            start_ip: 10,
            end_ip: 254,
            spacing: 0,
        });

        // Initialize counters
        for allocation in subnet_allocations.values() {
            subnet_counters.insert(allocation.base_subnet.clone(), allocation.start_ip);
        }

        GlobalIpRegistry {
            assigned_ips: HashMap::new(),
            subnet_allocations,
            subnet_counters,
        }
    }

    /// Assign a unique IP address for the given agent type and ID
    /// Distributes agents across different IP ranges to simulate global internet distribution
    pub fn assign_ip(&mut self, agent_type: AgentType, agent_id: &str) -> Result<String, String> {
        // Extract numeric part from agent_id (e.g., "user005" -> 5)
        let agent_number = if let Some(num_str) = agent_id.strip_prefix("user") {
            num_str.parse::<u32>().unwrap_or(0)
        } else if let Some(num_str) = agent_id.strip_prefix("script") {
            100 + num_str.parse::<u32>().unwrap_or(0) // Offset script agents
        } else {
            // For blockcontroller and other special cases
            match agent_id {
                "blockcontroller" => 200,
                _ => 0,
            }
        };

        // Global IP distribution - simulate different geographic regions
        // North America: 10.x.x.x, 192.168.x.x
        // Europe: 172.16-31.x.x
        // Asia: 203.x.x.x, 210.x.x.x
        // South America: 200.x.x.x
        // Africa: 197.x.x.x
        // Oceania: 202.x.x.x

        let (octet1, octet2, region_name) = match agent_number % 6 {
            0 => (10, (agent_number / 6) % 256, "North America"),     // 10.x.x.x
            1 => (172, 16 + (agent_number / 6) % 16, "Europe"),       // 172.16-31.x.x
            2 => (203, (agent_number / 6) % 256, "Asia"),             // 203.x.x.x
            3 => (200, (agent_number / 6) % 256, "South America"),    // 200.x.x.x
            4 => (197, (agent_number / 6) % 256, "Africa"),           // 197.x.x.x
            5 => (202, (agent_number / 6) % 256, "Oceania"),          // 202.x.x.x
            _ => (10, 0, "Default"),
        };

        // For North America, also use 192.168.x.x range occasionally
        let (final_octet1, final_octet2) = if octet1 == 10 && (agent_number % 12) == 0 {
            (192, 168) // Occasionally use 192.168.x.x for North America
        } else {
            (octet1, octet2)
        };

        // Create unique subnet and host
        let subnet_octet3 = agent_number % 256;
        let host_octet4 = 10 + (agent_number / 256) % 246; // Keep host part in valid range

        let ip = format!("{}.{}.{}.{}", final_octet1, final_octet2, subnet_octet3, host_octet4);

        // Check if this IP is already assigned
        if !self.assigned_ips.contains_key(&ip) {
            self.assigned_ips.insert(ip.clone(), agent_id.to_string());
            Ok(ip)
        } else {
            // Check if it's assigned to the same agent
            if self.assigned_ips.get(&ip) == Some(&agent_id.to_string()) {
                Ok(ip)
            } else {
                // Fallback: try a different host IP
                let fallback_ip = format!("{}.{}.{}.{}", final_octet1, final_octet2, subnet_octet3, host_octet4 + 100);
                if !self.assigned_ips.contains_key(&fallback_ip) {
                    self.assigned_ips.insert(fallback_ip.clone(), agent_id.to_string());
                    Ok(fallback_ip)
                } else {
                    Err(format!("Could not assign unique IP for agent {}", agent_id))
                }
            }
        }
    }

    /// Check if an IP is already assigned
    pub fn is_ip_assigned(&self, ip: &str) -> bool {
        self.assigned_ips.contains_key(ip)
    }

    /// Get the agent ID that owns a given IP
    pub fn get_agent_for_ip(&self, ip: &str) -> Option<&String> {
        self.assigned_ips.get(ip)
    }

    /// Get all assigned IPs for debugging
    pub fn get_all_assigned_ips(&self) -> &HashMap<String, String> {
        &self.assigned_ips
    }

    /// Get statistics about IP allocation
    pub fn get_allocation_stats(&self) -> HashMap<String, usize> {
        let mut stats = HashMap::new();
        for (subnet, _) in &self.subnet_counters {
            let count = self.assigned_ips.keys()
                .filter(|ip| ip.starts_with(&format!("{}.", subnet)))
                .count();
            stats.insert(subnet.clone(), count);
        }
        stats
    }
}

/// Legacy AS-aware subnet manager for backward compatibility with GML topologies
#[derive(Debug)]
pub struct AsSubnetManager {
    subnet_counters: HashMap<String, u8>,
}

impl AsSubnetManager {
    pub fn new() -> Self {
        let mut subnet_counters = HashMap::new();
        subnet_counters.insert("65001".to_string(), 100); // Start from 192.168.100.x for AS 65001
        subnet_counters.insert("65002".to_string(), 100); // Start from 192.168.101.x for AS 65002
        subnet_counters.insert("65003".to_string(), 100); // Start from 192.168.102.x for AS 65003
        AsSubnetManager { subnet_counters }
    }

    /// Get the subnet base for an AS number
    pub fn get_subnet_base(as_number: &str) -> Option<&'static str> {
        match as_number {
            "65001" => Some("192.168.100"),
            "65002" => Some("192.168.101"),
            "65003" => Some("192.168.102"),
            _ => None,
        }
    }

    /// Assign IP address based on AS number
    pub fn assign_as_aware_ip(&mut self, as_number: &str) -> Option<String> {
        if let Some(subnet_base) = Self::get_subnet_base(as_number) {
            let counter = self.subnet_counters.get_mut(as_number)?;
            // Check if we've exhausted the subnet (255 is the max for IPv4 last octet)
            if *counter >= 255 {
                return None; // Subnet exhausted
            }
            let ip = format!("{}.{}", subnet_base, counter);
            *counter = counter.checked_add(1).unwrap_or(255); // Use checked_add to prevent overflow
            Some(ip)
        } else {
            None
        }
    }
}

/// Get IP address for an agent using the centralized Global IP Registry
pub fn get_agent_ip(
    agent_type: AgentType,
    agent_id: &str,
    agent_index: usize,
    network_node_id: u32,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
) -> String {
    // For GML topologies with AS information, try AS-aware assignment first
    if using_gml_topology {
        if let Some(gml) = gml_graph {
            // Find the GML node with the matching network_node_id
            if let Some(gml_node) = gml.nodes.iter().find(|node| node.id == network_node_id) {
                // First, check if the GML node already has an IP address assigned
                if let Some(existing_ip) = gml_node.get_ip() {
                    // Check if this IP conflicts with our registry
                    if !ip_registry.is_ip_assigned(&existing_ip) {
                        // Register this IP in our central registry
                        ip_registry.assigned_ips.insert(existing_ip.clone(), agent_id.to_string());
                        return existing_ip;
                    }
                }

                // Try AS-aware assignment using the legacy AS subnet manager
                if let Some(as_number) = get_node_as_number(gml_node) {
                    if let Some(as_ip) = subnet_manager.assign_as_aware_ip(&as_number) {
                        // Check if this AS IP conflicts with our registry
                        if !ip_registry.is_ip_assigned(&as_ip) {
                            // Register this IP in our central registry
                            ip_registry.assigned_ips.insert(as_ip.clone(), agent_id.to_string());
                            return as_ip;
                        }
                    }
                }
            }
        }
    }

    // Use the centralized IP registry for assignment
    match ip_registry.assign_ip(agent_type, agent_id) {
        Ok(ip) => ip,
        Err(error) => {
            // Fallback to legacy assignment if centralized registry fails
            eprintln!("Warning: IP registry assignment failed for {}: {}. Using fallback.", agent_id, error);

            // Fallback logic using geographic subnets
            let fallback_ip = match agent_type {
                AgentType::UserAgent => format!("192.168.10.{}", 10 + agent_index),
                AgentType::BlockController => format!("192.168.20.{}", 10 + agent_index),
                AgentType::PureScriptAgent => format!("192.168.30.{}", 10 + agent_index),
            };

            // Try to register the fallback IP
            if !ip_registry.is_ip_assigned(&fallback_ip) {
                ip_registry.assigned_ips.insert(fallback_ip.clone(), agent_id.to_string());
            }

            fallback_ip
        }
    }
}


/// Generate Shadow network configuration from GML graph
fn generate_gml_network_config(gml_graph: &GmlGraph, gml_path: &str) -> color_eyre::eyre::Result<ShadowGraph> {
    // Validate the topology first
    validate_topology(gml_graph).map_err(|e| color_eyre::eyre::eyre!("Invalid GML topology: {}", e))?;

    // Create a temporary GML file with converted attributes (e.g., packet_loss percentages to floats)
    let temp_gml_path = format!("/tmp/monerosim_gml_{}.gml", std::process::id());

    let mut gml_content = String::new();
    gml_content.push_str("graph [\n");

    // Add graph attributes
    for (key, value) in &gml_graph.attributes {
        gml_content.push_str(&format!("  {} {}\n", key, value));
    }

    // Add nodes
    for node in &gml_graph.nodes {
        gml_content.push_str("  node [\n");
        gml_content.push_str(&format!("    id {}\n", node.id));
        if let Some(label) = &node.label {
            gml_content.push_str(&format!("    label \"{}\"\n", label));
        }
        for (key, value) in &node.attributes {
            let processed_value = if key == "bandwidth" {
                if value.ends_with("Gbit") {
                    // Convert Gbit to Mbit
                    if let Ok(gbit) = value.trim_end_matches("Gbit").parse::<f64>() {
                        format!("{}", gbit * 1000.0)
                    } else {
                        value.clone()
                    }
                } else if value.ends_with("Mbit") {
                    // Remove "Mbit" suffix
                    value.trim_end_matches("Mbit").to_string()
                } else {
                    value.clone()
                }
            } else {
                value.clone()
            };
            gml_content.push_str(&format!("    {} {}\n", key, processed_value));
        }
        gml_content.push_str("  ]\n");
    }

    // Add edges with converted attributes
    for edge in &gml_graph.edges {
        gml_content.push_str("  edge [\n");
        gml_content.push_str(&format!("    source {}\n", edge.source));
        gml_content.push_str(&format!("    target {}\n", edge.target));
        for (key, value) in &edge.attributes {
            let (processed_value, quote) = if key == "packet_loss" || key == "bandwidth" {
                // These are numeric values, no quotes
                let processed = if key == "bandwidth" {
                    if value.ends_with("Gbit") {
                        // Convert Gbit to Mbit
                        if let Ok(gbit) = value.trim_end_matches("Gbit").parse::<f64>() {
                            format!("{}", gbit * 1000.0)
                        } else {
                            value.clone()
                        }
                    } else if value.ends_with("Mbit") {
                        // Remove "Mbit" suffix
                        value.trim_end_matches("Mbit").to_string()
                    } else {
                        value.clone()
                    }
                } else {
                    value.clone()
                };
                (processed, false)
            } else {
                // Keep latency as string with unit, quoted
                (value.clone(), true)
            };
            if quote {
                gml_content.push_str(&format!("    {} \"{}\"\n", key, processed_value));
            } else {
                gml_content.push_str(&format!("    {} {}\n", key, processed_value));
            }
        }
        gml_content.push_str("  ]\n");
    }

    gml_content.push_str("]\n");

    // Write the temporary GML file
    std::fs::write(&temp_gml_path, &gml_content)
        .map_err(|e| color_eyre::eyre::eyre!("Failed to write temporary GML file: {}", e))?;

    Ok(ShadowGraph {
        graph_type: "gml".to_string(),
        file: Some(ShadowFileSource {
            path: temp_gml_path,
        }),
        nodes: None,
        edges: None,
    })
}

/// Distribute agents across GML network nodes with guaranteed distribution
/// Ensures every node gets at least one agent when possible to prevent Shadow connectivity errors
pub fn distribute_agents_across_gml_nodes(
    gml_graph: &GmlGraph,
    num_agents: usize,
) -> Vec<u32> {
    if gml_graph.nodes.is_empty() {
        return vec![0; num_agents]; // Fallback to node 0
    }

    let num_nodes = gml_graph.nodes.len();
    let mut agent_assignments = Vec::new();

    // Get autonomous systems for AS-aware distribution
    let as_groups = get_autonomous_systems(gml_graph);

    // First pass: Assign exactly 1 agent to each node (up to min(num_agents, num_nodes))
    let agents_assigned_first_pass = std::cmp::min(num_agents, num_nodes);

    // Create initial assignments ensuring each node gets at least one agent
    for i in 0..agents_assigned_first_pass {
        let node_id = gml_graph.nodes[i].id;
        agent_assignments.push(node_id);
    }

    // Handle case where we have more nodes than agents in first pass
    if num_agents < num_nodes {
        // Some nodes won't get agents - this is acceptable but may cause connectivity issues
        // Fill remaining agent assignments with the first node to maintain vector size
        for _ in num_agents..num_nodes {
            agent_assignments.push(gml_graph.nodes[0].id);
        }
        return agent_assignments;
    }

    // Second pass: Distribute remaining agents proportionally across all nodes
    let remaining_agents = num_agents - agents_assigned_first_pass;

    if remaining_agents > 0 {
        // Distribute remaining agents proportionally
        if as_groups.len() > 1 {
            // AS-aware proportional distribution for remaining agents
            distribute_remaining_agents_as_aware(&mut agent_assignments, &as_groups, remaining_agents, gml_graph);
        } else {
            // Simple proportional distribution across all nodes
            distribute_remaining_agents_simple(&mut agent_assignments, gml_graph, remaining_agents);
        }
    }

    agent_assignments
}

/// Distribute remaining agents proportionally across autonomous systems
fn distribute_remaining_agents_as_aware(
    agent_assignments: &mut Vec<u32>,
    as_groups: &[Vec<u32>],
    remaining_agents: usize,
    gml_graph: &GmlGraph,
) {
    let total_nodes: usize = as_groups.iter().map(|group| group.len()).sum();

    for i in 0..remaining_agents {
        // Find which AS this agent should go to based on proportional distribution
        let mut cumulative_nodes = 0;
        let mut target_as_index = 0;

        for (as_idx, as_group) in as_groups.iter().enumerate() {
            cumulative_nodes += as_group.len();
            if i * total_nodes / remaining_agents < cumulative_nodes {
                target_as_index = as_idx;
                break;
            }
        }

        let as_group = &as_groups[target_as_index];
        // Within the AS, distribute round-robin
        let node_in_as = as_group[i % as_group.len()];
        agent_assignments.push(node_in_as);
    }
}

/// Distribute remaining agents proportionally across all nodes (simple approach)
fn distribute_remaining_agents_simple(
    agent_assignments: &mut Vec<u32>,
    gml_graph: &GmlGraph,
    remaining_agents: usize,
) {
    let num_nodes = gml_graph.nodes.len();

    for i in 0..remaining_agents {
        // Simple proportional distribution across all nodes
        let node_index = i % num_nodes;
        let node_id = gml_graph.nodes[node_index].id;
        agent_assignments.push(node_id);
    }
}


/// Add a Monero daemon process to the processes list
fn add_daemon_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    agent_port: u16,
    agent_rpc_port: u16,
    monerod_path: &str,
    monero_environment: &HashMap<String, String>,
    seed_agents: &[String],
    index: usize,
    peer_mode: &PeerMode,
    topology: Option<&Topology>,
) {
    let mut daemon_args = vec![
        format!("--data-dir=/tmp/monero-{}", agent_id),
        "--log-file=/dev/stdout".to_string(),
        "--log-level=1".to_string(),
        "--simulation".to_string(),
        "--disable-dns-checkpoints".to_string(),
        //"--out-peers=4".to_string(),
        //"--in-peers=4".to_string(),
        // Only disable built-in seed nodes for non-Dynamic modes
        // For Dynamic mode, we allow seed nodes to be used
        if !matches!(peer_mode, PeerMode::Dynamic) {
            "--disable-seed-nodes".to_string()
        } else {
            // For Dynamic mode, don't disable seed nodes - let Monero use them
            "--no-igd".to_string()
        },
        "--prep-blocks-threads=1".to_string(),
        "--max-concurrency=1".to_string(),
        "--no-zmq".to_string(),
        "--db-sync-mode=safe".to_string(),
        "--non-interactive".to_string(),
        "--max-connections-per-ip=50".to_string(),
        "--limit-rate-up=1024".to_string(),
        "--limit-rate-down=1024".to_string(),
        "--block-sync-size=1".to_string(),
        format!("--rpc-bind-ip={}", agent_ip),
        format!("--rpc-bind-port={}", agent_rpc_port),
        "--confirm-external-bind".to_string(),
        "--disable-rpc-ban".to_string(),
        "--rpc-access-control-origins=*".to_string(),
        "--regtest".to_string(),
        format!("--p2p-bind-ip={}", agent_ip),
        format!("--p2p-bind-port={}", agent_port),
        //"--fixed-difficulty=200".to_string(),
        "--allow-local-ip".to_string(),
    ];

    // Add peer connection flags based on peer mode
    match peer_mode {
        PeerMode::Dynamic => {
            // For Dynamic mode, let Monero handle natural P2P discovery
            // Only add seed nodes if explicitly configured
            if !seed_agents.is_empty() {
                for seed_node in seed_agents.iter() {
                    // Don't add self as peer
                    if !seed_node.starts_with(&format!("{}:", agent_ip)) {
                        daemon_args.push(format!("--seed-node={}", seed_node));
                    }
                }
            }
            // No additional peer connection flags - let Monero discover peers naturally
        }
        PeerMode::Hardcoded => {
            // For Hardcoded mode, use explicit peer connections
            if index == 0 {
                // First daemon is the seed node - no peer flags needed
            } else {
                // Non-seed nodes use --add-exclusive-node to connect directly to seed nodes
                for seed_node in seed_agents.iter() {
                    // Don't add self as peer
                    if !seed_node.starts_with(&format!("{}:", agent_ip)) {
                        daemon_args.push(format!("--add-exclusive-node={}", seed_node));
                    }
                }
            }
        }
        PeerMode::Hybrid => {
            // For Hybrid mode, combine seed nodes and explicit peers
            if !seed_agents.is_empty() {
                for seed_node in seed_agents.iter() {
                    // Don't add self as peer
                    if !seed_node.starts_with(&format!("{}:", agent_ip)) {
                        daemon_args.push(format!("--add-exclusive-node={}", seed_node));
                    }
                }
            }
        }
    }

    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c 'rm -rf /tmp/monero-{} && {} {}'",
            agent_id, monerod_path, daemon_args.join(" ")
        ),
        environment: monero_environment.clone(),
        start_time: format!("{}s", 5 + index * 2), // Start daemons first
    });
}

/// Add a wallet process to the processes list
fn add_wallet_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    agent_rpc_port: u16,
    wallet_rpc_port: u16,
    wallet_path: &str,
    environment: &HashMap<String, String>,
    index: usize,
) {
    let wallet_name = format!("{}_wallet", agent_id);
    
    // Create wallet JSON content
    let wallet_json_content = format!(
        r#"{{"version": 1,"filename": "{}","scan_from_height": 0,"password": "","viewkey": "","spendkey": "","seed": "","seed_passphrase": "","address": "","restore_height": 0,"autosave_current": true}}"#,
        wallet_name
    );

    // Get the absolute path to the wallet launcher script
    let launcher_path = std::env::current_dir()
        .unwrap()
        .join("scripts/wallet_launcher.sh")
        .to_string_lossy()
        .to_string();

    // First, clean up any existing wallet files and create the wallet directory
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c 'rm -rf /tmp/monerosim_shared/{}_wallet && mkdir -p /tmp/monerosim_shared/{}_wallet'",
            agent_id, agent_id
        ),
        environment: environment.clone(),
        start_time: format!("{}s", 50 + index * 2), // Start earlier to ensure cleanup completes
    });

    // Launch wallet RPC directly - it will create wallets on demand
    let wallet_path = "/usr/local/bin/monero-wallet-rpc".to_string();
        
    let wallet_args = format!(
        "--daemon-address=http://{}:{} --rpc-bind-port={} --rpc-bind-ip={} --disable-rpc-login --trusted-daemon --log-level=1 --wallet-dir=/tmp/monerosim_shared/{}_wallet --non-interactive --confirm-external-bind --allow-mismatched-daemon-version --max-concurrency=1 --daemon-ssl-allow-any-cert",
        agent_ip, agent_rpc_port, wallet_rpc_port, agent_ip, agent_id
    );
    
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c '{} {}'",
            wallet_path, wallet_args
        ),
        environment: environment.clone(),
        start_time: format!("{}s", 60 + index * 2), // Increased delay to ensure cleanup completes
    });
}

/// Add a user agent process to the processes list
fn add_user_agent_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    agent_rpc_port: u16,
    wallet_rpc_port: u16,
    p2p_port: u16,
    script: &str,
    attributes: Option<&HashMap<String, String>>,
    environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    index: usize,
    stop_time: &str,
) {
    let mut agent_args = vec![
        format!("--id {}", agent_id),
        format!("--shared-dir {}", shared_dir.to_str().unwrap()),
        format!("--rpc-host {}", agent_ip),
        format!("--agent-rpc-port {}", agent_rpc_port),
        format!("--wallet-rpc-port {}", wallet_rpc_port),
        format!("--p2p-port {}", p2p_port),
        format!("--log-level DEBUG"),
        format!("--stop-time {}", stop_time),
    ];

    // Add attributes from config as command-line arguments
    if let Some(attrs) = attributes {
        // Map specific attributes to their correct parameter names
        for (key, value) in attrs {
            if key == "transaction_interval" {
                agent_args.push(format!("--tx-frequency {}", value));
            } else if (key == "min_transaction_amount" || key == "max_transaction_amount" ||
                      key == "can_receive_distributions" || key == "location" || key == "city") ||
                      (key == "is_miner" && value == "true") {
                // These should be passed as attributes, but only pass is_miner if it's true
                agent_args.push(format!("--attributes {} {}", key, value));
            } else if key != "hashrate" && key != "is_miner" {
                // Pass other attributes directly, but filter out hashrate and is_miner (when false)
                agent_args.push(format!("--attributes {} {}", key, value));
            }
        }
    }

    // Remove stop-time from agent args since agents handle their own lifecycle
    agent_args.retain(|arg| !arg.starts_with("--stop-time"));

    // Simplified command without nc dependency - just sleep and retry
    let python_cmd = if script.contains('.') && !script.contains('/') && !script.contains('\\') {
        format!("python3 -m {} {}", script, agent_args.join(" "))
    } else {
        format!("python3 {} {}", script, agent_args.join(" "))
    };

    // Create a simple wrapper script that handles retries internally
    let wrapper_script = format!(
        r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:/usr/local/bin"

# Simple retry loop without nc dependency
for i in {{1..30}}; do
    if curl -s --max-time 1 http://{}:{} >/dev/null 2>&1; then
        echo "Wallet RPC ready, starting agent..."
        {} 2>&1
        exit $?
    fi
    echo "Waiting for wallet RPC... (attempt $i/30)"
    sleep 3
done

echo "Wallet RPC not available after 30 attempts, starting agent anyway..."
{} 2>&1
"#,
        current_dir,
        current_dir,
        agent_ip,
        wallet_rpc_port,
        python_cmd,
        python_cmd
    );

    // Write wrapper script to a temporary file and execute it
    let script_path = format!("/tmp/agent_{}_wrapper.sh", agent_id);
    let script_creation_time = format!("{}s", 64 + index * 2);
    let script_execution_time = format!("{}s", 65 + index * 2);

    // Process 1: Create wrapper script
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!("-c 'cat > {} << \\EOF\n{}\\nEOF'", script_path, wrapper_script),
        environment: environment.clone(),
        start_time: script_creation_time,
    });

    // Process 2: Execute wrapper script
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: script_path.clone(),
        environment: environment.clone(),
        start_time: script_execution_time,
    });
}
/// Process user agents
fn process_user_agents(
    agents: &AgentDefinitions,
    hosts: &mut HashMap<String, ShadowHost>,
    seed_agents: &mut Vec<String>,
    effective_seed_nodes: &[String],
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    monerod_path: &str,
    wallet_path: &str,
    environment: &HashMap<String, String>,
    monero_environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    peer_mode: &PeerMode,
    topology: Option<&Topology>,
) -> color_eyre::eyre::Result<()> {
    // Get agent distribution across GML nodes if available AND we're actually using GML topology
    let agent_node_assignments = if let Some(gml) = gml_graph {
        if let Some(user_agents) = &agents.user_agents {
            if using_gml_topology {
                distribute_agents_across_gml_nodes(gml, user_agents.len())
            } else {
                // If we're not using GML topology (fallback to switch), all agents go to node 0
                vec![0; user_agents.len()]
            }
        } else {
            Vec::new()
        }
    } else {
        Vec::new()
    };

    // First, collect all agent information to build connection graphs
    let mut agent_info = Vec::new();
    let mut miners = Vec::new();
    let mut seed_nodes = Vec::new();
    let mut regular_agents = Vec::new();

    if let Some(user_agents) = &agents.user_agents {
        for (i, user_agent_config) in user_agents.iter().enumerate() {
            let is_miner = user_agent_config.is_miner_value();
            let is_seed_node = user_agent_config.attributes.as_ref()
                .map(|attrs| attrs.get("seed-node").map_or(false, |v| v == "true"))
                .unwrap_or(false);
            // Use consistent naming for all user agents
            let agent_id = format!("user{:03}", i);

            // Determine network node ID for this agent
            let network_node_id = if i < agent_node_assignments.len() {
                agent_node_assignments[i]
            } else {
                0 // Fallback to node 0 for switch-based networks
            };

            let agent_ip = get_agent_ip(AgentType::UserAgent, &agent_id, i, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
            let agent_port = 28080;

            let agent_entry = (i, is_miner, is_seed_node, agent_id, agent_ip.clone(), agent_port);

            if is_miner {
                miners.push(agent_entry);
            } else if is_seed_node {
                seed_nodes.push(agent_entry);
            } else {
                regular_agents.push(agent_entry);
            }

            agent_info.push((i, is_miner, is_seed_node, agent_id, agent_ip, agent_port));
        }
    }

    // Ensure we have exactly 5 seed nodes; if less, promote some regular agents
    while seed_nodes.len() < 5 {
        if let Some((i, _, _, id, ip, port)) = regular_agents.pop() {
            seed_nodes.push((i, false, true, id, ip, port));
        } else {
            // If no more regular agents, promote from miners if needed
            if let Some((i, _, _, id, ip, port)) = miners.pop() {
                seed_nodes.push((i, true, true, id, ip, port));
            }
        }
    }

    // Build seed_agents list for dynamic mode
    for (_, _, _, _, agent_ip, agent_port) in &seed_nodes {
        let seed_addr = format!("{}:{}", agent_ip, agent_port);
        seed_agents.push(seed_addr);
    }

    // Generate fixed connections for initial network bootstrap
    // Miners connect in Ring among themselves
    let mut miner_connections = HashMap::new();
    for (i, (_, _, _, id, ip, _)) in miners.iter().enumerate() {
        let mut connections = Vec::new();
        // Connect to previous and next miner
        let prev = if i == 0 { miners.len() - 1 } else { i - 1 };
        let next = if i == miners.len() - 1 { 0 } else { i + 1 };
        if prev < miners.len() {
            let prev_miner = &miners[prev];
            if prev_miner.4 != *ip { // Don't connect to self
                connections.push(format!("--add-peer={}:{}", prev_miner.4, prev_miner.5));
            }
        }
        if next < miners.len() {
            let next_miner = &miners[next];
            if next_miner.4 != *ip { // Don't connect to self
                connections.push(format!("--add-peer={}:{}", next_miner.4, next_miner.5));
            }
        }
        miner_connections.insert(id.clone(), connections);
    }

    // Seed nodes connect to all miners and to each other in Ring
    let mut seed_connections = HashMap::new();
    for (i, (_, _, _, id, ip, _)) in seed_nodes.iter().enumerate() {
        let mut connections = Vec::new();
        // Connect to all miners
        for (_, _, _, _, m_ip, m_port) in &miners {
            if m_ip != ip {
                connections.push(format!("--add-peer={}:{}", m_ip, m_port));
            }
        }
        // Connect to other seeds in Ring
        let prev = if i == 0 { seed_nodes.len() - 1 } else { i - 1 };
        let next = if i == seed_nodes.len() - 1 { 0 } else { i + 1 };
        if prev < seed_nodes.len() {
            let prev_seed = &seed_nodes[prev];
            if prev_seed.4 != *ip {
                connections.push(format!("--add-peer={}:{}", prev_seed.4, prev_seed.5));
            }
        }
        if next < seed_nodes.len() {
            let next_seed = &seed_nodes[next];
            if next_seed.4 != *ip {
                connections.push(format!("--add-peer={}:{}", next_seed.4, next_seed.5));
            }
        }
        seed_connections.insert(id.clone(), connections);
    }

    // Regular agents will use seed nodes for --seed-node

    // Now process all user agents with staggered start times
    if let Some(user_agents) = &agents.user_agents {
        for (i, user_agent_config) in user_agents.iter().enumerate() {
            // Determine agent type and start time
            let (is_miner, is_seed_node) = user_agent_config.is_miner_value();
            let start_time_daemon = if is_miner {
                format!("{}s", i * 2) // Miners start early, staggered by 2s
            } else if is_seed_node || seed_nodes.iter().any(|(_, _, is_s, _, _, _)| *is_s && agent_info[i].0 == i) {
                "3600s".to_string() // Seeds start at 60 min
            } else {
                // Regular agents start at 65 min + stagger
                let regular_index = regular_agents.iter().position(|(idx, _, _, _, _, _)| *idx == i).unwrap_or(0);
                format!("3900 + {}s", regular_index * 1) // Stagger by 1s
            };

            // Wallet start time: all at 120 min + stagger
            let wallet_start_time = format!("7200 + {}s", i * 1); // Stagger wallets by 1s

            // Use consistent naming for all user agents
            let agent_id = format!("user{:03}", i);

            // Determine network node ID for this agent
            let network_node_id = if i < agent_node_assignments.len() {
                agent_node_assignments[i]
            } else {
                0 // Fallback to node 0 for switch-based networks
            };

            let agent_ip = get_agent_ip(AgentType::UserAgent, &agent_id, i, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
            let agent_port = 28080;

            // Use standard RPC ports for all agents
            let agent_rpc_port = 28081;

            // Use standard wallet RPC port for all agents
            // Since each agent has its own IP address, they can all use the same port
            let wallet_rpc_port = 28082;
            let p2p_port = 28080;

            let mut processes = Vec::new();

            // Add Monero daemon process with appropriate connections
            let mut daemon_args_base = vec![
                format!("--data-dir=/tmp/monero-{}", agent_id),
                "--log-file=/dev/stdout".to_string(),
                "--log-level=1".to_string(),
                "--simulation".to_string(),
                "--disable-dns-checkpoints".to_string(),
                //"--out-peers=4".to_string(),
                //"--in-peers=4".to_string(),
                // Only disable built-in seed nodes for non-Dynamic modes
                // For Dynamic mode, we allow seed nodes to be used
                if !matches!(peer_mode, PeerMode::Dynamic) {
                    "--disable-seed-nodes".to_string()
                } else {
                    // For Dynamic mode, don't disable seed nodes - let Monero use them
                    "--no-igd".to_string()
                },
                "--prep-blocks-threads=1".to_string(),
                "--max-concurrency=1".to_string(),
                "--no-zmq".to_string(),
                "--db-sync-mode=safe".to_string(),
                "--non-interactive".to_string(),
                "--max-connections-per-ip=50".to_string(),
                "--limit-rate-up=1024".to_string(),
                "--limit-rate-down=1024".to_string(),
                "--block-sync-size=1".to_string(),
                format!("--rpc-bind-ip={}", agent_ip),
                format!("--rpc-bind-port={}", agent_rpc_port),
                "--confirm-external-bind".to_string(),
                "--disable-rpc-ban".to_string(),
                "--rpc-access-control-origins=*".to_string(),
                "--regtest".to_string(),
                format!("--p2p-bind-ip={}", agent_ip),
                format!("--p2p-bind-port={}", p2p_port),
                //"--fixed-difficulty=200".to_string(),
                "--allow-local-ip".to_string(),
            ];

            // Add initial fixed connections and seed nodes
            if is_miner {
                // Miners connect to other miners
                if let Some(conns) = miner_connections.get(&agent_id) {
                    for conn in conns {
                        daemon_args_base.push(conn.clone());
                    }
                }
            } else if is_seed_node || seed_nodes.iter().any(|(_, _, is_s, _, _, _)| *is_s && agent_info[i].0 == i) {
                // Seed nodes connect to miners and other seeds
                if let Some(conns) = seed_connections.get(&agent_id) {
                    for conn in conns {
                        daemon_args_base.push(conn.clone());
                    }
                }
            } else {
                // Regular agents use seed nodes
                for seed_addr in seed_agents.iter() {
                    if !seed_addr.starts_with(&format!("{}:", agent_ip)) {
                        daemon_args_base.push(format!("--seed-node={}", seed_addr));
                    }
                }
            }

            // All agents get seed nodes for dynamic discovery
            for seed_addr in seed_agents.iter() {
                if !seed_addr.starts_with(&format!("{}:", agent_ip)) {
                    daemon_args_base.push(format!("--seed-node={}", seed_addr));
                }
            }

            let daemon_args = daemon_args_base.join(" ");

            processes.push(ShadowProcess {
                path: "/bin/bash".to_string(),
                args: format!(
                    "-c 'rm -rf /tmp/monero-{} && {} {}'",
                    agent_id, monerod_path, daemon_args
                ),
                environment: monero_environment.clone(),
                start_time: start_time_daemon,
            });

            // Add wallet process if wallet is specified, but staggered at 120 min
            if user_agent_config.wallet.is_some() {
                add_wallet_process(
                    &mut processes,
                    &agent_id,
                    &agent_ip,
                    agent_rpc_port,
                    wallet_rpc_port,
                    wallet_path,
                    environment,
                    i,
                );

                // Override wallet start time
                if let Some(last_process) = processes.last_mut() {
                    last_process.start_time = wallet_start_time;
                }
            }

            // Add user agent script if specified
            let user_script = user_agent_config.user_script.clone().unwrap_or_else(|| {
                if is_miner {
                    "agents.regular_user".to_string()
                } else {
                    "agents.regular_user".to_string()
                }
            });

            if !user_script.is_empty() {
                add_user_agent_process(
                    &mut processes,
                    &agent_id,
                    &agent_ip,
                    agent_rpc_port,
                    wallet_rpc_port,
                    p2p_port,
                    &user_script,
                    user_agent_config.attributes.as_ref(),
                    environment,
                    shared_dir,
                    current_dir,
                    i,
                    environment.get("stop_time").map(|s| s.as_str()).unwrap_or("1800"),
                );
            }

            // Only add the host if it has any processes
            if !processes.is_empty() {
                // Determine network node ID based on GML assignment or fallback
                let network_node_id = if i < agent_node_assignments.len() {
                    agent_node_assignments[i]
                } else {
                    0 // Fallback to node 0 for switch-based networks
                };
                
                hosts.insert(agent_id.clone(), ShadowHost {
                    network_node_id,
                    ip_addr: Some(agent_ip.clone()),
                    processes,
                    bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
                    bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
                });
                // Note: next_ip is already incremented in get_agent_ip function
            }
        }
    }

    Ok(())
}

/// Process block controller agent
fn process_block_controller(
    agents: &AgentDefinitions,
    hosts: &mut HashMap<String, ShadowHost>,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    stop_time: &str,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    agent_offset: usize,
) -> color_eyre::eyre::Result<()> {
    if let Some(block_controller_config) = &agents.block_controller {
        let block_controller_id = "blockcontroller";
        // Assign block controller to node 0 (which has bandwidth info in GML)
        let network_node_id = 0;
        let block_controller_ip = get_agent_ip(AgentType::BlockController, block_controller_id, agent_offset, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
        let mut processes = Vec::new();

        let mut agent_args = vec![
            format!("--id {}", block_controller_id),
            format!("--shared-dir {}", shared_dir.to_str().unwrap()),
            format!("--log-level DEBUG"),
        ];

        if let Some(args) = &block_controller_config.arguments {
            agent_args.extend(args.iter().cloned());
        }

        // Simplified command for block controller
        let python_cmd = if block_controller_config.script.contains('.') && !block_controller_config.script.contains('/') && !block_controller_config.script.contains('\\') {
            format!("python3 -m {} {}", block_controller_config.script, agent_args.join(" "))
        } else {
            format!("python3 {} {}", block_controller_config.script, agent_args.join(" "))
        };

        // Create a simple wrapper script for block controller
        let wrapper_script = format!(
            r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:/usr/local/bin"

echo "Starting block controller..."
{} 2>&1
"#,
            current_dir,
            current_dir,
            python_cmd
        );

        // Write wrapper script to a temporary file and execute it
        let script_path = format!("/tmp/{}_wrapper.sh", block_controller_id);

        // Process 1: Create wrapper script
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: format!("-c 'cat > {} << \\EOF\n{}\\nEOF'", script_path, wrapper_script),
            environment: environment.clone(),
            start_time: "89s".to_string(), // Create script before execution
        });

        // Process 2: Execute wrapper script
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: script_path.clone(),
            environment: environment.clone(),
            start_time: "90s".to_string(), // Fixed start time for block controller
        });

        hosts.insert(block_controller_id.to_string(), ShadowHost {
            network_node_id, // Use the assigned GML node with bandwidth info
            ip_addr: Some(block_controller_ip),
            processes,
            bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
            bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
        });
        // Note: next_ip is already incremented in get_agent_ip function
    }

    Ok(())
}

/// Process pure script agents
fn process_pure_script_agents(
    agents: &AgentDefinitions,
    hosts: &mut HashMap<String, ShadowHost>,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    stop_time: &str,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    agent_offset: usize,
) -> color_eyre::eyre::Result<()> {
    if let Some(pure_script_agents) = &agents.pure_script_agents {
        for (i, pure_script_config) in pure_script_agents.iter().enumerate() {
            let script_id = format!("script{:03}", i);
            // Assign pure scripts to node 0 (which has bandwidth info in GML)
            let network_node_id = 0;
            let script_ip = get_agent_ip(AgentType::PureScriptAgent, &script_id, agent_offset + i, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
            let mut processes = Vec::new();

            let mut script_args = vec![
                format!("--id {}", script_id),
                format!("--shared-dir {}", shared_dir.to_str().unwrap()),
                format!("--log-level DEBUG"),
            ];

            if let Some(args) = &pure_script_config.arguments {
                script_args.extend(args.iter().cloned());
            }

            // Simplified command for pure script agents
            let python_cmd = format!("python3 {} {}", pure_script_config.script, script_args.join(" "));

            // Create a simple wrapper script for pure script agents
            let wrapper_script = format!(
                r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:/usr/local/bin"

echo "Starting pure script agent {}..."
{} 2>&1
"#,
                current_dir,
                current_dir,
                script_id,
                python_cmd
            );

            // Write wrapper script to a temporary file and execute it
            let script_path = format!("/tmp/{}_wrapper.sh", script_id);
            let script_creation_time = format!("{}s", 29 + i * 5);
            let script_execution_time = format!("{}s", 30 + i * 5);

            // Process 1: Create wrapper script
            processes.push(ShadowProcess {
                path: "/bin/bash".to_string(),
                args: format!("-c 'cat > {} << \\EOF\n{}\\nEOF'", script_path, wrapper_script),
                environment: environment.clone(),
                start_time: script_creation_time,
            });

            // Process 2: Execute wrapper script
            processes.push(ShadowProcess {
                path: "/bin/bash".to_string(),
                args: script_path.clone(),
                environment: environment.clone(),
                start_time: script_execution_time,
            });

            hosts.insert(script_id.clone(), ShadowHost {
                network_node_id, // Use the assigned GML node with bandwidth info
                ip_addr: Some(script_ip),
                processes,
                bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
                bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
            });
            // Note: next_ip is already incremented in get_agent_ip function
        }
    }

    Ok(())
}

/// Generate a Shadow configuration with agent support
pub fn generate_agent_shadow_config(
    config: &Config,
    output_path: &Path,
) -> color_eyre::eyre::Result<()> {
    const SHARED_DIR: &str = "/tmp/monerosim_shared";
    let shared_dir_path = Path::new(SHARED_DIR);

    let current_dir = std::env::current_dir()
        .map_err(|e| color_eyre::eyre::eyre!("Failed to get current directory: {}", e))?
        .to_string_lossy()
        .to_string();

    // Load and validate GML graph if specified
    let gml_graph = if let Some(Network::Gml { path, .. }) = &config.network {
        let graph = gml_parser::parse_gml_file(path)?;
        validate_topology(&graph).map_err(|e| color_eyre::eyre::eyre!("GML validation failed: {}", e))?;
        println!("Loaded GML topology from '{}' with {} nodes and {} edges",
                 path, graph.nodes.len(), graph.edges.len());
        Some(graph)
    } else {
        None
    };

    let mut hosts: HashMap<String, ShadowHost> = HashMap::new();

    // Common environment variables
    let mut environment: HashMap<String, String> = [
        ("MALLOC_MMAP_THRESHOLD_".to_string(), "131072".to_string()),
        ("MALLOC_TRIM_THRESHOLD_".to_string(), "131072".to_string()),
        ("GLIBC_TUNABLES".to_string(), "glibc.malloc.arena_max=1".to_string()),
        ("MALLOC_ARENA_MAX".to_string(), "1".to_string()),
        ("PYTHONUNBUFFERED".to_string(), "1".to_string()), // Ensure Python output is unbuffered
    ].iter().cloned().collect();

    // Add MONEROSIM_LOG_LEVEL if specified in config
    if let Some(log_level) = &config.general.log_level {
        environment.insert("MONEROSIM_LOG_LEVEL".to_string(), log_level.to_uppercase());
    }
    
    // Add stop_time to the environment
    environment.insert("stop_time".to_string(), config.general.stop_time.clone());

    // Monero-specific environment variables
    let mut monero_environment = environment.clone();
    monero_environment.insert("MONERO_BLOCK_SYNC_SIZE".to_string(), "1".to_string());
    monero_environment.insert("MONERO_DISABLE_DNS".to_string(), "1".to_string());
    monero_environment.insert("MONERO_MAX_CONNECTIONS_PER_IP".to_string(), "20".to_string());

    // Create centralized IP registry for robust IP management
    let mut ip_registry = GlobalIpRegistry::new();

    // Create AS-aware subnet manager for GML topology compatibility
    let mut subnet_manager = AsSubnetManager::new();

    // Helper to get absolute path for binaries
    let monerod_path = "/usr/local/bin/monerod".to_string();
    let wallet_path = "/usr/local/bin/monero-wallet-rpc".to_string();

    // Store seed nodes for P2P connections
    let mut seed_nodes: Vec<String> = Vec::new();

    // Determine if we're actually using GML topology based on network configuration
    let using_gml_topology = if let Some(Network::Gml { path: _, .. }) = &config.network {
        true // We're using GML topology
    } else {
        false // We're using switch topology
    };

    // Extract peer mode, seed nodes, and topology from configuration
    let (peer_mode, seed_node_list, topology) = match &config.network {
        Some(Network::Gml { peer_mode, seed_nodes, topology, .. }) => {
            let mode = peer_mode.as_ref().unwrap_or(&PeerMode::Dynamic).clone();
            let seeds = seed_nodes.as_ref().unwrap_or(&Vec::new()).clone();
            let topo = topology.as_ref().unwrap_or(&Topology::Dag).clone();
            (mode, seeds, Some(topo))
        }
        Some(Network::Switch { peer_mode, seed_nodes, topology, .. }) => {
            let mode = peer_mode.as_ref().unwrap_or(&PeerMode::Dynamic).clone();
            let seeds = seed_nodes.as_ref().unwrap_or(&Vec::new()).clone();
            let topo = topology.as_ref().unwrap_or(&Topology::Dag).clone();
            (mode, seeds, Some(topo))
        }
        None => {
            // Default to Dynamic mode with no seed nodes and DAG topology
            (PeerMode::Dynamic, Vec::new(), Some(Topology::Dag))
        }
    };

    // Validate topology configuration
    if let Some(topo) = &topology {
        if let Some(user_agents) = &config.agents.user_agents {
            if let Err(e) = validate_topology_config(topo, user_agents.len()) {
                println!("Warning: Topology validation failed: {}", e);
                // Continue with default DAG topology
            }
        }
    }

    // Use the configured seed nodes (simplified - only first agent is seed)
    let effective_seed_nodes = seed_node_list;

    // Process all agent types from the configuration
    process_user_agents(
        &config.agents,
        &mut hosts,
        &mut seed_nodes,
        &effective_seed_nodes,
        &mut subnet_manager,
        &mut ip_registry,
        &monerod_path,
        &wallet_path,
        &environment,
        &monero_environment,
        shared_dir_path,
        &current_dir,
        gml_graph.as_ref(),
        using_gml_topology,
        &peer_mode,
        topology.as_ref(),
    )?;


    // Calculate offset for block controller and script agents to avoid IP collisions
    // Use a larger offset to ensure clear separation between agent types
    let user_agent_count = config.agents.user_agents.as_ref().map(|ua| ua.len()).unwrap_or(0);
    let block_controller_offset = user_agent_count + 100; // Reserve 100 IPs for user agents
    let script_offset = user_agent_count + 200; // Reserve another 100 IPs for block controller and other uses

    process_block_controller(
        &config.agents,
        &mut hosts,
        &mut subnet_manager,
        &mut ip_registry,
        &environment,
        shared_dir_path,
        &current_dir,
        &config.general.stop_time,
        gml_graph.as_ref(),
        using_gml_topology,
        block_controller_offset,
    )?;

    process_pure_script_agents(
        &config.agents,
        &mut hosts,
        &mut subnet_manager,
        &mut ip_registry,
        &environment,
        shared_dir_path,
        &current_dir,
        &config.general.stop_time,
        gml_graph.as_ref(),
        using_gml_topology,
        script_offset,
    )?;

    // Create agent registry
    let mut agent_registry = AgentRegistry {
        agents: Vec::new(),
    };

    // Populate agent registry from all agent types
    // Extract IPs from the already created hosts instead of generating new ones

    // Add user agents to registry
    if let Some(user_agents) = &config.agents.user_agents {
        for (i, user_agent_config) in user_agents.iter().enumerate() {
            let agent_id = format!("user{:03}", i);

            // Get IP from the corresponding host that was already created
            let agent_ip = hosts.get(&agent_id)
                .and_then(|host| host.ip_addr.clone())
                .unwrap_or_else(|| {
                    // Fallback to geographic IP assignment
                    format!("192.168.10.{}", 10 + i)
                });

            let mut attributes = user_agent_config.attributes.clone().unwrap_or_default();

            // Add computed is_miner attribute to the agent registry
            let is_miner = user_agent_config.is_miner_value();
            attributes.insert("is_miner".to_string(), is_miner.to_string());

            let agent_info = AgentInfo {
                id: agent_id,
                ip_addr: agent_ip,
                daemon: true,
                wallet: user_agent_config.wallet.is_some(),
                user_script: user_agent_config.user_script.clone(),
                attributes,
                wallet_rpc_port: if user_agent_config.wallet.is_some() { Some(28082) } else { None },
                daemon_rpc_port: Some(28081),
            };
            agent_registry.agents.push(agent_info);
        }
    }

    // Add block controller to registry
    if config.agents.block_controller.is_some() {
        let block_controller_id = "blockcontroller".to_string();

        // Get IP from the corresponding host that was already created
        let block_controller_ip = hosts.get(&block_controller_id)
            .and_then(|host| host.ip_addr.clone())
            .unwrap_or_else(|| {
                // Fallback to geographic IP assignment for block controller
                format!("192.168.20.{}", 10 + block_controller_offset)
            });

        let agent_info = AgentInfo {
            id: block_controller_id,
            ip_addr: block_controller_ip,
            daemon: false, // Block controller does not run a daemon
            wallet: false, // Block controller does not have a wallet
            user_script: config.agents.block_controller.as_ref().map(|c| c.script.clone()),
            attributes: HashMap::new(), // No specific attributes for block controller
            wallet_rpc_port: None,
            daemon_rpc_port: None,
        };
        agent_registry.agents.push(agent_info);
    }

    // Add pure script agents to registry
    if let Some(pure_script_agents) = &config.agents.pure_script_agents {
        for (i, pure_script_config) in pure_script_agents.iter().enumerate() {
            let script_id = format!("script{:03}", i);

            // Get IP from the corresponding host that was already created
            let script_ip = hosts.get(&script_id)
                .and_then(|host| host.ip_addr.clone())
                .unwrap_or_else(|| {
                    // Fallback to geographic IP assignment for script agents
                    format!("192.168.30.{}", 10 + i)
                });

            let agent_info = AgentInfo {
                id: script_id,
                ip_addr: script_ip,
                daemon: false, // Pure script agents do not run a daemon
                wallet: false, // Pure script agents do not have a wallet
                user_script: Some(pure_script_config.script.clone()),
                attributes: HashMap::new(), // No specific attributes for pure script agents
                wallet_rpc_port: None,
                daemon_rpc_port: None,
            };
            agent_registry.agents.push(agent_info);
        }
    }

    // Write agent registry to file
    let agent_registry_path = shared_dir_path.join("agent_registry.json");
    let agent_registry_json = serde_json::to_string_pretty(&agent_registry)?;
    std::fs::write(&agent_registry_path, &agent_registry_json)?;

    // Create miner registry
    let mut miner_registry = MinerRegistry {
        miners: Vec::new(),
    };

    // Populate miner registry from user_agents that are miners
    if let Some(user_agents) = &config.agents.user_agents {
        for (i, user_agent_config) in user_agents.iter().enumerate() {
            if user_agent_config.is_miner_value() {
                let agent_id = format!("user{:03}", i);
                // Find the IP address from the already populated agent_registry
                let agent_ip = agent_registry.agents.iter()
                    .find(|a| a.id == agent_id)
                    .map(|a| a.ip_addr.clone())
                    .unwrap_or_else(|| {
                        // Geographic IP assignment for miners
                        format!("192.168.10.{}", 10 + i)
                    }); // Fallback

                // Determine miner weight (hashrate)
                // If no valid hashrate is specified, default to 10 (for even distribution)
                let weight = user_agent_config.attributes
                    .as_ref()
                    .and_then(|attrs| attrs.get("hashrate"))
                    .and_then(|h| h.parse::<u32>().ok())
                    .unwrap_or(10); // Default to 10 instead of 0 for better distribution
                
                let miner_info = MinerInfo {
                    agent_id: agent_id.clone(),
                    ip_addr: agent_ip,
                    wallet_address: None, // Will be populated by the block controller
                    weight,
                };
                miner_registry.miners.push(miner_info);
            }
        }
    }

    // Validate the miner registry before writing
    if miner_registry.miners.is_empty() {
        println!("Warning: No miners were found in the configuration. Mining will not work correctly.");
    } else {
        // Calculate total weight to ensure it's positive
        let total_weight: u32 = miner_registry.miners.iter().map(|m| m.weight).sum();
        if total_weight == 0 {
            println!("Warning: Total mining hashrate weight is zero. Setting default weights of 10 for each miner.");
            // Set default weights if total is zero
            for miner in miner_registry.miners.iter_mut() {
                miner.weight = 10;
            }
        } else {
            println!("Mining weight distribution: {} miners with total weight {}",
                     miner_registry.miners.len(), total_weight);
        }
    }

    // Write miner registry to file
    let miner_registry_path = shared_dir_path.join("miners.json");
    let miner_registry_json = serde_json::to_string_pretty(&miner_registry)?;
    std::fs::write(&miner_registry_path, &miner_registry_json)?;

    // Sort hosts by key to ensure consistent ordering in the output file
    let mut sorted_hosts: Vec<(String, ShadowHost)> = hosts.into_iter().collect();
    sorted_hosts.sort_by(|(a, _), (b, _)| a.cmp(b));
    let sorted_hosts_map: HashMap<String, ShadowHost> = sorted_hosts.into_iter().collect();

    // Create final Shadow configuration
    let shadow_config = ShadowConfig {
        general: ShadowGeneral {
            stop_time: config.general.stop_time.clone(),
            model_unblocked_syscall_latency: true,
            log_level: config.general.log_level.clone().unwrap_or("trace".to_string()),
        },
        experimental: ShadowExperimental {
            runahead: None,
            use_dynamic_runahead: true,
        },
        network: ShadowNetwork {
            graph: match &config.network {
                Some(Network::Gml { path, .. }) => {
                    // Use the loaded and validated GML graph to generate network config
                    if let Some(ref gml) = gml_graph {
                        // Pass both the GML graph and the path to the file
                        generate_gml_network_config(gml, path)?
                    } else {
                        // Fallback to switch if GML loading failed
                        ShadowGraph {
                            graph_type: "1_gbit_switch".to_string(),
                            file: None,
                            nodes: None,
                            edges: None,
                        }
                    }
                },
                Some(Network::Switch { network_type, .. }) => ShadowGraph {
                    graph_type: network_type.clone(),
                    file: None,
                    nodes: None,
                    edges: None,
                },
                None => ShadowGraph {
                    graph_type: "1_gbit_switch".to_string(),
                    file: None,
                    nodes: None,
                    edges: None,
                },
            },
        },
        hosts: sorted_hosts_map,
    };

    // Write configuration
    let config_yaml = serde_yaml::to_string(&shadow_config)?;
    std::fs::write(output_path, config_yaml)?;

    println!("Generated Agent-based Shadow configuration at {:?}", output_path);
    println!("  - Simulation time: {}", config.general.stop_time);
    println!("  - Total hosts: {}", shadow_config.hosts.len());
    
    // Show network topology information
    match &config.network {
        Some(Network::Gml { path, .. }) => {
            if let Some(ref gml) = gml_graph {
                println!("  - Network topology: GML from '{}' ({} nodes, {} edges)",
                         path, gml.nodes.len(), gml.edges.len());

                // Show autonomous systems if available
                let as_groups = get_autonomous_systems(gml);
                if as_groups.len() > 1 {
                    println!("  - Autonomous systems: {} groups", as_groups.len());
                }
            }
        },
        Some(Network::Switch { network_type, .. }) => {
            println!("  - Network topology: Switch ({})", network_type);
        },
        None => {
            println!("  - Network topology: Default switch (1_gbit_switch)");
        }
    }
    
    println!("  - Agent registry created at {:?}", agent_registry_path);
    println!("  - Miner registry created at {:?}", miner_registry_path);

    // Log IP allocation statistics
    let ip_stats = ip_registry.get_allocation_stats();
    println!("  - IP Allocation Summary:");
    for (subnet, count) in ip_stats {
        println!("    - {}: {} IPs assigned", subnet, count);
    }
    println!("  - Total IPs assigned: {}", ip_registry.get_all_assigned_ips().len());

    Ok(())
}
