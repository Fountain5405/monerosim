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

    // Create wallet JSON content
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

    // Create wallet RPC wrapper script with timeout mechanism
    let wallet_wrapper_content = format!(
        r#"#!/bin/bash
# Wallet RPC wrapper with timeout for Shadow simulation
cd /home/lever65/monerosim_dev/monerosim

# Start wallet RPC in background
/usr/local/bin/monero-wallet-rpc \
  --daemon-address=http://{}:{} \
  --rpc-bind-port={} \
  --rpc-bind-ip={} \
  --disable-rpc-login \
  --trusted-daemon \
  --log-level=1 \
  --wallet-dir=/tmp/monerosim_shared/{}_wallet \
  --non-interactive \
  --confirm-external-bind \
  --allow-mismatched-daemon-version \
  --max-concurrency=1 \
  --daemon-ssl-allow-any-cert &
WALLET_PID=$!

# Wait for wallet to be ready or timeout
for i in {{1..60}}; do
  if curl -s --max-time 1 http://{}:{} >/dev/null 2>&1; then
    echo "Wallet RPC ready"
    break
  fi
  sleep 1
done

# Keep wallet running until simulation end (Shadow will kill the process)
wait $WALLET_PID
"#,
        agent_ip, agent_rpc_port, wallet_rpc_port, agent_ip, agent_id, agent_ip, wallet_rpc_port
    );

    // Create the wrapper script
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c 'cat > /tmp/wallet_wrapper_{}.sh << EOF\n{}\nEOF'",
            agent_id, wallet_wrapper_content
        ),
        environment: environment.clone(),
        start_time: format!("{}s", parse_duration_to_seconds(wallet_start_time).unwrap_or(0) - 1),
    });

    // Make it executable and run it
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!("-c 'chmod +x /tmp/wallet_wrapper_{}.sh && /tmp/wallet_wrapper_{}.sh'", agent_id, agent_id),
        environment: environment.clone(),
        start_time: wallet_start_time.to_string(),
    });
}
