//! Configuration validation utilities.
//!
//! This module provides validation functions for configuration
//! parameters and consistency checks.

use crate::gml_parser::{GmlGraph, GmlNode};
use crate::config_v2::Topology;

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
///
/// let mut graph = GmlGraph::new();
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
}
