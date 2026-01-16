//! TX Relay V2 Protocol Analysis.
//!
//! Compares TX relay v1 (NOTIFY_NEW_TRANSACTIONS) vs v2 (NOTIFY_TX_POOL_HASH + request)
//! protocol behavior. Useful for testing PR #9933 and mixed network scenarios.

use std::collections::{HashMap, HashSet};

use super::types::*;

/// Analyze TX relay v2 protocol usage and compare with v1
pub fn analyze_tx_relay_v2(
    transactions: &[Transaction],
    log_data: &HashMap<String, NodeLogData>,
    agents: &[AgentInfo],
) -> TxRelayV2Report {
    let protocol_usage = analyze_protocol_usage(log_data);
    let delivery_analysis = analyze_tx_delivery(transactions, log_data, agents);
    let connection_stability = analyze_connection_stability(log_data);
    let request_response = analyze_request_response(log_data);
    let assessment = generate_assessment(
        &protocol_usage,
        &delivery_analysis,
        &connection_stability,
        &request_response,
    );

    TxRelayV2Report {
        protocol_usage,
        delivery_analysis,
        connection_stability,
        request_response,
        assessment,
    }
}

/// Analyze protocol usage statistics (v1 vs v2 message counts)
fn analyze_protocol_usage(log_data: &HashMap<String, NodeLogData>) -> ProtocolUsageStats {
    let mut v1_tx_broadcasts = 0usize;
    let mut v2_hash_announcements = 0usize;
    let mut v2_tx_requests = 0usize;

    for (_, node_data) in log_data {
        // Count v1 messages (NOTIFY_NEW_TRANSACTIONS)
        v1_tx_broadcasts += node_data.tx_observations.len();

        // Count v2 messages
        v2_hash_announcements += node_data.tx_hash_announcements.len();
        v2_tx_requests += node_data.tx_requests.len();
    }

    let total_messages = v1_tx_broadcasts + v2_hash_announcements + v2_tx_requests;
    let v2_usage_ratio = if total_messages > 0 {
        (v2_hash_announcements + v2_tx_requests) as f64 / total_messages as f64
    } else {
        0.0
    };

    ProtocolUsageStats {
        v1_tx_broadcasts,
        v2_hash_announcements,
        v2_tx_requests,
        v2_usage_ratio,
    }
}

/// Analyze TX delivery to identify lost transactions
fn analyze_tx_delivery(
    transactions: &[Transaction],
    log_data: &HashMap<String, NodeLogData>,
    agents: &[AgentInfo],
) -> TxDeliveryAnalysis {
    // Build set of TX hashes that were observed anywhere in the network
    let mut observed_txs: HashSet<String> = HashSet::new();
    let mut tx_observation_count: HashMap<String, HashSet<String>> = HashMap::new(); // tx_hash -> set of node_ids

    for (node_id, node_data) in log_data {
        for obs in &node_data.tx_observations {
            observed_txs.insert(obs.tx_hash.clone());
            tx_observation_count
                .entry(obs.tx_hash.clone())
                .or_default()
                .insert(node_id.clone());
        }
    }

    // Find transactions that were created but never observed
    let txs_potentially_lost: Vec<String> = transactions
        .iter()
        .filter(|tx| !observed_txs.contains(&tx.tx_hash))
        .map(|tx| tx.tx_hash.clone())
        .collect();

    // Calculate per-node delivery rate
    let total_created = transactions.len();
    let mut per_node_delivery_rate: HashMap<String, f64> = HashMap::new();

    for agent in agents {
        let node_txs_seen = log_data
            .get(&agent.id)
            .map(|d| {
                d.tx_observations
                    .iter()
                    .map(|o| &o.tx_hash)
                    .collect::<HashSet<_>>()
                    .len()
            })
            .unwrap_or(0);

        let rate = if total_created > 0 {
            node_txs_seen as f64 / total_created as f64
        } else {
            0.0
        };
        per_node_delivery_rate.insert(agent.id.clone(), rate);
    }

    // Calculate propagation coverage (how many nodes each TX reached on average)
    let total_active_nodes = log_data.len();
    let average_propagation_coverage = if !tx_observation_count.is_empty() && total_active_nodes > 0
    {
        tx_observation_count
            .values()
            .map(|nodes| nodes.len() as f64 / total_active_nodes as f64)
            .sum::<f64>()
            / tx_observation_count.len() as f64
    } else {
        0.0
    };

    // Count transactions that reached all active nodes
    let txs_fully_propagated = tx_observation_count
        .values()
        .filter(|nodes| nodes.len() >= total_active_nodes.saturating_sub(2)) // Allow 2 node margin
        .count();

    TxDeliveryAnalysis {
        total_txs_created: transactions.len(),
        txs_fully_propagated,
        txs_in_blocks: 0, // Will be set by caller if block data available
        txs_potentially_lost,
        per_node_delivery_rate,
        average_propagation_coverage,
    }
}

/// Analyze connection stability metrics
fn analyze_connection_stability(log_data: &HashMap<String, NodeLogData>) -> ConnectionStabilityMetrics {
    let mut total_drops = 0usize;
    let mut drops_tx_verification = 0usize;
    let mut drops_duplicate_tx = 0usize;
    let mut drops_protocol_violation = 0usize;
    let mut drops_other = 0usize;
    let mut drops_by_node: HashMap<String, usize> = HashMap::new();

    // Track connection durations
    let mut connection_durations: Vec<f64> = Vec::new();

    for (node_id, node_data) in log_data {
        // Count drops by reason
        for drop in &node_data.connection_drops {
            total_drops += 1;
            *drops_by_node.entry(node_id.clone()).or_default() += 1;

            match drop.reason.as_str() {
                "tx_verification_failed" => drops_tx_verification += 1,
                "duplicate_tx" => drops_duplicate_tx += 1,
                "protocol_violation" => drops_protocol_violation += 1,
                _ => drops_other += 1,
            }
        }

        // Calculate connection durations from open/close events
        let mut open_times: HashMap<String, f64> = HashMap::new(); // connection_id -> open_time

        for event in &node_data.connection_events {
            if event.is_open {
                open_times.insert(event.connection_id.clone(), event.timestamp);
            } else if let Some(open_time) = open_times.remove(&event.connection_id) {
                let duration = event.timestamp - open_time;
                if duration > 0.0 {
                    connection_durations.push(duration);
                }
            }
        }
    }

    let average_connection_duration_sec = if !connection_durations.is_empty() {
        connection_durations.iter().sum::<f64>() / connection_durations.len() as f64
    } else {
        0.0
    };

    ConnectionStabilityMetrics {
        total_drops,
        drops_tx_verification,
        drops_duplicate_tx,
        drops_protocol_violation,
        drops_other,
        drops_by_node,
        average_connection_duration_sec,
    }
}

/// Analyze request/response patterns for v2 protocol
fn analyze_request_response(log_data: &HashMap<String, NodeLogData>) -> RequestResponseMetrics {
    let mut requests_sent = 0usize;
    let mut requests_received = 0usize;

    for (_, node_data) in log_data {
        for request in &node_data.tx_requests {
            if request.is_outgoing {
                requests_sent += 1;
            } else {
                requests_received += 1;
            }
        }
    }

    // Estimate fulfilled requests based on ratio of hash announcements to TX observations
    // In v2, we expect: hash_announcement -> request -> TX delivery
    // So if v2 is working, we should see observations following announcements
    let total_hash_announcements: usize = log_data
        .values()
        .map(|d| d.tx_hash_announcements.len())
        .sum();

    let total_tx_observations: usize = log_data
        .values()
        .map(|d| d.tx_observations.len())
        .sum();

    // If v2 is being used, fulfilled ~ min(requests_sent, tx_observations)
    let requests_fulfilled = if requests_sent > 0 {
        requests_sent.min(total_tx_observations)
    } else {
        0
    };

    let fulfillment_ratio = if requests_sent > 0 {
        requests_fulfilled as f64 / requests_sent as f64
    } else if total_hash_announcements > 0 {
        // v2 is active but no explicit requests tracked - estimate from observations
        1.0 // Assume working if we have observations
    } else {
        0.0
    };

    RequestResponseMetrics {
        requests_sent,
        requests_received,
        requests_fulfilled,
        fulfillment_ratio,
    }
}

/// Generate overall assessment of TX relay health
fn generate_assessment(
    protocol_usage: &ProtocolUsageStats,
    delivery_analysis: &TxDeliveryAnalysis,
    connection_stability: &ConnectionStabilityMetrics,
    request_response: &RequestResponseMetrics,
) -> TxRelayAssessment {
    let mut health_score: u32 = 100;
    let mut findings: Vec<String> = Vec::new();
    let mut recommendations: Vec<String> = Vec::new();

    // Check v2 protocol activity
    let v2_active = protocol_usage.v2_hash_announcements > 0 || protocol_usage.v2_tx_requests > 0;

    if v2_active {
        findings.push(format!(
            "TX Relay V2 protocol is ACTIVE: {} hash announcements, {} requests",
            protocol_usage.v2_hash_announcements, protocol_usage.v2_tx_requests
        ));

        if protocol_usage.v2_usage_ratio > 0.5 {
            findings.push(format!(
                "V2 protocol dominates network traffic ({:.1}% of messages)",
                protocol_usage.v2_usage_ratio * 100.0
            ));
        }
    } else {
        findings.push("TX Relay V2 protocol is NOT active - using V1 only".to_string());
    }

    // Check for lost transactions
    let has_lost_txs = !delivery_analysis.txs_potentially_lost.is_empty();
    if has_lost_txs {
        let lost_count = delivery_analysis.txs_potentially_lost.len();
        let lost_pct =
            (lost_count as f64 / delivery_analysis.total_txs_created.max(1) as f64) * 100.0;

        health_score = health_score.saturating_sub((lost_pct * 2.0) as u32);

        findings.push(format!(
            "WARNING: {} transactions ({:.1}%) were never observed in the network",
            lost_count, lost_pct
        ));

        recommendations.push(
            "Investigate lost transactions - may indicate v2 protocol compatibility issues"
                .to_string(),
        );
    }

    // Check propagation coverage
    if delivery_analysis.average_propagation_coverage < 0.8 {
        health_score = health_score.saturating_sub(10);
        findings.push(format!(
            "Low propagation coverage: {:.1}% average",
            delivery_analysis.average_propagation_coverage * 100.0
        ));
        recommendations.push("Check network connectivity - transactions not reaching all nodes".to_string());
    } else {
        findings.push(format!(
            "Good propagation coverage: {:.1}% average",
            delivery_analysis.average_propagation_coverage * 100.0
        ));
    }

    // Check connection stability
    let has_stability_issues = connection_stability.total_drops > 0;
    if has_stability_issues {
        let drop_rate = connection_stability.total_drops as f64
            / delivery_analysis.total_txs_created.max(1) as f64;

        if drop_rate > 0.1 {
            health_score = health_score.saturating_sub(15);
            findings.push(format!(
                "HIGH connection drop rate: {} drops ({:.1}% of TX count)",
                connection_stability.total_drops,
                drop_rate * 100.0
            ));
        }

        if connection_stability.drops_tx_verification > 0 {
            findings.push(format!(
                "TX verification failures caused {} connection drops",
                connection_stability.drops_tx_verification
            ));
            recommendations.push(
                "TX verification drops may indicate v1/v2 protocol mismatch".to_string(),
            );
        }

        if connection_stability.drops_duplicate_tx > 0 {
            findings.push(format!(
                "Duplicate TX detection caused {} connection drops",
                connection_stability.drops_duplicate_tx
            ));
        }
    }

    // Check v2 request fulfillment
    if v2_active && request_response.requests_sent > 0 {
        if request_response.fulfillment_ratio < 0.9 {
            health_score = health_score.saturating_sub(10);
            findings.push(format!(
                "V2 request fulfillment ratio is low: {:.1}%",
                request_response.fulfillment_ratio * 100.0
            ));
            recommendations.push(
                "Check if peers are responding to NOTIFY_REQUEST_TX_POOL_TXS correctly".to_string(),
            );
        } else {
            findings.push(format!(
                "V2 request fulfillment is good: {:.1}%",
                request_response.fulfillment_ratio * 100.0
            ));
        }
    }

    // Summary
    if health_score >= 90 {
        findings.insert(0, "TX relay is functioning NORMALLY".to_string());
    } else if health_score >= 70 {
        findings.insert(0, "TX relay has MINOR issues".to_string());
    } else if health_score >= 50 {
        findings.insert(0, "TX relay has MODERATE issues".to_string());
    } else {
        findings.insert(0, "TX relay has SEVERE issues".to_string());
    }

    TxRelayAssessment {
        health_score,
        v2_active,
        has_lost_txs,
        has_stability_issues,
        findings,
        recommendations,
    }
}

/// Generate a comparison report between two simulation runs (v1 vs v2)
pub fn compare_runs(
    v1_report: &TxRelayV2Report,
    v2_report: &TxRelayV2Report,
) -> Vec<String> {
    let mut comparison: Vec<String> = Vec::new();

    comparison.push("=== TX RELAY V1 vs V2 COMPARISON ===".to_string());
    comparison.push(String::new());

    // Protocol usage comparison
    comparison.push("Protocol Usage:".to_string());
    comparison.push(format!(
        "  V1 run - broadcasts: {}, v2 messages: {} (ratio: {:.1}%)",
        v1_report.protocol_usage.v1_tx_broadcasts,
        v1_report.protocol_usage.v2_hash_announcements + v1_report.protocol_usage.v2_tx_requests,
        v1_report.protocol_usage.v2_usage_ratio * 100.0
    ));
    comparison.push(format!(
        "  V2 run - broadcasts: {}, v2 messages: {} (ratio: {:.1}%)",
        v2_report.protocol_usage.v1_tx_broadcasts,
        v2_report.protocol_usage.v2_hash_announcements + v2_report.protocol_usage.v2_tx_requests,
        v2_report.protocol_usage.v2_usage_ratio * 100.0
    ));
    comparison.push(String::new());

    // Delivery comparison
    comparison.push("TX Delivery:".to_string());
    comparison.push(format!(
        "  V1 run - created: {}, lost: {}, coverage: {:.1}%",
        v1_report.delivery_analysis.total_txs_created,
        v1_report.delivery_analysis.txs_potentially_lost.len(),
        v1_report.delivery_analysis.average_propagation_coverage * 100.0
    ));
    comparison.push(format!(
        "  V2 run - created: {}, lost: {}, coverage: {:.1}%",
        v2_report.delivery_analysis.total_txs_created,
        v2_report.delivery_analysis.txs_potentially_lost.len(),
        v2_report.delivery_analysis.average_propagation_coverage * 100.0
    ));
    comparison.push(String::new());

    // Stability comparison
    comparison.push("Connection Stability:".to_string());
    comparison.push(format!(
        "  V1 run - drops: {} (tx_verify: {}, dup: {})",
        v1_report.connection_stability.total_drops,
        v1_report.connection_stability.drops_tx_verification,
        v1_report.connection_stability.drops_duplicate_tx
    ));
    comparison.push(format!(
        "  V2 run - drops: {} (tx_verify: {}, dup: {})",
        v2_report.connection_stability.total_drops,
        v2_report.connection_stability.drops_tx_verification,
        v2_report.connection_stability.drops_duplicate_tx
    ));
    comparison.push(String::new());

    // Health score comparison
    comparison.push("Health Assessment:".to_string());
    comparison.push(format!(
        "  V1 run - score: {}/100",
        v1_report.assessment.health_score
    ));
    comparison.push(format!(
        "  V2 run - score: {}/100",
        v2_report.assessment.health_score
    ));
    comparison.push(String::new());

    // Summary
    let score_diff =
        v2_report.assessment.health_score as i32 - v1_report.assessment.health_score as i32;
    let lost_diff = v2_report.delivery_analysis.txs_potentially_lost.len() as i32
        - v1_report.delivery_analysis.txs_potentially_lost.len() as i32;

    comparison.push("Summary:".to_string());
    if score_diff > 5 {
        comparison.push("  V2 protocol shows IMPROVEMENT over V1".to_string());
    } else if score_diff < -5 {
        comparison.push("  V2 protocol shows REGRESSION from V1".to_string());
    } else {
        comparison.push("  V2 protocol is EQUIVALENT to V1".to_string());
    }

    if lost_diff > 0 {
        comparison.push(format!(
            "  WARNING: V2 lost {} more transactions than V1",
            lost_diff
        ));
    } else if lost_diff < 0 {
        comparison.push(format!(
            "  V2 lost {} fewer transactions than V1",
            -lost_diff
        ));
    }

    comparison
}
