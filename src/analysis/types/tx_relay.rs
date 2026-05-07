//! TX Relay V2 protocol analysis types.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

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
