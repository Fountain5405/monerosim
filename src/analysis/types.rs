//! Core data types for transaction routing analysis.

use std::collections::HashMap;
use serde::{Deserialize, Serialize};

/// Simulation timestamp in seconds since epoch (946684800 = 2000-01-01 00:00:00 UTC)
pub type SimTime = f64;

/// A transaction as recorded in transactions.json
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    pub tx_hash: String,
    pub sender_id: String,
    pub recipient_id: String,
    pub amount: f64,
    pub timestamp: SimTime,
}

/// Block information from blocks_with_transactions.json
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockInfo {
    pub height: u64,
    pub transactions: Vec<String>,
    pub tx_count: usize,
}

/// Agent information from agent_registry.json
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentInfo {
    pub id: String,
    pub ip_addr: String,
    pub rpc_port: u16,
    pub script_type: String,
    #[serde(default)]
    pub wallet_address: Option<String>,
}

/// Connection direction from log entries
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConnectionDirection {
    /// INC - peer connected to us
    Inbound,
    /// OUT - we connected to peer
    Outbound,
}

impl std::fmt::Display for ConnectionDirection {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ConnectionDirection::Inbound => write!(f, "INC"),
            ConnectionDirection::Outbound => write!(f, "OUT"),
        }
    }
}

/// A single observation of a transaction at a node
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TxObservation {
    pub tx_hash: String,
    pub node_id: String,
    pub timestamp: SimTime,
    pub source_ip: String,
    pub source_port: u16,
    pub direction: ConnectionDirection,
}

/// Connection event parsed from logs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectionEvent {
    pub timestamp: SimTime,
    pub peer_ip: String,
    pub peer_port: u16,
    pub connection_id: String,
    pub direction: ConnectionDirection,
    pub is_open: bool,
}

/// Block observation parsed from logs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockObservation {
    pub block_hash: String,
    pub height: u64,
    pub node_id: String,
    pub timestamp: SimTime,
    pub source_ip: Option<String>,
    pub is_local: bool,
}

/// All log data parsed from a single node
#[derive(Debug, Clone, Default)]
pub struct NodeLogData {
    pub node_id: String,
    pub tx_observations: Vec<TxObservation>,
    pub connection_events: Vec<ConnectionEvent>,
    pub block_observations: Vec<BlockObservation>,
}

impl NodeLogData {
    pub fn new(node_id: String) -> Self {
        Self {
            node_id,
            tx_observations: Vec::new(),
            connection_events: Vec::new(),
            block_observations: Vec::new(),
        }
    }
}

/// First-seen entry for spy node analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FirstSeenEntry {
    pub node_id: String,
    pub timestamp: SimTime,
    pub delta_from_first_ms: f64,
    pub source_ip: String,
}

/// Result of spy node analysis for a single transaction
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpyNodeTxAnalysis {
    pub tx_hash: String,
    pub true_sender: String,
    pub true_sender_ip: Option<String>,
    pub first_seen_by: Vec<FirstSeenEntry>,
    pub correlation_confidence: f64,
    pub timing_spread_ms: f64,
    pub inferred_originator_ip: Option<String>,
    pub inference_correct: bool,
}

/// Aggregated spy node analysis report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpyNodeReport {
    pub total_transactions: usize,
    pub analyzable_transactions: usize,
    pub inference_accuracy: f64,
    pub timing_spread_distribution: TimingDistribution,
    pub vulnerable_senders: Vec<VulnerableSender>,
    pub per_tx_analysis: Vec<SpyNodeTxAnalysis>,
}

/// Distribution of timing spreads
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimingDistribution {
    pub high_vulnerability_count: usize,   // < 100ms
    pub moderate_vulnerability_count: usize, // 100-500ms
    pub low_vulnerability_count: usize,    // > 500ms
}

/// A sender that is particularly vulnerable to deanonymization
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VulnerableSender {
    pub sender_id: String,
    pub high_confidence_inferences: usize,
    pub accuracy: f64,
}

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
