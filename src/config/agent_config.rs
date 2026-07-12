//! Per-agent configuration: `AgentConfig`, its custom deserializer, and the
//! flat-phase-field parsing helpers used to populate `daemon_phases` and
//! `wallet_phases` from YAML keys like `daemon_0`, `daemon_0_args`, etc.

use regex::Regex;
use serde::{Deserialize, Deserializer, Serialize};
use std::collections::BTreeMap;
use std::sync::LazyLock;

use crate::utils::duration::parse_duration_to_seconds;

use super::phases::{DaemonPhase, WalletPhase};
use super::types::{DaemonConfig, DaemonSelectionStrategy};

/// Deserialize an optional duration field that accepts either a u32 (seconds)
/// or a duration string like "4h", "30m", "120s".
fn deserialize_duration_option<'de, D>(deserializer: D) -> Result<Option<u32>, D::Error>
where
    D: Deserializer<'de>,
{
    use serde::de;

    let value: Option<serde_yaml::Value> = Option::deserialize(deserializer)?;
    match value {
        None => Ok(None),
        Some(serde_yaml::Value::Number(n)) => n
            .as_u64()
            .and_then(|v| u32::try_from(v).ok())
            .map(Some)
            .ok_or_else(|| de::Error::custom(format!("invalid u32 value: {n}"))),
        Some(serde_yaml::Value::String(s)) => parse_duration_to_seconds(&s)
            .map(|v| Some(v as u32))
            .map_err(|e| de::Error::custom(e)),
        Some(other) => Err(de::Error::custom(format!(
            "expected number or duration string, got: {other:?}"
        ))),
    }
}

// Static regex patterns for parsing phase fields (compiled once).
// `.expect()` is safe here: the literal patterns are syntactically valid Rust
// regex and tested at startup via LazyLock — if these ever fail, it's a code
// bug, not user input.
static DAEMON_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^daemon_(\d+)$").expect("invariant: DAEMON_RE pattern is a valid regex")
});
static DAEMON_ARGS_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^daemon_(\d+)_args$").expect("invariant: DAEMON_ARGS_RE pattern is a valid regex")
});
static DAEMON_ENV_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^daemon_(\d+)_env$").expect("invariant: DAEMON_ENV_RE pattern is a valid regex")
});
static DAEMON_START_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^daemon_(\d+)_start$")
        .expect("invariant: DAEMON_START_RE pattern is a valid regex")
});
static DAEMON_STOP_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^daemon_(\d+)_stop$").expect("invariant: DAEMON_STOP_RE pattern is a valid regex")
});
static WALLET_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^wallet_(\d+)$").expect("invariant: WALLET_RE pattern is a valid regex")
});
static WALLET_ARGS_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^wallet_(\d+)_args$").expect("invariant: WALLET_ARGS_RE pattern is a valid regex")
});
static WALLET_ENV_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^wallet_(\d+)_env$").expect("invariant: WALLET_ENV_RE pattern is a valid regex")
});
static WALLET_START_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^wallet_(\d+)_start$")
        .expect("invariant: WALLET_START_RE pattern is a valid regex")
});
static WALLET_STOP_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^wallet_(\d+)_stop$").expect("invariant: WALLET_STOP_RE pattern is a valid regex")
});

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
        !self.has_local_daemon()
            && !self.has_remote_daemon()
            && !self.has_wallet()
            && self.has_script()
    }

    /// Check if this agent has daemon phases
    pub fn has_daemon_phases(&self) -> bool {
        self.daemon_phases.as_ref().is_some_and(|p| !p.is_empty())
    }

    /// Check if this agent has wallet phases
    pub fn has_wallet_phases(&self) -> bool {
        self.wallet_phases.as_ref().is_some_and(|p| !p.is_empty())
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
        self.attributes
            .as_ref()
            .and_then(|attrs| attrs.get("is_public_node"))
            .map_or(false, |v| v.to_lowercase() == "true")
    }

    /// Check if this is a daemon-only (relay) agent: has daemon but no wallet or script
    pub fn is_daemon_only(&self) -> bool {
        (self.has_local_daemon() || self.has_daemon_phases())
            && !self.has_wallet()
            && !self.has_script()
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
    #[serde(default, deserialize_with = "deserialize_duration_option")]
    pub transaction_interval: Option<u32>,
    #[serde(default, deserialize_with = "deserialize_duration_option")]
    pub activity_start_time: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub can_receive_distributions: Option<bool>,
    #[serde(default, deserialize_with = "deserialize_duration_option")]
    pub wait_time: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub initial_fund_amount: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_transaction_amount: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_transaction_amount: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub md_n_recipients: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub md_out_per_tx: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub md_output_amount: Option<f64>,
    #[serde(default, deserialize_with = "deserialize_duration_option")]
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

    // Helper that parses the phase number capture group. The regex only
    // matches `\d+`, so the only realistic failure is u32 overflow on a
    // pathological key (e.g. `daemon_99999999999`). Skip with a warning
    // rather than panic — keeps load resilient to weird user input.
    let parse_phase_num = |caps: &regex::Captures, key: &str| -> Option<u32> {
        match caps[1].parse::<u32>() {
            Ok(n) => Some(n),
            Err(e) => {
                log::warn!(
                    "Ignoring phase key '{}': phase number does not fit in u32 ({})",
                    key,
                    e
                );
                None
            }
        }
    };

    for (key, value) in extra {
        if let Some(caps) = re_path.captures(key) {
            let Some(phase_num) = parse_phase_num(&caps, key) else {
                continue;
            };
            phases
                .entry(phase_num)
                .or_default()
                .set_path(value.as_str().unwrap_or_default().to_string());
        } else if let Some(caps) = re_args.captures(key) {
            let Some(phase_num) = parse_phase_num(&caps, key) else {
                continue;
            };
            if let Some(args) = value.as_sequence() {
                let args: Vec<String> = args
                    .iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect();
                phases.entry(phase_num).or_default().set_args(args);
            }
        } else if let Some(caps) = re_env.captures(key) {
            let Some(phase_num) = parse_phase_num(&caps, key) else {
                continue;
            };
            if let Some(env_map) = value.as_mapping() {
                let env: BTreeMap<String, String> = env_map
                    .iter()
                    .filter_map(|(k, v)| Some((k.as_str()?.to_string(), v.as_str()?.to_string())))
                    .collect();
                phases.entry(phase_num).or_default().set_env(env);
            }
        } else if let Some(caps) = re_start.captures(key) {
            let Some(phase_num) = parse_phase_num(&caps, key) else {
                continue;
            };
            phases
                .entry(phase_num)
                .or_default()
                .set_start(value.as_str().unwrap_or_default().to_string());
        } else if let Some(caps) = re_stop.captures(key) {
            let Some(phase_num) = parse_phase_num(&caps, key) else {
                continue;
            };
            phases
                .entry(phase_num)
                .or_default()
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
        extra,
        &DAEMON_RE,
        &DAEMON_ARGS_RE,
        &DAEMON_ENV_RE,
        &DAEMON_START_RE,
        &DAEMON_STOP_RE,
    );
    let wallet_phases = parse_typed_phases(
        extra,
        &WALLET_RE,
        &WALLET_ARGS_RE,
        &WALLET_ENV_RE,
        &WALLET_START_RE,
        &WALLET_STOP_RE,
    );
    (daemon_phases, wallet_phases)
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
            fn set_path(&mut self, path: String) {
                self.path = path;
            }
            fn set_args(&mut self, args: Vec<String>) {
                self.args = Some(args);
            }
            fn set_env(&mut self, env: BTreeMap<String, String>) {
                self.env = Some(env);
            }
            fn set_start(&mut self, start: String) {
                self.start = Some(start);
            }
            fn set_stop(&mut self, stop: String) {
                self.stop = Some(stop);
            }
        }
    };
}

impl_phase!(DaemonPhase);
impl_phase!(WalletPhase);
