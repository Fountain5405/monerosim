//! Transaction routing analysis CLI for MoneroSim simulations.
//!
//! Analyzes transaction propagation patterns, spy node vulnerabilities,
//! and network resilience from simulation logs.

use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use clap::{Parser, Subcommand};
use color_eyre::eyre::{Context, Result};

use monerosim::analysis::{
    self,
    types::{AgentInfo, AnalysisMetadata, BlockInfo, FullAnalysisReport, NodeLogData, Transaction},
};

#[derive(Parser)]
#[command(name = "tx-analyzer")]
#[command(about = "Transaction routing analysis for MoneroSim simulations")]
#[command(version)]
struct Cli {
    #[command(subcommand)]
    command: Commands,

    /// Path to shadow.data directory
    #[arg(short, long, default_value = "shadow.data")]
    data_dir: PathBuf,

    /// Path to shared data directory
    #[arg(short, long, default_value = "/tmp/monerosim_shared")]
    shared_dir: PathBuf,

    /// Output directory for reports
    #[arg(short, long, default_value = "analysis_output")]
    output: PathBuf,

    /// Log level (trace, debug, info, warn, error)
    #[arg(long, default_value = "info")]
    log_level: String,

    /// Number of parallel workers (0 = auto-detect)
    #[arg(short = 'j', long, default_value = "0")]
    threads: usize,

    /// Disable parsed log cache (force re-parse from raw logs)
    #[arg(long)]
    no_cache: bool,
}

#[derive(Subcommand)]
enum Commands {
    /// Run full analysis (spy node + propagation + resilience)
    Full {
        /// Skip spy node analysis
        #[arg(long)]
        no_spy: bool,

        /// Skip propagation analysis
        #[arg(long)]
        no_propagation: bool,

        /// Skip resilience analysis
        #[arg(long)]
        no_resilience: bool,
    },

    /// Analyze spy node vulnerability only
    SpyNode {
        /// Minimum confidence threshold for reporting
        #[arg(long, default_value = "0.5")]
        min_confidence: f64,
    },

    /// Analyze propagation timing only
    Propagation {
        /// Include per-transaction details in output
        #[arg(long)]
        detailed: bool,
    },

    /// Analyze network resilience only
    Resilience {
        /// Export network graph for visualization
        #[arg(long)]
        export_graph: bool,
    },

    /// Show summary statistics
    Summary,

    /// Analyze TX relay v2 protocol behavior (PR #9933)
    TxRelayV2 {
        /// Path to second simulation data directory for comparison
        #[arg(long)]
        compare_with: Option<PathBuf>,

        /// Path to second shared data directory for comparison
        #[arg(long)]
        compare_shared: Option<PathBuf>,
    },

    /// Analyze Dandelion++ stem paths and privacy
    Dandelion {
        /// Show full path details for each transaction
        #[arg(long)]
        detailed: bool,

        /// Only show transactions with stem length <= N (privacy concerns)
        #[arg(long)]
        short_stems: Option<usize>,
    },

    /// Analyze network P2P topology and connection patterns
    NetworkGraph {
        /// Export GraphViz DOT file for visualization
        #[arg(long)]
        dot: bool,

        /// Expected max outbound connections (default: 8 for Monero)
        #[arg(long, default_value = "8")]
        expected_outbound: usize,
    },

    /// Analyze upgrade impact by comparing metrics across time windows
    UpgradeAnalysis {
        /// Size of each time window in seconds
        #[arg(long, default_value = "60")]
        window_size: u64,

        /// Path to upgrade manifest JSON (optional)
        #[arg(long)]
        manifest: Option<PathBuf>,

        /// Manual override: end of pre-upgrade period (simulation time in seconds)
        #[arg(long)]
        pre_upgrade_end: Option<f64>,

        /// Manual override: start of post-upgrade period (simulation time in seconds)
        #[arg(long)]
        post_upgrade_start: Option<f64>,
    },

    /// Analyze bandwidth and data usage
    Bandwidth {
        /// Show per-node breakdown
        #[arg(long)]
        per_node: bool,

        /// Show per-category breakdown
        #[arg(long)]
        by_category: bool,

        /// Show bandwidth over time (window size in seconds)
        #[arg(long)]
        time_series: Option<u64>,

        /// Show top N nodes by bandwidth
        #[arg(long, default_value = "10")]
        top: usize,
    },
}

fn main() -> Result<()> {
    color_eyre::install()?;
    let cli = Cli::parse();

    // Initialize logging
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or(&cli.log_level))
        .init();

    // Set thread pool size
    if cli.threads > 0 {
        rayon::ThreadPoolBuilder::new()
            .num_threads(cli.threads)
            .build_global()
            .context("Failed to configure thread pool")?;
    }

    // Load data sources
    log::info!("Loading data from {}...", cli.shared_dir.display());
    let agents = load_agent_registry(&cli.shared_dir)?;
    let transactions = load_transactions(&cli.shared_dir)?;
    let blocks = load_blocks(&cli.shared_dir)?;

    log::info!(
        "Loaded {} agents, {} transactions, {} blocks",
        agents.len(),
        transactions.len(),
        blocks.len()
    );

    // Parse logs (with caching)
    let hosts_dir = cli.data_dir.join("hosts");
    let cache_path = cli.data_dir.join("parsed_logs.bincode");
    let start = std::time::Instant::now();

    let log_data = if !cli.no_cache {
        if let Some(cached) = try_load_cache(&cache_path, &hosts_dir) {
            log::info!("Loaded parsed logs from cache in {:.1}s", start.elapsed().as_secs_f64());
            cached
        } else {
            log::info!("Parsing logs from {}...", hosts_dir.display());
            let data = analysis::parse_all_logs(&hosts_dir, &agents)?;
            log::info!("Parsed logs in {:.1}s", start.elapsed().as_secs_f64());
            if let Err(e) = save_cache(&cache_path, &data) {
                log::warn!("Failed to write cache: {}", e);
            }
            data
        }
    } else {
        log::info!("Parsing logs from {} (cache disabled)...", hosts_dir.display());
        let data = analysis::parse_all_logs(&hosts_dir, &agents)?;
        log::info!("Parsed logs in {:.1}s (cache disabled)", start.elapsed().as_secs_f64());
        data
    };

    // Create output directory
    fs::create_dir_all(&cli.output)
        .with_context(|| format!("Failed to create output directory: {}", cli.output.display()))?;

    // Run requested analysis
    match cli.command {
        Commands::Full {
            no_spy,
            no_propagation,
            no_resilience,
        } => {
            run_full_analysis(
                &cli.output,
                &cli.data_dir,
                &transactions,
                &blocks,
                &log_data,
                &agents,
                !no_spy,
                !no_propagation,
                !no_resilience,
            )?;
        }
        Commands::SpyNode { min_confidence } => {
            let spy_report = analysis::analyze_spy_vulnerability(&transactions, &log_data, &agents);

            // Filter by confidence if requested
            let filtered_report = if min_confidence > 0.0 {
                let mut report = spy_report;
                report.per_tx_analysis.retain(|a| a.correlation_confidence >= min_confidence);
                report
            } else {
                spy_report
            };

            let report = FullAnalysisReport {
                metadata: create_metadata(&cli.data_dir, &agents, &transactions, &blocks),
                spy_node_analysis: Some(filtered_report),
                propagation_analysis: None,
                resilience_analysis: None,
            };

            analysis::generate_json_report(&report, &cli.output.join("spy_node_report.json"))?;
            analysis::generate_text_report(&report, &cli.output.join("spy_node_report.txt"))?;
            analysis::report::print_summary(&report);
        }
        Commands::Propagation { detailed } => {
            let mut prop_report =
                analysis::analyze_propagation(&transactions, &blocks, &log_data, agents.len());

            if !detailed {
                prop_report.per_tx_analysis.clear();
            }

            let report = FullAnalysisReport {
                metadata: create_metadata(&cli.data_dir, &agents, &transactions, &blocks),
                spy_node_analysis: None,
                propagation_analysis: Some(prop_report),
                resilience_analysis: None,
            };

            analysis::generate_json_report(&report, &cli.output.join("propagation_report.json"))?;
            analysis::generate_text_report(&report, &cli.output.join("propagation_report.txt"))?;
            analysis::report::print_summary(&report);
        }
        Commands::Resilience { export_graph } => {
            let resilience_report = analysis::analyze_resilience(&log_data, &agents);

            if export_graph {
                // Export connection graph
                let graph_path = cli.output.join("network_graph.json");
                let graph_data: std::collections::HashMap<String, Vec<String>> = log_data
                    .iter()
                    .map(|(node_id, data)| {
                        let peers: Vec<String> = data
                            .connection_events
                            .iter()
                            .filter(|e| e.is_open)
                            .map(|e| e.peer_ip.clone())
                            .collect();
                        (node_id.clone(), peers)
                    })
                    .collect();

                let json = serde_json::to_string_pretty(&graph_data)?;
                fs::write(&graph_path, json)?;
                log::info!("Network graph exported to {}", graph_path.display());
            }

            let report = FullAnalysisReport {
                metadata: create_metadata(&cli.data_dir, &agents, &transactions, &blocks),
                spy_node_analysis: None,
                propagation_analysis: None,
                resilience_analysis: Some(resilience_report),
            };

            analysis::generate_json_report(&report, &cli.output.join("resilience_report.json"))?;
            analysis::generate_text_report(&report, &cli.output.join("resilience_report.txt"))?;
            analysis::report::print_summary(&report);
        }
        Commands::Summary => {
            // Quick summary without full analysis
            println!("\n=== MONEROSIM DATA SUMMARY ===\n");
            println!("Data directory: {}", cli.data_dir.display());
            println!("Shared directory: {}", cli.shared_dir.display());
            println!();
            println!("Agents: {}", agents.len());
            println!(
                "  Miners: {}",
                agents.iter().filter(|a| a.script_type.contains("miner")).count()
            );
            println!(
                "  Users: {}",
                agents.iter().filter(|a| a.script_type.contains("user")).count()
            );
            println!();
            println!("Transactions: {}", transactions.len());
            println!("Blocks: {}", blocks.len());
            println!();
            println!(
                "Log data parsed: {} nodes",
                log_data.len()
            );
            let total_tx_obs: usize = log_data.values().map(|d| d.tx_observations.len()).sum();
            let total_conn_events: usize = log_data.values().map(|d| d.connection_events.len()).sum();
            let total_v2_announcements: usize = log_data.values().map(|d| d.tx_hash_announcements.len()).sum();
            let total_v2_requests: usize = log_data.values().map(|d| d.tx_requests.len()).sum();
            let total_drops: usize = log_data.values().map(|d| d.connection_drops.len()).sum();
            println!("  TX observations (v1): {}", total_tx_obs);
            println!("  TX hash announcements (v2): {}", total_v2_announcements);
            println!("  TX requests (v2): {}", total_v2_requests);
            println!("  Connection events: {}", total_conn_events);
            println!("  Connection drops: {}", total_drops);
            println!();
        }
        Commands::TxRelayV2 { compare_with, compare_shared } => {
            log::info!("Analyzing TX relay v2 protocol behavior...");

            // Run v2 analysis on primary data
            let v2_report = analysis::analyze_tx_relay_v2(&transactions, &log_data, &agents);

            // Print primary report
            print_v2_report(&v2_report);

            // Save primary report
            let json = serde_json::to_string_pretty(&v2_report)?;
            fs::write(cli.output.join("tx_relay_v2_report.json"), &json)?;
            log::info!("V2 report written to {}", cli.output.join("tx_relay_v2_report.json").display());

            // If comparison requested, load and analyze second dataset
            if let (Some(compare_dir), Some(compare_shared_dir)) = (compare_with, compare_shared) {
                log::info!("Loading comparison data from {}...", compare_shared_dir.display());

                let compare_agents = load_agent_registry(&compare_shared_dir)?;
                let compare_transactions = load_transactions(&compare_shared_dir)?;

                let compare_hosts_dir = compare_dir.join("hosts");
                let compare_log_data = analysis::parse_all_logs(&compare_hosts_dir, &compare_agents)?;

                let compare_report = analysis::analyze_tx_relay_v2(&compare_transactions, &compare_log_data, &compare_agents);

                // Print comparison
                println!("\n");
                let comparison = analysis::tx_relay_v2::compare_runs(&v2_report, &compare_report);
                for line in &comparison {
                    println!("{}", line);
                }

                // Save comparison report
                let compare_json = serde_json::to_string_pretty(&compare_report)?;
                fs::write(cli.output.join("tx_relay_v2_comparison_report.json"), &compare_json)?;

                // Save comparison summary
                let comparison_text = comparison.join("\n");
                fs::write(cli.output.join("tx_relay_comparison.txt"), &comparison_text)?;
                log::info!("Comparison written to {}", cli.output.join("tx_relay_comparison.txt").display());
            }
        }
        Commands::Dandelion { detailed, short_stems } => {
            log::info!("Analyzing Dandelion++ stem paths...");

            let dandelion_report = analysis::analyze_dandelion(&transactions, &log_data, &agents);

            // Print report
            print_dandelion_report(&dandelion_report, detailed, short_stems);

            // Save JSON report
            let json = serde_json::to_string_pretty(&dandelion_report)?;
            fs::write(cli.output.join("dandelion_report.json"), &json)?;
            log::info!("Dandelion report written to {}", cli.output.join("dandelion_report.json").display());
        }
        Commands::NetworkGraph { dot, expected_outbound: _ } => {
            log::info!("Analyzing network P2P topology...");

            let graph_report = analysis::analyze_network_graph(&log_data, &agents, None);

            // Print report
            print_network_graph_report(&graph_report);

            // Save JSON report
            let json = serde_json::to_string_pretty(&graph_report)?;
            fs::write(cli.output.join("network_graph_report.json"), &json)?;
            log::info!("Network graph report written to {}", cli.output.join("network_graph_report.json").display());

            // Export DOT if requested
            if dot {
                let dot_content = analysis::network_graph::generate_dot(&graph_report.final_state, &agents);
                fs::write(cli.output.join("network_graph.dot"), &dot_content)?;
                log::info!("GraphViz DOT file written to {}", cli.output.join("network_graph.dot").display());
                println!("\nTo visualize: dot -Tpng network_graph.dot -o network_graph.png");
            }
        }
        Commands::UpgradeAnalysis {
            window_size,
            manifest,
            pre_upgrade_end,
            post_upgrade_start,
        } => {
            log::info!("Analyzing upgrade impact with {}s time windows...", window_size);

            let config = analysis::upgrade_analysis::UpgradeAnalysisConfig {
                window_size_sec: window_size as f64,
                manifest_path: manifest.map(|p| p.to_string_lossy().to_string()),
                pre_upgrade_end,
                post_upgrade_start,
            };

            let upgrade_report = analysis::analyze_upgrade_impact(
                &transactions,
                &log_data,
                &agents,
                &blocks,
                &config,
                &cli.data_dir.to_string_lossy(),
            )?;

            // Generate text report
            let text_report = format_upgrade_report(&upgrade_report);
            print!("{}", text_report);

            // Save text report
            let txt_path = cli.output.join("upgrade_analysis_report.txt");
            fs::write(&txt_path, &text_report)?;
            log::info!("Upgrade analysis text report written to {}", txt_path.display());

            // Save JSON report
            let json = serde_json::to_string_pretty(&upgrade_report)?;
            fs::write(cli.output.join("upgrade_analysis.json"), &json)?;
            log::info!("Upgrade analysis written to {}", cli.output.join("upgrade_analysis.json").display());
        }

        Commands::Bandwidth {
            per_node,
            by_category,
            time_series,
            top,
        } => {
            log::info!("Analyzing bandwidth usage...");

            // Analyze bandwidth
            let mut report = analysis::analyze_bandwidth(&log_data, 10);

            // Calculate time series if requested
            if let Some(window_size) = time_series {
                report.bandwidth_over_time = analysis::bandwidth_time_series(&log_data, window_size as f64);
            }

            // Print report
            print_bandwidth_report(&report, per_node, by_category, top);

            // Save JSON report
            let json = serde_json::to_string_pretty(&report)?;
            fs::write(cli.output.join("bandwidth_report.json"), &json)?;
            log::info!("Bandwidth report written to {}", cli.output.join("bandwidth_report.json").display());
        }
    }

    Ok(())
}

/// Print TX relay v2 report to stdout
fn print_v2_report(report: &analysis::types::TxRelayV2Report) {
    println!("\n================================================================================");
    println!("                      TX RELAY V2 PROTOCOL ANALYSIS");
    println!("================================================================================\n");

    println!("Protocol Usage:");
    println!("  V1 broadcasts (NOTIFY_NEW_TRANSACTIONS): {}", report.protocol_usage.v1_tx_broadcasts);
    println!("  V2 hash announcements (NOTIFY_TX_POOL_HASH): {}", report.protocol_usage.v2_hash_announcements);
    println!("  V2 requests (NOTIFY_REQUEST_TX_POOL_TXS): {}", report.protocol_usage.v2_tx_requests);
    println!("  V2 usage ratio: {:.1}%", report.protocol_usage.v2_usage_ratio * 100.0);
    println!();

    println!("TX Delivery:");
    println!("  Transactions created: {}", report.delivery_analysis.total_txs_created);
    println!("  Fully propagated: {}", report.delivery_analysis.txs_fully_propagated);
    println!("  Potentially lost: {}", report.delivery_analysis.txs_potentially_lost.len());
    println!("  Average propagation coverage: {:.1}%", report.delivery_analysis.average_propagation_coverage * 100.0);
    if !report.delivery_analysis.txs_potentially_lost.is_empty() {
        println!("  Lost TX hashes:");
        for (i, tx) in report.delivery_analysis.txs_potentially_lost.iter().take(5).enumerate() {
            println!("    {}. {}...", i + 1, &tx[..16.min(tx.len())]);
        }
        if report.delivery_analysis.txs_potentially_lost.len() > 5 {
            println!("    ... and {} more", report.delivery_analysis.txs_potentially_lost.len() - 5);
        }
    }
    println!();

    println!("Connection Stability:");
    println!("  Total drops: {}", report.connection_stability.total_drops);
    println!("    TX verification failures: {}", report.connection_stability.drops_tx_verification);
    println!("    Duplicate TX: {}", report.connection_stability.drops_duplicate_tx);
    println!("    Protocol violations: {}", report.connection_stability.drops_protocol_violation);
    println!("    Other: {}", report.connection_stability.drops_other);
    println!("  Avg connection duration: {:.1}s", report.connection_stability.average_connection_duration_sec);
    println!();

    if report.protocol_usage.v2_tx_requests > 0 {
        println!("V2 Request/Response:");
        println!("  Requests sent: {}", report.request_response.requests_sent);
        println!("  Requests received: {}", report.request_response.requests_received);
        println!("  Fulfillment ratio: {:.1}%", report.request_response.fulfillment_ratio * 100.0);
        println!();
    }

    println!("Assessment:");
    println!("  Health score: {}/100", report.assessment.health_score);
    println!("  V2 active: {}", if report.assessment.v2_active { "YES" } else { "NO" });
    println!("  Lost TXs: {}", if report.assessment.has_lost_txs { "YES" } else { "NO" });
    println!("  Stability issues: {}", if report.assessment.has_stability_issues { "YES" } else { "NO" });
    println!();
    println!("Findings:");
    for finding in &report.assessment.findings {
        println!("  - {}", finding);
    }
    if !report.assessment.recommendations.is_empty() {
        println!();
        println!("Recommendations:");
        for rec in &report.assessment.recommendations {
            println!("  - {}", rec);
        }
    }
    println!();
}

/// Print Dandelion++ analysis report to stdout
fn print_dandelion_report(report: &analysis::types::DandelionReport, detailed: bool, short_stems: Option<usize>) {
    println!("\n================================================================================");
    println!("                    DANDELION++ STEM PATH ANALYSIS");
    println!("================================================================================\n");

    println!("Overview:");
    println!("  Total transactions: {}", report.total_transactions);
    println!("  Paths reconstructed: {}", report.paths_reconstructed);
    println!("  Originator confirmed: {} ({:.1}%)",
        report.originator_confirmed_count,
        if report.paths_reconstructed > 0 {
            (report.originator_confirmed_count as f64 / report.paths_reconstructed as f64) * 100.0
        } else { 0.0 }
    );
    println!();

    println!("Stem Length Statistics:");
    println!("  Average: {:.1} hops", report.avg_stem_length);
    println!("  Min: {} hops", report.min_stem_length);
    println!("  Max: {} hops", report.max_stem_length);
    println!("  Distribution:");
    let mut lengths: Vec<_> = report.stem_length_distribution.iter().collect();
    lengths.sort_by_key(|(k, _)| *k);
    for (len, count) in lengths {
        let pct = (*count as f64 / report.paths_reconstructed.max(1) as f64) * 100.0;
        println!("    {} hops: {} ({:.1}%)", len, count, pct);
    }
    println!();

    println!("Timing:");
    println!("  Avg stem duration: {:.1}ms", report.avg_stem_duration_ms);
    println!("  Avg hop delay: {:.1}ms", report.avg_hop_delay_ms);
    println!();

    if !report.frequent_fluff_nodes.is_empty() {
        println!("Frequent Fluff Points (potential privacy concern):");
        for (node, count) in &report.frequent_fluff_nodes {
            let pct = (*count as f64 / report.paths_reconstructed.max(1) as f64) * 100.0;
            println!("  {}: {} times ({:.1}%)", node, count, pct);
        }
        println!();
    }

    println!("Privacy Assessment:");
    println!("  Score: {}/100", report.privacy_assessment.privacy_score);
    println!("  Effective anonymity: {}", if report.privacy_assessment.effective_anonymity { "YES" } else { "NO" });
    println!("  Trivially deanonymizable: {:.1}%", report.privacy_assessment.trivially_deanonymizable_pct);
    println!();
    println!("Findings:");
    for finding in &report.privacy_assessment.findings {
        println!("  - {}", finding);
    }
    if !report.privacy_assessment.recommendations.is_empty() {
        println!();
        println!("Recommendations:");
        for rec in &report.privacy_assessment.recommendations {
            println!("  - {}", rec);
        }
    }
    println!();

    // Show detailed paths if requested
    if detailed || short_stems.is_some() {
        println!("================================================================================");
        println!("                         TRANSACTION PATHS");
        println!("================================================================================\n");

        let paths_to_show: Vec<_> = if let Some(max_len) = short_stems {
            report.paths.iter().filter(|p| p.stem_length <= max_len).collect()
        } else {
            report.paths.iter().collect()
        };

        if paths_to_show.is_empty() {
            println!("  No paths match the filter criteria.");
        } else {
            for path in paths_to_show.iter().take(50) {
                println!("TX: {}...", &path.tx_hash[..16.min(path.tx_hash.len())]);
                println!("  Originator: {}", path.originator);
                println!("  Stem length: {} hops", path.stem_length);
                println!("  Stem duration: {:.1}ms", path.stem_duration_ms);
                println!("  Fluff node: {}", path.fluff_node.as_deref().unwrap_or("unknown"));
                println!("  Fluff recipients: {}", path.fluff_recipients);
                println!("  Path: {}", analysis::dandelion::format_stem_path(path));
                println!();
            }
            if paths_to_show.len() > 50 {
                println!("  ... and {} more paths (see JSON report for full details)", paths_to_show.len() - 50);
            }
        }
    }
}

/// Print network graph analysis report to stdout
fn print_network_graph_report(report: &analysis::NetworkGraphReport) {
    println!("\n================================================================================");
    println!("                    NETWORK P2P TOPOLOGY ANALYSIS");
    println!("================================================================================\n");

    println!("Overview:");
    println!("  Daemon nodes: {}", report.total_daemon_nodes);
    println!("  Unique connections observed: {}", report.total_unique_connections);
    println!("  Analysis duration: {:.1}s ({:.1}h)",
        report.analysis_duration_sec,
        report.analysis_duration_sec / 3600.0);
    println!();

    println!("Final Network State ({}):", report.final_state.time_label);
    println!("  Active connections: {}", report.final_state.total_connections);
    println!("  Avg outbound: {:.1}", report.final_state.avg_outbound);
    println!("  Avg inbound: {:.1}", report.final_state.avg_inbound);
    if !report.final_state.isolated_nodes.is_empty() {
        println!("  Isolated nodes: {:?}", report.final_state.isolated_nodes);
    }
    println!();

    println!("Degree Distribution (final state):");
    println!("  Outbound: min={}, max={}, mean={:.1}, median={:.1}",
        report.degree_distribution.outbound_stats.min,
        report.degree_distribution.outbound_stats.max,
        report.degree_distribution.outbound_stats.mean,
        report.degree_distribution.outbound_stats.median);
    println!("  Inbound:  min={}, max={}, mean={:.1}, median={:.1}",
        report.degree_distribution.inbound_stats.min,
        report.degree_distribution.inbound_stats.max,
        report.degree_distribution.inbound_stats.mean,
        report.degree_distribution.inbound_stats.median);
    println!();

    println!("Connection Churn:");
    println!("  Total opens: {}", report.churn_stats.total_opens);
    println!("  Total closes: {}", report.churn_stats.total_closes);
    println!("  Avg connection duration: {:.1}s", report.churn_stats.avg_duration_sec);
    println!("  Median duration: {:.1}s", report.churn_stats.median_duration_sec);
    println!("  Long-lived (still active): {}", report.churn_stats.long_lived_connections);
    println!("  Short-lived (<60s): {}", report.churn_stats.short_lived_connections);
    println!();

    println!("Validation (expected max outbound: {}):", report.validation.expected_max_outbound);
    println!("  Actual max outbound: {}", report.validation.actual_max_outbound);
    println!("  Within limits: {}", if report.validation.outbound_valid { "YES" } else { "NO" });
    if !report.validation.nodes_exceeding_outbound.is_empty() {
        println!("  Nodes exceeding limit: {:?}", report.validation.nodes_exceeding_outbound);
    }
    println!();

    println!("Findings:");
    for finding in &report.validation.findings {
        println!("  - {}", finding);
    }
    println!();

    // Show snapshots over time
    if report.snapshots.len() > 1 {
        println!("Network Evolution:");
        for snapshot in &report.snapshots {
            println!("  {}: {} connections, {:.1} out / {:.1} in avg",
                snapshot.time_label,
                snapshot.total_connections,
                snapshot.avg_outbound,
                snapshot.avg_inbound);
        }
        println!();
    }

    // Show per-node details for top nodes
    println!("Per-Node Degrees (sorted by total):");
    let mut node_degrees: Vec<_> = report.final_state.node_degrees.values().collect();
    node_degrees.sort_by(|a, b| b.total.cmp(&a.total));
    for (i, degree) in node_degrees.iter().take(10).enumerate() {
        println!("  {}. {}: {} out, {} in ({} total)",
            i + 1,
            degree.node_id,
            degree.outbound,
            degree.inbound,
            degree.total);
    }
    if node_degrees.len() > 10 {
        println!("  ... and {} more nodes", node_degrees.len() - 10);
    }
    println!();
}

/// Print upgrade analysis report to stdout
fn format_upgrade_report(report: &analysis::types::UpgradeAnalysisReport) -> String {
    use std::fmt::Write;
    let mut out = String::new();

    writeln!(out, "\n================================================================================").unwrap();
    writeln!(out, "                      UPGRADE IMPACT ANALYSIS").unwrap();
    writeln!(out, "================================================================================\n").unwrap();

    // Metadata
    writeln!(out, "Simulation Duration: {:.1}s - {:.1}s ({:.1}s total)",
        report.metadata.simulation_start,
        report.metadata.simulation_end,
        report.metadata.simulation_end - report.metadata.simulation_start).unwrap();
    writeln!(out, "Window Size: {}s ({} windows)",
        report.metadata.window_size_sec as u64,
        report.metadata.total_windows).unwrap();
    writeln!(out).unwrap();

    // Upgrade info
    if let Some(ref upgrade_info) = report.upgrade_info {
        if let (Some(start), Some(end)) = (upgrade_info.upgrade_start, upgrade_info.upgrade_end) {
            writeln!(out, "Upgrade Period: {:.1}s - {:.1}s", start, end).unwrap();
            writeln!(out, "Nodes Upgraded: {}", upgrade_info.node_upgrades.len()).unwrap();
            let mut version_line = String::new();
            if let Some(ref pre) = upgrade_info.pre_upgrade_version {
                write!(version_line, "  {} ", pre).unwrap();
            }
            write!(version_line, "->").unwrap();
            if let Some(ref post) = upgrade_info.post_upgrade_version {
                write!(version_line, " {}", post).unwrap();
            }
            writeln!(out, "{}", version_line).unwrap();
        }
    }

    // Period summaries
    if let (Some(ref pre), Some(ref post)) = (&report.pre_upgrade_summary, &report.post_upgrade_summary) {
        writeln!(out).unwrap();
        writeln!(out, "Pre-Upgrade Period: {:.1}s - {:.1}s ({} windows)",
            pre.start, pre.end, pre.window_count).unwrap();
        writeln!(out, "Post-Upgrade Period: {:.1}s - {:.1}s ({} windows)",
            post.start, post.end, post.window_count).unwrap();
    }
    writeln!(out).unwrap();

    // Metric comparison table
    if !report.changes.is_empty() {
        writeln!(out, "================================================================================").unwrap();
        writeln!(out, "                         METRIC COMPARISON").unwrap();
        writeln!(out, "================================================================================\n").unwrap();

        writeln!(out, "{:<25} | {:>12} | {:>12} | {:>10} | {:>10}",
            "Metric", "Pre-Upgrade", "Post-Upgrade", "Change", "Significant").unwrap();
        writeln!(out, "{:-<25}-+-{:-^12}-+-{:-^12}-+-{:-^10}-+-{:-^10}",
            "", "", "", "", "").unwrap();

        for change in &report.changes {
            let sig_marker = if change.statistically_significant { "YES *" } else { "NO" };

            let (pre_str, post_str, change_str) = if change.metric_name.contains("accuracy")
                || change.metric_name.contains("coverage")
                || change.metric_name.contains("ratio")
                || change.metric_name.starts_with("Spy Acc (") {
                (format!("{:.1}%", change.pre_value * 100.0),
                 format!("{:.1}%", change.post_value * 100.0),
                 format!("{:+.1}%", change.percent_change))
            } else if change.metric_name.contains("propagation") || change.metric_name.contains("ms") {
                (format!("{:.0}ms", change.pre_value),
                 format!("{:.0}ms", change.post_value),
                 format!("{:+.1}%", change.percent_change))
            } else if change.metric_name.contains("gini") || change.metric_name.contains("coefficient") {
                (format!("{:.3}", change.pre_value),
                 format!("{:.3}", change.post_value),
                 format!("{:+.1}%", change.percent_change))
            } else if change.metric_name.contains("Bandwidth") || change.metric_name.contains("bandwidth") {
                (analysis::bandwidth::format_bytes(change.pre_value as u64),
                 analysis::bandwidth::format_bytes(change.post_value as u64),
                 format!("{:+.1}%", change.percent_change))
            } else {
                (format!("{:.1}", change.pre_value),
                 format!("{:.1}", change.post_value),
                 format!("{:+.1}%", change.percent_change))
            };

            writeln!(out, "{:<25} | {:>12} | {:>12} | {:>10} | {:>10}",
                change.metric_name, pre_str, post_str, change_str, sig_marker).unwrap();
        }
        writeln!(out).unwrap();
        writeln!(out, "* Statistically significant at p < 0.05").unwrap();
        writeln!(out).unwrap();
    }

    // Synthetic Spy Node Analysis section
    if let (Some(_), Some(_)) = (&report.pre_upgrade_summary, &report.post_upgrade_summary) {
        let spy_changes: Vec<_> = report.changes.iter()
            .filter(|c| c.metric_name.starts_with("Spy Acc ("))
            .collect();
        if !spy_changes.is_empty() {
            writeln!(out, "================================================================================").unwrap();
            writeln!(out, "                    SYNTHETIC SPY NODE ANALYSIS").unwrap();
            writeln!(out, "================================================================================\n").unwrap();

            writeln!(out, "Methodology: For each visibility level, {} random trials select that fraction",
                report.metadata.spy_trials_per_level).unwrap();
            writeln!(out, "of nodes as \"monitored\". The spy infers the originator of each TX from the").unwrap();
            writeln!(out, "earliest observation at a monitored node (source_ip = inferred sender).\n").unwrap();

            writeln!(out, "{:<12} | {:>17} | {:>18} | {:>9} | {:>11}",
                "Visibility", "Pre-Upgrade Acc", "Post-Upgrade Acc", "Change", "Significant").unwrap();
            writeln!(out, "{:-<12}-+-{:-^17}-+-{:-^18}-+-{:-^9}-+-{:-^11}",
                "", "", "", "", "").unwrap();

            for change in &spy_changes {
                let sig_marker = if change.statistically_significant { "YES *" } else { "NO" };
                // Extract the visibility label from the metric name e.g. "Spy Acc (5% vis)" -> "5%"
                let vis_label = change.metric_name
                    .trim_start_matches("Spy Acc (")
                    .trim_end_matches(" vis)")
                    .to_string();

                writeln!(out, "{:>12} | {:>16.1}% | {:>17.1}% | {:>8.1}% | {:>11}",
                    vis_label,
                    change.pre_value * 100.0,
                    change.post_value * 100.0,
                    change.percent_change,
                    sig_marker).unwrap();
            }
            writeln!(out).unwrap();
        }
    }

    // Stem Length by Fluff Gap Threshold section
    if let (Some(_), Some(_)) = (&report.pre_upgrade_summary, &report.post_upgrade_summary) {
        let stem_changes: Vec<_> = report.changes.iter()
            .filter(|c| c.metric_name.starts_with("Stem Len ("))
            .collect();
        if !stem_changes.is_empty() {
            writeln!(out, "================================================================================").unwrap();
            writeln!(out, "                  STEM LENGTH BY FLUFF GAP THRESHOLD").unwrap();
            writeln!(out, "================================================================================\n").unwrap();

            writeln!(out, "Methodology: A fluff broadcast sends to 3+ peers in a tight time cluster.").unwrap();
            writeln!(out, "The gap threshold controls how tight: smaller thresholds only detect very").unwrap();
            writeln!(out, "fast broadcasts, larger thresholds tolerate more scheduling jitter.\n").unwrap();

            writeln!(out, "{:<16} | {:>13} | {:>14} | {:>9} | {:>11}",
                "Gap Threshold", "Pre-Upgrade", "Post-Upgrade", "Change", "Significant").unwrap();
            writeln!(out, "{:-<16}-+-{:-^13}-+-{:-^14}-+-{:-^9}-+-{:-^11}",
                "", "", "", "", "").unwrap();

            for change in &stem_changes {
                let sig_marker = if change.statistically_significant { "YES *" } else { "NO" };
                // Extract the threshold label from the metric name e.g. "Stem Len (500ms gap)" -> "500ms"
                let threshold_label = change.metric_name
                    .trim_start_matches("Stem Len (")
                    .trim_end_matches(" gap)")
                    .to_string();

                writeln!(out, "{:>16} | {:>13.1} | {:>14.1} | {:>8.1}% | {:>11}",
                    threshold_label,
                    change.pre_value,
                    change.post_value,
                    change.percent_change,
                    sig_marker).unwrap();
            }
            writeln!(out).unwrap();
        }
    }

    // Interpretation
    if !report.changes.is_empty() {
        writeln!(out, "================================================================================").unwrap();
        writeln!(out, "                          INTERPRETATION").unwrap();
        writeln!(out, "================================================================================\n").unwrap();

        let positive: Vec<_> = report.changes.iter()
            .filter(|c| c.statistically_significant && !c.interpretation.is_empty())
            .filter(|c| c.interpretation.to_lowercase().contains("improved")
                || c.interpretation.to_lowercase().contains("increased")
                || c.interpretation.to_lowercase().contains("better"))
            .collect();

        let negative: Vec<_> = report.changes.iter()
            .filter(|c| c.statistically_significant && !c.interpretation.is_empty())
            .filter(|c| c.interpretation.to_lowercase().contains("degraded")
                || c.interpretation.to_lowercase().contains("decreased")
                || c.interpretation.to_lowercase().contains("worse")
                || c.interpretation.to_lowercase().contains("concern"))
            .collect();

        let neutral: Vec<_> = report.changes.iter()
            .filter(|c| !c.statistically_significant ||
                (!positive.iter().any(|p| p.metric_name == c.metric_name) &&
                 !negative.iter().any(|n| n.metric_name == c.metric_name)))
            .collect();

        if !positive.is_empty() {
            writeln!(out, "POSITIVE CHANGES:").unwrap();
            for change in &positive {
                writeln!(out, "  - {}: {}", change.metric_name, change.interpretation).unwrap();
            }
            writeln!(out).unwrap();
        }

        if !negative.is_empty() {
            writeln!(out, "CONCERNS:").unwrap();
            for change in &negative {
                writeln!(out, "  - {}: {}", change.metric_name, change.interpretation).unwrap();
            }
            writeln!(out).unwrap();
        }

        if !neutral.is_empty() && neutral.len() < 10 {
            writeln!(out, "NEUTRAL/NO CHANGE:").unwrap();
            for change in &neutral {
                if !change.interpretation.is_empty() {
                    writeln!(out, "  - {}: {}", change.metric_name, change.interpretation).unwrap();
                } else {
                    writeln!(out, "  - {}: No significant change detected", change.metric_name).unwrap();
                }
            }
            writeln!(out).unwrap();
        }
    }

    // Assessment
    writeln!(out, "================================================================================").unwrap();
    writeln!(out, "                            ASSESSMENT").unwrap();
    writeln!(out, "================================================================================\n").unwrap();

    let verdict_str = match report.assessment.verdict {
        analysis::types::UpgradeVerdict::Positive => "POSITIVE - Upgrade improved network behavior",
        analysis::types::UpgradeVerdict::Negative => "NEGATIVE - Upgrade degraded network behavior",
        analysis::types::UpgradeVerdict::Mixed => "MIXED - Upgrade had mixed effects",
        analysis::types::UpgradeVerdict::Neutral => "NEUTRAL - No significant changes detected",
        analysis::types::UpgradeVerdict::Inconclusive => "INCONCLUSIVE - Insufficient data for assessment",
    };
    writeln!(out, "Verdict: {}", verdict_str).unwrap();
    writeln!(out).unwrap();

    if !report.assessment.findings.is_empty() {
        writeln!(out, "Findings:").unwrap();
        for line in &report.assessment.findings {
            writeln!(out, "  - {}", line).unwrap();
        }
        writeln!(out).unwrap();
    }

    if !report.assessment.concerns.is_empty() {
        writeln!(out, "Concerns:").unwrap();
        for concern in &report.assessment.concerns {
            writeln!(out, "  - {}", concern).unwrap();
        }
        writeln!(out).unwrap();
    }

    if !report.assessment.recommendations.is_empty() {
        writeln!(out, "Recommendations:").unwrap();
        for rec in &report.assessment.recommendations {
            writeln!(out, "  - {}", rec).unwrap();
        }
        writeln!(out).unwrap();
    }

    // Time series summary
    if !report.time_series.is_empty() {
        writeln!(out, "================================================================================").unwrap();
        writeln!(out, "                       TIME SERIES SUMMARY").unwrap();
        writeln!(out, "================================================================================\n").unwrap();

        writeln!(out, "{:<20} | {:>8} | {:>12} | {:>12} | {:>10} | {:>10}",
            "Window", "TXs", "Spy 20%", "Avg Prop", "Stem Len", "Peer Cnt").unwrap();
        writeln!(out, "{:-<20}-+-{:-^8}-+-{:-^12}-+-{:-^12}-+-{:-^10}-+-{:-^10}",
            "", "", "", "", "", "").unwrap();

        for window in &report.time_series {
            let label = window.window.label.as_deref().unwrap_or("");
            let label_display = format!("{:.0}s-{:.0}s {}",
                window.window.start,
                window.window.end,
                if !label.is_empty() { format!("({})", label) } else { String::new() });

            // Show 20% visibility level (index 2) as representative
            let spy_str = window.spy_accuracy_by_visibility
                .as_ref()
                .and_then(|v| v.get(2))
                .map(|v| format!("{:.1}%", v * 100.0))
                .unwrap_or_else(|| "-".to_string());
            let prop_str = window.avg_propagation_ms
                .map(|v| format!("{:.0}ms", v))
                .unwrap_or_else(|| "-".to_string());
            let stem_str = window.avg_stem_length
                .map(|v| format!("{:.1}", v))
                .unwrap_or_else(|| "-".to_string());
            let peer_str = window.avg_peer_count
                .map(|v| format!("{:.1}", v))
                .unwrap_or_else(|| "-".to_string());

            writeln!(out, "{:<20} | {:>8} | {:>12} | {:>12} | {:>10} | {:>10}",
                &label_display[..label_display.len().min(20)],
                window.tx_count,
                spy_str,
                prop_str,
                stem_str,
                peer_str).unwrap();
        }
        writeln!(out).unwrap();
    }

    writeln!(out, "(See upgrade_analysis.json for full time-series data)").unwrap();
    writeln!(out).unwrap();

    out
}

/// Print bandwidth analysis report to stdout
fn print_bandwidth_report(
    report: &analysis::types::BandwidthReport,
    show_per_node: bool,
    show_by_category: bool,
    top_n: usize,
) {
    println!("\n================================================================================");
    println!("                      BANDWIDTH ANALYSIS");
    println!("================================================================================\n");

    // Network totals
    println!("Network Totals:");
    println!("  Total Data:     {} ({} sent, {} received)",
        analysis::format_bytes(report.total_bytes),
        analysis::format_bytes(report.total_bytes_sent),
        analysis::format_bytes(report.total_bytes_received));
    println!("  Total Messages: {}", report.total_messages);
    println!("  Nodes:          {}", report.per_node_stats.len());
    println!();

    // Per-node summary
    println!("Per-Node Statistics:");
    println!("  Average:  {}/node", analysis::format_bytes(report.avg_bytes_per_node as u64));
    println!("  Median:   {}/node", analysis::format_bytes(report.median_bytes_per_node as u64));
    println!("  Max:      {} ({})", analysis::format_bytes(report.max_bytes_node.1), report.max_bytes_node.0);
    println!("  Min:      {} ({})", analysis::format_bytes(report.min_bytes_node.1), report.min_bytes_node.0);
    println!();

    // By category table
    if show_by_category && !report.bytes_by_category.is_empty() {
        println!("Bandwidth by Message Type:");
        println!("{:<20} | {:>12} | {:>12} | {:>12} | {:>10}",
            "Category", "Sent", "Received", "Total", "Messages");
        println!("{:-<20}-+-{:-^12}-+-{:-^12}-+-{:-^12}-+-{:-^10}",
            "", "", "", "", "");

        // Sort categories by total bytes
        let mut categories: Vec<_> = report.bytes_by_category.values().collect();
        categories.sort_by(|a, b| {
            let a_total = a.bytes_sent + a.bytes_received;
            let b_total = b.bytes_sent + b.bytes_received;
            b_total.cmp(&a_total)
        });

        for cat in categories {
            let total = cat.bytes_sent + cat.bytes_received;
            println!("{:<20} | {:>12} | {:>12} | {:>12} | {:>10}",
                cat.category_name,
                analysis::format_bytes(cat.bytes_sent),
                analysis::format_bytes(cat.bytes_received),
                analysis::format_bytes(total),
                cat.message_count);
        }
        println!();
    }

    // Top nodes table
    let nodes_to_show = top_n.min(report.per_node_stats.len());
    if nodes_to_show > 0 {
        println!("Top {} Nodes by Bandwidth:", nodes_to_show);
        println!("{:>4} | {:<15} | {:>12} | {:>12} | {:>12} | {:>10}",
            "Rank", "Node", "Total", "Sent", "Received", "Messages");
        println!("{:-^4}-+-{:-^15}-+-{:-^12}-+-{:-^12}-+-{:-^12}-+-{:-^10}",
            "", "", "", "", "", "");

        for (i, stats) in report.per_node_stats.iter().take(nodes_to_show).enumerate() {
            let total_msgs = stats.message_count_sent + stats.message_count_received;
            println!("{:>4} | {:<15} | {:>12} | {:>12} | {:>12} | {:>10}",
                i + 1,
                &stats.node_id[..stats.node_id.len().min(15)],
                analysis::format_bytes(stats.total_bytes),
                analysis::format_bytes(stats.total_bytes_sent),
                analysis::format_bytes(stats.total_bytes_received),
                total_msgs);
        }
        println!();
    }

    // Per-node detailed breakdown
    if show_per_node && !report.per_node_stats.is_empty() {
        println!("All Nodes:");
        println!("{:<20} | {:>12} | {:>12} | {:>12}",
            "Node", "Total", "Sent", "Received");
        println!("{:-<20}-+-{:-^12}-+-{:-^12}-+-{:-^12}",
            "", "", "", "");

        for stats in &report.per_node_stats {
            println!("{:<20} | {:>12} | {:>12} | {:>12}",
                &stats.node_id[..stats.node_id.len().min(20)],
                analysis::format_bytes(stats.total_bytes),
                analysis::format_bytes(stats.total_bytes_sent),
                analysis::format_bytes(stats.total_bytes_received));
        }
        println!();
    }

    // Time series (if available)
    if !report.bandwidth_over_time.is_empty() {
        println!("Bandwidth Over Time:");
        println!("{:<15} | {:>12} | {:>12} | {:>10}",
            "Time Range", "Sent", "Received", "Messages");
        println!("{:-<15}-+-{:-^12}-+-{:-^12}-+-{:-^10}",
            "", "", "", "");

        for window in &report.bandwidth_over_time {
            let time_range = format!("{:.0}s-{:.0}s", window.start - 946684800.0, window.end - 946684800.0);
            println!("{:<15} | {:>12} | {:>12} | {:>10}",
                time_range,
                analysis::format_bytes(window.bytes_sent),
                analysis::format_bytes(window.bytes_received),
                window.message_count);
        }
        println!();
    }

    println!("(See bandwidth_report.json for full data)");
    println!();
}

fn run_full_analysis(
    output_dir: &PathBuf,
    data_dir: &PathBuf,
    transactions: &[Transaction],
    blocks: &[BlockInfo],
    log_data: &std::collections::HashMap<String, analysis::types::NodeLogData>,
    agents: &[AgentInfo],
    run_spy: bool,
    run_propagation: bool,
    run_resilience: bool,
) -> Result<()> {
    log::info!("Running full analysis...");

    let spy_report = if run_spy {
        log::info!("Analyzing spy node vulnerability...");
        Some(analysis::analyze_spy_vulnerability(transactions, log_data, agents))
    } else {
        None
    };

    let prop_report = if run_propagation {
        log::info!("Analyzing propagation timing...");
        Some(analysis::analyze_propagation(transactions, blocks, log_data, agents.len()))
    } else {
        None
    };

    let resilience_report = if run_resilience {
        log::info!("Analyzing network resilience...");
        Some(analysis::analyze_resilience(log_data, agents))
    } else {
        None
    };

    let report = FullAnalysisReport {
        metadata: create_metadata(data_dir, agents, transactions, blocks),
        spy_node_analysis: spy_report,
        propagation_analysis: prop_report,
        resilience_analysis: resilience_report,
    };

    // Generate reports
    analysis::generate_json_report(&report, &output_dir.join("full_report.json"))?;
    analysis::generate_text_report(&report, &output_dir.join("report.txt"))?;

    // Print summary
    analysis::report::print_summary(&report);

    log::info!("Analysis complete. Reports written to {}", output_dir.display());

    Ok(())
}

fn create_metadata(
    data_dir: &PathBuf,
    agents: &[AgentInfo],
    transactions: &[Transaction],
    blocks: &[BlockInfo],
) -> AnalysisMetadata {
    AnalysisMetadata {
        analysis_timestamp: chrono::Utc::now().to_rfc3339(),
        simulation_data_dir: data_dir.display().to_string(),
        total_nodes: agents.len(),
        total_transactions: transactions.len(),
        total_blocks: blocks.len(),
    }
}

fn load_agent_registry(shared_dir: &PathBuf) -> Result<Vec<AgentInfo>> {
    let path = shared_dir.join("agent_registry.json");
    let content = fs::read_to_string(&path)
        .with_context(|| format!("Failed to read agent registry from {}", path.display()))?;

    // Parse as generic JSON first to detect format
    let json: serde_json::Value =
        serde_json::from_str(&content).context("Failed to parse agent registry JSON")?;

    let mut agents = Vec::new();

    // Handle format with "agents" array
    if let Some(agents_array) = json.get("agents").and_then(|v| v.as_array()) {
        for value in agents_array {
            let id = value
                .get("id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let ip_addr = value
                .get("ip_addr")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let rpc_port = value
                .get("daemon_rpc_port")
                .or_else(|| value.get("rpc_port"))
                .and_then(|v| v.as_u64())
                .unwrap_or(18081) as u16;
            let script_type = value
                .get("user_script")
                .or_else(|| value.get("script_type"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let wallet_address = value
                .get("wallet_address")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string());

            agents.push(AgentInfo {
                id,
                ip_addr,
                rpc_port,
                script_type,
                wallet_address,
            });
        }
    }
    // Handle format as map of agent_id -> agent_info
    else if let Some(obj) = json.as_object() {
        for (id, value) in obj {
            let ip_addr = value
                .get("ip_addr")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let rpc_port = value
                .get("daemon_rpc_port")
                .or_else(|| value.get("rpc_port"))
                .and_then(|v| v.as_u64())
                .unwrap_or(18081) as u16;
            let script_type = value
                .get("user_script")
                .or_else(|| value.get("script_type"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let wallet_address = value
                .get("wallet_address")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string());

            agents.push(AgentInfo {
                id: id.clone(),
                ip_addr,
                rpc_port,
                script_type,
                wallet_address,
            });
        }
    }

    Ok(agents)
}

fn load_transactions(shared_dir: &PathBuf) -> Result<Vec<Transaction>> {
    let path = shared_dir.join("transactions.json");

    if !path.exists() {
        log::warn!("No transactions.json found at {}", path.display());
        return Ok(Vec::new());
    }

    let content = fs::read_to_string(&path)
        .with_context(|| format!("Failed to read transactions from {}", path.display()))?;

    // Parse as array of generic JSON values first to handle malformed entries
    let values: Vec<serde_json::Value> =
        serde_json::from_str(&content).context("Failed to parse transactions JSON")?;

    let mut transactions = Vec::new();
    let mut skipped = 0;

    for value in values {
        // Only accept entries where tx_hash is a string
        if let Some(tx_hash) = value.get("tx_hash").and_then(|v| v.as_str()) {
            let sender_id = value
                .get("sender_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let recipient_id = value
                .get("recipient_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let amount = value.get("amount").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let timestamp = value.get("timestamp").and_then(|v| v.as_f64()).unwrap_or(0.0);

            transactions.push(Transaction {
                tx_hash: tx_hash.to_string(),
                sender_id,
                recipient_id,
                amount,
                timestamp,
            });
        } else {
            skipped += 1;
        }
    }

    if skipped > 0 {
        log::warn!("Skipped {} malformed transaction entries", skipped);
    }

    Ok(transactions)
}

/// Try to load parsed log data from a bincode cache file.
/// Returns None if the cache doesn't exist, is stale, or fails to deserialize.
fn try_load_cache(cache_path: &Path, hosts_dir: &Path) -> Option<HashMap<String, NodeLogData>> {
    let cache_meta = fs::metadata(cache_path).ok()?;
    let cache_mtime = cache_meta.modified().ok()?;

    // Walk hosts_dir to find the newest log file; if any is newer than cache, invalidate
    if let Ok(entries) = fs::read_dir(hosts_dir) {
        for entry in entries.flatten() {
            let host_dir = entry.path();
            if !host_dir.is_dir() {
                continue;
            }
            if let Ok(files) = fs::read_dir(&host_dir) {
                for file in files.flatten() {
                    if let Ok(meta) = file.metadata() {
                        if let Ok(mtime) = meta.modified() {
                            if mtime > cache_mtime {
                                log::info!("Cache stale: {} is newer than cache", file.path().display());
                                return None;
                            }
                        }
                    }
                }
            }
        }
    }

    let file = fs::File::open(cache_path).ok()?;
    let decoder = match zstd::Decoder::new(file) {
        Ok(d) => d,
        Err(e) => {
            log::warn!("Cache decompression failed: {}", e);
            return None;
        }
    };
    let reader = std::io::BufReader::new(decoder);
    match bincode::deserialize_from(reader) {
        Ok(data) => Some(data),
        Err(e) => {
            log::warn!("Cache deserialization failed (schema change?): {}", e);
            None
        }
    }
}

/// Save parsed log data to a zstd-compressed bincode cache file (atomic write via tmp+rename).
/// Uses streaming compression to avoid materializing the full uncompressed buffer in memory.
fn save_cache(cache_path: &Path, data: &HashMap<String, NodeLogData>) -> Result<()> {
    let tmp_path = cache_path.with_extension("bincode.tmp");
    let file = fs::File::create(&tmp_path)
        .with_context(|| format!("Failed to create cache tmp file: {}", tmp_path.display()))?;
    // zstd level 3 is a good balance of speed and compression
    let mut encoder = zstd::Encoder::new(file, 3)
        .context("Failed to create zstd encoder")?;
    bincode::serialize_into(&mut encoder, data)
        .context("Failed to serialize log data to bincode+zstd")?;
    encoder.finish()
        .context("Failed to finish zstd compression")?;
    let compressed_size = fs::metadata(&tmp_path)
        .map(|m| m.len())
        .unwrap_or(0);
    fs::rename(&tmp_path, cache_path)
        .with_context(|| format!("Failed to rename cache file to {}", cache_path.display()))?;
    log::info!("Wrote cache: {} ({:.1} MB)", cache_path.display(), compressed_size as f64 / 1_048_576.0);
    Ok(())
}

fn load_blocks(shared_dir: &PathBuf) -> Result<Vec<BlockInfo>> {
    let path = shared_dir.join("blocks_with_transactions.json");

    if !path.exists() {
        log::warn!("No blocks_with_transactions.json found at {}", path.display());
        return Ok(Vec::new());
    }

    let content = fs::read_to_string(&path)
        .with_context(|| format!("Failed to read blocks from {}", path.display()))?;

    let blocks: Vec<BlockInfo> =
        serde_json::from_str(&content).context("Failed to parse blocks JSON")?;

    Ok(blocks)
}
