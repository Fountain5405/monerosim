//! Network topology management, peer connections, and agent distribution.
//!
//! Supports switch-based and GML-based topologies with dynamic, hardcoded,
//! or hybrid peer discovery.

pub mod types;
pub mod connections;
pub mod distribution;

pub use types::Topology;
pub use connections::{generate_peer_connections, generate_topology_connections};
pub use distribution::distribute_agents_across_topology;
