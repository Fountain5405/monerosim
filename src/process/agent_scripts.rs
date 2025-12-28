//! Agent script process configuration.
//!
//! This file handles generation of Shadow process configurations
//! for Python agent scripts.

use crate::shadow::ShadowProcess;
use crate::utils::duration::parse_duration_to_seconds;
use std::collections::HashMap;
use std::path::Path;

/// Add a user agent process to the processes list
pub fn add_user_agent_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    agent_rpc_port: u16,
    wallet_rpc_port: u16,
    p2p_port: u16,
    script: &str,
    attributes: Option<&HashMap<String, String>>,
    environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    index: usize,
    stop_time: &str,
    custom_start_time: Option<&str>,
) {
    let mut agent_args = vec![
        format!("--id {}", agent_id),
        format!("--shared-dir {}", shared_dir.to_str().unwrap()),
        format!("--rpc-host {}", agent_ip),
        format!("--agent-rpc-port {}", agent_rpc_port),
        format!("--wallet-rpc-port {}", wallet_rpc_port),
        format!("--p2p-port {}", p2p_port),
        format!("--log-level DEBUG"),
        format!("--stop-time {}", stop_time),
    ];

    // Add attributes from config as command-line arguments
    if let Some(attrs) = attributes {
        // Map specific attributes to their correct parameter names
        for (key, value) in attrs {
            if key == "transaction_interval" {
                agent_args.push(format!("--tx-frequency {}", value));
            } else if (key == "min_transaction_amount" || key == "max_transaction_amount" ||
                      key == "can_receive_distributions" || key == "location" || key == "city") ||
                      (key == "is_miner" && value == "true") {
                // These should be passed as attributes, but only pass is_miner if it's true
                agent_args.push(format!("--attributes {} {}", key, value));
            } else if key != "hashrate" && key != "is_miner" {
                // Pass other attributes directly, but filter out hashrate and is_miner (when false)
                agent_args.push(format!("--attributes {} {}", key, value));
            }
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

    // Create a simple wrapper script that handles retries internally
    let wrapper_script = format!(
        r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:/usr/local/bin"

# Simple retry loop without nc dependency
for i in {{1..30}}; do
    if curl -s --max-time 1 http://{}:{} >/dev/null 2>&1; then
        echo "Wallet RPC ready, starting agent..."
        {} 2>&1
        exit $?
    fi
    echo "Waiting for wallet RPC... (attempt $i/30)"
    sleep 3
done

echo "Wallet RPC not available after 30 attempts, starting agent anyway..."
{} 2>&1
"#,
        current_dir,
        current_dir,
        agent_ip,
        wallet_rpc_port,
        python_cmd,
        python_cmd
    );

    // Write wrapper script to a temporary file and execute it
    let script_path = format!("/tmp/agent_{}_wrapper.sh", agent_id);

    // Use custom start time if provided, otherwise use default staggered timing
    let (script_creation_time, script_execution_time) = if let Some(custom_time) = custom_start_time {
        if let Ok(seconds) = parse_duration_to_seconds(custom_time) {
            (format!("{}s", seconds - 1), custom_time.to_string())
        } else {
            // Fallback to default timing if parsing fails
            (format!("{}s", 64 + index * 2), format!("{}s", 65 + index * 2))
        }
    } else {
        (format!("{}s", 64 + index * 2), format!("{}s", 65 + index * 2))
    };

    // Process 1: Create wrapper script
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!("-c 'cat > {} << \\EOF\n{}\\EOF'", script_path, wrapper_script),
        environment: environment.clone(),
        start_time: script_creation_time,
    });

    // Process 2: Execute wrapper script
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: script_path.clone(),
        environment: environment.clone(),
        start_time: script_execution_time,
    });
}

/// Create mining agent processes
///
/// This function generates Shadow process configurations for autonomous mining agents.
/// Mining agents use the `autonomous_miner.py` script and require specific arguments
/// for RPC connections and agent attributes.
pub fn create_mining_agent_process(
    agent_id: &str,
    ip_addr: &str,
    agent_rpc_port: u16,
    wallet_rpc_port: Option<u16>,
    mining_script: &str,
    attributes: Option<&HashMap<String, String>>,
    environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    index: usize,
    _stop_time: &str,
    custom_start_time: Option<&str>,
) -> Vec<ShadowProcess> {
    let mut processes = Vec::new();
    
    // Build Python command with all required arguments
    let mut args = vec![
        format!("--id {}", agent_id),
        format!("--rpc-host {}", ip_addr),
        format!("--agent-rpc-port {}", agent_rpc_port),
        format!("--shared-dir {}", shared_dir.to_str().unwrap()),
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
    
    // Create a simple wrapper script that handles retries internally
    let wrapper_script = format!(
        r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:/usr/local/bin"

# Simple retry loop without nc dependency
for i in {{1..30}}; do
    if curl -s --max-time 1 http://{}:{} >/dev/null 2>&1; then
        echo "Wallet RPC ready, starting mining agent..."
        {} 2>&1
        exit $?
    fi
    echo "Waiting for wallet RPC... (attempt $i/30)"
    sleep 3
done

echo "Wallet RPC not available after 30 attempts, starting mining agent anyway..."
{} 2>&1
"#,
        current_dir,
        current_dir,
        ip_addr,
        wallet_rpc_port.unwrap_or(agent_rpc_port),
        python_cmd,
        python_cmd
    );
    
    // Write wrapper script to a temporary file and execute it
    let script_path = format!("/tmp/mining_agent_{}_wrapper.sh", agent_id);
    
    // Use custom start time if provided, otherwise use default staggered timing
    let (script_creation_time, script_execution_time) = if let Some(custom_time) = custom_start_time {
        if let Ok(seconds) = parse_duration_to_seconds(custom_time) {
            (format!("{}s", seconds - 1), custom_time.to_string())
        } else {
            // Fallback to default timing if parsing fails
            (format!("{}s", 64 + index * 2), format!("{}s", 65 + index * 2))
        }
    } else {
        (format!("{}s", 64 + index * 2), format!("{}s", 65 + index * 2))
    };
    
    // Process 1: Create wrapper script
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!("-c 'cat > {} << \\\\EOF\\n{}\\\\EOF'", script_path, wrapper_script),
        environment: environment.clone(),
        start_time: script_creation_time,
    });
    
    // Process 2: Execute wrapper script
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: script_path.clone(),
        environment: environment.clone(),
        start_time: script_execution_time,
    });
    
    processes
}
