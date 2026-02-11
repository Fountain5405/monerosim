//! Transaction routing analysis for MoneroSim simulations.
//!
//! This module provides tools for analyzing transaction propagation patterns,
//! spy node vulnerabilities, and network resilience metrics.

pub mod types;
pub mod log_parser;
pub mod spy_node;
pub mod propagation;
pub mod network_resilience;
pub mod network_graph;
pub mod report;
pub mod tx_relay_v2;
pub mod dandelion;
pub mod time_window;
pub mod upgrade_analysis;
pub mod bandwidth;

pub use types::*;
pub use log_parser::parse_all_logs;
pub use spy_node::analyze_spy_vulnerability;
pub use propagation::analyze_propagation;
pub use network_resilience::analyze_resilience;
pub use network_graph::{analyze_network_graph, NetworkGraphReport};
pub use report::{generate_json_report, generate_text_report};
pub use tx_relay_v2::analyze_tx_relay_v2;
pub use dandelion::analyze_dandelion;
pub use time_window::*;
pub use upgrade_analysis::analyze_upgrade_impact;
pub use bandwidth::{analyze_bandwidth, bandwidth_time_series, format_bytes};

/// Calculate Gini coefficient for a slice of values.
///
/// Returns 0.0 for empty slices or when all values are zero.
/// Result ranges from 0.0 (perfect equality) to 1.0 (maximum inequality).
pub(crate) fn calculate_gini(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }

    let n = values.len() as f64;
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let sum: f64 = sorted.iter().sum();
    if sum == 0.0 {
        return 0.0;
    }

    let mut gini_sum = 0.0;
    for (i, &val) in sorted.iter().enumerate() {
        gini_sum += val * (2.0 * (i as f64 + 1.0) - n - 1.0);
    }

    gini_sum / (n * sum)
}
