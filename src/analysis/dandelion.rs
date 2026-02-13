//! Dandelion++ stem path reconstruction and analysis.
//!
//! Reconstructs the propagation path of transactions through the network,
//! identifying stem phase (linear relay) vs fluff phase (broadcast).

use std::collections::HashMap;

use super::types::*;

/// Threshold for detecting fluff: if N nodes receive from same source within this window
const FLUFF_TIME_WINDOW_MS: f64 = 100.0;
/// Minimum recipients in window to consider it a fluff event
const FLUFF_MIN_RECIPIENTS: usize = 3;

/// Analyze Dandelion++ stem paths for all transactions
pub fn analyze_dandelion(
    transactions: &[Transaction],
    log_data: &HashMap<String, NodeLogData>,
    agents: &[AnalysisAgentInfo],
) -> DandelionReport {
    // Build IP -> node_id mapping
    let ip_to_node: HashMap<String, String> = agents
        .iter()
        .map(|a| (a.ip_addr.clone(), a.id.clone()))
        .collect();

    // Build node_id -> IP mapping
    let node_to_ip: HashMap<String, String> = agents
        .iter()
        .map(|a| (a.id.clone(), a.ip_addr.clone()))
        .collect();

    // Collect all TX observations grouped by tx_hash
    let mut tx_observations: HashMap<String, Vec<TxObservation>> = HashMap::new();
    for (_, node_data) in log_data {
        for obs in &node_data.tx_observations {
            tx_observations
                .entry(obs.tx_hash.clone())
                .or_default()
                .push(obs.clone());
        }
    }

    // Reconstruct paths for each transaction
    let mut paths: Vec<DandelionPath> = Vec::new();
    let mut node_stem_counts: HashMap<String, usize> = HashMap::new();
    let mut node_fluff_counts: HashMap<String, usize> = HashMap::new();
    let mut node_originator_counts: HashMap<String, usize> = HashMap::new();
    let mut node_stem_positions: HashMap<String, Vec<usize>> = HashMap::new();

    for tx in transactions {
        if let Some(observations) = tx_observations.get(&tx.tx_hash) {
            if let Some(path) = reconstruct_path(
                tx,
                observations,
                &ip_to_node,
                &node_to_ip,
            ) {
                // Update node statistics
                *node_originator_counts.entry(path.originator.clone()).or_default() += 1;

                for (pos, hop) in path.stem_path.iter().enumerate() {
                    if pos > 0 {
                        // Not the originator, this is a relay
                        *node_stem_counts.entry(hop.node_id.clone()).or_default() += 1;
                        node_stem_positions
                            .entry(hop.node_id.clone())
                            .or_default()
                            .push(pos);
                    }
                }

                if let Some(ref fluff_node) = path.fluff_node {
                    *node_fluff_counts.entry(fluff_node.clone()).or_default() += 1;
                }

                paths.push(path);
            }
        }
    }

    // Calculate statistics
    let stem_lengths: Vec<usize> = paths.iter().map(|p| p.stem_length).collect();
    let stem_durations: Vec<f64> = paths.iter().map(|p| p.stem_duration_ms).collect();

    let avg_stem_length = if !stem_lengths.is_empty() {
        stem_lengths.iter().sum::<usize>() as f64 / stem_lengths.len() as f64
    } else {
        0.0
    };

    let min_stem_length = stem_lengths.iter().copied().min().unwrap_or(0);
    let max_stem_length = stem_lengths.iter().copied().max().unwrap_or(0);

    // Stem length distribution
    let mut stem_length_distribution: HashMap<usize, usize> = HashMap::new();
    for &len in &stem_lengths {
        *stem_length_distribution.entry(len).or_default() += 1;
    }

    let avg_stem_duration_ms = if !stem_durations.is_empty() {
        stem_durations.iter().sum::<f64>() / stem_durations.len() as f64
    } else {
        0.0
    };

    // Calculate average hop delay
    let total_hops: usize = paths.iter().map(|p| p.stem_length.saturating_sub(1)).sum();
    let avg_hop_delay_ms = if total_hops > 0 {
        stem_durations.iter().sum::<f64>() / total_hops as f64
    } else {
        0.0
    };

    // Build per-node statistics
    let mut all_nodes: std::collections::HashSet<String> = std::collections::HashSet::new();
    all_nodes.extend(node_stem_counts.keys().cloned());
    all_nodes.extend(node_fluff_counts.keys().cloned());
    all_nodes.extend(node_originator_counts.keys().cloned());

    let node_stats: Vec<NodeDandelionStats> = all_nodes
        .into_iter()
        .map(|node_id| {
            let positions = node_stem_positions.get(&node_id);
            let avg_stem_position = if let Some(pos) = positions {
                if !pos.is_empty() {
                    pos.iter().sum::<usize>() as f64 / pos.len() as f64
                } else {
                    0.0
                }
            } else {
                0.0
            };

            NodeDandelionStats {
                node_id: node_id.clone(),
                stem_relay_count: *node_stem_counts.get(&node_id).unwrap_or(&0),
                fluff_point_count: *node_fluff_counts.get(&node_id).unwrap_or(&0),
                originator_count: *node_originator_counts.get(&node_id).unwrap_or(&0),
                avg_stem_position,
            }
        })
        .collect();

    // Find frequent fluff nodes
    let mut frequent_fluff_nodes: Vec<(String, usize)> = node_fluff_counts
        .into_iter()
        .filter(|(_, count)| *count >= 2)
        .collect();
    frequent_fluff_nodes.sort_by(|a, b| b.1.cmp(&a.1));
    frequent_fluff_nodes.truncate(10);

    // Count originator confirmations
    let originator_confirmed_count = paths.iter().filter(|p| p.originator_confirmed).count();

    // Generate privacy assessment
    let privacy_assessment = assess_privacy(&paths, transactions.len());

    DandelionReport {
        total_transactions: transactions.len(),
        paths_reconstructed: paths.len(),
        originator_confirmed_count,
        avg_stem_length,
        min_stem_length,
        max_stem_length,
        stem_length_distribution,
        avg_stem_duration_ms,
        avg_hop_delay_ms,
        node_stats,
        frequent_fluff_nodes,
        paths,
        privacy_assessment,
    }
}

/// Reconstruct the stem path for a single transaction
///
/// The stem path is a chain: originator -> A -> B -> C -> fluff
/// Each node in the chain receives from the previous node, then relays to exactly one next node.
/// The fluff point is where a node broadcasts to multiple peers simultaneously.
fn reconstruct_path(
    tx: &Transaction,
    observations: &[TxObservation],
    ip_to_node: &HashMap<String, String>,
    node_to_ip: &HashMap<String, String>,
) -> Option<DandelionPath> {
    if observations.is_empty() {
        return None;
    }

    // Sort observations by timestamp
    let mut sorted_obs = observations.to_vec();
    sorted_obs.sort_by(|a, b| {
        a.timestamp
            .partial_cmp(&b.timestamp)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    // Get originator info
    let originator = tx.sender_id.clone();
    let originator_ip = node_to_ip.get(&originator).cloned();

    // Build the stem path by following the chain of relays
    // Key insight: in stem phase, each receiver becomes the sender to exactly one next node
    // In fluff phase, one sender broadcasts to many nodes simultaneously

    let mut stem_path: Vec<StemHop> = Vec::new();
    #[allow(unused_assignments)]
    let mut current_sender_ip = originator_ip.clone();
    let mut used_observations: std::collections::HashSet<usize> = std::collections::HashSet::new();
    let mut fluff_node: Option<String> = None;
    let mut fluff_recipients = 0usize;

    // First, find the first observation that came from the originator
    let first_hop_idx = sorted_obs.iter().position(|obs| {
        originator_ip.as_ref().map(|ip| &obs.source_ip == ip).unwrap_or(false)
    });

    if let Some(idx) = first_hop_idx {
        // Start building chain from first hop
        let first_obs = &sorted_obs[idx];
        stem_path.push(StemHop {
            node_id: first_obs.node_id.clone(),
            from_node_id: Some(originator.clone()),
            from_ip: first_obs.source_ip.clone(),
            timestamp: first_obs.timestamp,
            delta_ms: 0.0,
        });
        used_observations.insert(idx);
        current_sender_ip = node_to_ip.get(&first_obs.node_id).cloned();
    } else {
        // Originator not found in observations, start from first observation
        let first_obs = &sorted_obs[0];
        let from_node = ip_to_node.get(&first_obs.source_ip).cloned();
        stem_path.push(StemHop {
            node_id: first_obs.node_id.clone(),
            from_node_id: from_node,
            from_ip: first_obs.source_ip.clone(),
            timestamp: first_obs.timestamp,
            delta_ms: 0.0,
        });
        used_observations.insert(0);
        current_sender_ip = node_to_ip.get(&first_obs.node_id).cloned();
    }

    // Follow the chain: find next observation where source_ip matches current node's IP
    let mut max_iterations = 100; // Prevent infinite loops
    while max_iterations > 0 {
        max_iterations -= 1;

        if current_sender_ip.is_none() {
            break;
        }

        let sender_ip = current_sender_ip.as_ref().unwrap();

        // Find all observations from the current sender that we haven't used
        let from_current: Vec<(usize, &TxObservation)> = sorted_obs
            .iter()
            .enumerate()
            .filter(|(i, obs)| !used_observations.contains(i) && &obs.source_ip == sender_ip)
            .collect();

        if from_current.is_empty() {
            // No more observations from this sender - end of traceable path
            break;
        }

        // Check if this is a fluff point: multiple nodes received from same sender
        if from_current.len() >= FLUFF_MIN_RECIPIENTS {
            // Check if they're within the time window (simultaneous broadcast)
            let first_time = from_current.first().unwrap().1.timestamp;
            let recipients_in_window = from_current
                .iter()
                .filter(|(_, obs)| (obs.timestamp - first_time) * 1000.0 <= FLUFF_TIME_WINDOW_MS)
                .count();

            if recipients_in_window >= FLUFF_MIN_RECIPIENTS {
                // This is the fluff point!
                fluff_node = stem_path.last().map(|h| h.node_id.clone());
                fluff_recipients = from_current.len();
                break;
            }
        }

        // Single relay (stem phase) - take the first/earliest one
        let (next_idx, next_obs) = from_current[0];
        let prev_timestamp = stem_path.last().map(|h| h.timestamp).unwrap_or(next_obs.timestamp);

        stem_path.push(StemHop {
            node_id: next_obs.node_id.clone(),
            from_node_id: ip_to_node.get(sender_ip).cloned(),
            from_ip: next_obs.source_ip.clone(),
            timestamp: next_obs.timestamp,
            delta_ms: (next_obs.timestamp - prev_timestamp) * 1000.0,
        });

        used_observations.insert(next_idx);
        current_sender_ip = node_to_ip.get(&next_obs.node_id).cloned();
    }

    // If no fluff detected, the last node in stem is likely the fluff point
    if fluff_node.is_none() {
        fluff_node = stem_path.last().map(|h| h.node_id.clone());
        // Count remaining observations as fluff recipients
        fluff_recipients = sorted_obs.len().saturating_sub(used_observations.len());
    }

    // Check if originator is confirmed (first hop came from originator)
    let originator_confirmed = stem_path
        .first()
        .and_then(|hop| hop.from_node_id.as_ref())
        .map(|from| from == &originator)
        .unwrap_or(false);

    let stem_length = stem_path.len();
    let stem_duration_ms = if stem_path.len() >= 2 {
        (stem_path.last().unwrap().timestamp - stem_path.first().unwrap().timestamp) * 1000.0
    } else {
        0.0
    };

    Some(DandelionPath {
        tx_hash: tx.tx_hash.clone(),
        originator,
        originator_ip,
        stem_path,
        fluff_node,
        stem_length,
        stem_duration_ms,
        fluff_recipients,
        originator_confirmed,
    })
}

/// Find the index where fluff (broadcast) begins
/// Returns the index of the first observation that's part of the fluff
#[allow(dead_code)]
fn find_fluff_point(
    sorted_obs: &[TxObservation],
    _ip_to_node: &HashMap<String, String>,
) -> Option<usize> {
    if sorted_obs.len() < FLUFF_MIN_RECIPIENTS + 1 {
        return None;
    }

    // Look for a point where multiple nodes receive from the same source in quick succession
    for i in 0..sorted_obs.len() {
        let base_time = sorted_obs[i].timestamp;
        let base_source = &sorted_obs[i].source_ip;

        // Count how many observations from same source within time window
        let mut same_source_count = 0;
        for j in i..sorted_obs.len() {
            let delta_ms = (sorted_obs[j].timestamp - base_time) * 1000.0;
            if delta_ms > FLUFF_TIME_WINDOW_MS {
                break;
            }
            if &sorted_obs[j].source_ip == base_source {
                same_source_count += 1;
            }
        }

        if same_source_count >= FLUFF_MIN_RECIPIENTS {
            return Some(i);
        }
    }

    None
}

/// Assess privacy based on Dandelion++ behavior
fn assess_privacy(paths: &[DandelionPath], _total_txs: usize) -> DandelionPrivacyAssessment {
    let mut findings: Vec<String> = Vec::new();
    let mut recommendations: Vec<String> = Vec::new();
    let mut privacy_score: u32 = 100;

    if paths.is_empty() {
        return DandelionPrivacyAssessment {
            privacy_score: 0,
            effective_anonymity: false,
            trivially_deanonymizable_pct: 100.0,
            findings: vec!["No transaction paths could be reconstructed".to_string()],
            recommendations: vec!["Check if logging is capturing TX propagation".to_string()],
        };
    }

    // Check stem length distribution
    let avg_stem_length: f64 =
        paths.iter().map(|p| p.stem_length).sum::<usize>() as f64 / paths.len() as f64;

    if avg_stem_length < 2.0 {
        privacy_score = privacy_score.saturating_sub(30);
        findings.push(format!(
            "Very short stem paths (avg {:.1} hops) - transactions often fluff immediately",
            avg_stem_length
        ));
        recommendations.push("Short stems reduce anonymity. Check Dandelion++ configuration.".to_string());
    } else if avg_stem_length < 4.0 {
        privacy_score = privacy_score.saturating_sub(10);
        findings.push(format!(
            "Moderate stem length (avg {:.1} hops)",
            avg_stem_length
        ));
    } else {
        findings.push(format!(
            "Good stem length (avg {:.1} hops) - provides reasonable anonymity",
            avg_stem_length
        ));
    }

    // Check originator confirmation rate
    let confirmed_count = paths.iter().filter(|p| p.originator_confirmed).count();
    let _confirmed_pct = (confirmed_count as f64 / paths.len() as f64) * 100.0;

    // Count trivially deanonymizable (stem length 1 = first hop reveals originator)
    let trivial_count = paths.iter().filter(|p| p.stem_length <= 1).count();
    let trivially_deanonymizable_pct = (trivial_count as f64 / paths.len() as f64) * 100.0;

    if trivially_deanonymizable_pct > 20.0 {
        privacy_score = privacy_score.saturating_sub(25);
        findings.push(format!(
            "HIGH RISK: {:.1}% of transactions have stem length <= 1 (trivially deanonymizable)",
            trivially_deanonymizable_pct
        ));
        recommendations.push(
            "Many transactions fluff immediately, revealing originator. Check network connectivity."
                .to_string(),
        );
    }

    // Check if certain nodes are over-represented as fluff points
    let mut fluff_counts: HashMap<String, usize> = HashMap::new();
    for path in paths {
        if let Some(ref node) = path.fluff_node {
            *fluff_counts.entry(node.clone()).or_default() += 1;
        }
    }

    let max_fluff_count = fluff_counts.values().copied().max().unwrap_or(0);
    let max_fluff_pct = (max_fluff_count as f64 / paths.len() as f64) * 100.0;

    if max_fluff_pct > 30.0 {
        privacy_score = privacy_score.saturating_sub(15);
        let top_fluff_node = fluff_counts
            .iter()
            .max_by_key(|(_, v)| *v)
            .map(|(k, _)| k.clone())
            .unwrap_or_default();
        findings.push(format!(
            "Centralized fluff point: {} fluffs {:.1}% of transactions",
            top_fluff_node, max_fluff_pct
        ));
        recommendations.push(
            "Fluff points are concentrated - this node could correlate many transactions".to_string(),
        );
    }

    let effective_anonymity = privacy_score >= 70 && trivially_deanonymizable_pct < 10.0;

    if effective_anonymity {
        findings.insert(0, "Dandelion++ is providing EFFECTIVE anonymity".to_string());
    } else if privacy_score >= 50 {
        findings.insert(0, "Dandelion++ is providing MODERATE anonymity".to_string());
    } else {
        findings.insert(0, "Dandelion++ is providing WEAK anonymity".to_string());
    }

    DandelionPrivacyAssessment {
        privacy_score,
        effective_anonymity,
        trivially_deanonymizable_pct,
        findings,
        recommendations,
    }
}

/// Format a stem path as a string for display
pub fn format_stem_path(path: &DandelionPath) -> String {
    let mut parts: Vec<String> = Vec::new();

    // Start with originator
    parts.push(format!("{} (originator)", path.originator));

    // Add each hop
    for hop in &path.stem_path {
        if hop.from_node_id.as_ref() != Some(&path.originator) || parts.len() > 1 {
            parts.push(hop.node_id.clone());
        }
    }

    // Mark fluff point
    if let Some(ref fluff_node) = path.fluff_node {
        if parts.last().map(|s| s.as_str()) != Some(fluff_node) {
            parts.push(format!("{} (fluff)", fluff_node));
        } else if let Some(last) = parts.last_mut() {
            *last = format!("{} (fluff)", fluff_node);
        }
    }

    parts.join(" → ")
}
