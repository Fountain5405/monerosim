//! Core/log primitives shared across all analysis pipelines.

use serde::{Deserialize, Serialize};

/// Simulation timestamp in seconds since epoch (946684800 = 2000-01-01 00:00:00 UTC)
pub type SimTime = f64;

/// A transaction as recorded in transactions.json
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    pub tx_hash: String,
    pub sender_id: String,
    pub recipient_id: String,
    pub amount: f64,
    pub timestamp: SimTime,
}

/// Block information from blocks_with_transactions.json
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockInfo {
    pub height: u64,
    pub transactions: Vec<String>,
    pub tx_count: usize,
}

/// Agent information from agent_registry.json
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnalysisAgentInfo {
    pub id: String,
    pub ip_addr: String,
    pub rpc_port: u16,
    pub script_type: String,
    #[serde(default)]
    pub wallet_address: Option<String>,
}

/// Connection direction from log entries
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConnectionDirection {
    /// INC - peer connected to us
    Inbound,
    /// OUT - we connected to peer
    Outbound,
}

impl std::fmt::Display for ConnectionDirection {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ConnectionDirection::Inbound => write!(f, "INC"),
            ConnectionDirection::Outbound => write!(f, "OUT"),
        }
    }
}

/// A single observation of a transaction at a node
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TxObservation {
    pub tx_hash: String,
    pub node_id: String,
    pub timestamp: SimTime,
    pub source_ip: String,
    pub source_port: u16,
    pub direction: ConnectionDirection,
}

/// Connection event parsed from logs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectionEvent {
    pub timestamp: SimTime,
    pub peer_ip: String,
    pub peer_port: u16,
    pub connection_id: String,
    pub direction: ConnectionDirection,
    pub is_open: bool,
}

/// Block observation parsed from logs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockObservation {
    pub block_hash: String,
    pub height: u64,
    pub node_id: String,
    pub timestamp: SimTime,
    pub source_ip: Option<String>,
    pub is_local: bool,
}

/// TX relay protocol version
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TxRelayProtocol {
    /// V1: Full transaction broadcast via NOTIFY_NEW_TRANSACTIONS
    V1,
    /// V2: Hash announcement + request via NOTIFY_TX_POOL_HASH / NOTIFY_REQUEST_TX_POOL_TXS
    V2,
}

/// TX hash announcement (v2 protocol)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TxHashAnnouncement {
    pub timestamp: SimTime,
    pub node_id: String,
    pub source_ip: String,
    pub direction: ConnectionDirection,
    pub tx_count: usize,
    pub tx_hashes: Vec<String>, // May be empty if not logged individually
}

/// TX request event (v2 protocol)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TxRequest {
    pub timestamp: SimTime,
    pub node_id: String,
    pub target_ip: String,
    pub tx_count: usize,
    pub is_outgoing: bool, // true = we sent request, false = we received request
}

/// Connection drop event with reason
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectionDrop {
    pub timestamp: SimTime,
    pub node_id: String,
    pub peer_ip: String,
    pub reason: String,
}

/// All log data parsed from a single node
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct NodeLogData {
    pub node_id: String,
    pub tx_observations: Vec<TxObservation>,
    pub connection_events: Vec<ConnectionEvent>,
    pub block_observations: Vec<BlockObservation>,
    // TX Relay V2 specific
    pub tx_hash_announcements: Vec<TxHashAnnouncement>,
    pub tx_requests: Vec<TxRequest>,
    pub connection_drops: Vec<ConnectionDrop>,
    // Bandwidth tracking
    pub bandwidth_events: Vec<super::bandwidth::BandwidthEvent>,
}

impl NodeLogData {
    pub fn new(node_id: String) -> Self {
        Self {
            node_id,
            tx_observations: Vec::new(),
            connection_events: Vec::new(),
            block_observations: Vec::new(),
            tx_hash_announcements: Vec::new(),
            tx_requests: Vec::new(),
            connection_drops: Vec::new(),
            bandwidth_events: Vec::new(),
        }
    }
}
