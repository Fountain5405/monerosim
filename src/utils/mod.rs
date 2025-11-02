//! Utility functions module.
//!
//! This module provides utility functions for duration parsing,
//! validation, and other common operations.

pub mod duration;
pub mod ip_utils;
pub mod validation;

// Re-export commonly used utility functions
pub use duration::parse_duration_to_seconds;
pub use validation::{validate_gml_ip_consistency, validate_topology_config};
