//! Shared utilities: duration parsing, validation, IP helpers, seed extraction.

pub mod binary;
pub mod duration;
pub mod options;
pub mod script;
pub mod seed_extractor;
pub mod validation;

pub use binary::{resolve_binary_path, resolve_binary_path_for_shadow, BinaryError};
pub use duration::parse_duration_to_seconds;
pub use options::{
    merge_options, options_to_args, translate_daemon_log_level, translate_wallet_log_level,
};
pub use seed_extractor::{extract_mainnet_seed_ips_from_repo, SeedNode};
pub use validation::{
    validate_agent_daemon_config, validate_gml_ip_consistency, validate_ip_subnet_diversity,
    validate_mining_config, validate_topology_config,
};
