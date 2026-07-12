//! Topology type definitions.
//!
//! This file contains type definitions for different network topology
//! patterns supported by the system (Star, Mesh, Ring, DAG).

/// Re-export types from config to maintain API compatibility
pub use crate::config::{PeerMode, Topology};
