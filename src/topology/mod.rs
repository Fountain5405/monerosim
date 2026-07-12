//! Network topology management, peer connections, and agent distribution.
//!
//! Supports switch-based and GML-based topologies with dynamic, hardcoded,
//! or hybrid peer discovery.

pub mod types;
pub mod connections;
pub mod distribution;
pub mod peer_connections;

pub use types::Topology;
pub use connections::generate_topology_connections;
pub use distribution::distribute_agents_across_topology;
pub use peer_connections::{build_peer_topology, AgentEntry, PeerTopology};
