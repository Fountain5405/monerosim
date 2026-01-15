//! Report generation for transaction routing analysis.
//!
//! Generates both JSON and human-readable text reports.

use std::fs;
use std::path::Path;

use color_eyre::eyre::{Context, Result};

use super::types::*;

/// Generate JSON report
pub fn generate_json_report(report: &FullAnalysisReport, output_path: &Path) -> Result<()> {
    let json = serde_json::to_string_pretty(report)
        .context("Failed to serialize report to JSON")?;

    fs::write(output_path, json)
        .with_context(|| format!("Failed to write JSON report to {}", output_path.display()))?;

    log::info!("JSON report written to {}", output_path.display());
    Ok(())
}

/// Generate human-readable text report
pub fn generate_text_report(report: &FullAnalysisReport, output_path: &Path) -> Result<()> {
    let mut lines: Vec<String> = Vec::new();

    // Header
    lines.push("=".repeat(80));
    lines.push("                   MONEROSIM TRANSACTION ROUTING ANALYSIS".to_string());
    lines.push("=".repeat(80));
    lines.push(String::new());

    // Metadata
    lines.push(format!("Analysis Date: {}", report.metadata.analysis_timestamp));
    lines.push(format!("Data Directory: {}", report.metadata.simulation_data_dir));
    lines.push(format!("Nodes Analyzed: {}", report.metadata.total_nodes));
    lines.push(format!("Transactions: {}", report.metadata.total_transactions));
    lines.push(format!("Blocks: {}", report.metadata.total_blocks));
    lines.push(String::new());

    // Spy Node Analysis
    if let Some(ref spy) = report.spy_node_analysis {
        lines.push("=".repeat(80));
        lines.push("                          SPY NODE VULNERABILITY".to_string());
        lines.push("=".repeat(80));
        lines.push(String::new());

        lines.push(format!(
            "Overall Inference Accuracy: {:.1}%",
            spy.inference_accuracy * 100.0
        ));
        lines.push("  A spy node observing first-seen timing could correctly identify the sender".to_string());
        lines.push(format!(
            "  for {} out of {} transactions.",
            (spy.inference_accuracy * spy.analyzable_transactions as f64).round() as usize,
            spy.analyzable_transactions
        ));
        lines.push(String::new());

        lines.push("Timing Distribution:".to_string());
        lines.push(format!(
            "  < 100ms spread:  {} transactions (high vulnerability)",
            spy.timing_spread_distribution.high_vulnerability_count
        ));
        lines.push(format!(
            "  100-500ms:       {} transactions (moderate vulnerability)",
            spy.timing_spread_distribution.moderate_vulnerability_count
        ));
        lines.push(format!(
            "  > 500ms:         {} transactions (low vulnerability)",
            spy.timing_spread_distribution.low_vulnerability_count
        ));
        lines.push(String::new());

        if !spy.vulnerable_senders.is_empty() {
            lines.push("Most Observable Senders:".to_string());
            for (i, sender) in spy.vulnerable_senders.iter().take(5).enumerate() {
                lines.push(format!(
                    "  {}. {}: {} high-confidence inferences ({:.0}% accurate)",
                    i + 1,
                    sender.sender_id,
                    sender.high_confidence_inferences,
                    sender.accuracy * 100.0
                ));
            }
            lines.push(String::new());
        }

        lines.push("RECOMMENDATION: Transaction timing correlation is viable in this topology.".to_string());
        lines.push("Consider implementing Dandelion++ or similar origin-hiding protocols.".to_string());
        lines.push(String::new());
    }

    // Propagation Analysis
    if let Some(ref prop) = report.propagation_analysis {
        lines.push("=".repeat(80));
        lines.push("                         PROPAGATION TIMING".to_string());
        lines.push("=".repeat(80));
        lines.push(String::new());

        lines.push("Transaction Propagation:".to_string());
        lines.push(format!(
            "  Average time to reach all nodes: {:.1}ms",
            prop.average_propagation_ms
        ));
        lines.push(format!("  Median: {:.1}ms", prop.median_propagation_ms));
        lines.push(format!("  95th percentile: {:.1}ms", prop.p95_propagation_ms));
        lines.push(String::new());

        lines.push("Block Confirmation Delays:".to_string());
        lines.push(format!(
            "  Average time from TX creation to block inclusion: {:.1} seconds",
            prop.average_confirmation_delay_sec
        ));
        lines.push(String::new());

        if !prop.bottleneck_nodes.is_empty() {
            lines.push("Bottleneck Nodes (consistently slow to receive):".to_string());
            for (i, node) in prop.bottleneck_nodes.iter().take(5).enumerate() {
                lines.push(format!(
                    "  {}. {} (avg delay: {:.0}ms) - {} observations",
                    i + 1,
                    node.node_id,
                    node.average_delay_ms,
                    node.observations
                ));
            }
            lines.push(String::new());
        }
    }

    // Network Resilience
    if let Some(ref res) = report.resilience_analysis {
        lines.push("=".repeat(80));
        lines.push("                        NETWORK RESILIENCE".to_string());
        lines.push("=".repeat(80));
        lines.push(String::new());

        lines.push("Connectivity:".to_string());
        lines.push(format!(
            "  Total nodes: {}",
            res.connectivity.total_nodes
        ));
        lines.push(format!(
            "  Average peer count: {:.1}",
            res.connectivity.average_peer_count
        ));
        lines.push(format!(
            "  Min: {}, Max: {}",
            res.connectivity.min_peer_count, res.connectivity.max_peer_count
        ));
        if !res.connectivity.isolated_nodes.is_empty() {
            lines.push(format!(
                "  Isolated nodes: {}",
                res.connectivity.isolated_nodes.join(", ")
            ));
        }
        lines.push(String::new());

        lines.push("Centralization Metrics:".to_string());
        lines.push(format!(
            "  First-seen Gini coefficient: {:.2} (0=equal, 1=centralized)",
            res.centralization.first_seen_gini
        ));
        if !res.centralization.dominant_observers.is_empty() {
            lines.push(format!(
                "  Dominant observers (>15% of first-sees): {}",
                res.centralization.dominant_observers.join(", ")
            ));
        }
        lines.push(format!(
            "  Miner first-seen ratio: {:.1}%",
            res.centralization.miner_first_seen_ratio * 100.0
        ));
        lines.push(String::new());

        lines.push("Partition Risk:".to_string());
        lines.push(format!(
            "  Connected components: {}",
            res.partition_risk.connected_components
        ));
        if !res.partition_risk.bridge_nodes.is_empty() {
            lines.push(format!(
                "  Bridge nodes (removal may partition): {}",
                res.partition_risk.bridge_nodes.join(", ")
            ));
        }
        lines.push(String::new());

        let gini = res.centralization.first_seen_gini;
        if gini > 0.4 {
            lines.push("RECOMMENDATION: Network shows significant centralization.".to_string());
            lines.push("This creates potential surveillance points.".to_string());
        } else if gini > 0.2 {
            lines.push("RECOMMENDATION: Network has moderate centralization around some nodes.".to_string());
        } else {
            lines.push("RECOMMENDATION: Network appears well-distributed.".to_string());
        }
        lines.push(String::new());
    }

    // Footer
    lines.push("=".repeat(80));

    let content = lines.join("\n");
    fs::write(output_path, content)
        .with_context(|| format!("Failed to write text report to {}", output_path.display()))?;

    log::info!("Text report written to {}", output_path.display());
    Ok(())
}

/// Print a summary to stdout
pub fn print_summary(report: &FullAnalysisReport) {
    println!("\n=== TRANSACTION ROUTING ANALYSIS SUMMARY ===\n");
    println!("Nodes: {}", report.metadata.total_nodes);
    println!("Transactions: {}", report.metadata.total_transactions);
    println!("Blocks: {}", report.metadata.total_blocks);

    if let Some(ref spy) = report.spy_node_analysis {
        println!("\nSpy Node Vulnerability:");
        println!("  Inference accuracy: {:.1}%", spy.inference_accuracy * 100.0);
        println!(
            "  High vulnerability TXs: {}",
            spy.timing_spread_distribution.high_vulnerability_count
        );
    }

    if let Some(ref prop) = report.propagation_analysis {
        println!("\nPropagation Timing:");
        println!("  Average: {:.1}ms", prop.average_propagation_ms);
        println!("  Median: {:.1}ms", prop.median_propagation_ms);
        println!("  P95: {:.1}ms", prop.p95_propagation_ms);
    }

    if let Some(ref res) = report.resilience_analysis {
        println!("\nNetwork Resilience:");
        println!("  Avg peers: {:.1}", res.connectivity.average_peer_count);
        println!("  Gini coefficient: {:.2}", res.centralization.first_seen_gini);
        println!("  Components: {}", res.partition_risk.connected_components);
    }

    println!();
}
