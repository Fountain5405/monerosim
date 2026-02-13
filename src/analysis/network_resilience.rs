//! Network resilience analysis.
//!
//! Analyzes network connectivity, centralization metrics, and partition risk
//! based on connection patterns observed in simulation logs.

use std::collections::{HashMap, HashSet};

use super::types::*;
use super::calculate_gini;

/// Analyze network resilience based on connection topology
pub fn analyze_resilience(
    log_data: &HashMap<String, NodeLogData>,
    agents: &[AnalysisAgentInfo],
) -> ResilienceMetrics {
    // Build adjacency graph from connection events
    let graph = build_connection_graph(log_data, agents);

    // Connectivity metrics
    let connectivity = analyze_connectivity(&graph, agents);

    // Centralization metrics
    let centralization = analyze_centralization(log_data, agents);

    // Partition risk
    let partition_risk = analyze_partition_risk(&graph);

    ResilienceMetrics {
        connectivity,
        centralization,
        partition_risk,
    }
}

/// Build a graph of active connections (node_id -> set of connected peer IPs)
fn build_connection_graph(
    log_data: &HashMap<String, NodeLogData>,
    agents: &[AnalysisAgentInfo],
) -> HashMap<String, HashSet<String>> {
    let mut graph: HashMap<String, HashSet<String>> = HashMap::new();

    // Initialize all nodes
    for agent in agents {
        graph.insert(agent.id.clone(), HashSet::new());
    }

    // Build IP to node ID mapping
    let ip_to_node: HashMap<&str, &str> = agents
        .iter()
        .map(|a| (a.ip_addr.as_str(), a.id.as_str()))
        .collect();

    for (node_id, node_data) in log_data {
        // Track active connections by connection_id
        let mut active_connections: HashMap<String, String> = HashMap::new();

        for event in &node_data.connection_events {
            if event.is_open {
                active_connections.insert(event.connection_id.clone(), event.peer_ip.clone());
            } else {
                active_connections.remove(&event.connection_id);
            }
        }

        // Add final active connections to graph
        let node_connections = graph.entry(node_id.clone()).or_default();
        for peer_ip in active_connections.values() {
            // Convert IP to node ID if possible
            if let Some(&peer_id) = ip_to_node.get(peer_ip.as_str()) {
                node_connections.insert(peer_id.to_string());
            } else {
                node_connections.insert(peer_ip.clone());
            }
        }
    }

    graph
}

/// Analyze connectivity metrics
fn analyze_connectivity(
    graph: &HashMap<String, HashSet<String>>,
    agents: &[AnalysisAgentInfo],
) -> ConnectivityMetrics {
    let peer_counts: Vec<usize> = graph.values().map(|peers| peers.len()).collect();

    let min_peer_count = peer_counts.iter().min().copied().unwrap_or(0);
    let max_peer_count = peer_counts.iter().max().copied().unwrap_or(0);
    let average_peer_count = if peer_counts.is_empty() {
        0.0
    } else {
        peer_counts.iter().sum::<usize>() as f64 / peer_counts.len() as f64
    };

    // Find isolated nodes
    let isolated_nodes: Vec<String> = graph
        .iter()
        .filter(|(_, peers)| peers.is_empty())
        .map(|(node_id, _)| node_id.clone())
        .collect();

    // Build peer count distribution
    let peer_count_distribution: HashMap<String, usize> = graph
        .iter()
        .map(|(node_id, peers)| (node_id.clone(), peers.len()))
        .collect();

    ConnectivityMetrics {
        total_nodes: agents.len(),
        average_peer_count,
        min_peer_count,
        max_peer_count,
        isolated_nodes,
        peer_count_distribution,
    }
}

/// Analyze centralization metrics
fn analyze_centralization(
    log_data: &HashMap<String, NodeLogData>,
    agents: &[AnalysisAgentInfo],
) -> CentralizationMetrics {
    // Count first-seen observations per node
    let mut first_seen_counts: HashMap<String, usize> = HashMap::new();
    let mut tx_first_seen: HashMap<String, (String, SimTime)> = HashMap::new(); // tx_hash -> (node_id, timestamp)

    // Find which node saw each TX first
    for (node_id, node_data) in log_data {
        for obs in &node_data.tx_observations {
            tx_first_seen
                .entry(obs.tx_hash.clone())
                .and_modify(|(existing_node, existing_time)| {
                    if obs.timestamp < *existing_time {
                        *existing_node = node_id.clone();
                        *existing_time = obs.timestamp;
                    }
                })
                .or_insert((node_id.clone(), obs.timestamp));
        }
    }

    // Count first-seen per node
    for (_, (node_id, _)) in &tx_first_seen {
        *first_seen_counts.entry(node_id.clone()).or_insert(0) += 1;
    }

    // Calculate Gini coefficient
    let counts: Vec<f64> = first_seen_counts.values().map(|&c| c as f64).collect();
    let first_seen_gini = calculate_gini(&counts);

    // Find dominant observers (>15% of first-sees)
    let total_txs = tx_first_seen.len();
    let threshold = total_txs as f64 * 0.15;
    let dominant_observers: Vec<String> = first_seen_counts
        .iter()
        .filter(|(_, &count)| count as f64 > threshold)
        .map(|(node_id, _)| node_id.clone())
        .collect();

    // Calculate miner first-seen ratio
    let miner_ids: HashSet<&str> = agents
        .iter()
        .filter(|a| a.script_type.contains("miner"))
        .map(|a| a.id.as_str())
        .collect();

    let miner_first_seen: usize = tx_first_seen
        .values()
        .filter(|(node_id, _)| miner_ids.contains(node_id.as_str()))
        .count();

    let miner_first_seen_ratio = if total_txs > 0 {
        miner_first_seen as f64 / total_txs as f64
    } else {
        0.0
    };

    CentralizationMetrics {
        first_seen_gini,
        dominant_observers,
        miner_first_seen_ratio,
    }
}

/// Analyze partition risk
fn analyze_partition_risk(graph: &HashMap<String, HashSet<String>>) -> PartitionRiskMetrics {
    // Find connected components using simple BFS
    let components = find_connected_components(graph);

    // Find bridge nodes (simplified: nodes with high betweenness)
    let bridge_nodes = find_bridge_nodes(graph);

    PartitionRiskMetrics {
        bridge_nodes,
        connected_components: components.len(),
    }
}

/// Find connected components using BFS
fn find_connected_components(graph: &HashMap<String, HashSet<String>>) -> Vec<HashSet<String>> {
    let mut visited: HashSet<String> = HashSet::new();
    let mut components: Vec<HashSet<String>> = Vec::new();

    for start_node in graph.keys() {
        if visited.contains(start_node) {
            continue;
        }

        let mut component: HashSet<String> = HashSet::new();
        let mut queue: Vec<String> = vec![start_node.clone()];

        while let Some(node) = queue.pop() {
            if visited.contains(&node) {
                continue;
            }

            visited.insert(node.clone());
            component.insert(node.clone());

            if let Some(neighbors) = graph.get(&node) {
                for neighbor in neighbors {
                    if !visited.contains(neighbor) && graph.contains_key(neighbor) {
                        queue.push(neighbor.clone());
                    }
                }
            }
        }

        if !component.is_empty() {
            components.push(component);
        }
    }

    components
}

/// Find bridge nodes (simplified heuristic: nodes with connections to multiple distinct groups)
fn find_bridge_nodes(graph: &HashMap<String, HashSet<String>>) -> Vec<String> {
    // Simplified approach: find nodes whose removal would increase component count
    // For efficiency, we just identify nodes with unique connections

    let mut bridge_candidates: Vec<(String, usize)> = Vec::new();

    for (node_id, neighbors) in graph {
        if neighbors.len() < 2 {
            continue;
        }

        // Count how many of this node's neighbors are NOT connected to each other
        let mut unconnected_pairs = 0;
        let neighbor_list: Vec<&String> = neighbors.iter().collect();

        for i in 0..neighbor_list.len() {
            for j in (i + 1)..neighbor_list.len() {
                let n1 = neighbor_list[i];
                let n2 = neighbor_list[j];

                // Check if n1 and n2 are connected (excluding through node_id)
                let n1_neighbors = graph.get(n1);
                let connected = n1_neighbors
                    .map(|ns| ns.contains(n2))
                    .unwrap_or(false);

                if !connected {
                    unconnected_pairs += 1;
                }
            }
        }

        if unconnected_pairs > 0 {
            bridge_candidates.push((node_id.clone(), unconnected_pairs));
        }
    }

    // Sort by bridge score (higher = more bridging)
    bridge_candidates.sort_by(|a, b| b.1.cmp(&a.1));

    // Return top candidates
    bridge_candidates
        .into_iter()
        .take(5)
        .map(|(node_id, _)| node_id)
        .collect()
}
