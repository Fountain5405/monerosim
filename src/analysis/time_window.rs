//! Time windowing utilities for segmented analysis.
//!
//! Provides functions to divide simulation time into windows and filter
//! observations/transactions to specific time ranges.

use std::collections::HashMap;
use std::fs;
use std::path::Path;

use color_eyre::eyre::{Context, Result};

use super::types::*;

/// Create time windows spanning the simulation duration.
///
/// # Arguments
/// * `start` - Simulation start time
/// * `end` - Simulation end time
/// * `window_size_sec` - Size of each window in seconds
///
/// # Returns
/// Vector of TimeWindow structs covering the entire simulation
pub fn create_time_windows(start: SimTime, end: SimTime, window_size_sec: f64) -> Vec<TimeWindow> {
    let mut windows = Vec::new();
    let mut current = start;
    let mut index = 0;

    while current < end {
        let window_end = (current + window_size_sec).min(end);
        windows.push(TimeWindow {
            start: current,
            end: window_end,
            label: Some(format!("window_{}", index)),
        });
        current = window_end;
        index += 1;
    }

    windows
}

/// Find the time range of all observations in the log data.
pub fn find_simulation_time_range(log_data: &HashMap<String, NodeLogData>) -> (SimTime, SimTime) {
    let mut min_time = f64::MAX;
    let mut max_time = f64::MIN;

    for node_data in log_data.values() {
        for obs in &node_data.tx_observations {
            min_time = min_time.min(obs.timestamp);
            max_time = max_time.max(obs.timestamp);
        }
        for event in &node_data.connection_events {
            min_time = min_time.min(event.timestamp);
            max_time = max_time.max(event.timestamp);
        }
        for obs in &node_data.block_observations {
            min_time = min_time.min(obs.timestamp);
            max_time = max_time.max(obs.timestamp);
        }
    }

    if min_time == f64::MAX {
        (0.0, 0.0)
    } else {
        (min_time, max_time)
    }
}

/// Filter transactions to those created within a time window.
pub fn filter_transactions_by_window<'a>(
    transactions: &'a [Transaction],
    window: &TimeWindow,
) -> Vec<&'a Transaction> {
    transactions
        .iter()
        .filter(|tx| window.contains(tx.timestamp))
        .collect()
}

/// Filter TX observations to those within a time window.
pub fn filter_tx_observations_by_window(
    log_data: &HashMap<String, NodeLogData>,
    window: &TimeWindow,
) -> HashMap<String, Vec<TxObservation>> {
    let mut filtered: HashMap<String, Vec<TxObservation>> = HashMap::new();

    for (node_id, node_data) in log_data {
        let obs: Vec<TxObservation> = node_data
            .tx_observations
            .iter()
            .filter(|o| window.contains(o.timestamp))
            .cloned()
            .collect();

        if !obs.is_empty() {
            filtered.insert(node_id.clone(), obs);
        }
    }

    filtered
}

/// Get connection state at a specific point in time.
///
/// Replays connection events up to `at_time` and returns the active connections.
pub fn get_connection_state_at(
    log_data: &HashMap<String, NodeLogData>,
    at_time: SimTime,
) -> HashMap<String, Vec<String>> {
    let mut connections: HashMap<String, HashMap<String, bool>> = HashMap::new();

    for (node_id, node_data) in log_data {
        let node_connections = connections.entry(node_id.clone()).or_default();

        for event in &node_data.connection_events {
            if event.timestamp > at_time {
                break; // Events are assumed sorted by time
            }

            let peer_key = format!("{}:{}", event.peer_ip, event.connection_id);
            if event.is_open {
                node_connections.insert(peer_key, true);
            } else {
                node_connections.remove(&peer_key);
            }
        }
    }

    // Convert to peer IP list
    connections
        .into_iter()
        .map(|(node_id, peers)| {
            let peer_ips: Vec<String> = peers
                .keys()
                .map(|k| k.split(':').next().unwrap_or("").to_string())
                .collect();
            (node_id, peer_ips)
        })
        .collect()
}

/// Filter block observations to those within a time window.
pub fn filter_block_observations_by_window(
    log_data: &HashMap<String, NodeLogData>,
    window: &TimeWindow,
) -> Vec<BlockObservation> {
    let mut blocks = Vec::new();

    for node_data in log_data.values() {
        for obs in &node_data.block_observations {
            if window.contains(obs.timestamp) {
                blocks.push(obs.clone());
            }
        }
    }

    blocks
}

/// Load upgrade manifest from JSON file.
pub fn load_upgrade_manifest(path: &Path) -> Result<UpgradeManifest> {
    let content = fs::read_to_string(path)
        .with_context(|| format!("Failed to read upgrade manifest: {}", path.display()))?;

    // Parse the JSON structure
    let data: serde_json::Value = serde_json::from_str(&content)
        .with_context(|| "Failed to parse upgrade manifest JSON")?;

    let mut manifest = UpgradeManifest {
        pre_upgrade_version: data
            .get("pre_upgrade_version")
            .and_then(|v| v.as_str())
            .map(String::from),
        post_upgrade_version: data
            .get("post_upgrade_version")
            .and_then(|v| v.as_str())
            .map(String::from),
        node_upgrades: Vec::new(),
        upgrade_start: None,
        upgrade_end: None,
    };

    // Parse node upgrades
    if let Some(upgrades) = data.get("upgrades").and_then(|v| v.as_array()) {
        for upgrade in upgrades {
            if let (Some(node_id), Some(timestamp)) = (
                upgrade.get("node_id").and_then(|v| v.as_str()),
                upgrade.get("timestamp").and_then(|v| v.as_f64()),
            ) {
                let version = upgrade
                    .get("version")
                    .and_then(|v| v.as_str())
                    .unwrap_or("unknown")
                    .to_string();

                manifest.node_upgrades.push(NodeUpgradeEvent {
                    node_id: node_id.to_string(),
                    timestamp,
                    version,
                });
            }
        }
    }

    // Calculate upgrade start/end times
    if !manifest.node_upgrades.is_empty() {
        manifest.upgrade_start = manifest
            .node_upgrades
            .iter()
            .map(|u| u.timestamp)
            .min_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        manifest.upgrade_end = manifest
            .node_upgrades
            .iter()
            .map(|u| u.timestamp)
            .max_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    }

    Ok(manifest)
}

/// Label windows based on upgrade manifest.
///
/// Windows before upgrade_start get "pre-upgrade" label.
/// Windows during upgrade get "transition" label.
/// Windows after upgrade_end get "post-upgrade" label.
pub fn label_windows_by_upgrade(
    windows: &mut [TimeWindow],
    manifest: &UpgradeManifest,
) {
    let upgrade_start = manifest.upgrade_start.unwrap_or(f64::MAX);
    let upgrade_end = manifest.upgrade_end.unwrap_or(f64::MAX);

    for window in windows.iter_mut() {
        let label = if window.end <= upgrade_start {
            "pre-upgrade"
        } else if window.start >= upgrade_end {
            "post-upgrade"
        } else {
            "transition"
        };
        window.label = Some(label.to_string());
    }
}

/// Classify windows into periods and aggregate metrics.
pub fn aggregate_windows_by_label(
    windows: &[WindowedMetrics],
) -> HashMap<String, Vec<&WindowedMetrics>> {
    let mut by_label: HashMap<String, Vec<&WindowedMetrics>> = HashMap::new();

    for window in windows {
        let label = window
            .window
            .label
            .as_deref()
            .unwrap_or("unknown")
            .to_string();
        by_label.entry(label).or_default().push(window);
    }

    by_label
}

/// Calculate mean and standard deviation for a series of Option<f64> values.
pub fn calculate_stats(values: &[Option<f64>]) -> (Option<f64>, Option<f64>) {
    let valid: Vec<f64> = values.iter().filter_map(|v| *v).collect();

    if valid.is_empty() {
        return (None, None);
    }

    let n = valid.len() as f64;
    let mean = valid.iter().sum::<f64>() / n;

    let std = if valid.len() > 1 {
        let variance = valid.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (n - 1.0);
        Some(variance.sqrt())
    } else {
        None
    };

    (Some(mean), std)
}

/// Perform a simple two-sample t-test (Welch's t-test).
///
/// Returns the p-value for the null hypothesis that the two samples have equal means.
pub fn welch_t_test(sample1: &[f64], sample2: &[f64]) -> Option<f64> {
    if sample1.len() < 2 || sample2.len() < 2 {
        return None;
    }

    let n1 = sample1.len() as f64;
    let n2 = sample2.len() as f64;

    let mean1 = sample1.iter().sum::<f64>() / n1;
    let mean2 = sample2.iter().sum::<f64>() / n2;

    let var1 = sample1.iter().map(|x| (x - mean1).powi(2)).sum::<f64>() / (n1 - 1.0);
    let var2 = sample2.iter().map(|x| (x - mean2).powi(2)).sum::<f64>() / (n2 - 1.0);

    let se = (var1 / n1 + var2 / n2).sqrt();
    if se == 0.0 {
        return None;
    }

    let t = (mean1 - mean2).abs() / se;

    // Welch-Satterthwaite degrees of freedom
    let df_num = (var1 / n1 + var2 / n2).powi(2);
    let df_denom = (var1 / n1).powi(2) / (n1 - 1.0) + (var2 / n2).powi(2) / (n2 - 1.0);
    let df = df_num / df_denom;

    // Approximate p-value using normal distribution for large df
    // (For small df, we'd need a proper t-distribution CDF)
    if df > 30.0 {
        // Use normal approximation
        let p = 2.0 * (1.0 - standard_normal_cdf(t));
        Some(p)
    } else {
        // For small sample sizes, use a conservative approximation
        // In production, you'd want a proper t-distribution implementation
        let p = 2.0 * (1.0 - standard_normal_cdf(t * 0.9)); // Conservative adjustment
        Some(p)
    }
}

/// Standard normal CDF approximation (Abramowitz and Stegun)
fn standard_normal_cdf(x: f64) -> f64 {
    let a1 = 0.254829592;
    let a2 = -0.284496736;
    let a3 = 1.421413741;
    let a4 = -1.453152027;
    let a5 = 1.061405429;
    let p = 0.3275911;

    let sign = if x < 0.0 { -1.0 } else { 1.0 };
    let x = x.abs() / std::f64::consts::SQRT_2;

    let t = 1.0 / (1.0 + p * x);
    let y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * (-x * x).exp();

    0.5 * (1.0 + sign * y)
}

/// Determine if a change is statistically significant at p < 0.05.
pub fn is_significant(p_value: Option<f64>) -> bool {
    p_value.map(|p| p < 0.05).unwrap_or(false)
}

/// Calculate coefficient of variation (CV) for detecting steady state.
/// Low CV (< 0.1) indicates stable, steady-state behavior.
pub fn coefficient_of_variation(values: &[f64]) -> Option<f64> {
    if values.len() < 2 {
        return None;
    }

    let mean = values.iter().sum::<f64>() / values.len() as f64;
    if mean == 0.0 {
        return None;
    }

    let variance = values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (values.len() - 1) as f64;
    Some(variance.sqrt() / mean.abs())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_time_windows() {
        let windows = create_time_windows(0.0, 300.0, 60.0);
        assert_eq!(windows.len(), 5);
        assert_eq!(windows[0].start, 0.0);
        assert_eq!(windows[0].end, 60.0);
        assert_eq!(windows[4].start, 240.0);
        assert_eq!(windows[4].end, 300.0);
    }

    #[test]
    fn test_time_window_contains() {
        let window = TimeWindow::new(100.0, 200.0);
        assert!(!window.contains(99.9));
        assert!(window.contains(100.0));
        assert!(window.contains(150.0));
        assert!(!window.contains(200.0)); // End is exclusive
    }

    #[test]
    fn test_calculate_stats() {
        let values = vec![Some(1.0), Some(2.0), Some(3.0), Some(4.0), Some(5.0)];
        let (mean, std) = calculate_stats(&values);
        assert!((mean.unwrap() - 3.0).abs() < 0.001);
        assert!((std.unwrap() - 1.5811).abs() < 0.01);
    }

    #[test]
    fn test_coefficient_of_variation() {
        // Low CV = stable
        let stable = vec![100.0, 101.0, 99.0, 100.0, 100.0];
        let cv = coefficient_of_variation(&stable).unwrap();
        assert!(cv < 0.1);

        // High CV = variable
        let variable = vec![50.0, 150.0, 25.0, 200.0, 75.0];
        let cv = coefficient_of_variation(&variable).unwrap();
        assert!(cv > 0.5);
    }
}
