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

    // Keep stop-time in agent args so agents know when to exit
    // agent_args.retain(|arg| !arg.starts_with("--stop-time"));

    // Simplified command without nc dependency - just sleep and retry
    let python_cmd = if script.contains('.') && !script.contains('/') && !script.contains('\\') {
        format!("python3 -m {} {}", script, agent_args.join(" "))
    } else {
        format!("python3 {} {}", script, agent_args.join(" "))
    };

    // Create a simple wrapper script that handles retries internally and includes timeout
    let wrapper_script = format!(
        r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:/usr/local/bin"

# Start agent with timeout to match simulation duration (600 seconds = 10 minutes)
# Give 30 seconds grace period before simulation end
timeout 570 {} &
AGENT_PID=$!

# Wait for wallet RPC to be ready
for i in {{1..30}}; do
    if curl -s --max-time 1 http://{}:{} >/dev/null 2>&1; then
        echo "Wallet RPC ready"
        break
    fi
    echo "Waiting for wallet RPC... (attempt $i/30)"
    sleep 3
done

# Wait for agent to complete or timeout
wait $AGENT_PID
exit $?
"#,
        current_dir,
        current_dir,
        python_cmd,
        agent_ip,
        wallet_rpc_port
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
        args: format!("-c 'cat > {} << EOF\n{}EOF'", script_path, wrapper_script),
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

/// Add a miner initialization process to processes list
pub fn add_miner_init_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    wallet_rpc_port: u16,
    daemon_rpc_port: u16,
    environment: &HashMap<String, String>,
    start_time: &str,
) {
    let miner_init_script = format!(
        r#"#!/bin/bash
cd /home/lever65/monerosim_dev/monerosim
export PYTHONPATH="${{PYTHONPATH}}:/home/lever65/monerosim_dev/monerosim"
export PATH="${{PATH}}:/usr/local/bin"

# Run miner initialization script
./agents/miner_init.sh {} {} {} {} MINER_WALLET_ADDRESS 2>&1
"#,
        agent_id, agent_ip, wallet_rpc_port, daemon_rpc_port
    );

    // Write miner init script to a temporary file
    let script_path = format!("/tmp/miner_init_{}.sh", agent_id);

    // Process 1: Create miner init script
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!("-c 'cat > {} << EOF\n{}\nEOF'", script_path, miner_init_script),
        environment: environment.clone(),
        start_time: start_time.to_string(),
    });

    // Process 2: Make script executable and run it
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!("-c 'chmod +x {} && {}'", script_path, script_path),
        environment: environment.clone(),
        start_time: format!("{}s", parse_duration_to_seconds(start_time).unwrap_or(0) + 1),
    });
}
