//! Transaction propagation timing analysis.
//!
//! Analyzes how quickly transactions propagate through the network and
//! identifies bottleneck nodes.

use std::collections::HashMap;

use super::types::*;

/// Analyze propagation timing for all transactions
pub fn analyze_propagation(
    transactions: &[Transaction],
    blocks: &[BlockInfo],
    log_data: &HashMap<String, NodeLogData>,
    total_nodes: usize,
) -> PropagationReport {
    // Build TX hash to block inclusion time mapping
    let mut tx_to_block: HashMap<String, (u64, SimTime)> = HashMap::new();

    // We need to estimate block times from log data
    // Collect all block observations and find the earliest time for each height
    let mut block_times: HashMap<u64, SimTime> = HashMap::new();
    for (_, node_data) in log_data {
        for obs in &node_data.block_observations {
            block_times
                .entry(obs.height)
                .and_modify(|t| {
                    if obs.timestamp < *t {
                        *t = obs.timestamp;
                    }
                })
                .or_insert(obs.timestamp);
        }
    }

    // Map TX hashes to their block inclusion time
    for block in blocks {
        if let Some(&block_time) = block_times.get(&block.height) {
            for tx_hash in &block.transactions {
                tx_to_block.insert(tx_hash.clone(), (block.height, block_time));
            }
        }
    }

    // Build TX hash to observations mapping
    let mut tx_observations: HashMap<String, Vec<&TxObservation>> = HashMap::new();
    for (_, node_data) in log_data {
        for obs in &node_data.tx_observations {
            tx_observations
                .entry(obs.tx_hash.clone())
                .or_default()
                .push(obs);
        }
    }

    // Analyze each transaction
    let analyses: Vec<PropagationAnalysis> = transactions
        .iter()
        .filter_map(|tx| {
            let observations = tx_observations.get(&tx.tx_hash)?;
            Some(analyze_single_tx_propagation(
                tx,
                observations,
                tx_to_block.get(&tx.tx_hash).cloned(),
                total_nodes,
            ))
        })
        .collect();

    // Calculate aggregate statistics
    let propagation_times: Vec<f64> = analyses
        .iter()
        .map(|a| a.network_propagation_time_ms)
        .collect();

    let confirmation_delays: Vec<f64> = analyses
        .iter()
        .filter_map(|a| a.confirmation_delay_sec)
        .collect();

    // Find bottleneck nodes
    let bottleneck_nodes = identify_bottlenecks(&analyses, &tx_observations);

    PropagationReport {
        total_transactions: transactions.len(),
        analyzed_transactions: analyses.len(),
        average_propagation_ms: mean(&propagation_times),
        median_propagation_ms: median(&propagation_times),
        p95_propagation_ms: percentile(&propagation_times, 95.0),
        average_confirmation_delay_sec: mean(&confirmation_delays),
        bottleneck_nodes,
        per_tx_analysis: analyses,
    }
}

/// Analyze propagation for a single transaction
fn analyze_single_tx_propagation(
    tx: &Transaction,
    observations: &[&TxObservation],
    block_info: Option<(u64, SimTime)>,
    total_nodes: usize,
) -> PropagationAnalysis {
    // Sort observations by timestamp
    let mut sorted_obs: Vec<&TxObservation> = observations.to_vec();
    sorted_obs.sort_by(|a, b| {
        a.timestamp.partial_cmp(&b.timestamp).unwrap_or(std::cmp::Ordering::Equal)
    });

    let first_seen_time = sorted_obs.first().map(|o| o.timestamp);
    let last_seen_time = sorted_obs.last().map(|o| o.timestamp);

    // Calculate propagation times relative to first observation
    let propagation_times: Vec<f64> = sorted_obs
        .iter()
        .map(|o| (o.timestamp - first_seen_time.unwrap_or(o.timestamp)) * 1000.0)
        .collect();

    let network_propagation_time_ms = match (first_seen_time, last_seen_time) {
        (Some(first), Some(last)) => (last - first) * 1000.0,
        _ => 0.0,
    };

    // Calculate confirmation delay
    let (block_inclusion_time, confirmation_delay_sec) = match block_info {
        Some((_, block_time)) => (
            Some(block_time),
            Some(block_time - tx.timestamp),
        ),
        None => (None, None),
    };

    // Count unique nodes that observed this TX
    let mut unique_nodes: std::collections::HashSet<&str> = std::collections::HashSet::new();
    for obs in &sorted_obs {
        unique_nodes.insert(&obs.node_id);
    }
    let nodes_observed = unique_nodes.len();

    let propagation_coverage = if total_nodes > 0 {
        nodes_observed as f64 / total_nodes as f64
    } else {
        0.0
    };

    PropagationAnalysis {
        tx_hash: tx.tx_hash.clone(),
        creation_time: tx.timestamp,
        first_seen_time,
        block_inclusion_time,
        confirmation_delay_sec,
        network_propagation_time_ms,
        median_propagation_ms: median(&propagation_times),
        p95_propagation_ms: percentile(&propagation_times, 95.0),
        nodes_observed,
        total_nodes,
        propagation_coverage,
    }
}

/// Identify nodes that are consistently slow to receive transactions
fn identify_bottlenecks(
    _analyses: &[PropagationAnalysis],
    tx_observations: &HashMap<String, Vec<&TxObservation>>,
) -> Vec<BottleneckNode> {
    // For each node, calculate average time to receive TXs relative to first seen
    let mut node_delays: HashMap<String, Vec<f64>> = HashMap::new();

    for (_tx_hash, observations) in tx_observations {
        if observations.is_empty() {
            continue;
        }

        // Find first observation time for this TX
        let first_time = observations
            .iter()
            .map(|o| o.timestamp)
            .min_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal))
            .unwrap_or(0.0);

        for obs in observations {
            let delay = (obs.timestamp - first_time) * 1000.0;
            node_delays
                .entry(obs.node_id.clone())
                .or_default()
                .push(delay);
        }
    }

    // Find nodes with consistently high delays
    let mut bottlenecks: Vec<BottleneckNode> = node_delays
        .into_iter()
        .filter(|(_, delays)| delays.len() >= 3) // Need at least 3 observations
        .map(|(node_id, delays)| {
            let avg_delay = mean(&delays);
            BottleneckNode {
                node_id,
                average_delay_ms: avg_delay,
                observations: delays.len(),
            }
        })
        .filter(|b| b.average_delay_ms > 200.0) // Threshold for "slow"
        .collect();

    // Sort by average delay (highest first)
    bottlenecks.sort_by(|a, b| {
        b.average_delay_ms
            .partial_cmp(&a.average_delay_ms)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    bottlenecks.truncate(10);

    bottlenecks
}

/// Calculate mean of a slice
fn mean(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    values.iter().sum::<f64>() / values.len() as f64
}

/// Calculate median of a slice
fn median(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let mid = sorted.len() / 2;
    if sorted.len() % 2 == 0 {
        (sorted[mid - 1] + sorted[mid]) / 2.0
    } else {
        sorted[mid]
    }
}

/// Calculate percentile of a slice
fn percentile(values: &[f64], p: f64) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let idx = ((p / 100.0) * (sorted.len() - 1) as f64).round() as usize;
    sorted[idx.min(sorted.len() - 1)]
}
