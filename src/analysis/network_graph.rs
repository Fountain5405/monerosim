//! Network graph analysis module.
//!
//! Provides detailed analysis of the P2P network topology including:
//! - Connection state tracking over time
//! - Degree distribution (inbound/outbound)
//! - Time-based topology snapshots
//! - GraphViz DOT output for visualization

use std::collections::{HashMap, HashSet};
use serde::{Deserialize, Serialize};

use super::types::*;

/// A snapshot of the network graph at a specific point in time
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkSnapshot {
    /// Simulation time of this snapshot
    pub timestamp: SimTime,
    /// Human-readable time description
    pub time_label: String,
    /// Number of active connections
    pub total_connections: usize,
    /// Per-node connection counts
    pub node_degrees: HashMap<String, NodeDegree>,
    /// Average outbound connections
    pub avg_outbound: f64,
    /// Average inbound connections
    pub avg_inbound: f64,
    /// Nodes with no connections
    pub isolated_nodes: Vec<String>,
}

/// Degree information for a single node
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeDegree {
    pub node_id: String,
    pub outbound: usize,
    pub inbound: usize,
    pub total: usize,
}

/// A directed edge in the network graph
#[derive(Debug, Clone, Hash, Eq, PartialEq)]
pub struct Edge {
    pub from_node: String,
    pub to_node: String,
}

/// Active connection with metadata
#[derive(Debug, Clone)]
struct ActiveConnection {
    #[allow(dead_code)]
    peer_ip: String,
    peer_node: Option<String>,
    direction: ConnectionDirection,
    open_time: SimTime,
}

/// Full network graph analysis report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkGraphReport {
    /// Analysis metadata
    pub total_daemon_nodes: usize,
    pub total_unique_connections: usize,
    pub analysis_duration_sec: f64,

    /// Snapshots at key points in time
    pub snapshots: Vec<NetworkSnapshot>,

    /// Final state analysis
    pub final_state: NetworkSnapshot,

    /// Degree distribution at end of simulation
    pub degree_distribution: DegreeDistribution,

    /// Connection churn statistics
    pub churn_stats: ConnectionChurnStats,

    /// Validation against expected Monero defaults
    pub validation: NetworkValidation,
}

/// Degree distribution statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DegreeDistribution {
    /// Outbound degree histogram (degree -> count of nodes)
    pub outbound_histogram: HashMap<usize, usize>,
    /// Inbound degree histogram
    pub inbound_histogram: HashMap<usize, usize>,
    /// Total degree histogram
    pub total_histogram: HashMap<usize, usize>,
    /// Statistical summary
    pub outbound_stats: DegreeStats,
    pub inbound_stats: DegreeStats,
}

/// Statistical summary of degrees
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DegreeStats {
    pub min: usize,
    pub max: usize,
    pub mean: f64,
    pub median: f64,
    pub std_dev: f64,
}

/// Connection churn statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectionChurnStats {
    /// Total connection open events
    pub total_opens: usize,
    /// Total connection close events
    pub total_closes: usize,
    /// Average connection duration in seconds
    pub avg_duration_sec: f64,
    /// Median connection duration
    pub median_duration_sec: f64,
    /// Connections that lasted the entire simulation
    pub long_lived_connections: usize,
    /// Short-lived connections (< 60 seconds)
    pub short_lived_connections: usize,
}

/// Validation against expected network properties
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkValidation {
    /// Expected max outbound (Monero default: 8)
    pub expected_max_outbound: usize,
    /// Actual max outbound observed
    pub actual_max_outbound: usize,
    /// Is outbound within expected limits?
    pub outbound_valid: bool,
    /// Nodes exceeding outbound limit
    pub nodes_exceeding_outbound: Vec<String>,
    /// Findings
    pub findings: Vec<String>,
}

/// Analyze the network graph from connection events
pub fn analyze_network_graph(
    log_data: &HashMap<String, NodeLogData>,
    agents: &[AnalysisAgentInfo],
    snapshot_times: Option<Vec<SimTime>>,
) -> NetworkGraphReport {
    // Build IP to node mapping (only for daemon nodes)
    let daemon_agents: Vec<&AnalysisAgentInfo> = agents
        .iter()
        .filter(|a| !a.script_type.contains("distributor") && !a.script_type.contains("monitor"))
        .collect();

    let ip_to_node: HashMap<&str, &str> = daemon_agents
        .iter()
        .map(|a| (a.ip_addr.as_str(), a.id.as_str()))
        .collect();

    let daemon_node_ids: HashSet<&str> = daemon_agents
        .iter()
        .map(|a| a.id.as_str())
        .collect();

    // Collect all connection events sorted by time
    let mut all_events: Vec<(SimTime, &str, &ConnectionEvent)> = Vec::new();

    for (node_id, node_data) in log_data {
        if !daemon_node_ids.contains(node_id.as_str()) {
            continue;
        }
        for event in &node_data.connection_events {
            all_events.push((event.timestamp, node_id.as_str(), event));
        }
    }

    all_events.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));

    // Determine simulation time range
    let start_time = all_events.first().map(|(t, _, _)| *t).unwrap_or(0.0);
    let end_time = all_events.last().map(|(t, _, _)| *t).unwrap_or(0.0);
    let duration = end_time - start_time;

    // Default snapshot times if not provided
    let snapshot_times = snapshot_times.unwrap_or_else(|| {
        let mut times = vec![start_time];
        // Add snapshots at 25%, 50%, 75%, and 100% of simulation
        for pct in [0.25, 0.5, 0.75, 1.0] {
            times.push(start_time + duration * pct);
        }
        times
    });

    // Track connection state over time
    // node_id -> connection_id -> ActiveConnection
    let mut connection_state: HashMap<String, HashMap<String, ActiveConnection>> = HashMap::new();

    // Initialize all nodes
    for agent in &daemon_agents {
        connection_state.insert(agent.id.clone(), HashMap::new());
    }

    // Track connection durations for churn analysis
    let mut connection_durations: Vec<f64> = Vec::new();
    let mut total_opens = 0usize;
    let mut total_closes = 0usize;

    // Track snapshots
    let mut snapshots: Vec<NetworkSnapshot> = Vec::new();
    let mut snapshot_idx = 0;

    // Process events in chronological order
    for (timestamp, node_id, event) in &all_events {
        // Take snapshot if we've passed the snapshot time
        while snapshot_idx < snapshot_times.len() && *timestamp >= snapshot_times[snapshot_idx] {
            let snapshot = create_snapshot(
                snapshot_times[snapshot_idx],
                &connection_state,
                &ip_to_node,
                &daemon_node_ids,
            );
            snapshots.push(snapshot);
            snapshot_idx += 1;
        }

        let node_connections = connection_state.entry(node_id.to_string()).or_default();

        if event.is_open {
            total_opens += 1;

            // Resolve peer IP to node ID
            let peer_node = ip_to_node.get(event.peer_ip.as_str()).map(|s| s.to_string());

            // Only track connections to other daemon nodes
            if peer_node.is_some() {
                node_connections.insert(
                    event.connection_id.clone(),
                    ActiveConnection {
                        peer_ip: event.peer_ip.clone(),
                        peer_node,
                        direction: event.direction,
                        open_time: *timestamp,
                    },
                );
            }
        } else {
            total_closes += 1;

            // Record duration if we were tracking this connection
            if let Some(conn) = node_connections.remove(&event.connection_id) {
                let duration = timestamp - conn.open_time;
                connection_durations.push(duration);
            }
        }
    }

    // Create final snapshot
    let final_state = create_snapshot(end_time, &connection_state, &ip_to_node, &daemon_node_ids);

    // Calculate degree distribution from final state
    let degree_distribution = calculate_degree_distribution(&final_state);

    // Calculate churn statistics
    let churn_stats = calculate_churn_stats(
        total_opens,
        total_closes,
        &connection_durations,
        &connection_state,
        duration,
    );

    // Validate against expected Monero defaults
    let validation = validate_network(&final_state, 8); // Monero default is 8 outbound

    // Count unique connections ever observed
    let mut unique_edges: HashSet<(String, String)> = HashSet::new();
    for (node_id, node_data) in log_data {
        for event in &node_data.connection_events {
            if event.is_open {
                if let Some(&peer_node) = ip_to_node.get(event.peer_ip.as_str()) {
                    unique_edges.insert((node_id.clone(), peer_node.to_string()));
                }
            }
        }
    }

    NetworkGraphReport {
        total_daemon_nodes: daemon_agents.len(),
        total_unique_connections: unique_edges.len(),
        analysis_duration_sec: duration,
        snapshots,
        final_state,
        degree_distribution,
        churn_stats,
        validation,
    }
}

/// Create a network snapshot at a specific point in time
fn create_snapshot(
    timestamp: SimTime,
    connection_state: &HashMap<String, HashMap<String, ActiveConnection>>,
    _ip_to_node: &HashMap<&str, &str>,
    daemon_nodes: &HashSet<&str>,
) -> NetworkSnapshot {
    let mut node_degrees: HashMap<String, NodeDegree> = HashMap::new();
    let mut total_connections = 0usize;

    // Initialize all daemon nodes
    for &node_id in daemon_nodes {
        node_degrees.insert(node_id.to_string(), NodeDegree {
            node_id: node_id.to_string(),
            outbound: 0,
            inbound: 0,
            total: 0,
        });
    }

    // Count connections per node
    for (node_id, connections) in connection_state {
        if !daemon_nodes.contains(node_id.as_str()) {
            continue;
        }

        for conn in connections.values() {
            // Only count connections to other daemon nodes
            if conn.peer_node.is_none() {
                continue;
            }

            total_connections += 1;

            let degree = node_degrees.entry(node_id.clone()).or_insert(NodeDegree {
                node_id: node_id.clone(),
                outbound: 0,
                inbound: 0,
                total: 0,
            });

            match conn.direction {
                ConnectionDirection::Outbound => degree.outbound += 1,
                ConnectionDirection::Inbound => degree.inbound += 1,
            }
            degree.total += 1;
        }
    }

    // Calculate averages
    let outbound_sum: usize = node_degrees.values().map(|d| d.outbound).sum();
    let inbound_sum: usize = node_degrees.values().map(|d| d.inbound).sum();
    let node_count = node_degrees.len();

    let avg_outbound = if node_count > 0 {
        outbound_sum as f64 / node_count as f64
    } else {
        0.0
    };

    let avg_inbound = if node_count > 0 {
        inbound_sum as f64 / node_count as f64
    } else {
        0.0
    };

    // Find isolated nodes
    let isolated_nodes: Vec<String> = node_degrees
        .iter()
        .filter(|(_, d)| d.total == 0)
        .map(|(id, _)| id.clone())
        .collect();

    // Create human-readable time label
    let hours = (timestamp / 3600.0) as u32;
    let minutes = ((timestamp % 3600.0) / 60.0) as u32;
    let time_label = format!("t={}h{}m", hours, minutes);

    NetworkSnapshot {
        timestamp,
        time_label,
        total_connections,
        node_degrees,
        avg_outbound,
        avg_inbound,
        isolated_nodes,
    }
}

/// Calculate degree distribution statistics
fn calculate_degree_distribution(snapshot: &NetworkSnapshot) -> DegreeDistribution {
    let mut outbound_histogram: HashMap<usize, usize> = HashMap::new();
    let mut inbound_histogram: HashMap<usize, usize> = HashMap::new();
    let mut total_histogram: HashMap<usize, usize> = HashMap::new();

    let mut outbound_values: Vec<usize> = Vec::new();
    let mut inbound_values: Vec<usize> = Vec::new();

    for degree in snapshot.node_degrees.values() {
        *outbound_histogram.entry(degree.outbound).or_insert(0) += 1;
        *inbound_histogram.entry(degree.inbound).or_insert(0) += 1;
        *total_histogram.entry(degree.total).or_insert(0) += 1;

        outbound_values.push(degree.outbound);
        inbound_values.push(degree.inbound);
    }

    DegreeDistribution {
        outbound_histogram,
        inbound_histogram,
        total_histogram,
        outbound_stats: calculate_stats(&outbound_values),
        inbound_stats: calculate_stats(&inbound_values),
    }
}

/// Calculate statistical summary
fn calculate_stats(values: &[usize]) -> DegreeStats {
    if values.is_empty() {
        return DegreeStats {
            min: 0,
            max: 0,
            mean: 0.0,
            median: 0.0,
            std_dev: 0.0,
        };
    }

    let mut sorted = values.to_vec();
    sorted.sort();

    let min = *sorted.first().unwrap();
    let max = *sorted.last().unwrap();
    let sum: usize = sorted.iter().sum();
    let mean = sum as f64 / sorted.len() as f64;

    let median = if sorted.len() % 2 == 0 {
        (sorted[sorted.len() / 2 - 1] + sorted[sorted.len() / 2]) as f64 / 2.0
    } else {
        sorted[sorted.len() / 2] as f64
    };

    let variance: f64 = sorted
        .iter()
        .map(|&v| {
            let diff = v as f64 - mean;
            diff * diff
        })
        .sum::<f64>()
        / sorted.len() as f64;

    let std_dev = variance.sqrt();

    DegreeStats {
        min,
        max,
        mean,
        median,
        std_dev,
    }
}

/// Calculate connection churn statistics
fn calculate_churn_stats(
    total_opens: usize,
    total_closes: usize,
    durations: &[f64],
    final_state: &HashMap<String, HashMap<String, ActiveConnection>>,
    _sim_duration: f64,
) -> ConnectionChurnStats {
    let avg_duration_sec = if durations.is_empty() {
        0.0
    } else {
        durations.iter().sum::<f64>() / durations.len() as f64
    };

    let median_duration_sec = if durations.is_empty() {
        0.0
    } else {
        let mut sorted = durations.to_vec();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        sorted[sorted.len() / 2]
    };

    // Count connections still active at end (long-lived)
    let long_lived: usize = final_state
        .values()
        .map(|conns| conns.len())
        .sum();

    // Count short-lived connections (< 60 seconds)
    let short_lived = durations.iter().filter(|&&d| d < 60.0).count();

    ConnectionChurnStats {
        total_opens,
        total_closes,
        avg_duration_sec,
        median_duration_sec,
        long_lived_connections: long_lived,
        short_lived_connections: short_lived,
    }
}

/// Validate network against expected properties
fn validate_network(snapshot: &NetworkSnapshot, expected_max_outbound: usize) -> NetworkValidation {
    let actual_max_outbound = snapshot
        .node_degrees
        .values()
        .map(|d| d.outbound)
        .max()
        .unwrap_or(0);

    let nodes_exceeding: Vec<String> = snapshot
        .node_degrees
        .iter()
        .filter(|(_, d)| d.outbound > expected_max_outbound)
        .map(|(id, _)| id.clone())
        .collect();

    let outbound_valid = nodes_exceeding.is_empty();

    let mut findings = Vec::new();

    if !outbound_valid {
        findings.push(format!(
            "{} nodes exceed expected outbound limit of {}",
            nodes_exceeding.len(),
            expected_max_outbound
        ));
    }

    if snapshot.isolated_nodes.len() > 0 {
        findings.push(format!(
            "{} nodes are isolated (no connections)",
            snapshot.isolated_nodes.len()
        ));
    }

    let avg_total = snapshot.avg_outbound + snapshot.avg_inbound;
    if avg_total < 4.0 {
        findings.push(format!(
            "Low average peer count ({:.1}) may indicate connectivity issues",
            avg_total
        ));
    }

    if findings.is_empty() {
        findings.push("Network topology appears healthy".to_string());
    }

    NetworkValidation {
        expected_max_outbound,
        actual_max_outbound,
        outbound_valid,
        nodes_exceeding_outbound: nodes_exceeding,
        findings,
    }
}

/// Generate GraphViz DOT format for visualization
pub fn generate_dot(snapshot: &NetworkSnapshot, _agents: &[AnalysisAgentInfo]) -> String {
    let mut dot = String::new();
    dot.push_str("digraph MoneroNetwork {\n");
    dot.push_str("    rankdir=LR;\n");
    dot.push_str("    node [shape=circle];\n");
    dot.push_str(&format!("    label=\"Network at {}\";\n", snapshot.time_label));
    dot.push_str("    labelloc=t;\n\n");

    // Create node labels with degree info
    for (node_id, degree) in &snapshot.node_degrees {
        let color = if degree.total == 0 {
            "red"
        } else if node_id.starts_with("miner") {
            "gold"
        } else {
            "lightblue"
        };

        dot.push_str(&format!(
            "    \"{}\" [label=\"{}\\n({}/{})\", fillcolor={}, style=filled];\n",
            node_id,
            node_id,
            degree.outbound,
            degree.inbound,
            color
        ));
    }

    dot.push_str("\n");

    // Note: We don't have edge information in the snapshot
    // For full edge visualization, we'd need to pass the connection state

    dot.push_str("}\n");
    dot
}
