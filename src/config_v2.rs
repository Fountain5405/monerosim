use serde::{Deserialize, Deserializer, Serialize};
use std::collections::BTreeMap;
use regex::Regex;
use crate::utils::duration::parse_duration_to_seconds;

/// Peer mode options for network configuration
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub enum PeerMode {
    /// Dynamic peer discovery using network protocols
    Dynamic,
    /// Hardcoded list of peers
    Hardcoded,
    /// Hybrid approach combining dynamic and hardcoded peers
    Hybrid,
}

/// Topology templates for peer connections
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub enum Topology {
    /// Star topology: all nodes connect to a central hub
    Star,
    /// Mesh topology: all nodes connect to all other nodes
    Mesh,
    /// Ring topology: circular connections between nodes
    Ring,
    /// DAG (Directed Acyclic Graph): hierarchical connections
    Dag,
}

/// Flexible option value for daemon/wallet flags
/// Supports bool, string, and number types for YAML flexibility
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(untagged)]
pub enum OptionValue {
    /// Boolean flag (true -> --flag, false -> omit)
    Bool(bool),
    /// String value (--flag=value)
    String(String),
    /// Numeric value (--flag=123)
    Number(i64),
}

/// Unified agent configuration for all agent types
/// Replaces separate UserAgentConfig, MinerDistributorConfig, etc.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentConfig {
    /// Daemon binary (e.g., "monerod") or remote daemon config
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon: Option<DaemonConfig>,

    /// Wallet binary (e.g., "monero-wallet-rpc")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet: Option<String>,

    /// Script to run (e.g., "agents.autonomous_miner", "agents.regular_user")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub script: Option<String>,

    /// Per-agent daemon options (override global defaults)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_options: Option<BTreeMap<String, OptionValue>>,

    /// Per-agent wallet options (override global defaults)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_options: Option<BTreeMap<String, OptionValue>>,

    /// Start time for this agent (e.g., "0s", "30m", "2h")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub start_time: Option<String>,

    // === Miner-specific fields ===
    /// Hashrate for autonomous miners
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hashrate: Option<u32>,

    // === User-specific fields ===
    /// Transaction interval in seconds for regular users
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transaction_interval: Option<u32>,

    /// Time when activity starts (seconds from sim start)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub activity_start_time: Option<u32>,

    /// Whether this agent can receive distributions from miner_distributor
    #[serde(skip_serializing_if = "Option::is_none")]
    pub can_receive_distributions: Option<bool>,

    // === Miner distributor fields ===
    /// Wait time before starting distributions (seconds)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait_time: Option<u32>,

    /// Initial fund amount for distributions
    #[serde(skip_serializing_if = "Option::is_none")]
    pub initial_fund_amount: Option<String>,

    /// Maximum transaction amount
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_transaction_amount: Option<String>,

    /// Minimum transaction amount
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_transaction_amount: Option<String>,

    /// Transaction frequency in seconds
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transaction_frequency: Option<u32>,

    // === Simulation monitor fields ===
    /// Poll interval in seconds
    #[serde(skip_serializing_if = "Option::is_none")]
    pub poll_interval: Option<u32>,

    /// Status file path
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status_file: Option<String>,

    /// Enable alerts
    #[serde(skip_serializing_if = "Option::is_none")]
    pub enable_alerts: Option<bool>,

    /// Enable detailed logging
    #[serde(skip_serializing_if = "Option::is_none")]
    pub detailed_logging: Option<bool>,

    // === Phase support (for upgrade scenarios) ===
    /// Daemon phases for upgrade scenarios
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_phases: Option<BTreeMap<u32, DaemonPhase>>,

    /// Wallet phases for upgrade scenarios
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_phases: Option<BTreeMap<u32, WalletPhase>>,

    // === Legacy support ===
    /// Additional daemon arguments (legacy, prefer daemon_options)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_args: Option<Vec<String>>,

    /// Additional wallet arguments (legacy, prefer wallet_options)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_args: Option<Vec<String>>,

    /// Environment variables for daemon
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_env: Option<BTreeMap<String, String>>,

    /// Environment variables for wallet
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_env: Option<BTreeMap<String, String>>,

    /// Generic attributes (for custom script parameters)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attributes: Option<BTreeMap<String, String>>,
}

impl AgentConfig {
    /// Check if this agent has a local daemon
    pub fn has_local_daemon(&self) -> bool {
        matches!(&self.daemon, Some(DaemonConfig::Local(_))) || self.has_daemon_phases()
    }

    /// Check if this agent has a remote daemon (wallet-only)
    pub fn has_remote_daemon(&self) -> bool {
        matches!(&self.daemon, Some(DaemonConfig::Remote { .. }))
    }

    /// Check if this agent has a wallet
    pub fn has_wallet(&self) -> bool {
        self.wallet.is_some() || self.has_wallet_phases()
    }

    /// Check if this agent has a script
    pub fn has_script(&self) -> bool {
        self.script.is_some()
    }

    /// Check if this is a script-only agent
    pub fn is_script_only(&self) -> bool {
        !self.has_local_daemon() && !self.has_remote_daemon() && !self.has_wallet() && self.has_script()
    }

    /// Check if this agent has daemon phases
    pub fn has_daemon_phases(&self) -> bool {
        self.daemon_phases.is_some() && !self.daemon_phases.as_ref().unwrap().is_empty()
    }

    /// Check if this agent has wallet phases
    pub fn has_wallet_phases(&self) -> bool {
        self.wallet_phases.is_some() && !self.wallet_phases.as_ref().unwrap().is_empty()
    }

    /// Check if this is a miner based on hashrate or script name
    pub fn is_miner(&self) -> bool {
        self.hashrate.is_some() ||
        self.script.as_ref().map_or(false, |s| s.contains("miner"))
    }

    /// Check if this agent can receive distributions
    pub fn can_receive_distributions(&self) -> bool {
        self.can_receive_distributions.unwrap_or(false)
    }

    /// Get the remote daemon address if this is a wallet-only agent
    pub fn remote_daemon_address(&self) -> Option<&str> {
        match &self.daemon {
            Some(DaemonConfig::Remote { address, .. }) => Some(address),
            _ => None,
        }
    }

    /// Get the daemon selection strategy if this is a wallet-only agent with auto discovery
    pub fn daemon_selection_strategy(&self) -> Option<&DaemonSelectionStrategy> {
        match &self.daemon {
            Some(DaemonConfig::Remote { strategy, .. }) => strategy.as_ref(),
            _ => None,
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
                    if seed_nodes.is_none() || seed_nodes.as_ref().unwrap().is_empty() {
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
    
    /// Check if this is an agent configuration (always true now)
    pub fn is_agent_mode(&self) -> bool {
        true
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

    /// Default daemon options applied to all agents (can be overridden per-agent)
    /// Example: { "log-level": 1, "no-zmq": true, "db-sync-mode": "fastest" }
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_defaults: Option<BTreeMap<String, OptionValue>>,

    /// Default wallet options applied to all agents (can be overridden per-agent)
    /// Example: { "log-level": 1 }
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_defaults: Option<BTreeMap<String, OptionValue>>,
}

fn default_simulation_seed() -> u64 {
    12345
}

fn default_parallelism() -> u32 {
    0  // Auto-detect CPU cores for best performance
}

fn default_difficulty_cache_ttl() -> u32 {
    30  // 30 seconds - difficulty doesn't change frequently in simulation
}

fn default_shadow_log_level() -> String {
    "info".to_string()  // Reduced from "trace" to lower I/O overhead
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

/// User agent configuration
///
/// Supports four agent types:
/// - Full agents: daemon + wallet
/// - Daemon-only: daemon without wallet (public nodes, infrastructure, miners)
/// - Wallet-only: wallet connecting to a remote daemon
/// - Script-only: no Monero processes, just a script (DNS servers, monitors, etc.)
///
/// Also supports phase-based configuration for upgrade scenarios using flat fields:
/// - daemon_0, daemon_0_args, daemon_0_env, daemon_0_start, daemon_0_stop
/// - daemon_1, daemon_1_args, daemon_1_env, daemon_1_start, daemon_1_stop
/// - (same pattern for wallet_0, wallet_1, etc.)
#[derive(Debug, Serialize)]
pub struct UserAgentConfig {
    /// Daemon configuration - local daemon, remote daemon reference, or None
    /// - Local: "monerod" - runs a local daemon (path or shorthand name)
    /// - Remote: { address: "auto", strategy: "random" } - wallet-only connecting to public node
    /// - Remote: { address: "192.168.1.10:18081" } - wallet-only connecting to specific daemon
    /// - None: script-only agent with no Monero daemon
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon: Option<DaemonConfig>,
    /// Additional CLI arguments for the daemon (appended to generated args)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_args: Option<Vec<String>>,
    /// Environment variables for the daemon process
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_env: Option<BTreeMap<String, String>>,
    /// Wallet binary path or shorthand name (e.g., "monero-wallet-rpc" or "~/.monerosim/bin/wallet-v19")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet: Option<String>,
    /// Additional CLI arguments for the wallet (appended to generated args)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_args: Option<Vec<String>>,
    /// Environment variables for the wallet process
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_env: Option<BTreeMap<String, String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_script: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mining_script: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_miner: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attributes: Option<BTreeMap<String, String>>,
    /// Optional start time offset (e.g., "2h", "7200s", "30m")
    /// This offset is added to the normally calculated start time,
    /// allowing agents to join mid-simulation while preserving staggered launches.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub start_time_offset: Option<String>,

    // Phase-based daemon configuration (daemon_0, daemon_1, etc.)
    // These are collected from flat fields during deserialization
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_phases: Option<BTreeMap<u32, DaemonPhase>>,
    // Phase-based wallet configuration (wallet_0, wallet_1, etc.)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_phases: Option<BTreeMap<u32, WalletPhase>>,
}

/// Intermediate struct for deserializing UserAgentConfig with flat phase fields
#[derive(Deserialize)]
struct UserAgentConfigRaw {
    #[serde(default)]
    daemon: Option<DaemonConfig>,
    #[serde(default)]
    daemon_args: Option<Vec<String>>,
    #[serde(default)]
    daemon_env: Option<BTreeMap<String, String>>,
    #[serde(default)]
    wallet: Option<String>,
    #[serde(default)]
    wallet_args: Option<Vec<String>>,
    #[serde(default)]
    wallet_env: Option<BTreeMap<String, String>>,
    #[serde(default)]
    user_script: Option<String>,
    #[serde(default)]
    mining_script: Option<String>,
    #[serde(default)]
    is_miner: Option<bool>,
    #[serde(default)]
    attributes: Option<BTreeMap<String, String>>,
    #[serde(default)]
    start_time_offset: Option<String>,
    // Capture all extra fields for phase parsing
    #[serde(flatten)]
    extra: BTreeMap<String, serde_yaml::Value>,
}

impl<'de> Deserialize<'de> for UserAgentConfig {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = UserAgentConfigRaw::deserialize(deserializer)?;

        // Parse phase fields from extra
        let (daemon_phases, wallet_phases) = parse_phase_fields(&raw.extra);

        Ok(UserAgentConfig {
            daemon: raw.daemon,
            daemon_args: raw.daemon_args,
            daemon_env: raw.daemon_env,
            wallet: raw.wallet,
            wallet_args: raw.wallet_args,
            wallet_env: raw.wallet_env,
            user_script: raw.user_script,
            mining_script: raw.mining_script,
            is_miner: raw.is_miner,
            attributes: raw.attributes,
            start_time_offset: raw.start_time_offset,
            daemon_phases,
            wallet_phases,
        })
    }
}

/// Parse flat phase fields (daemon_0, daemon_0_args, etc.) into structured phases
fn parse_phase_fields(extra: &BTreeMap<String, serde_yaml::Value>) -> (Option<BTreeMap<u32, DaemonPhase>>, Option<BTreeMap<u32, WalletPhase>>) {
    // Regex patterns for phase fields
    let daemon_re = Regex::new(r"^daemon_(\d+)$").unwrap();
    let daemon_args_re = Regex::new(r"^daemon_(\d+)_args$").unwrap();
    let daemon_env_re = Regex::new(r"^daemon_(\d+)_env$").unwrap();
    let daemon_start_re = Regex::new(r"^daemon_(\d+)_start$").unwrap();
    let daemon_stop_re = Regex::new(r"^daemon_(\d+)_stop$").unwrap();

    let wallet_re = Regex::new(r"^wallet_(\d+)$").unwrap();
    let wallet_args_re = Regex::new(r"^wallet_(\d+)_args$").unwrap();
    let wallet_env_re = Regex::new(r"^wallet_(\d+)_env$").unwrap();
    let wallet_start_re = Regex::new(r"^wallet_(\d+)_start$").unwrap();
    let wallet_stop_re = Regex::new(r"^wallet_(\d+)_stop$").unwrap();

    let mut daemon_phases: BTreeMap<u32, DaemonPhase> = BTreeMap::new();
    let mut wallet_phases: BTreeMap<u32, WalletPhase> = BTreeMap::new();

    for (key, value) in extra {
        // Parse daemon phase fields
        if let Some(caps) = daemon_re.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap_or(0);
            let path = value.as_str().unwrap_or("").to_string();
            daemon_phases.entry(phase_num).or_insert_with(|| DaemonPhase {
                path: String::new(),
                args: None,
                env: None,
                start: None,
                stop: None,
            }).path = path;
        } else if let Some(caps) = daemon_args_re.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap_or(0);
            if let Some(seq) = value.as_sequence() {
                let args: Vec<String> = seq.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect();
                daemon_phases.entry(phase_num).or_insert_with(|| DaemonPhase {
                    path: String::new(),
                    args: None,
                    env: None,
                    start: None,
                    stop: None,
                }).args = Some(args);
            }
        } else if let Some(caps) = daemon_env_re.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap_or(0);
            if let Some(map) = value.as_mapping() {
                let env: BTreeMap<String, String> = map.iter()
                    .filter_map(|(k, v)| {
                        let key = k.as_str()?.to_string();
                        let val = v.as_str()?.to_string();
                        Some((key, val))
                    })
                    .collect();
                daemon_phases.entry(phase_num).or_insert_with(|| DaemonPhase {
                    path: String::new(),
                    args: None,
                    env: None,
                    start: None,
                    stop: None,
                }).env = Some(env);
            }
        } else if let Some(caps) = daemon_start_re.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap_or(0);
            let start = value.as_str().unwrap_or("").to_string();
            daemon_phases.entry(phase_num).or_insert_with(|| DaemonPhase {
                path: String::new(),
                args: None,
                env: None,
                start: None,
                stop: None,
            }).start = Some(start);
        } else if let Some(caps) = daemon_stop_re.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap_or(0);
            let stop = value.as_str().unwrap_or("").to_string();
            daemon_phases.entry(phase_num).or_insert_with(|| DaemonPhase {
                path: String::new(),
                args: None,
                env: None,
                start: None,
                stop: None,
            }).stop = Some(stop);
        }

        // Parse wallet phase fields
        if let Some(caps) = wallet_re.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap_or(0);
            let path = value.as_str().unwrap_or("").to_string();
            wallet_phases.entry(phase_num).or_insert_with(|| WalletPhase {
                path: String::new(),
                args: None,
                env: None,
                start: None,
                stop: None,
            }).path = path;
        } else if let Some(caps) = wallet_args_re.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap_or(0);
            if let Some(seq) = value.as_sequence() {
                let args: Vec<String> = seq.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect();
                wallet_phases.entry(phase_num).or_insert_with(|| WalletPhase {
                    path: String::new(),
                    args: None,
                    env: None,
                    start: None,
                    stop: None,
                }).args = Some(args);
            }
        } else if let Some(caps) = wallet_env_re.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap_or(0);
            if let Some(map) = value.as_mapping() {
                let env: BTreeMap<String, String> = map.iter()
                    .filter_map(|(k, v)| {
                        let key = k.as_str()?.to_string();
                        let val = v.as_str()?.to_string();
                        Some((key, val))
                    })
                    .collect();
                wallet_phases.entry(phase_num).or_insert_with(|| WalletPhase {
                    path: String::new(),
                    args: None,
                    env: None,
                    start: None,
                    stop: None,
                }).env = Some(env);
            }
        } else if let Some(caps) = wallet_start_re.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap_or(0);
            let start = value.as_str().unwrap_or("").to_string();
            wallet_phases.entry(phase_num).or_insert_with(|| WalletPhase {
                path: String::new(),
                args: None,
                env: None,
                start: None,
                stop: None,
            }).start = Some(start);
        } else if let Some(caps) = wallet_stop_re.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap_or(0);
            let stop = value.as_str().unwrap_or("").to_string();
            wallet_phases.entry(phase_num).or_insert_with(|| WalletPhase {
                path: String::new(),
                args: None,
                env: None,
                start: None,
                stop: None,
            }).stop = Some(stop);
        }
    }

    let daemon_phases = if daemon_phases.is_empty() { None } else { Some(daemon_phases) };
    let wallet_phases = if wallet_phases.is_empty() { None } else { Some(wallet_phases) };

    (daemon_phases, wallet_phases)
}

/// Configuration for a single daemon phase in an upgrade scenario
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DaemonPhase {
    /// Path to the daemon binary (or shorthand name)
    pub path: String,
    /// Additional CLI arguments for this phase
    #[serde(skip_serializing_if = "Option::is_none")]
    pub args: Option<Vec<String>>,
    /// Environment variables for this phase
    #[serde(skip_serializing_if = "Option::is_none")]
    pub env: Option<BTreeMap<String, String>>,
    /// Start time for this phase (default: "0s" for phase 0)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub start: Option<String>,
    /// Stop time for this phase (when to send SIGTERM)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stop: Option<String>,
}

/// Configuration for a single wallet phase in an upgrade scenario
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct WalletPhase {
    /// Path to the wallet binary (or shorthand name)
    pub path: String,
    /// Additional CLI arguments for this phase
    #[serde(skip_serializing_if = "Option::is_none")]
    pub args: Option<Vec<String>>,
    /// Environment variables for this phase
    #[serde(skip_serializing_if = "Option::is_none")]
    pub env: Option<BTreeMap<String, String>>,
    /// Start time for this phase
    #[serde(skip_serializing_if = "Option::is_none")]
    pub start: Option<String>,
    /// Stop time for this phase (when to send SIGTERM)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stop: Option<String>,
}

impl UserAgentConfig {
    /// Check if this agent is a miner based on top-level field or attributes
    /// Returns true if is_miner is true or "is_miner" in attributes is "true" or true
    /// Returns false otherwise
    pub fn is_miner_value(&self) -> bool {
        // Check top-level is_miner field first
        if let Some(is_miner) = self.is_miner {
            return is_miner;
        }

        // Fall back to attributes
        if let Some(attrs) = &self.attributes {
            if let Some(is_miner_value) = attrs.get("is_miner") {
                // Handle string representations
                match is_miner_value.to_lowercase().as_str() {
                    "true" | "1" | "yes" | "on" => return true,
                    "false" | "0" | "no" | "off" => return false,
                    _ => {} // Continue to check other formats
                }

                // Try to parse as boolean directly
                if let Ok(parsed_bool) = is_miner_value.parse::<bool>() {
                    return parsed_bool;
                }
            }
        }
        false
    }

    /// Check if this agent has a local daemon
    /// Includes both simple daemon config and phase-based configuration
    pub fn has_local_daemon(&self) -> bool {
        matches!(&self.daemon, Some(DaemonConfig::Local(_))) || self.has_daemon_phases()
    }

    /// Check if this agent has a remote daemon configuration (wallet-only)
    pub fn has_remote_daemon(&self) -> bool {
        matches!(&self.daemon, Some(DaemonConfig::Remote { .. }))
    }

    /// Check if this agent has a wallet
    /// Includes both simple wallet config and phase-based configuration
    pub fn has_wallet(&self) -> bool {
        self.wallet.is_some() || self.has_wallet_phases()
    }

    /// Check if this agent has any script (user_script or mining_script)
    pub fn has_script(&self) -> bool {
        self.user_script.is_some() || self.mining_script.is_some()
    }

    /// Check if this is a script-only agent (no daemon, no wallet)
    pub fn is_script_only(&self) -> bool {
        !self.has_local_daemon() && !self.has_remote_daemon() && !self.has_wallet() && self.has_script()
    }

    /// Check if this is a daemon-only agent (daemon, no wallet)
    pub fn is_daemon_only(&self) -> bool {
        self.has_local_daemon() && !self.has_wallet()
    }

    /// Check if this is a wallet-only agent (remote daemon, wallet, no local daemon)
    pub fn is_wallet_only(&self) -> bool {
        self.has_remote_daemon() && self.has_wallet()
    }

    /// Check if this is a full agent (local daemon + wallet)
    pub fn is_full_agent(&self) -> bool {
        self.has_local_daemon() && self.has_wallet()
    }

    /// Check if this agent is configured as a public node
    pub fn is_public_node(&self) -> bool {
        if let Some(attrs) = &self.attributes {
            if let Some(value) = attrs.get("is_public_node") {
                return value.to_lowercase() == "true";
            }
        }
        false
    }

    /// Get the remote daemon address if this is a wallet-only agent
    pub fn remote_daemon_address(&self) -> Option<&str> {
        match &self.daemon {
            Some(DaemonConfig::Remote { address, .. }) => Some(address),
            _ => None,
        }
    }

    /// Get the daemon selection strategy if this is a wallet-only agent with auto discovery
    pub fn daemon_selection_strategy(&self) -> Option<&DaemonSelectionStrategy> {
        match &self.daemon {
            Some(DaemonConfig::Remote { strategy, .. }) => strategy.as_ref(),
            _ => None,
        }
    }

    /// Check if this agent uses daemon phases (upgrade scenario)
    pub fn has_daemon_phases(&self) -> bool {
        self.daemon_phases.is_some() && !self.daemon_phases.as_ref().unwrap().is_empty()
    }

    /// Check if this agent uses wallet phases (upgrade scenario)
    pub fn has_wallet_phases(&self) -> bool {
        self.wallet_phases.is_some() && !self.wallet_phases.as_ref().unwrap().is_empty()
    }

    /// Validate daemon phase configuration
    ///
    /// Checks:
    /// - Sequential numbering starting from 0
    /// - Each phase has a non-empty path
    /// - No time overlap between phases (stop < next start)
    pub fn validate_daemon_phases(&self) -> Result<(), PhaseValidationError> {
        let phases = match &self.daemon_phases {
            Some(p) if !p.is_empty() => p,
            _ => return Ok(()), // No phases to validate
        };

        // Check sequential numbering starting from 0
        let phase_nums: Vec<u32> = phases.keys().copied().collect();
        for (i, &num) in phase_nums.iter().enumerate() {
            if num != i as u32 {
                return Err(PhaseValidationError::NonSequentialPhases {
                    expected: i as u32,
                    found: num,
                    phase_type: "daemon".to_string(),
                });
            }
        }

        // Check each phase has a path
        for (num, phase) in phases {
            if phase.path.is_empty() {
                return Err(PhaseValidationError::MissingPath {
                    phase_num: *num,
                    phase_type: "daemon".to_string(),
                });
            }
        }

        // Check timing for multi-phase configurations
        for i in 0..phase_nums.len().saturating_sub(1) {
            let current_phase = &phases[&phase_nums[i]];
            let next_phase = &phases[&phase_nums[i + 1]];
            let current_num = phase_nums[i];
            let next_num = phase_nums[i + 1];

            // Check stop time exists for non-last phases
            let stop_time = match &current_phase.stop {
                Some(s) if !s.is_empty() => s,
                _ => {
                    return Err(PhaseValidationError::MissingTiming {
                        phase_num: current_num,
                        phase_type: "daemon".to_string(),
                        detail: "stop time required when followed by another phase".to_string(),
                    });
                }
            };

            // Check start time exists for phases after phase 0
            let start_time = match &next_phase.start {
                Some(s) if !s.is_empty() => s,
                _ => {
                    return Err(PhaseValidationError::MissingTiming {
                        phase_num: next_num,
                        phase_type: "daemon".to_string(),
                        detail: "start time required for phases after phase 0".to_string(),
                    });
                }
            };

            // Parse durations and check gap
            let stop_secs = parse_duration_to_seconds(stop_time).map_err(|e| {
                PhaseValidationError::InvalidDuration {
                    phase_type: "daemon".to_string(),
                    phase_num: current_num,
                    detail: format!("stop time '{}': {}", stop_time, e),
                }
            })?;

            let start_secs = parse_duration_to_seconds(start_time).map_err(|e| {
                PhaseValidationError::InvalidDuration {
                    phase_type: "daemon".to_string(),
                    phase_num: next_num,
                    detail: format!("start time '{}': {}", start_time, e),
                }
            })?;

            // Check that there's adequate gap between stop and start
            if start_secs < stop_secs + MIN_PHASE_GAP_SECONDS {
                return Err(PhaseValidationError::GapTooSmall {
                    phase_type: "daemon".to_string(),
                    phase_num: current_num,
                    next_phase_num: next_num,
                    stop_time: stop_time.clone(),
                    start_time: start_time.clone(),
                    min_gap: MIN_PHASE_GAP_SECONDS,
                });
            }
        }

        Ok(())
    }

    /// Validate wallet phase configuration (same rules as daemon phases)
    pub fn validate_wallet_phases(&self) -> Result<(), PhaseValidationError> {
        let phases = match &self.wallet_phases {
            Some(p) if !p.is_empty() => p,
            _ => return Ok(()), // No phases to validate
        };

        // Check sequential numbering starting from 0
        let phase_nums: Vec<u32> = phases.keys().copied().collect();
        for (i, &num) in phase_nums.iter().enumerate() {
            if num != i as u32 {
                return Err(PhaseValidationError::NonSequentialPhases {
                    expected: i as u32,
                    found: num,
                    phase_type: "wallet".to_string(),
                });
            }
        }

        // Check each phase has a path
        for (num, phase) in phases {
            if phase.path.is_empty() {
                return Err(PhaseValidationError::MissingPath {
                    phase_num: *num,
                    phase_type: "wallet".to_string(),
                });
            }
        }

        // Check timing for multi-phase configurations
        for i in 0..phase_nums.len().saturating_sub(1) {
            let current_phase = &phases[&phase_nums[i]];
            let next_phase = &phases[&phase_nums[i + 1]];
            let current_num = phase_nums[i];
            let next_num = phase_nums[i + 1];

            // Check stop time exists for non-last phases
            let stop_time = match &current_phase.stop {
                Some(s) if !s.is_empty() => s,
                _ => {
                    return Err(PhaseValidationError::MissingTiming {
                        phase_num: current_num,
                        phase_type: "wallet".to_string(),
                        detail: "stop time required when followed by another phase".to_string(),
                    });
                }
            };

            // Check start time exists for phases after phase 0
            let start_time = match &next_phase.start {
                Some(s) if !s.is_empty() => s,
                _ => {
                    return Err(PhaseValidationError::MissingTiming {
                        phase_num: next_num,
                        phase_type: "wallet".to_string(),
                        detail: "start time required for phases after phase 0".to_string(),
                    });
                }
            };

            // Parse durations and check gap
            let stop_secs = parse_duration_to_seconds(stop_time).map_err(|e| {
                PhaseValidationError::InvalidDuration {
                    phase_type: "wallet".to_string(),
                    phase_num: current_num,
                    detail: format!("stop time '{}': {}", stop_time, e),
                }
            })?;

            let start_secs = parse_duration_to_seconds(start_time).map_err(|e| {
                PhaseValidationError::InvalidDuration {
                    phase_type: "wallet".to_string(),
                    phase_num: next_num,
                    detail: format!("start time '{}': {}", start_time, e),
                }
            })?;

            // Check that there's adequate gap between stop and start
            if start_secs < stop_secs + MIN_PHASE_GAP_SECONDS {
                return Err(PhaseValidationError::GapTooSmall {
                    phase_type: "wallet".to_string(),
                    phase_num: current_num,
                    next_phase_num: next_num,
                    stop_time: stop_time.clone(),
                    start_time: start_time.clone(),
                    min_gap: MIN_PHASE_GAP_SECONDS,
                });
            }
        }

        Ok(())
    }

    /// Validate that simple config and phase config are not mixed
    pub fn validate_no_mixed_config(&self) -> Result<(), PhaseValidationError> {
        if self.daemon.is_some() && self.has_daemon_phases() {
            return Err(PhaseValidationError::MixedConfig {
                phase_type: "daemon".to_string(),
                detail: "Cannot use both 'daemon' and 'daemon_N' fields".to_string(),
            });
        }
        if self.wallet.is_some() && self.has_wallet_phases() {
            return Err(PhaseValidationError::MixedConfig {
                phase_type: "wallet".to_string(),
                detail: "Cannot use both 'wallet' and 'wallet_N' fields".to_string(),
            });
        }
        Ok(())
    }

    /// Validate all phase configuration
    pub fn validate_phases(&self) -> Result<(), PhaseValidationError> {
        self.validate_no_mixed_config()?;
        self.validate_daemon_phases()?;
        self.validate_wallet_phases()?;
        Ok(())
    }
}

/// Minimum gap between phase stop and next phase start (in seconds)
/// This allows time for graceful shutdown and startup of the next binary
pub const MIN_PHASE_GAP_SECONDS: u64 = 30;

/// Errors from phase validation
#[derive(Debug, thiserror::Error)]
pub enum PhaseValidationError {
    #[error("Non-sequential phase numbering for {phase_type}: expected {expected}, found {found}")]
    NonSequentialPhases {
        expected: u32,
        found: u32,
        phase_type: String,
    },

    #[error("Missing path for {phase_type} phase {phase_num}")]
    MissingPath {
        phase_num: u32,
        phase_type: String,
    },

    #[error("Missing timing for {phase_type} phase {phase_num}: {detail}")]
    MissingTiming {
        phase_num: u32,
        phase_type: String,
        detail: String,
    },

    #[error("Mixed configuration for {phase_type}: {detail}")]
    MixedConfig {
        phase_type: String,
        detail: String,
    },

    #[error("Insufficient gap between {phase_type} phases {phase_num} and {next_phase_num}: stop={stop_time}, start={start_time}, need at least {min_gap}s gap")]
    GapTooSmall {
        phase_type: String,
        phase_num: u32,
        next_phase_num: u32,
        stop_time: String,
        start_time: String,
        min_gap: u64,
    },

    #[error("Invalid duration format for {phase_type} phase {phase_num}: {detail}")]
    InvalidDuration {
        phase_type: String,
        phase_num: u32,
        detail: String,
    },
}

/// Miner distributor agent configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct MinerDistributorConfig {
    pub script: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attributes: Option<BTreeMap<String, String>>,
}

/// Pure script agent configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct PureScriptAgentConfig {
    pub script: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arguments: Option<Vec<String>>,
}

/// Simulation monitor agent configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct SimulationMonitorConfig {
    pub script: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub poll_interval: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status_file: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub enable_alerts: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub detailed_logging: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arguments: Option<Vec<String>>,
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
    },
}

/// Configuration validation errors
#[derive(Debug, thiserror::Error)]
pub enum ValidationError {
    #[error("Invalid agent configuration: {0}")]
    InvalidAgent(String),
    #[error("Invalid general configuration: {0}")]
    InvalidGeneral(String),
    #[error("Invalid network configuration: {0}")]
    InvalidNetwork(String),
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
            daemon_defaults: None,  // No daemon defaults by default
            wallet_defaults: None,  // No wallet defaults by default
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




