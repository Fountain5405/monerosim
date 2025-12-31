//! # Utility Functions Module
//!
//! This module provides shared utility functions and helpers used across
//! the Monerosim codebase for common operations like duration parsing,
//! validation, IP utilities, and configuration processing.
//!
//! ## Core Utilities
//!
//! **Duration Parsing** (`duration.rs`):
//! - Parse human-readable duration strings ("1h", "30m", "45s")
//! - Convert between different time units
//! - Validate duration specifications
//!
//! **IP Utilities** (`ip_utils.rs`):
//! - IP address manipulation and validation
//! - Subnet calculations and range checking
//! - Network address operations
//!
//! **Validation** (`validation.rs`):
//! - Configuration validation and consistency checks
//! - GML topology validation
//! - IP allocation conflict detection
//! - Agent configuration verification
//!
//! ## Usage Patterns
//!
//! These utilities are designed to be:
//!
//! - **Pure Functions**: No side effects, deterministic behavior
//! - **Composable**: Easy to combine for complex operations
//! - **Well-Tested**: Comprehensive test coverage for reliability
//! - **Performance-Oriented**: Optimized for simulation workloads
//!
//! ## Error Handling
//!
//! Utilities follow consistent error handling patterns:
//!
//! - Return `Result<T, E>` for operations that can fail
//! - Use custom error types for specific failure modes
//! - Provide descriptive error messages for debugging
//! - Validate inputs early to prevent downstream issues
//!
//! ## Performance Considerations
//!
//! Utilities are optimized for:
//!
//! - **Memory Efficiency**: Minimal allocations in hot paths
//! - **CPU Efficiency**: Fast operations for large-scale simulations
//! - **Scalability**: Linear performance with input size
//! - **Thread Safety**: Safe for concurrent access where needed
//!
//! ## Testing
//!
//! Each utility module includes comprehensive tests covering:
//!
//! - Normal operation scenarios
//! - Edge cases and boundary conditions
//! - Error conditions and failure modes
//! - Performance characteristics
//! - Integration with other modules

pub mod duration;
pub mod ip_utils;
pub mod seed_extractor;
pub mod validation;

// Re-export commonly used utility functions
pub use duration::parse_duration_to_seconds;
pub use seed_extractor::{extract_mainnet_seed_ips, SeedNode};
pub use validation::{validate_gml_ip_consistency, validate_topology_config, validate_mining_config, validate_simulation_seed};
