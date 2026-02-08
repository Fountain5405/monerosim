//! # Shadow Simulator Configuration Module
//!
//! This module provides comprehensive functionality for generating Shadow network
//! simulator configuration files, serving as the bridge between Monerosim's
//! high-level agent specifications and Shadow's low-level execution environment.
//!
//! ## Core Functionality
//!
//! The module transforms Monerosim configurations into Shadow YAML format,
//! handling the complex mapping from agent behaviors to simulator processes,
//! network topologies, and execution parameters.
//!
//! ## Key Components
//!
//! - `types.rs`: Core Shadow data structures and type definitions
//! - `network.rs`: Network topology translation to Shadow format
//! - `process.rs`: Process configuration generation for Shadow execution
//!
//! ## Shadow Configuration Structure
//!
//! Shadow configurations consist of several key sections:
//!
//! - **General**: Simulation-wide settings (duration, logging, randomness)
//! - **Network**: Topology definition (switch or GML-based)
//! - **Hosts**: Individual host configurations with IP addresses
//! - **Processes**: Executable definitions with arguments and scheduling
//!
//! ## Data Flow
//!
//! 1. **Input Processing**: Receive validated Monerosim configuration
//! 2. **Structure Mapping**: Convert agents to Shadow hosts and processes
//! 3. **Network Translation**: Transform topology to Shadow network format
//! 4. **Serialization**: Generate YAML configuration for Shadow execution
//!
//! ## Process Generation
//!
//! Each Monerosim agent becomes one or more Shadow processes:
//!
//! - **Daemon Process**: `monerod` with P2P and RPC configuration
//! - **Wallet Process**: `monero-wallet-rpc` for miners and users
//! - **Agent Scripts**: Python agents with custom behaviors
//! - **Monitoring Scripts**: Analysis and logging utilities
//!
//! ## Network Integration
//!
//! The module integrates with network topology specifications:
//!
//! - **Switch Networks**: Simple, high-performance connectivity
//! - **GML Networks**: Complex, realistic internet topologies
//! - **Peer Discovery**: Dynamic, hardcoded, or hybrid connection modes
//!
//! ## Configuration Validation
//!
//! Ensures generated Shadow configurations are:
//!
//! - **Syntactically Correct**: Valid YAML structure
//! - **Semantically Sound**: Proper process dependencies and timing
//! - **Resource Balanced**: Appropriate resource allocation
//! - **Execution Ready**: All required files and paths specified
//!
//! ## Example Generated Structure
//!
//! ```yaml
//! general:
//!   stop_time: "3h"
//!   log_level: "info"
//!
//! network:
//!   type: "1_gbit_switch"
//!
//! hosts:
//!   node000:
//!     ip_address: "10.0.0.1"
//!     processes:
//!       - path: "/path/to/monerod"
//!         args: ["--p2p-bind-ip", "10.0.0.1"]
//!         start_time: "1s"
//! ```
//!
//! ## Error Handling
//!
//! Comprehensive error handling for configuration generation:
//!
//! - Invalid agent specifications
//! - Network topology inconsistencies
//! - Resource allocation conflicts
//! - Path and dependency validation
//! - Shadow compatibility issues

pub mod types;

// Re-export commonly used types for convenience
pub use types::{
    // Registry types
    MinerInfo,
    MinerRegistry,
    AgentInfo,
    AgentRegistry,
    PublicNodeInfo,
    PublicNodeRegistry,
    // Shadow configuration types
    ShadowConfig,
    ShadowGeneral,
    ShadowExperimental,
    ShadowNetwork,
    ShadowGraph,
    ShadowFileSource,
    ShadowNetworkNode,
    ShadowNetworkEdge,
    ShadowHost,
    ShadowProcess,
    ExpectedFinalState,
};