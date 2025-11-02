//! IP address allocation and management module.
//!
//! This module handles IP address allocation for agents in the simulation,
//! including geographic distribution across continents and AS-aware placement
//! for GML-based network topologies.

pub mod registry;
pub mod as_manager;
pub mod allocator;

// Re-export commonly used types
pub use registry::{AgentType, SubnetAllocation, GlobalIpRegistry};
pub use as_manager::AsSubnetManager;
pub use allocator::get_agent_ip;