//! Bandwidth analysis for MoneroSim simulations.
//!
//! Provides functions to analyze network bandwidth usage from parsed log data,
//! including per-node statistics, category breakdowns, and time series.

use std::collections::HashMap;

use super::types::*;

/// Map command IDs to human-readable names
pub fn command_name(category: &str) -> &'static str {
    match category {
        "command-1001" => "Handshake",
        "command-1002" => "Block Query",
        "command-1003" => "Ping",
        "command-2002" => "Chain Sync Request",
        "command-2003" => "Block Request",
        "command-2004" => "Block Response",
        "command-2006" => "Chain Info Request",
        "command-2007" => "Chain Response",
        "command-2008" => "TX Broadcast",
        "command-2010" => "Keepalive",
        _ => "Unknown",
    }
}

/// Calculate per-node bandwidth statistics
fn calculate_node_stats(node_id: &str, events: &[BandwidthEvent], top_peers_count: usize) -> NodeBandwidthStats {
    let mut total_bytes_sent: u64 = 0;
    let mut total_bytes_received: u64 = 0;
    let mut message_count_sent: u64 = 0;
    let mut message_count_received: u64 = 0;
    let mut by_category: HashMap<String, CategoryBandwidth> = HashMap::new();
    let mut by_peer: HashMap<String, PeerBandwidth> = HashMap::new();

    for event in events {
        if event.is_sent {
            total_bytes_sent += event.bytes;
            message_count_sent += 1;
        } else {
            total_bytes_received += event.bytes;
            message_count_received += 1;
        }

        // Aggregate by category
        let cat = by_category.entry(event.command_category.clone()).or_insert_with(|| {
            CategoryBandwidth {
                category: event.command_category.clone(),
                category_name: command_name(&event.command_category).to_string(),
                bytes_sent: 0,
                bytes_received: 0,
                message_count: 0,
            }
        });
        if event.is_sent {
            cat.bytes_sent += event.bytes;
        } else {
            cat.bytes_received += event.bytes;
        }
        cat.message_count += 1;

        // Aggregate by peer
        let peer = by_peer.entry(event.peer_ip.clone()).or_insert_with(|| {
            PeerBandwidth {
                peer_ip: event.peer_ip.clone(),
                bytes_sent: 0,
                bytes_received: 0,
                message_count: 0,
            }
        });
        if event.is_sent {
            peer.bytes_sent += event.bytes;
        } else {
            peer.bytes_received += event.bytes;
        }
        peer.message_count += 1;
    }

    // Get top peers by total bytes
    let mut peers: Vec<PeerBandwidth> = by_peer.into_values().collect();
    peers.sort_by(|a, b| {
        let a_total = a.bytes_sent + a.bytes_received;
        let b_total = b.bytes_sent + b.bytes_received;
        b_total.cmp(&a_total)
    });
    peers.truncate(top_peers_count);

    NodeBandwidthStats {
        node_id: node_id.to_string(),
        total_bytes_sent,
        total_bytes_received,
        total_bytes: total_bytes_sent + total_bytes_received,
        bytes_by_category: by_category,
        top_peers: peers,
        message_count_sent,
        message_count_received,
    }
}

/// Analyze bandwidth usage from parsed log data
pub fn analyze_bandwidth(
    log_data: &HashMap<String, NodeLogData>,
    top_peers_per_node: usize,
) -> BandwidthReport {
    let mut per_node_stats: Vec<NodeBandwidthStats> = Vec::new();
    let mut network_by_category: HashMap<String, CategoryBandwidth> = HashMap::new();

    // Calculate per-node stats
    for (node_id, node_data) in log_data {
        if node_data.bandwidth_events.is_empty() {
            continue;
        }

        let stats = calculate_node_stats(node_id, &node_data.bandwidth_events, top_peers_per_node);

        // Aggregate categories into network-wide totals
        for (cat_id, cat_stats) in &stats.bytes_by_category {
            let net_cat = network_by_category.entry(cat_id.clone()).or_insert_with(|| {
                CategoryBandwidth {
                    category: cat_id.clone(),
                    category_name: command_name(cat_id).to_string(),
                    bytes_sent: 0,
                    bytes_received: 0,
                    message_count: 0,
                }
            });
            net_cat.bytes_sent += cat_stats.bytes_sent;
            net_cat.bytes_received += cat_stats.bytes_received;
            net_cat.message_count += cat_stats.message_count;
        }

        per_node_stats.push(stats);
    }

    // Sort by total bytes descending
    per_node_stats.sort_by(|a, b| b.total_bytes.cmp(&a.total_bytes));

    // Calculate network totals
    let total_bytes_sent: u64 = per_node_stats.iter().map(|s| s.total_bytes_sent).sum();
    let total_bytes_received: u64 = per_node_stats.iter().map(|s| s.total_bytes_received).sum();
    let total_bytes = total_bytes_sent + total_bytes_received;
    let total_messages: u64 = per_node_stats.iter()
        .map(|s| s.message_count_sent + s.message_count_received)
        .sum();

    // Calculate per-node statistics
    let node_count = per_node_stats.len();
    let avg_bytes_per_node = if node_count > 0 {
        total_bytes as f64 / node_count as f64
    } else {
        0.0
    };

    // Calculate median
    let median_bytes_per_node = if node_count > 0 {
        let mut bytes: Vec<u64> = per_node_stats.iter().map(|s| s.total_bytes).collect();
        bytes.sort();
        if node_count % 2 == 0 {
            (bytes[node_count / 2 - 1] + bytes[node_count / 2]) as f64 / 2.0
        } else {
            bytes[node_count / 2] as f64
        }
    } else {
        0.0
    };

    // Find max/min nodes
    let max_bytes_node = per_node_stats.first()
        .map(|s| (s.node_id.clone(), s.total_bytes))
        .unwrap_or_else(|| ("".to_string(), 0));

    let min_bytes_node = per_node_stats.last()
        .map(|s| (s.node_id.clone(), s.total_bytes))
        .unwrap_or_else(|| ("".to_string(), 0));

    BandwidthReport {
        total_bytes,
        total_bytes_sent,
        total_bytes_received,
        total_messages,
        avg_bytes_per_node,
        median_bytes_per_node,
        max_bytes_node,
        min_bytes_node,
        bytes_by_category: network_by_category,
        per_node_stats,
        bandwidth_over_time: Vec::new(), // Populated by bandwidth_time_series if needed
    }
}

/// Calculate bandwidth over time windows
pub fn bandwidth_time_series(
    log_data: &HashMap<String, NodeLogData>,
    window_size_sec: f64,
) -> Vec<BandwidthWindow> {
    // Collect all bandwidth events with timestamps
    let mut all_events: Vec<&BandwidthEvent> = Vec::new();
    for node_data in log_data.values() {
        for event in &node_data.bandwidth_events {
            all_events.push(event);
        }
    }

    if all_events.is_empty() {
        return Vec::new();
    }

    // Find time range
    let min_time = all_events.iter().map(|e| e.timestamp).fold(f64::MAX, f64::min);
    let max_time = all_events.iter().map(|e| e.timestamp).fold(f64::MIN, f64::max);

    if min_time >= max_time {
        return Vec::new();
    }

    // Create windows
    let mut windows: Vec<BandwidthWindow> = Vec::new();
    let mut current = min_time;

    while current < max_time {
        let window_end = (current + window_size_sec).min(max_time);
        windows.push(BandwidthWindow {
            start: current,
            end: window_end,
            bytes_sent: 0,
            bytes_received: 0,
            message_count: 0,
        });
        current = window_end;
    }

    // Aggregate events into windows
    for event in all_events {
        // Find which window this event belongs to
        let window_idx = ((event.timestamp - min_time) / window_size_sec) as usize;
        if window_idx < windows.len() {
            let window = &mut windows[window_idx];
            if event.is_sent {
                window.bytes_sent += event.bytes;
            } else {
                window.bytes_received += event.bytes;
            }
            window.message_count += 1;
        }
    }

    windows
}

/// Format bytes as human-readable string
pub fn format_bytes(bytes: u64) -> String {
    if bytes >= 1_000_000_000 {
        format!("{:.2} GB", bytes as f64 / 1_000_000_000.0)
    } else if bytes >= 1_000_000 {
        format!("{:.2} MB", bytes as f64 / 1_000_000.0)
    } else if bytes >= 1_000 {
        format!("{:.2} KB", bytes as f64 / 1_000.0)
    } else {
        format!("{} B", bytes)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_command_name() {
        assert_eq!(command_name("command-1001"), "Handshake");
        assert_eq!(command_name("command-2008"), "TX Broadcast");
        assert_eq!(command_name("command-9999"), "Unknown");
    }

    #[test]
    fn test_format_bytes() {
        assert_eq!(format_bytes(500), "500 B");
        assert_eq!(format_bytes(1500), "1.50 KB");
        assert_eq!(format_bytes(1_500_000), "1.50 MB");
        assert_eq!(format_bytes(1_500_000_000), "1.50 GB");
    }

    #[test]
    fn test_calculate_node_stats() {
        let events = vec![
            BandwidthEvent {
                timestamp: 100.0,
                peer_ip: "1.0.0.1".to_string(),
                peer_port: 18080,
                direction: ConnectionDirection::Outbound,
                bytes: 1000,
                is_sent: true,
                command_category: "command-1001".to_string(),
                initiated_by_us: true,
            },
            BandwidthEvent {
                timestamp: 101.0,
                peer_ip: "1.0.0.1".to_string(),
                peer_port: 18080,
                direction: ConnectionDirection::Outbound,
                bytes: 500,
                is_sent: false,
                command_category: "command-1001".to_string(),
                initiated_by_us: false,
            },
        ];

        let stats = calculate_node_stats("test-node", &events, 10);
        assert_eq!(stats.total_bytes_sent, 1000);
        assert_eq!(stats.total_bytes_received, 500);
        assert_eq!(stats.total_bytes, 1500);
        assert_eq!(stats.message_count_sent, 1);
        assert_eq!(stats.message_count_received, 1);
    }
}
