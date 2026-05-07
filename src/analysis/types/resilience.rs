//! Network resilience analysis types and the top-level full-analysis report aggregator.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use super::propagation::PropagationReport;
use super::spy::SpyNodeReport;

/// Network resilience metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResilienceMetrics {
    pub connectivity: ConnectivityMetrics,
    pub centralization: CentralizationMetrics,
    pub partition_risk: PartitionRiskMetrics,
}

/// Connectivity analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectivityMetrics {
    pub total_nodes: usize,
    pub average_peer_count: f64,
    pub min_peer_count: usize,
    pub max_peer_count: usize,
    pub isolated_nodes: Vec<String>,
    pub peer_count_distribution: HashMap<String, usize>,
}

/// Centralization analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CentralizationMetrics {
    /// Gini coefficient for first-seen TX observations (0=equal, 1=centralized)
    pub first_seen_gini: f64,
    /// Nodes that see >15% of TXs first
    pub dominant_observers: Vec<String>,
    /// How often miners see TXs first (should be ~random if healthy)
    pub miner_first_seen_ratio: f64,
}

/// Partition risk analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PartitionRiskMetrics {
    /// Nodes whose removal would significantly impact connectivity
    pub bridge_nodes: Vec<String>,
    /// Number of distinct network components
    pub connected_components: usize,
}

/// Complete analysis report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FullAnalysisReport {
    pub metadata: AnalysisMetadata,
    pub spy_node_analysis: Option<SpyNodeReport>,
    pub propagation_analysis: Option<PropagationReport>,
    pub resilience_analysis: Option<ResilienceMetrics>,
}

/// Report metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnalysisMetadata {
    pub analysis_timestamp: String,
    pub simulation_data_dir: String,
    pub total_nodes: usize,
    pub total_transactions: usize,
    pub total_blocks: usize,
}
