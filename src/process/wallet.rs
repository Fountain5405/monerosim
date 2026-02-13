//! Monero wallet RPC process configuration.
//!
//! This file handles generation of Shadow process configurations
//! for monero-wallet-rpc instances.

use crate::config_v2::OptionValue;
use crate::shadow::ShadowProcess;
use crate::utils::options::{options_to_args, merge_options};
use std::collections::BTreeMap;

/// Build wallet command-line arguments common to both local and remote daemon modes.
fn build_wallet_args(
    agent_id: &str,
    agent_ip: &str,
    daemon_address: &str,
    wallet_rpc_port: u16,
    environment: &BTreeMap<String, String>,
    custom_args: Option<&Vec<String>>,
    wallet_defaults: Option<&BTreeMap<String, OptionValue>>,
    wallet_options: Option<&BTreeMap<String, OptionValue>>,
) -> String {
    let process_threads: u32 = environment.get("PROCESS_THREADS")
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);

    let merged_wallet_options = merge_options(wallet_defaults, wallet_options);

    let mut args = vec![
        format!("--daemon-address={}", daemon_address),
        format!("--rpc-bind-port={}", wallet_rpc_port),
        format!("--rpc-bind-ip={}", agent_ip),
        "--disable-rpc-login".to_string(),
        "--trusted-daemon".to_string(),
        format!("--wallet-dir={}/{}_wallet", crate::SHARED_DIR, agent_id),
        "--confirm-external-bind".to_string(),
        "--allow-mismatched-daemon-version".to_string(),
    ];

    if process_threads > 0 && !merged_wallet_options.contains_key("max-concurrency") {
        args.push(format!("--max-concurrency={}", process_threads));
    }

    args.extend(options_to_args(&merged_wallet_options));
    args.push("--daemon-ssl-allow-any-cert".to_string());

    if let Some(custom) = custom_args {
        args.extend(custom.iter().cloned());
    }

    args.join(" ")
}

/// Add a wallet process connecting to a local daemon on the same host.
pub fn add_wallet_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    daemon_rpc_port: u16,
    wallet_rpc_port: u16,
    wallet_binary_path: &str,
    environment: &BTreeMap<String, String>,
    _index: usize,
    wallet_start_time: &str,
    custom_args: Option<&Vec<String>>,
    custom_env: Option<&BTreeMap<String, String>>,
    wallet_defaults: Option<&BTreeMap<String, OptionValue>>,
    wallet_options: Option<&BTreeMap<String, OptionValue>>,
) {
    let daemon_address = format!("http://{}:{}", agent_ip, daemon_rpc_port);
    let wallet_args = build_wallet_args(
        agent_id, agent_ip, &daemon_address, wallet_rpc_port,
        environment, custom_args, wallet_defaults, wallet_options,
    );

    let mut wallet_env = environment.clone();
    if let Some(env) = custom_env {
        for (key, value) in env {
            wallet_env.insert(key.clone(), value.clone());
        }
    }

    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!("-c '{} {}'", wallet_binary_path, wallet_args),
        environment: wallet_env,
        start_time: wallet_start_time.to_string(),
        shutdown_time: None,
        expected_final_state: Some(crate::shadow::ExpectedFinalState::Running),
    });
}

/// Add a wallet process connecting to a remote daemon.
///
/// For "auto" mode, uses a localhost placeholder; the Python agent will
/// call `set_daemon()` at runtime to connect to a discovered public node.
pub fn add_remote_wallet_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    remote_daemon_address: Option<&str>,
    wallet_rpc_port: u16,
    wallet_binary_path: &str,
    environment: &BTreeMap<String, String>,
    _index: usize,
    wallet_start_time: &str,
    custom_args: Option<&Vec<String>>,
    custom_env: Option<&BTreeMap<String, String>>,
    wallet_defaults: Option<&BTreeMap<String, OptionValue>>,
    wallet_options: Option<&BTreeMap<String, OptionValue>>,
) {
    let daemon_address = match remote_daemon_address {
        Some(addr) if addr != "auto" => format!("http://{}", addr),
        _ => format!("http://127.0.0.1:{}", crate::MONERO_RPC_PORT),
    };

    let wallet_args = build_wallet_args(
        agent_id, agent_ip, &daemon_address, wallet_rpc_port,
        environment, custom_args, wallet_defaults, wallet_options,
    );

    let mut wallet_env = environment.clone();
    if let Some(env) = custom_env {
        for (key, value) in env {
            wallet_env.insert(key.clone(), value.clone());
        }
    }

    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!("-c '{} {}'", wallet_binary_path, wallet_args),
        environment: wallet_env,
        start_time: wallet_start_time.to_string(),
        shutdown_time: None,
        expected_final_state: Some(crate::shadow::ExpectedFinalState::Running),
    });
}
