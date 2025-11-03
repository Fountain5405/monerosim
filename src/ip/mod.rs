//! # IP Address Allocation and Management Module
//!
//! This module provides comprehensive IP address management for Monerosim
//! network simulations, ensuring realistic geographic distribution and
//! preventing address conflicts across agents.
//!
//! ## Geographic Distribution
//!
//! IP addresses are allocated across 6 continents to simulate global network
//! distribution:
//!
//! - **North America**: 10.0.0.0/8 range
//! - **Europe**: 172.16.0.0/12 range
//! - **Asia**: 203.0.0.0/8 range
//! - **South America**: 200.0.0.0/8 range
//! - **Africa**: 197.0.0.0/8 range
//! - **Oceania**: 202.0.0.0/8 range
//!
//! ## Key Components
//!
//! - `allocator.rs`: Core IP allocation logic with geographic distribution
//! - `as_manager.rs`: AS-aware IP placement for GML topologies
//! - `registry.rs`: Global IP registry tracking and conflict prevention
//!
//! ## Allocation Strategy
//!
//! **Switch-Based Networks**:
//! - Round-robin distribution across continents
//! - Deterministic assignment based on agent index
//! - Ensures balanced geographic representation
//!
//! **GML-Based Networks**:
//! - AS-aware placement using topology information
//! - Respects autonomous system boundaries
//! - Maintains geographic consistency within AS groups
//!
//! ## IP Registry System
//!
//! The global IP registry prevents conflicts by:
//!
//! - Tracking all allocated IP addresses
//! - Validating uniqueness before assignment
//! - Supporting both IPv4 and IPv6 (future extension)
//! - Providing lookup capabilities for debugging
//!
//! ## Configuration Integration
//!
//! IP allocation is transparent to users - addresses are automatically
//! assigned based on network topology and agent requirements. The system
//! ensures:
//!
//! - No IP conflicts across all agents
//! - Realistic geographic distribution
//! - Deterministic assignment for reproducibility
//! - Scalability to hundreds of agents
//!
//! ## Example Allocation
//!
//! ```rust
//! // Agent 0: North America - 10.0.0.1
//! // Agent 1: Europe - 172.16.0.1
//! // Agent 2: Asia - 203.0.0.1
//! // Agent 3: South America - 200.0.0.1
//! // Agent 4: Africa - 197.0.0.1
//! // Agent 5: Oceania - 202.0.0.1
//! // Agent 6: North America - 10.0.0.2
//! ```
//!
//! ## Error Handling
//!
//! The module provides robust error handling for:
//!
//! - IP address exhaustion in subnets
//! - Registry conflicts (should not occur)
//! - Invalid geographic assignments
//! - Topology inconsistencies

pub mod registry;
pub mod as_manager;
pub mod allocator;

// Re-export commonly used types
pub use registry::{AgentType, SubnetAllocation, GlobalIpRegistry};
pub use as_manager::AsSubnetManager;
pub use allocator::get_agent_ip;