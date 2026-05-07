//! Option value conversion and merging utilities.

use crate::config::OptionValue;
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
/// - String(s) -> --flag=s   (literal value; no shell quoting)
/// - Number(n) -> --flag=n
///
/// Each returned string is one argv element. Daemon and wallet processes
/// are launched directly via Shadow (`ProcessArgs::List`), so values pass
/// straight to execve and never see a shell. Glob/word-split concerns
/// only matter when the joined form is later fed back through a shell —
/// see `shell_quote_args` for that path (currently the `WALLET_RPC_CMD`
/// env var consumed by `restart_wallet_rpc()` via `subprocess.Popen(..., shell=True)`).
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

/// Join argv-style elements into a single shell command string, quoting
/// each element so the shell will reproduce it verbatim. Use this when
/// you need to ferry a command through `shell=True` or `bash -c '...'`
/// (e.g. `WALLET_RPC_CMD`); for direct Shadow process launches, prefer
/// passing the `Vec<String>` itself as `ProcessArgs::List`.
pub fn shell_quote_args(args: &[String]) -> String {
    args.iter().map(|a| shell_quote(a)).collect::<Vec<_>>().join(" ")
}

/// POSIX-shell-quote a single argument: wrap in single quotes, escaping
/// any embedded single quotes with the standard `'\''` dance. Always
/// quotes — the cost is two extra bytes; the upside is unconditional
/// safety regardless of metacharacters.
fn shell_quote(arg: &str) -> String {
    if arg.contains('\'') {
        format!("'{}'", arg.replace('\'', r"'\''"))
    } else {
        format!("'{}'", arg)
    }
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
