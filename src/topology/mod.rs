//! Network topology module.
//!
//! This module contains functionality for managing network topologies,
//! peer connections, and agent distribution across topologies.

pub mod types;
pub mod connections;
pub mod distribution;

// Re-export key types and functions for easier access
pub use types::Topology;
pub use connections::{generate_peer_connections, generate_topology_connections};
pub use distribution::distribute_agents_across_topology;
