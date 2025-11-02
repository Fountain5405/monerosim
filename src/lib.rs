//! # Monerosim - Configuration utility for Monero network simulations in Shadow
//!
//! This library provides core functionality for generating Shadow network
//! simulator configurations for Monero cryptocurrency network simulations.
//!
//! ## Overview
//!
//! Monerosim enables controlled, reproducible Monero network research and testing
//! without deploying real infrastructure. It generates configuration files that
//! coordinate autonomous agents running within the Shadow network simulator.
//!
//! ## Key Features
//!
//! - **Scalable Simulations**: Support for 2-40+ Monero nodes on a single machine
//! - **Agent Framework**: Autonomous miners, users, and network participants
//! - **Network Topologies**: Switch-based (simple) or GML-based (realistic internet-like)
//! - **Geographic Distribution**: Automatic IP allocation across 6 continents
//! - **Peer Discovery**: Dynamic, Hardcoded, or Hybrid connection modes
//! - **Reproducible**: Deterministic simulations for scientific research
//!
//! ## Architecture
//!
//! The library is organized into several modules:
//!
//! - `config_v2`: Type-safe configuration structures and YAML parsing
//! - `config_loader`: Configuration file loading and migration
//! - `shadow_agents`: Agent processing functions for Shadow configuration
//! - `gml_parser`: GML graph parser for complex network topologies
//! - `shadow`: Shadow data structures and serialization
//! - `ip`: IP address allocation and management
//! - `topology`: Network topology generation and management
//! - `agent`: Agent configuration and lifecycle management
//! - `process`: Process configuration generation
//! - `registry`: Agent and miner registry management
//! - `utils`: Utility functions and helpers
//! - `orchestrator`: High-level orchestration of configuration generation
//!
//! ## Example Usage
//!
//! ```rust,no_run
//! use monerosim::{config_loader, orchestrator};
//!
//! // Load configuration from YAML file
//! let config = config_loader::load_config("config.yaml")?;
//!
//! // Generate Shadow configuration
//! let shadow_config = orchestrator::generate_shadow_config(&config, "shadow_output")?;
//!
//! // The shadow_output directory now contains:
//! // - shadow_agents.yaml: Shadow simulator configuration
//! // - agent_registry.json: Agent information
//! // - miners.json: Mining configuration
//! # Ok::<(), Box<dyn std::error::Error>>(())
//! ```
//!
//! ## Configuration Format
//!
//! Configurations use YAML format with a unified agent-based model:
//!
//! ```yaml
//! general:
//!   stop_time: "3h"
//!   fresh_blockchain: true
//!   log_level: info
//!
//! network:
//!   type: "1_gbit_switch"  # or path: "topology.gml"
//!   peer_mode: "Dynamic"   # Dynamic/Hardcoded/Hybrid
//!   topology: "Mesh"       # Star/Mesh/Ring/DAG
//!
//! agents:
//!   user_agents:
//!     - daemon: "monerod"
//!       wallet: "monero-wallet-rpc"
//!       attributes:
//!         is_miner: true
//!         hashrate: "25"
//!   block_controller:
//!     script: "agents.block_controller"
//! ```
//!
//! ## Simulation Execution
//!
//! Generated configurations are executed using the Shadow network simulator:
//!
//! ```bash
//! # Run the simulation
//! shadow shadow_output/shadow_agents.yaml
//!
//! # Analyze results
//! python scripts/log_processor.py
//! ```
//!
//! ## Error Handling
//!
//! The library uses `color_eyre` for comprehensive error reporting with context.
//! All public functions return `Result<T, color_eyre::eyre::Error>` for consistent
//! error handling throughout the application.

// Existing modules
pub mod config_v2;
pub mod config_loader;
pub mod shadow_agents;
pub mod gml_parser;

// New modular components - Phase 1 scaffolding
pub mod shadow;
pub mod ip;
pub mod topology;
pub mod agent;
pub mod process;
pub mod registry;
pub mod utils;
pub mod orchestrator;