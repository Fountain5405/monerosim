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



#[derive(serde::Serialize, Debug)]
struct ShadowConfig {
    general: ShadowGeneral,
    network: ShadowNetwork,
    experimental: ShadowExperimental,
    hosts: HashMap<String, ShadowHost>,
}

#[derive(serde::Serialize, Debug)]
struct ShadowGeneral {
    stop_time: u64,
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


/// Parse duration string (e.g., "5h", "30m", "1800s") to seconds
fn parse_duration_to_seconds(duration: &str) -> Result<u64, String> {
    let duration = duration.trim();
    if let Ok(seconds) = duration.parse::<u64>() {
        return Ok(seconds);
    }

    if duration.ends_with('s') || duration.ends_with("sec") || duration.ends_with("secs") || duration.ends_with("second") || duration.ends_with("seconds") {
        let num_str = duration.trim_end_matches(|c: char| !c.is_ascii_digit());
        if let Ok(seconds) = num_str.parse::<u64>() {
            return Ok(seconds);
        }
    }

    if duration.ends_with('m') || duration.ends_with("min") || duration.ends_with("mins") || duration.ends_with("minute") || duration.ends_with("minutes") {
        let num_str = duration.trim_end_matches(|c: char| !c.is_ascii_digit());
        if let Ok(minutes) = num_str.parse::<u64>() {
            return Ok(minutes * 60);
        }
    }

    if duration.ends_with('h') || duration.ends_with("hr") || duration.ends_with("hrs") || duration.ends_with("hour") || duration.ends_with("hours") {
        let num_str = duration.trim_end_matches(|c: char| !c.is_ascii_digit());
        if let Ok(hours) = num_str.parse::<u64>() {
            return Ok(hours * 3600);
        }
    }

    Err(format!("Invalid duration format: {}", duration))
}

/// Get AS number from a GML node
fn get_node_as_number(gml_node: &GmlNode) -> Option<String> {
    gml_node.attributes.get("AS").or_else(|| gml_node.attributes.get("as")).cloned()
}

/// Generate peer connections based on topology template
fn generate_topology_connections(
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
    /// Fast lookup for IP uniqueness checking
    used_ips: std::collections::HashSet<String>,
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
        let mut subnet_counters = HashMap::new();

        // Initialize counters for the base subnet
        subnet_counters.insert("192.168".to_string(), 10);

        GlobalIpRegistry {
            assigned_ips: HashMap::new(),
            used_ips: std::collections::HashSet::new(),
            subnet_counters,
        }
    }

    /// Assign a unique IP address for the given agent type and ID
    /// Distributes agents across different IP ranges to simulate global internet distribution
    pub fn assign_ip(&mut self, _agent_type: AgentType, agent_id: &str) -> Result<String, String> {
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

        // Global IP distribution - simulate different geographic regions across multiple /16 subnets
        // North America: 10.x.x.x, 192.168.x.x
        // Europe: 172.16-31.x.x
        // Asia: 203.x.x.x
        // South America: 200.x.x.x
        // Africa: 197.x.x.x
        // Oceania: 202.x.x.x

        let region = agent_number % 6;
        let subnet_offset = agent_number / 6;
        let (octet1, octet2, _region_name) = match region {
            0 => (10, subnet_offset % 256, "North America"),          // 10.x.x.x (/16 subnets)
            1 => (172, 16 + (subnet_offset % 16), "Europe"),          // 172.16-31.x.x (/16 subnets)
            2 => (203, subnet_offset % 256, "Asia"),                  // 203.x.x.x (/16 subnets)
            3 => (200, subnet_offset % 256, "South America"),         // 200.x.x.x (/16 subnets)
            4 => (197, subnet_offset % 256, "Africa"),                // 197.x.x.x (/16 subnets)
            5 => (202, subnet_offset % 256, "Oceania"),               // 202.x.x.x (/16 subnets)
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

        // Check if this IP is already assigned using HashSet for fast lookup
        if !self.used_ips.contains(&ip) {
            self.used_ips.insert(ip.clone());
            self.assigned_ips.insert(ip.clone(), agent_id.to_string());
            Ok(ip)
        } else {
            // Check if it's assigned to the same agent (shouldn't happen with HashSet, but being safe)
            if self.assigned_ips.get(&ip) == Some(&agent_id.to_string()) {
                Ok(ip)
            } else {
                // Fallback: try a different host IP
                let fallback_ip = format!("{}.{}.{}.{}", final_octet1, final_octet2, subnet_octet3, host_octet4 + 100);
                if !self.used_ips.contains(&fallback_ip) {
                    self.used_ips.insert(fallback_ip.clone());
                    self.assigned_ips.insert(fallback_ip.clone(), agent_id.to_string());
                    Ok(fallback_ip)
                } else {
                    Err(format!("Could not assign unique IP for agent {}", agent_id))
                }
            }
        }
    }

    /// Check if an IP is already assigned (fast HashSet lookup)
    pub fn is_ip_assigned(&self, ip: &str) -> bool {
        self.used_ips.contains(ip)
    }

    /// Register a pre-allocated IP from GML file
    pub fn register_pre_allocated_ip(&mut self, ip: &str, agent_id: &str) -> Result<(), String> {
        if self.used_ips.contains(ip) {
            if let Some(existing_agent) = self.assigned_ips.get(ip) {
                if existing_agent != agent_id {
                    return Err(format!("IP {} already assigned to agent {}", ip, existing_agent));
                }
            }
            // If same agent, it's OK
            Ok(())
        } else {
            self.used_ips.insert(ip.to_string());
            self.assigned_ips.insert(ip.to_string(), agent_id.to_string());
            Ok(())
        }
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
/// Priority order: 1) Pre-allocated GML IP, 2) AS-aware IP, 3) Dynamic IP assignment
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
    // For GML topologies, try pre-allocated and AS-aware assignment first
    if using_gml_topology {
        if let Some(gml) = gml_graph {
            // Find the GML node with the matching network_node_id
            if let Some(gml_node) = gml.nodes.iter().find(|node| node.id == network_node_id) {
                // Priority 1: Check for pre-allocated IP from GML node
                if let Some(pre_allocated_ip) = gml_node.get_ip() {
                    // Validate IP format
                    if !GmlNode::is_valid_ip(pre_allocated_ip) {
                        log::warn!("Invalid pre-allocated IP '{}' for node {} in GML file", pre_allocated_ip, network_node_id);
                    } else {
                        // Check for conflicts with existing assignments
                        if let Some(conflicting_agent) = ip_registry.get_agent_for_ip(pre_allocated_ip) {
                            if conflicting_agent != agent_id {
                                log::warn!("IP conflict detected: {} already assigned to agent {}, agent {} (node {}) will use fallback IP",
                                           pre_allocated_ip, conflicting_agent, agent_id, network_node_id);
                                // Continue to fallback instead of panicking
                            } else {
                                log::debug!("Using pre-allocated IP {} for agent {} (node {})", pre_allocated_ip, agent_id, network_node_id);
                                return pre_allocated_ip.to_string();
                            }
                        } else {
                            // Register this IP in our central registry
                            if let Err(conflict) = ip_registry.register_pre_allocated_ip(pre_allocated_ip, agent_id) {
                                log::error!("Failed to register pre-allocated IP {} for agent {}: {}", pre_allocated_ip, agent_id, conflict);
                                // Continue to fallback
                            } else {
                                log::info!("Assigned pre-allocated IP {} to agent {} (node {})", pre_allocated_ip, agent_id, network_node_id);
                                return pre_allocated_ip.to_string();
                            }
                        }
                    }
                }

                // Priority 2: Try AS-aware assignment using the legacy AS subnet manager
                if let Some(as_number) = get_node_as_number(gml_node) {
                    if let Some(as_ip) = subnet_manager.assign_as_aware_ip(&as_number) {
                        // Check if this AS IP conflicts with our registry
                        if let Some(conflicting_agent) = ip_registry.get_agent_for_ip(&as_ip) {
                            if conflicting_agent != agent_id {
                                log::warn!("AS-aware IP {} for agent {} conflicts with existing assignment to {}", as_ip, agent_id, conflicting_agent);
                            } else {
                                log::debug!("Using AS-aware IP {} for agent {} (AS {}, node {})", as_ip, agent_id, as_number, network_node_id);
                                return as_ip;
                            }
                        } else {
                            // Register this IP in our central registry
                            if let Err(conflict) = ip_registry.register_pre_allocated_ip(&as_ip, agent_id) {
                                log::warn!("Failed to register AS-aware IP {} for agent {}: {}", as_ip, agent_id, conflict);
                                // Continue to fallback
                            } else {
                                log::info!("Assigned AS-aware IP {} to agent {} (AS {}, node {})", as_ip, agent_id, as_number, network_node_id);
                                return as_ip;
                            }
                        }
                    }
                }
            } else {
                log::warn!("Agent {} assigned to node {} which doesn't exist in GML topology", agent_id, network_node_id);
            }
        }
    }

    // Priority 3: Use the centralized IP registry for dynamic assignment
    match ip_registry.assign_ip(agent_type, agent_id) {
        Ok(ip) => {
            log::info!("Assigned dynamic IP {} to agent {} using global registry", ip, agent_id);
            ip
        },
        Err(error) => {
            // Fallback to legacy assignment if centralized registry fails
            log::warn!("IP registry assignment failed for {}: {}. Using geographic fallback.", agent_id, error);

            // Fallback logic using geographic subnets
            let fallback_ip = match agent_type {
                AgentType::UserAgent => format!("192.168.10.{}", 10 + agent_index),
                AgentType::BlockController => format!("192.168.20.{}", 10 + agent_index),
                AgentType::PureScriptAgent => format!("192.168.30.{}", 10 + agent_index),
            };

            // Try to register the fallback IP
            if let Some(conflicting_agent) = ip_registry.get_agent_for_ip(&fallback_ip) {
                if conflicting_agent != agent_id {
                    log::error!("Fallback IP {} conflicts with existing assignment to {}", fallback_ip, conflicting_agent);
                }
            } else {
                ip_registry.assigned_ips.insert(fallback_ip.clone(), agent_id.to_string());
            }

            log::info!("Assigned fallback IP {} to agent {}", fallback_ip, agent_id);
            fallback_ip
        }
    }
}


/// Validate GML topology for IP conflicts and inconsistencies
fn validate_gml_ip_consistency(gml_graph: &GmlGraph) -> Result<(), String> {
    use std::collections::HashSet;

    let mut assigned_ips = HashSet::new();
    let mut nodes_with_ips = 0;
    let mut nodes_without_ips = 0;

    for node in &gml_graph.nodes {
        if let Some(ip) = node.get_ip() {
            // Check IP format
            if !GmlNode::is_valid_ip(ip) {
                return Err(format!("Invalid IP address '{}' for node {}", ip, node.id));
            }

            // Check for duplicates
            if !assigned_ips.insert(ip.to_string()) {
                return Err(format!("Duplicate IP address '{}' found in GML file (nodes have conflicting IPs)", ip));
            }

            nodes_with_ips += 1;
        } else {
            nodes_without_ips += 1;
        }
    }

    // Log IP assignment statistics
    let total_nodes = gml_graph.nodes.len();
    if nodes_with_ips > 0 {
        let coverage_percentage = (nodes_with_ips as f64 / total_nodes as f64 * 100.0).round();
        log::info!("GML IP assignment: {} nodes with pre-allocated IPs, {} nodes without ({}% coverage)",
                  nodes_with_ips, nodes_without_ips, coverage_percentage);

        if nodes_without_ips > 0 && nodes_with_ips > 0 {
            log::warn!("Inconsistent IP assignment in GML file: {} nodes have IPs, {} nodes don't. This may cause unpredictable IP assignment behavior.",
                      nodes_with_ips, nodes_without_ips);
        }
    } else {
        log::info!("No pre-allocated IPs in GML file - all IPs will be assigned dynamically");
    }

    Ok(())
}

/// Generate Shadow network configuration from GML graph
fn generate_gml_network_config(gml_graph: &GmlGraph, _gml_path: &str) -> color_eyre::eyre::Result<ShadowGraph> {
    // Validate the topology first
    validate_topology(gml_graph).map_err(|e| color_eyre::eyre::eyre!("Invalid GML topology: {}", e))?;

    // Validate IP consistency
    validate_gml_ip_consistency(gml_graph).map_err(|e| color_eyre::eyre::eyre!("GML IP validation failed: {}", e))?;

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
            let (processed_value, quote) = if key == "bandwidth" {
                // Bandwidth is numeric, no quotes needed
                let processed = if value.ends_with("Gbit") {
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
                };
                (processed, false)
            } else {
                // String attributes like "region" need to be quoted
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
/// Supports sparse placement for large-scale topologies and region-aware distribution
pub fn distribute_agents_across_gml_nodes(
    gml_graph: &GmlGraph,
    num_agents: usize,
) -> Vec<u32> {
    if gml_graph.nodes.is_empty() {
        return vec![0; num_agents]; // Fallback to node 0
    }

    let num_nodes = gml_graph.nodes.len();
    let mut agent_assignments = Vec::new();

    // Check for region information for region-aware distribution
    let has_regions = gml_graph.nodes.iter().any(|node| node.get_region().is_some());

    if num_agents <= num_nodes {
        // Sparse or equal placement: distribute agents across available nodes
        if has_regions {
            // Region-aware sparse distribution
            distribute_agents_region_aware(&mut agent_assignments, gml_graph, num_agents);
        } else {
            // Round-robin sparse distribution for even coverage
            distribute_agents_round_robin(&mut agent_assignments, gml_graph, num_agents);
        }
    } else {
        // Dense placement: more agents than nodes, use original logic
        log::warn!("More agents ({}) than nodes ({}). Some nodes will host multiple agents, which may impact performance.", num_agents, num_nodes);

        // Get autonomous systems for AS-aware distribution
        let as_groups = get_autonomous_systems(gml_graph);

        // First pass: Assign exactly 1 agent to each node
        for node in &gml_graph.nodes {
            agent_assignments.push(node.id);
        }

        // Second pass: Distribute remaining agents proportionally across all nodes
        let remaining_agents = num_agents - num_nodes;

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
    }

    agent_assignments
}

/// Distribute remaining agents proportionally across autonomous systems
fn distribute_remaining_agents_as_aware(
    agent_assignments: &mut Vec<u32>,
    as_groups: &[Vec<u32>],
    remaining_agents: usize,
    _gml_graph: &GmlGraph,
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

/// Distribute agents using round-robin spacing for sparse placement
/// Example: 1000 agents on 5000 nodes -> agents at nodes 0, 5, 10, 15, etc.
fn distribute_agents_round_robin(
    agent_assignments: &mut Vec<u32>,
    gml_graph: &GmlGraph,
    num_agents: usize,
) {
    let num_nodes = gml_graph.nodes.len();

    if num_agents >= num_nodes {
        // Fall back to assigning one agent per node
        for node in &gml_graph.nodes {
            agent_assignments.push(node.id);
        }
        return;
    }

    // Calculate spacing for even distribution
    let spacing = num_nodes as f64 / num_agents as f64;
    let coverage_percentage = (num_agents as f64 / num_nodes as f64 * 100.0).round();

    log::info!("Sparse agent placement: {} agents across {} nodes ({}% coverage) using round-robin distribution",
               num_agents, num_nodes, coverage_percentage);

    for i in 0..num_agents {
        // Calculate node index using spacing
        let node_index = ((i as f64 * spacing).round() as usize).min(num_nodes - 1);
        let node_id = gml_graph.nodes[node_index].id;
        agent_assignments.push(node_id);

        log::debug!("Agent {} assigned to node {}", i, node_id);
    }
}

/// Distribute agents across regions when region information is available
fn distribute_agents_region_aware(
    agent_assignments: &mut Vec<u32>,
    gml_graph: &GmlGraph,
    num_agents: usize,
) {
    use std::collections::HashMap;

    // Group nodes by region
    let mut region_groups: HashMap<String, Vec<usize>> = HashMap::new();
    let mut nodes_without_region = Vec::new();

    for (i, node) in gml_graph.nodes.iter().enumerate() {
        if let Some(region) = node.get_region() {
            region_groups.entry(region.to_string()).or_insert_with(Vec::new).push(i);
        } else {
            nodes_without_region.push(i);
        }
    }

    // Calculate agents per region proportionally, but cap at number of nodes per region
    let total_regional_nodes: usize = region_groups.values().map(|v| v.len()).sum();
    let mut agents_per_region = HashMap::new();

    // First pass: assign 1 agent to each region that has nodes
    let num_regions = region_groups.len();
    let mut remaining_agents = num_agents.saturating_sub(num_regions);

    for (region, nodes) in &region_groups {
        let base_agents = if !nodes.is_empty() { 1 } else { 0 };
        let max_additional = nodes.len().saturating_sub(base_agents);

        // Calculate additional agents proportionally
        let region_percentage = nodes.len() as f64 / total_regional_nodes as f64;
        let additional_agents = (remaining_agents as f64 * region_percentage).round() as usize;
        let capped_additional = additional_agents.min(max_additional);

        let total_for_region = base_agents + capped_additional;
        agents_per_region.insert(region.clone(), total_for_region);
        remaining_agents = remaining_agents.saturating_sub(capped_additional);
    }

    // Distribute any remaining agents to regions that can still take more
    if remaining_agents > 0 {
        let mut regions_by_remaining_capacity: Vec<_> = region_groups.iter()
            .map(|(r, nodes)| {
                let current = agents_per_region.get(r).unwrap_or(&0);
                let remaining_capacity = nodes.len().saturating_sub(*current);
                (r.clone(), remaining_capacity)
            })
            .filter(|(_, capacity)| *capacity > 0)
            .collect();

        regions_by_remaining_capacity.sort_by(|a, b| b.1.cmp(&a.1)); // Sort by capacity descending

        for (region, _) in regions_by_remaining_capacity {
            if remaining_agents == 0 { break; }
            *agents_per_region.get_mut(&region).unwrap() += 1;
            remaining_agents -= 1;
        }
    }

    // Log geographic distribution
    log::info!("Geographic agent distribution:");
    for (region, count) in &agents_per_region {
        let percentage = (*count as f64 / num_agents as f64 * 100.0).round();
        log::info!("  {}: {} agents ({}%)", region, count, percentage);
    }

    // Assign agents to unique nodes, preferring correct region
    let mut used_nodes = std::collections::HashSet::new();
    let mut agent_index = 0;

    // First, assign agents to their preferred regions
    for (region, agent_count) in &agents_per_region.clone() {
        if let Some(node_indices) = region_groups.get(region) {
            let mut assigned_in_region = 0;
            for i in 0..*agent_count {
                if agent_index >= num_agents { break; }

                // Find an unused node in this region
                let mut node_assigned = false;
                for j in 0..node_indices.len() {
                    let node_idx = node_indices[(i + j) % node_indices.len()];
                    let node_id = gml_graph.nodes[node_idx].id;
                    if !used_nodes.contains(&node_id) {
                        agent_assignments.push(node_id);
                        used_nodes.insert(node_id);
                        log::debug!("Agent {} (region {}) assigned to node {}", agent_index, region, node_id);
                        agent_index += 1;
                        assigned_in_region += 1;
                        node_assigned = true;
                        break;
                    }
                }

                if !node_assigned {
                    // No more available nodes in this region
                    break;
                }
            }

            // Update the count for this region
            if let Some(count) = agents_per_region.get_mut(region) {
                *count = assigned_in_region;
            }
        }
    }

    // Handle any remaining agents by assigning to unused nodes from any region
    while agent_index < num_agents {
        // Find any unused node
        let mut assigned = false;
        for (_i, node) in gml_graph.nodes.iter().enumerate() {
            let node_id = node.id;
            if !used_nodes.contains(&node_id) {
                agent_assignments.push(node_id);
                used_nodes.insert(node_id);
                log::debug!("Agent {} assigned to unused node {} (any region)", agent_index, node_id);
                agent_index += 1;
                assigned = true;
                break;
            }
        }

        if !assigned {
            // No more unused nodes, fallback to node 0
            agent_assignments.push(0);
            log::warn!("Agent {} assigned to fallback node 0 (no unused nodes)", agent_index);
            agent_index += 1;
        }
    }
}



/// Add a wallet process to the processes list
fn add_wallet_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    agent_rpc_port: u16,
    wallet_rpc_port: u16,
    _wallet_path: &str,
    environment: &HashMap<String, String>,
    index: usize,
    wallet_start_time: &str,
) {
    let wallet_name = format!("{}_wallet", agent_id);
    
    // Create wallet JSON content
    let _wallet_json_content = format!(
        r#"{{"version": 1,"filename": "{}","scan_from_height": 0,"password": "","viewkey": "","spendkey": "","seed": "","seed_passphrase": "","address": "","restore_height": 0,"autosave_current": true}}"#,
        wallet_name
    );

    // Get the absolute path to the wallet launcher script
    let _launcher_path = std::env::current_dir()
        .unwrap()
        .join("scripts/wallet_launcher.sh")
        .to_string_lossy()
        .to_string();

    // Calculate wallet cleanup start time (2 seconds before wallet start)
    let cleanup_start_time = if let Ok(wallet_seconds) = parse_duration_to_seconds(wallet_start_time) {
        format!("{}s", wallet_seconds.saturating_sub(2))
    } else {
        format!("{}s", 48 + index * 2) // Fallback
    };

    // First, clean up any existing wallet files and create the wallet directory
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c 'rm -rf /tmp/monerosim_shared/{}_wallet && mkdir -p /tmp/monerosim_shared/{}_wallet'",
            agent_id, agent_id
        ),
        environment: environment.clone(),
        start_time: cleanup_start_time, // Start earlier to ensure cleanup completes
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
        start_time: wallet_start_time.to_string(), // Use the calculated wallet start time
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
    custom_start_time: Option<&str>,
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

    // Use custom start time if provided, otherwise use default staggered timing
    let (script_creation_time, script_execution_time) = if let Some(custom_time) = custom_start_time {
        if let Ok(seconds) = parse_duration_to_seconds(custom_time) {
            (format!("{}s", seconds - 1), custom_time.to_string())
        } else {
            // Fallback to default timing if parsing fails
            (format!("{}s", 64 + index * 2), format!("{}s", 65 + index * 2))
        }
    } else {
        (format!("{}s", 64 + index * 2), format!("{}s", 65 + index * 2))
    };

    // Process 1: Create wrapper script
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!("-c 'cat > {} << \\EOF\n{}\\EOF'", script_path, wrapper_script),
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
    let mut all_agent_ips = Vec::new(); // Collect all agent IPs for topology connections
    let mut miners = Vec::new();
    let mut seed_nodes = Vec::new();
    let mut regular_agents = Vec::new();

    if let Some(user_agents) = &agents.user_agents {
        for (i, user_agent_config) in user_agents.iter().enumerate() {
            let is_miner = user_agent_config.is_miner_value();
            let is_seed_node = is_miner || user_agent_config.attributes.as_ref()
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

            // Collect all agent IPs for topology connections
            all_agent_ips.push(format!("{}:{}", agent_ip, agent_port));

            let agent_entry = (i, is_miner, is_seed_node, agent_id.clone(), agent_ip.clone(), agent_port);

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

    // Ensure we have exactly 5 seed nodes; if less, promote some regular agents (for Hardcoded/Hybrid modes)
    if !matches!(peer_mode, PeerMode::Dynamic) {
        while seed_nodes.len() < 5 {
            if let Some((i, _, _, id, ip, port)) = regular_agents.pop() {
                seed_nodes.push((i, false, true, id, ip, port));
            } else {
                // If no more regular agents, promote from miners if needed
                if let Some((i, _, _, id, ip, port)) = miners.pop() {
                    seed_nodes.push((i, true, true, id, ip, port));
                } else {
                    // No more agents to promote
                    break;
                }
            }
        }
    }

    // Build seed_agents list - use effective_seed_nodes for Dynamic mode, seed_nodes for others
    if matches!(peer_mode, PeerMode::Dynamic) {
        seed_agents.extend(effective_seed_nodes.iter().cloned());
    } else {
        for (_, _, _, _, agent_ip, agent_port) in &seed_nodes {
            let seed_addr = format!("{}:{}", agent_ip, agent_port);
            seed_agents.push(seed_addr);
        }
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
                connections.push(format!("--add-priority-node={}:{}", prev_miner.4, prev_miner.5));
            }
        }
        if next < miners.len() {
            let next_miner = &miners[next];
            if next_miner.4 != *ip { // Don't connect to self
                connections.push(format!("--add-priority-node={}:{}", next_miner.4, next_miner.5));
            }
        }
        miner_connections.insert(id.clone(), connections);
    }

    // Seed nodes connect to all miners and to each other in Ring (for Hardcoded/Hybrid modes)
    let seed_connections = if !matches!(peer_mode, PeerMode::Dynamic) {
        let mut seed_connections = HashMap::new();
        for (i, (_, _, _, id, ip, _)) in seed_nodes.iter().enumerate() {
            let mut connections = Vec::new();
            // Connect to all miners using --seed-node
            for (_, _, _, _, m_ip, m_port) in &miners {
                if m_ip != ip {
                    connections.push(format!("--seed-node={}:{}", m_ip, m_port));
                }
            }
            // Connect to other seeds in Ring
            let prev = if i == 0 { seed_nodes.len() - 1 } else { i - 1 };
            let next = if i == seed_nodes.len() - 1 { 0 } else { i + 1 };
            if prev < seed_nodes.len() {
                let prev_seed = &seed_nodes[prev];
                if prev_seed.4 != *ip {
                    connections.push(format!("--add-priority-node={}:{}", prev_seed.4, prev_seed.5));
                }
            }
            if next < seed_nodes.len() {
                let next_seed = &seed_nodes[next];
                if next_seed.4 != *ip {
                    connections.push(format!("--add-priority-node={}:{}", next_seed.4, next_seed.5));
                }
            }
            seed_connections.insert(id.clone(), connections);
        }
        seed_connections
    } else {
        HashMap::new()
    };

    // Regular agents will use seed nodes for --seed-node

    // Now process all user agents with staggered start times
    if let Some(user_agents) = &agents.user_agents {
        for (i, user_agent_config) in user_agents.iter().enumerate() {
            // Determine agent type and start time
            let is_miner = user_agent_config.is_miner_value();
            let is_seed_node = is_miner || user_agent_config.attributes.as_ref()
                .map(|attrs| attrs.get("seed-node").map_or(false, |v| v == "true"))
                .unwrap_or(false);

            let start_time_daemon = if matches!(peer_mode, PeerMode::Dynamic) {
                // Optimized Dynamic mode launch sequence - reduced staggered timing
                if is_miner {
                    if i == 0 {
                        "0s".to_string() // First miner (node 0) at t=0s
                    } else {
                        format!("{}s", 1 + i) // Remaining miners every 1s starting t=1s
                    }
                } else {
                    // Regular users start after miners, with reduced stagger
                    format!("{}s", 5 + (i.saturating_sub(miners.len())))
                }
            } else {
                // Optimized logic for other modes - reduced timing
                if is_miner {
                    format!("{}s", i) // Miners start early, staggered by 1s
                } else if is_seed_node || seed_nodes.iter().any(|(_, _, is_s, _, _, _)| *is_s && agent_info[i].0 == i) {
                    "3s".to_string() // Seeds start at 3s
                } else {
                    // Regular agents start after seeds, with reduced stagger
                    let regular_index = regular_agents.iter().position(|(idx, _, _, _, _, _)| *idx == i).unwrap_or(0);
                    format!("{}s", 6 + regular_index) // Stagger by 1s
                }
            };

            // Wallet start time: coordinate with daemon start time (reduced delay)
            let wallet_start_time = if matches!(peer_mode, PeerMode::Dynamic) {
                // Dynamic mode: start wallet 2 seconds after daemon (reduced from 5s)
                if let Ok(daemon_seconds) = parse_duration_to_seconds(&start_time_daemon) {
                    format!("{}s", daemon_seconds + 2)
                } else {
                    format!("{}s", 2 + i)
                }
            } else {
                // Other modes: start wallet 2 seconds after daemon (reduced from 5s)
                if let Ok(daemon_seconds) = parse_duration_to_seconds(&start_time_daemon) {
                    format!("{}s", daemon_seconds + 2)
                } else {
                    format!("{}s", 2 + i)
                }
            };

            // Agent start time: ensure agents start after their wallet services are ready (reduced delay)
            let agent_start_time = if matches!(peer_mode, PeerMode::Dynamic) {
                // Dynamic mode: start agent 3 seconds after wallet (reduced from 10s)
                if let Ok(wallet_seconds) = parse_duration_to_seconds(&wallet_start_time) {
                    format!("{}s", wallet_seconds + 3)
                } else {
                    format!("{}s", 5 + i)
                }
            } else {
                // Other modes: start agent 3 seconds after wallet (reduced from 10s)
                if let Ok(wallet_seconds) = parse_duration_to_seconds(&wallet_start_time) {
                    format!("{}s", wallet_seconds + 3)
                } else {
                    format!("{}s", 5 + i)
                }
            };

            // Use consistent naming for all user agents
            let agent_id = format!("user{:03}", i);

            // Determine network node ID for this agent
            let network_node_id = if i < agent_node_assignments.len() {
                agent_node_assignments[i]
            } else {
                0 // Fallback to node 0 for switch-based networks
            };

            let agent_ip = get_agent_ip(AgentType::UserAgent, &agent_id, i, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
            let _agent_port = 28080;

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

            // Only disable built-in seed nodes for miners
            if is_miner {
                daemon_args_base.push("--disable-seed-nodes".to_string());
            }

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
                // Regular agents will get peer connections based on peer_mode below
            }

            // For regular agents, add peer connections based on peer mode
            let is_actual_seed_node = seed_nodes.iter().any(|(idx, _, _, _, _, _)| *idx == i);
            if !is_miner && !is_actual_seed_node {
                // Add seed node connections for all modes
                for seed_node in seed_agents.iter() {
                    if !seed_node.starts_with(&format!("{}:", agent_ip)) {
                        let peer_arg = if matches!(peer_mode, PeerMode::Dynamic) {
                            format!("--seed-node={}", seed_node)
                        } else {
                            format!("--add-priority-node={}", seed_node)
                        };
                        daemon_args_base.push(peer_arg);
                    }
                }

                // For Hybrid mode, also add topology-based connections
                if matches!(peer_mode, PeerMode::Hybrid) {
                    if let Some(topo) = topology {
                        let topology_connections = generate_topology_connections(topo, i, &all_agent_ips, &agent_ip);
                        for conn in topology_connections {
                            daemon_args_base.push(conn);
                        }
                    }
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

            // Add wallet process if wallet is specified
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
                    &wallet_start_time,
                );
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
                    Some(&agent_start_time), // Pass the calculated agent start time
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
    _stop_time: &str,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    agent_offset: usize,
    peer_mode: &PeerMode,
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

        // Determine execution start time (optimized)
        let block_controller_start_time = if matches!(peer_mode, PeerMode::Dynamic) {
            "10s".to_string() // Dynamic mode: block controller starts at 10s (reduced from 20s)
        } else {
            "15s".to_string() // Other modes: reduced from 90s
        };

        // Calculate script creation time (1 second before execution)
        let script_creation_time = if let Ok(exec_seconds) = parse_duration_to_seconds(&block_controller_start_time) {
            format!("{}s", exec_seconds.saturating_sub(1))
        } else {
            // Fallback if parsing fails
            "89s".to_string()
        };

        // Process 1: Create wrapper script
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: format!("-c 'cat > {} << \\EOF\n{}\\EOF'", script_path, wrapper_script),
            environment: environment.clone(),
            start_time: script_creation_time,
        });

        // Process 2: Execute wrapper script
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: script_path.clone(),
            environment: environment.clone(),
            start_time: block_controller_start_time,
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

/// Process miner distributor agent
fn process_miner_distributor(
    agents: &AgentDefinitions,
    hosts: &mut HashMap<String, ShadowHost>,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    _stop_time: &str,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    agent_offset: usize,
    peer_mode: &PeerMode,
) -> color_eyre::eyre::Result<()> {
    if let Some(miner_distributor_config) = &agents.miner_distributor {
        let miner_distributor_id = "minerdistributor";
        // Assign miner distributor to node 0 (which has bandwidth info in GML)
        let network_node_id = 0;
        let miner_distributor_ip = get_agent_ip(AgentType::BlockController, miner_distributor_id, agent_offset, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
        let mut processes = Vec::new();

        let mut agent_args = vec![
            format!("--id {}", miner_distributor_id),
            format!("--shared-dir {}", shared_dir.to_str().unwrap()),
            format!("--log-level DEBUG"),
        ];

        // Add attributes from config
        if let Some(attrs) = &miner_distributor_config.attributes {
            for (key, value) in attrs {
                agent_args.push(format!("--attributes {} {}", key, value));
            }
        }

        // Simplified command for miner distributor
        let python_cmd = if miner_distributor_config.script.contains('.') && !miner_distributor_config.script.contains('/') && !miner_distributor_config.script.contains('\\') {
            format!("python3 -m {} {}", miner_distributor_config.script, agent_args.join(" "))
        } else {
            format!("python3 {} {}", miner_distributor_config.script, agent_args.join(" "))
        };

        // Create a simple wrapper script for miner distributor
        let wrapper_script = format!(
            r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:/usr/local/bin"

echo "Starting miner distributor..."
{} 2>&1
"#,
            current_dir,
            current_dir,
            python_cmd
        );

        // Write wrapper script to a temporary file and execute it
        let script_path = format!("/tmp/{}_wrapper.sh", miner_distributor_id);

        // Determine execution start time (keeping original for block maturity)
        let miner_distributor_start_time = if matches!(peer_mode, PeerMode::Dynamic) {
            "3900s".to_string() // Dynamic mode: miner distributor starts at 65 minutes (block reward maturity)
        } else {
            "3900s".to_string() // Other modes: also start at 65 minutes (block reward maturity)
        };

        // Calculate script creation time (1 second before execution)
        let script_creation_time = if let Ok(exec_seconds) = parse_duration_to_seconds(&miner_distributor_start_time) {
            format!("{}s", exec_seconds.saturating_sub(1))
        } else {
            // Fallback if parsing fails
            "89s".to_string()
        };

        // Process 1: Create wrapper script
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: format!("-c 'cat > {} << \\EOF\n{}\\EOF'", script_path, wrapper_script),
            environment: environment.clone(),
            start_time: script_creation_time,
        });

        // Process 2: Execute wrapper script
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: script_path.clone(),
            environment: environment.clone(),
            start_time: miner_distributor_start_time,
        });

        hosts.insert(miner_distributor_id.to_string(), ShadowHost {
            network_node_id, // Use the assigned GML node with bandwidth info
            ip_addr: Some(miner_distributor_ip),
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
    _stop_time: &str,
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
            let script_creation_time = format!("{}s", 5 + i * 2);
            let script_execution_time = format!("{}s", 6 + i * 2);

            // Process 1: Create wrapper script
            processes.push(ShadowProcess {
                path: "/bin/bash".to_string(),
                args: format!("-c 'cat > {} << \\EOF\n{}\\EOF'", script_path, wrapper_script),
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

    // Use the configured seed nodes, or collect miner IPs if not provided
    let effective_seed_nodes = if seed_node_list.is_empty() {
        // Collect actual miner IPs for seed nodes
        let mut miner_ips = Vec::new();
        if let Some(user_agents) = &config.agents.user_agents {
            for (i, user_agent_config) in user_agents.iter().enumerate() {
                if user_agent_config.is_miner_value() {
                    let agent_id = format!("user{:03}", i);
                    // For seed node IP calculation, use node 0 (switch topology assumption)
                    // This ensures consistent IP assignment for miners
                    let network_node_id = 0;
                    let agent_ip = get_agent_ip(AgentType::UserAgent, &agent_id, i, network_node_id, gml_graph.as_ref(), using_gml_topology, &mut subnet_manager, &mut ip_registry);
                    miner_ips.push(format!("{}:28080", agent_ip));
                }
            }
        }
        println!("Using {} miner IPs as seed nodes: {:?}", miner_ips.len(), miner_ips);
        miner_ips
    } else {
        println!("Using configured seed nodes: {:?}", seed_node_list);
        seed_node_list
    };

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
        &peer_mode,
    )?;

    process_miner_distributor(
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
        block_controller_offset + 10, // Offset from block controller
        &peer_mode,
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

    // Add miner distributor to registry
    if config.agents.miner_distributor.is_some() {
        let miner_distributor_id = "minerdistributor".to_string();

        // Get IP from the corresponding host that was already created
        let miner_distributor_ip = hosts.get(&miner_distributor_id)
            .and_then(|host| host.ip_addr.clone())
            .unwrap_or_else(|| {
                // Fallback to geographic IP assignment for miner distributor
                format!("192.168.21.{}", 10 + block_controller_offset)
            });

        let agent_info = AgentInfo {
            id: miner_distributor_id,
            ip_addr: miner_distributor_ip,
            daemon: false, // Miner distributor does not run a daemon
            wallet: false, // Miner distributor does not have a wallet
            user_script: config.agents.miner_distributor.as_ref().map(|c| c.script.clone()),
            attributes: config.agents.miner_distributor.as_ref()
                .and_then(|c| c.attributes.clone())
                .unwrap_or_default(),
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

    // For GML topologies, ensure all nodes in the GML file have corresponding hosts in Shadow
    // This is required because Shadow expects a 1:1 mapping between GML nodes and hosts
    if let Some(gml) = &gml_graph {
        if using_gml_topology {
            for node in &gml.nodes {
                let dummy_host_name = format!("gml-node-{}", node.id);
                if !hosts.contains_key(&dummy_host_name) {
                    // Create a dummy host for this GML node with no processes
                    let dummy_host = ShadowHost {
                        network_node_id: node.id,
                        ip_addr: None, // No IP needed for dummy hosts
                        processes: Vec::new(), // No processes to run
                        bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
                        bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
                    };
                    hosts.insert(dummy_host_name, dummy_host);
                    log::debug!("Created dummy host for GML node {}", node.id);
                }
            }
        }
    }

    // Sort hosts by key to ensure consistent ordering in the output file
    let mut sorted_hosts: Vec<(String, ShadowHost)> = hosts.into_iter().collect();
    sorted_hosts.sort_by(|(a, _), (b, _)| a.cmp(b));
    let sorted_hosts_map: HashMap<String, ShadowHost> = sorted_hosts.into_iter().collect();

    // Parse stop_time to seconds
    let stop_time_seconds = parse_duration_to_seconds(&config.general.stop_time)
        .map_err(|e| color_eyre::eyre::eyre!("Failed to parse stop_time '{}': {}", config.general.stop_time, e))?;

    // Create final Shadow configuration
    let shadow_config = ShadowConfig {
        general: ShadowGeneral {
            stop_time: stop_time_seconds,
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
