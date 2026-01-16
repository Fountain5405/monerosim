//! Upgrade impact analysis.
//!
//! Analyzes changes in network behavior before and after a daemon upgrade
//! by comparing metrics across time windows.

use std::collections::HashMap;
use std::path::Path;

use chrono::Utc;
use color_eyre::eyre::Result;

use super::time_window::*;
use super::types::*;

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
    agents: &[AgentInfo],
    blocks: &[BlockInfo],
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
    log::info!("Created {} time windows of {}s each", windows.len(), config.window_size_sec);

    // Label windows based on upgrade timing
    if let Some(ref m) = manifest {
        label_windows_by_upgrade(&mut windows, m);
    } else if let (Some(pre_end), Some(post_start)) = (config.pre_upgrade_end, config.post_upgrade_start) {
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

    // Calculate metrics for each window
    let mut windowed_metrics = Vec::with_capacity(windows.len());
    for (i, window) in windows.iter().enumerate() {
        log::debug!("Analyzing window {} ({:.1}s - {:.1}s)", i, window.start, window.end);
        let metrics = calculate_window_metrics(window, transactions, log_data, agents, blocks);
        windowed_metrics.push(metrics);
    }

    // Aggregate by period label
    let by_label = aggregate_windows_by_label(&windowed_metrics);

    // Create period summaries
    let pre_upgrade_summary = create_period_summary("pre-upgrade", &by_label);
    let transition_summary = create_period_summary("transition", &by_label);
    let post_upgrade_summary = create_period_summary("post-upgrade", &by_label);

    // Compare pre vs post
    let changes = if pre_upgrade_summary.is_some() && post_upgrade_summary.is_some() {
        compare_periods(
            pre_upgrade_summary.as_ref().unwrap(),
            post_upgrade_summary.as_ref().unwrap(),
        )
    } else {
        Vec::new()
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

/// Calculate all metrics for a single time window.
fn calculate_window_metrics(
    window: &TimeWindow,
    transactions: &[Transaction],
    log_data: &HashMap<String, NodeLogData>,
    agents: &[AgentInfo],
    _blocks: &[BlockInfo],
) -> WindowedMetrics {
    let mut metrics = WindowedMetrics {
        window: window.clone(),
        ..Default::default()
    };

    // Filter transactions to this window
    let window_txs: Vec<&Transaction> = filter_transactions_by_window(transactions, window);
    metrics.tx_count = window_txs.len();

    // Build IP-to-agent mapping
    let ip_to_agent: HashMap<&str, &AgentInfo> = agents
        .iter()
        .map(|a| (a.ip_addr.as_str(), a))
        .collect();

    // Filter observations to this window
    let filtered_obs = filter_tx_observations_by_window(log_data, window);
    metrics.observation_count = filtered_obs.values().map(|v| v.len()).sum();

    if window_txs.is_empty() || metrics.observation_count == 0 {
        return metrics;
    }

    // Build TX hash to observations mapping (only for window TXs)
    let window_tx_hashes: std::collections::HashSet<&str> =
        window_txs.iter().map(|tx| tx.tx_hash.as_str()).collect();

    let mut tx_observations: HashMap<String, Vec<&TxObservation>> = HashMap::new();
    for node_data in log_data.values() {
        for obs in &node_data.tx_observations {
            if window.contains(obs.timestamp) && window_tx_hashes.contains(obs.tx_hash.as_str()) {
                tx_observations
                    .entry(obs.tx_hash.clone())
                    .or_default()
                    .push(obs);
            }
        }
    }

    // Spy node analysis
    let (spy_accuracy, spy_analyzable) =
        calculate_spy_accuracy_for_window(&window_txs, &tx_observations, &ip_to_agent);
    metrics.spy_accuracy = spy_accuracy;
    metrics.spy_analyzable_txs = spy_analyzable;

    // Propagation analysis
    let (avg_prop, median_prop, p95_prop) =
        calculate_propagation_for_window(&tx_observations);
    metrics.avg_propagation_ms = avg_prop;
    metrics.median_propagation_ms = median_prop;
    metrics.p95_propagation_ms = p95_prop;

    // Network state at window end
    let connections = get_connection_state_at(log_data, window.end);
    if !connections.is_empty() {
        let peer_counts: Vec<f64> = connections.values().map(|v| v.len() as f64).collect();
        metrics.avg_peer_count = Some(peer_counts.iter().sum::<f64>() / peer_counts.len() as f64);
    }

    // Gini coefficient for first-seen distribution in this window
    metrics.gini_coefficient = calculate_gini_for_window(&tx_observations);

    // Dandelion analysis (simplified - just stem length)
    let (avg_stem, paths_count) =
        calculate_dandelion_for_window(&window_txs, &tx_observations, &ip_to_agent);
    metrics.avg_stem_length = avg_stem;
    metrics.paths_reconstructed = paths_count;

    metrics
}

/// Calculate spy node accuracy for a window.
fn calculate_spy_accuracy_for_window(
    transactions: &[&Transaction],
    tx_observations: &HashMap<String, Vec<&TxObservation>>,
    ip_to_agent: &HashMap<&str, &AgentInfo>,
) -> (Option<f64>, usize) {
    let mut correct = 0;
    let mut analyzable = 0;

    for tx in transactions {
        if let Some(observations) = tx_observations.get(&tx.tx_hash) {
            if observations.is_empty() {
                continue;
            }

            analyzable += 1;

            // Sort by timestamp
            let mut sorted_obs: Vec<&&TxObservation> = observations.iter().collect();
            sorted_obs.sort_by(|a, b| {
                a.timestamp
                    .partial_cmp(&b.timestamp)
                    .unwrap_or(std::cmp::Ordering::Equal)
            });

            // Infer originator from first 5 observations
            let early_count = sorted_obs.len().min(5);
            let early_obs = &sorted_obs[..early_count];

            let mut source_counts: HashMap<&str, (usize, usize)> = HashMap::new();
            for (idx, obs) in early_obs.iter().enumerate() {
                source_counts
                    .entry(&obs.source_ip)
                    .and_modify(|(count, _)| *count += 1)
                    .or_insert((1, idx));
            }

            let inferred_ip = source_counts
                .into_iter()
                .max_by(|(_, (count_a, idx_a)), (_, (count_b, idx_b))| {
                    count_a.cmp(count_b).then_with(|| idx_b.cmp(idx_a))
                })
                .map(|(ip, _)| ip);

            // Get true sender IP
            let true_sender_ip = ip_to_agent
                .iter()
                .find(|(_, agent)| agent.id == tx.sender_id)
                .map(|(ip, _)| *ip);

            if let (Some(inferred), Some(true_ip)) = (inferred_ip, true_sender_ip) {
                if inferred == true_ip {
                    correct += 1;
                }
            }
        }
    }

    if analyzable > 0 {
        (Some(correct as f64 / analyzable as f64), analyzable)
    } else {
        (None, 0)
    }
}

/// Calculate propagation metrics for a window.
fn calculate_propagation_for_window(
    tx_observations: &HashMap<String, Vec<&TxObservation>>,
) -> (Option<f64>, Option<f64>, Option<f64>) {
    let mut all_propagation_times: Vec<f64> = Vec::new();

    for observations in tx_observations.values() {
        if observations.is_empty() {
            continue;
        }

        let mut sorted_obs: Vec<&&TxObservation> = observations.iter().collect();
        sorted_obs.sort_by(|a, b| {
            a.timestamp
                .partial_cmp(&b.timestamp)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        let first_time = sorted_obs.first().map(|o| o.timestamp).unwrap_or(0.0);
        let last_time = sorted_obs.last().map(|o| o.timestamp).unwrap_or(0.0);

        let propagation_ms = (last_time - first_time) * 1000.0;
        all_propagation_times.push(propagation_ms);
    }

    if all_propagation_times.is_empty() {
        return (None, None, None);
    }

    all_propagation_times.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let avg = all_propagation_times.iter().sum::<f64>() / all_propagation_times.len() as f64;
    let median = all_propagation_times[all_propagation_times.len() / 2];
    let p95_idx = (all_propagation_times.len() as f64 * 0.95) as usize;
    let p95 = all_propagation_times.get(p95_idx).copied().unwrap_or(median);

    (Some(avg), Some(median), Some(p95))
}

/// Calculate Gini coefficient for first-seen distribution.
fn calculate_gini_for_window(
    tx_observations: &HashMap<String, Vec<&TxObservation>>,
) -> Option<f64> {
    // Count first-seens per node
    let mut first_seen_counts: HashMap<&str, usize> = HashMap::new();

    for observations in tx_observations.values() {
        if observations.is_empty() {
            continue;
        }

        // Find the node that saw this TX first
        let first_obs = observations
            .iter()
            .min_by(|a, b| {
                a.timestamp
                    .partial_cmp(&b.timestamp)
                    .unwrap_or(std::cmp::Ordering::Equal)
            });

        if let Some(obs) = first_obs {
            *first_seen_counts.entry(&obs.node_id).or_insert(0) += 1;
        }
    }

    if first_seen_counts.is_empty() {
        return None;
    }

    // Calculate Gini coefficient
    let mut values: Vec<f64> = first_seen_counts.values().map(|&v| v as f64).collect();
    values.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let n = values.len() as f64;
    let sum: f64 = values.iter().sum();

    if sum == 0.0 {
        return Some(0.0);
    }

    let mut gini_sum = 0.0;
    for (i, v) in values.iter().enumerate() {
        gini_sum += (2.0 * (i + 1) as f64 - n - 1.0) * v;
    }

    Some(gini_sum / (n * sum))
}

/// Calculate simplified Dandelion metrics for a window.
fn calculate_dandelion_for_window(
    transactions: &[&Transaction],
    tx_observations: &HashMap<String, Vec<&TxObservation>>,
    ip_to_agent: &HashMap<&str, &AgentInfo>,
) -> (Option<f64>, usize) {
    let mut stem_lengths: Vec<f64> = Vec::new();

    for tx in transactions {
        if let Some(observations) = tx_observations.get(&tx.tx_hash) {
            if observations.is_empty() {
                continue;
            }

            // Get originator IP
            let originator_ip = ip_to_agent
                .iter()
                .find(|(_, agent)| agent.id == tx.sender_id)
                .map(|(ip, _)| *ip);

            if originator_ip.is_none() {
                continue;
            }

            let originator_ip = originator_ip.unwrap();

            // Sort observations
            let mut sorted_obs: Vec<&TxObservation> = observations.iter().copied().collect();
            sorted_obs.sort_by(|a, b| {
                a.timestamp
                    .partial_cmp(&b.timestamp)
                    .unwrap_or(std::cmp::Ordering::Equal)
            });

            // Simple stem length: count hops until we see broadcast pattern
            let mut stem_length = 0;
            let mut used: std::collections::HashSet<usize> = std::collections::HashSet::new();

            // Find first observation from originator
            let first_hop_idx = sorted_obs
                .iter()
                .enumerate()
                .find(|(_, obs)| obs.source_ip == originator_ip)
                .map(|(i, _)| i);

            if let Some(idx) = first_hop_idx {
                used.insert(idx);
                stem_length = 1;

                // Build node_to_ip map
                let node_to_ip: HashMap<&str, &str> = ip_to_agent
                    .iter()
                    .map(|(ip, agent)| (agent.id.as_str(), *ip))
                    .collect();

                // Follow chain
                let mut current_sender_ip = node_to_ip
                    .get(sorted_obs[idx].node_id.as_str())
                    .copied();

                for _ in 0..50 {
                    if current_sender_ip.is_none() {
                        break;
                    }

                    let sender_ip = current_sender_ip.unwrap();

                    // Find next observation from current sender
                    let from_current: Vec<(usize, &TxObservation)> = sorted_obs
                        .iter()
                        .enumerate()
                        .filter(|(i, obs)| !used.contains(i) && obs.source_ip == sender_ip)
                        .map(|(i, obs)| (i, *obs))
                        .collect();

                    if from_current.is_empty() {
                        break;
                    }

                    // Check for fluff (3+ recipients within 100ms)
                    if from_current.len() >= 3 {
                        let first_time = from_current[0].1.timestamp;
                        let in_window = from_current
                            .iter()
                            .filter(|(_, obs)| (obs.timestamp - first_time) * 1000.0 <= 100.0)
                            .count();
                        if in_window >= 3 {
                            break; // Fluff detected
                        }
                    }

                    // Take first recipient
                    let (next_idx, next_obs) = from_current[0];
                    used.insert(next_idx);
                    stem_length += 1;

                    current_sender_ip = node_to_ip.get(next_obs.node_id.as_str()).copied();
                }
            }

            if stem_length > 0 {
                stem_lengths.push(stem_length as f64);
            }
        }
    }

    if stem_lengths.is_empty() {
        (None, 0)
    } else {
        let avg = stem_lengths.iter().sum::<f64>() / stem_lengths.len() as f64;
        (Some(avg), stem_lengths.len())
    }
}

/// Create an aggregated summary for a labeled period.
fn create_period_summary(
    label: &str,
    by_label: &HashMap<String, Vec<&WindowedMetrics>>,
) -> Option<AggregatedMetrics> {
    let windows = by_label.get(label)?;

    if windows.is_empty() {
        return None;
    }

    let start = windows.iter().map(|w| w.window.start).min_by(|a, b| a.partial_cmp(b).unwrap())?;
    let end = windows.iter().map(|w| w.window.end).max_by(|a, b| a.partial_cmp(b).unwrap())?;
    let total_txs: usize = windows.iter().map(|w| w.tx_count).sum();

    // Calculate means and stds
    let spy_values: Vec<Option<f64>> = windows.iter().map(|w| w.spy_accuracy).collect();
    let (mean_spy, std_spy) = calculate_stats(&spy_values);

    let prop_values: Vec<Option<f64>> = windows.iter().map(|w| w.avg_propagation_ms).collect();
    let (mean_prop, std_prop) = calculate_stats(&prop_values);

    let peer_values: Vec<Option<f64>> = windows.iter().map(|w| w.avg_peer_count).collect();
    let (mean_peer, std_peer) = calculate_stats(&peer_values);

    let gini_values: Vec<Option<f64>> = windows.iter().map(|w| w.gini_coefficient).collect();
    let (mean_gini, std_gini) = calculate_stats(&gini_values);

    let stem_values: Vec<Option<f64>> = windows.iter().map(|w| w.avg_stem_length).collect();
    let (mean_stem, std_stem) = calculate_stats(&stem_values);

    Some(AggregatedMetrics {
        period_label: label.to_string(),
        start,
        end,
        window_count: windows.len(),
        total_txs,
        mean_spy_accuracy: mean_spy,
        mean_propagation_ms: mean_prop,
        mean_peer_count: mean_peer,
        mean_gini: mean_gini,
        mean_stem_length: mean_stem,
        std_spy_accuracy: std_spy,
        std_propagation_ms: std_prop,
        std_peer_count: std_peer,
        std_gini: std_gini,
        std_stem_length: std_stem,
        windows: windows.iter().map(|w| (*w).clone()).collect(),
    })
}

/// Compare pre and post upgrade periods.
fn compare_periods(pre: &AggregatedMetrics, post: &AggregatedMetrics) -> Vec<MetricChange> {
    let mut changes = Vec::new();

    // Helper to create a metric change
    let add_change = |name: &str,
                      pre_val: Option<f64>,
                      post_val: Option<f64>,
                      pre_windows: &[WindowedMetrics],
                      post_windows: &[WindowedMetrics],
                      higher_is_better: bool|
     -> Option<MetricChange> {
        let (pre_v, post_v) = (pre_val?, post_val?);

        let absolute_change = post_v - pre_v;
        let percent_change = if pre_v != 0.0 {
            (absolute_change / pre_v) * 100.0
        } else {
            0.0
        };

        // Extract values for t-test
        let pre_samples: Vec<f64> = pre_windows
            .iter()
            .filter_map(|w| match name {
                "Spy Node Accuracy" => w.spy_accuracy,
                "Avg Propagation (ms)" => w.avg_propagation_ms,
                "Avg Peer Count" => w.avg_peer_count,
                "Gini Coefficient" => w.gini_coefficient,
                "Avg Stem Length" => w.avg_stem_length,
                _ => None,
            })
            .collect();

        let post_samples: Vec<f64> = post_windows
            .iter()
            .filter_map(|w| match name {
                "Spy Node Accuracy" => w.spy_accuracy,
                "Avg Propagation (ms)" => w.avg_propagation_ms,
                "Avg Peer Count" => w.avg_peer_count,
                "Gini Coefficient" => w.gini_coefficient,
                "Avg Stem Length" => w.avg_stem_length,
                _ => None,
            })
            .collect();

        let p_value = welch_t_test(&pre_samples, &post_samples);
        let significant = is_significant(p_value);

        // Determine impact
        let impact = if !significant {
            ChangeImpact::Neutral
        } else if higher_is_better {
            if absolute_change > 0.0 {
                ChangeImpact::Positive
            } else {
                ChangeImpact::Negative
            }
        } else {
            // Lower is better
            if absolute_change < 0.0 {
                ChangeImpact::Positive
            } else {
                ChangeImpact::Negative
            }
        };

        // Generate interpretation
        let interpretation = generate_interpretation(name, percent_change, significant, impact);

        Some(MetricChange {
            metric_name: name.to_string(),
            pre_value: pre_v,
            post_value: post_v,
            absolute_change,
            percent_change,
            p_value,
            statistically_significant: significant,
            interpretation,
            impact,
        })
    };

    // Compare each metric
    // Spy accuracy: Lower is better (harder to deanonymize)
    if let Some(change) = add_change(
        "Spy Node Accuracy",
        pre.mean_spy_accuracy,
        post.mean_spy_accuracy,
        &pre.windows,
        &post.windows,
        false,
    ) {
        changes.push(change);
    }

    // Propagation: Lower is better (faster network)
    if let Some(change) = add_change(
        "Avg Propagation (ms)",
        pre.mean_propagation_ms,
        post.mean_propagation_ms,
        &pre.windows,
        &post.windows,
        false,
    ) {
        changes.push(change);
    }

    // Peer count: Higher is better (more connectivity)
    if let Some(change) = add_change(
        "Avg Peer Count",
        pre.mean_peer_count,
        post.mean_peer_count,
        &pre.windows,
        &post.windows,
        true,
    ) {
        changes.push(change);
    }

    // Gini: Lower is better (less centralized)
    if let Some(change) = add_change(
        "Gini Coefficient",
        pre.mean_gini,
        post.mean_gini,
        &pre.windows,
        &post.windows,
        false,
    ) {
        changes.push(change);
    }

    // Stem length: Higher is better (better privacy)
    if let Some(change) = add_change(
        "Avg Stem Length",
        pre.mean_stem_length,
        post.mean_stem_length,
        &pre.windows,
        &post.windows,
        true,
    ) {
        changes.push(change);
    }

    changes
}

/// Generate human-readable interpretation of a metric change.
fn generate_interpretation(
    metric_name: &str,
    percent_change: f64,
    significant: bool,
    impact: ChangeImpact,
) -> String {
    if !significant {
        return format!("{} remained stable (no significant change)", metric_name);
    }

    let direction = if percent_change > 0.0 {
        "increased"
    } else {
        "decreased"
    };

    let impact_word = match impact {
        ChangeImpact::Positive => "improved",
        ChangeImpact::Negative => "degraded",
        ChangeImpact::Neutral => "changed",
    };

    match metric_name {
        "Spy Node Accuracy" => format!(
            "Privacy {} - spy node inference {} by {:.1}%",
            impact_word, direction, percent_change.abs()
        ),
        "Avg Propagation (ms)" => format!(
            "Network speed {} - propagation time {} by {:.1}%",
            impact_word, direction, percent_change.abs()
        ),
        "Avg Peer Count" => format!(
            "Connectivity {} - average peer count {} by {:.1}%",
            impact_word, direction, percent_change.abs()
        ),
        "Gini Coefficient" => format!(
            "Centralization {} - Gini coefficient {} by {:.1}%",
            impact_word, direction, percent_change.abs()
        ),
        "Avg Stem Length" => format!(
            "Dandelion++ privacy {} - stem length {} by {:.1}%",
            impact_word, direction, percent_change.abs()
        ),
        _ => format!("{} {} by {:.1}%", metric_name, direction, percent_change.abs()),
    }
}

/// Generate overall assessment of upgrade impact.
fn generate_assessment(
    changes: &[MetricChange],
    pre: &Option<AggregatedMetrics>,
    post: &Option<AggregatedMetrics>,
) -> UpgradeAssessment {
    let mut findings = Vec::new();
    let mut concerns = Vec::new();
    let mut recommendations = Vec::new();

    let mut improved = 0;
    let mut degraded = 0;
    let mut unchanged = 0;

    for change in changes {
        match change.impact {
            ChangeImpact::Positive => {
                improved += 1;
                findings.push(change.interpretation.clone());
            }
            ChangeImpact::Negative => {
                degraded += 1;
                concerns.push(change.interpretation.clone());
            }
            ChangeImpact::Neutral => {
                unchanged += 1;
            }
        }
    }

    // Determine verdict
    let verdict = if pre.is_none() || post.is_none() {
        recommendations.push(
            "Provide upgrade manifest or manual timestamps to identify pre/post periods".to_string(),
        );
        UpgradeVerdict::Inconclusive
    } else if degraded > 0 && improved == 0 {
        recommendations.push("Consider reverting upgrade or investigating degraded metrics".to_string());
        UpgradeVerdict::Negative
    } else if improved > 0 && degraded == 0 {
        UpgradeVerdict::Positive
    } else if improved > 0 && degraded > 0 {
        recommendations.push("Investigate trade-offs between improved and degraded metrics".to_string());
        UpgradeVerdict::Mixed
    } else {
        findings.push("No significant changes detected in measured metrics".to_string());
        UpgradeVerdict::Neutral
    };

    UpgradeAssessment {
        verdict,
        metrics_improved: improved,
        metrics_degraded: degraded,
        metrics_unchanged: unchanged,
        findings,
        concerns,
        recommendations,
    }
}
