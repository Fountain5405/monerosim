//! Option value conversion and merging utilities.

use crate::config_v2::OptionValue;
use std::collections::BTreeMap;

/// monerod `--log-level` category string that silences the bulk of the
/// per-host stdout while preserving everything the live monitor
/// (`agents/simulation_monitor.py`) and post-run analyzer
/// (`src/analysis/log_parser.rs`) parse:
///
/// - `blockchain:INFO` keeps "+++++ BLOCK SUCCESSFULLY ADDED" + height/PoW/id lines.
/// - `txpool:INFO` keeps "Transaction added to pool: txid <HASH>".
/// - `net.p2p.msg:INFO` keeps "Received NOTIFY_NEW_FLUFFY_BLOCK",
///   "Received NOTIFY_NEW_TRANSACTIONS", "Including transaction <HASH>".
/// - `daemon.rpc:INFO` keeps the RPC_TRACKER lines that include
///   "generateblocks" (used by the monitor to disambiguate
///   locally-mined vs network-received blocks).
/// - Everything else (notably `net.cn`, `verify`, `serialization`, `perf.*`)
///   is suppressed via the `*:WARNING` wildcard plus explicit `:FATAL`
///   overrides where the wildcard isn't aggressive enough.
const MONITOR_LOG_CATEGORIES: &str = "*:WARNING,blockchain:INFO,txpool:INFO,net.p2p.msg:INFO,daemon.rpc:INFO,global:INFO,stacktrace:INFO,logging:INFO,msgwriter:INFO,verify:FATAL,serialization:FATAL,perf.*:FATAL";

/// Translate symbolic monerod `log-level` values into the equivalent
/// `--log-level` category string. Pass-through for numeric or already-
/// formatted category strings. Mutates the map in place.
///
/// Currently supports `monitor` (see `MONITOR_LOG_CATEGORIES`). Wallet
/// RPC uses different categories — call `translate_wallet_log_level`
/// for wallet options instead.
pub fn translate_daemon_log_level(opts: &mut BTreeMap<String, OptionValue>) {
    let translated = match opts.get("log-level") {
        Some(OptionValue::String(s)) if s == "monitor" => Some(MONITOR_LOG_CATEGORIES),
        _ => None,
    };
    if let Some(cat_string) = translated {
        opts.insert("log-level".to_string(), OptionValue::String(cat_string.to_string()));
    }
}

/// Coerce monerod-only symbolic log-level values into something
/// monero-wallet-rpc can use. If the user sets `log-level: monitor`
/// on wallet_defaults, the intent is "be quiet" — map to wallet level
/// `0` (WARNING). Numeric or unrecognized strings pass through.
pub fn translate_wallet_log_level(opts: &mut BTreeMap<String, OptionValue>) {
    let coerce = matches!(
        opts.get("log-level"),
        Some(OptionValue::String(s)) if s == "monitor"
    );
    if coerce {
        opts.insert("log-level".to_string(), OptionValue::Number(0));
    }
}

/// Convert OptionValue map to command-line arguments
/// - Bool(true) -> --flag
/// - Bool(false) -> (omitted)
/// - String(s) -> --flag="s"  (always double-quoted; see note below)
/// - Number(n) -> --flag=n
///
/// String values are always double-quoted because callers (notably
/// `agent/user_agents.rs`) wrap the joined args in `bash -c 'exec <bin>
/// <args>'`. Bash re-tokenizes the inside of the `-c` and would expand
/// shell metacharacters (`*`, `?`, `~`, etc.) in unquoted values
/// against the working directory before invoking the binary. The
/// double quotes suppress that. In practice this matters for the
/// `log-level` category-string passthrough (e.g.
/// `"*:WARNING,blockchain:INFO"`); no real value contains a literal
/// `"`, so naive quoting is sufficient.
pub fn options_to_args(options: &BTreeMap<String, OptionValue>) -> Vec<String> {
    options.iter().filter_map(|(key, value)| {
        match value {
            OptionValue::Bool(true) => Some(format!("--{}", key)),
            OptionValue::Bool(false) => None,
            OptionValue::String(s) => Some(format!("--{}=\"{}\"", key, s)),
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
