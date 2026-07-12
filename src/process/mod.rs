//! Shadow process configuration for daemons, wallets, and agent scripts.

pub mod agent_scripts;
pub mod wallet;

pub use agent_scripts::{
    add_user_agent_process, create_mining_agent_process, MiningAgentProcessArgs,
    UserAgentProcessArgs,
};
pub use wallet::{add_wallet_process, DaemonAddress, WalletProcessArgs};
