//! # Agent Configuration Module
//!
//! This module handles the configuration, processing, and lifecycle management
//! of different agent types within Monerosim simulations. It provides a unified
//! interface for managing autonomous network participants that interact with
//! the Monero blockchain.
//!
//! ## Agent Types
//!
//! The module supports several categories of agents:
//!
//! - **User Agents**: Regular Monero network participants that can mine, transact,
//!   and interact with the blockchain. These include both miners (with wallets)
//!   and regular users (with transaction behaviors). Miners use autonomous mining
//!   via the `mining_script` attribute.
//!
//! - **Miner Distributor**: Handles reward distribution logic for mining pools
//!   and coordinated mining efforts.
//!
//! - **Pure Script Agents**: Lightweight agents that run custom Python scripts
//!   for monitoring, analysis, or specialized behaviors without full daemon/wallet setup.
//!
//! - **Simulation Monitor**: Real-time monitoring and logging agent for
//!   simulation analytics and debugging.
//!
//! ## Key Components
//!
//! - `user_agents.rs`: Processing logic for user agents (miners and regular users)
//! - `miner_distributor.rs`: Mining reward distribution logic
//! - `pure_scripts.rs`: Pure script agent processing
//! - `simulation_monitor.rs`: Simulation monitoring functionality
//! - `types.rs`: Common type definitions and data structures
//! - `lifecycle.rs`: Agent lifecycle management and state transitions
//!
//! ## Configuration Integration
//!
//! Agents are configured through the main YAML configuration file under the
//! `agents` section, with support for:
//!
//! - Dynamic agent attributes and behaviors
//! - Geographic IP distribution
//! - Process scheduling and startup timing
//! - Resource allocation and constraints
//!
//! ## Example Usage
//!
//! ```yaml
//! agents:
//!   user_agents:
//!     - daemon: "monerod"
//!       wallet: "monero-wallet-rpc"
//!       mining_script: "agents.autonomous_miner"
//!       attributes:
//!         is_miner: true
//!         hashrate: "50"
//! ```
//!
//! ## Processing Flow
//!
//! 1. Configuration parsing and validation
//! 2. Agent type determination and attribute processing
//! 3. IP address allocation with geographic distribution
//! 4. Process configuration generation (daemons, wallets, scripts)
//! 5. Shadow YAML structure creation
//! 6. Registry generation for inter-agent coordination

pub mod types;
pub mod user_agents;
pub mod miner_distributor;
pub mod pure_scripts;
pub mod simulation_monitor;

// Re-export the main processing functions for easy access
pub use user_agents::process_user_agents;
pub use miner_distributor::process_miner_distributor;
pub use pure_scripts::process_pure_script_agents;
pub use simulation_monitor::process_simulation_monitor;
