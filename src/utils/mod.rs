//! Shared utilities: duration parsing, validation, IP helpers, seed extraction.

pub mod binary;
pub mod duration;
pub mod ip_utils;
pub mod options;
pub mod script;
pub mod seed_extractor;
pub mod validation;

pub use binary::{resolve_binary_path, resolve_binary_path_for_shadow, validate_binary, validate_binary_spec, BinaryError};
pub use duration::parse_duration_to_seconds;
pub use seed_extractor::{extract_mainnet_seed_ips, SeedNode};
pub use options::{options_to_args, merge_options};
pub use validation::{validate_gml_ip_consistency, validate_topology_config, validate_mining_config, validate_agent_daemon_config, validate_ip_subnet_diversity};
