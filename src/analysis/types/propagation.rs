//! Transaction propagation analysis result types.

use serde::{Deserialize, Serialize};

use super::core::SimTime;

/// Propagation analysis for a single transaction
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PropagationAnalysis {
    pub tx_hash: String,
    pub creation_time: SimTime,
    pub first_seen_time: Option<SimTime>,
    pub block_inclusion_time: Option<SimTime>,
    pub confirmation_delay_sec: Option<f64>,
    pub network_propagation_time_ms: f64,
    pub median_propagation_ms: f64,
    pub p95_propagation_ms: f64,
    pub nodes_observed: usize,
    pub total_nodes: usize,
    pub propagation_coverage: f64,
}

/// Aggregated propagation report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PropagationReport {
    pub total_transactions: usize,
    pub analyzed_transactions: usize,
    pub average_propagation_ms: f64,
    pub median_propagation_ms: f64,
    pub p95_propagation_ms: f64,
    pub average_confirmation_delay_sec: f64,
    pub bottleneck_nodes: Vec<BottleneckNode>,
    pub per_tx_analysis: Vec<PropagationAnalysis>,
}

/// A node that is consistently slow to receive transactions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BottleneckNode {
    pub node_id: String,
    pub average_delay_ms: f64,
    pub observations: usize,
}
