//! Agent distribution across network topology.
//!
//! This module handles the distribution of agents across different network
//! topologies. For GML topologies, it supports multiple distribution strategies:
//!
//! - **Global**: Distribute agents proportionally across all 6 geographic regions
//! - **Sequential**: Assign agents to nodes 0, 1, 2, ... (legacy behavior)
//! - **Weighted**: Custom weights per region
//!
//! The distribution ensures agents are spread across the simulated Internet
//! rather than clustering in a single region.

use std::path::Path;
use log::{debug, info, warn};

use crate::config_v2::{DistributionStrategy, RegionWeights};
use crate::ip::as_manager::calculate_region_boundaries;

/// Distributes agents across network topology nodes.
///
/// # Arguments
///
/// * `topology_path` - Optional path to GML topology file
/// * `agent_count` - Number of agents to distribute
/// * `as_numbers` - Vector of AS numbers from GML (if available)
/// * `strategy` - Distribution strategy to use (defaults to Global)
/// * `weights` - Optional custom region weights (for Weighted strategy)
///
/// # Returns
///
/// * Vector of node assignments (indices for GML, empty for switch)
pub fn distribute_agents_across_topology(
    topology_path: Option<&Path>,
    agent_count: usize,
    as_numbers: &[Option<String>],
    strategy: Option<&DistributionStrategy>,
    weights: Option<&RegionWeights>,
) -> Vec<Option<usize>> {
    let strategy = strategy.unwrap_or(&DistributionStrategy::Global);
    let total_nodes = as_numbers.len();

    match topology_path {
        Some(path) => {
            info!("Distributing {} agents across GML topology '{}' using {:?} strategy",
                  agent_count, path.display(), strategy);
            distribute_agents_gml(agent_count, total_nodes, strategy, weights)
        }
        None => {
            info!("Using switch-based topology with {} agents", agent_count);
            // For switch-based topology, there's no explicit distribution needed
            vec![None; agent_count]
        }
    }
}

/// Distributes agents across GML topology using the specified strategy.
///
/// # Arguments
///
/// * `agent_count` - Number of agents to distribute
/// * `total_nodes` - Total number of nodes in the GML topology
/// * `strategy` - Distribution strategy to use
/// * `weights` - Optional custom region weights
///
/// # Returns
///
/// * Vector of node assignments (indices in the GML file)
fn distribute_agents_gml(
    agent_count: usize,
    total_nodes: usize,
    strategy: &DistributionStrategy,
    weights: Option<&RegionWeights>,
) -> Vec<Option<usize>> {
    if total_nodes == 0 {
        warn!("No topology nodes available for distribution");
        return vec![None; agent_count];
    }

    match strategy {
        DistributionStrategy::Sequential => {
            info!("Using sequential distribution (nodes 0, 1, 2, ...)");
            distribute_sequential(agent_count, total_nodes)
        }
        DistributionStrategy::Global => {
            info!("Using global distribution across all regions");
            distribute_global(agent_count, total_nodes)
        }
        DistributionStrategy::Weighted => {
            info!("Using weighted distribution with custom region weights");
            distribute_weighted(agent_count, total_nodes, weights)
        }
    }
}

/// Sequential distribution: assign agents to nodes 0, 1, 2, ...
/// This is the legacy behavior that clusters agents in the first region.
fn distribute_sequential(agent_count: usize, total_nodes: usize) -> Vec<Option<usize>> {
    (0..agent_count)
        .map(|i| Some(i % total_nodes))
        .collect()
}

/// Global distribution: spread agents proportionally across all 6 regions.
///
/// Agents are distributed round-robin across regions, then spread within
/// each region. This ensures geographic diversity.
fn distribute_global(agent_count: usize, total_nodes: usize) -> Vec<Option<usize>> {
    let boundaries = calculate_region_boundaries(total_nodes);
    let mut assignments = Vec::with_capacity(agent_count);

    // Track how many agents we've placed in each region
    let mut region_counters = [0usize; 6];

    for i in 0..agent_count {
        // Cycle through regions round-robin
        let region_idx = i % 6;
        let (region, start, end) = boundaries[region_idx];
        let region_size = end.saturating_sub(start) + 1;

        if region_size == 0 {
            // Region has no nodes, skip to next
            warn!("Region {:?} has no nodes, assigning to node 0", region);
            assignments.push(Some(0));
            continue;
        }

        // Calculate offset within the region
        let offset = region_counters[region_idx] % region_size;
        let node = start + offset;

        assignments.push(Some(node));
        region_counters[region_idx] += 1;

        debug!("Agent {} -> node {} ({:?})", i, node, region);
    }

    // Log distribution summary
    info!("Global distribution summary:");
    for (i, (region, _, _)) in boundaries.iter().enumerate() {
        if region_counters[i] > 0 {
            info!("  {:?}: {} agents", region, region_counters[i]);
        }
    }

    assignments
}

/// Weighted distribution: use custom weights to determine how many agents
/// go to each region.
fn distribute_weighted(
    agent_count: usize,
    total_nodes: usize,
    weights: Option<&RegionWeights>,
) -> Vec<Option<usize>> {
    let boundaries = calculate_region_boundaries(total_nodes);

    // Get weights or use defaults
    let region_weights: [u32; 6] = match weights {
        Some(w) => [
            w.north_america.unwrap_or(17),
            w.europe.unwrap_or(25),
            w.asia.unwrap_or(25),
            w.south_america.unwrap_or(17),
            w.africa.unwrap_or(8),
            w.oceania.unwrap_or(8),
        ],
        None => [17, 25, 25, 17, 8, 8], // Default proportions
    };

    let total_weight: u32 = region_weights.iter().sum();

    // Calculate how many agents go to each region
    let mut agents_per_region = [0usize; 6];
    let mut assigned = 0;

    for i in 0..6 {
        let proportion = region_weights[i] as f64 / total_weight as f64;
        let count = (agent_count as f64 * proportion).round() as usize;
        agents_per_region[i] = count;
        assigned += count;
    }

    // Adjust for rounding errors
    while assigned < agent_count {
        // Add to the largest region
        let max_idx = region_weights.iter()
            .enumerate()
            .max_by_key(|(_, &w)| w)
            .map(|(i, _)| i)
            .unwrap_or(0);
        agents_per_region[max_idx] += 1;
        assigned += 1;
    }
    while assigned > agent_count {
        // Remove from the smallest non-zero region
        let min_idx = agents_per_region.iter()
            .enumerate()
            .filter(|(_, &c)| c > 0)
            .min_by_key(|(_, &c)| c)
            .map(|(i, _)| i)
            .unwrap_or(0);
        if agents_per_region[min_idx] > 0 {
            agents_per_region[min_idx] -= 1;
            assigned -= 1;
        } else {
            break;
        }
    }

    // Assign agents to nodes within each region
    let mut assignments = Vec::with_capacity(agent_count);

    for (region_idx, &count) in agents_per_region.iter().enumerate() {
        let (region, start, end) = boundaries[region_idx];
        let region_size = end.saturating_sub(start) + 1;

        for j in 0..count {
            let offset = j % region_size;
            let node = start + offset;
            assignments.push(Some(node));
            debug!("Agent -> node {} ({:?})", node, region);
        }
    }

    // Log distribution summary
    info!("Weighted distribution summary:");
    for (i, (region, _, _)) in boundaries.iter().enumerate() {
        if agents_per_region[i] > 0 {
            info!("  {:?}: {} agents (weight {})", region, agents_per_region[i], region_weights[i]);
        }
    }

    assignments
}

// Keep the old function signature for backward compatibility
// This will be removed once all callers are updated
#[deprecated(note = "Use distribute_agents_across_topology with strategy parameter")]
pub fn distribute_agents_across_topology_legacy(
    topology_path: Option<&Path>,
    node_count: usize,
    as_numbers: &[Option<String>]
) -> Vec<Option<usize>> {
    distribute_agents_across_topology(
        topology_path,
        node_count,
        as_numbers,
        Some(&DistributionStrategy::Global),
        None,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sequential_distribution() {
        let result = distribute_sequential(10, 100);
        assert_eq!(result.len(), 10);
        for (i, node) in result.iter().enumerate() {
            assert_eq!(*node, Some(i));
        }
    }

    #[test]
    fn test_global_distribution_spreads_across_regions() {
        // With 12 agents and 1200 nodes, we should have 2 agents per region
        let result = distribute_global(12, 1200);
        assert_eq!(result.len(), 12);

        // Calculate boundaries for 1200 nodes
        let boundaries = calculate_region_boundaries(1200);

        // Check that agents are in different regions
        let mut region_counts = [0; 6];
        for node in result.iter() {
            if let Some(n) = node {
                for (i, (_, start, end)) in boundaries.iter().enumerate() {
                    if *n >= *start && *n <= *end {
                        region_counts[i] += 1;
                        break;
                    }
                }
            }
        }

        // Each region should have exactly 2 agents (12 agents / 6 regions)
        for count in region_counts {
            assert_eq!(count, 2);
        }
    }

    #[test]
    fn test_global_distribution_wraps_within_region() {
        // With 24 agents and 1200 nodes, regions should wrap
        let result = distribute_global(24, 1200);
        assert_eq!(result.len(), 24);

        // All assignments should be valid
        for node in result.iter() {
            assert!(node.is_some());
            assert!(node.unwrap() < 1200);
        }
    }

    #[test]
    fn test_weighted_distribution() {
        let weights = RegionWeights {
            north_america: Some(50),  // 50% to North America
            europe: Some(50),         // 50% to Europe
            asia: Some(0),
            south_america: Some(0),
            africa: Some(0),
            oceania: Some(0),
        };

        let result = distribute_weighted(10, 1200, Some(&weights));
        assert_eq!(result.len(), 10);

        // All agents should be in North America (0-199) or Europe (200-499)
        let boundaries = calculate_region_boundaries(1200);
        let na_end = boundaries[0].2;
        let eu_end = boundaries[1].2;

        for node in result.iter() {
            if let Some(n) = node {
                assert!(*n <= eu_end, "Node {} should be in NA or EU", n);
            }
        }
    }
}
