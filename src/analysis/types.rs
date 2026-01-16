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

/// TX relay protocol version
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TxRelayProtocol {
    /// V1: Full transaction broadcast via NOTIFY_NEW_TRANSACTIONS
    V1,
    /// V2: Hash announcement + request via NOTIFY_TX_POOL_HASH / NOTIFY_REQUEST_TX_POOL_TXS
    V2,
}

/// TX hash announcement (v2 protocol)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TxHashAnnouncement {
    pub timestamp: SimTime,
    pub node_id: String,
    pub source_ip: String,
    pub direction: ConnectionDirection,
    pub tx_count: usize,
    pub tx_hashes: Vec<String>, // May be empty if not logged individually
}

/// TX request event (v2 protocol)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TxRequest {
    pub timestamp: SimTime,
    pub node_id: String,
    pub target_ip: String,
    pub tx_count: usize,
    pub is_outgoing: bool, // true = we sent request, false = we received request
}

/// Connection drop event with reason
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectionDrop {
    pub timestamp: SimTime,
    pub node_id: String,
    pub peer_ip: String,
    pub reason: String,
}

/// All log data parsed from a single node
#[derive(Debug, Clone, Default)]
pub struct NodeLogData {
    pub node_id: String,
    pub tx_observations: Vec<TxObservation>,
    pub connection_events: Vec<ConnectionEvent>,
    pub block_observations: Vec<BlockObservation>,
    // TX Relay V2 specific
    pub tx_hash_announcements: Vec<TxHashAnnouncement>,
    pub tx_requests: Vec<TxRequest>,
    pub connection_drops: Vec<ConnectionDrop>,
}

impl NodeLogData {
    pub fn new(node_id: String) -> Self {
        Self {
            node_id,
            tx_observations: Vec::new(),
            connection_events: Vec::new(),
            block_observations: Vec::new(),
            tx_hash_announcements: Vec::new(),
            tx_requests: Vec::new(),
            connection_drops: Vec::new(),
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

// ============================================================================
// TX Relay V2 Protocol Analysis Types
// ============================================================================

/// Protocol usage statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProtocolUsageStats {
    /// Total NOTIFY_NEW_TRANSACTIONS messages (v1)
    pub v1_tx_broadcasts: usize,
    /// Total NOTIFY_TX_POOL_HASH messages (v2)
    pub v2_hash_announcements: usize,
    /// Total NOTIFY_REQUEST_TX_POOL_TXS messages (v2)
    pub v2_tx_requests: usize,
    /// Ratio of v2 to total protocol messages
    pub v2_usage_ratio: f64,
}

/// TX delivery analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TxDeliveryAnalysis {
    /// Total transactions created
    pub total_txs_created: usize,
    /// Transactions that reached all nodes
    pub txs_fully_propagated: usize,
    /// Transactions that were included in blocks
    pub txs_in_blocks: usize,
    /// Transactions that may have been lost (created but never observed)
    pub txs_potentially_lost: Vec<String>,
    /// Per-node delivery rate
    pub per_node_delivery_rate: HashMap<String, f64>,
    /// Average propagation coverage (% of nodes reached)
    pub average_propagation_coverage: f64,
}

/// Connection stability metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectionStabilityMetrics {
    /// Total connection drops observed
    pub total_drops: usize,
    /// Drops due to TX verification failure
    pub drops_tx_verification: usize,
    /// Drops due to duplicate TX
    pub drops_duplicate_tx: usize,
    /// Drops due to protocol violations
    pub drops_protocol_violation: usize,
    /// Drops with other/unknown reasons
    pub drops_other: usize,
    /// Per-node drop counts
    pub drops_by_node: HashMap<String, usize>,
    /// Average connection duration (seconds)
    pub average_connection_duration_sec: f64,
}

/// Request/response efficiency for v2 protocol
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RequestResponseMetrics {
    /// Total TX requests sent
    pub requests_sent: usize,
    /// Total TX requests received (from peers)
    pub requests_received: usize,
    /// Estimated fulfilled requests (TX received after request)
    pub requests_fulfilled: usize,
    /// Request fulfillment ratio
    pub fulfillment_ratio: f64,
}

/// Full TX relay v2 comparison report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TxRelayV2Report {
    /// Protocol usage statistics
    pub protocol_usage: ProtocolUsageStats,
    /// TX delivery analysis
    pub delivery_analysis: TxDeliveryAnalysis,
    /// Connection stability
    pub connection_stability: ConnectionStabilityMetrics,
    /// Request/response metrics (v2 only)
    pub request_response: RequestResponseMetrics,
    /// Summary assessment
    pub assessment: TxRelayAssessment,
}

/// Assessment of tx relay behavior
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TxRelayAssessment {
    /// Overall health score (0-100)
    pub health_score: u32,
    /// Is v2 protocol being used?
    pub v2_active: bool,
    /// Any transactions lost?
    pub has_lost_txs: bool,
    /// Connection stability issues?
    pub has_stability_issues: bool,
    /// Detailed findings
    pub findings: Vec<String>,
    /// Recommendations
    pub recommendations: Vec<String>,
}

// ============================================================================
// Dandelion++ Stem Path Analysis Types
// ============================================================================

/// A single hop in the stem path
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StemHop {
    /// Node that received the TX at this hop
    pub node_id: String,
    /// Node that sent the TX (None for originator)
    pub from_node_id: Option<String>,
    /// Source IP of sender
    pub from_ip: String,
    /// Timestamp when received
    pub timestamp: SimTime,
    /// Time delta from previous hop (ms)
    pub delta_ms: f64,
}

/// Reconstructed Dandelion++ path for a single transaction
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DandelionPath {
    /// Transaction hash
    pub tx_hash: String,
    /// True originator (from transactions.json)
    pub originator: String,
    /// Originator's IP address
    pub originator_ip: Option<String>,
    /// The stem path (sequence of hops before fluff)
    pub stem_path: Vec<StemHop>,
    /// Node that initiated the fluff (broadcast)
    pub fluff_node: Option<String>,
    /// Number of hops in stem phase
    pub stem_length: usize,
    /// Time spent in stem phase (ms)
    pub stem_duration_ms: f64,
    /// Total nodes that received during fluff
    pub fluff_recipients: usize,
    /// Did the first hop match the originator? (sanity check)
    pub originator_confirmed: bool,
}

/// Statistics about a node's role in Dandelion++
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeDandelionStats {
    pub node_id: String,
    /// Times this node was in a stem path (as relay)
    pub stem_relay_count: usize,
    /// Times this node was the fluff point
    pub fluff_point_count: usize,
    /// Times this node originated a TX
    pub originator_count: usize,
    /// Average position in stem (1 = first hop after originator)
    pub avg_stem_position: f64,
}

/// Dandelion++ analysis report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DandelionReport {
    /// Total transactions analyzed
    pub total_transactions: usize,
    /// Transactions with reconstructable paths
    pub paths_reconstructed: usize,
    /// Transactions where originator was confirmed in path
    pub originator_confirmed_count: usize,

    /// Stem length statistics
    pub avg_stem_length: f64,
    pub min_stem_length: usize,
    pub max_stem_length: usize,
    pub stem_length_distribution: HashMap<usize, usize>,

    /// Stem timing statistics
    pub avg_stem_duration_ms: f64,
    pub avg_hop_delay_ms: f64,

    /// Per-node statistics
    pub node_stats: Vec<NodeDandelionStats>,

    /// Nodes that frequently act as fluff points (potential privacy concern)
    pub frequent_fluff_nodes: Vec<(String, usize)>,

    /// Per-transaction path details
    pub paths: Vec<DandelionPath>,

    /// Privacy assessment
    pub privacy_assessment: DandelionPrivacyAssessment,
}

/// Privacy assessment based on Dandelion++ behavior
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DandelionPrivacyAssessment {
    /// Overall privacy score (0-100)
    pub privacy_score: u32,
    /// Is Dandelion++ effectively hiding originators?
    pub effective_anonymity: bool,
    /// Percentage of TXs where originator could be trivially identified
    pub trivially_deanonymizable_pct: f64,
    /// Findings and concerns
    pub findings: Vec<String>,
    /// Recommendations
    pub recommendations: Vec<String>,
}
