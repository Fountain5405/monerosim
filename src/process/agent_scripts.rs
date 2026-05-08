//! Agent script process configuration.
//!
//! This file handles generation of Shadow process configurations
//! for Python agent scripts.

use crate::shadow::ShadowProcess;
use crate::utils::duration::parse_duration_to_seconds;
use crate::utils::script::write_wrapper_script;
use std::collections::BTreeMap;
use std::path::Path;

/// Arguments for `add_user_agent_process`.
pub struct UserAgentProcessArgs<'a> {
    pub processes: &'a mut Vec<ShadowProcess>,
    pub agent_id: &'a str,
    pub agent_ip: &'a str,
    pub daemon_rpc_port: Option<u16>,
    pub wallet_rpc_port: Option<u16>,
    pub p2p_port: Option<u16>,
    pub script: &'a str,
    pub attributes: Option<&'a BTreeMap<String, String>>,
    pub environment: &'a BTreeMap<String, String>,
    pub shared_dir: &'a Path,
    pub current_dir: &'a str,
    pub index: usize,
    pub stop_time: &'a str,
    pub custom_start_time: Option<&'a str>,
    pub remote_daemon: Option<&'a str>,
    pub daemon_selection_strategy: Option<&'a str>,
    pub scripts_dir: &'a Path,
    pub wallet_rpc_cmd: Option<&'a str>,
}

/// Add a user agent process to the processes list
///
/// Supports full agents (local daemon + wallet), wallet-only agents (remote daemon),
/// and script-only agents (no daemon or wallet).
pub fn add_user_agent_process(args: UserAgentProcessArgs<'_>) {
    let mut agent_args = vec![
        format!("--id {}", args.agent_id),
        format!("--shared-dir {}", args.shared_dir.to_string_lossy()),
        format!("--rpc-host {}", args.agent_ip),
        format!("--log-level DEBUG"),
        format!("--stop-time {}", args.stop_time),
    ];

    // Add local daemon RPC port if available
    if let Some(port) = args.daemon_rpc_port {
        agent_args.push(format!("--daemon-rpc-port {}", port));
    }

    // Add wallet RPC port if available
    if let Some(port) = args.wallet_rpc_port {
        agent_args.push(format!("--wallet-rpc-port {}", port));
    }

    // Add P2P port if available
    if let Some(port) = args.p2p_port {
        agent_args.push(format!("--p2p-port {}", port));
    }

    // Add remote daemon configuration for wallet-only agents
    if let Some(remote_addr) = args.remote_daemon {
        agent_args.push(format!("--remote-daemon {}", remote_addr));
    }

    // Add daemon selection strategy if specified
    if let Some(strategy) = args.daemon_selection_strategy {
        agent_args.push(format!("--daemon-selection-strategy {}", strategy));
    }

    // Add attributes from config as command-line arguments
    // This ensures attributes are available inside Shadow's isolated filesystem
    if let Some(attrs) = args.attributes {
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

    // `exec` so bash is replaced by python3 — Shadow's SIGTERM at shutdown
    // then goes directly to the agent (which has its own SIGTERM handler in
    // base_agent.py) instead of being absorbed by an idle bash parent.
    let python_cmd = if args.script.contains('.') && !args.script.contains('/') && !args.script.contains('\\') {
        format!("exec python3 -m {} {}", args.script, agent_args.join(" "))
    } else {
        format!("exec python3 {} {}", args.script, agent_args.join(" "))
    };

    // Resolve HOME for fully-qualified paths (no shell expansion needed)
    let home_dir = args.environment.get("HOME").cloned()
        .unwrap_or_else(|| std::env::var("HOME").unwrap_or_else(|_| "/root".to_string()));

    // Create wrapper script with fully-resolved paths.
    // No shell variable expansion needed - all paths are absolute.
    // Python agents handle their own RPC readiness retries via
    // wait_until_ready() with exponential backoff in base_agent.py.
    let wallet_export = match args.wallet_rpc_cmd {
        // Outer double-quotes make the assignment a single word; the inner
        // single-quoted segments produced by shell_quote_args are then
        // literal (no glob/word-split). Safe because our args never
        // contain $, ", \, or backtick.
        Some(cmd) => format!("export WALLET_RPC_CMD=\"{}\"\n", cmd),
        None => String::new(),
    };

    // Include venv site-packages in PYTHONPATH so pip-installed deps (e.g. requests) are found
    let venv_sp = args.environment.get("VENV_SITE_PACKAGES").cloned().unwrap_or_default();

    let wrapper_content = format!(
        r#"#!/bin/bash
cd {}
export PYTHONPATH={}:{}
export PATH="$PATH:{}/.monerosim/bin"
{}
{} 2>&1
"#,
        args.current_dir,
        args.current_dir,
        venv_sp,
        home_dir,
        wallet_export,
        python_cmd
    );

    // Determine start time
    let start_time = if let Some(custom_time) = args.custom_start_time {
        if parse_duration_to_seconds(custom_time).is_ok() {
            custom_time.to_string()
        } else {
            format!("{}s", 65 + args.index * 2)
        }
    } else {
        format!("{}s", 65 + args.index * 2)
    };

    match write_wrapper_script(
        args.scripts_dir,
        &format!("agent_{}_wrapper.sh", args.agent_id),
        &wrapper_content,
        args.environment,
        start_time,
        None,
        Some(crate::shadow::ExpectedFinalState::Running),
    ) {
        Ok(process) => args.processes.push(process),
        Err(e) => log::error!("Failed to write wrapper script for agent {}: {}", args.agent_id, e),
    }
}

/// Arguments for `create_mining_agent_process`.
pub struct MiningAgentProcessArgs<'a> {
    pub agent_id: &'a str,
    pub ip_addr: &'a str,
    pub daemon_rpc_port: u16,
    pub wallet_rpc_port: Option<u16>,
    pub mining_script: &'a str,
    pub attributes: Option<&'a BTreeMap<String, String>>,
    pub environment: &'a BTreeMap<String, String>,
    pub shared_dir: &'a Path,
    pub current_dir: &'a str,
    pub index: usize,
    pub custom_start_time: Option<&'a str>,
    pub scripts_dir: &'a Path,
    pub wallet_rpc_cmd: Option<&'a str>,
}

/// Create mining agent processes
///
/// This function generates Shadow process configurations for autonomous mining agents.
/// Mining agents use the `autonomous_miner.py` script and require specific arguments
/// for RPC connections and agent attributes.
pub fn create_mining_agent_process(args: MiningAgentProcessArgs<'_>) -> Vec<ShadowProcess> {
    // Build Python command with all required arguments
    let mut script_args = vec![
        format!("--id {}", args.agent_id),
        format!("--rpc-host {}", args.ip_addr),
        format!("--daemon-rpc-port {}", args.daemon_rpc_port),
        format!("--shared-dir {}", args.shared_dir.to_string_lossy()),
        format!("--log-level DEBUG"),
    ];

    // Add wallet RPC port if provided
    if let Some(wallet_port) = args.wallet_rpc_port {
        script_args.push(format!("--wallet-rpc-port {}", wallet_port));
    }

    // Add attributes as key-value pairs
    if let Some(attrs) = args.attributes {
        for (key, value) in attrs {
            script_args.push(format!("--attributes {} {}", key, value));
        }
    }

    // `exec` so bash is replaced by python3 (see add_user_agent_process).
    let python_cmd = if args.mining_script.contains('.') && !args.mining_script.contains('/') && !args.mining_script.contains('\\') {
        format!("exec python3 -m {} {}", args.mining_script, script_args.join(" "))
    } else {
        format!("exec python3 {} {}", args.mining_script, script_args.join(" "))
    };

    // Resolve HOME for fully-qualified paths (no shell expansion needed)
    let home_dir = args.environment.get("HOME").cloned()
        .unwrap_or_else(|| std::env::var("HOME").unwrap_or_else(|_| "/root".to_string()));

    // Create wrapper script with fully-resolved paths.
    let wallet_export = match args.wallet_rpc_cmd {
        // Outer double-quotes make the assignment a single word; the inner
        // single-quoted segments produced by shell_quote_args are then
        // literal (no glob/word-split). Safe because our args never
        // contain $, ", \, or backtick.
        Some(cmd) => format!("export WALLET_RPC_CMD=\"{}\"\n", cmd),
        None => String::new(),
    };

    // Include venv site-packages in PYTHONPATH so pip-installed deps (e.g. requests) are found
    let venv_sp = args.environment.get("VENV_SITE_PACKAGES").cloned().unwrap_or_default();

    let wrapper_content = format!(
        r#"#!/bin/bash
cd {}
export PYTHONPATH={}:{}
export PATH="$PATH:{}/.monerosim/bin"
{}
{} 2>&1
"#,
        args.current_dir,
        args.current_dir,
        venv_sp,
        home_dir,
        wallet_export,
        python_cmd
    );

    // Determine start time
    let start_time = if let Some(custom_time) = args.custom_start_time {
        if parse_duration_to_seconds(custom_time).is_ok() {
            custom_time.to_string()
        } else {
            format!("{}s", 65 + args.index * 2)
        }
    } else {
        format!("{}s", 65 + args.index * 2)
    };

    match write_wrapper_script(
        args.scripts_dir,
        &format!("mining_agent_{}_wrapper.sh", args.agent_id),
        &wrapper_content,
        args.environment,
        start_time,
        None,
        Some(crate::shadow::ExpectedFinalState::Running),
    ) {
        Ok(process) => vec![process],
        Err(e) => {
            log::error!("Failed to write wrapper script for mining agent {}: {}", args.agent_id, e);
            Vec::new()
        }
    }
}
