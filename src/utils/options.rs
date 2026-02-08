//! Option value conversion and merging utilities.

use crate::config_v2::OptionValue;
use std::collections::BTreeMap;

/// Convert OptionValue map to command-line arguments
/// - Bool(true) -> --flag
/// - Bool(false) -> (omitted)
/// - String(s) -> --flag=s
/// - Number(n) -> --flag=n
pub fn options_to_args(options: &BTreeMap<String, OptionValue>) -> Vec<String> {
    options.iter().filter_map(|(key, value)| {
        match value {
            OptionValue::Bool(true) => Some(format!("--{}", key)),
            OptionValue::Bool(false) => None,
            OptionValue::String(s) => Some(format!("--{}={}", key, s)),
            OptionValue::Number(n) => Some(format!("--{}={}", key, n)),
        }
    }).collect()
}

/// Merge two option maps, with overrides taking precedence over defaults
pub fn merge_options(
    defaults: Option<&BTreeMap<String, OptionValue>>,
    overrides: Option<&BTreeMap<String, OptionValue>>,
) -> BTreeMap<String, OptionValue> {
    let mut merged = BTreeMap::new();

    // Apply defaults first
    if let Some(defs) = defaults {
        for (k, v) in defs {
            merged.insert(k.clone(), v.clone());
        }
    }

    // Apply overrides (these take precedence)
    if let Some(ovrs) = overrides {
        for (k, v) in ovrs {
            merged.insert(k.clone(), v.clone());
        }
    }

    merged
}
