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
            
            let process = ShadowProcess {
                path: binary_path.clone(),
                args: monerod_args,
                environment: HashMap::new(),
                start_time: "5s".to_string(),
                expected_final_state: "running".to_string(),
            };
            
            let host = ShadowHost {
                network_node_id: node_id_counter,
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
    };
    
    // Serialize to YAML, then manually insert use_shortest_path: false
    let mut yaml = serde_yaml::to_string(&shadow_config)?;
    // Insert use_shortest_path: false under network
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
        "--log-level=1".to_string(),
        "--log-file=/dev/stdout".to_string(),
        format!("--data-dir=/tmp/monero-{}", host_name),
        "--non-interactive".to_string(),  // Run in non-interactive mode to avoid stdin issues
        "--no-sync".to_string(),  // Don't sync blockchain to reduce complexity
        "--disable-dns-checkpoints".to_string(),  // Disable DNS checkpoints
        "--disable-rpc-ban".to_string(),  // Disable RPC ban
        "--max-concurrency=1".to_string(),  // Limit concurrency to reduce syscall complexity
        "--p2p-bind-port=0".to_string(),  // Let the OS choose a random port
        "--rpc-bind-port=0".to_string(),  // Let the OS choose a random port
        "--no-igd".to_string(),  // Disable UPnP port mapping
        "--no-zmq".to_string(),  // Disable ZMQ RPC server
    ];

    // Add mining configuration for the first node
    if is_miner {
        // Temporarily disable mining to test basic Shadow integration
        // args.push("--start-mining=9wviCeQ2DUXEK6ypCW6V6QKFJYivE2cun5U8Jesjscg4eK4q7npfqDUJ3qLR1cdJuLB4NBu9tS7VnssF5xKhdm8eK6tW8".to_string());
        // args.push("--mining-threads=1".to_string());
    }

    args.join(" ")
}

fn generate_simple_network_graph(node_count: u32) -> String {
    let mut graph = String::from("graph [\n");
    
    // Add nodes
    for i in 0..node_count {
        graph.push_str(&format!("  node [\n    id {}\n    host_bandwidth_down \"100 Mbit\"\n    host_bandwidth_up \"100 Mbit\"\n  ]\n", i));
    }
    
    // Add one edge per unordered pair (including self-loops)
    for i in 0..node_count {
        for j in i..node_count {
            let latency = if i == j { "1 ns" } else { "50 ms" };
            let packet_loss = if i == j { "0.0" } else { "0.001" };
            graph.push_str(&format!("  edge [\n    source {}\n    target {}\n    latency \"{}\"\n    packet_loss {}\n  ]\n", i, j, latency, packet_loss));
        }
    }
    
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