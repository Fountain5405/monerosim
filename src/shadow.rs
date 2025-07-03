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
    ip_addr: Option<String>,
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

    // Assign unique IPs to all Monero nodes up front
    let mut node_ips = Vec::new();
    for i in 0..total_nodes {
        node_ips.push(format!("11.0.0.{}", i + 1));
    }
    // Assign unique IPs to test servers and client (separate subnet)
    let mut test_server_ips = vec![];
    for i in 0..3 {
        test_server_ips.push(format!("11.0.1.{}", i + 1));
    }
    let test_client_ip = "11.0.1.100".to_string();

    for node_type in &config.monero.nodes {
        let binary_path = get_system_binary_path(node_type)?;
        for i in 0..node_type.count {
            let host_name = format!("{}{}", node_type.name.to_lowercase(), i);
            let node_index = node_id_counter;
            let p2p_ip = node_ips[node_index as usize].clone();
            let monerod_args = generate_monerod_args(&host_name, node_index, &p2p_ip, &node_ips, node_type, total_nodes, node_id_counter == 0);
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
                ip_addr: Some(p2p_ip),
            };
            hosts.insert(host_name, host);
            node_id_counter += 1;
        }
    }

    // Add monitoring host that queries all nodes
    let monitor_args = generate_monitor_args(total_nodes);
    let monitor_process = ShadowProcess {
        path: monitor_args,
        args: "".to_string(),
        environment: HashMap::new(),
        start_time: "30s".to_string(), // Start after nodes have had time to initialize
        expected_final_state: "running".to_string(),
    };
    let monitor_host = ShadowHost {
        network_node_id: 0,
        processes: vec![monitor_process],
        ip_addr: None,
    };
    hosts.insert("monitor".to_string(), monitor_host);

    // Add test HTTP servers for network connectivity testing
    let test_servers = vec![
        (8080, "server1"),
        (8081, "server2"),
        (8082, "server3"),
    ];

    for (idx, (port, server_id)) in test_servers.iter().enumerate() {
        let assigned_ip = &test_server_ips[idx];
        let mut env = HashMap::new();
        env.insert("SERVER_ID".to_string(), server_id.to_string());
        let server_process = ShadowProcess {
            path: std::env::current_dir()?.join("test_network.py").to_string_lossy().to_string(),
            args: format!("{} {} {}", assigned_ip, port, server_id),
            environment: env,
            start_time: "10s".to_string(),
            expected_final_state: "running".to_string(),
        };
        let server_host = ShadowHost {
            network_node_id: 0,
            processes: vec![server_process],
            ip_addr: Some(assigned_ip.clone()),
        };
        hosts.insert(format!("testserver{}", server_id.replace("server", "")), server_host);
    }

    // Add test client
    let client_process = ShadowProcess {
        path: std::env::current_dir()?.join("test_client.py").to_string_lossy().to_string(),
        args: "".to_string(),
        environment: HashMap::new(),
        start_time: "40s".to_string(),
        expected_final_state: "running".to_string(),
    };
    let client_host = ShadowHost {
        network_node_id: 0,
        processes: vec![client_process],
        ip_addr: Some(test_client_ip.clone()),
    };
    hosts.insert("testclient".to_string(), client_host);

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
        "--max-concurrency=1".to_string(),
        format!("--p2p-bind-ip={}", p2p_ip),
        format!("--p2p-bind-port={}", p2p_port),
        format!("--rpc-bind-ip={}", p2p_ip),
        "--confirm-external-bind".to_string(),
        format!("--rpc-bind-port={}", rpc_port),
        "--no-igd".to_string(),
        "--no-zmq".to_string(),
        "--fixed-difficulty=100".to_string(),
        "--non-interactive".to_string(),
    ];
    // Add exclusive node config for all other nodes with their unique ports and IPs
    for (i, peer_ip) in node_ips.iter().enumerate() {
        if i as u32 != node_index {
            let peer_port = 28080 + i as u32;
            args.push(format!("--add-exclusive-node={}:{}", peer_ip, peer_port));
        }
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
        assert!(yaml.contains("A0:"));
        assert!(yaml.contains("A1:"));
    }
} 