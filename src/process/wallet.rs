//! Monero wallet RPC process configuration.
//!
//! This file handles generation of Shadow process configurations
//! for monero-wallet-rpc instances.

use crate::config_v2::OptionValue;
use crate::shadow::{ShadowProcess, ProcessArgs};
use crate::utils::options::{options_to_args, merge_options, shell_quote_args, translate_wallet_log_level};
use std::collections::BTreeMap;

/// Build wallet command-line arguments common to both local and remote daemon modes.
///
/// Returns argv-style strings (one element per arg); join later if a shell
/// string is needed (see `shell_quote_args`).
fn build_wallet_args(
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
    Local { agent_ip: &'a str, daemon_rpc_port: u16 },
    Remote(Option<&'a str>),
}

impl DaemonAddress<'_> {
    fn format(&self) -> String {
        match self {
            DaemonAddress::Local { agent_ip, daemon_rpc_port } => {
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

/// Add a wallet process pointing at the given daemon address.
pub fn add_wallet_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    daemon: DaemonAddress<'_>,
    wallet_rpc_port: u16,
    wallet_binary_path: &str,
    environment: &BTreeMap<String, String>,
    _index: usize,
    wallet_start_time: &str,
    custom_args: Option<&Vec<String>>,
    custom_env: Option<&BTreeMap<String, String>>,
    wallet_defaults: Option<&BTreeMap<String, OptionValue>>,
    wallet_options: Option<&BTreeMap<String, OptionValue>>,
    shared_dir: &str,
) -> String {
    let daemon_address = daemon.format();
    let wallet_args = build_wallet_args(
        agent_id, agent_ip, &daemon_address, wallet_rpc_port,
        environment, custom_args, wallet_defaults, wallet_options, shared_dir,
    );

    // Shell-quoted command string for the WALLET_RPC_CMD env var consumed
    // by `restart_wallet_rpc()` in agents/base_agent.py (which runs it via
    // `subprocess.Popen(..., shell=True)`). The Shadow process itself is
    // launched directly (no shell), using ProcessArgs::List(wallet_args).
    let wallet_cmd = format!(
        "{} {}",
        shell_quote_args(&[wallet_binary_path.to_string()]),
        shell_quote_args(&wallet_args),
    );

    let mut wallet_env = environment.clone();
    if let Some(env) = custom_env {
        for (key, value) in env {
            wallet_env.insert(key.clone(), value.clone());
        }
    }

    processes.push(ShadowProcess {
        path: wallet_binary_path.to_string(),
        args: ProcessArgs::List(wallet_args),
        environment: wallet_env,
        start_time: wallet_start_time.to_string(),
        shutdown_time: None,
        shutdown_signal: None,
        expected_final_state: Some(crate::shadow::ExpectedFinalState::Running),
    });

    wallet_cmd
}
