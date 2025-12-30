//! Monero wallet RPC process configuration.
//!
//! This file handles generation of Shadow process configurations
//! for monero-wallet-rpc instances.

use crate::shadow::ShadowProcess;
use crate::utils::duration::parse_duration_to_seconds;
use std::collections::HashMap;

/// Add a wallet process to the processes list
pub fn add_wallet_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    agent_rpc_port: u16,
    wallet_rpc_port: u16,
    _wallet_path: &str,
    environment: &HashMap<String, String>,
    index: usize,
    wallet_start_time: &str,
) {
    let wallet_name = format!("{}_wallet", agent_id);

    // Create wallet JSON content (currently unused but kept for potential future use)
    let _wallet_json_content = format!(
        r#"{{"version": 1,"filename": "{}","scan_from_height": 0,"password": "","viewkey": "","spendkey": "","seed": "","seed_passphrase": "","address": "","restore_height": 0,"autosave_current": true}}"#,
        wallet_name
    );

    // Get the absolute path to the wallet launcher script
    let _launcher_path = std::env::current_dir()
        .unwrap()
        .join("scripts/wallet_launcher.sh")
        .to_string_lossy()
        .to_string();

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
    });

    // Launch wallet RPC directly - it will create wallets on demand
    let wallet_path = "/usr/local/bin/monero-wallet-rpc".to_string();

    let wallet_args = format!(
        "--daemon-address=http://{}:{} --rpc-bind-port={} --rpc-bind-ip={} --disable-rpc-login --trusted-daemon --log-level=1 --wallet-dir=/tmp/monerosim_shared/{}_wallet --non-interactive --confirm-external-bind --allow-mismatched-daemon-version --max-concurrency=1 --daemon-ssl-allow-any-cert",
        agent_ip, agent_rpc_port, wallet_rpc_port, agent_ip, agent_id
    );

    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c '{} {}'",
            wallet_path, wallet_args
        ),
        environment: environment.clone(),
        start_time: wallet_start_time.to_string(), // Use the calculated wallet start time
    });
}

/// Add a wallet process for wallet-only agents that connect to a remote daemon
///
/// For wallet-only agents, the daemon address can be either:
/// - A specific address (e.g., "192.168.1.10:28081")
/// - "auto" - wallet starts without initial daemon, Python agent calls set_daemon()
pub fn add_remote_wallet_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    remote_daemon_address: Option<&str>,
    wallet_rpc_port: u16,
    environment: &HashMap<String, String>,
    index: usize,
    wallet_start_time: &str,
) {
    let _wallet_name = format!("{}_wallet", agent_id);

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
    });

    // Launch wallet RPC
    let wallet_path = "/usr/local/bin/monero-wallet-rpc".to_string();

    // Determine daemon address
    let daemon_address_arg = match remote_daemon_address {
        Some(addr) if addr != "auto" => {
            // Specific remote daemon address
            format!("--daemon-address=http://{}", addr)
        }
        _ => {
            // For "auto" mode, start without daemon - Python agent will set it via RPC
            // Use a placeholder that won't connect (wallet will start but daemon calls will fail)
            // The Python agent must call set_daemon() before making daemon-dependent calls
            "--daemon-address=http://127.0.0.1:18081".to_string()
        }
    };

    let wallet_args = format!(
        "{} --rpc-bind-port={} --rpc-bind-ip={} --disable-rpc-login --log-level=1 --wallet-dir=/tmp/monerosim_shared/{}_wallet --non-interactive --confirm-external-bind --allow-mismatched-daemon-version --max-concurrency=1 --daemon-ssl-allow-any-cert",
        daemon_address_arg, wallet_rpc_port, agent_ip, agent_id
    );

    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c '{} {}'",
            wallet_path, wallet_args
        ),
        environment: environment.clone(),
        start_time: wallet_start_time.to_string(),
    });
}
