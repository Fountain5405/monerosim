//! Result assembly: aggregate per-window metrics into period summaries,
//! compare pre vs post upgrade periods, and generate the overall assessment.

use std::collections::HashMap;

use super::super::time_window::*;
use super::super::types::*;
use super::metrics::FLUFF_GAP_THRESHOLDS_MS;

/// Create an aggregated summary for a labeled period.
pub(super) fn create_period_summary(
    label: &str,
    by_label: &HashMap<String, Vec<&WindowedMetrics>>,
) -> Option<AggregatedMetrics> {
    let windows = by_label.get(label)?;

    if windows.is_empty() {
        return None;
    }

    let start = windows
        .iter()
        .map(|w| w.window.start)
        .min_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal))?;
    let end = windows
        .iter()
        .map(|w| w.window.end)
        .max_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal))?;
    let total_txs: usize = windows.iter().map(|w| w.tx_count).sum();

    // Calculate per-visibility-level spy accuracy stats
    // Determine number of visibility levels from the first window that has data
    let num_levels = windows
        .iter()
        .filter_map(|w| w.spy_accuracy_by_visibility.as_ref())
        .map(|v| v.len())
        .next()
        .unwrap_or(0);

    let (mean_spy_by_vis, std_spy_by_vis) = if num_levels > 0 {
        let mut means = Vec::with_capacity(num_levels);
        let mut stds = Vec::with_capacity(num_levels);
        for level_idx in 0..num_levels {
            let values: Vec<Option<f64>> = windows
                .iter()
                .map(|w| {
                    w.spy_accuracy_by_visibility
                        .as_ref()
                        .and_then(|v| v.get(level_idx).copied())
                })
                .collect();
            let (m, s) = calculate_stats(&values);
            means.push(m.unwrap_or(0.0));
            stds.push(s.unwrap_or(0.0));
        }
        (Some(means), Some(stds))
    } else {
        (None, None)
    };

    let prop_values: Vec<Option<f64>> = windows.iter().map(|w| w.avg_propagation_ms).collect();
    let (mean_prop, std_prop) = calculate_stats(&prop_values);

    let peer_values: Vec<Option<f64>> = windows.iter().map(|w| w.avg_peer_count).collect();
    let (mean_peer, std_peer) = calculate_stats(&peer_values);

    let gini_values: Vec<Option<f64>> = windows.iter().map(|w| w.gini_coefficient).collect();
    let (mean_gini, std_gini) = calculate_stats(&gini_values);

    let stem_values: Vec<Option<f64>> = windows.iter().map(|w| w.avg_stem_length).collect();
    let (mean_stem, std_stem) = calculate_stats(&stem_values);

    // Per-threshold stem length aggregation (mirrors spy accuracy pattern)
    let num_thresholds = windows
        .iter()
        .filter_map(|w| w.stem_length_by_gap_threshold.as_ref())
        .map(|v| v.len())
        .next()
        .unwrap_or(0);

    let (mean_stem_by_threshold, std_stem_by_threshold) = if num_thresholds > 0 {
        let mut means = Vec::with_capacity(num_thresholds);
        let mut stds = Vec::with_capacity(num_thresholds);
        for t_idx in 0..num_thresholds {
            let values: Vec<Option<f64>> = windows
                .iter()
                .map(|w| {
                    w.stem_length_by_gap_threshold
                        .as_ref()
                        .and_then(|v| v.get(t_idx).copied())
                })
                .collect();
            let (m, s) = calculate_stats(&values);
            means.push(m.unwrap_or(0.0));
            stds.push(s.unwrap_or(0.0));
        }
        (Some(means), Some(stds))
    } else {
        (None, None)
    };

    // Bandwidth aggregation
    let total_bytes_sent: u64 = windows.iter().filter_map(|w| w.bytes_sent).sum();
    let total_bytes_received: u64 = windows.iter().filter_map(|w| w.bytes_received).sum();
    let total_bandwidth: u64 = windows.iter().filter_map(|w| w.total_bandwidth).sum();

    let bandwidth_values: Vec<Option<f64>> = windows
        .iter()
        .map(|w| w.total_bandwidth.map(|b| b as f64))
        .collect();
    let (mean_bw, std_bw) = calculate_stats(&bandwidth_values);

    Some(AggregatedMetrics {
        period_label: label.to_string(),
        start,
        end,
        window_count: windows.len(),
        total_txs,
        mean_spy_accuracy_by_visibility: mean_spy_by_vis,
        mean_propagation_ms: mean_prop,
        mean_peer_count: mean_peer,
        mean_gini: mean_gini,
        mean_stem_length: mean_stem,
        mean_stem_length_by_gap_threshold: mean_stem_by_threshold,
        std_spy_accuracy_by_visibility: std_spy_by_vis,
        std_propagation_ms: std_prop,
        std_peer_count: std_peer,
        std_gini: std_gini,
        std_stem_length: std_stem,
        std_stem_length_by_gap_threshold: std_stem_by_threshold,
        total_bytes_sent: if total_bytes_sent > 0 {
            Some(total_bytes_sent)
        } else {
            None
        },
        total_bytes_received: if total_bytes_received > 0 {
            Some(total_bytes_received)
        } else {
            None
        },
        total_bandwidth: if total_bandwidth > 0 {
            Some(total_bandwidth)
        } else {
            None
        },
        mean_bandwidth_per_window: mean_bw,
        std_bandwidth_per_window: std_bw,
        windows: windows.iter().map(|w| (*w).clone()).collect(),
    })
}

/// Compare pre and post upgrade periods.
pub(super) fn compare_periods(
    pre: &AggregatedMetrics,
    post: &AggregatedMetrics,
) -> Vec<MetricChange> {
    let mut changes = Vec::new();

    // Helper to create a metric change with explicit sample extraction
    let build_change = |name: &str,
                        pre_v: f64,
                        post_v: f64,
                        pre_samples: Vec<f64>,
                        post_samples: Vec<f64>,
                        higher_is_better: bool|
     -> MetricChange {
        let absolute_change = post_v - pre_v;
        let percent_change = if pre_v != 0.0 {
            (absolute_change / pre_v) * 100.0
        } else {
            0.0
        };

        let p_value = welch_t_test(&pre_samples, &post_samples);
        let significant = is_significant(p_value);

        let impact = if !significant {
            ChangeImpact::Neutral
        } else if higher_is_better {
            if absolute_change > 0.0 {
                ChangeImpact::Positive
            } else {
                ChangeImpact::Negative
            }
        } else {
            if absolute_change < 0.0 {
                ChangeImpact::Positive
            } else {
                ChangeImpact::Negative
            }
        };

        let interpretation = generate_interpretation(name, percent_change, significant, impact);

        MetricChange {
            metric_name: name.to_string(),
            pre_value: pre_v,
            post_value: post_v,
            absolute_change,
            percent_change,
            p_value,
            statistically_significant: significant,
            interpretation,
            impact,
        }
    };

    // Helper for simple Option<f64> metrics
    let add_change = |name: &str,
                      pre_val: Option<f64>,
                      post_val: Option<f64>,
                      extract: &dyn Fn(&WindowedMetrics) -> Option<f64>,
                      higher_is_better: bool|
     -> Option<MetricChange> {
        let (pre_v, post_v) = (pre_val?, post_val?);
        let pre_samples: Vec<f64> = pre.windows.iter().filter_map(extract).collect();
        let post_samples: Vec<f64> = post.windows.iter().filter_map(extract).collect();
        Some(build_change(
            name,
            pre_v,
            post_v,
            pre_samples,
            post_samples,
            higher_is_better,
        ))
    };

    // Per-visibility-level spy accuracy comparisons (lower is better)
    let visibility_levels = [0.05, 0.10, 0.20, 0.30, 0.50];
    if let (Some(pre_means), Some(post_means)) = (
        &pre.mean_spy_accuracy_by_visibility,
        &post.mean_spy_accuracy_by_visibility,
    ) {
        for (level_idx, &vis) in visibility_levels.iter().enumerate() {
            if let (Some(&pre_v), Some(&post_v)) =
                (pre_means.get(level_idx), post_means.get(level_idx))
            {
                let name = format!("Spy Acc ({}% vis)", (vis * 100.0) as u32);
                let pre_samples: Vec<f64> = pre
                    .windows
                    .iter()
                    .filter_map(|w| {
                        w.spy_accuracy_by_visibility
                            .as_ref()
                            .and_then(|v| v.get(level_idx).copied())
                    })
                    .collect();
                let post_samples: Vec<f64> = post
                    .windows
                    .iter()
                    .filter_map(|w| {
                        w.spy_accuracy_by_visibility
                            .as_ref()
                            .and_then(|v| v.get(level_idx).copied())
                    })
                    .collect();
                changes.push(build_change(
                    &name,
                    pre_v,
                    post_v,
                    pre_samples,
                    post_samples,
                    false,
                ));
            }
        }
    }

    // Propagation: Lower is better (faster network)
    if let Some(change) = add_change(
        "Avg Propagation (ms)",
        pre.mean_propagation_ms,
        post.mean_propagation_ms,
        &|w: &WindowedMetrics| w.avg_propagation_ms,
        false,
    ) {
        changes.push(change);
    }

    // Peer count: Higher is better (more connectivity)
    if let Some(change) = add_change(
        "Avg Peer Count",
        pre.mean_peer_count,
        post.mean_peer_count,
        &|w: &WindowedMetrics| w.avg_peer_count,
        true,
    ) {
        changes.push(change);
    }

    // Gini: Lower is better (less centralized)
    if let Some(change) = add_change(
        "Gini Coefficient",
        pre.mean_gini,
        post.mean_gini,
        &|w: &WindowedMetrics| w.gini_coefficient,
        false,
    ) {
        changes.push(change);
    }

    // Stem length: Higher is better (better privacy)
    if let Some(change) = add_change(
        "Avg Stem Length",
        pre.mean_stem_length,
        post.mean_stem_length,
        &|w: &WindowedMetrics| w.avg_stem_length,
        true,
    ) {
        changes.push(change);
    }

    // Per-threshold stem length comparisons (higher is better)
    if let (Some(pre_means), Some(post_means)) = (
        &pre.mean_stem_length_by_gap_threshold,
        &post.mean_stem_length_by_gap_threshold,
    ) {
        for (t_idx, &threshold) in FLUFF_GAP_THRESHOLDS_MS.iter().enumerate() {
            if let (Some(&pre_v), Some(&post_v)) = (pre_means.get(t_idx), post_means.get(t_idx)) {
                let name = format!("Stem Len ({}ms gap)", threshold as u64);
                let pre_samples: Vec<f64> = pre
                    .windows
                    .iter()
                    .filter_map(|w| {
                        w.stem_length_by_gap_threshold
                            .as_ref()
                            .and_then(|v| v.get(t_idx).copied())
                    })
                    .collect();
                let post_samples: Vec<f64> = post
                    .windows
                    .iter()
                    .filter_map(|w| {
                        w.stem_length_by_gap_threshold
                            .as_ref()
                            .and_then(|v| v.get(t_idx).copied())
                    })
                    .collect();
                changes.push(build_change(
                    &name,
                    pre_v,
                    post_v,
                    pre_samples,
                    post_samples,
                    true,
                ));
            }
        }
    }

    // Bandwidth: Lower is better (more efficient)
    if let Some(change) = add_change(
        "Bandwidth per Window",
        pre.mean_bandwidth_per_window,
        post.mean_bandwidth_per_window,
        &|w: &WindowedMetrics| w.total_bandwidth.map(|b| b as f64),
        false,
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
        name if name.starts_with("Spy Acc (") => format!(
            "Privacy {} - {} inference {} by {:.1}%",
            impact_word,
            name,
            direction,
            percent_change.abs()
        ),
        "Avg Propagation (ms)" => format!(
            "Network speed {} - propagation time {} by {:.1}%",
            impact_word,
            direction,
            percent_change.abs()
        ),
        "Avg Peer Count" => format!(
            "Connectivity {} - average peer count {} by {:.1}%",
            impact_word,
            direction,
            percent_change.abs()
        ),
        "Gini Coefficient" => format!(
            "Centralization {} - Gini coefficient {} by {:.1}%",
            impact_word,
            direction,
            percent_change.abs()
        ),
        name if name == "Avg Stem Length" || name.starts_with("Stem Len (") => format!(
            "Dandelion++ privacy {} - stem length {} by {:.1}%",
            impact_word,
            direction,
            percent_change.abs()
        ),
        "Bandwidth per Window" => format!(
            "Bandwidth efficiency {} - data usage {} by {:.1}%",
            impact_word,
            direction,
            percent_change.abs()
        ),
        _ => format!(
            "{} {} by {:.1}%",
            metric_name,
            direction,
            percent_change.abs()
        ),
    }
}

/// Generate overall assessment of upgrade impact.
pub(super) fn generate_assessment(
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
            "Provide upgrade manifest or manual timestamps to identify pre/post periods"
                .to_string(),
        );
        UpgradeVerdict::Inconclusive
    } else if degraded > 0 && improved == 0 {
        recommendations
            .push("Consider reverting upgrade or investigating degraded metrics".to_string());
        UpgradeVerdict::Negative
    } else if improved > 0 && degraded == 0 {
        UpgradeVerdict::Positive
    } else if improved > 0 && degraded > 0 {
        recommendations
            .push("Investigate trade-offs between improved and degraded metrics".to_string());
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
