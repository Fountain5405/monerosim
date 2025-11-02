//! Shadow simulator configuration module.
//!
//! This module provides functionality for generating Shadow network simulator
//! configuration files. It handles the creation of Shadow YAML structures,
//! network definitions, and host configurations for Monero network simulations.

pub mod types;
pub mod network;
pub mod process;

// Re-export commonly used types for convenience
pub use types::{
    // Registry types
    MinerInfo,
    MinerRegistry,
    AgentInfo,
    AgentRegistry,
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
};