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
    start_time: String,
}

pub fn generate_shadow_config(config: &Config, _builds_dir: &Path) -> Result<String, color_eyre::eyre::Error> {
    let mut hosts = HashMap::new();
    let mut node_id_counter = 0u32;
    
    // Generate IP addresses for each node
    let mut node_ips = Vec::new();
    let total_nodes: u32 = config.monero.nodes.iter().map(|n| n.count).sum();
    
    for i in 0..total_nodes {
        node_ips.push(format!("11.0.0.{}", i + 1));
    }

    // === OPTIMIZED MONERO NODES ONLY ===
    for node_type in &config.monero.nodes {
        for _i in 0..node_type.count {
            let host_name = format!("a{}", node_id_counter);
            let p2p_ip = &node_ips[node_id_counter as usize];
            
            // === SHADOW OPTIMIZATION 2: Staggered Startup Timing ===
            // Prevent "thundering herd" by staggering node startups
            let startup_delay = node_id_counter * 10; // 10 second intervals
            let start_time = format!("{}s", startup_delay);
            
            let monerod_args = generate_monerod_args(
                &host_name,
                node_id_counter,
                p2p_ip,
                &node_ips,
                node_type,
                total_nodes,
                false, // is_miner
            );

            hosts.insert(host_name, ShadowHost {
                network_node_id: 0, // All nodes on same network
                processes: vec![ShadowProcess {
                    path: "builds/A/monero/build/Linux/_HEAD_detached_at_v0.18.4.0_/release/bin/monerod".to_string(),
                    args: monerod_args,
                    start_time, // Staggered startup
                }],
            });

            node_id_counter += 1;
        }
    }

    // === SHADOW OPTIMIZATION 2: Enhanced Network Configuration ===
    let shadow_config = ShadowConfig {
        general: ShadowGeneral {
            stop_time: config.general.stop_time.clone(),
            model_unblocked_syscall_latency: true, // Better syscall modeling
            log_level: "info".to_string(),
        },
        network: ShadowNetwork {
            graph: ShadowGraph {
                // Use built-in topology optimized for Shadow
                graph_type: "1_gbit_switch".to_string(),
            },
        },
        hosts,
    };

    let yaml_string = serde_yaml::to_string(&shadow_config)?;
    Ok(yaml_string)
}

fn get_system_binary_path(node_type: &NodeType) -> Result<String, color_eyre::eyre::Error> {
    // For now, use simple mapping based on node type name
    // A nodes use v0.18.4.0, B nodes use master
    match node_type.name.as_str() {
        "A" => Ok("/usr/local/bin/monerod-v0.18.4.0".to_string()),
        "B" => Ok("/usr/local/bin/monerod-master".to_string()),
        _ => Err(color_eyre::eyre::eyre!("Unknown node type: {}", node_type.name))
    }
}

fn generate_monerod_args(host_name: &str, node_index: u32, p2p_ip: &str, node_ips: &Vec<String>, _node_type: &NodeType, total_nodes: u32, _is_miner: bool) -> String {
    // Calculate unique P2P port for this node (base port 28080 + node_index)
    let p2p_port = 28080 + node_index;
    // Calculate unique RPC port for this node (base port 28090 + node_index)
    let rpc_port = 28090 + node_index;
    
    let mut args = vec![
        "--testnet".to_string(),
        "--log-level=2".to_string(),
        "--log-file=/dev/stdout".to_string(),
        format!("--data-dir=/tmp/monero-{}", host_name),
        "--disable-dns-checkpoints".to_string(),
        "--disable-rpc-ban".to_string(),
        
        // === SHADOW OPTIMIZATION 1: Reduce Monero's Network Aggressiveness ===
        
        // Drastically reduce concurrent connections to ease Shadow's TCP load
        "--out-peers=2".to_string(),          // Default: 8, reduced to 2
        "--in-peers=4".to_string(),           // Default: 64, reduced to 4
        "--max-connections-per-ip=1".to_string(), // Prevent connection storms
        
        // Bandwidth throttling to reduce data volume Shadow must handle
        "--limit-rate-up=1024".to_string(),   // 1MB/s upload limit
        "--limit-rate-down=1024".to_string(), // 1MB/s download limit
        
        // Conservative sync behavior to reduce request frequency
        "--block-sync-size=1".to_string(),    // Default: 20, sync 1 block at a time
        "--prep-blocks-threads=1".to_string(), // Single-threaded block prep
        
        // Reduced threading to lower system complexity for Shadow
        "--max-concurrency=1".to_string(),    // Single-threaded operation
        
        // === SHADOW COMPATIBILITY: Minimize threading issues ===
        "--offline".to_string(),              // Disable P2P to avoid thread issues
        
        // Network timing optimizations for Shadow's discrete-event scheduling
        format!("--p2p-bind-ip={}", p2p_ip),
        format!("--p2p-bind-port={}", p2p_port),
        format!("--rpc-bind-ip={}", p2p_ip),
        format!("--rpc-bind-port={}", rpc_port),
        "--rpc-access-control-origins=*".to_string(),
        "--confirm-external-bind".to_string(),
        "--non-interactive".to_string(),
    ];

    // Only add seed nodes if not running in offline mode
    // (Commented out since we're using --offline for this test)
    // Add seed nodes (other nodes in simulation) with conservative connection strategy
    // Only connect to a subset to prevent connection storms
    // let max_seed_nodes = std::cmp::min(total_nodes.saturating_sub(1), 2); // Max 2 seed connections
    // for (i, ip) in node_ips.iter().enumerate() {
    //     if i as u32 != node_index && (i as u32) < max_seed_nodes {
    //         let seed_port = 28080 + i as u32;
    //         args.push(format!("--add-peer={}:{}", ip, seed_port));
    //     }
    // }

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