//! Monero daemon process configuration.
//!
//! This module handles generation of Shadow process configurations
//! for monerod daemon instances with support for both mining and
//! standard daemon configurations.
//!
//! ## Mining Daemon Configuration
//!
//! Mining daemons use real wallet addresses retrieved via RPC and mining shim:
//! - Mining shim library preloading (LD_PRELOAD)
//! - Real wallet address retrieval via miner_init.sh script
//! - Environment variable-based address passing
//! - Mining-specific command-line arguments
//!
//! ## Standard Daemon Configuration
//!
//! Standard daemons run without mining capabilities and use
//! basic monerod configuration for blockchain synchronization.

use crate::shadow::ShadowProcess;
use std::collections::HashMap;

/// Add a mining-enabled daemon process to the processes list
///
/// This function configures a monerod daemon process for a miner agent,
/// including mining shim integration and real wallet address usage.
///
/// # Arguments
/// * `processes` - Mutable reference to the processes vector
/// * `agent_id` - Unique identifier for the agent
/// * `agent_ip` - IP address assigned to the agent
/// * `daemon_port` - RPC port for the daemon
/// * `wallet_port` - RPC port for the wallet
/// * `mining_shim_path` - Path to the mining shim library
/// * `hashrate` - Mining hashrate percentage (0-100)
/// * `simulation_seed` - Seed for deterministic simulation behavior
/// * `environment` - Base environment variables
/// * `index` - Agent index for timing calculations
/// * `daemon_start_time` - When the daemon should start
///
/// # Mining Shim Integration
///
/// The mining shim is loaded via LD_PRELOAD and configured with:
/// - `MINER_HASHRATE`: Hashrate value from agent attributes
/// - `AGENT_ID`: Unique agent identifier
/// - `SIMULATION_SEED`: Seed for deterministic behavior
/// - `MININGSHIM_LOG_LEVEL`: Logging level (default: info)
/// - `MINING_ADDRESS`: Real wallet address from miner_init.sh (environment variable)
///
/// # Process Sequence
///
/// 1. miner_init.sh script runs first (retrieves real wallet address via RPC)
/// 2. Script exports MINING_ADDRESS environment variable
/// 3. Daemon starts with --start-mining $MINING_ADDRESS
/// 4. Mining shim intercepts mining calls for probabilistic behavior
pub fn add_miner_daemon_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    daemon_port: u16,
    wallet_port: u16,
    mining_shim_path: &str,
    hashrate: &str,
    simulation_seed: u64,
    environment: &HashMap<String, String>,
    _index: usize,
    daemon_start_time: &str,
) {
    // NOTE: This function is now DEPRECATED for mining shim integration
    // The miner_init.sh script handles both wallet address retrieval AND monerod launch
    // This function should NOT be called for mining shim configurations
    //
    // Mining Architecture:
    // 1. miner_init.sh runs first (queries wallet RPC for real address)
    // 2. Script exports MINING_ADDRESS environment variable
    // 3. Script launches monerod directly with the real address
    // 4. Mining shim (LD_PRELOAD) intercepts mining calls for deterministic behavior
    //
    // This function is kept for backward compatibility but should not be used
    // with mining_shim_path configurations

    eprintln!("WARNING: add_miner_daemon_process called but should not be used with mining shim!");
    eprintln!("The miner_init.sh script should handle monerod launch for mining shim integration");

    // For backward compatibility, create a no-op process that does nothing
    // This prevents breaking existing code that might call this function
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: "-c 'echo \"Deprecated add_miner_daemon_process called - doing nothing\"'".to_string(),
        environment: environment.clone(),
        start_time: daemon_start_time.to_string(),
    });
}


/// Add a standard daemon process to the processes list
///
/// This function configures a monerod daemon process for non-mining nodes,
/// providing basic blockchain synchronization without mining capabilities.
///
/// # Arguments
/// * `processes` - Mutable reference to the processes vector
/// * `agent_id` - Unique identifier for the agent
/// * `agent_ip` - IP address assigned to the agent
/// * `daemon_port` - RPC port for the daemon
/// * `environment` - Environment variables
/// * `_index` - Agent index for timing calculations (unused)
/// * `daemon_start_time` - When the daemon should start
///
/// # Standard Configuration
///
/// Standard daemons are configured with:
/// - Basic RPC binding for peer communication
/// - Data directory isolation per agent
/// - Standard logging and external bind confirmation
/// - No mining shim or mining-related configuration
pub fn add_standard_daemon_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    daemon_port: u16,
    environment: &HashMap<String, String>,
    _index: usize,
    daemon_start_time: &str,
) {
    // Standard daemon configuration without mining
    let daemon_path = "/usr/local/bin/monerod";
    let daemon_args = format!(
        "--rpc-bind-ip={} --rpc-bind-port={} --confirm-external-bind --log-level=1 --data-dir=/tmp/monerosim_shared/{}_data --simulation",
        agent_ip, daemon_port, agent_id
    );

    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!("-c '{} {}'", daemon_path, daemon_args),
        environment: environment.clone(),
        start_time: daemon_start_time.to_string(),
    });
}
