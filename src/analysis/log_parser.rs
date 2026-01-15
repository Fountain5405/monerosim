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
    }

    Ok(data)
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
            // Find the monerod log file (bash.1000.stdout is typically the daemon)
            let log_path = hosts_dir.join(&agent.id).join("bash.1000.stdout");

            if !log_path.exists() {
                log::debug!("No log file found for {}", agent.id);
                return None;
            }

            match parse_log_file(&log_path, &agent.id) {
                Ok(data) => {
                    log::debug!(
                        "Parsed {}: {} TX observations, {} connection events",
                        agent.id,
                        data.tx_observations.len(),
                        data.connection_events.len()
                    );
                    Some((agent.id.clone(), data))
                }
                Err(e) => {
                    log::warn!("Failed to parse {}: {}", log_path.display(), e);
                    None
                }
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
        // 2000-01-01 00:00:00 UTC = 946684800
        // 04:00:05.464 = 4*3600 + 5 + 0.464 = 14405.464
        let expected = 946684800.0 + 14405.464;
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
