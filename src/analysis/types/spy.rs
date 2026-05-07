//! Spy node analysis result types.

use serde::{Deserialize, Serialize};

use super::core::SimTime;

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
