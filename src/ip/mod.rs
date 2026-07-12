//! IP address allocation with geographic distribution across continents.
//!
//! Handles switch-based (round-robin) and GML-based (AS-aware) allocation.

pub mod allocator;
pub mod as_manager;
pub mod registry;

pub use allocator::get_agent_ip;
pub use as_manager::AsSubnetManager;
pub use registry::{AgentType, GlobalIpRegistry};
