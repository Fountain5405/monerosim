use crate::config::{Config, NodeType};
use serde_yaml;
use std::collections::HashMap;
use std::path::Path;
use walkdir;

#[derive(Debug, serde::Serialize)]
struct ShadowConfig {
    general: ShadowGeneral,
    network: ShadowNetwork,
    hosts: HashMap<String, ShadowHost>,
    experimental: ShadowExperimental,
}

#[derive(Debug, serde::Serialize)]
struct ShadowExperimental {
    use_preload_libc: bool,
    use_preload_openssl_rng: bool,
    use_new_tcp: bool,
}

#[derive(Debug, serde::Serialize)]
struct ShadowGeneral {
    stop_time: String,
}

#[derive(Debug, serde::Serialize)]
struct ShadowNetwork {
    graph: ShadowGraph,
}

#[derive(Debug, serde::Serialize)]
struct ShadowGraph {
    #[serde(rename = "type")]
    graph_type: String,
    inline: String,
}

#[derive(Debug, serde::Serialize)]
struct ShadowHost {
    network_node_id: u32,
    processes: Vec<ShadowProcess>,
}

#[derive(Debug, serde::Serialize)]
struct ShadowProcess {
    path: String,
    args: String,
    environment: HashMap<String, String>,
    start_time: String,
    shutdown_signal: String,
    expected_final_state: String,
}

pub fn generate_shadow_config(config: &Config, builds_dir: &Path) -> Result<String, color_eyre::eyre::Error> {
    let mut hosts = HashMap::new();
    let mut node_id_counter = 0;
    let total_nodes: u32 = config.monero.nodes.iter().map(|nt| nt.count).sum();
    
    // Generate hosts for each node type
    for node_type in &config.monero.nodes {
        // Use system binary path based on node type
        let binary_path = get_system_binary_path(node_type)?;
        
        for i in 0..node_type.count {
            let host_name = format!("{}{}", node_type.name.to_lowercase(), i);
            let monerod_args = generate_monerod_args(&host_name, node_id_counter, node_type, total_nodes, node_id_counter == 0);
            
            // Set up environment for Shadow preload interposition
            let mut environment = HashMap::new();
            // Enable Shadow's preload libraries for syscall interposition
            environment.insert("LD_PRELOAD".to_string(), "libshadow_injector.so:libshadow_libc.so".to_string());
            // Disable some problematic features
            environment.insert("SHADOW_LOG_LEVEL".to_string(), "info".to_string());
            
            let process = ShadowProcess {
                path: binary_path.clone(),
                args: monerod_args,
                environment,
                start_time: "0s".to_string(),
                shutdown_signal: "SIGTERM".to_string(),
                expected_final_state: "running".to_string(),
            };
            
            // Use the same network_node_id for all nodes (like ethshadow does)
            // This allows multiple hosts to share the same network node and connect to each other
            let host = ShadowHost {
                network_node_id: 0,  // All nodes use the same network node
                processes: vec![process],
            };
            
            hosts.insert(host_name, host);
            node_id_counter += 1;
        }
    }
    
    // Generate a simple network topology - just one node for now
    let network_graph = generate_simple_network_graph(node_id_counter);
    
    let shadow_config = ShadowConfig {
        general: ShadowGeneral {
            stop_time: config.general.stop_time.clone(),
        },
        network: ShadowNetwork {
            graph: ShadowGraph {
                graph_type: "gml".to_string(),
                inline: network_graph,
            },
        },
        hosts,
        experimental: ShadowExperimental {
            use_preload_libc: true,
            use_preload_openssl_rng: true,
            use_new_tcp: false,  // Use legacy TCP implementation
        },
    };
    
    // Serialize to YAML, then manually insert use_shortest_path: false (like ethshadow)
    let mut yaml = serde_yaml::to_string(&shadow_config)?;
    // Insert use_shortest_path: false under network to enable direct connections
    yaml = yaml.replacen("graph:", "use_shortest_path: false\n  graph:", 1);
    Ok(yaml)
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

fn generate_monerod_args(host_name: &str, node_index: u32, node_type: &NodeType, total_nodes: u32, is_miner: bool) -> String {
    let mut args = vec![
        "--testnet".to_string(),
        "--log-level=2".to_string(),  // Increase log level to see more details
        "--log-file=/dev/stdout".to_string(),
        format!("--data-dir=/tmp/monero-{}", host_name),
        "--non-interactive".to_string(),  // Run in non-interactive mode to avoid stdin issues
        "--no-sync".to_string(),  // Don't sync blockchain to reduce complexity
        "--disable-dns-checkpoints".to_string(),  // Disable DNS checkpoints
        "--disable-rpc-ban".to_string(),  // Disable RPC ban
        "--max-concurrency=1".to_string(),  // Limit concurrency to reduce syscall complexity
        format!("--p2p-bind-ip=11.0.0.{}", node_index + 1), // Bind to unique simulated IP
        format!("--p2p-bind-port={}", 28080 + node_index),  // Use predictable ports starting from 28080
        "--rpc-bind-port=0".to_string(),  // Let the OS choose a random port
        "--no-igd".to_string(),  // Disable UPnP port mapping
        "--no-zmq".to_string(),  // Disable ZMQ RPC server
    ];

    // Add exclusive node configuration to prevent external connections
    // Each node will only connect to other nodes in our simulation
    for i in 0..total_nodes {
        if i != node_index {
            // Add other nodes as exclusive peers (IP addresses from Shadow network)
            let peer_ip = format!("11.0.0.{}", i + 1);
            args.push(format!("--add-exclusive-node={}:{}", peer_ip, 28080 + i));
        }
    }
    
    // Add additional network options to help with connection issues
    // Allow multiple connections like ethshadow does
    args.push("--out-peers=8".to_string());  // Allow multiple outbound connections
    args.push("--in-peers=8".to_string());   // Allow multiple inbound connections
    args.push("--max-connections-per-ip=8".to_string());  // Allow multiple connections per IP
    args.push("--limit-rate-up=1024".to_string());  // Limit upload rate
    args.push("--limit-rate-down=1024".to_string());  // Limit download rate

    // Add mining configuration for the first node
    if is_miner {
        args.push("--start-mining=A1xAe2Cm2fCPhMNXprWcb9CgQKbEZtnqU6TXp4XJ83R8T4HJ5bkAxKNCAMofNRH22TcFw2yewgN1jd8dywsRG4cWE7GAbkd".to_string());
        args.push("--mining-threads=1".to_string());
    }

    args.join(" ")
}

fn generate_simple_network_graph(node_count: u32) -> String {
    let mut graph = String::from("graph [\n");
    
    // Create a single network node (like ethshadow does)
    // All hosts will share this same network node, allowing them to connect to each other
    graph.push_str("  node [\n    id 0\n    host_bandwidth_down \"100 Mbit\"\n    host_bandwidth_up \"100 Mbit\"\n  ]\n");
    
    // Add self-loop for the single node (required by Shadow)
    graph.push_str("  edge [\n    source 0\n    target 0\n    latency \"1 ns\"\n    packet_loss 0.0\n  ]\n");
    
    graph.push_str("]");
    graph
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
        assert!(yaml.contains("A0:"));
        assert!(yaml.contains("A1:"));
    }
} 