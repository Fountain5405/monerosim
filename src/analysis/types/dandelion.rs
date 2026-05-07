//! Dandelion++ stem path analysis types.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use super::core::SimTime;

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
