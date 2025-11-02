//! Shadow-specific type definitions.
//!
//! This module contains type definitions for Shadow network simulator
//! configurations, including host definitions, process configurations,
//! network topology structures, and agent/miner registry types.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

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
#[derive(Serialize, Debug)]
pub struct AgentInfo {
    /// Unique identifier for the agent
    pub id: String,
    /// IP address assigned to the agent
    pub ip_addr: String,
    /// Whether this agent runs a Monero daemon
    pub daemon: bool,
    /// Whether this agent has a wallet
    pub wallet: bool,
    /// Python script module path for agent behavior (if applicable)
    pub user_script: Option<String>,
    /// Custom attributes for agent configuration
    pub attributes: HashMap<String, String>,
    /// RPC port for wallet service
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_rpc_port: Option<u16>,
    /// RPC port for daemon service
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_rpc_port: Option<u16>,
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
    pub hosts: HashMap<String, ShadowHost>,
}

/// General Shadow simulation settings.
#[derive(Serialize, Debug)]
pub struct ShadowGeneral {
    /// Simulation stop time in seconds
    pub stop_time: u64,
    /// Whether to model unblocked syscall latency
    pub model_unblocked_syscall_latency: bool,
    /// Log level for Shadow (trace, debug, info, warn, error)
    pub log_level: String,
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
    pub environment: HashMap<String, String>,
    /// Start time for the process (e.g., "0s", "10s", "1m")
    pub start_time: String,
}