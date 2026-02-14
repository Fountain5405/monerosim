//! IP address allocation with geographic distribution across continents.
//!
//! Handles switch-based (round-robin) and GML-based (AS-aware) allocation.

pub mod registry;
pub mod as_manager;
pub mod allocator;

pub use registry::{AgentType, SubnetAllocation, GlobalIpRegistry};
pub use as_manager::AsSubnetManager;
pub use allocator::get_agent_ip;
