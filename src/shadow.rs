use crate::config::Config;
use serde_yaml;
use std::collections::HashMap;
use std::path::Path;


#[derive(serde::Serialize, Debug)]
struct ShadowConfig {
    general: ShadowGeneral,
    network: ShadowNetwork,
    hosts: HashMap<String, ShadowHost>,
}

#[derive(serde::Serialize, Debug)]
struct ShadowGeneral {
    stop_time: String,
    model_unblocked_syscall_latency: bool,
    log_level: String,
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
    let mut hosts = HashMap::new();
    
    // Clear blockchain data if fresh_blockchain is enabled
    if config.general.fresh_blockchain.unwrap_or(false) {
        for node in &config.nodes {
            let host_name = node.name.to_lowercase();
            let data_dir = format!("/tmp/monero-{}", host_name);
            // Clean up any existing blockchain data
            std::process::Command::new("rm")
                .args(["-rf", &data_dir])
                .output()
                .ok(); // Ignore errors if directory doesn't exist
        }
    }
    
    let mut environment = HashMap::new();
    environment.insert("MALLOC_ARENA_MAX".to_string(), "1".to_string());
    environment.insert("MALLOC_MMAP_THRESHOLD_".to_string(), "131072".to_string());
    environment.insert("MALLOC_TRIM_THRESHOLD_".to_string(), "131072".to_string());
    environment.insert("GLIBC_TUNABLES".to_string(), "glibc.malloc.arena_max=1".to_string());

    // Generate hosts for each node
    for (node_index, node) in config.nodes.iter().enumerate() {
        let host_name = node.name.to_lowercase();
        let start_time = node.start_time.as_ref().unwrap_or(&"10s".to_string()).clone();
        let rpc_port = node.port + 10; // RPC port is P2P port + 10
        
        // Build monerod arguments
        let mut args = vec![
            format!("--data-dir=/tmp/monero-{}", host_name),
            "--log-file=/dev/stdout".to_string(),
            "--log-level=2".to_string(),
            
            // === TESTNET CONFIGURATION ===
            "--testnet".to_string(),
            "--disable-dns-checkpoints".to_string(),
            
            // === FORCE LOCAL-ONLY P2P ===
            "--hide-my-port".to_string(),
            "--out-peers=8".to_string(),
            "--in-peers=8".to_string(),
            "--disable-seed-nodes".to_string(),
            "--no-igd".to_string(),
            
            // === SHADOW COMPATIBILITY ===
            "--prep-blocks-threads=1".to_string(),
            "--max-concurrency=1".to_string(),
            "--no-zmq".to_string(),
            "--db-sync-mode=safe".to_string(),
            "--non-interactive".to_string(),
            "--max-connections-per-ip=50".to_string(),
            
            // === RPC CONFIGURATION ===
            format!("--rpc-bind-ip={}", node.ip),
            format!("--rpc-bind-port={}", rpc_port),
            "--confirm-external-bind".to_string(),
            "--disable-rpc-ban".to_string(),
            
            // === P2P CONFIGURATION ===  
            format!("--p2p-bind-ip={}", node.ip),
            format!("--p2p-bind-port={}", node.port),
        ];

        // Add fixed difficulty if specified
        if let Some(difficulty) = node.fixed_difficulty {
            args.push(format!("--fixed-difficulty={}", difficulty));
        }

        // Add exclusive peer connections to nodes with a "lower" name to prevent loops
        for other_node in &config.nodes {
            if other_node.name < node.name {
                args.push(format!("--add-exclusive-node={}:{}", other_node.ip, other_node.port));
            }
        }

        // Add mining configuration if enabled
        if node.mining.unwrap_or(false) {
            // Generate a deterministic testnet address for mining based on node name
            let mining_address = match node.name.as_str() {
                "A0" => "9wviCeWe2D8XS82k2ovp5EUYLzBt9pYNW2LXUFsZiv8S3Mt21FZ5qQaAroko1enzw3eGr9qC7X1D7Geoo2RrAotYPwq9Gm8",
                _ => "9wviCeWe2D8XS82k2ovp5EUYLzBt9pYNW2LXUFsZiv8S3Mt21FZ5qQaAroko1enzw3eGr9qC7X1D7Geoo2RrAotYPwq9Gm8"
            };
            args.push(format!("--start-mining={}", mining_address));
            args.push("--mining-threads=1".to_string());
            // Use foreground mining instead of background mining for Shadow compatibility
            // Background mining waits for system triggers that don't exist in virtualized environments
        }

        let monerod_process = ShadowProcess {
            path: std::fs::canonicalize("builds/A/monero/bin/monerod")
                .expect("Failed to resolve absolute path to monerod")
                .to_string_lossy()
                .to_string(),
            args: args.join(" "),
            environment: environment.clone(),
            start_time: start_time.clone(),
        };

        let mut processes = vec![monerod_process];

        let host = ShadowHost {
            network_node_id: 0,
            processes,
        };

        hosts.insert(host_name, host);
    }

    // Add monitoring process
    let current_dir = std::env::current_dir()
        .expect("Failed to get current directory")
        .to_string_lossy()
        .to_string();
    let monitor_process = ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!("-c 'cd {} && while true; do ./monitor_script.sh; sleep 30; done'", current_dir),
        environment: environment.clone(),
        start_time: "60s".to_string(),
    };

    let monitor_host = ShadowHost {
        network_node_id: 0,
        processes: vec![monitor_process],
    };

    hosts.insert("monitor".to_string(), monitor_host);

    let shadow_config = ShadowConfig {
        general: ShadowGeneral {
            stop_time: config.general.stop_time.clone(),
            model_unblocked_syscall_latency: true,
            log_level: "trace".to_string(),
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