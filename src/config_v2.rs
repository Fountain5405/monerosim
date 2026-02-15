use serde::{Deserialize, Deserializer, Serialize};
use std::collections::BTreeMap;
use std::sync::LazyLock;
use regex::Regex;
use crate::utils::duration::parse_duration_to_seconds;

// Static regex patterns for parsing phase fields (compiled once)
static DAEMON_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^daemon_(\d+)$").unwrap());
static DAEMON_ARGS_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^daemon_(\d+)_args$").unwrap());
static DAEMON_ENV_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^daemon_(\d+)_env$").unwrap());
static DAEMON_START_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^daemon_(\d+)_start$").unwrap());
static DAEMON_STOP_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^daemon_(\d+)_stop$").unwrap());
static WALLET_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^wallet_(\d+)$").unwrap());
static WALLET_ARGS_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^wallet_(\d+)_args$").unwrap());
static WALLET_ENV_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^wallet_(\d+)_env$").unwrap());
static WALLET_START_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^wallet_(\d+)_start$").unwrap());
static WALLET_STOP_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^wallet_(\d+)_stop$").unwrap());

/// Peer mode options for network configuration
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub enum PeerMode {
    Dynamic,
    Hardcoded,
    Hybrid,
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
///
/// Uses flat format for daemon/wallet phases:
/// `daemon_0: "monerod"`, `daemon_0_start: "0s"`, `daemon_0_stop: "30m"`
#[derive(Debug, Clone, Serialize)]
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

    /// Initial wait time before first distribution (seconds)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub initial_wait_time: Option<u32>,

    /// Number of recipients per batch transaction (max 16 due to Monero tx size limits)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub md_n_recipients: Option<u32>,

    /// Number of outputs per recipient per transaction (recipients * outputs <= 16)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub md_out_per_tx: Option<u32>,

    /// Amount per output in XMR
    #[serde(skip_serializing_if = "Option::is_none")]
    pub md_output_amount: Option<f64>,

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
    // Daemon phases are parsed from flat fields (daemon_0, daemon_0_start, daemon_0_stop, etc.)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_phases: Option<BTreeMap<u32, DaemonPhase>>,

    // Wallet phases are parsed from flat fields (wallet_0, wallet_0_start, wallet_0_stop, etc.)
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

    /// Subnet group for IP clustering
    /// Agents with the same subnet_group will be assigned IPs in the same /24 subnet.
    /// Useful for simulating Sybil attacks where an attacker's nodes share infrastructure.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub subnet_group: Option<String>,
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

    /// Check if this is a miner based on hashrate
    /// Note: Miners are identified by having a hashrate value, not by script name
    /// (e.g., "miner_distributor" is NOT a miner - it distributes rewards)
    pub fn is_miner(&self) -> bool {
        self.hashrate.is_some()
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

    /// Check if this agent is configured as a public node
    pub fn is_public_node(&self) -> bool {
        self.attributes.as_ref()
            .and_then(|attrs| attrs.get("is_public_node"))
            .map_or(false, |v| v.to_lowercase() == "true")
    }

    /// Check if this is a daemon-only (relay) agent: has daemon but no wallet or script
    pub fn is_daemon_only(&self) -> bool {
        (self.has_local_daemon() || self.has_daemon_phases()) && !self.has_wallet() && !self.has_script()
    }
}

/// Raw struct for deserializing AgentConfig with flat phase fields support
#[derive(Debug, Clone, Deserialize)]
struct AgentConfigRaw {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon: Option<DaemonConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub script: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_options: Option<BTreeMap<String, OptionValue>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_options: Option<BTreeMap<String, OptionValue>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub start_time: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hashrate: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transaction_interval: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub activity_start_time: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub can_receive_distributions: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait_time: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub initial_fund_amount: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_transaction_amount: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_transaction_amount: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transaction_frequency: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub initial_wait_time: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub md_n_recipients: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub md_out_per_tx: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub md_output_amount: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub poll_interval: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status_file: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub enable_alerts: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub detailed_logging: Option<bool>,
    // Note: daemon_phases and wallet_phases are NOT parsed from YAML directly
    // They are populated from flat fields (daemon_0, daemon_0_start, etc.)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_args: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_args: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub daemon_env: Option<BTreeMap<String, String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_env: Option<BTreeMap<String, String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attributes: Option<BTreeMap<String, String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub subnet_group: Option<String>,
    /// Capture any extra fields for flat phase parsing
    #[serde(flatten)]
    pub extra: BTreeMap<String, serde_yaml::Value>,
}

impl<'de> Deserialize<'de> for AgentConfig {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let raw = AgentConfigRaw::deserialize(deserializer)?;

        // Parse flat phase fields from extra (e.g., daemon_0, daemon_0_args, daemon_0_start)
        let (parsed_daemon_phases, parsed_wallet_phases) = parse_phase_fields(&raw.extra);

        // Convert parsed phases to Option (None if empty)
        let daemon_phases = if !parsed_daemon_phases.is_empty() {
            Some(parsed_daemon_phases)
        } else {
            None
        };

        let wallet_phases = if !parsed_wallet_phases.is_empty() {
            Some(parsed_wallet_phases)
        } else {
            None
        };

        Ok(AgentConfig {
            daemon: raw.daemon,
            wallet: raw.wallet,
            script: raw.script,
            daemon_options: raw.daemon_options,
            wallet_options: raw.wallet_options,
            start_time: raw.start_time,
            hashrate: raw.hashrate,
            transaction_interval: raw.transaction_interval,
            activity_start_time: raw.activity_start_time,
            can_receive_distributions: raw.can_receive_distributions,
            wait_time: raw.wait_time,
            initial_fund_amount: raw.initial_fund_amount,
            max_transaction_amount: raw.max_transaction_amount,
            min_transaction_amount: raw.min_transaction_amount,
            transaction_frequency: raw.transaction_frequency,
            initial_wait_time: raw.initial_wait_time,
            md_n_recipients: raw.md_n_recipients,
            md_out_per_tx: raw.md_out_per_tx,
            md_output_amount: raw.md_output_amount,
            poll_interval: raw.poll_interval,
            status_file: raw.status_file,
            enable_alerts: raw.enable_alerts,
            detailed_logging: raw.detailed_logging,
            daemon_phases,
            wallet_phases,
            daemon_args: raw.daemon_args,
            wallet_args: raw.wallet_args,
            daemon_env: raw.daemon_env,
            wallet_env: raw.wallet_env,
            attributes: raw.attributes,
            subnet_group: raw.subnet_group,
        })
    }
}

/// Parse phase fields for a single phase type (daemon or wallet) from flat YAML keys.
///
/// Matches keys like `{prefix}_{N}`, `{prefix}_{N}_args`, etc. against the
/// provided regex patterns and populates the phases map.
fn parse_typed_phases<P: Phase>(
    extra: &BTreeMap<String, serde_yaml::Value>,
    re_path: &Regex,
    re_args: &Regex,
    re_env: &Regex,
    re_start: &Regex,
    re_stop: &Regex,
) -> BTreeMap<u32, P> {
    let mut phases: BTreeMap<u32, P> = BTreeMap::new();

    for (key, value) in extra {
        if let Some(caps) = re_path.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap();
            phases.entry(phase_num).or_default()
                .set_path(value.as_str().unwrap_or_default().to_string());
        } else if let Some(caps) = re_args.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap();
            if let Some(args) = value.as_sequence() {
                let args: Vec<String> = args.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect();
                phases.entry(phase_num).or_default().set_args(args);
            }
        } else if let Some(caps) = re_env.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap();
            if let Some(env_map) = value.as_mapping() {
                let env: BTreeMap<String, String> = env_map.iter()
                    .filter_map(|(k, v)| {
                        Some((k.as_str()?.to_string(), v.as_str()?.to_string()))
                    })
                    .collect();
                phases.entry(phase_num).or_default().set_env(env);
            }
        } else if let Some(caps) = re_start.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap();
            phases.entry(phase_num).or_default()
                .set_start(value.as_str().unwrap_or_default().to_string());
        } else if let Some(caps) = re_stop.captures(key) {
            let phase_num: u32 = caps[1].parse().unwrap();
            phases.entry(phase_num).or_default()
                .set_stop(value.as_str().unwrap_or_default().to_string());
        }
    }

    phases
}

/// Parse flat phase fields (daemon_0, daemon_0_args, etc.) into structured phases
fn parse_phase_fields(
    extra: &BTreeMap<String, serde_yaml::Value>,
) -> (BTreeMap<u32, DaemonPhase>, BTreeMap<u32, WalletPhase>) {
    let daemon_phases = parse_typed_phases(
        extra, &DAEMON_RE, &DAEMON_ARGS_RE, &DAEMON_ENV_RE, &DAEMON_START_RE, &DAEMON_STOP_RE,
    );
    let wallet_phases = parse_typed_phases(
        extra, &WALLET_RE, &WALLET_ARGS_RE, &WALLET_ENV_RE, &WALLET_START_RE, &WALLET_STOP_RE,
    );
    (daemon_phases, wallet_phases)
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

fn default_shared_dir() -> String {
    "/tmp/monerosim_shared".to_string()
}

fn default_daemon_data_dir() -> String {
    "/tmp".to_string()
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

/// Configuration for a single daemon phase in an upgrade scenario
#[derive(Debug, Serialize, Deserialize, Clone, Default)]
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
#[derive(Debug, Serialize, Deserialize, Clone, Default)]
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

/// Common interface for phase types (DaemonPhase and WalletPhase share identical fields)
trait Phase: Default {
    fn set_path(&mut self, path: String);
    fn set_args(&mut self, args: Vec<String>);
    fn set_env(&mut self, env: BTreeMap<String, String>);
    fn set_start(&mut self, start: String);
    fn set_stop(&mut self, stop: String);
}

macro_rules! impl_phase {
    ($t:ty) => {
        impl Phase for $t {
            fn set_path(&mut self, path: String) { self.path = path; }
            fn set_args(&mut self, args: Vec<String>) { self.args = Some(args); }
            fn set_env(&mut self, env: BTreeMap<String, String>) { self.env = Some(env); }
            fn set_start(&mut self, start: String) { self.start = Some(start); }
            fn set_stop(&mut self, stop: String) { self.stop = Some(stop); }
        }
    };
}

impl_phase!(DaemonPhase);
impl_phase!(WalletPhase);

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

/// Validate daemon phases for an agent, ensuring sufficient gaps between phases.
/// Returns Ok(()) if valid, or an error describing the validation failure.
pub fn validate_daemon_phases(
    agent_id: &str,
    phases: &BTreeMap<u32, DaemonPhase>,
) -> Result<(), PhaseValidationError> {
    let phase_nums: Vec<u32> = phases.keys().copied().collect();

    // Check sequential numbering
    for (i, &phase_num) in phase_nums.iter().enumerate() {
        if phase_num != i as u32 {
            return Err(PhaseValidationError::NonSequentialPhases {
                expected: i as u32,
                found: phase_num,
                phase_type: format!("daemon (agent {})", agent_id),
            });
        }
    }

    // Check each phase has required fields and validate gaps
    for (i, (&phase_num, phase)) in phases.iter().enumerate() {
        // Check path is not empty
        if phase.path.is_empty() {
            return Err(PhaseValidationError::MissingPath {
                phase_num,
                phase_type: format!("daemon (agent {})", agent_id),
            });
        }

        // Check start time exists
        if phase.start.is_none() {
            return Err(PhaseValidationError::MissingTiming {
                phase_num,
                phase_type: format!("daemon (agent {})", agent_id),
                detail: "missing start time".to_string(),
            });
        }

        // For non-final phases, check stop time and gap to next phase
        if i < phases.len() - 1 {
            let next_phase_num = phase_nums[i + 1];
            let next_phase = &phases[&next_phase_num];

            // Current phase needs stop time
            let stop_time = match &phase.stop {
                Some(t) => t,
                None => {
                    return Err(PhaseValidationError::MissingTiming {
                        phase_num,
                        phase_type: format!("daemon (agent {})", agent_id),
                        detail: "non-final phase must have stop time".to_string(),
                    });
                }
            };

            // Next phase needs start time
            let next_start_time = match &next_phase.start {
                Some(t) => t,
                None => {
                    return Err(PhaseValidationError::MissingTiming {
                        phase_num: next_phase_num,
                        phase_type: format!("daemon (agent {})", agent_id),
                        detail: "missing start time".to_string(),
                    });
                }
            };

            // Parse and compare times
            let stop_seconds = parse_duration_to_seconds(stop_time).map_err(|e| {
                PhaseValidationError::InvalidDuration {
                    phase_type: format!("daemon (agent {})", agent_id),
                    phase_num,
                    detail: format!("stop time: {}", e),
                }
            })?;

            let start_seconds = parse_duration_to_seconds(next_start_time).map_err(|e| {
                PhaseValidationError::InvalidDuration {
                    phase_type: format!("daemon (agent {})", agent_id),
                    phase_num: next_phase_num,
                    detail: format!("start time: {}", e),
                }
            })?;

            // Check gap is sufficient
            if start_seconds < stop_seconds + MIN_PHASE_GAP_SECONDS {
                return Err(PhaseValidationError::GapTooSmall {
                    phase_type: format!("daemon (agent {})", agent_id),
                    phase_num,
                    next_phase_num,
                    stop_time: stop_time.clone(),
                    start_time: next_start_time.clone(),
                    min_gap: MIN_PHASE_GAP_SECONDS,
                });
            }
        }
    }

    Ok(())
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
            native_preemption: None,  // Shadow default (false) applies when unset
            daemon_defaults: None,  // No daemon defaults by default
            wallet_defaults: None,  // No wallet defaults by default
            shared_dir: default_shared_dir(),
            daemon_data_dir: default_daemon_data_dir(),
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




