//! Agent distribution across network topology.
//!
//! This module handles the distribution of agents across different network
//! topologies, including AS-aware distribution for GML topologies and
//! round-robin distribution for switch-based topologies.

use std::collections::{HashMap, HashSet};
use std::path::Path;
use log::{debug, info, warn};

/// Distributes agents across network topology nodes.
/// 
/// # Arguments
/// 
/// * `topology_path` - Optional path to GML topology file
/// * `node_count` - Number of agents to distribute
/// * `as_numbers` - Vector of AS numbers from GML (if available)
/// 
/// # Returns
/// 
/// * Vector of node assignments (indices for GML, empty for switch)
pub fn distribute_agents_across_topology(
    topology_path: Option<&Path>,
    node_count: usize,
    as_numbers: &[Option<String>]
) -> Vec<Option<usize>> {
    match topology_path {
        Some(path) => {
            info!("Distributing {} agents across GML topology '{}'", node_count, path.display());
            distribute_agents_gml(node_count, as_numbers)
        }
        None => {
            info!("Using switch-based topology with {} agents", node_count);
            // For switch-based topology, there's no explicit distribution needed
            vec![None; node_count]
        }
    }
}

/// Distributes agents across GML topology with AS awareness
/// 
/// # Arguments
/// 
/// * `node_count` - Number of agents to distribute
/// * `as_numbers` - Vector of AS numbers from GML
/// 
/// # Returns
/// 
/// * Vector of node assignments (indices in the GML file)
fn distribute_agents_gml(node_count: usize, as_numbers: &[Option<String>]) -> Vec<Option<usize>> {
    if as_numbers.is_empty() {
        warn!("No AS numbers provided for GML distribution, using default distribution");
        // Default distribution if no AS numbers provided
        return (0..node_count).map(|i| Some(i % as_numbers.len())).collect();
    }

    // Group nodes by AS number for AS-aware distribution
    let mut as_groups: HashMap<String, Vec<usize>> = HashMap::new();
    let mut unknown_as_nodes: Vec<usize> = Vec::new();

    // Populate AS groups
    for (node_idx, as_opt) in as_numbers.iter().enumerate() {
        if let Some(as_num) = as_opt {
            as_groups.entry(as_num.clone()).or_insert_with(Vec::new).push(node_idx);
        } else {
            unknown_as_nodes.push(node_idx);
        }
    }

    // Print AS distribution for debugging
    debug!("Distributing agents across {} AS groups", as_groups.len());
    for (as_num, nodes) in &as_groups {
        debug!("AS {}: {} nodes", as_num, nodes.len());
    }

    // Distribute agents across AS groups
    let mut assignments = Vec::with_capacity(node_count);
    let mut used_nodes = HashSet::new();
    
    // First, try to assign each agent to a different AS if possible
    let mut as_keys: Vec<String> = as_groups.keys().cloned().collect();
    as_keys.sort(); // Sort for deterministic behavior

    for i in 0..node_count {
        if i < as_keys.len() {
            // Select the first available node from the AS
            let as_num = &as_keys[i];
            if let Some(nodes) = as_groups.get(as_num) {
                for &node_idx in nodes {
                    if !used_nodes.contains(&node_idx) {
                        assignments.push(Some(node_idx));
                        used_nodes.insert(node_idx);
                        break;
                    }
                }
                
                // If no unused nodes in this AS, try a random one
                if assignments.len() <= i {
                    if let Some(&node_idx) = nodes.first() {
                        assignments.push(Some(node_idx));
                        used_nodes.insert(node_idx);
                    }
                }
            }
        } else {
            // If we have more agents than AS groups, distribute evenly
            let as_idx = i % as_keys.len();
            let as_num = &as_keys[as_idx];
            if let Some(nodes) = as_groups.get(as_num) {
                if let Some(&node_idx) = nodes.get(i % nodes.len()) {
                    assignments.push(Some(node_idx));
                    used_nodes.insert(node_idx);
                }
            }
        }
        
        // If still no assignment, use unknown AS nodes or repeat
        if assignments.len() <= i {
            if !unknown_as_nodes.is_empty() {
                let node_idx = unknown_as_nodes[i % unknown_as_nodes.len()];
                assignments.push(Some(node_idx));
                used_nodes.insert(node_idx);
            } else {
                // Last resort - pick any node
                let total_nodes = as_numbers.len();
                if total_nodes > 0 {
                    assignments.push(Some(i % total_nodes));
                } else {
                    assignments.push(None);
                }
            }
        }
    }

    debug!("Assigned {} agents to GML nodes", assignments.len());
    assignments
}
