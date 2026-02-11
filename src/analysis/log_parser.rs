//! Log parsing for Monero daemon logs.
//!
//! Parses transaction observations, connection events, and block observations
//! from monerod log files using streaming and parallel processing.

use std::collections::HashMap;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;
use std::sync::LazyLock;

use color_eyre::eyre::{Context, Result};
use rayon::prelude::*;
use regex::Regex;

use super::types::*;

/// Compiled regex patterns for log parsing
pub struct LogPatterns {
    /// Match: "[IP:PORT INC/OUT] Received NOTIFY_NEW_TRANSACTIONS (N txes)"
    pub tx_notification: Regex,
    /// Match: "Including transaction <HASH>"
    pub tx_hash: Regex,
    /// Match: "Transaction added to pool: txid <HASH>"
    pub tx_added_to_pool: Regex,
    /// Match: "[IP:PORT UUID INC/OUT] NEW CONNECTION"
    pub connection_open: Regex,
    /// Match: "[IP:PORT UUID INC/OUT] CLOSE CONNECTION"
    pub connection_close: Regex,
    /// Match: "Received NOTIFY_NEW_FLUFFY_BLOCK <HASH> (height N"
    pub block_received: Regex,
    /// Match: "+++++ BLOCK SUCCESSFULLY ADDED"
    pub block_mined: Regex,
    /// Match: "HEIGHT N, difficulty:"
    pub block_height_line: Regex,
    /// Match timestamp at start of line
    pub timestamp: Regex,
    // TX Relay V2 patterns
    /// Match: "[IP:PORT INC/OUT] Received NOTIFY_TX_POOL_HASH (N txes)"
    pub tx_pool_hash: Regex,
    /// Match: "[IP:PORT INC/OUT] Received NOTIFY_REQUEST_TX_POOL_TXS (N txes)"
    pub tx_pool_request_received: Regex,
    /// Match: "Requesting N transactions via NOTIFY_REQUEST_TX_POOL_TXS"
    pub tx_pool_request_sent: Regex,
    /// Match: "Tx verification failed, dropping connection"
    pub drop_tx_verification: Regex,
    /// Match: "Duplicate transaction in notification, dropping connection"
    pub drop_duplicate_tx: Regex,
    /// Match generic "dropping connection" with context
    pub drop_connection: Regex,
    /// Match: "[IP:PORT DIR] N bytes (sent|received) for category command-XXXX initiated by (us|peer)"
    pub bandwidth: Regex,
}

impl LogPatterns {
    pub fn new() -> Self {
        Self {
            tx_notification: Regex::new(
                r"\[(\d+\.\d+\.\d+\.\d+):(\d+)\s+(INC|OUT)\]\s+Received NOTIFY_NEW_TRANSACTIONS \((\d+) txes\)"
            ).expect("Invalid tx_notification regex"),
            tx_hash: Regex::new(
                r"Including transaction <([a-f0-9]{64})>"
            ).expect("Invalid tx_hash regex"),
            tx_added_to_pool: Regex::new(
                r"Transaction added to pool: txid <([a-f0-9]{64})>"
            ).expect("Invalid tx_added_to_pool regex"),
            connection_open: Regex::new(
                r"\[(\d+\.\d+\.\d+\.\d+):(\d+)\s+([a-f0-9-]+)\s+(INC|OUT)\]\s+NEW CONNECTION"
            ).expect("Invalid connection_open regex"),
            connection_close: Regex::new(
                r"\[(\d+\.\d+\.\d+\.\d+):(\d+)\s+([a-f0-9-]+)\s+(INC|OUT)\]\s+CLOSE CONNECTION"
            ).expect("Invalid connection_close regex"),
            block_received: Regex::new(
                r"\[(\d+\.\d+\.\d+\.\d+):\d+\s+(INC|OUT)\].*Received NOTIFY_NEW_FLUFFY_BLOCK <([a-f0-9]{64})> \(height (\d+)"
            ).expect("Invalid block_received regex"),
            block_mined: Regex::new(
                r"\+\+\+\+\+ BLOCK SUCCESSFULLY ADDED"
            ).expect("Invalid block_mined regex"),
            block_height_line: Regex::new(
                r"HEIGHT (\d+), difficulty:"
            ).expect("Invalid block_height_line regex"),
            timestamp: Regex::new(
                r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)"
            ).expect("Invalid timestamp regex"),
            // TX Relay V2 patterns
            tx_pool_hash: Regex::new(
                r"\[(\d+\.\d+\.\d+\.\d+):(\d+)\s+(INC|OUT)\]\s+Received NOTIFY_TX_POOL_HASH \((\d+) txes\)"
            ).expect("Invalid tx_pool_hash regex"),
            tx_pool_request_received: Regex::new(
                r"\[(\d+\.\d+\.\d+\.\d+):(\d+)\s+(INC|OUT)\]\s+Received NOTIFY_REQUEST_TX_POOL_TXS \((\d+) txes\)"
            ).expect("Invalid tx_pool_request_received regex"),
            tx_pool_request_sent: Regex::new(
                r"Requesting (\d+) transactions via NOTIFY_REQUEST_TX_POOL_TXS"
            ).expect("Invalid tx_pool_request_sent regex"),
            drop_tx_verification: Regex::new(
                r"Tx verification failed, dropping connection"
            ).expect("Invalid drop_tx_verification regex"),
            drop_duplicate_tx: Regex::new(
                r"Duplicate transaction.*dropping connection"
            ).expect("Invalid drop_duplicate_tx regex"),
            drop_connection: Regex::new(
                r"\[(\d+\.\d+\.\d+\.\d+):\d+.*\].*dropping connection"
            ).expect("Invalid drop_connection regex"),
            bandwidth: Regex::new(
                r"\[(\d+\.\d+\.\d+\.\d+):(\d+)\s+(INC|OUT)\]\s+(\d+)\s+bytes\s+(sent|received)\s+for\s+category\s+(command-\d+)\s+initiated\s+by\s+(us|peer)"
            ).expect("Invalid bandwidth regex"),
        }
    }
}

/// Global patterns instance
pub static PATTERNS: LazyLock<LogPatterns> = LazyLock::new(LogPatterns::new);

/// Parse a timestamp string to SimTime (seconds since epoch)
/// Format: "2000-01-01 04:00:05.464"
pub fn parse_timestamp(s: &str) -> Option<SimTime> {
    let caps = PATTERNS.timestamp.captures(s)?;
    let ts_str = caps.get(1)?.as_str();

    // Parse using chrono
    let dt = chrono::NaiveDateTime::parse_from_str(ts_str, "%Y-%m-%d %H:%M:%S%.3f").ok()?;
    Some(dt.and_utc().timestamp() as f64 + dt.and_utc().timestamp_subsec_millis() as f64 / 1000.0)
}

/// Parse connection direction from string
fn parse_direction(s: &str) -> ConnectionDirection {
    match s {
        "INC" => ConnectionDirection::Inbound,
        "OUT" => ConnectionDirection::Outbound,
        _ => ConnectionDirection::Inbound, // Default
    }
}

/// State for multi-line parsing
struct ParseState {
    /// Pending TX notification context (source_ip, source_port, direction, timestamp)
    pending_tx_notification: Option<(String, u16, ConnectionDirection, SimTime)>,
    /// Pending block mined flag
    pending_block_mined: bool,
    /// Last seen timestamp
    last_timestamp: SimTime,
}

impl Default for ParseState {
    fn default() -> Self {
        Self {
            pending_tx_notification: None,
            pending_block_mined: false,
            last_timestamp: 0.0,
        }
    }
}

/// Parse a single log file
pub fn parse_log_file(path: &Path, node_id: &str) -> Result<NodeLogData> {
    let file = File::open(path)
        .with_context(|| format!("Failed to open log file: {}", path.display()))?;
    let reader = BufReader::with_capacity(64 * 1024, file);

    let mut data = NodeLogData::new(node_id.to_string());
    let mut state = ParseState::default();

    for line_result in reader.lines() {
        let line = match line_result {
            Ok(l) => l,
            Err(_) => continue, // Skip malformed lines
        };

        // Try to parse timestamp
        if let Some(ts) = parse_timestamp(&line) {
            state.last_timestamp = ts;
        }

        // Check for TX notification (sets up context for following TX hash lines)
        if let Some(caps) = PATTERNS.tx_notification.captures(&line) {
            let source_ip = caps.get(1).map(|m| m.as_str().to_string()).unwrap_or_default();
            let source_port: u16 = caps.get(2)
                .and_then(|m| m.as_str().parse().ok())
                .unwrap_or(0);
            let direction = parse_direction(caps.get(3).map(|m| m.as_str()).unwrap_or(""));
            let tx_count: u32 = caps.get(4)
                .and_then(|m| m.as_str().parse().ok())
                .unwrap_or(0);

            if tx_count > 0 {
                state.pending_tx_notification = Some((source_ip, source_port, direction, state.last_timestamp));
            }
            continue;
        }

        // Check for TX hash (immediately follows notification)
        if let Some(caps) = PATTERNS.tx_hash.captures(&line) {
            if let Some((ref source_ip, source_port, direction, timestamp)) = state.pending_tx_notification {
                let tx_hash = caps.get(1).map(|m| m.as_str().to_string()).unwrap_or_default();
                data.tx_observations.push(TxObservation {
                    tx_hash,
                    node_id: node_id.to_string(),
                    timestamp,
                    source_ip: source_ip.clone(),
                    source_port,
                    direction,
                });
            }
            // Don't clear pending_tx_notification - there may be multiple TXs in one notification
            continue;
        }

        // If we hit a non-TX-hash line, clear the pending notification
        if state.pending_tx_notification.is_some() && !PATTERNS.tx_hash.is_match(&line) {
            state.pending_tx_notification = None;
        }

        // Check for connection open
        if let Some(caps) = PATTERNS.connection_open.captures(&line) {
            let peer_ip = caps.get(1).map(|m| m.as_str().to_string()).unwrap_or_default();
            let peer_port: u16 = caps.get(2)
                .and_then(|m| m.as_str().parse().ok())
                .unwrap_or(0);
            let connection_id = caps.get(3).map(|m| m.as_str().to_string()).unwrap_or_default();
            let direction = parse_direction(caps.get(4).map(|m| m.as_str()).unwrap_or(""));

            data.connection_events.push(ConnectionEvent {
                timestamp: state.last_timestamp,
                peer_ip,
                peer_port,
                connection_id,
                direction,
                is_open: true,
            });
            continue;
        }

        // Check for connection close
        if let Some(caps) = PATTERNS.connection_close.captures(&line) {
            let peer_ip = caps.get(1).map(|m| m.as_str().to_string()).unwrap_or_default();
            let peer_port: u16 = caps.get(2)
                .and_then(|m| m.as_str().parse().ok())
                .unwrap_or(0);
            let connection_id = caps.get(3).map(|m| m.as_str().to_string()).unwrap_or_default();
            let direction = parse_direction(caps.get(4).map(|m| m.as_str()).unwrap_or(""));

            data.connection_events.push(ConnectionEvent {
                timestamp: state.last_timestamp,
                peer_ip,
                peer_port,
                connection_id,
                direction,
                is_open: false,
            });
            continue;
        }

        // Check for block received
        if let Some(caps) = PATTERNS.block_received.captures(&line) {
            let source_ip = caps.get(1).map(|m| m.as_str().to_string());
            let block_hash = caps.get(3).map(|m| m.as_str().to_string()).unwrap_or_default();
            let height: u64 = caps.get(4)
                .and_then(|m| m.as_str().parse().ok())
                .unwrap_or(0);

            data.block_observations.push(BlockObservation {
                block_hash,
                height,
                node_id: node_id.to_string(),
                timestamp: state.last_timestamp,
                source_ip,
                is_local: false,
            });
            continue;
        }

        // Check for block mined locally
        if PATTERNS.block_mined.is_match(&line) {
            state.pending_block_mined = true;
            continue;
        }

        // Check for block height (follows block mined)
        if state.pending_block_mined {
            if let Some(caps) = PATTERNS.block_height_line.captures(&line) {
                let height: u64 = caps.get(1)
                    .and_then(|m| m.as_str().parse().ok())
                    .unwrap_or(0);

                data.block_observations.push(BlockObservation {
                    block_hash: String::new(), // We don't have the hash from this line
                    height,
                    node_id: node_id.to_string(),
                    timestamp: state.last_timestamp,
                    source_ip: None,
                    is_local: true,
                });
                state.pending_block_mined = false;
            }
        }

        // ================================================================
        // TX Relay V2 Protocol Parsing
        // ================================================================

        // Check for TX pool hash announcement (v2)
        if let Some(caps) = PATTERNS.tx_pool_hash.captures(&line) {
            let source_ip = caps.get(1).map(|m| m.as_str().to_string()).unwrap_or_default();
            let direction = parse_direction(caps.get(3).map(|m| m.as_str()).unwrap_or(""));
            let tx_count: usize = caps.get(4)
                .and_then(|m| m.as_str().parse().ok())
                .unwrap_or(0);

            data.tx_hash_announcements.push(TxHashAnnouncement {
                timestamp: state.last_timestamp,
                node_id: node_id.to_string(),
                source_ip,
                direction,
                tx_count,
                tx_hashes: Vec::new(), // Not logged individually at this level
            });
            continue;
        }

        // Check for TX pool request received (v2)
        if let Some(caps) = PATTERNS.tx_pool_request_received.captures(&line) {
            let source_ip = caps.get(1).map(|m| m.as_str().to_string()).unwrap_or_default();
            let tx_count: usize = caps.get(4)
                .and_then(|m| m.as_str().parse().ok())
                .unwrap_or(0);

            data.tx_requests.push(TxRequest {
                timestamp: state.last_timestamp,
                node_id: node_id.to_string(),
                target_ip: source_ip,
                tx_count,
                is_outgoing: false,
            });
            continue;
        }

        // Check for TX pool request sent (v2)
        if let Some(caps) = PATTERNS.tx_pool_request_sent.captures(&line) {
            let tx_count: usize = caps.get(1)
                .and_then(|m| m.as_str().parse().ok())
                .unwrap_or(0);

            data.tx_requests.push(TxRequest {
                timestamp: state.last_timestamp,
                node_id: node_id.to_string(),
                target_ip: String::new(), // Not captured in this log line
                tx_count,
                is_outgoing: true,
            });
            continue;
        }

        // Check for connection drops with reasons
        if PATTERNS.drop_tx_verification.is_match(&line) {
            if let Some(caps) = PATTERNS.drop_connection.captures(&line) {
                let peer_ip = caps.get(1).map(|m| m.as_str().to_string()).unwrap_or_default();
                data.connection_drops.push(ConnectionDrop {
                    timestamp: state.last_timestamp,
                    node_id: node_id.to_string(),
                    peer_ip,
                    reason: "tx_verification_failed".to_string(),
                });
            }
            continue;
        }

        if PATTERNS.drop_duplicate_tx.is_match(&line) {
            if let Some(caps) = PATTERNS.drop_connection.captures(&line) {
                let peer_ip = caps.get(1).map(|m| m.as_str().to_string()).unwrap_or_default();
                data.connection_drops.push(ConnectionDrop {
                    timestamp: state.last_timestamp,
                    node_id: node_id.to_string(),
                    peer_ip,
                    reason: "duplicate_tx".to_string(),
                });
            }
            continue;
        }

        // Generic dropping connection
        if let Some(caps) = PATTERNS.drop_connection.captures(&line) {
            let peer_ip = caps.get(1).map(|m| m.as_str().to_string()).unwrap_or_default();
            data.connection_drops.push(ConnectionDrop {
                timestamp: state.last_timestamp,
                node_id: node_id.to_string(),
                peer_ip,
                reason: "other".to_string(),
            });
            continue;
        }

        // Check for bandwidth log entry
        if let Some(caps) = PATTERNS.bandwidth.captures(&line) {
            let peer_ip = caps.get(1).map(|m| m.as_str().to_string()).unwrap_or_default();
            let peer_port: u16 = caps.get(2)
                .and_then(|m| m.as_str().parse().ok())
                .unwrap_or(0);
            let direction = parse_direction(caps.get(3).map(|m| m.as_str()).unwrap_or(""));
            let bytes: u64 = caps.get(4)
                .and_then(|m| m.as_str().parse().ok())
                .unwrap_or(0);
            let is_sent = caps.get(5).map(|m| m.as_str() == "sent").unwrap_or(false);
            let command_category = caps.get(6).map(|m| m.as_str().to_string()).unwrap_or_default();
            let initiated_by_us = caps.get(7).map(|m| m.as_str() == "us").unwrap_or(false);

            data.bandwidth_events.push(BandwidthEvent {
                timestamp: state.last_timestamp,
                peer_ip,
                peer_port,
                direction,
                bytes,
                is_sent,
                command_category,
                initiated_by_us,
            });
        }
    }

    Ok(data)
}

/// Find all daemon log files for a node (handles upgrade scenarios with multiple daemon processes)
fn find_daemon_log_files(host_dir: &Path) -> Vec<std::path::PathBuf> {
    let mut daemon_logs = Vec::new();

    // Read directory and find all .stdout files
    if let Ok(entries) = std::fs::read_dir(host_dir) {
        for entry in entries.filter_map(|e| e.ok()) {
            let path = entry.path();
            if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                // Look for bash.*.stdout files
                if name.starts_with("bash.") && name.ends_with(".stdout") {
                    // Check if file is non-empty and contains daemon output
                    if let Ok(metadata) = path.metadata() {
                        if metadata.len() > 1000 {
                            // Quick check: read first few KB to see if it looks like daemon output
                            if let Ok(file) = std::fs::File::open(&path) {
                                let mut reader = std::io::BufReader::new(file);
                                let mut buffer = String::new();
                                use std::io::BufRead;
                                // Read first few lines
                                for _ in 0..20 {
                                    buffer.clear();
                                    if reader.read_line(&mut buffer).unwrap_or(0) == 0 {
                                        break;
                                    }
                                    // Daemon logs have characteristic patterns
                                    if buffer.contains("[P2P]") ||
                                       buffer.contains("[net.p2p]") ||
                                       buffer.contains("Cryptonote protocol") ||
                                       buffer.contains("[INC]") ||
                                       buffer.contains("[OUT]") ||
                                       buffer.contains("NOTIFY_NEW_TRANSACTIONS") ||
                                       buffer.contains("bytes sent for category") ||
                                       buffer.contains("bytes received for category") {
                                        daemon_logs.push(path);
                                        break;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Sort by filename to ensure consistent ordering
    daemon_logs.sort();
    daemon_logs
}

/// Parse all log files in parallel
pub fn parse_all_logs(
    hosts_dir: &Path,
    agents: &[AgentInfo],
) -> Result<HashMap<String, NodeLogData>> {
    log::info!("Parsing logs for {} agents in parallel...", agents.len());

    let results: Vec<(String, NodeLogData)> = agents
        .par_iter()
        .filter_map(|agent| {
            let host_dir = hosts_dir.join(&agent.id);

            // Find all daemon log files (handles upgrade scenarios with v1 and v2 daemons)
            let log_files = find_daemon_log_files(&host_dir);

            if log_files.is_empty() {
                // Fallback to old behavior for backward compatibility
                let log_path = host_dir.join("bash.1000.stdout");
                if !log_path.exists() {
                    log::debug!("No log file found for {}", agent.id);
                    return None;
                }

                match parse_log_file(&log_path, &agent.id) {
                    Ok(data) => Some((agent.id.clone(), data)),
                    Err(e) => {
                        log::warn!("Failed to parse {}: {}", log_path.display(), e);
                        None
                    }
                }
            } else {
                // Parse all daemon log files and merge results
                let mut merged_data = NodeLogData::new(agent.id.clone());

                for log_path in &log_files {
                    match parse_log_file(log_path, &agent.id) {
                        Ok(data) => {
                            merged_data.tx_observations.extend(data.tx_observations);
                            merged_data.tx_hash_announcements.extend(data.tx_hash_announcements);
                            merged_data.tx_requests.extend(data.tx_requests);
                            merged_data.connection_events.extend(data.connection_events);
                            merged_data.block_observations.extend(data.block_observations);
                            merged_data.connection_drops.extend(data.connection_drops);
                            merged_data.bandwidth_events.extend(data.bandwidth_events);
                        }
                        Err(e) => {
                            log::debug!("Failed to parse {}: {}", log_path.display(), e);
                        }
                    }
                }

                // Sort by timestamp after merging
                merged_data.tx_observations.sort_by(|a, b| a.timestamp.partial_cmp(&b.timestamp).unwrap_or(std::cmp::Ordering::Equal));
                merged_data.connection_events.sort_by(|a, b| a.timestamp.partial_cmp(&b.timestamp).unwrap_or(std::cmp::Ordering::Equal));
                merged_data.bandwidth_events.sort_by(|a, b| a.timestamp.partial_cmp(&b.timestamp).unwrap_or(std::cmp::Ordering::Equal));

                log::debug!(
                    "Parsed {} ({} log files): {} TX observations, {} connection events",
                    agent.id,
                    log_files.len(),
                    merged_data.tx_observations.len(),
                    merged_data.connection_events.len()
                );

                Some((agent.id.clone(), merged_data))
            }
        })
        .collect();

    let node_count = results.len();
    let total_tx_obs: usize = results.iter().map(|(_, d)| d.tx_observations.len()).sum();
    log::info!("Parsed {} nodes, {} total TX observations", node_count, total_tx_obs);

    Ok(results.into_iter().collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_timestamp() {
        let ts = parse_timestamp("2000-01-01 04:00:05.464\tI Something");
        assert!(ts.is_some());
        // 2000-01-01 00:00:00 UTC = SHADOW_EPOCH
        // 04:00:05.464 = 4*3600 + 5 + 0.464 = 14405.464
        let expected = crate::SHADOW_EPOCH + 14405.464;
        assert!((ts.unwrap() - expected).abs() < 0.001);
    }

    #[test]
    fn test_tx_notification_regex() {
        let line = "[25.0.0.10:31844 INC] Received NOTIFY_NEW_TRANSACTIONS (1 txes)";
        let caps = PATTERNS.tx_notification.captures(line);
        assert!(caps.is_some());
        let caps = caps.unwrap();
        assert_eq!(caps.get(1).unwrap().as_str(), "25.0.0.10");
        assert_eq!(caps.get(2).unwrap().as_str(), "31844");
        assert_eq!(caps.get(3).unwrap().as_str(), "INC");
        assert_eq!(caps.get(4).unwrap().as_str(), "1");
    }

    #[test]
    fn test_tx_hash_regex() {
        let line = "Including transaction <9effc6a5a5fa0f07e1f5b540ed604804471f4fb7d7e7d7e57f0c0010ed67c8b7>";
        let caps = PATTERNS.tx_hash.captures(line);
        assert!(caps.is_some());
        assert_eq!(
            caps.unwrap().get(1).unwrap().as_str(),
            "9effc6a5a5fa0f07e1f5b540ed604804471f4fb7d7e7d7e57f0c0010ed67c8b7"
        );
    }
}
