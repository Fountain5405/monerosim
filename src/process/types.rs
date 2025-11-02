//! Process type definitions.
//!
//! This file contains type definitions for different process types
//! used in Shadow process configuration.

/// Enum representing different types of processes that can be configured in Shadow
#[derive(Debug, Clone, PartialEq)]
pub enum ProcessType {
    /// Monero daemon process
    Daemon,
    /// Monero wallet RPC process
    Wallet,
    /// Python agent script process
    Agent,
    /// Pure Python script process (no daemon/wallet)
    Script,
}

impl ProcessType {
    /// Get the string representation of the process type
    pub fn as_str(&self) -> &'static str {
        match self {
            ProcessType::Daemon => "daemon",
            ProcessType::Wallet => "wallet",
            ProcessType::Agent => "agent",
            ProcessType::Script => "script",
        }
    }
}