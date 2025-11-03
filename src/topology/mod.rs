//! # Network Topology Module
//!
//! This module handles network topology management, peer connection configuration,
//! and intelligent agent distribution across different network architectures.
//! It supports both simple switch-based networks and complex GML-based topologies.
//!
//! ## Supported Topology Types
//!
//! **Switch-Based Topologies**:
//! - **1_gbit_switch**: High-performance, uniform connectivity
//! - Best for: Development, testing, performance-critical simulations
//! - Characteristics: All agents connected via high-bandwidth switch
//!
//! **GML-Based Topologies**:
//! - **Complex Internet Topologies**: AS-aware, realistic network structures
//! - **CAIDA Datasets**: Real-world autonomous system connectivity
//! - **Custom Topologies**: User-defined network graphs
//! - Best for: Research, realistic network behavior studies
//!
//! ## Peer Discovery Modes
//!
//! **Dynamic Mode**:
//! - Intelligent seed selection prioritizing miners
//! - Automatic peer discovery and connection establishment
//! - Adaptive to network changes and agent availability
//!
//! **Hardcoded Mode**:
//! - Explicit topology templates (Star, Mesh, Ring, DAG)
//! - Predictable, reproducible connection patterns
//! - Deterministic network behavior for testing
//!
//! **Hybrid Mode**:
//! - Combines GML topology with dynamic discovery elements
//! - Realistic base topology with adaptive peer selection
//! - Best for production-like simulation scenarios
//!
//! ## Topology Templates
//!
//! **Star Topology**: All agents connect to a central hub (first agent)
//! - Min agents: 2, Max agents: Unlimited
//! - Characteristics: Single point of failure, efficient routing
//!
//! **Mesh Topology**: Fully connected network (each agent connects to all others)
//! - Min agents: 2, Max agents: ~50 (performance considerations)
//! - Characteristics: Maximum connectivity, high resource usage
//!
//! **Ring Topology**: Circular connections between agents
//! - Min agents: 3, Max agents: Unlimited
//! - Characteristics: Balanced load, fault-tolerant routing
//!
//! **DAG Topology**: Blockchain-optimized directed acyclic graph
//! - Min agents: 2, Max agents: Unlimited
//! - Characteristics: Optimized for blockchain consensus
//!
//! ## Agent Distribution Strategies
//!
//! **Switch-Based Distribution**:
//! - Round-robin assignment across geographic regions
//! - Deterministic IP allocation for reproducibility
//! - Balanced continental representation
//!
//! **GML-Based Distribution**:
//! - AS-aware placement respecting autonomous system boundaries
//! - Geographic consistency within AS groups
//! - Realistic internet structure modeling
//!
//! ## Key Components
//!
//! - `types.rs`: Topology and connection type definitions
//! - `connections.rs`: Peer connection generation and management
//! - `distribution.rs`: Agent placement and distribution algorithms
//!
//! ## Configuration Integration
//!
//! Topology configuration is specified in the main YAML under the `network` section:
//!
//! ```yaml
//! network:
//!   type: "1_gbit_switch"        # or path: "topology.gml"
//!   peer_mode: "Dynamic"         # Dynamic/Hardcoded/Hybrid
//!   topology: "Mesh"             # Star/Mesh/Ring/DAG (Hardcoded mode)
//! ```
//!
//! ## Performance Considerations
//!
//! - **Switch Networks**: Near real-time performance, minimal overhead
//! - **GML Networks**: Variable performance based on topology complexity
//! - **Large Topologies**: Consider resource limits and simulation time
//! - **Mesh Topologies**: Exponential connection growth with agent count
//!
//! ## Error Handling
//!
//! Comprehensive validation for:
//!
//! - Topology file existence and format correctness
//! - Agent count compatibility with topology requirements
//! - Network connectivity and reachability
//! - Resource constraints and performance limits
//! - Configuration consistency and completeness

pub mod types;
pub mod connections;
pub mod distribution;

// Re-export key types and functions for easier access
pub use types::Topology;
pub use connections::{generate_peer_connections, generate_topology_connections};
pub use distribution::distribute_agents_across_topology;
