//! Spy node vulnerability analysis.
//!
//! Analyzes how effectively a spy node could deanonymize transaction origins
//! by observing first-seen timing patterns.

use std::collections::HashMap;

use super::types::*;

/// Analyze spy node vulnerability for all transactions
pub fn analyze_spy_vulnerability(
    transactions: &[Transaction],
    log_data: &HashMap<String, NodeLogData>,
    agents: &[AgentInfo],
) -> SpyNodeReport {
    // Build IP-to-agent mapping
    let ip_to_agent: HashMap<&str, &AgentInfo> = agents
        .iter()
        .map(|a| (a.ip_addr.as_str(), a))
        .collect();

    // Build TX hash to observations mapping
    let mut tx_observations: HashMap<String, Vec<&TxObservation>> = HashMap::new();
    for (_, node_data) in log_data {
        for obs in &node_data.tx_observations {
            tx_observations
                .entry(obs.tx_hash.clone())
                .or_default()
                .push(obs);
        }
    }

    let mut analyses = Vec::new();
    let mut correct_inferences = 0;

    for tx in transactions {
        if let Some(observations) = tx_observations.get(&tx.tx_hash) {
            let analysis = analyze_single_tx(tx, observations, &ip_to_agent);
            if analysis.inference_correct {
                correct_inferences += 1;
            }
            analyses.push(analysis);
        }
    }

    let total_txs = analyses.len();
    let inference_accuracy = if total_txs > 0 {
        correct_inferences as f64 / total_txs as f64
    } else {
        0.0
    };

    // Calculate timing distribution
    let timing_distribution = calculate_timing_distribution(&analyses);

    // Find vulnerable senders
    let vulnerable_senders = find_vulnerable_senders(&analyses);

    SpyNodeReport {
        total_transactions: transactions.len(),
        analyzable_transactions: total_txs,
        inference_accuracy,
        timing_spread_distribution: timing_distribution,
        vulnerable_senders,
        per_tx_analysis: analyses,
    }
}

/// Analyze a single transaction for spy node vulnerability
fn analyze_single_tx(
    tx: &Transaction,
    observations: &[&TxObservation],
    ip_to_agent: &HashMap<&str, &AgentInfo>,
) -> SpyNodeTxAnalysis {
    // Sort observations by timestamp
    let mut sorted_obs: Vec<&TxObservation> = observations.to_vec();
    sorted_obs.sort_by(|a, b| a.timestamp.partial_cmp(&b.timestamp).unwrap_or(std::cmp::Ordering::Equal));

    let first_timestamp = sorted_obs.first().map(|o| o.timestamp).unwrap_or(0.0);
    let last_timestamp = sorted_obs.last().map(|o| o.timestamp).unwrap_or(0.0);

    // Build first-seen entries (top 10)
    let first_seen_by: Vec<FirstSeenEntry> = sorted_obs
        .iter()
        .take(10)
        .map(|obs| FirstSeenEntry {
            node_id: obs.node_id.clone(),
            timestamp: obs.timestamp,
            delta_from_first_ms: (obs.timestamp - first_timestamp) * 1000.0,
            source_ip: obs.source_ip.clone(),
        })
        .collect();

    // Calculate timing spread (first to last observation)
    let timing_spread_ms = (last_timestamp - first_timestamp) * 1000.0;

    // Infer originator: most common source_ip in early observations
    let inferred_originator_ip = infer_originator(&sorted_obs);

    // Get true sender IP
    let true_sender_ip = ip_to_agent
        .iter()
        .find(|(_, agent)| agent.id == tx.sender_id)
        .map(|(ip, _)| ip.to_string());

    // Check if inference is correct
    let inference_correct = match (&inferred_originator_ip, &true_sender_ip) {
        (Some(inferred), Some(true_ip)) => inferred == true_ip,
        _ => false,
    };

    // Calculate correlation confidence
    let correlation_confidence = calculate_correlation_confidence(
        &first_seen_by,
        timing_spread_ms,
        &inferred_originator_ip,
    );

    SpyNodeTxAnalysis {
        tx_hash: tx.tx_hash.clone(),
        true_sender: tx.sender_id.clone(),
        true_sender_ip,
        first_seen_by,
        correlation_confidence,
        timing_spread_ms,
        inferred_originator_ip,
        inference_correct,
    }
}

/// Infer the originator IP based on observation patterns
fn infer_originator(observations: &[&TxObservation]) -> Option<String> {
    if observations.is_empty() {
        return None;
    }

    // Strategy: Most common source_ip in early observations
    // Tie-breaker: Earlier observation wins (observations are pre-sorted by timestamp)
    let early_count = observations.len().min(5);
    let early_obs = &observations[..early_count];

    // Count occurrences and track first appearance index for deterministic tie-breaking
    let mut source_counts: HashMap<&str, (usize, usize)> = HashMap::new(); // ip -> (count, first_index)
    for (idx, obs) in early_obs.iter().enumerate() {
        source_counts
            .entry(&obs.source_ip)
            .and_modify(|(count, _)| *count += 1)
            .or_insert((1, idx));
    }

    // Find max count, then among ties pick the one with smallest first_index
    source_counts
        .into_iter()
        .max_by(|(_, (count_a, idx_a)), (_, (count_b, idx_b))| {
            // First compare by count (higher is better)
            // Then by index (lower is better for tie-breaking)
            count_a.cmp(count_b).then_with(|| idx_b.cmp(idx_a))
        })
        .map(|(ip, _)| ip.to_string())
}

/// Calculate confidence in origin inference
fn calculate_correlation_confidence(
    first_seen: &[FirstSeenEntry],
    timing_spread_ms: f64,
    inferred_ip: &Option<String>,
) -> f64 {
    let mut confidence = 0.0;

    // Timing factor: tight spread = higher confidence
    if timing_spread_ms < 100.0 {
        confidence += 0.3;
    } else if timing_spread_ms < 500.0 {
        confidence += 0.15;
    }

    // Source consistency factor
    if let Some(ref ip) = inferred_ip {
        let matching = first_seen
            .iter()
            .take(3)
            .filter(|e| &e.source_ip == ip)
            .count();
        confidence += (matching as f64 / 3.0) * 0.4;
    }

    // Multiple observers factor
    if first_seen.len() >= 3 {
        confidence += 0.3;
    } else if first_seen.len() >= 2 {
        confidence += 0.15;
    }

    confidence.min(1.0)
}

/// Calculate timing spread distribution
fn calculate_timing_distribution(analyses: &[SpyNodeTxAnalysis]) -> TimingDistribution {
    let mut high = 0;
    let mut moderate = 0;
    let mut low = 0;

    for analysis in analyses {
        if analysis.timing_spread_ms < 100.0 {
            high += 1;
        } else if analysis.timing_spread_ms < 500.0 {
            moderate += 1;
        } else {
            low += 1;
        }
    }

    TimingDistribution {
        high_vulnerability_count: high,
        moderate_vulnerability_count: moderate,
        low_vulnerability_count: low,
    }
}

/// Find senders that are particularly vulnerable
fn find_vulnerable_senders(analyses: &[SpyNodeTxAnalysis]) -> Vec<VulnerableSender> {
    // Group by sender
    let mut sender_analyses: HashMap<&str, Vec<&SpyNodeTxAnalysis>> = HashMap::new();
    for analysis in analyses {
        sender_analyses
            .entry(&analysis.true_sender)
            .or_default()
            .push(analysis);
    }

    // Calculate vulnerability for each sender
    let mut vulnerable: Vec<VulnerableSender> = sender_analyses
        .into_iter()
        .filter_map(|(sender_id, analyses)| {
            let high_confidence: Vec<_> = analyses
                .iter()
                .filter(|a| a.correlation_confidence > 0.5)
                .collect();

            if high_confidence.is_empty() {
                return None;
            }

            let correct = high_confidence.iter().filter(|a| a.inference_correct).count();
            let accuracy = correct as f64 / high_confidence.len() as f64;

            Some(VulnerableSender {
                sender_id: sender_id.to_string(),
                high_confidence_inferences: high_confidence.len(),
                accuracy,
            })
        })
        .collect();

    // Sort by number of high-confidence inferences
    vulnerable.sort_by(|a, b| b.high_confidence_inferences.cmp(&a.high_confidence_inferences));
    vulnerable.truncate(10);

    vulnerable
}
