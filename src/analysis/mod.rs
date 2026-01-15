//! Transaction routing analysis for MoneroSim simulations.
//!
//! This module provides tools for analyzing transaction propagation patterns,
//! spy node vulnerabilities, and network resilience metrics.

pub mod types;
pub mod log_parser;
pub mod spy_node;
pub mod propagation;
pub mod network_resilience;
pub mod report;

pub use types::*;
pub use log_parser::parse_all_logs;
pub use spy_node::analyze_spy_vulnerability;
pub use propagation::analyze_propagation;
pub use network_resilience::analyze_resilience;
pub use report::{generate_json_report, generate_text_report};
