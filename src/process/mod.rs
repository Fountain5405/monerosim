//! # Process Configuration Module
//!
//! This module handles the generation and configuration of Shadow process
//! definitions for all Monerosim components, including Monero daemons,
//! wallets, Python agents, and custom scripts.
//!
//! ## Process Types
//!
//! The module supports several categories of processes:
//!
//! - **Daemons**: Monero daemon processes (`monerod`) that maintain the blockchain
//!   and handle P2P networking. Each daemon can be configured with custom startup
//!   parameters, peer connections, and resource limits.
//!
//! - **Wallets**: Monero wallet RPC processes (`monero-wallet-rpc`) that provide
//!   wallet functionality for miners and users. Required for any agent that needs
//!   to send/receive transactions.
//!
//! - **User Agents**: Python scripts that implement autonomous agent behaviors,
//!   such as regular users sending transactions or miners participating in mining pools.
//!
//! - **Pure Scripts**: Lightweight Python scripts for monitoring, analysis, or
//!   specialized behaviors without full daemon/wallet setup.
//!
//! ## Key Components
//!
//! - `types.rs`: Common type definitions and process-related data structures
//! - `daemon.rs`: Monero daemon process configuration and generation
//! - `wallet.rs`: Wallet RPC process configuration and generation
//! - `agent_scripts.rs`: User agent script process configuration
//! - `pure_scripts.rs`: Pure script process configuration
//!
//! ## Process Scheduling
//!
//! Processes are scheduled with staggered startup times to prevent resource
//! contention and ensure proper initialization order:
//!
//! - Daemons start first (typically 1-5 seconds)
//! - Wallets start after daemons (typically 10-15 seconds)
//! - Agent scripts start last (typically 20+ seconds)
//!
//! ## Configuration Integration
//!
//! Process configurations are generated based on agent specifications in the
//! main YAML configuration. Each agent can specify:
//!
//! - Process type and executable path
//! - Command-line arguments and environment variables
//! - Resource limits (CPU, memory, network)
//! - Startup timing and dependencies
//! - Logging and output redirection
//!
//! ## Shadow Process Structure
//!
//! Each process is converted to a Shadow process definition with:
//!
//! ```yaml
//! processes:
//!   - path: "/path/to/executable"
//!     args: ["arg1", "arg2"]
//!     environment: {"VAR": "value"}
//!     start_time: "10s"
//!     expected_final_state: "running"
//! ```
//!
//! ## Resource Management
//!
//! The module handles resource allocation across processes:
//!
//! - IP address assignment for network binding
//! - Port allocation to prevent conflicts
//! - Working directory and file system setup
//! - Log file configuration and rotation
//!
//! ## Error Handling
//!
//! Process configuration includes validation for:
//!
//! - Required dependencies (wallets need daemons)
//! - Resource conflicts (duplicate ports/IPs)
//! - Configuration consistency
//! - Path and permission validation

pub mod types;
pub mod daemon;
pub mod wallet;
pub mod agent_scripts;
pub mod pure_scripts;

// Re-export commonly used functions for convenience
pub use types::ProcessType;
pub use wallet::add_wallet_process;
pub use agent_scripts::add_user_agent_process;
