//! Time-windowed analysis types used by the upgrade-impact pipeline.

use serde::{Deserialize, Serialize};

use super::core::SimTime;

/// A time window for segmented analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeWindow {
    /// Start time (inclusive)
    pub start: SimTime,
    /// End time (exclusive)
    pub end: SimTime,
    /// Optional label for the window
    pub label: Option<String>,
}

impl TimeWindow {
    pub fn new(start: SimTime, end: SimTime) -> Self {
        Self {
            start,
            end,
            label: None,
        }
    }

    pub fn contains(&self, timestamp: SimTime) -> bool {
        timestamp >= self.start && timestamp < self.end
    }
}

/// Metrics calculated for a single time window
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WindowedMetrics {
    /// The time window these metrics cover
    pub window: TimeWindow,
    /// Number of transactions created in this window
    pub tx_count: usize,
    /// Total observations in this window
    pub observation_count: usize,

    // Spy node metrics
    /// Synthetic spy accuracy at each visibility level (parallel to visibility_levels in metadata)
    pub spy_accuracy_by_visibility: Option<Vec<f64>>,
    /// Number of TXs analyzable for spy analysis
    pub spy_analyzable_txs: usize,

    // Propagation metrics
    /// Average propagation time (ms)
    pub avg_propagation_ms: Option<f64>,
    /// Median propagation time (ms)
    pub median_propagation_ms: Option<f64>,
    /// 95th percentile propagation (ms)
    pub p95_propagation_ms: Option<f64>,

    // Network metrics (snapshot at window end)
    /// Average peer count
    pub avg_peer_count: Option<f64>,
    /// Gini coefficient for first-seen distribution
    pub gini_coefficient: Option<f64>,

    // Dandelion metrics
    /// Average stem length
    pub avg_stem_length: Option<f64>,
    /// Average stem length at each fluff gap threshold (parallel to fluff_gap_thresholds_ms in metadata)
    pub stem_length_by_gap_threshold: Option<Vec<f64>>,
    /// Number of paths reconstructed
    pub paths_reconstructed: usize,

    // Bandwidth metrics
    /// Total bytes sent in this window
    pub bytes_sent: Option<u64>,
    /// Total bytes received in this window
    pub bytes_received: Option<u64>,
    /// Total bandwidth (sent + received)
    pub total_bandwidth: Option<u64>,
    /// Total message count
    pub bandwidth_message_count: Option<u64>,
}

impl Default for WindowedMetrics {
    fn default() -> Self {
        Self {
            window: TimeWindow::new(0.0, 0.0),
            tx_count: 0,
            observation_count: 0,
            spy_accuracy_by_visibility: None,
            spy_analyzable_txs: 0,
            avg_propagation_ms: None,
            median_propagation_ms: None,
            p95_propagation_ms: None,
            avg_peer_count: None,
            gini_coefficient: None,
            avg_stem_length: None,
            stem_length_by_gap_threshold: None,
            paths_reconstructed: 0,
            bytes_sent: None,
            bytes_received: None,
            total_bandwidth: None,
            bandwidth_message_count: None,
        }
    }
}

/// Aggregated metrics for a period (multiple windows)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AggregatedMetrics {
    /// Label for this period
    pub period_label: String,
    /// Start time of period
    pub start: SimTime,
    /// End time of period
    pub end: SimTime,
    /// Number of windows in this period
    pub window_count: usize,
    /// Total transactions in period
    pub total_txs: usize,

    // Aggregated metrics (mean of window values)
    /// Mean spy accuracy at each visibility level
    pub mean_spy_accuracy_by_visibility: Option<Vec<f64>>,
    pub mean_propagation_ms: Option<f64>,
    pub mean_peer_count: Option<f64>,
    pub mean_gini: Option<f64>,
    pub mean_stem_length: Option<f64>,
    /// Mean stem length at each fluff gap threshold
    pub mean_stem_length_by_gap_threshold: Option<Vec<f64>>,

    // Standard deviations (for significance testing)
    /// Std dev of spy accuracy at each visibility level
    pub std_spy_accuracy_by_visibility: Option<Vec<f64>>,
    pub std_propagation_ms: Option<f64>,
    pub std_peer_count: Option<f64>,
    pub std_gini: Option<f64>,
    pub std_stem_length: Option<f64>,
    /// Std dev of stem length at each fluff gap threshold
    pub std_stem_length_by_gap_threshold: Option<Vec<f64>>,

    // Bandwidth aggregates
    /// Total bytes sent in period
    pub total_bytes_sent: Option<u64>,
    /// Total bytes received in period
    pub total_bytes_received: Option<u64>,
    /// Total bandwidth in period
    pub total_bandwidth: Option<u64>,
    /// Mean bandwidth per window
    pub mean_bandwidth_per_window: Option<f64>,
    /// Standard deviation of bandwidth per window
    pub std_bandwidth_per_window: Option<f64>,

    /// Per-window metrics for detailed analysis
    pub windows: Vec<WindowedMetrics>,
}

/// A detected change in a metric between periods
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricChange {
    /// Name of the metric
    pub metric_name: String,
    /// Value before upgrade
    pub pre_value: f64,
    /// Value after upgrade
    pub post_value: f64,
    /// Absolute change
    pub absolute_change: f64,
    /// Percent change
    pub percent_change: f64,
    /// P-value from statistical test (lower = more significant)
    pub p_value: Option<f64>,
    /// Is the change statistically significant? (p < 0.05)
    pub statistically_significant: bool,
    /// Human-readable interpretation
    pub interpretation: String,
    /// Direction of impact (positive, negative, neutral)
    pub impact: ChangeImpact,
}

/// Direction and nature of a metric change
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ChangeImpact {
    /// Change is beneficial (e.g., faster propagation, better privacy)
    Positive,
    /// Change is harmful (e.g., slower propagation, worse privacy)
    Negative,
    /// Change is neutral or within normal variation
    Neutral,
}

/// Information about the upgrade being analyzed
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpgradeManifest {
    /// Version before upgrade
    pub pre_upgrade_version: Option<String>,
    /// Version after upgrade
    pub post_upgrade_version: Option<String>,
    /// Individual node upgrade events
    pub node_upgrades: Vec<NodeUpgradeEvent>,
    /// Timestamp when first node upgraded
    pub upgrade_start: Option<SimTime>,
    /// Timestamp when last node upgraded
    pub upgrade_end: Option<SimTime>,
}

/// A single node's upgrade event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeUpgradeEvent {
    pub node_id: String,
    pub timestamp: SimTime,
    pub version: String,
}

/// Complete upgrade impact analysis report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpgradeAnalysisReport {
    /// Analysis metadata
    pub metadata: UpgradeAnalysisMetadata,
    /// Information about the upgrade
    pub upgrade_info: Option<UpgradeManifest>,
    /// Per-window metrics (time series)
    pub time_series: Vec<WindowedMetrics>,
    /// Pre-upgrade period summary (if identifiable)
    pub pre_upgrade_summary: Option<AggregatedMetrics>,
    /// Transition period summary
    pub transition_summary: Option<AggregatedMetrics>,
    /// Post-upgrade period summary (if identifiable)
    pub post_upgrade_summary: Option<AggregatedMetrics>,
    /// Detected changes between pre and post upgrade
    pub changes: Vec<MetricChange>,
    /// Overall assessment
    pub assessment: UpgradeAssessment,
}

/// Metadata for upgrade analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpgradeAnalysisMetadata {
    pub analysis_timestamp: String,
    pub simulation_data_dir: String,
    pub simulation_start: SimTime,
    pub simulation_end: SimTime,
    pub window_size_sec: f64,
    pub total_windows: usize,
    pub total_nodes: usize,
    pub total_transactions: usize,
    /// Visibility levels used for synthetic spy analysis
    pub spy_visibility_levels: Vec<f64>,
    /// Number of random trials per visibility level
    pub spy_trials_per_level: usize,
    /// Gap thresholds (ms) used for multi-threshold stem length analysis
    pub fluff_gap_thresholds_ms: Vec<f64>,
}

/// Overall assessment of upgrade impact
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpgradeAssessment {
    /// Summary verdict
    pub verdict: UpgradeVerdict,
    /// Number of metrics that improved
    pub metrics_improved: usize,
    /// Number of metrics that degraded
    pub metrics_degraded: usize,
    /// Number of metrics unchanged
    pub metrics_unchanged: usize,
    /// Key findings
    pub findings: Vec<String>,
    /// Concerns (if any)
    pub concerns: Vec<String>,
    /// Recommendations
    pub recommendations: Vec<String>,
}

/// Overall verdict on upgrade impact
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum UpgradeVerdict {
    /// Upgrade improved network behavior
    Positive,
    /// Upgrade degraded network behavior
    Negative,
    /// Upgrade had mixed effects
    Mixed,
    /// No significant changes detected
    Neutral,
    /// Insufficient data for assessment
    Inconclusive,
}
