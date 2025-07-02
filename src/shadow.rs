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
    model_unblocked_syscall_latency: bool,
    log_level: String,
}

#[derive(Debug, serde::Serialize)]
struct ShadowNetwork {
    graph: ShadowGraph,
}

#[derive(Debug, serde::Serialize)]
struct ShadowGraph {
    #[serde(rename = "type")]
    graph_type: String,
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

pub fn generate_shadow_config(config: &Config, _builds_dir: &Path) -> Result<String, color_eyre::eyre::Error> {
    let mut hosts = HashMap::new();
    let total_nodes: u32 = config.monero.nodes.iter().map(|nt| nt.count).sum();
    let mut node_id_counter = 0;

    for node_type in &config.monero.nodes {
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
                network_node_id: 0,
                processes: vec![process],
            };
            hosts.insert(host_name, host);
            node_id_counter += 1;
        }
    }

    let shadow_config = ShadowConfig {
        general: ShadowGeneral {
            stop_time: config.general.stop_time.clone(),
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
    let yaml = serde_yaml::to_string(&shadow_config)?;
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

fn generate_monerod_args(host_name: &str, node_index: u32, _node_type: &NodeType, total_nodes: u32, _is_miner: bool) -> String {
    // Derive the p2p-bind-ip for this node
    let p2p_ip = format!("11.0.0.{}", node_index + 1);
    let mut args = vec![
        "--testnet".to_string(),
        "--log-level=1".to_string(), // match hand-written config
        "--log-file=/dev/stdout".to_string(),
        format!("--data-dir=/tmp/monero-{}", host_name),
        "--disable-dns-checkpoints".to_string(),
        "--disable-rpc-ban".to_string(),
        "--max-concurrency=1".to_string(),
        format!("--p2p-bind-ip={}", p2p_ip),
        "--no-igd".to_string(),
        "--no-zmq".to_string(),
        "--fixed-difficulty=100".to_string(),
        "--non-interactive".to_string(),
    ];
    // Add exclusive node config for all other nodes
    for i in 0..total_nodes {
        if i != node_index {
            let peer_ip = format!("11.0.0.{}", i + 1);
            args.push(format!("--add-exclusive-node={}:28080", peer_ip));
        }
    }
    args.join(" ")
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