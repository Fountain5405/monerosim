//! Topology type definitions.
//!
//! This file contains type definitions for different network topology
//! patterns supported by the system (Star, Mesh, Ring, DAG).


/// Re-export types from config_v2 to maintain API compatibility
pub use crate::config_v2::{Topology, PeerMode};

/// Type of network topology to generate
#[derive(Debug, Clone, PartialEq)]
pub enum TopologyType {
    /// Simple switch-based network (all nodes on single switch)
    Switch(String),
    /// Complex GML-based topology with bandwidth/latency attributes
    Gml(String),
}

impl TopologyType {
    /// Returns true if this is a GML-based topology
    pub fn is_gml(&self) -> bool {
        matches!(self, Self::Gml(_))
    }

    /// Returns the path to the GML file if this is a GML topology
    pub fn gml_path(&self) -> Option<&str> {
        match self {
            Self::Gml(path) => Some(path),
            _ => None,
        }
    }

    /// Returns the switch type if this is a switch-based topology
    pub fn switch_type(&self) -> Option<&str> {
        match self {
            Self::Switch(switch_type) => Some(switch_type),
            _ => None,
        }
    }
}
