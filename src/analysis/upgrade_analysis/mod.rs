//! Upgrade impact analysis.
//!
//! Analyzes changes in network behavior before and after a daemon upgrade
//! by comparing metrics across time windows.
//!
//! Internal layout:
//!
//! - `windows`: pre-partitioning of TX observations, bandwidth events, and
//!   connection state into per-window slices, plus the synthetic-spy trial
//!   sets shared across the parallel window pipeline.
//! - `metrics`: per-window metric computation (TX propagation, bandwidth,
//!   peer counts, synthetic spy accuracy, Gini coefficient, Dandelion stem
//!   length).
//! - `assembly`: per-period aggregation, pre-vs-post comparison, and
//!   overall-assessment generation.
//!
//! The public surface is `UpgradeAnalysisConfig` and `analyze_upgrade_impact`,
//! re-exported below to preserve the existing `analysis::upgrade_analysis::*`
//! call sites.

mod assembly;
mod metrics;
mod windows;

use std::collections::HashMap;
use std::path::Path;

use chrono::Utc;
use color_eyre::eyre::Result;
use rayon::prelude::*;

use super::time_window::*;
use super::types::*;

use assembly::{compare_periods, create_period_summary, generate_assessment};
use metrics::{calculate_window_metrics_fast, FLUFF_GAP_THRESHOLDS_MS};
use windows::{build_spy_trial_sets, prepartition_data};

/// Configuration for upgrade analysis
#[derive(Debug, Clone)]
pub struct UpgradeAnalysisConfig {
    /// Size of each time window in seconds
    pub window_size_sec: f64,
    /// Optional path to upgrade manifest
    pub manifest_path: Option<String>,
    /// Manual override: end of pre-upgrade period
    pub pre_upgrade_end: Option<SimTime>,
    /// Manual override: start of post-upgrade period
    pub post_upgrade_start: Option<SimTime>,
}

impl Default for UpgradeAnalysisConfig {
    fn default() -> Self {
        Self {
            window_size_sec: 60.0,
            manifest_path: None,
            pre_upgrade_end: None,
            post_upgrade_start: None,
        }
    }
}

/// Main entry point for upgrade impact analysis.
pub fn analyze_upgrade_impact(
    transactions: &[Transaction],
    log_data: &HashMap<String, NodeLogData>,
    agents: &[AnalysisAgentInfo],
    _blocks: &[BlockInfo],
    config: &UpgradeAnalysisConfig,
    data_dir: &str,
) -> Result<UpgradeAnalysisReport> {
    // Find simulation time range
    let (sim_start, sim_end) = find_simulation_time_range(log_data);
    log::info!(
        "Simulation time range: {:.1}s - {:.1}s ({:.1}s duration)",
        sim_start,
        sim_end,
        sim_end - sim_start
    );

    // Load upgrade manifest if provided
    let manifest = if let Some(ref path) = config.manifest_path {
        Some(load_upgrade_manifest(Path::new(path))?)
    } else {
        None
    };

    // Create time windows
    let mut windows = create_time_windows(sim_start, sim_end, config.window_size_sec);
    log::info!(
        "Created {} time windows of {}s each",
        windows.len(),
        config.window_size_sec
    );

    // Label windows based on upgrade timing
    if let Some(ref m) = manifest {
        label_windows_by_upgrade(&mut windows, m);
    } else if let (Some(pre_end), Some(post_start)) =
        (config.pre_upgrade_end, config.post_upgrade_start)
    {
        // Use manual overrides
        let manual_manifest = UpgradeManifest {
            pre_upgrade_version: None,
            post_upgrade_version: None,
            node_upgrades: Vec::new(),
            upgrade_start: Some(pre_end),
            upgrade_end: Some(post_start),
        };
        label_windows_by_upgrade(&mut windows, &manual_manifest);
    }

    // Pre-sort transactions by timestamp for binary-search window filtering
    let mut sorted_txs: Vec<&Transaction> = transactions.iter().collect();
    sorted_txs.sort_by(|a, b| {
        a.timestamp
            .partial_cmp(&b.timestamp)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    // Pre-partition all observation data (one-time O(N*O*log) cost)
    log::info!(
        "Pre-partitioning observation data for {} windows...",
        windows.len()
    );
    let prepartitioned = prepartition_data(log_data, &windows);
    log::info!(
        "Pre-partitioned: {} TX observations, {} bandwidth events",
        prepartitioned.tx_obs_sorted.len(),
        prepartitioned.bw_sorted.len(),
    );

    // Build IP-to-agent mapping (shared across all windows)
    let ip_to_agent: HashMap<&str, &AnalysisAgentInfo> =
        agents.iter().map(|a| (a.ip_addr.as_str(), a)).collect();

    // Pre-compute synthetic spy trial sets (shared read-only across parallel windows)
    const SPY_VISIBILITY_LEVELS: &[f64] = &[0.05, 0.10, 0.20, 0.30, 0.50];
    const SPY_TRIALS_PER_LEVEL: usize = 3;

    let node_ids: Vec<&str> = log_data.keys().map(|s| s.as_str()).collect();
    let spy_trials =
        build_spy_trial_sets(&node_ids, SPY_VISIBILITY_LEVELS, SPY_TRIALS_PER_LEVEL, 42);

    // Process all windows in parallel using rayon
    let windowed_metrics: Vec<WindowedMetrics> = windows
        .par_iter()
        .enumerate()
        .map(|(i, window)| {
            // Binary search for transactions in this window
            let tx_start = sorted_txs.partition_point(|tx| tx.timestamp < window.start);
            let tx_end = sorted_txs.partition_point(|tx| tx.timestamp < window.end);
            let window_txs = &sorted_txs[tx_start..tx_end];

            // Get pre-computed slices
            let (obs_start, obs_end) = prepartitioned.tx_obs_window_ranges[i];
            let tx_obs_slice = &prepartitioned.tx_obs_sorted[obs_start..obs_end];

            let (bw_start, bw_end) = prepartitioned.bw_window_ranges[i];
            let bw_slice = &prepartitioned.bw_sorted[bw_start..bw_end];

            let avg_peer_count = prepartitioned.conn_avg_peer_counts[i];

            calculate_window_metrics_fast(
                window,
                window_txs,
                tx_obs_slice,
                bw_slice,
                avg_peer_count,
                &ip_to_agent,
                &spy_trials,
            )
        })
        .collect();

    // Aggregate by period label
    let by_label = aggregate_windows_by_label(&windowed_metrics);

    // Create period summaries
    let pre_upgrade_summary = create_period_summary("pre-upgrade", &by_label);
    let transition_summary = create_period_summary("transition", &by_label);
    let post_upgrade_summary = create_period_summary("post-upgrade", &by_label);

    // Compare pre vs post
    let changes = match (pre_upgrade_summary.as_ref(), post_upgrade_summary.as_ref()) {
        (Some(pre), Some(post)) => compare_periods(pre, post),
        _ => Vec::new(),
    };

    // Generate assessment
    let assessment = generate_assessment(&changes, &pre_upgrade_summary, &post_upgrade_summary);

    // Build metadata
    let metadata = UpgradeAnalysisMetadata {
        analysis_timestamp: Utc::now().to_rfc3339(),
        simulation_data_dir: data_dir.to_string(),
        simulation_start: sim_start,
        simulation_end: sim_end,
        window_size_sec: config.window_size_sec,
        total_windows: windowed_metrics.len(),
        total_nodes: agents.len(),
        total_transactions: transactions.len(),
        spy_visibility_levels: SPY_VISIBILITY_LEVELS.to_vec(),
        spy_trials_per_level: SPY_TRIALS_PER_LEVEL,
        fluff_gap_thresholds_ms: FLUFF_GAP_THRESHOLDS_MS.to_vec(),
    };

    Ok(UpgradeAnalysisReport {
        metadata,
        upgrade_info: manifest,
        time_series: windowed_metrics,
        pre_upgrade_summary,
        transition_summary,
        post_upgrade_summary,
        changes,
        assessment,
    })
}
