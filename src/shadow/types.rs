//! Shadow-specific type definitions.
//!
//! This module contains type definitions for Shadow network simulator
//! configurations, including host definitions, process configurations,
//! network topology structures, and agent/miner registry types.

use serde::Serialize;
use std::collections::BTreeMap;

// ============================================================================
// Registry Types
// ============================================================================

/// Information about a miner agent in the simulation.
///
/// This structure contains details about miners that are used by the block
/// controller to manage mining operations and reward distribution.
#[derive(Serialize, Debug)]
pub struct MinerInfo {
    /// Unique identifier for the miner agent
    pub agent_id: String,
    /// IP address of the miner
    pub ip_addr: String,
    /// Wallet address for receiving mining rewards (populated at runtime)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_address: Option<String>,
    /// Mining weight/hashrate percentage (should sum to 100 across all miners)
    pub weight: u32,
}

/// Registry of all miners in the simulation.
///
/// This is written to `/tmp/monerosim_shared/miners.json` for use by
/// the block controller and mining coordination agents.
#[derive(Serialize, Debug)]
pub struct MinerRegistry {
    /// List of all miner agents
    pub miners: Vec<MinerInfo>,
}

/// Information about any agent (user, miner, or script) in the simulation.
///
/// This structure provides a comprehensive view of each agent's configuration,
/// network location, and capabilities.
///
/// Supports four agent types:
/// - Full agents: daemon=true, wallet=true
/// - Daemon-only: daemon=true, wallet=false
/// - Wallet-only: daemon=false, wallet=true, remote_daemon=Some(...)
/// - Script-only: daemon=false, wallet=false
#[derive(Serialize, Debug)]
pub struct AgentInfo {
    /// Unique identifier for the agent
    pub id: String,
    /// IP address assigned to the agent
    pub ip_addr: String,
    /// Whether this agent runs a local Monero daemon
    pub daemon: bool,
    /// Whether this agent has a wallet
    pub wallet: bool,
    /// Python script module path for agent behavior (if applicable)
    pub user_script: Option<String>,
    /// Custom attributes for agent configuration
    pub attributes: BTreeMap<String, String>,
    /// RPC port for wallet service
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_rpc_port: Option<u16>,
    /// RPC port for daemon service (None for wallet-only and script-only agents)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_rpc_port: Option<u16>,
    /// Whether this agent's daemon is available as a public node
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_public_node: Option<bool>,
    /// Remote daemon address for wallet-only agents (e.g., "auto" or "192.168.1.10:18081")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub remote_daemon: Option<String>,
    /// Daemon selection strategy for wallet-only agents using "auto" (e.g., "random", "first", "round_robin")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_selection_strategy: Option<String>,
}

/// Registry of all agents in the simulation.
///
/// This is written to `/tmp/monerosim_shared/agent_registry.json` for use by
/// all agents to discover each other and coordinate activities.
#[derive(Serialize, Debug)]
pub struct AgentRegistry {
    /// List of all agents in the simulation
    pub agents: Vec<AgentInfo>,
}

/// Information about a public node available for wallet-only agents.
///
/// Public nodes are daemon agents that have `is_public_node: true` attribute
/// and can accept connections from wallet-only agents.
#[derive(Serialize, Debug)]
pub struct PublicNodeInfo {
    /// Agent ID of the public node
    pub agent_id: String,
    /// IP address of the public node
    pub ip_addr: String,
    /// RPC port for daemon connections (typically 18081 for mainnet/regtest)
    pub rpc_port: u16,
    /// P2P port for network connections (typically 18080 for mainnet/regtest)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub p2p_port: Option<u16>,
    /// Status of the node (e.g., "available", "busy", "offline")
    pub status: String,
    /// Timestamp when this node was registered (Unix timestamp)
    pub registered_at: f64,
    /// Custom attributes from the agent configuration
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attributes: Option<BTreeMap<String, String>>,
}

/// Registry of public nodes available for wallet-only agents.
///
/// This is written to `/tmp/monerosim_shared/public_nodes.json` for use by
/// wallet-only agents to discover daemons they can connect to.
#[derive(Serialize, Debug)]
pub struct PublicNodeRegistry {
    /// List of all public nodes
    pub nodes: Vec<PublicNodeInfo>,
    /// Registry format version
    pub version: u32,
}

// ============================================================================
// Shadow Configuration Types
// ============================================================================

/// Main Shadow simulator configuration.
///
/// This is the root structure that gets serialized to YAML and consumed
/// by the Shadow network simulator.
#[derive(Serialize, Debug)]
pub struct ShadowConfig {
    /// General simulation settings
    pub general: ShadowGeneral,
    /// Network topology configuration
    pub network: ShadowNetwork,
    /// Experimental Shadow features
    pub experimental: ShadowExperimental,
    /// Map of hostname to host configuration
    pub hosts: BTreeMap<String, ShadowHost>,
}

/// General Shadow simulation settings.
#[derive(Serialize, Debug)]
pub struct ShadowGeneral {
    /// Simulation stop time in seconds
    pub stop_time: u64,
    /// Random seed for deterministic simulation
    /// Shadow uses this to seed all random number generators
    pub seed: u64,
    /// Number of parallel worker threads (1 = single-threaded for determinism)
    pub parallelism: u32,
    /// Whether to model unblocked syscall latency
    pub model_unblocked_syscall_latency: bool,
    /// Log level for Shadow (trace, debug, info, warn, error)
    pub log_level: String,
    /// Bootstrap end time - during bootstrap period, Shadow enables high bandwidth and no packet loss
    /// This helps networks settle before applying realistic constraints
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bootstrap_end_time: Option<String>,
    /// Show simulation progress on stderr
    pub progress: bool,
}

/// Experimental Shadow features configuration.
#[derive(Serialize, Debug)]
pub struct ShadowExperimental {
    /// Runahead duration (optional, e.g., "1ms")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub runahead: Option<String>,
    /// Whether to use dynamic runahead
    pub use_dynamic_runahead: bool,
}

/// Shadow network configuration.
#[derive(Serialize, Debug)]
pub struct ShadowNetwork {
    /// Network graph/topology definition
    pub graph: ShadowGraph,
}

/// Shadow network graph definition.
///
/// Can represent either a simple switch network or a complex GML-based topology.
#[derive(Serialize, Debug)]
pub struct ShadowGraph {
    /// Type of network graph (e.g., "1_gbit_switch" or "gml")
    #[serde(rename = "type")]
    pub graph_type: String,
    /// Path to GML file (for GML-based topologies)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub file: Option<ShadowFileSource>,
    /// Inline node definitions (for non-GML topologies)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub nodes: Option<Vec<ShadowNetworkNode>>,
    /// Inline edge definitions (for non-GML topologies)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub edges: Option<Vec<ShadowNetworkEdge>>,
}

/// Reference to an external GML topology file.
#[derive(Serialize, Debug)]
pub struct ShadowFileSource {
    /// Path to the GML file
    pub path: String,
}

/// Network node definition for inline topologies.
#[derive(Serialize, Debug)]
pub struct ShadowNetworkNode {
    /// Unique node ID
    pub id: u32,
    /// Download bandwidth (e.g., "1Gbit")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bandwidth_down: Option<String>,
    /// Upload bandwidth (e.g., "1Gbit")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bandwidth_up: Option<String>,
    /// Packet loss rate (e.g., "0.01" for 1%)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub packet_loss: Option<String>,
}

/// Network edge (link) definition for inline topologies.
#[derive(Serialize, Debug)]
pub struct ShadowNetworkEdge {
    /// Source node ID
    pub source: u32,
    /// Target node ID
    pub target: u32,
    /// Link latency (e.g., "10ms")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub latency: Option<String>,
    /// Link bandwidth (e.g., "100Mbit")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bandwidth: Option<String>,
    /// Packet loss rate on this link
    #[serde(skip_serializing_if = "Option::is_none")]
    pub packet_loss: Option<String>,
}

/// Shadow host definition.
///
/// Represents a simulated host in the Shadow network, which can run multiple
/// processes (e.g., monerod, monero-wallet-rpc, agent scripts).
#[derive(Serialize, Debug)]
pub struct ShadowHost {
    /// ID of the network node this host is attached to
    pub network_node_id: u32,
    /// IP address assigned to this host
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ip_addr: Option<String>,
    /// List of processes to run on this host
    pub processes: Vec<ShadowProcess>,
    /// Download bandwidth for this host
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bandwidth_down: Option<String>,
    /// Upload bandwidth for this host
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bandwidth_up: Option<String>,
}

/// Expected final state for a Shadow process.
///
/// Used to tell Shadow what state a process should be in when the simulation
/// ends, to avoid spurious error reports for intentionally-killed processes.
///
/// Shadow expects format like:
/// ```yaml
/// expected_final_state:
///   signaled: SIGTERM
/// ```
#[derive(Debug, Clone)]
pub enum ExpectedFinalState {
    /// Process exited with the given exit code
    Exited(i32),
    /// Process was terminated by the given signal
    Signaled(String),
    /// Process is still running when simulation ends
    Running,
}

impl serde::Serialize for ExpectedFinalState {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeMap;
        match self {
            ExpectedFinalState::Exited(code) => {
                let mut map = serializer.serialize_map(Some(1))?;
                map.serialize_entry("exited", code)?;
                map.end()
            }
            ExpectedFinalState::Signaled(signal) => {
                let mut map = serializer.serialize_map(Some(1))?;
                map.serialize_entry("signaled", signal)?;
                map.end()
            }
            ExpectedFinalState::Running => {
                serializer.serialize_str("running")
            }
        }
    }
}

/// Shadow process definition.
///
/// Represents a single process to be executed within a Shadow host.
#[derive(Serialize, Debug)]
pub struct ShadowProcess {
    /// Path to the executable
    pub path: String,
    /// Command-line arguments
    pub args: String,
    /// Environment variables for the process
    pub environment: BTreeMap<String, String>,
    /// Start time for the process (e.g., "0s", "10s", "1m")
    pub start_time: String,
    /// Shutdown time - when to send shutdown_signal to the process
    #[serde(skip_serializing_if = "Option::is_none")]
    pub shutdown_time: Option<String>,
    /// Expected final state when simulation ends (to avoid spurious errors)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expected_final_state: Option<ExpectedFinalState>,
}