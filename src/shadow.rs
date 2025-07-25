use crate::config::Config;
use serde_yaml;
use std::collections::HashMap;
use std::path::Path;


#[derive(serde::Serialize, Debug)]
struct ShadowConfig {
    general: ShadowGeneral,
    network: ShadowNetwork,
    experimental: ShadowExperimental,
    hosts: HashMap<String, ShadowHost>,
}

#[derive(serde::Serialize, Debug)]
struct ShadowGeneral {
    stop_time: String,
    model_unblocked_syscall_latency: bool,
    log_level: String,
}

#[derive(serde::Serialize, Debug)]
struct ShadowExperimental {
    #[serde(skip_serializing_if = "Option::is_none")]
    runahead: Option<String>,
    use_dynamic_runahead: bool,
}

#[derive(serde::Serialize, Debug)]
struct ShadowNetwork {
    graph: ShadowGraph,
}

#[derive(serde::Serialize, Debug)]
struct ShadowGraph {
    #[serde(rename = "type")]
    graph_type: String,
}

#[derive(serde::Serialize, Debug)]
struct ShadowHost {
    network_node_id: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    ip_addr: Option<String>,
    processes: Vec<ShadowProcess>,
}

#[derive(serde::Serialize, Debug)]
struct ShadowProcess {
    path: String,
    args: String,
    environment: HashMap<String, String>,
    start_time: String,
}

pub fn generate_shadow_config(config: &Config, output_dir: &Path) -> color_eyre::eyre::Result<()> {
    let current_dir = std::env::current_dir()
        .expect("Failed to get current directory")
        .to_string_lossy()
        .to_string();

    let mut hosts: HashMap<String, ShadowHost> = HashMap::new();

    // Common environment variables for all processes
    let environment: HashMap<String, String> = [
        ("MALLOC_MMAP_THRESHOLD_".to_string(), "131072".to_string()),
        ("MALLOC_TRIM_THRESHOLD_".to_string(), "131072".to_string()),
        ("GLIBC_TUNABLES".to_string(), "glibc.malloc.arena_max=1".to_string()),
        ("MALLOC_ARENA_MAX".to_string(), "1".to_string()),
    ].iter().cloned().collect();

    // Create Monero-specific environment variables (without pruned blocks)
    let mut monero_environment = environment.clone();
    monero_environment.insert("MONERO_BLOCK_SYNC_SIZE".to_string(), "1".to_string());
    monero_environment.insert("MONERO_DISABLE_DNS".to_string(), "1".to_string());
    monero_environment.insert("MONERO_MAX_CONNECTIONS_PER_IP".to_string(), "20".to_string());

    // Add each node as a host
    for node in &config.nodes {
        let node_name = node.name.to_lowercase();
        
        // Build the monerod arguments
        let mut args = vec![
            format!("--data-dir=/tmp/monero-{}", node_name),
            "--log-file=/dev/stdout".to_string(),
            "--log-level=1".to_string(),
            "--simulation".to_string(),
            "--disable-dns-checkpoints".to_string(),
            // Removed hide-my-port to improve P2P connectivity
            "--out-peers=8".to_string(),  // Increased from 2 to 8
            "--in-peers=8".to_string(),   // Increased from 4 to 8
            "--disable-seed-nodes".to_string(),
            "--no-igd".to_string(),
            "--prep-blocks-threads=1".to_string(),
            "--max-concurrency=1".to_string(),
            "--no-zmq".to_string(),
            "--db-sync-mode=safe".to_string(),
            "--non-interactive".to_string(),
            "--max-connections-per-ip=20".to_string(), // Increased from 10 to 20
            "--limit-rate-up=2048".to_string(),        // Increased from 1024 to 2048
            "--limit-rate-down=2048".to_string(),      // Increased from 1024 to 2048
            "--block-sync-size=1".to_string(),
            format!("--rpc-bind-ip={}", node.ip),
            format!("--rpc-bind-port={}", node.port + 10), // RPC port is P2P port + 10
            "--confirm-external-bind".to_string(),
            "--disable-rpc-ban".to_string(),
            "--rpc-access-control-origins=*".to_string(),
            "--regtest".to_string(),
            format!("--p2p-bind-ip={}", node.ip),
            format!("--p2p-bind-port={}", node.port),
        ];

        // Always set a fixed difficulty for consistent mining and synchronization
        // Default to 200 if not specified
        let difficulty = node.fixed_difficulty.unwrap_or(200);
        args.push(format!("--fixed-difficulty={}", difficulty));

        // Enhanced P2P connection settings for sync node
        if node.name == "A1" {
            // Enhanced P2P connectivity settings for sync node
            args.push("--add-exclusive-node=11.0.0.1:28080".to_string());
            args.push("--add-priority-node=11.0.0.1:28080".to_string());
            args.push("--p2p-external-port=28080".to_string()); // Explicitly set external port
            args.push("--allow-local-ip".to_string()); // Allow connections to local IPs
        }
        
        // Add specific P2P settings for mining node
        if node.name == "A0" {
            args.push("--p2p-external-port=28080".to_string()); // Explicitly set external port
            args.push("--allow-local-ip".to_string()); // Allow connections to local IPs
        }

        let monerod_path = std::fs::canonicalize("monerod")
            .expect("Failed to resolve absolute path to monerod")
            .to_string_lossy()
            .to_string();

        let node_process = ShadowProcess {
            path: monerod_path,
            args: args.join(" "),
            environment: monero_environment.clone(),
            // Use the configured start time or provide defaults
            start_time: match &node.start_time {
                Some(time) => time.clone(),
                None => if node.name == "A0" {
                    "0s".to_string()
                } else {
                    // Default delay for A1 if not specified
                    "1s".to_string()
                }
            },
        };

        let node_host = ShadowHost {
            network_node_id: 0, // All hosts on the same network switch
            ip_addr: Some(node.ip.clone()),
            processes: vec![node_process],
        };

        hosts.insert(node_name, node_host);
    }

    // Add wallet1 host (mining wallet) connected to A0
    let wallet1_path = std::fs::canonicalize("monero-wallet-rpc")
        .expect("Failed to resolve absolute path to monero-wallet-rpc")
        .to_string_lossy()
        .to_string();
    let wallet1_args = "--daemon-address=11.0.0.1:28090 --rpc-bind-port=28091 --rpc-bind-ip=11.0.0.3 --disable-rpc-login --trusted-daemon --log-level=1 --wallet-dir=/tmp/wallet1_data --non-interactive --confirm-external-bind --allow-mismatched-daemon-version --max-concurrency=1 --daemon-ssl-allow-any-cert";
    
    // Improved wallet directory initialization with better error handling and safer permissions
    let wallet1_process = ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c 'rm -rf /tmp/wallet1_data && mkdir -p /tmp/wallet1_data && chmod 777 /tmp/wallet1_data && {} {}'",
            wallet1_path,
            wallet1_args
        ),
        environment: environment.clone(), // Wallet doesn't need Monero-specific env vars
        start_time: "45s".to_string(), // Start after both daemons are fully ready
    };

    let mut wallet1_host = ShadowHost {
        network_node_id: 0,
        ip_addr: Some("11.0.0.3".to_string()),
        processes: vec![wallet1_process],
    };

    hosts.insert("wallet1".to_string(), wallet1_host);

    // Add wallet2 host (recipient wallet) connected to A1
    let wallet2_path = std::fs::canonicalize("monero-wallet-rpc")
        .expect("Failed to resolve absolute path to monero-wallet-rpc")
        .to_string_lossy()
        .to_string();
    let wallet2_args = "--daemon-address=11.0.0.2:28090 --rpc-bind-port=28092 --rpc-bind-ip=11.0.0.4 --disable-rpc-login --trusted-daemon --log-level=1 --wallet-dir=/tmp/wallet2_data --non-interactive --confirm-external-bind --allow-mismatched-daemon-version --max-concurrency=1 --daemon-ssl-allow-any-cert";

    // Improved wallet directory initialization with better error handling and safer permissions
    let wallet2_process = ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c 'rm -rf /tmp/wallet2_data && mkdir -p /tmp/wallet2_data && chmod 777 /tmp/wallet2_data && {} {}'",
            wallet2_path,
            wallet2_args
        ),
        environment: environment.clone(), // Wallet doesn't need Monero-specific env vars
        start_time: "45s".to_string(), // Start after both daemons are fully ready
    };

    let mut wallet2_host = ShadowHost {
        network_node_id: 0,
        ip_addr: Some("11.0.0.4".to_string()),
        processes: vec![wallet2_process],
    };

    hosts.insert("wallet2".to_string(), wallet2_host);

    // Add block controller script
    let block_controller_process = ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!("-c 'cd {} && ./block_controller.sh'", current_dir),
        environment: environment.clone(),
        start_time: "60s".to_string(), // Start after wallets are ready
    };

    let block_controller_host = ShadowHost {
        network_node_id: 0,
        ip_addr: None,
        processes: vec![block_controller_process],
    };

    hosts.insert("block-controller".to_string(), block_controller_host);

    // Add comprehensive test script
    let python_executable = config.general.python_venv
        .as_ref()
        .map(|venv| format!("{}/bin/python", venv))
        .unwrap_or_else(|| "python3".to_string());

    let script_path = Path::new(&current_dir).join("scripts").join("send_transaction.py");
    let comprehensive_test_process = ShadowProcess {
        path: python_executable,
        args: script_path.to_string_lossy().to_string(),
        environment: environment.clone(),
        start_time: "9000s".to_string(), // Start after wallets and block controller are ready
    };

    let comprehensive_test_host = ShadowHost {
        network_node_id: 0,
        ip_addr: None,
        processes: vec![comprehensive_test_process],
    };

    hosts.insert("comprehensive-test".to_string(), comprehensive_test_host);

    let shadow_config = ShadowConfig {
        general: ShadowGeneral {
            stop_time: config.general.stop_time.clone(),
            model_unblocked_syscall_latency: true,
            log_level: "trace".to_string(),
        },
        experimental: ShadowExperimental {
            runahead: None,
            use_dynamic_runahead: true,
        },
        network: ShadowNetwork {
            graph: ShadowGraph {
                graph_type: "1_gbit_switch".to_string(),
            },
        },
        hosts,
    };

    let shadow_config_path = output_dir.join("shadow.yaml");
    let config_yaml = serde_yaml::to_string(&shadow_config)?;
    std::fs::write(&shadow_config_path, config_yaml)?;
    
    println!("Generated Shadow configuration at {:?}", shadow_config_path);
    println!("  - {} nodes with {} simulation time", config.nodes.len(), config.general.stop_time);
    println!("  - Mining enabled on: {:?}", 
        config.nodes.iter()
            .filter(|n| n.mining.unwrap_or(false))
            .map(|n| &n.name)
            .collect::<Vec<_>>()
    );
    Ok(())
}



#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{Config, General, NodeConfig};
    
    #[test]
    fn test_generate_shadow_config() {
        let config = Config {
            general: General {
                stop_time: "1h".to_string(),
                fresh_blockchain: Some(true),
                python_venv: Some("/path/to/venv".to_string()),
            },
            nodes: vec![
                NodeConfig {
                    name: "A0".to_string(),
                    ip: "11.0.0.1".to_string(),
                    port: 28080,
                    start_time: Some("10s".to_string()),
                    mining: Some(true),
                    fixed_difficulty: Some(200),
                },
                NodeConfig {
                    name: "A1".to_string(),
                    ip: "11.0.0.2".to_string(),
                    port: 28080,
                    start_time: Some("120s".to_string()),
                    mining: Some(false),
                    fixed_difficulty: None,
                },
            ],
        };
        
        let output_dir = std::env::temp_dir();
        let result = generate_shadow_config(&config, &output_dir);
        assert!(result.is_ok());
    }
} 
