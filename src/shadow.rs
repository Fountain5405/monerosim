use crate::config::{Config, NodeType};
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
    
    // Environment variables based on EthShadow approach for threading compatibility
    let mut environment = HashMap::new();
    environment.insert("MALLOC_ARENA_MAX".to_string(), "1".to_string());
    environment.insert("MALLOC_MMAP_THRESHOLD_".to_string(), "131072".to_string());
    environment.insert("MALLOC_TRIM_THRESHOLD_".to_string(), "131072".to_string());
    environment.insert("GLIBC_TUNABLES".to_string(), "glibc.malloc.arena_max=1".to_string());

    let mut node_counter = 0;
    
    // Generate hosts for each node type
    for node_type in &config.monero.nodes {
        for _ in 0..node_type.count {
            let host_name = format!("a{}", node_counter);
            let node_ip = format!("11.0.0.{}", node_counter + 1);
            let p2p_port = 28080 + node_counter;
            let rpc_port = 28090 + node_counter;
            let start_time = format!("{}s", node_counter * 10);
            
            // Build peer connections - each node connects to node 0 (bootstrap)
            let mut args = vec![
                format!("--data-dir=/tmp/monero-{}", host_name),
                "--log-file=/tmp/monerod.log".to_string(),
                "--log-level=4".to_string(),
                
                // === SHADOW COMPATIBILITY: Single-threaded operation ===
                "--no-sync".to_string(),               // Disable blockchain sync (prevents threading loops)
                "--offline".to_string(),               // Disable P2P networking (Shadow will simulate)
                "--prep-blocks-threads=1".to_string(), // Single-threaded block processing
                "--max-concurrency=1".to_string(),     // Single-threaded for all operations
                "--no-zmq".to_string(),                // Disable ZMQ (extra thread management)
                
                // === MINIMAL OPERATION: Reduce threading pressure ===
                "--db-sync-mode=safe".to_string(),     // Safer database operations
                "--block-sync-size=1".to_string(),     // Minimal batch processing
                "--fast-block-sync=0".to_string(),     // Disable fast sync (avoids threading)
                "--non-interactive".to_string(),       // No stdin threads
                
                // === P2P SETTINGS: Conservative limits ===
                "--out-peers=2".to_string(),
                "--in-peers=4".to_string(),
                "--limit-rate-up=1024".to_string(),
                "--limit-rate-down=1024".to_string(),
                "--max-connections-per-ip=1".to_string(),
                "--no-igd".to_string(),
                
                // === RPC CONFIGURATION ===
                format!("--rpc-bind-ip={}", node_ip),
                format!("--rpc-bind-port={}", rpc_port),
                "--confirm-external-bind".to_string(),
                "--disable-rpc-ban".to_string(),
                
                // === P2P CONFIGURATION ===  
                format!("--p2p-bind-ip={}", node_ip),
                format!("--p2p-bind-port={}", p2p_port),
            ];

            // Add peer connections for non-bootstrap nodes (but P2P disabled anyway)
            if node_counter > 0 {
                args.push(format!("--add-peer=11.0.0.1:28080"));
            }

            let process = ShadowProcess {
                path: format!("builds/{}/monero/build/Linux/_HEAD_detached_at_v0.18.4.0_/release/bin/monerod", node_type.name),
                args: args.join(" "),
                environment: environment.clone(),
                start_time,
            };

            let host = ShadowHost {
                network_node_id: 0, // All on same network segment
                processes: vec![process],
            };

            hosts.insert(host_name, host);
            node_counter += 1;
        }
    }

    let shadow_config = ShadowConfig {
        general: ShadowGeneral {
            stop_time: "10m".to_string(), // Extended time to capture P2P connections
            model_unblocked_syscall_latency: true,
            log_level: "info".to_string(),
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
    
    println!("Generated EthShadow-style Shadow configuration at {:?}", shadow_config_path);
    println!("  - {} nodes with 10-minute simulation time", node_counter);
    println!("  - P2P connections configured to bootstrap node");
    println!("  - EthShadow environment variables applied");
    Ok(())
}

fn get_system_binary_path(node_type: &NodeType) -> Result<String, color_eyre::eyre::Error> {
    // Use Shadow-compatible monerod binaries from our builds
    let build_path = format!("builds/{}/monero/bin/monerod", node_type.name);
    let canonical_path = std::fs::canonicalize(&build_path)
        .map_err(|e| color_eyre::eyre::eyre!("Failed to resolve Shadow-compatible monerod path '{}': {}", build_path, e))?;
    Ok(canonical_path.to_string_lossy().to_string())
}

fn generate_monerod_args(host_name: &str, node_index: u32, p2p_ip: &str, node_ips: &Vec<String>, _node_type: &NodeType, total_nodes: u32, _is_miner: bool) -> String {
    // Calculate unique P2P port for this node (base port 28080 + node_index)
    let p2p_port = 28080 + node_index;
    // Calculate unique RPC port for this node (base port 28090 + node_index)
    let rpc_port = 28090 + node_index;
    
    let mut args = vec![
        "--testnet".to_string(),
        "--log-level=4".to_string(),  // Detailed logging for debugging
        "--log-file=/dev/stdout".to_string(),
        format!("--data-dir=/tmp/monero-{}", host_name),
        "--disable-dns-checkpoints".to_string(),
        "--disable-rpc-ban".to_string(),
        
        // === ETHSHADOW APPROACH: MINIMAL flags, rely on environment variables ===
        // Basic P2P configuration
        format!("--p2p-bind-ip={}", p2p_ip),
        format!("--p2p-bind-port={}", p2p_port),
        
        // RPC configuration
        "--rpc-bind-ip=0.0.0.0".to_string(),
        format!("--rpc-bind-port={}", rpc_port),
        
        // Basic optimizations only
        "--out-peers=2".to_string(),
        "--in-peers=4".to_string(),
        "--limit-rate-up=1024".to_string(),
        "--limit-rate-down=1024".to_string(),
        
        // Essential compatibility flags  
        "--rpc-access-control-origins=*".to_string(),
        "--confirm-external-bind".to_string(),
        "--non-interactive".to_string(),
    ];

    // Add simple peer connections (only to earlier nodes)
    if node_index > 0 {
        // Connect only to the first node for simplicity
        args.push(format!("--add-peer={}:{}", node_ips[0], 28080));
    }

    args.join(" ")
}

fn generate_monitor_args(_total_nodes: u32) -> String {
    // Return the path to our monitoring script
    "./monitor_script.sh".to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::Config;
    
    #[test]
    fn test_generate_shadow_config() {
        let config = Config {
            general: crate::config::General {
                stop_time: "1h".to_string(),
            },
            monero: crate::config::Monero {
                nodes: vec![
                    crate::config::NodeType {
                        name: "A".to_string(),
                        count: 2,
                        base_commit: Some("v0.18.4.0".to_string()),
                        patches: Some(vec!["test.patch".to_string()]),
                        prs: None,
                        base: None,
                    },
                ],
            },
        };
        
        let builds_dir = Path::new("/tmp/builds");
        let result = generate_shadow_config(&config, builds_dir);
        assert!(result.is_ok());
        
        let yaml = result.unwrap();
        assert!(yaml.contains("general:"));
        assert!(yaml.contains("network:"));
        assert!(yaml.contains("hosts:"));
        assert!(yaml.contains("a0:"));
        assert!(yaml.contains("a1:"));
    }
} 