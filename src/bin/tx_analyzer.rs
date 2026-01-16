//! Transaction routing analysis CLI for MoneroSim simulations.
//!
//! Analyzes transaction propagation patterns, spy node vulnerabilities,
//! and network resilience from simulation logs.

use std::fs;
use std::path::PathBuf;

use clap::{Parser, Subcommand};
use color_eyre::eyre::{Context, Result};

use monerosim::analysis::{
    self,
    types::{AgentInfo, AnalysisMetadata, BlockInfo, FullAnalysisReport, Transaction},
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

    // Parse logs in parallel
    let hosts_dir = cli.data_dir.join("hosts");
    log::info!("Parsing logs from {}...", hosts_dir.display());
    let log_data = analysis::parse_all_logs(&hosts_dir, &agents)?;

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
