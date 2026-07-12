//! Per-window metric computation: TX propagation, bandwidth, peer counts,
//! synthetic spy accuracy, Gini coefficient, and Dandelion stem length.

use std::collections::{HashMap, HashSet};

use super::super::types::*;
use super::windows::{BwRef, SpyTrialSets};

/// Gap thresholds (ms) for multi-threshold stem length analysis.
pub(super) const FLUFF_GAP_THRESHOLDS_MS: &[f64] = &[500.0, 1000.0, 2000.0, 3000.0, 5000.0];

/// Index of the representative threshold (2000ms) used for backward-compatible avg_stem_length.
const REPRESENTATIVE_THRESHOLD_IDX: usize = 2;

/// Calculate all metrics for a single time window using pre-partitioned data.
///
/// Receives pre-windowed slices instead of re-scanning all observations.
pub(super) fn calculate_window_metrics_fast(
    window: &TimeWindow,
    window_txs: &[&Transaction],
    tx_obs_slice: &[&TxObservation],
    bw_slice: &[BwRef],
    avg_peer_count: Option<f64>,
    ip_to_agent: &HashMap<&str, &AnalysisAgentInfo>,
    spy_trials: &SpyTrialSets,
) -> WindowedMetrics {
    let mut metrics = WindowedMetrics {
        window: window.clone(),
        ..Default::default()
    };

    metrics.tx_count = window_txs.len();
    metrics.observation_count = tx_obs_slice.len();

    if window_txs.is_empty() || tx_obs_slice.is_empty() {
        // Still compute bandwidth even if no TXs
        let (bytes_sent, bytes_received, msg_count) = calculate_bandwidth_from_slice(bw_slice);
        if bytes_sent > 0 || bytes_received > 0 {
            metrics.bytes_sent = Some(bytes_sent);
            metrics.bytes_received = Some(bytes_received);
            metrics.total_bandwidth = Some(bytes_sent + bytes_received);
            metrics.bandwidth_message_count = Some(msg_count);
        }
        metrics.avg_peer_count = avg_peer_count;
        return metrics;
    }

    // Build TX hash -> observations mapping from the pre-windowed slice
    let window_tx_hashes: HashSet<&str> =
        window_txs.iter().map(|tx| tx.tx_hash.as_str()).collect();

    let mut tx_observations: HashMap<String, Vec<&TxObservation>> = HashMap::new();
    for &obs in tx_obs_slice {
        if window_tx_hashes.contains(obs.tx_hash.as_str()) {
            tx_observations
                .entry(obs.tx_hash.clone())
                .or_default()
                .push(obs);
        }
    }

    // Synthetic spy node analysis
    let (spy_accuracy_by_vis, spy_analyzable) =
        calculate_synthetic_spy_accuracy(window_txs, &tx_observations, ip_to_agent, spy_trials);
    metrics.spy_accuracy_by_visibility = spy_accuracy_by_vis;
    metrics.spy_analyzable_txs = spy_analyzable;

    // Propagation analysis
    let (avg_prop, median_prop, p95_prop) =
        calculate_propagation_for_window(&tx_observations);
    metrics.avg_propagation_ms = avg_prop;
    metrics.median_propagation_ms = median_prop;
    metrics.p95_propagation_ms = p95_prop;

    // Pre-computed connection state
    metrics.avg_peer_count = avg_peer_count;

    // Gini coefficient for first-seen distribution in this window
    metrics.gini_coefficient = calculate_gini_for_window(&tx_observations);

    // Dandelion analysis (gap-based fluff detection, multiple thresholds)
    let (avg_stem, paths_count, stem_by_threshold) =
        calculate_dandelion_for_window(window_txs, &tx_observations, ip_to_agent, FLUFF_GAP_THRESHOLDS_MS);
    metrics.avg_stem_length = avg_stem;
    metrics.stem_length_by_gap_threshold = stem_by_threshold;
    metrics.paths_reconstructed = paths_count;

    // Bandwidth analysis from pre-windowed slice
    let (bytes_sent, bytes_received, msg_count) = calculate_bandwidth_from_slice(bw_slice);
    if bytes_sent > 0 || bytes_received > 0 {
        metrics.bytes_sent = Some(bytes_sent);
        metrics.bytes_received = Some(bytes_received);
        metrics.total_bandwidth = Some(bytes_sent + bytes_received);
        metrics.bandwidth_message_count = Some(msg_count);
    }

    metrics
}

/// Calculate bandwidth metrics from a pre-windowed slice of bandwidth events.
fn calculate_bandwidth_from_slice(bw_slice: &[BwRef]) -> (u64, u64, u64) {
    let mut bytes_sent: u64 = 0;
    let mut bytes_received: u64 = 0;
    let mut message_count: u64 = 0;

    for bw in bw_slice {
        if bw.event.is_sent {
            bytes_sent += bw.event.bytes;
        } else {
            bytes_received += bw.event.bytes;
        }
        message_count += 1;
    }

    (bytes_sent, bytes_received, message_count)
}

/// Calculate synthetic spy accuracy at multiple visibility levels.
///
/// For each visibility level, for each trial:
///   For each TX, find earliest observation from a monitored node,
///   infer originator = source_ip of that observation.
///   Compare to true sender IP.
/// Average accuracy across trials for each level.
fn calculate_synthetic_spy_accuracy(
    transactions: &[&Transaction],
    tx_observations: &HashMap<String, Vec<&TxObservation>>,
    ip_to_agent: &HashMap<&str, &AnalysisAgentInfo>,
    spy_trials: &SpyTrialSets,
) -> (Option<Vec<f64>>, usize) {
    // Count analyzable TXs (have observations and a known sender IP)
    let mut analyzable = 0usize;
    for tx in transactions {
        if let Some(observations) = tx_observations.get(&tx.tx_hash) {
            if observations.is_empty() {
                continue;
            }
            let true_sender_ip = ip_to_agent
                .iter()
                .find(|(_, agent)| agent.id == tx.sender_id)
                .map(|(ip, _)| *ip);
            if true_sender_ip.is_some() {
                analyzable += 1;
            }
        }
    }

    if analyzable == 0 {
        return (None, 0);
    }

    let mut level_accuracies = Vec::with_capacity(spy_trials.visibility_levels.len());
    for level_trials in &spy_trials.trial_sets {
        let mut trial_accuracies = Vec::new();
        for monitored_set in level_trials {
            let mut correct = 0;
            let mut total = 0;
            for tx in transactions {
                if let Some(observations) = tx_observations.get(&tx.tx_hash) {
                    let true_sender_ip = ip_to_agent
                        .iter()
                        .find(|(_, agent)| agent.id == tx.sender_id)
                        .map(|(ip, _)| *ip);
                    if true_sender_ip.is_none() {
                        continue;
                    }
                    let true_ip = true_sender_ip
                        .expect("invariant: true_sender_ip.is_none() handled by continue above");

                    // Find earliest observation from a monitored node
                    let earliest = observations
                        .iter()
                        .filter(|obs| monitored_set.contains(&obs.node_id))
                        .min_by(|a, b| {
                            a.timestamp
                                .partial_cmp(&b.timestamp)
                                .unwrap_or(std::cmp::Ordering::Equal)
                        });

                    if let Some(obs) = earliest {
                        total += 1;
                        if obs.source_ip == true_ip {
                            correct += 1;
                        }
                    }
                }
            }
            if total > 0 {
                trial_accuracies.push(correct as f64 / total as f64);
            }
        }
        if !trial_accuracies.is_empty() {
            let avg = trial_accuracies.iter().sum::<f64>() / trial_accuracies.len() as f64;
            level_accuracies.push(avg);
        } else {
            level_accuracies.push(0.0);
        }
    }

    (Some(level_accuracies), analyzable)
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

    // stats:: helpers sort internally and average even-length medians.
    let avg = crate::analysis::stats::mean(&all_propagation_times);
    let median = crate::analysis::stats::median(&all_propagation_times);
    let p95 = crate::analysis::stats::percentile(&all_propagation_times, 95.0);

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

    // Calculate Gini coefficient over the per-node first-seen counts.
    let values: Vec<f64> = first_seen_counts.values().map(|&v| v as f64).collect();
    Some(crate::analysis::stats::gini(&values))
}

/// Trace stem length for a single TX with a given fluff gap threshold.
///
/// Walks the chain of relays starting from the originator. At each step, if 3+
/// recipients are found from the current sender, checks whether the time gap
/// between the 1st and 3rd observation is within `threshold_ms`. If so, it's
/// a genuine fluff broadcast and the chain stops. Otherwise, the first
/// observation is a stem relay (the rest are later gossip re-relays).
fn trace_stem_with_threshold(
    sorted_obs: &[&TxObservation],
    originator_ip: &str,
    node_to_ip: &HashMap<&str, &str>,
    threshold_ms: f64,
) -> usize {
    let mut stem_length = 0usize;
    let mut used: HashSet<usize> = HashSet::new();

    // Find first observation from originator
    let first_hop_idx = sorted_obs
        .iter()
        .enumerate()
        .find(|(_, obs)| obs.source_ip == originator_ip)
        .map(|(i, _)| i);

    if let Some(idx) = first_hop_idx {
        used.insert(idx);
        stem_length = 1;

        let mut current_sender_ip = node_to_ip
            .get(sorted_obs[idx].node_id.as_str())
            .copied();

        for _ in 0..50 {
            if current_sender_ip.is_none() {
                break;
            }

            let sender_ip = current_sender_ip
                .expect("invariant: current_sender_ip.is_none() handled by break above");

            let from_current: Vec<(usize, &TxObservation)> = sorted_obs
                .iter()
                .enumerate()
                .filter(|(i, obs)| !used.contains(i) && obs.source_ip == sender_ip)
                .map(|(i, obs)| (i, *obs))
                .collect();

            if from_current.is_empty() {
                break;
            }

            // Check for fluff (3+ recipients with clustered timing)
            if from_current.len() >= 3 {
                let first_time = from_current[0].1.timestamp;
                let third_time = from_current[2].1.timestamp;
                let gap_ms = (third_time - first_time) * 1000.0;

                if gap_ms <= threshold_ms {
                    // Genuine fluff broadcast -> stop
                    break;
                }
                // Large gap -> stem relay + later gossip, fall through
            }

            // Take first recipient as next stem hop
            let (next_idx, next_obs) = from_current[0];
            used.insert(next_idx);
            stem_length += 1;

            current_sender_ip = node_to_ip.get(next_obs.node_id.as_str()).copied();
        }
    }

    stem_length
}

/// Calculate simplified Dandelion metrics for a window with multi-threshold gap detection.
fn calculate_dandelion_for_window(
    transactions: &[&Transaction],
    tx_observations: &HashMap<String, Vec<&TxObservation>>,
    ip_to_agent: &HashMap<&str, &AnalysisAgentInfo>,
    gap_thresholds_ms: &[f64],
) -> (Option<f64>, usize, Option<Vec<f64>>) {
    // Build node_to_ip map once
    let node_to_ip: HashMap<&str, &str> = ip_to_agent
        .iter()
        .map(|(ip, agent)| (agent.id.as_str(), *ip))
        .collect();

    let mut per_threshold_lengths: Vec<Vec<f64>> = vec![Vec::new(); gap_thresholds_ms.len()];
    let mut paths_count = 0usize;

    for tx in transactions {
        if let Some(observations) = tx_observations.get(&tx.tx_hash) {
            if observations.is_empty() {
                continue;
            }

            let originator_ip = ip_to_agent
                .iter()
                .find(|(_, agent)| agent.id == tx.sender_id)
                .map(|(ip, _)| *ip);

            if originator_ip.is_none() {
                continue;
            }

            let originator_ip =
                originator_ip.expect("invariant: originator_ip.is_none() handled by continue above");

            // Sort observations once
            let mut sorted_obs: Vec<&TxObservation> = observations.iter().copied().collect();
            sorted_obs.sort_by(|a, b| {
                a.timestamp
                    .partial_cmp(&b.timestamp)
                    .unwrap_or(std::cmp::Ordering::Equal)
            });

            let mut any_positive = false;
            for (t_idx, &threshold_ms) in gap_thresholds_ms.iter().enumerate() {
                let stem_len = trace_stem_with_threshold(
                    &sorted_obs,
                    originator_ip,
                    &node_to_ip,
                    threshold_ms,
                );
                if stem_len > 0 {
                    per_threshold_lengths[t_idx].push(stem_len as f64);
                    any_positive = true;
                }
            }

            if any_positive {
                paths_count += 1;
            }
        }
    }

    if paths_count == 0 {
        return (None, 0, None);
    }

    // Compute per-threshold averages
    let threshold_avgs: Vec<f64> = per_threshold_lengths
        .iter()
        .map(|lengths| {
            if lengths.is_empty() {
                0.0
            } else {
                lengths.iter().sum::<f64>() / lengths.len() as f64
            }
        })
        .collect();

    // Representative value: use the middle threshold (2000ms) for backward compat
    let representative_idx = REPRESENTATIVE_THRESHOLD_IDX.min(threshold_avgs.len().saturating_sub(1));
    let avg_stem = threshold_avgs.get(representative_idx).copied();

    (avg_stem, paths_count, Some(threshold_avgs))
}
