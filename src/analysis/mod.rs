//! Transaction routing analysis for MoneroSim simulations.
//!
//! This module provides tools for analyzing transaction propagation patterns,
//! spy node vulnerabilities, and network resilience metrics.

pub mod bandwidth;
pub mod dandelion;
pub mod log_parser;
pub mod network_graph;
pub mod network_resilience;
pub mod propagation;
pub mod report;
pub mod spy_node;
pub(crate) mod stats;
pub mod time_window;
pub mod tx_relay;
pub mod types;
pub mod upgrade_analysis;

pub use bandwidth::{analyze_bandwidth, bandwidth_time_series, format_bytes};
pub use dandelion::analyze_dandelion;
pub use log_parser::parse_all_logs;
pub use network_graph::{analyze_network_graph, NetworkGraphReport};
pub use network_resilience::analyze_resilience;
pub use propagation::analyze_propagation;
pub use report::{generate_json_report, generate_text_report};
pub use spy_node::analyze_spy_vulnerability;
pub use time_window::*;
pub use tx_relay::analyze_tx_relay_v2;
pub use types::*;
pub use upgrade_analysis::analyze_upgrade_impact;
