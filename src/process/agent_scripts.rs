//! Agent script process configuration.
//!
//! This file handles generation of Shadow process configurations
//! for Python agent scripts.

use crate::shadow::ShadowProcess;
use crate::utils::duration::parse_duration_to_seconds;
use crate::utils::script::write_wrapper_script;
use std::collections::BTreeMap;
use std::path::Path;

/// Add a user agent process to the processes list
///
/// Supports full agents (local daemon + wallet), wallet-only agents (remote daemon),
/// and script-only agents (no daemon or wallet).
pub fn add_user_agent_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    daemon_rpc_port: Option<u16>,
    wallet_rpc_port: Option<u16>,
    p2p_port: Option<u16>,
    script: &str,
    attributes: Option<&BTreeMap<String, String>>,
    environment: &BTreeMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    index: usize,
    stop_time: &str,
    custom_start_time: Option<&str>,
    remote_daemon: Option<&str>,
    daemon_selection_strategy: Option<&str>,
    scripts_dir: &Path,
    wallet_rpc_cmd: Option<&str>,
) {
    let mut agent_args = vec![
        format!("--id {}", agent_id),
        format!("--shared-dir {}", shared_dir.to_string_lossy()),
        format!("--rpc-host {}", agent_ip),
        format!("--log-level DEBUG"),
        format!("--stop-time {}", stop_time),
    ];

    // Add local daemon RPC port if available
    if let Some(port) = daemon_rpc_port {
        agent_args.push(format!("--daemon-rpc-port {}", port));
    }

    // Add wallet RPC port if available
    if let Some(port) = wallet_rpc_port {
        agent_args.push(format!("--wallet-rpc-port {}", port));
    }

    // Add P2P port if available
    if let Some(port) = p2p_port {
        agent_args.push(format!("--p2p-port {}", port));
    }

    // Add remote daemon configuration for wallet-only agents
    if let Some(remote_addr) = remote_daemon {
        agent_args.push(format!("--remote-daemon {}", remote_addr));
    }

    // Add daemon selection strategy if specified
    if let Some(strategy) = daemon_selection_strategy {
        agent_args.push(format!("--daemon-selection-strategy {}", strategy));
    }

    // Add attributes from config as command-line arguments
    // This ensures attributes are available inside Shadow's isolated filesystem
    if let Some(attrs) = attributes {
        for (key, value) in attrs {
            // Map transaction_interval to --tx-frequency for backward compatibility
            if key == "transaction_interval" {
                agent_args.push(format!("--tx-frequency {}", value));
            }
            // Pass ALL attributes as --attributes key value pairs
            // This bypasses Shadow filesystem isolation issues
            agent_args.push(format!("--attributes {} {}", key, value));
        }
    }

    // Remove stop-time from agent args since agents handle their own lifecycle
    agent_args.retain(|arg| !arg.starts_with("--stop-time"));

    // Simplified command without nc dependency - just sleep and retry
    let python_cmd = if script.contains('.') && !script.contains('/') && !script.contains('\\') {
        format!("python3 -m {} {}", script, agent_args.join(" "))
    } else {
        format!("python3 {} {}", script, agent_args.join(" "))
    };

    // Resolve HOME for fully-qualified paths (no shell expansion needed)
    let home_dir = environment.get("HOME").cloned()
        .unwrap_or_else(|| std::env::var("HOME").unwrap_or_else(|_| "/root".to_string()));

    // Create wrapper script with fully-resolved paths.
    // No shell variable expansion needed - all paths are absolute.
    // Python agents handle their own RPC readiness retries via
    // wait_until_ready() with exponential backoff in base_agent.py.
    let wallet_export = match wallet_rpc_cmd {
        Some(cmd) => format!("export WALLET_RPC_CMD='{}'\n", cmd),
        None => String::new(),
    };

    let wrapper_content = format!(
        r#"#!/bin/bash
cd {}
export PYTHONPATH={}
export PATH=/usr/local/bin:/usr/bin:/bin:{}/.monerosim/bin
{}
{} 2>&1
"#,
        current_dir,
        current_dir,
        home_dir,
        wallet_export,
        python_cmd
    );

    // Determine start time
    let start_time = if let Some(custom_time) = custom_start_time {
        if parse_duration_to_seconds(custom_time).is_ok() {
            custom_time.to_string()
        } else {
            format!("{}s", 65 + index * 2)
        }
    } else {
        format!("{}s", 65 + index * 2)
    };

    match write_wrapper_script(
        scripts_dir,
        &format!("agent_{}_wrapper.sh", agent_id),
        &wrapper_content,
        environment,
        start_time,
        None,
        Some(crate::shadow::ExpectedFinalState::Running),
    ) {
        Ok(process) => processes.push(process),
        Err(e) => log::error!("Failed to write wrapper script for agent {}: {}", agent_id, e),
    }
}

/// Create mining agent processes
///
/// This function generates Shadow process configurations for autonomous mining agents.
/// Mining agents use the `autonomous_miner.py` script and require specific arguments
/// for RPC connections and agent attributes.
pub fn create_mining_agent_process(
    agent_id: &str,
    ip_addr: &str,
    daemon_rpc_port: u16,
    wallet_rpc_port: Option<u16>,
    mining_script: &str,
    attributes: Option<&BTreeMap<String, String>>,
    environment: &BTreeMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    index: usize,
    _stop_time: &str,
    custom_start_time: Option<&str>,
    scripts_dir: &Path,
    wallet_rpc_cmd: Option<&str>,
) -> Vec<ShadowProcess> {
    // Build Python command with all required arguments
    let mut args = vec![
        format!("--id {}", agent_id),
        format!("--rpc-host {}", ip_addr),
        format!("--daemon-rpc-port {}", daemon_rpc_port),
        format!("--shared-dir {}", shared_dir.to_string_lossy()),
        format!("--log-level DEBUG"),
    ];

    // Add wallet RPC port if provided
    if let Some(wallet_port) = wallet_rpc_port {
        args.push(format!("--wallet-rpc-port {}", wallet_port));
    }

    // Add attributes as key-value pairs
    if let Some(attrs) = attributes {
        for (key, value) in attrs {
            args.push(format!("--attributes {} {}", key, value));
        }
    }

    // Create Python command - handle module path format
    let python_cmd = if mining_script.contains('.') && !mining_script.contains('/') && !mining_script.contains('\\') {
        format!("python3 -m {} {}", mining_script, args.join(" "))
    } else {
        format!("python3 {} {}", mining_script, args.join(" "))
    };

    // Resolve HOME for fully-qualified paths (no shell expansion needed)
    let home_dir = environment.get("HOME").cloned()
        .unwrap_or_else(|| std::env::var("HOME").unwrap_or_else(|_| "/root".to_string()));

    // Create wrapper script with fully-resolved paths.
    let wallet_export = match wallet_rpc_cmd {
        Some(cmd) => format!("export WALLET_RPC_CMD='{}'\n", cmd),
        None => String::new(),
    };

    let wrapper_content = format!(
        r#"#!/bin/bash
cd {}
export PYTHONPATH={}
export PATH=/usr/local/bin:/usr/bin:/bin:{}/.monerosim/bin
{}
{} 2>&1
"#,
        current_dir,
        current_dir,
        home_dir,
        wallet_export,
        python_cmd
    );

    // Determine start time
    let start_time = if let Some(custom_time) = custom_start_time {
        if parse_duration_to_seconds(custom_time).is_ok() {
            custom_time.to_string()
        } else {
            format!("{}s", 65 + index * 2)
        }
    } else {
        format!("{}s", 65 + index * 2)
    };

    match write_wrapper_script(
        scripts_dir,
        &format!("mining_agent_{}_wrapper.sh", agent_id),
        &wrapper_content,
        environment,
        start_time,
        None,
        Some(crate::shadow::ExpectedFinalState::Running),
    ) {
        Ok(process) => vec![process],
        Err(e) => {
            log::error!("Failed to write wrapper script for mining agent {}: {}", agent_id, e);
            Vec::new()
        }
    }
}
