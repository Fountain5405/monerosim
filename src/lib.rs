//! Configuration generator for Monero network simulations in Shadow.
//!
//! Takes a YAML config and produces Shadow-compatible YAML, wrapper scripts,
//! and Python agent configurations.
//!
//! ## Modules
//!
//! - `config` / `config_loader`: YAML config parsing and loading
//! - `orchestrator`: High-level config generation coordination
//! - `shadow`: Shadow YAML data structures
//! - `ip`: IP address allocation with geographic distribution
//! - `topology`: Network topology (switch, GML) and peer connections
//! - `agent`: Agent config generation (miners, users, scripts)
//! - `process`: Process/wrapper script generation
//! - `analysis`: Post-simulation log analysis
//! - `utils`: Duration parsing, validation, seed extraction

use std::sync::OnceLock;

/// Config-file stem used to build the generated per-run tmp namespace (see
/// `generated_run_id`). Set once via `set_run_context`, early in `main`,
/// before any config defaults are resolved.
static CONFIG_STEM: OnceLock<String> = OnceLock::new();

/// The generated per-run id, computed once per process on first use.
static RUN_ID: OnceLock<String> = OnceLock::new();

/// Record the config-file stem for the generated per-run tmp namespace
/// (`/tmp/monerosim-<timestamp>_<stem>_<pid>`). Call once, as early as
/// possible in `main`, before `shared_dir()` / `default_daemon_data_dir()`
/// (or anything that resolves config defaults) can run. Later calls are
/// no-ops; if never called the stem falls back to `"config"`.
pub fn set_run_context(config_stem: &str) {
    let _ = CONFIG_STEM.set(config_stem.to_string());
}

/// Build (and cache) the per-process run id:
/// `<UTC YYYYMMDD_HHMMSS>_<config stem>_<pid>`.
fn generated_run_id() -> &'static str {
    RUN_ID.get_or_init(|| {
        let stem = CONFIG_STEM.get().map(|s| s.as_str()).unwrap_or("config");
        let now = chrono::Utc::now().format("%Y%m%d_%H%M%S");
        let pid = std::process::id();
        format!("{now}_{stem}_{pid}")
    })
}

/// Whether the resolved shared/daemon-data dirs came from the environment
/// (both, one, or neither) vs. our generated per-run namespace. Used for a
/// human-readable startup log line; does not affect resolution.
pub fn run_namespace_source() -> String {
    let shared_from_env = std::env::var("MONEROSIM_SHARED_DIR").is_ok();
    let daemon_from_env = std::env::var("MONEROSIM_DAEMON_DATA_DIR").is_ok();
    match (shared_from_env, daemon_from_env) {
        (true, true) => "from env (MONEROSIM_SHARED_DIR + MONEROSIM_DAEMON_DATA_DIR)".to_string(),
        (true, false) => format!(
            "shared_dir from env, daemon_data_dir generated (run id {})",
            generated_run_id()
        ),
        (false, true) => format!(
            "daemon_data_dir from env, shared_dir generated (run id {})",
            generated_run_id()
        ),
        (false, false) => format!("generated (run id {})", generated_run_id()),
    }
}

/// Shared directory for inter-agent communication and registry files.
///
/// Reads `MONEROSIM_SHARED_DIR` env var; if unset, defaults to a fresh
/// per-process namespace `/tmp/monerosim-<run id>/shared` (see
/// `generated_run_id`) rather than a fixed, shared, multi-user path.
/// Override on hardened RHEL/SUSE installs where `/tmp` may have noexec,
/// SELinux contexts, or aggressive cleanup.
pub fn shared_dir() -> String {
    std::env::var("MONEROSIM_SHARED_DIR")
        .unwrap_or_else(|_| format!("/tmp/monerosim-{}/shared", generated_run_id()))
}

/// Default base directory for per-agent monerod data directories.
///
/// Reads `MONEROSIM_DAEMON_DATA_DIR` env var; if unset, defaults to a fresh
/// per-process namespace `/tmp/monerosim-<run id>` (see `generated_run_id`)
/// rather than the bare, shared `/tmp`.
pub fn default_daemon_data_dir() -> String {
    std::env::var("MONEROSIM_DAEMON_DATA_DIR")
        .unwrap_or_else(|_| format!("/tmp/monerosim-{}", generated_run_id()))
}

#[cfg(test)]
mod run_namespace_tests {
    use super::*;
    use std::sync::Mutex;

    // std::env is process-global; serialise tests that touch these two vars.
    static ENV_LOCK: Mutex<()> = Mutex::new(());

    /// RAII guard restoring an env var's previous value on drop.
    struct EnvGuard {
        key: &'static str,
        prev: Option<String>,
    }

    impl EnvGuard {
        fn unset(key: &'static str) -> Self {
            let prev = std::env::var(key).ok();
            std::env::remove_var(key);
            Self { key, prev }
        }

        fn set(key: &'static str, value: &str) -> Self {
            let prev = std::env::var(key).ok();
            std::env::set_var(key, value);
            Self { key, prev }
        }
    }

    impl Drop for EnvGuard {
        fn drop(&mut self) {
            match &self.prev {
                Some(v) => std::env::set_var(self.key, v),
                None => std::env::remove_var(self.key),
            }
        }
    }

    #[test]
    fn generated_defaults_share_one_run_id_and_match_pattern() {
        let _lock = ENV_LOCK.lock().unwrap();
        let _shared = EnvGuard::unset("MONEROSIM_SHARED_DIR");
        let _daemon = EnvGuard::unset("MONEROSIM_DAEMON_DATA_DIR");

        let daemon_dir = default_daemon_data_dir();
        let shared = shared_dir();

        let re = regex::Regex::new(r"^/tmp/monerosim-\d{8}_\d{6}_config_\d+$").unwrap();
        assert!(
            re.is_match(&daemon_dir),
            "daemon_data_dir '{daemon_dir}' did not match expected pattern"
        );
        let re_shared =
            regex::Regex::new(r"^/tmp/monerosim-\d{8}_\d{6}_config_\d+/shared$").unwrap();
        assert!(
            re_shared.is_match(&shared),
            "shared_dir '{shared}' did not match expected pattern"
        );
        // Both must share the same generated run id.
        assert_eq!(format!("{daemon_dir}/shared"), shared);
    }

    #[test]
    fn env_vars_win_over_generated_defaults() {
        let _lock = ENV_LOCK.lock().unwrap();
        let _shared = EnvGuard::set("MONEROSIM_SHARED_DIR", "/tmp/explicit-shared");
        let _daemon = EnvGuard::set("MONEROSIM_DAEMON_DATA_DIR", "/tmp/explicit-daemon");

        assert_eq!(shared_dir(), "/tmp/explicit-shared");
        assert_eq!(default_daemon_data_dir(), "/tmp/explicit-daemon");
    }
}

/// Shadow simulation epoch: 2000-01-01 00:00:00 UTC as Unix timestamp.
/// Shadow's simulated clock starts from this point; subtract it from
/// `time.time()` (Python) or log timestamps to get simulation-relative seconds.
pub const SHADOW_EPOCH: f64 = 946_684_800.0;

/// Monero P2P port (mainnet/regtest default).
pub const MONERO_P2P_PORT: u16 = 18080;
/// Monero daemon RPC port (mainnet/regtest default).
pub const MONERO_RPC_PORT: u16 = 18081;
/// Monero wallet RPC port (mainnet/regtest default).
pub const MONERO_WALLET_RPC_PORT: u16 = 18082;

/// Default host bandwidth in bits/sec (1 Gbit/s).
pub const DEFAULT_BANDWIDTH_BPS: &str = "1000000000";
/// glibc malloc mmap threshold for memory-constrained simulation hosts.
pub const MALLOC_THRESHOLD: &str = "131072";
// MAX_CONNECTIONS_PER_IP intentionally removed: it backed an env var
// (MONERO_MAX_CONNECTIONS_PER_IP) that monerod never read, so the
// "override" was a no-op. We run at monerod's CLI default (1) instead.
// See orchestrator.rs near monero_environment population for the
// re-enable recipe (use daemon_defaults instead of an env var).
/// IP offset for miner-distributor agents to avoid collision with user agents.
pub const DISTRIBUTOR_IP_OFFSET: usize = 100;
/// IP offset for pure-script agents.
pub const SCRIPT_IP_OFFSET: usize = 200;
/// Delay (seconds) between daemon start and wallet start.
pub const WALLET_STARTUP_DELAY_SECS: u64 = 2;
/// Delay (seconds) between wallet start and agent script start.
pub const AGENT_STARTUP_DELAY_SECS: u64 = 3;
/// Max chars to preview when logging registry JSON.
pub const REGISTRY_PREVIEW_CHARS: usize = 500;
/// Monero coinbase maturity: 60 blocks at 120s each.
pub const BLOCK_MATURITY_SECONDS: u64 = 7200;

/// Mainnet fallback seed IPs hardcoded in monerod at
/// `monero-shadow/src/p2p/net_node.inl:752-758`. These are the IPs monerod
/// falls back to when DNS seeds and configured `--seed-node` peers fail.
/// In-sim hosts pinned to these IPs let the fallback path resolve inside
/// the simulation instead of hitting Shadow's "no host exists" warning.
///
/// **This is a fallback default.** At runtime, `prepare_fallback_seeds`
/// (driven by `general.fallback_seeds`) extracts the live list from the
/// Monero source tree (`<repo>/sibling_repos/monero-shadow/src/p2p/net_node.inl`
/// or sibling layouts; override with `MONERO_SRC_DIR`). This baked-in
/// list is only used if the source isn't reachable on disk.
pub const MONERO_FALLBACK_SEED_IPS: [&str; 6] = [
    "176.9.0.187",
    "88.198.163.90",
    "192.99.8.110",
    "37.187.74.171",
    "88.99.195.15",
    "5.104.84.64",
];

/// Generate the agent ID for the Nth fallback seed (1-indexed).
/// `seed_index = 1` → `"monero-seed-001"`.
pub fn fallback_seed_agent_id(seed_index: usize) -> String {
    format!("monero-seed-{:03}", seed_index)
}

pub mod agent;
pub mod analysis;
pub mod config;
pub mod config_loader;
pub mod gml_parser;
pub mod ip;
pub mod orchestrator;
pub mod process;
pub mod shadow;
pub mod topology;
pub mod utils;
