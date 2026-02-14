//! Shadow process configuration for daemons, wallets, and agent scripts.

pub mod wallet;
pub mod agent_scripts;

pub use wallet::{add_wallet_process, add_remote_wallet_process};
pub use agent_scripts::{add_user_agent_process, create_mining_agent_process};
