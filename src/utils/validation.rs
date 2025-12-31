//! Configuration validation utilities.
//!
//! This module provides validation functions for configuration
//! parameters and consistency checks.

use crate::gml_parser::{GmlGraph, GmlNode};
use crate::config_v2::{Topology, UserAgentConfig};

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
/// - Mining agents have hashrate attribute (percentage of network hashrate)
/// - Hashrate values are valid (0-100)
/// - Total hashrate equals 100% (warning if not)
///
/// # Arguments
/// * `agents` - The list of user agents to validate
///
/// # Returns
/// * `Ok(())` if validation succeeds
/// * `Err(String)` with an error message if validation fails
///
/// # Examples
/// ```
/// use monerosim::utils::validation::validate_mining_config;
/// use monerosim::config_v2::{DaemonConfig, UserAgentConfig};
/// use std::collections::HashMap;
///
/// let mut attributes = HashMap::new();
/// attributes.insert("hashrate".to_string(), "100".to_string());
///
/// let agent = UserAgentConfig {
///     daemon: Some(DaemonConfig::Local("monerod".to_string())),
///     wallet: Some("monero-wallet-rpc".to_string()),
///     mining_script: Some("agents.autonomous_miner".to_string()),
///     user_script: None,
///     is_miner: None,
///     attributes: Some(attributes),
///     start_time_offset: None,
/// };
///
/// assert!(validate_mining_config(&[agent]).is_ok());
/// ```
pub fn validate_mining_config(agents: &[UserAgentConfig]) -> Result<(), String> {
    let mut total_hashrate = 0.0;
    let mut mining_agent_count = 0;
    
    for (idx, agent) in agents.iter().enumerate() {
        // Skip non-mining agents
        if agent.mining_script.is_none() {
            continue;
        }
        
        mining_agent_count += 1;
        
        // Validate wallet is present for mining agents
        if agent.wallet.is_none() {
            return Err(format!(
                "Mining agent at index {} must have 'wallet' field for reward address (agents with 'mining_script' require a wallet)",
                idx
            ));
        }
        
        // Validate hashrate attribute exists
        let hashrate_str = agent.attributes.as_ref()
            .and_then(|attrs| attrs.get("hashrate"))
            .ok_or_else(|| format!(
                "Mining agent at index {} must have 'hashrate' attribute (percentage of network hashrate)",
                idx
            ))?;
            
        // Parse and validate hashrate value
        let hashrate = hashrate_str.parse::<f64>()
            .map_err(|_| format!(
                "Mining agent at index {}: invalid hashrate '{}' (must be a number between 0 and 100)",
                idx, hashrate_str
            ))?;
            
        if hashrate <= 0.0 || hashrate > 100.0 {
            return Err(format!(
                "Mining agent at index {}: hashrate {}% out of valid range (must be greater than 0 and at most 100)",
                idx, hashrate
            ));
        }
        
        total_hashrate += hashrate;
    }
    
    // Warn if total doesn't equal 100 (but don't fail - this is recoverable)
    if mining_agent_count > 0 && (total_hashrate - 100.0).abs() > 0.01 {
        eprintln!(
            "Warning: Total mining hashrate is {:.2}% (expected 100%). \
            Distribution may not match expectations. Found {} mining agent(s).",
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
/// 1. Mining requires local daemon - `mining_script` and `is_miner` require local daemon
/// 2. Must have daemon OR wallet OR script - At least one component required
/// 3. Public node requires daemon - `is_public_node: true` requires local daemon
/// 4. Wallet-only requires remote daemon - If wallet specified without local daemon, need remote config
/// 5. Auto-discovery requires public nodes - `address: auto` needs at least one public node
///
/// # Arguments
/// * `agents` - The list of user agents to validate
///
/// # Returns
/// * `Ok(())` if validation succeeds
/// * `Err(String)` with an error message if validation fails
pub fn validate_agent_daemon_config(agents: &[UserAgentConfig]) -> Result<(), String> {
    let mut has_public_node = false;
    let mut has_auto_discovery = false;

    for (idx, agent) in agents.iter().enumerate() {
        let has_local_daemon = agent.has_local_daemon();
        let has_remote_daemon = agent.has_remote_daemon();
        let has_wallet = agent.has_wallet();
        let has_script = agent.has_script();
        let has_mining_script = agent.mining_script.is_some();
        let is_miner = agent.is_miner_value();

        // Track public nodes for auto-discovery validation
        if agent.is_public_node() {
            if !has_local_daemon {
                return Err(format!(
                    "Agent at index {}: is_public_node attribute requires a local daemon",
                    idx
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
        if has_mining_script && !has_local_daemon {
            return Err(format!(
                "Agent at index {}: mining_script requires a local daemon (cannot mine through remote node)",
                idx
            ));
        }

        if is_miner && !has_local_daemon {
            return Err(format!(
                "Agent at index {}: is_miner requires a local daemon",
                idx
            ));
        }

        // Rule 2: Must have daemon OR wallet OR script
        if !has_local_daemon && !has_remote_daemon && !has_wallet && !has_script {
            return Err(format!(
                "Agent at index {}: must have at least one of: daemon, wallet, or user_script",
                idx
            ));
        }

        // Rule 4: Wallet-only requires remote daemon config
        if has_wallet && !has_local_daemon && !has_remote_daemon {
            return Err(format!(
                "Agent at index {}: wallet without local daemon requires remote daemon configuration \
                (use daemon: {{ address: \"auto\" }} or daemon: {{ address: \"ip:port\" }})",
                idx
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::gml_parser::{GmlGraph, GmlNode};
    use std::collections::HashMap;

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
        
        // Test valid configuration
        assert!(validate_gml_ip_consistency(&graph).is_ok());
        
        // Add a node with invalid IP
        graph.nodes.push(GmlNode {
            id: 2,
            label: None,
            ip: Some("invalid.ip.address".to_string()),
            region: None,
            attributes: HashMap::new(),
        });

        // Test invalid IP detection
        let result = validate_gml_ip_consistency(&graph);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Invalid IP address"));
        
        // Remove invalid node and add a duplicate IP
        graph.nodes.pop();
        graph.nodes.push(GmlNode {
            id: 2,
            label: None,
            ip: Some("192.168.1.1".to_string()), // Duplicate of node 0
            region: None,
            attributes: HashMap::new(),
        });
        
        // Test duplicate IP detection
        let result = validate_gml_ip_consistency(&graph);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Duplicate IP address"));
    }

    #[test]
    fn test_validate_topology_config() {
        // Test Mesh topology
        assert!(validate_topology_config(&Topology::Mesh, 10).is_ok());
        assert!(validate_topology_config(&Topology::Mesh, 51).is_err());
        
        // Test Ring topology
        assert!(validate_topology_config(&Topology::Ring, 3).is_ok());
        assert!(validate_topology_config(&Topology::Ring, 2).is_err());
        
        // Test Star topology
        assert!(validate_topology_config(&Topology::Star, 2).is_ok());
        assert!(validate_topology_config(&Topology::Star, 1).is_err());
        
        // Test DAG topology (always valid)
        assert!(validate_topology_config(&Topology::Dag, 0).is_ok());
        assert!(validate_topology_config(&Topology::Dag, 100).is_ok());
    }

    #[test]
    fn test_validate_mining_config_valid() {
        use std::collections::HashMap;

        let mut attributes = HashMap::new();
        attributes.insert("hashrate".to_string(), "100".to_string());

        let agent = UserAgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: Some("monero-wallet-rpc".to_string()),
            mining_script: Some("agents.autonomous_miner".to_string()),
            user_script: None,
            is_miner: None,
            attributes: Some(attributes),
            start_time_offset: None,
        };

        assert!(validate_mining_config(&[agent]).is_ok());
    }

    #[test]
    fn test_validate_mining_config_missing_wallet() {
        use std::collections::HashMap;

        let mut attributes = HashMap::new();
        attributes.insert("hashrate".to_string(), "50".to_string());

        let agent = UserAgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: None, // Missing wallet
            mining_script: Some("agents.autonomous_miner".to_string()),
            user_script: None,
            is_miner: None,
            attributes: Some(attributes),
            start_time_offset: None,
        };

        let result = validate_mining_config(&[agent]);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("must have 'wallet' field"));
    }

    #[test]
    fn test_validate_mining_config_missing_hashrate() {
        let agent = UserAgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: Some("monero-wallet-rpc".to_string()),
            mining_script: Some("agents.autonomous_miner".to_string()),
            user_script: None,
            is_miner: None,
            attributes: None, // Missing hashrate attribute
            start_time_offset: None,
        };

        let result = validate_mining_config(&[agent]);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("must have 'hashrate' attribute"));
    }

    #[test]
    fn test_validate_mining_config_invalid_hashrate_format() {
        use std::collections::HashMap;

        let mut attributes = HashMap::new();
        attributes.insert("hashrate".to_string(), "not_a_number".to_string());

        let agent = UserAgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: Some("monero-wallet-rpc".to_string()),
            mining_script: Some("agents.autonomous_miner".to_string()),
            user_script: None,
            is_miner: None,
            attributes: Some(attributes),
            start_time_offset: None,
        };

        let result = validate_mining_config(&[agent]);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("invalid hashrate"));
    }

    #[test]
    fn test_validate_mining_config_negative_hashrate() {
        use std::collections::HashMap;

        let mut attributes = HashMap::new();
        attributes.insert("hashrate".to_string(), "-10".to_string());

        let agent = UserAgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: Some("monero-wallet-rpc".to_string()),
            mining_script: Some("agents.autonomous_miner".to_string()),
            user_script: None,
            is_miner: None,
            attributes: Some(attributes),
            start_time_offset: None,
        };

        let result = validate_mining_config(&[agent]);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("out of valid range"));
    }

    #[test]
    fn test_validate_mining_config_hashrate_over_100() {
        use std::collections::HashMap;

        let mut attributes = HashMap::new();
        attributes.insert("hashrate".to_string(), "150".to_string());

        let agent = UserAgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: Some("monero-wallet-rpc".to_string()),
            mining_script: Some("agents.autonomous_miner".to_string()),
            user_script: None,
            is_miner: None,
            attributes: Some(attributes),
            start_time_offset: None,
        };

        let result = validate_mining_config(&[agent]);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("out of valid range"));
    }

    #[test]
    fn test_validate_mining_config_skips_non_miners() {
        use std::collections::HashMap;

        // Non-mining agent without hashrate should be skipped
        let agent = UserAgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: Some("monero-wallet-rpc".to_string()),
            mining_script: None, // Not a mining agent
            user_script: Some("agents.regular_user".to_string()),
            is_miner: None,
            attributes: Some(HashMap::new()),
            start_time_offset: None,
        };

        assert!(validate_mining_config(&[agent]).is_ok());
    }

    // Tests for validate_agent_daemon_config

    #[test]
    fn test_validate_agent_daemon_config_full_agent() {
        // Full agent with local daemon and wallet
        let agent = UserAgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: Some("monero-wallet-rpc".to_string()),
            mining_script: None,
            user_script: Some("agents.regular_user".to_string()),
            is_miner: None,
            attributes: None,
            start_time_offset: None,
        };

        assert!(validate_agent_daemon_config(&[agent]).is_ok());
    }

    #[test]
    fn test_validate_agent_daemon_config_daemon_only() {
        use std::collections::HashMap;

        // Daemon-only agent (public node)
        let mut attributes = HashMap::new();
        attributes.insert("is_public_node".to_string(), "true".to_string());

        let agent = UserAgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: None,
            mining_script: None,
            user_script: None,
            is_miner: None,
            attributes: Some(attributes),
            start_time_offset: None,
        };

        assert!(validate_agent_daemon_config(&[agent]).is_ok());
    }

    #[test]
    fn test_validate_agent_daemon_config_wallet_only_with_public_node() {
        use std::collections::HashMap;
        use crate::config_v2::DaemonSelectionStrategy;

        // Public node (daemon-only)
        let mut pub_attrs = HashMap::new();
        pub_attrs.insert("is_public_node".to_string(), "true".to_string());

        let public_node = UserAgentConfig {
            daemon: Some(DaemonConfig::Local("monerod".to_string())),
            wallet: None,
            mining_script: None,
            user_script: None,
            is_miner: None,
            attributes: Some(pub_attrs),
            start_time_offset: None,
        };

        // Wallet-only agent using auto-discovery
        let wallet_only = UserAgentConfig {
            daemon: Some(DaemonConfig::Remote {
                address: "auto".to_string(),
                strategy: Some(DaemonSelectionStrategy::Random),
            }),
            wallet: Some("monero-wallet-rpc".to_string()),
            mining_script: None,
            user_script: Some("agents.regular_user".to_string()),
            is_miner: None,
            attributes: None,
            start_time_offset: None,
        };

        assert!(validate_agent_daemon_config(&[public_node, wallet_only]).is_ok());
    }

    #[test]
    fn test_validate_agent_daemon_config_wallet_only_specific_daemon() {
        // Wallet-only agent connecting to specific daemon (no public node needed)
        let agent = UserAgentConfig {
            daemon: Some(DaemonConfig::Remote {
                address: "192.168.1.10:18081".to_string(),
                strategy: None,
            }),
            wallet: Some("monero-wallet-rpc".to_string()),
            mining_script: None,
            user_script: Some("agents.regular_user".to_string()),
            is_miner: None,
            attributes: None,
            start_time_offset: None,
        };

        assert!(validate_agent_daemon_config(&[agent]).is_ok());
    }

    #[test]
    fn test_validate_agent_daemon_config_script_only() {
        // Script-only agent (no daemon, no wallet)
        let agent = UserAgentConfig {
            daemon: None,
            wallet: None,
            mining_script: None,
            user_script: Some("agents.dns_server".to_string()),
            is_miner: None,
            attributes: None,
            start_time_offset: None,
        };

        assert!(validate_agent_daemon_config(&[agent]).is_ok());
    }

    #[test]
    fn test_validate_agent_daemon_config_mining_requires_local_daemon() {
        use std::collections::HashMap;

        let mut attributes = HashMap::new();
        attributes.insert("hashrate".to_string(), "100".to_string());

        // Mining agent with remote daemon (should fail)
        let agent = UserAgentConfig {
            daemon: Some(DaemonConfig::Remote {
                address: "192.168.1.10:18081".to_string(),
                strategy: None,
            }),
            wallet: Some("monero-wallet-rpc".to_string()),
            mining_script: Some("agents.autonomous_miner".to_string()),
            user_script: None,
            is_miner: None,
            attributes: Some(attributes),
            start_time_offset: None,
        };

        let result = validate_agent_daemon_config(&[agent]);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("mining_script requires a local daemon"));
    }

    #[test]
    fn test_validate_agent_daemon_config_public_node_requires_daemon() {
        use std::collections::HashMap;

        // Public node without daemon (should fail)
        let mut attributes = HashMap::new();
        attributes.insert("is_public_node".to_string(), "true".to_string());

        let agent = UserAgentConfig {
            daemon: None,
            wallet: None,
            mining_script: None,
            user_script: Some("agents.monitor".to_string()),
            is_miner: None,
            attributes: Some(attributes),
            start_time_offset: None,
        };

        let result = validate_agent_daemon_config(&[agent]);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("is_public_node attribute requires a local daemon"));
    }

    #[test]
    fn test_validate_agent_daemon_config_auto_requires_public_node() {
        use crate::config_v2::DaemonSelectionStrategy;

        // Wallet-only with auto but no public node (should fail)
        let agent = UserAgentConfig {
            daemon: Some(DaemonConfig::Remote {
                address: "auto".to_string(),
                strategy: Some(DaemonSelectionStrategy::Random),
            }),
            wallet: Some("monero-wallet-rpc".to_string()),
            mining_script: None,
            user_script: Some("agents.regular_user".to_string()),
            is_miner: None,
            attributes: None,
            start_time_offset: None,
        };

        let result = validate_agent_daemon_config(&[agent]);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("require at least one public node"));
    }

    #[test]
    fn test_validate_agent_daemon_config_empty_agent() {
        // Agent with nothing (should fail)
        let agent = UserAgentConfig {
            daemon: None,
            wallet: None,
            mining_script: None,
            user_script: None,
            is_miner: None,
            attributes: None,
            start_time_offset: None,
        };

        let result = validate_agent_daemon_config(&[agent]);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("must have at least one of"));
    }

    #[test]
    fn test_validate_agent_daemon_config_wallet_without_daemon_ref() {
        // Wallet without daemon config (should fail)
        let agent = UserAgentConfig {
            daemon: None,
            wallet: Some("monero-wallet-rpc".to_string()),
            mining_script: None,
            user_script: Some("agents.regular_user".to_string()),
            is_miner: None,
            attributes: None,
            start_time_offset: None,
        };

        let result = validate_agent_daemon_config(&[agent]);
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
