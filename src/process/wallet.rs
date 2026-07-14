//! Monero wallet RPC process configuration.
//!
//! This file handles generation of Shadow process configurations
//! for monero-wallet-rpc instances.

use crate::config::OptionValue;
use crate::shadow::{ProcessArgs, ShadowProcess};
use crate::utils::options::{
    merge_options, options_to_args, shell_quote_args, translate_wallet_log_level,
};
use std::collections::BTreeMap;

/// Build wallet command-line arguments common to both local and remote daemon modes.
///
/// Single source of truth for the wallet-rpc argument list: used by
/// `add_wallet_process` (simple wallets) and by the phase-based wallet path in
/// `agent::user_agents` (upgrade scenarios). The only things that differ between
/// call sites are parameterized here — `daemon_address`, ports, wallet/ringdb
/// dir (derived from `shared_dir` + `agent_id`), and the phase-specific
/// `custom_args`.
///
/// Returns argv-style strings (one element per arg); join later if a shell
/// string is needed (see `shell_quote_args`).
pub fn build_wallet_args(
    agent_id: &str,
    agent_ip: &str,
    daemon_address: &str,
    wallet_rpc_port: u16,
    _environment: &BTreeMap<String, String>,
    custom_args: Option<&Vec<String>>,
    wallet_defaults: Option<&BTreeMap<String, OptionValue>>,
    wallet_options: Option<&BTreeMap<String, OptionValue>>,
    shared_dir: &str,
) -> Vec<String> {
    let mut merged_wallet_options = merge_options(wallet_defaults, wallet_options);
    translate_wallet_log_level(&mut merged_wallet_options);

    let mut args = vec![
        format!("--daemon-address={}", daemon_address),
        format!("--rpc-bind-port={}", wallet_rpc_port),
        format!("--rpc-bind-ip={}", agent_ip),
        "--disable-rpc-login".to_string(),
        "--trusted-daemon".to_string(),
        format!("--wallet-dir={}/{}_wallet", shared_dir, agent_id),
        format!("--shared-ringdb-dir={}/{}_ringdb", shared_dir, agent_id),
        "--confirm-external-bind".to_string(),
        "--allow-mismatched-daemon-version".to_string(),
    ];

    // Note: we intentionally do NOT set --max-concurrency on wallet-rpc.
    // With limited threads (e.g., 2), wallet-rpc's background refresh can
    // deadlock against an in-flight transfer when both need the wallet lock
    // and compete for the same threads. Letting wallet-rpc use its default
    // (all cores) reduces the frequency but does not fully eliminate it
    // under Shadow's cooperative scheduling — non-final wallet phases use
    // shutdown_signal: SIGKILL to recover. See docs/UPGRADE_WALLET_SIGKILL.md.
    // process_threads is still applied to monerod (see daemon.rs).

    args.extend(options_to_args(&merged_wallet_options));
    args.push("--daemon-ssl-allow-any-cert".to_string());

    if let Some(custom) = custom_args {
        args.extend(custom.iter().cloned());
    }

    args
}

/// Format a daemon URL for a wallet's `--daemon-address` flag.
///
/// `Local { agent_ip, daemon_rpc_port }` → `http://ip:port` (same-host daemon).
/// `Remote(None)` or `Remote(Some("auto"))` → localhost placeholder; the
/// Python agent calls `set_daemon()` at runtime to connect to a discovered
/// public node.
/// `Remote(Some(addr))` for an explicit address → `http://addr`.
pub enum DaemonAddress<'a> {
    Local {
        agent_ip: &'a str,
        daemon_rpc_port: u16,
    },
    Remote(Option<&'a str>),
}

impl DaemonAddress<'_> {
    pub fn format(&self) -> String {
        match self {
            DaemonAddress::Local {
                agent_ip,
                daemon_rpc_port,
            } => {
                format!("http://{}:{}", agent_ip, daemon_rpc_port)
            }
            DaemonAddress::Remote(Some(addr)) if *addr != "auto" => {
                format!("http://{}", addr)
            }
            DaemonAddress::Remote(_) => {
                format!("http://127.0.0.1:{}", crate::MONERO_RPC_PORT)
            }
        }
    }
}

/// Arguments for `add_wallet_process`.
pub struct WalletProcessArgs<'a> {
    pub processes: &'a mut Vec<ShadowProcess>,
    pub agent_id: &'a str,
    pub agent_ip: &'a str,
    pub daemon: DaemonAddress<'a>,
    pub wallet_rpc_port: u16,
    pub wallet_binary_path: &'a str,
    pub environment: &'a BTreeMap<String, String>,
    pub wallet_start_time: &'a str,
    pub custom_args: Option<&'a Vec<String>>,
    pub custom_env: Option<&'a BTreeMap<String, String>>,
    pub wallet_defaults: Option<&'a BTreeMap<String, OptionValue>>,
    pub wallet_options: Option<&'a BTreeMap<String, OptionValue>>,
    pub shared_dir: &'a str,
}

/// Add a wallet process pointing at the given daemon address.
pub fn add_wallet_process(args: WalletProcessArgs<'_>) -> String {
    let daemon_address = args.daemon.format();
    let wallet_args = build_wallet_args(
        args.agent_id,
        args.agent_ip,
        &daemon_address,
        args.wallet_rpc_port,
        args.environment,
        args.custom_args,
        args.wallet_defaults,
        args.wallet_options,
        args.shared_dir,
    );

    // Shell-quoted command string for the WALLET_RPC_CMD env var consumed
    // by `restart_wallet_rpc()` in agents/base_agent.py (which runs it via
    // `subprocess.Popen(..., shell=True)`). The Shadow process itself is
    // launched directly (no shell), using ProcessArgs::List(wallet_args).
    let wallet_cmd = format!(
        "{} {}",
        shell_quote_args(&[args.wallet_binary_path.to_string()]),
        shell_quote_args(&wallet_args),
    );

    let mut wallet_env = args.environment.clone();
    if let Some(env) = args.custom_env {
        for (key, value) in env {
            wallet_env.insert(key.clone(), value.clone());
        }
    }

    args.processes.push(ShadowProcess {
        path: args.wallet_binary_path.to_string(),
        args: ProcessArgs::List(wallet_args),
        environment: wallet_env,
        start_time: args.wallet_start_time.to_string(),
        shutdown_time: None,
        shutdown_signal: None,
        expected_final_state: Some(crate::shadow::ExpectedFinalState::Running),
    });

    wallet_cmd
}
