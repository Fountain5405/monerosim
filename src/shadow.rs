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
    println!("Generating optimized Shadow configuration for Monero...");

    // Calculate total nodes
    let total_nodes: u32 = config.monero.nodes.iter().map(|n| n.count).sum();
    
    // Generate node IPs  
    let node_ips: Vec<String> = (1..=total_nodes)
        .map(|i| format!("11.0.0.{}", i))
        .collect();

    let mut hosts = HashMap::new();
    let mut node_id_counter = 0u32;

    // === OPTIMIZED MONERO NODES ===
    for node_type in &config.monero.nodes {
        for _ in 0..node_type.count {
            let host_name = format!("a{}", node_id_counter);
            let p2p_ip = &node_ips[node_id_counter as usize];
            
            // CRITICAL: EthShadow-style staggered startup timing
            let start_time = format!("{}s", node_id_counter * 10);
            
            let monerod_args = generate_monerod_args(
                &host_name,
                node_id_counter,
                p2p_ip,
                &node_ips,
                node_type,
                total_nodes,
                false, // is_miner
            );

            // CRITICAL: EthShadow-style environment variables for threading compatibility
            let mut environment = HashMap::new();
            
            // Based on Shadow compatibility notes - these are the key fixes:
            environment.insert("MALLOC_ARENA_MAX".to_string(), "1".to_string());     // Limit memory arenas
            environment.insert("MALLOC_MMAP_THRESHOLD_".to_string(), "131072".to_string()); // Control mmap usage
            environment.insert("MALLOC_TRIM_THRESHOLD_".to_string(), "131072".to_string()); // Control memory trimming
            environment.insert("GLIBC_TUNABLES".to_string(), "glibc.malloc.arena_max=1".to_string()); // Glibc tuning
            
            hosts.insert(host_name, ShadowHost {
                network_node_id: 0, // All on same network
                processes: vec![ShadowProcess {
                    path: "builds/A/monero/build/Linux/_HEAD_detached_at_v0.18.4.0_/release/bin/monerod".to_string(),
                    args: monerod_args,
                    environment, // CRITICAL: This fixes threading issues!
                    start_time,
                }],
            });

            node_id_counter += 1;
        }
    }

    // ETHSHADOW APPROACH: Shadow configuration with threading compatibility 
    let shadow_config = ShadowConfig {
        general: ShadowGeneral {
            stop_time: config.general.stop_time.clone(),
            model_unblocked_syscall_latency: true, // CRITICAL: This fixes busy loops and threading issues
            log_level: "info".to_string(),
        },
        network: ShadowNetwork {
            graph: ShadowGraph {
                graph_type: "1_gbit_switch".to_string(), // Simplified topology  
            },
        },
        hosts,
    };

    // Write Shadow configuration
    let shadow_config_path = output_dir.join("shadow.yaml");
    let shadow_config_file = std::fs::File::create(&shadow_config_path)?;
    serde_yaml::to_writer(shadow_config_file, &shadow_config)?;

    println!("✅ EthShadow-style optimized Shadow configuration generated!");
    println!("   - Environment-based threading compatibility");
    println!("   - model_unblocked_syscall_latency enabled");
    println!("   - Staggered startup timing");
    println!("   - Simplified networking optimizations");

    Ok(())
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