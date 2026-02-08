//! Configuration validation utilities.
//!
//! This module provides validation functions for configuration
//! parameters and consistency checks.

use crate::gml_parser::{GmlGraph, GmlNode};
use crate::config_v2::{Topology, AgentConfig};
use std::collections::BTreeMap;

/// Validate GML topology for IP conflicts and inconsistencies
///
/// Checks for:
/// - Valid IP address formats
/// - Duplicate IP addresses
/// - Inconsistent IP assignment (some nodes have IPs, others don't)
///
/// # Arguments
/// * `gml_graph` - The GML graph to validate
///
/// # Returns
/// * `Ok(())` if validation succeeds
/// * `Err(String)` with an error message if validation fails
///
/// # Examples
/// ```
/// use monerosim::utils::validation::validate_gml_ip_consistency;
/// use monerosim::gml_parser::{GmlGraph, GmlNode};
/// use std::collections::HashMap;
///
/// let mut graph = GmlGraph {
///     nodes: Vec::new(),
///     edges: Vec::new(),
///     attributes: HashMap::new(),
/// };
/// // Add nodes and edges...
/// assert!(validate_gml_ip_consistency(&graph).is_ok());
/// ```
pub fn validate_gml_ip_consistency(gml_graph: &GmlGraph) -> Result<(), String> {
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

/// Validate topology configuration
///
/// Checks if the topology is compatible with the number of agents:
/// - Mesh topology: Not recommended for more than 50 agents
/// - Ring topology: Requires at least 3 agents
/// - Star topology: Requires at least 2 agents
/// - DAG topology: Always valid
///
/// # Arguments
/// * `topology` - The topology to validate
/// * `total_agents` - The total number of agents
///
/// # Returns
/// * `Ok(())` if validation succeeds
/// * `Err(String)` with an error message if validation fails
///
/// # Examples
/// ```
/// use monerosim::utils::validation::validate_topology_config;
/// use monerosim::config_v2::Topology;
///
/// assert!(validate_topology_config(&Topology::Mesh, 10).is_ok());
/// assert!(validate_topology_config(&Topology::Ring, 2).is_err()); // Ring needs at least 3 agents
/// assert!(validate_topology_config(&Topology::Star, 1).is_err()); // Star needs at least 2 agents
/// ```
pub fn validate_topology_config(topology: &Topology, total_agents: usize) -> Result<(), String> {
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

/// Validate mining configuration
///
/// Checks mining agent configuration for:
/// - Mining agents have wallet field (required for reward address)
/// - Mining agents have hashrate field (percentage of network hashrate)
/// - Hashrate values are valid (0-100)
/// - Total hashrate equals 100% (warning if not)
///
/// # Arguments
/// * `agents` - Map of agent_id to AgentConfig
///
/// # Returns
/// * `Ok(())` if validation succeeds
/// * `Err(String)` with an error message if validation fails
pub fn validate_mining_config(agents: &BTreeMap<String, AgentConfig>) -> Result<(), String> {
    let mut total_hashrate = 0u32;
    let mut mining_agent_count = 0;

    for (agent_id, agent) in agents.iter() {
        // Skip non-mining agents (miners have hashrate or script containing "miner")
        if !agent.is_miner() {
            continue;
        }

        mining_agent_count += 1;

        // Validate wallet is present for mining agents
        if !agent.has_wallet() {
            return Err(format!(
                "Mining agent '{}' must have 'wallet' field for reward address",
                agent_id
            ));
        }

        // Validate hashrate exists for miners
        let hashrate = agent.hashrate.ok_or_else(|| format!(
            "Mining agent '{}' must have 'hashrate' field (percentage of network hashrate)",
            agent_id
        ))?;

        // Validate hashrate is in valid range
        if hashrate == 0 || hashrate > 100 {
            return Err(format!(
                "Mining agent '{}': hashrate {}% out of valid range (must be 1-100)",
                agent_id, hashrate
            ));
        }

        total_hashrate += hashrate;
    }

    // Warn if total doesn't equal 100 (but don't fail - this is recoverable)
    if mining_agent_count > 0 && total_hashrate != 100 {
        log::warn!(
            "Total mining hashrate is {}% (expected 100%). Found {} mining agent(s).",
            total_hashrate, mining_agent_count
        );
    }

    Ok(())
}

/// Validate agent daemon/wallet configuration
///
/// Validates agent configuration for the four supported agent types:
/// - Full agents: local daemon + wallet
/// - Daemon-only: local daemon without wallet
/// - Wallet-only: remote daemon + wallet
/// - Script-only: no daemon/wallet, just a script
///
/// # Validation Rules
/// 1. Mining requires local daemon - miners cannot mine through remote nodes
/// 2. Must have daemon OR wallet OR script - At least one component required
/// 3. Public node requires daemon - `is_public_node: true` requires local daemon
/// 4. Wallet-only requires remote daemon - If wallet specified without local daemon, need remote config
/// 5. Auto-discovery requires public nodes - `address: auto` needs at least one public node
///
/// # Arguments
/// * `agents` - Map of agent_id to AgentConfig
///
/// # Returns
/// * `Ok(())` if validation succeeds
/// * `Err(String)` with an error message if validation fails
pub fn validate_agent_daemon_config(agents: &BTreeMap<String, AgentConfig>) -> Result<(), String> {
    let mut has_public_node = false;
    let mut has_auto_discovery = false;

    for (agent_id, agent) in agents.iter() {
        let has_local_daemon = agent.has_local_daemon();
        let has_remote_daemon = agent.has_remote_daemon();
        let has_wallet = agent.has_wallet();
        let has_script = agent.has_script();
        let is_miner = agent.is_miner();

        // Track public nodes for auto-discovery validation
        if agent.is_public_node() {
            if !has_local_daemon {
                return Err(format!(
                    "Agent '{}': is_public_node attribute requires a local daemon",
                    agent_id
                ));
            }
            has_public_node = true;
        }

        // Track if any agent uses auto-discovery
        if let Some(addr) = agent.remote_daemon_address() {
            if addr == "auto" {
                has_auto_discovery = true;
            }
        }

        // Rule 1: Mining requires local daemon
        if is_miner && !has_local_daemon {
            return Err(format!(
                "Agent '{}': miners require a local daemon (cannot mine through remote node)",
                agent_id
            ));
        }

        // Rule 2: Must have daemon OR wallet OR script
        if !has_local_daemon && !has_remote_daemon && !has_wallet && !has_script {
            return Err(format!(
                "Agent '{}': must have at least one of: daemon, wallet, or script",
                agent_id
            ));
        }

        // Rule 4: Wallet-only requires remote daemon config
        if has_wallet && !has_local_daemon && !has_remote_daemon {
            return Err(format!(
                "Agent '{}': wallet without local daemon requires remote daemon configuration \
                (use daemon: {{ address: \"auto\" }} or daemon: {{ address: \"ip:port\" }})",
                agent_id
            ));
        }
    }

    // Rule 5: Auto-discovery requires at least one public node
    if has_auto_discovery && !has_public_node {
        return Err(
            "Wallet-only agents with 'auto' daemon address require at least one public node. \
            Add 'is_public_node: true' attribute to a daemon-enabled agent.".to_string()
        );
    }

    Ok(())
}

/// Validate simulation seed
///
/// Validates that the simulation seed is a valid non-negative u64 value.
/// Since u64 is inherently non-negative, this function always succeeds
/// but exists for API consistency and future extensibility.
///
/// # Arguments
/// * `simulation_seed` - The simulation seed to validate
///
/// # Returns
/// * `Ok(())` - Always succeeds for u64 values
///
/// # Examples
/// ```
/// use monerosim::utils::validation::validate_simulation_seed;
///
/// assert!(validate_simulation_seed(12345).is_ok());
/// assert!(validate_simulation_seed(0).is_ok());
/// assert!(validate_simulation_seed(u64::MAX).is_ok());
/// ```
pub fn validate_simulation_seed(simulation_seed: u64) -> Result<(), String> {
    // u64 is already non-negative by type definition, so this is always valid
    // This function exists for API consistency and future extensibility
    log::debug!("Validated simulation seed: {}", simulation_seed);
    Ok(())
}

/// Validate IP address diversity for Monero P2P compatibility.
///
/// Monero's P2P layer has anti-Sybil protections that limit connections:
/// 1. max_connections_per_ip: Only 1 connection per IP address (default)
/// 2. /24 subnet deduplication: Prefers peers from different /24 subnets
///
/// This function warns if the simulation has insufficient IP diversity,
/// which could cause connection issues or unrealistic P2P behavior.
///
/// # Arguments
/// * `ip_addresses` - List of IP addresses assigned to agents
/// * `agent_count` - Total number of agents in simulation
///
/// # Returns
/// * `Ok(())` if diversity is sufficient
/// * Logs warnings if diversity is low but still usable
pub fn validate_ip_subnet_diversity(ip_addresses: &[String], agent_count: usize) -> Result<(), String> {
    use std::collections::HashSet;

    if ip_addresses.is_empty() || agent_count == 0 {
        return Ok(());
    }

    // Extract unique /24 subnets (first 3 octets)
    let mut subnets_24: HashSet<String> = HashSet::new();
    // Extract unique first octets for diversity check
    let mut first_octets: HashSet<u8> = HashSet::new();

    for ip in ip_addresses {
        let parts: Vec<&str> = ip.split('.').collect();
        if parts.len() >= 4 {
            // /24 subnet
            let subnet = format!("{}.{}.{}", parts[0], parts[1], parts[2]);
            subnets_24.insert(subnet);

            // First octet
            if let Ok(first) = parts[0].parse::<u8>() {
                first_octets.insert(first);
            }
        }
    }

    let unique_subnets = subnets_24.len();
    let unique_octets = first_octets.len();
    let subnet_ratio = unique_subnets as f64 / agent_count as f64;

    log::info!("IP Diversity Analysis:");
    log::info!("  Total agents: {}", agent_count);
    log::info!("  Unique /24 subnets: {} ({:.1}% of agents)",
              unique_subnets, subnet_ratio * 100.0);
    log::info!("  Unique first octets: {}", unique_octets);

    // Monero's /24 deduplication means low subnet diversity can cause issues
    // Warn if less than 50% of agents have unique /24 subnets
    if subnet_ratio < 0.5 {
        log::warn!(
            "LOW IP DIVERSITY: Only {:.1}% of agents have unique /24 subnets. \
             Monero's P2P layer deduplicates by /24 subnet, which may cause \
             connection issues or unrealistic network behavior.",
            subnet_ratio * 100.0
        );
    }

    // Warn if very few first octets (unrealistic Internet distribution)
    if unique_octets < 5 && agent_count > 50 {
        log::warn!(
            "LIMITED IP RANGE: Only {} unique first octets for {} agents. \
             Real Internet traffic comes from diverse IP ranges.",
            unique_octets, agent_count
        );
    }

    // Critical warning if subnet count is very low
    if unique_subnets < agent_count / 4 && agent_count > 20 {
        log::error!(
            "CRITICAL: Only {} unique /24 subnets for {} agents ({:.1}%). \
             This will severely impact Monero P2P connectivity simulation. \
             Consider increasing topology node count or reducing agent count.",
            unique_subnets, agent_count, subnet_ratio * 100.0
        );
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config_v2::{DaemonConfig, DaemonSelectionStrategy};
    use crate::gml_parser::{GmlGraph, GmlNode};
    use std::collections::HashMap;

    /// Helper to create a BTreeMap with a single agent
    fn single_agent(id: &str, agent: AgentConfig) -> BTreeMap<String, AgentConfig> {
        let mut map = BTreeMap::new();
        map.insert(id.to_string(), agent);
        map
    }

    /// Helper to create a minimal AgentConfig
    fn base_agent() -> AgentConfig {
        AgentConfig {
            daemon: None,
            wallet: None,
            script: None,
            daemon_options: None,
            wallet_options: None,
            start_time: None,
            hashrate: None,
            transaction_interval: None,
            activity_start_time: None,
            can_receive_distributions: None,
            wait_time: None,
            initial_fund_amount: None,
            max_transaction_amount: None,
            min_transaction_amount: None,
            transaction_frequency: None,
            initial_wait_time: None,
            md_n_recipients: None,
            md_out_per_tx: None,
            md_output_amount: None,
            poll_interval: None,
            status_file: None,
            enable_alerts: None,
            detailed_logging: None,
            daemon_phases: None,
            wallet_phases: None,
            daemon_args: None,
            wallet_args: None,
            daemon_env: None,
            wallet_env: None,
            attributes: None,
            subnet_group: None,
        }
    }

    #[test]
    fn test_validate_gml_ip_consistency() {
        let mut graph = GmlGraph {
            nodes: Vec::new(),
            edges: Vec::new(),
            attributes: HashMap::new(),
        };

        // Add nodes with valid IPs
        graph.nodes.push(GmlNode {
            id: 0,
            label: None,
            ip: Some("192.168.1.1".to_string()),
            region: None,
            attributes: HashMap::new(),
        });
        graph.nodes.push(GmlNode {
            id: 1,
            label: None,
            ip: Some("10.0.0.1".to_string()),
            region: None,
            attributes: HashMap::new(),
        });

        assert!(validate_gml_ip_consistency(&graph).is_ok());

        // Add a node with invalid IP
        graph.nodes.push(GmlNode {
            id: 2,
            label: None,
            ip: Some("invalid.ip.address".to_string()),
            region: None,
            attributes: HashMap::new(),
        });

        let result = validate_gml_ip_consistency(&graph);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Invalid IP address"));

        // Remove invalid node and add a duplicate IP
        graph.nodes.pop();
        graph.nodes.push(GmlNode {
            id: 2,
            label: None,
            ip: Some("192.168.1.1".to_string()),
            region: None,
            attributes: HashMap::new(),
        });

        let result = validate_gml_ip_consistency(&graph);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Duplicate IP address"));
    }

    #[test]
    fn test_validate_topology_config() {
        assert!(validate_topology_config(&Topology::Mesh, 10).is_ok());
        assert!(validate_topology_config(&Topology::Mesh, 51).is_err());
        assert!(validate_topology_config(&Topology::Ring, 3).is_ok());
        assert!(validate_topology_config(&Topology::Ring, 2).is_err());
        assert!(validate_topology_config(&Topology::Star, 2).is_ok());
        assert!(validate_topology_config(&Topology::Star, 1).is_err());
        assert!(validate_topology_config(&Topology::Dag, 0).is_ok());
        assert!(validate_topology_config(&Topology::Dag, 100).is_ok());
    }

    // Tests for validate_mining_config

    #[test]
    fn test_validate_mining_config_valid() {
        let agent = AgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: Some("monero-wallet-rpc".to_string()),
            script: Some("agents.autonomous_miner".to_string()),
            hashrate: Some(100),
            ..base_agent()
        };

        assert!(validate_mining_config(&single_agent("miner-001", agent)).is_ok());
    }

    #[test]
    fn test_validate_mining_config_missing_wallet() {
        let agent = AgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: None,
            script: Some("agents.autonomous_miner".to_string()),
            hashrate: Some(50),
            ..base_agent()
        };

        let result = validate_mining_config(&single_agent("miner-001", agent));
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("must have 'wallet' field"));
    }

    #[test]
    fn test_validate_mining_config_non_miner_script_ok() {
        // Script with "miner" in name but no hashrate is NOT a miner
        // (e.g., miner_distributor distributes rewards, doesn't mine)
        let agent = AgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: Some("monero-wallet-rpc".to_string()),
            script: Some("agents.miner_distributor".to_string()),
            hashrate: None,
            ..base_agent()
        };

        // Should pass - not identified as a miner without hashrate
        assert!(validate_mining_config(&single_agent("distributor-001", agent)).is_ok());
    }

    #[test]
    fn test_validate_mining_config_zero_hashrate() {
        let agent = AgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: Some("monero-wallet-rpc".to_string()),
            hashrate: Some(0),
            ..base_agent()
        };

        let result = validate_mining_config(&single_agent("miner-001", agent));
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("out of valid range"));
    }

    #[test]
    fn test_validate_mining_config_hashrate_over_100() {
        let agent = AgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: Some("monero-wallet-rpc".to_string()),
            hashrate: Some(150),
            ..base_agent()
        };

        let result = validate_mining_config(&single_agent("miner-001", agent));
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("out of valid range"));
    }

    #[test]
    fn test_validate_mining_config_skips_non_miners() {
        // Non-mining agent without hashrate should be skipped
        let agent = AgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: Some("monero-wallet-rpc".to_string()),
            script: Some("agents.regular_user".to_string()),
            ..base_agent()
        };

        assert!(validate_mining_config(&single_agent("user-001", agent)).is_ok());
    }

    // Tests for validate_agent_daemon_config

    #[test]
    fn test_validate_agent_daemon_config_full_agent() {
        let agent = AgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: Some("monero-wallet-rpc".to_string()),
            script: Some("agents.regular_user".to_string()),
            ..base_agent()
        };

        assert!(validate_agent_daemon_config(&single_agent("user-001", agent)).is_ok());
    }

    #[test]
    fn test_validate_agent_daemon_config_daemon_only() {
        let mut attrs = BTreeMap::new();
        attrs.insert("is_public_node".to_string(), "true".to_string());

        let agent = AgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            attributes: Some(attrs),
            ..base_agent()
        };

        assert!(validate_agent_daemon_config(&single_agent("public-001", agent)).is_ok());
    }

    #[test]
    fn test_validate_agent_daemon_config_wallet_only_with_public_node() {
        let mut pub_attrs = BTreeMap::new();
        pub_attrs.insert("is_public_node".to_string(), "true".to_string());

        let public_node = AgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            attributes: Some(pub_attrs),
            ..base_agent()
        };

        let wallet_only = AgentConfig {
            daemon: Some(DaemonConfig::Remote {
                address: "auto".to_string(),
                strategy: Some(DaemonSelectionStrategy::Random),
            }),
            wallet: Some("monero-wallet-rpc".to_string()),
            script: Some("agents.regular_user".to_string()),
            ..base_agent()
        };

        let mut agents = BTreeMap::new();
        agents.insert("public-001".to_string(), public_node);
        agents.insert("wallet-001".to_string(), wallet_only);

        assert!(validate_agent_daemon_config(&agents).is_ok());
    }

    #[test]
    fn test_validate_agent_daemon_config_wallet_only_specific_daemon() {
        let agent = AgentConfig {
            daemon: Some(DaemonConfig::Remote {
                address: "192.168.1.10:18081".to_string(),
                strategy: None,
            }),
            wallet: Some("monero-wallet-rpc".to_string()),
            script: Some("agents.regular_user".to_string()),
            ..base_agent()
        };

        assert!(validate_agent_daemon_config(&single_agent("wallet-001", agent)).is_ok());
    }

    #[test]
    fn test_validate_agent_daemon_config_script_only() {
        let agent = AgentConfig {
            script: Some("agents.dns_server".to_string()),
            ..base_agent()
        };

        assert!(validate_agent_daemon_config(&single_agent("dns-001", agent)).is_ok());
    }

    #[test]
    fn test_validate_agent_daemon_config_mining_requires_local_daemon() {
        let agent = AgentConfig {
            daemon: Some(DaemonConfig::Remote {
                address: "192.168.1.10:18081".to_string(),
                strategy: None,
            }),
            wallet: Some("monero-wallet-rpc".to_string()),
            hashrate: Some(100),
            ..base_agent()
        };

        let result = validate_agent_daemon_config(&single_agent("miner-001", agent));
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("miners require a local daemon"));
    }

    #[test]
    fn test_validate_agent_daemon_config_public_node_requires_daemon() {
        let mut attrs = BTreeMap::new();
        attrs.insert("is_public_node".to_string(), "true".to_string());

        let agent = AgentConfig {
            script: Some("agents.monitor".to_string()),
            attributes: Some(attrs),
            ..base_agent()
        };

        let result = validate_agent_daemon_config(&single_agent("public-001", agent));
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("is_public_node attribute requires a local daemon"));
    }

    #[test]
    fn test_validate_agent_daemon_config_auto_requires_public_node() {
        let agent = AgentConfig {
            daemon: Some(DaemonConfig::Remote {
                address: "auto".to_string(),
                strategy: Some(DaemonSelectionStrategy::Random),
            }),
            wallet: Some("monero-wallet-rpc".to_string()),
            script: Some("agents.regular_user".to_string()),
            ..base_agent()
        };

        let result = validate_agent_daemon_config(&single_agent("wallet-001", agent));
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("require at least one public node"));
    }

    #[test]
    fn test_validate_agent_daemon_config_empty_agent() {
        let agent = base_agent();

        let result = validate_agent_daemon_config(&single_agent("empty-001", agent));
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("must have at least one of"));
    }

    #[test]
    fn test_validate_agent_daemon_config_wallet_without_daemon_ref() {
        let agent = AgentConfig {
            wallet: Some("monero-wallet-rpc".to_string()),
            script: Some("agents.regular_user".to_string()),
            ..base_agent()
        };

        let result = validate_agent_daemon_config(&single_agent("wallet-001", agent));
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("wallet without local daemon requires remote daemon configuration"));
    }

    #[test]
    fn test_validate_simulation_seed() {
        assert!(validate_simulation_seed(12345).is_ok());
        assert!(validate_simulation_seed(0).is_ok());
        assert!(validate_simulation_seed(u64::MAX).is_ok());
    }
}
