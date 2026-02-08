//! Monero wallet RPC process configuration.
//!
//! This file handles generation of Shadow process configurations
//! for monero-wallet-rpc instances.

use crate::config_v2::OptionValue;
use crate::shadow::ShadowProcess;
use crate::utils::options::{options_to_args, merge_options};
use std::collections::BTreeMap;

/// Add a wallet process to the processes list
///
/// # Parameters
/// - `wallet_binary_path`: Path to wallet-rpc binary (already resolved for Shadow, e.g., "$HOME/.monerosim/bin/monero-wallet-rpc")
/// - `custom_args`: Optional additional CLI arguments to append
/// - `custom_env`: Optional additional environment variables to merge
/// - `wallet_defaults`: Global wallet defaults from config
/// - `wallet_options`: Per-agent wallet options (overrides defaults)
pub fn add_wallet_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    agent_rpc_port: u16,
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
    // Note: wallet directory cleanup is handled pre-simulation by the orchestrator.
    // It creates /tmp/monerosim_shared/{agent_id}_wallet with chmod 755 before
    // the Shadow config is even written.

    // Get process_threads from environment (convenience setting)
    let process_threads: u32 = environment.get("PROCESS_THREADS")
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);

    // Merge wallet_defaults with wallet_options
    let merged_wallet_options = merge_options(wallet_defaults, wallet_options);

    // Build wallet args - start with required flags
    let mut wallet_args_parts = vec![
        format!("--daemon-address=http://{}:{}", agent_ip, agent_rpc_port),
        format!("--rpc-bind-port={}", wallet_rpc_port),
        format!("--rpc-bind-ip={}", agent_ip),
        "--disable-rpc-login".to_string(),
        "--trusted-daemon".to_string(),
        format!("--wallet-dir={}/{}_wallet", crate::SHARED_DIR, agent_id),
        "--confirm-external-bind".to_string(),
        "--allow-mismatched-daemon-version".to_string(),
    ];

    // Add process_threads flag if set and not overridden in wallet_defaults
    if process_threads > 0 && !merged_wallet_options.contains_key("max-concurrency") {
        wallet_args_parts.push(format!("--max-concurrency={}", process_threads));
    }

    // Add configurable options from merged wallet_defaults + wallet_options
    wallet_args_parts.extend(options_to_args(&merged_wallet_options));

    wallet_args_parts.push("--daemon-ssl-allow-any-cert".to_string());

    // Append custom args if provided
    if let Some(args) = custom_args {
        for arg in args {
            wallet_args_parts.push(arg.clone());
        }
    }

    let wallet_args = wallet_args_parts.join(" ");

    // Merge custom environment if provided
    let mut wallet_env = environment.clone();
    if let Some(env) = custom_env {
        for (key, value) in env {
            wallet_env.insert(key.clone(), value.clone());
        }
    }

    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c '{} {}'",
            wallet_binary_path, wallet_args
        ),
        environment: wallet_env,
        start_time: wallet_start_time.to_string(),
        shutdown_time: None,
        expected_final_state: None,
    });
}

/// Add a wallet process for wallet-only agents that connect to a remote daemon
///
/// For wallet-only agents, the daemon address can be either:
/// - A specific address (e.g., "192.168.1.10:18081")
/// - "auto" - wallet starts without initial daemon, Python agent calls set_daemon()
///
/// # Parameters
/// - `wallet_binary_path`: Path to wallet-rpc binary (already resolved for Shadow)
/// - `custom_args`: Optional additional CLI arguments to append
/// - `custom_env`: Optional additional environment variables to merge
/// - `wallet_defaults`: Global wallet defaults from config
/// - `wallet_options`: Per-agent wallet options (overrides defaults)
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
    // Note: wallet directory cleanup is handled pre-simulation by the orchestrator.

    // Determine daemon address
    let daemon_address_arg = match remote_daemon_address {
        Some(addr) if addr != "auto" => {
            format!("--daemon-address=http://{}", addr)
        }
        _ => {
            // For "auto" mode, use a placeholder - Python agent will set it via RPC
            format!("--daemon-address=http://127.0.0.1:{}", crate::MONERO_RPC_PORT)
        }
    };

    // Get process_threads from environment (convenience setting)
    let process_threads: u32 = environment.get("PROCESS_THREADS")
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);

    // Merge wallet_defaults with wallet_options
    let merged_wallet_options = merge_options(wallet_defaults, wallet_options);

    // Build wallet args - start with required flags
    let mut wallet_args_parts = vec![
        daemon_address_arg,
        format!("--rpc-bind-port={}", wallet_rpc_port),
        format!("--rpc-bind-ip={}", agent_ip),
        "--disable-rpc-login".to_string(),
        format!("--wallet-dir={}/{}_wallet", crate::SHARED_DIR, agent_id),
        "--confirm-external-bind".to_string(),
        "--allow-mismatched-daemon-version".to_string(),
    ];

    // Add process_threads flag if set and not overridden in wallet_defaults
    if process_threads > 0 && !merged_wallet_options.contains_key("max-concurrency") {
        wallet_args_parts.push(format!("--max-concurrency={}", process_threads));
    }

    // Add configurable options from merged wallet_defaults + wallet_options
    wallet_args_parts.extend(options_to_args(&merged_wallet_options));

    wallet_args_parts.push("--daemon-ssl-allow-any-cert".to_string());

    // Append custom args if provided
    if let Some(args) = custom_args {
        for arg in args {
            wallet_args_parts.push(arg.clone());
        }
    }

    let wallet_args = wallet_args_parts.join(" ");

    // Merge custom environment if provided
    let mut wallet_env = environment.clone();
    if let Some(env) = custom_env {
        for (key, value) in env {
            wallet_env.insert(key.clone(), value.clone());
        }
    }

    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c '{} {}'",
            wallet_binary_path, wallet_args
        ),
        environment: wallet_env,
        start_time: wallet_start_time.to_string(),
        shutdown_time: None,
        expected_final_state: None,
    });
}
