//! Daemon and wallet phase configuration types for upgrade scenarios.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

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

/// Minimum gap between phase stop and next phase start (in seconds)
/// This allows time for graceful shutdown and startup of the next binary
pub const MIN_PHASE_GAP_SECONDS: u64 = 30;
