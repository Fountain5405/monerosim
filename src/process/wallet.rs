//! Monero wallet RPC process configuration.
//!
//! This file handles generation of Shadow process configurations
//! for monero-wallet-rpc instances.

use crate::shadow::ShadowProcess;
use crate::utils::duration::parse_duration_to_seconds;
use std::collections::BTreeMap;

/// Add a wallet process to the processes list
///
/// # Parameters
/// - `wallet_binary_path`: Path to wallet-rpc binary (already resolved for Shadow, e.g., "$HOME/.monerosim/bin/monero-wallet-rpc")
/// - `custom_args`: Optional additional CLI arguments to append
/// - `custom_env`: Optional additional environment variables to merge
pub fn add_wallet_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    agent_rpc_port: u16,
    wallet_rpc_port: u16,
    wallet_binary_path: &str,
    environment: &BTreeMap<String, String>,
    index: usize,
    wallet_start_time: &str,
    custom_args: Option<&Vec<String>>,
    custom_env: Option<&BTreeMap<String, String>>,
) {
    // Calculate wallet cleanup start time (2 seconds before wallet start)
    let cleanup_start_time = if let Ok(wallet_seconds) = parse_duration_to_seconds(wallet_start_time) {
        format!("{}s", wallet_seconds.saturating_sub(2))
    } else {
        format!("{}s", 48 + index * 2) // Fallback
    };

    // First, clean up any existing wallet files and create the wallet directory
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c 'rm -rf /tmp/monerosim_shared/{}_wallet && mkdir -p /tmp/monerosim_shared/{}_wallet'",
            agent_id, agent_id
        ),
        environment: environment.clone(),
        start_time: cleanup_start_time, // Start earlier to ensure cleanup completes
        shutdown_time: None,
        expected_final_state: None,
    });

    // Get thread count from environment (0=auto/omit flag, 1+=explicit count)
    let process_threads: u32 = environment.get("PROCESS_THREADS")
        .and_then(|s| s.parse().ok())
        .unwrap_or(1);

    // Build wallet args
    let mut wallet_args_parts = vec![
        format!("--daemon-address=http://{}:{}", agent_ip, agent_rpc_port),
        format!("--rpc-bind-port={}", wallet_rpc_port),
        format!("--rpc-bind-ip={}", agent_ip),
        "--disable-rpc-login".to_string(),
        "--trusted-daemon".to_string(),
        "--log-level=1".to_string(),
        format!("--wallet-dir=/tmp/monerosim_shared/{}_wallet", agent_id),
        "--non-interactive".to_string(),
        "--confirm-external-bind".to_string(),
        "--allow-mismatched-daemon-version".to_string(),
    ];

    // Add thread flag only if process_threads > 0
    if process_threads > 0 {
        wallet_args_parts.push(format!("--max-concurrency={}", process_threads));
    }

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
pub fn add_remote_wallet_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    remote_daemon_address: Option<&str>,
    wallet_rpc_port: u16,
    wallet_binary_path: &str,
    environment: &BTreeMap<String, String>,
    index: usize,
    wallet_start_time: &str,
    custom_args: Option<&Vec<String>>,
    custom_env: Option<&BTreeMap<String, String>>,
) {
    // Calculate wallet cleanup start time (2 seconds before wallet start)
    let cleanup_start_time = if let Ok(wallet_seconds) = parse_duration_to_seconds(wallet_start_time) {
        format!("{}s", wallet_seconds.saturating_sub(2))
    } else {
        format!("{}s", 48 + index * 2) // Fallback
    };

    // First, clean up any existing wallet files and create the wallet directory
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c 'rm -rf /tmp/monerosim_shared/{}_wallet && mkdir -p /tmp/monerosim_shared/{}_wallet'",
            agent_id, agent_id
        ),
        environment: environment.clone(),
        start_time: cleanup_start_time,
        shutdown_time: None,
        expected_final_state: None,
    });

    // Determine daemon address
    let daemon_address_arg = match remote_daemon_address {
        Some(addr) if addr != "auto" => {
            format!("--daemon-address=http://{}", addr)
        }
        _ => {
            // For "auto" mode, use a placeholder - Python agent will set it via RPC
            "--daemon-address=http://127.0.0.1:18081".to_string()
        }
    };

    // Get thread count from environment (0=auto/omit flag, 1+=explicit count)
    let process_threads: u32 = environment.get("PROCESS_THREADS")
        .and_then(|s| s.parse().ok())
        .unwrap_or(1);

    // Build wallet args
    let mut wallet_args_parts = vec![
        daemon_address_arg,
        format!("--rpc-bind-port={}", wallet_rpc_port),
        format!("--rpc-bind-ip={}", agent_ip),
        "--disable-rpc-login".to_string(),
        "--log-level=1".to_string(),
        format!("--wallet-dir=/tmp/monerosim_shared/{}_wallet", agent_id),
        "--non-interactive".to_string(),
        "--confirm-external-bind".to_string(),
        "--allow-mismatched-daemon-version".to_string(),
    ];

    // Add thread flag only if process_threads > 0
    if process_threads > 0 {
        wallet_args_parts.push(format!("--max-concurrency={}", process_threads));
    }

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
