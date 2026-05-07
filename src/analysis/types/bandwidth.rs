//! Bandwidth analysis types.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use super::core::{ConnectionDirection, SimTime};

/// Single bandwidth log entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BandwidthEvent {
    /// When the transfer occurred
    pub timestamp: SimTime,
    /// Remote peer IP
    pub peer_ip: String,
    /// Remote peer port
    pub peer_port: u16,
    /// Connection direction (INC or OUT)
    pub direction: ConnectionDirection,
    /// Bytes transferred
    pub bytes: u64,
    /// True if sent, false if received
    pub is_sent: bool,
    /// Command category (e.g., "command-1001")
    pub command_category: String,
    /// Whether we initiated the message
    pub initiated_by_us: bool,
}

/// Bandwidth statistics per command category
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct CategoryBandwidth {
    /// Category ID (e.g., "command-1001")
    pub category: String,
    /// Human-readable name
    pub category_name: String,
    /// Bytes sent in this category
    pub bytes_sent: u64,
    /// Bytes received in this category
    pub bytes_received: u64,
    /// Total message count
    pub message_count: u64,
}

/// Bandwidth statistics per peer
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct PeerBandwidth {
    /// Peer IP address
    pub peer_ip: String,
    /// Bytes sent to this peer
    pub bytes_sent: u64,
    /// Bytes received from this peer
    pub bytes_received: u64,
    /// Total message count with this peer
    pub message_count: u64,
}

/// Per-node bandwidth summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeBandwidthStats {
    /// Node identifier
    pub node_id: String,
    /// Total bytes sent
    pub total_bytes_sent: u64,
    /// Total bytes received
    pub total_bytes_received: u64,
    /// Total bytes (sent + received)
    pub total_bytes: u64,
    /// Breakdown by command category
    pub bytes_by_category: HashMap<String, CategoryBandwidth>,
    /// Breakdown by peer (top peers only)
    pub top_peers: Vec<PeerBandwidth>,
    /// Number of messages sent
    pub message_count_sent: u64,
    /// Number of messages received
    pub message_count_received: u64,
}

/// Bandwidth in a time window
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BandwidthWindow {
    /// Window start time
    pub start: SimTime,
    /// Window end time
    pub end: SimTime,
    /// Bytes sent in this window
    pub bytes_sent: u64,
    /// Bytes received in this window
    pub bytes_received: u64,
    /// Message count in this window
    pub message_count: u64,
}

/// Network-wide bandwidth report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BandwidthReport {
    /// Total bytes transferred across network
    pub total_bytes: u64,
    /// Total bytes sent
    pub total_bytes_sent: u64,
    /// Total bytes received
    pub total_bytes_received: u64,
    /// Total messages
    pub total_messages: u64,
    /// Average bytes per node
    pub avg_bytes_per_node: f64,
    /// Median bytes per node
    pub median_bytes_per_node: f64,
    /// Node with maximum bandwidth (node_id, bytes)
    pub max_bytes_node: (String, u64),
    /// Node with minimum bandwidth (node_id, bytes)
    pub min_bytes_node: (String, u64),
    /// Breakdown by command category
    pub bytes_by_category: HashMap<String, CategoryBandwidth>,
    /// Per-node statistics
    pub per_node_stats: Vec<NodeBandwidthStats>,
    /// Bandwidth over time (if time series requested)
    pub bandwidth_over_time: Vec<BandwidthWindow>,
}
