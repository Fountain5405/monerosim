//! # Registry Generation Module
//!
//! This module handles the generation and management of JSON registry files
//! that enable coordination and communication between agents during simulation.
//! Registries serve as the central coordination mechanism for distributed
//! agent behaviors.
//!
//! ## Registry Types
//!
//! **Agent Registry** (`agent_registry.json`):
//! - Comprehensive listing of all agents in the simulation
//! - IP addresses, ports, and network configuration
//! - Agent attributes and capabilities (miner status, hashrate, etc.)
//! - Runtime state and coordination data
//!
//! **Miner Registry** (`miners.json`):
//! - Specialized registry for mining participants
//! - Hashrate distribution and mining power allocation
//! - Mining strategy coordination data
//! - Reward distribution parameters
//!
//! ## Key Components
//!
//! - `agent_registry.rs`: Agent registry generation and management
//! - `miner_registry.rs`: Miner-specific registry handling
//!
//! ## Registry Generation Process
//!
//! 1. **Collection Phase**: Gather agent configurations and attributes
//! 2. **Validation Phase**: Ensure consistency and completeness
//! 3. **Serialization Phase**: Convert to JSON format for inter-process communication
//! 4. **Distribution Phase**: Make available to all simulation processes
//!
//! ## File Locations
//!
//! Registries are stored in the shared state directory:
//! ```text
//! /tmp/monerosim_shared/
//! |-- agent_registry.json    # All agents and their attributes
//! \-- miners.json           # Mining-specific coordination data
//! ```
//!
//! ## Usage in Agents
//!
//! Python agents read these registries to:
//!
//! - Discover other agents in the network
//! - Coordinate mining activities
//! - Route transactions appropriately
//! - Implement distributed behaviors
//!
//! ## Example Registry Structure
//!
//! ```json
//! {
//!   "agents": [
//!     {
//!       "id": "node000",
//!       "ip": "10.0.0.1",
//!       "port": 18080,
//!       "is_miner": true,
//!       "hashrate": 25
//!     }
//!   ],
//!   "miners": [
//!     {
//!       "id": "node000",
//!       "hashrate_percent": 25,
//!       "can_receive_distributions": true
//!     }
//!   ]
//! }
//! ```
//!
//! ## Coordination Patterns
//!
//! Registries enable several coordination patterns:
//!
//! - **Dynamic Discovery**: Agents find each other at runtime
//! - **Load Balancing**: Distribute work across capable agents
//! - **Consensus Coordination**: Coordinate blockchain activities
//! - **State Synchronization**: Share simulation state between processes
//!
//! ## Error Handling
//!
//! The module provides robust error handling for:
//!
//! - Registry file I/O operations
//! - JSON serialization/deserialization
//! - Data consistency validation
//! - Concurrent access coordination

