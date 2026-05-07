//! Top-level configuration data types: `Config`, `GeneralConfig`, `Network`,
//! and the small enums/structs they compose (peer modes, topology shapes,
//! distribution strategies, daemon configs, agent definitions, etc.).

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

use super::agent_config::{AgentConfig, OptionValue};
use super::defaults::{
    default_daemon_data_dir, default_difficulty_cache_ttl, default_model_unblocked_syscall_latency,
    default_parallelism, default_shadow_log_level, default_shared_dir, default_simulation_seed,
};
use super::errors::ValidationError;

/// Peer mode options for network configuration
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub enum PeerMode {
    Dynamic,
    Hardcoded,
    Hybrid,
}

/// How to populate the in-sim hosts at Monero's hardcoded fallback seed IPs
/// (the IPs baked into monerod at src/p2p/net_node.inl).
///
/// - `Auto`: monerosim auto-injects 6 daemon-only hosts named
///   `monero-seed-001..006`, each pinned to one fallback IP.
/// - `Custom`: user declares agents named `monero-seed-NNN` in the YAML;
///   monerosim pins their IPs to the fallback list in declaration order.
/// - `Off`: no fallback seeds; miners alone serve the seed-node role
///   (current legacy behavior). Some monerod fallback warnings may appear.
///
/// Distinct from `network.seed_nodes` (a list of IP:port strings used by
/// Hardcoded/Hybrid peer-discovery modes). This field controls Monero's
/// hardcoded *fallback* IPs; that field configures explicit peer seeds.
#[derive(Debug, Serialize, Deserialize, Clone, Copy, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum FallbackSeedsMode {
    Auto,
    Custom,
    Off,
}

impl Default for FallbackSeedsMode {
    fn default() -> Self {
        FallbackSeedsMode::Auto
    }
}

/// Topology templates for peer connections
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub enum Topology {
    Star,
    Mesh,
    Ring,
    Dag,
}

/// Strategy for distributing agents across network topology nodes.
///
/// The GML topology represents a synthetic Internet with nodes numbered 0 to N-1.
/// These are remapped from real AS numbers (which can range from small values to 400,000+)
/// to contiguous IDs because Shadow requires sequential node IDs and real AS numbers
/// have large gaps. The region mapping divides these synthetic AS numbers proportionally
/// across 6 geographic regions.
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Default)]
pub enum DistributionStrategy {
    /// Distribute agents proportionally across all 6 geographic regions (default).
    /// Agents are spread across North America, Europe, Asia, South America, Africa,
    /// and Oceania based on their proportion of the total topology.
    #[default]
    Global,
    /// Sequential assignment to nodes 0, 1, 2, ... (legacy behavior).
    /// All agents end up in the first region (typically North America).
    Sequential,
    /// Custom weights per region. Use with `weights` field to specify
    /// how many agents should go to each region.
    Weighted,
}

/// Region weight configuration for weighted distribution strategy.
/// Values are relative weights (not percentages). If not specified,
/// regions use their default proportions from the topology.
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Default)]
pub struct RegionWeights {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub north_america: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub europe: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub asia: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub south_america: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub africa: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub oceania: Option<u32>,
}

/// Distribution configuration for GML network topologies.
///
/// Controls how simulation agents are placed across the network topology nodes.
/// By default, agents are distributed globally across all geographic regions
/// to simulate a realistic Internet deployment.
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub struct Distribution {
    /// The distribution strategy to use
    #[serde(default)]
    pub strategy: DistributionStrategy,
    /// Custom region weights (only used with Weighted strategy)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub weights: Option<RegionWeights>,
}

impl Default for Distribution {
    fn default() -> Self {
        Self {
            strategy: DistributionStrategy::Global,
            weights: None,
        }
    }
}

/// Unified configuration that supports only agent mode
#[derive(Debug, Serialize, Deserialize)]
pub struct Config {
    pub general: GeneralConfig,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub network: Option<Network>,
    pub agents: AgentDefinitions,
    /// Optional performance-tuning knobs that don't fit neatly into
    /// `general:`. Existing perf fields (runahead, parallelism, process_threads,
    /// shadow_log_level) stay in `general:` for backward compat — this
    /// stanza is for additions, currently just one Shadow-level toggle.
    #[serde(default)]
    pub performance: PerformanceConfig,
}

/// Shadow / sim-engine performance knobs. All fields default to the
/// safer / more accurate setting; flip them to trade accuracy for
/// wall-time speedup when you've decided you don't need the precision.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PerformanceConfig {
    /// When true (default), Shadow charges simulated time for every
    /// syscall — even ones that don't actually block in the host
    /// kernel. Setting to false skips that cost for non-blocking
    /// syscalls. Faster sim, slightly looser syscall-timing fidelity.
    /// Safe for Monero workloads — they don't hinge on sub-microsecond
    /// syscall accuracy.
    #[serde(default = "default_model_unblocked_syscall_latency")]
    pub model_unblocked_syscall_latency: bool,
}

impl Default for PerformanceConfig {
    fn default() -> Self {
        PerformanceConfig {
            model_unblocked_syscall_latency: default_model_unblocked_syscall_latency(),
        }
    }
}

impl Config {
    /// Validate the configuration
    pub fn validate(&self) -> Result<(), ValidationError> {
        // Validate general settings
        if self.general.stop_time.is_empty() {
            return Err(ValidationError::InvalidGeneral(
                "stop_time cannot be empty".to_string()
            ));
        }

        // Validate network settings
        if let Some(network) = &self.network {
            match network {
                Network::Gml { path, peer_mode, seed_nodes, .. } => {
                    if path.is_empty() {
                        return Err(ValidationError::InvalidNetwork(
                            "GML path cannot be empty".to_string(),
                        ));
                    }
                    Self::validate_peer_config(peer_mode, seed_nodes)?;
                }
                Network::Switch { network_type, peer_mode, seed_nodes, .. } => {
                    if network_type.is_empty() {
                        return Err(ValidationError::InvalidNetwork(
                            "Network type cannot be empty for Switch".to_string(),
                        ));
                    }
                    Self::validate_peer_config(peer_mode, seed_nodes)?;
                }
            }
        }

        Ok(())
    }

    /// Validate peer configuration based on peer mode
    fn validate_peer_config(peer_mode: &Option<PeerMode>, seed_nodes: &Option<Vec<String>>) -> Result<(), ValidationError> {
        if let Some(mode) = peer_mode {
            match mode {
                PeerMode::Hardcoded | PeerMode::Hybrid => {
                    if !seed_nodes.as_ref().is_some_and(|n| !n.is_empty()) {
                        return Err(ValidationError::InvalidNetwork(
                            format!("seed_nodes must be provided and non-empty for peer_mode {:?}", mode)
                        ));
                    }
                }
                PeerMode::Dynamic => {
                    // For Dynamic, seed_nodes can be None or empty
                }
            }
        }

        // If seed_nodes is provided, ensure it's not empty
        if let Some(nodes) = seed_nodes {
            if nodes.is_empty() {
                return Err(ValidationError::InvalidNetwork(
                    "seed_nodes cannot be an empty list".to_string()
                ));
            }
        }

        Ok(())
    }

    /// Get the general configuration
    pub fn general(&self) -> &GeneralConfig {
        &self.general
    }

}

/// Shared general configuration
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GeneralConfig {
    pub stop_time: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fresh_blockchain: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub python_venv: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub log_level: Option<String>,
    #[serde(default = "default_simulation_seed")]
    pub simulation_seed: u64,
    /// Shadow parallelism: number of worker threads
    /// - 0 = auto-detect CPU cores (default, fastest)
    /// - 1 = single-threaded (required for deterministic runs)
    /// - N = use N worker threads
    #[serde(default = "default_parallelism")]
    pub parallelism: u32,
    /// Enable DNS server for monerod peer discovery
    /// When enabled, a DNS server agent is created and monerod uses DNS_PUBLIC to connect to it
    #[serde(skip_serializing_if = "Option::is_none")]
    pub enable_dns_server: Option<bool>,
    /// TTL in seconds for difficulty caching in autonomous miners
    /// Reduces RPC calls by caching difficulty (default: 30 seconds)
    #[serde(default = "default_difficulty_cache_ttl")]
    pub difficulty_cache_ttl: u32,
    /// Shadow log level (trace, debug, info, warn, error)
    /// Lower levels reduce I/O overhead (default: "info")
    #[serde(default = "default_shadow_log_level")]
    pub shadow_log_level: String,
    /// Shadow runahead duration (e.g., "1ms", "10ms")
    /// Experimental: may improve simulation speed at cost of accuracy
    #[serde(skip_serializing_if = "Option::is_none")]
    pub runahead: Option<String>,
    /// Bootstrap end time - Shadow provides high bandwidth/no packet loss until this time
    /// Useful for allowing network to settle before applying realistic constraints
    /// Format: e.g., "7200s" or "2h"
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bootstrap_end_time: Option<String>,
    /// Show simulation progress on stderr (default: true for visibility)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub progress: Option<bool>,
    /// Thread count for monerod and wallet-rpc processes
    /// - None or 0: auto-detect (omits thread flags, lets processes decide)
    /// - 1: single-threaded (default for determinism)
    /// - 2+: use specified thread count
    /// Affects --max-concurrency and --prep-blocks-threads flags
    #[serde(skip_serializing_if = "Option::is_none")]
    pub process_threads: Option<u32>,

    /// Enable Shadow native preemption for CPU-bound threads.
    /// Helps prevent thread starvation but breaks determinism.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub native_preemption: Option<bool>,

    /// Default daemon options applied to all agents (can be overridden per-agent)
    /// Example: { "log-level": 1, "no-zmq": true, "db-sync-mode": "fastest" }
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_defaults: Option<BTreeMap<String, OptionValue>>,

    /// Default wallet options applied to all agents (can be overridden per-agent)
    /// Example: { "log-level": 1 }
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_defaults: Option<BTreeMap<String, OptionValue>>,

    /// Directory for inter-agent communication files (registries, wallets, locks).
    #[serde(default = "default_shared_dir")]
    pub shared_dir: String,

    /// Base directory for per-agent monerod data directories.
    /// Each agent gets `{daemon_data_dir}/monero-{agent_id}`.
    #[serde(default = "default_daemon_data_dir")]
    pub daemon_data_dir: String,

    /// How to populate hosts at Monero's hardcoded fallback seed IPs.
    /// See `FallbackSeedsMode` for semantics.
    ///
    /// Note: this is **distinct from `network.seed_nodes`** (a list of
    /// `ip:port` strings for Hardcoded/Hybrid peer-discovery modes).
    /// This field is a mode enum controlling Monero's hardcoded
    /// *fallback* IPs. Both fields can coexist in one config.
    #[serde(default)]
    pub fallback_seeds: FallbackSeedsMode,
}

/// Agent definitions - named map of agents
/// Each key is the agent ID (e.g., "miner_001", "user_001")
#[derive(Debug, Serialize, Deserialize)]
pub struct AgentDefinitions {
    /// Named agents map - agent_id -> AgentConfig
    #[serde(flatten)]
    pub agents: BTreeMap<String, AgentConfig>,
}

/// Daemon selection strategy for wallet-only agents connecting to remote public nodes
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum DaemonSelectionStrategy {
    /// Randomly select from available public nodes
    Random,
    /// Use the first available public node
    First,
    /// Round-robin through available public nodes
    RoundRobin,
}

impl Default for DaemonSelectionStrategy {
    fn default() -> Self {
        DaemonSelectionStrategy::Random
    }
}

impl DaemonSelectionStrategy {
    /// Convert the strategy to its string representation for CLI arguments
    pub fn as_str(&self) -> &'static str {
        match self {
            DaemonSelectionStrategy::Random => "random",
            DaemonSelectionStrategy::First => "first",
            DaemonSelectionStrategy::RoundRobin => "round_robin",
        }
    }
}

/// Daemon configuration supporting local daemon, remote daemon, or no daemon
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(untagged)]
pub enum DaemonConfig {
    /// Local daemon - runs monerod on the agent (e.g., "monerod")
    Local(String),
    /// Remote daemon - connects to another daemon for wallet-only agents
    Remote {
        /// "auto" for automatic discovery from public nodes, or specific "ip:port"
        address: String,
        /// Selection strategy when address is "auto"
        #[serde(skip_serializing_if = "Option::is_none")]
        strategy: Option<DaemonSelectionStrategy>,
    },
}

impl DaemonConfig {
    /// Check if this is a local daemon configuration
    pub fn is_local(&self) -> bool {
        matches!(self, DaemonConfig::Local(_))
    }

    /// Check if this is a remote daemon configuration
    pub fn is_remote(&self) -> bool {
        matches!(self, DaemonConfig::Remote { .. })
    }

    /// Get the local daemon name if this is a local config
    pub fn local_name(&self) -> Option<&str> {
        match self {
            DaemonConfig::Local(name) => Some(name),
            _ => None,
        }
    }

    /// Get the remote address if this is a remote config
    pub fn remote_address(&self) -> Option<&str> {
        match self {
            DaemonConfig::Remote { address, .. } => Some(address),
            _ => None,
        }
    }

    /// Get the selection strategy if this is a remote config with auto discovery
    pub fn selection_strategy(&self) -> Option<&DaemonSelectionStrategy> {
        match self {
            DaemonConfig::Remote { strategy, .. } => strategy.as_ref(),
            _ => None,
        }
    }
}

/// Network configuration, supporting different topology types
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(untagged)]
pub enum Network {
    Switch {
        #[serde(rename = "type")]
        network_type: String, // e.g., "1_gbit_switch"
        #[serde(skip_serializing_if = "Option::is_none")]
        bandwidth: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        latency: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        peer_mode: Option<PeerMode>,
        #[serde(skip_serializing_if = "Option::is_none")]
        seed_nodes: Option<Vec<String>>,
        #[serde(skip_serializing_if = "Option::is_none")]
        topology: Option<Topology>,
    },
    Gml {
        path: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        peer_mode: Option<PeerMode>,
        #[serde(skip_serializing_if = "Option::is_none")]
        seed_nodes: Option<Vec<String>>,
        #[serde(skip_serializing_if = "Option::is_none")]
        topology: Option<Topology>,
        /// Agent distribution strategy across the GML topology.
        /// Defaults to Global (distribute across all regions).
        #[serde(skip_serializing_if = "Option::is_none")]
        distribution: Option<Distribution>,
    },
}

/// Default implementations
impl Default for GeneralConfig {
    fn default() -> Self {
        Self {
            stop_time: "1h".to_string(),
            fresh_blockchain: Some(true),
            python_venv: None,
            log_level: Some("info".to_string()),
            simulation_seed: default_simulation_seed(),
            parallelism: default_parallelism(),
            enable_dns_server: None,
            difficulty_cache_ttl: default_difficulty_cache_ttl(),
            shadow_log_level: default_shadow_log_level(),
            runahead: None,
            bootstrap_end_time: None,
            progress: Some(true),  // Default to showing progress
            process_threads: Some(1),  // Default to single-threaded for determinism
            native_preemption: None,  // Shadow default (false) applies when unset
            daemon_defaults: None,  // No daemon defaults by default
            wallet_defaults: None,  // No wallet defaults by default
            shared_dir: default_shared_dir(),
            daemon_data_dir: default_daemon_data_dir(),
            fallback_seeds: FallbackSeedsMode::default(),
        }
    }
}

impl Default for Network {
    fn default() -> Self {
        Network::Switch {
            network_type: "1_gbit_switch".to_string(),
            bandwidth: None,
            latency: None,
            peer_mode: Some(PeerMode::Dynamic),
            seed_nodes: None,
            topology: Some(Topology::Dag), // Default to DAG for backward compatibility
        }
    }
}
