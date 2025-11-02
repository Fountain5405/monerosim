//! Process configuration module.
//!
//! This module handles generation of Shadow process configurations
//! for various Monerosim components (daemons, wallets, agents, scripts).

pub mod types;
pub mod daemon;
pub mod wallet;
pub mod agent_scripts;
pub mod pure_scripts;

// Re-export commonly used functions for convenience
pub use types::ProcessType;
