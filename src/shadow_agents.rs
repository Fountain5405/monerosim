//! Shadow agent configuration and processing.
//!
//! This module handles the creation and configuration of Shadow simulation
//! agents, including user agents, miners, block controllers, and pure script agents.
//! It manages the complex logic for peer discovery, IP allocation, and process
//! configuration within the Shadow network simulator environment.

use crate::config_v2::{AgentDefinitions, PeerMode, Config, Network};
use crate::gml_parser::{GmlGraph, parse_gml_file, validate_topology, get_autonomous_systems};
use crate::shadow::{AgentInfo, AgentRegistry, ShadowHost, ShadowProcess, MinerRegistry, MinerInfo, ShadowConfig, ShadowGeneral, ShadowExperimental, ShadowNetwork, ShadowGraph};
use crate::topology::{distribute_agents_across_topology, Topology, generate_topology_connections};
use crate::utils::duration::parse_duration_to_seconds;
use crate::utils::validation::validate_topology_config;
use crate::ip::{GlobalIpRegistry, AsSubnetManager, AgentType, get_agent_ip};
use crate::orchestrator::generate_gml_network_config;
use std::collections::HashMap;
use std::path::Path;




/// Add a wallet process to the processes list
fn add_wallet_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    agent_rpc_port: u16,
    wallet_rpc_port: u16,
    _wallet_path: &str,
    environment: &HashMap<String, String>,
    index: usize,
    wallet_start_time: &str,
) {
    let wallet_name = format!("{}_wallet", agent_id);
    
    // Create wallet JSON content
    let _wallet_json_content = format!(
        r#"{{"version": 1,"filename": "{}","scan_from_height": 0,"password": "","viewkey": "","spendkey": "","seed": "","seed_passphrase": "","address": "","restore_height": 0,"autosave_current": true}}"#,
        wallet_name
    );

    // Get the absolute path to the wallet launcher script
    let _launcher_path = std::env::current_dir()
        .unwrap()
        .join("scripts/wallet_launcher.sh")
        .to_string_lossy()
        .to_string();

    // Calculate wallet cleanup start time (2 seconds before wallet start)
    let cleanup_start_time = if let Ok(wallet_seconds) = parse_duration_to_seconds(wallet_start_time) {
        format!("{}s", wallet_seconds.saturating_sub(2))
    } else {
        format!("{}s", 48 + index * 2) // Fallback
    };

    // First, clean up any existing wallet files and create the wallet directory
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c 'rm -rf /tmp/monerosim_shared/{}_wallet && mkdir -p /tmp/monerosim_shared/{}_wallet'",
            agent_id, agent_id
        ),
        environment: environment.clone(),
        start_time: cleanup_start_time, // Start earlier to ensure cleanup completes
    });

    // Launch wallet RPC directly - it will create wallets on demand
    let wallet_path = "/usr/local/bin/monero-wallet-rpc".to_string();

    let wallet_args = format!(
        "--daemon-address=http://{}:{} --rpc-bind-port={} --rpc-bind-ip={} --disable-rpc-login --trusted-daemon --log-level=1 --wallet-dir=/tmp/monerosim_shared/{}_wallet --non-interactive --confirm-external-bind --allow-mismatched-daemon-version --max-concurrency=1 --daemon-ssl-allow-any-cert",
        agent_ip, agent_rpc_port, wallet_rpc_port, agent_ip, agent_id
    );

    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!(
            "-c '{} {}'",
            wallet_path, wallet_args
        ),
        environment: environment.clone(),
        start_time: wallet_start_time.to_string(), // Use the calculated wallet start time
    });
}

/// Add a user agent process to the processes list
fn add_user_agent_process(
    processes: &mut Vec<ShadowProcess>,
    agent_id: &str,
    agent_ip: &str,
    agent_rpc_port: u16,
    wallet_rpc_port: u16,
    p2p_port: u16,
    script: &str,
    attributes: Option<&HashMap<String, String>>,
    environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    index: usize,
    stop_time: &str,
    custom_start_time: Option<&str>,
) {
    let mut agent_args = vec![
        format!("--id {}", agent_id),
        format!("--shared-dir {}", shared_dir.to_str().unwrap()),
        format!("--rpc-host {}", agent_ip),
        format!("--agent-rpc-port {}", agent_rpc_port),
        format!("--wallet-rpc-port {}", wallet_rpc_port),
        format!("--p2p-port {}", p2p_port),
        format!("--log-level DEBUG"),
        format!("--stop-time {}", stop_time),
    ];

    // Add attributes from config as command-line arguments
    if let Some(attrs) = attributes {
        // Map specific attributes to their correct parameter names
        for (key, value) in attrs {
            if key == "transaction_interval" {
                agent_args.push(format!("--tx-frequency {}", value));
            } else if (key == "min_transaction_amount" || key == "max_transaction_amount" ||
                      key == "can_receive_distributions" || key == "location" || key == "city") ||
                      (key == "is_miner" && value == "true") {
                // These should be passed as attributes, but only pass is_miner if it's true
                agent_args.push(format!("--attributes {} {}", key, value));
            } else if key != "hashrate" && key != "is_miner" {
                // Pass other attributes directly, but filter out hashrate and is_miner (when false)
                agent_args.push(format!("--attributes {} {}", key, value));
            }
        }
    }

    // Remove stop-time from agent args since agents handle their own lifecycle
    agent_args.retain(|arg| !arg.starts_with("--stop-time"));

    // Simplified command without nc dependency - just sleep and retry
    let python_cmd = if script.contains('.') && !script.contains('/') && !script.contains('\\') {
        format!("python3 -m {} {}", script, agent_args.join(" "))
    } else {
        format!("python3 {} {}", script, agent_args.join(" "))
    };

    // Create a simple wrapper script that handles retries internally
    let wrapper_script = format!(
        r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:/usr/local/bin"

# Simple retry loop without nc dependency
for i in {{1..30}}; do
    if curl -s --max-time 1 http://{}:{} >/dev/null 2>&1; then
        echo "Wallet RPC ready, starting agent..."
        {} 2>&1
        exit $?
    fi
    echo "Waiting for wallet RPC... (attempt $i/30)"
    sleep 3
done

echo "Wallet RPC not available after 30 attempts, starting agent anyway..."
{} 2>&1
"#,
        current_dir,
        current_dir,
        agent_ip,
        wallet_rpc_port,
        python_cmd,
        python_cmd
    );

    // Write wrapper script to a temporary file and execute it
    let script_path = format!("/tmp/agent_{}_wrapper.sh", agent_id);

    // Use custom start time if provided, otherwise use default staggered timing
    let (script_creation_time, script_execution_time) = if let Some(custom_time) = custom_start_time {
        if let Ok(seconds) = parse_duration_to_seconds(custom_time) {
            (format!("{}s", seconds - 1), custom_time.to_string())
        } else {
            // Fallback to default timing if parsing fails
            (format!("{}s", 64 + index * 2), format!("{}s", 65 + index * 2))
        }
    } else {
        (format!("{}s", 64 + index * 2), format!("{}s", 65 + index * 2))
    };

    // Process 1: Create wrapper script
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: format!("-c 'cat > {} << \\EOF\n{}\\EOF'", script_path, wrapper_script),
        environment: environment.clone(),
        start_time: script_creation_time,
    });

    // Process 2: Execute wrapper script
    processes.push(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: script_path.clone(),
        environment: environment.clone(),
        start_time: script_execution_time,
    });
}
/// Process user agents
pub fn process_user_agents(
    agents: &AgentDefinitions,
    hosts: &mut HashMap<String, ShadowHost>,
    seed_agents: &mut Vec<String>,
    effective_seed_nodes: &[String],
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    monerod_path: &str,
    wallet_path: &str,
    environment: &HashMap<String, String>,
    monero_environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    peer_mode: &PeerMode,
    topology: Option<&Topology>,
) -> color_eyre::eyre::Result<()> {
    // Get agent distribution across GML nodes if available AND we're actually using GML topology
    let agent_node_assignments = if let Some(gml) = gml_graph {
        if let Some(user_agents) = &agents.user_agents {
            if using_gml_topology {
                let as_numbers = gml.nodes.iter().map(|node| node.get_ip().map(|ip| ip.to_string())).collect::<Vec<Option<String>>>();
                distribute_agents_across_topology(Some(Path::new("")), user_agents.len(), &as_numbers)
                    .into_iter()
                    .map(|opt_idx| opt_idx.map_or(0, |idx| idx as u32))
                    .collect()
            } else {
                // If we're not using GML topology (fallback to switch), all agents go to node 0
                vec![0; user_agents.len()]
            }
        } else {
            Vec::new()
        }
    } else {
        Vec::new()
    };

    // First, collect all agent information to build connection graphs
    let mut agent_info = Vec::new();
    let mut all_agent_ips = Vec::new(); // Collect all agent IPs for topology connections
    let mut miners = Vec::new();
    let mut seed_nodes = Vec::new();
    let mut regular_agents = Vec::new();

    if let Some(user_agents) = &agents.user_agents {
        for (i, user_agent_config) in user_agents.iter().enumerate() {
            let is_miner = user_agent_config.is_miner_value();
            let is_seed_node = is_miner || user_agent_config.attributes.as_ref()
                .map(|attrs| attrs.get("seed-node").map_or(false, |v| v == "true"))
                .unwrap_or(false);
            // Use consistent naming for all user agents
            let agent_id = format!("user{:03}", i);

            // Determine network node ID for this agent
            let network_node_id = if i < agent_node_assignments.len() {
                agent_node_assignments[i]
            } else {
                0 // Fallback to node 0 for switch-based networks
            };

            let agent_ip = get_agent_ip(AgentType::UserAgent, &agent_id, i, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
            let agent_port = 28080;

            // Collect all agent IPs for topology connections
            all_agent_ips.push(format!("{}:{}", agent_ip, agent_port));

            let agent_entry = (i, is_miner, is_seed_node, agent_id.clone(), agent_ip.clone(), agent_port);

            if is_miner {
                miners.push(agent_entry);
            } else if is_seed_node {
                seed_nodes.push(agent_entry);
            } else {
                regular_agents.push(agent_entry);
            }

            agent_info.push((i, is_miner, is_seed_node, agent_id, agent_ip, agent_port));
        }
    }

    // Ensure we have exactly 5 seed nodes; if less, promote some regular agents (for Hardcoded/Hybrid modes)
    if !matches!(peer_mode, PeerMode::Dynamic) {
        while seed_nodes.len() < 5 {
            if let Some((i, _, _, id, ip, port)) = regular_agents.pop() {
                seed_nodes.push((i, false, true, id, ip, port));
            } else {
                // If no more regular agents, promote from miners if needed
                if let Some((i, _, _, id, ip, port)) = miners.pop() {
                    seed_nodes.push((i, true, true, id, ip, port));
                } else {
                    // No more agents to promote
                    break;
                }
            }
        }
    }

    // Build seed_agents list - use effective_seed_nodes for Dynamic mode, seed_nodes for others
    if matches!(peer_mode, PeerMode::Dynamic) {
        seed_agents.extend(effective_seed_nodes.iter().cloned());
    } else {
        for (_, _, _, _, agent_ip, agent_port) in &seed_nodes {
            let seed_addr = format!("{}:{}", agent_ip, agent_port);
            seed_agents.push(seed_addr);
        }
    }

    // Generate fixed connections for initial network bootstrap
    // Miners connect in Ring among themselves
    let mut miner_connections = HashMap::new();
    for (i, (_, _, _, id, ip, _)) in miners.iter().enumerate() {
        let mut connections = Vec::new();
        // Connect to previous and next miner
        let prev = if i == 0 { miners.len() - 1 } else { i - 1 };
        let next = if i == miners.len() - 1 { 0 } else { i + 1 };
        if prev < miners.len() {
            let prev_miner = &miners[prev];
            if prev_miner.4 != *ip { // Don't connect to self
                connections.push(format!("--add-priority-node={}:{}", prev_miner.4, prev_miner.5));
            }
        }
        if next < miners.len() {
            let next_miner = &miners[next];
            if next_miner.4 != *ip { // Don't connect to self
                connections.push(format!("--add-priority-node={}:{}", next_miner.4, next_miner.5));
            }
        }
        miner_connections.insert(id.clone(), connections);
    }

    // Seed nodes connect to all miners and to each other in Ring (for Hardcoded/Hybrid modes)
    let seed_connections = if !matches!(peer_mode, PeerMode::Dynamic) {
        let mut seed_connections = HashMap::new();
        for (i, (_, _, _, id, ip, _)) in seed_nodes.iter().enumerate() {
            let mut connections = Vec::new();
            // Connect to all miners using --seed-node
            for (_, _, _, _, m_ip, m_port) in &miners {
                if m_ip != ip {
                    connections.push(format!("--seed-node={}:{}", m_ip, m_port));
                }
            }
            // Connect to other seeds in Ring
            let prev = if i == 0 { seed_nodes.len() - 1 } else { i - 1 };
            let next = if i == seed_nodes.len() - 1 { 0 } else { i + 1 };
            if prev < seed_nodes.len() {
                let prev_seed = &seed_nodes[prev];
                if prev_seed.4 != *ip {
                    connections.push(format!("--add-priority-node={}:{}", prev_seed.4, prev_seed.5));
                }
            }
            if next < seed_nodes.len() {
                let next_seed = &seed_nodes[next];
                if next_seed.4 != *ip {
                    connections.push(format!("--add-priority-node={}:{}", next_seed.4, next_seed.5));
                }
            }
            seed_connections.insert(id.clone(), connections);
        }
        seed_connections
    } else {
        HashMap::new()
    };

    // Regular agents will use seed nodes for --seed-node

    // Now process all user agents with staggered start times
    if let Some(user_agents) = &agents.user_agents {
        for (i, user_agent_config) in user_agents.iter().enumerate() {
            // Determine agent type and start time
            let is_miner = user_agent_config.is_miner_value();
            let is_seed_node = is_miner || user_agent_config.attributes.as_ref()
                .map(|attrs| attrs.get("seed-node").map_or(false, |v| v == "true"))
                .unwrap_or(false);

            let start_time_daemon = if matches!(peer_mode, PeerMode::Dynamic) {
                // Optimized Dynamic mode launch sequence - reduced staggered timing
                if is_miner {
                    if i == 0 {
                        "0s".to_string() // First miner (node 0) at t=0s
                    } else {
                        format!("{}s", 1 + i) // Remaining miners every 1s starting t=1s
                    }
                } else {
                    // Regular users start after miners, with reduced stagger
                    format!("{}s", 5 + (i.saturating_sub(miners.len())))
                }
            } else {
                // Optimized logic for other modes - reduced timing
                if is_miner {
                    format!("{}s", i) // Miners start early, staggered by 1s
                } else if is_seed_node || seed_nodes.iter().any(|(_, _, is_s, _, _, _)| *is_s && agent_info[i].0 == i) {
                    "3s".to_string() // Seeds start at 3s
                } else {
                    // Regular agents start after seeds, with reduced stagger
                    let regular_index = regular_agents.iter().position(|(idx, _, _, _, _, _)| *idx == i).unwrap_or(0);
                    format!("{}s", 6 + regular_index) // Stagger by 1s
                }
            };

            // Wallet start time: coordinate with daemon start time (reduced delay)
            let wallet_start_time = if matches!(peer_mode, PeerMode::Dynamic) {
                // Dynamic mode: start wallet 2 seconds after daemon (reduced from 5s)
                if let Ok(daemon_seconds) = parse_duration_to_seconds(&start_time_daemon) {
                    format!("{}s", daemon_seconds + 2)
                } else {
                    format!("{}s", 2 + i)
                }
            } else {
                // Other modes: start wallet 2 seconds after daemon (reduced from 5s)
                if let Ok(daemon_seconds) = parse_duration_to_seconds(&start_time_daemon) {
                    format!("{}s", daemon_seconds + 2)
                } else {
                    format!("{}s", 2 + i)
                }
            };

            // Agent start time: ensure agents start after their wallet services are ready (reduced delay)
            let agent_start_time = if matches!(peer_mode, PeerMode::Dynamic) {
                // Dynamic mode: start agent 3 seconds after wallet (reduced from 10s)
                if let Ok(wallet_seconds) = parse_duration_to_seconds(&wallet_start_time) {
                    format!("{}s", wallet_seconds + 3)
                } else {
                    format!("{}s", 5 + i)
                }
            } else {
                // Other modes: start agent 3 seconds after wallet (reduced from 10s)
                if let Ok(wallet_seconds) = parse_duration_to_seconds(&wallet_start_time) {
                    format!("{}s", wallet_seconds + 3)
                } else {
                    format!("{}s", 5 + i)
                }
            };

            // Use consistent naming for all user agents
            let agent_id = format!("user{:03}", i);

            // Determine network node ID for this agent
            let network_node_id = if i < agent_node_assignments.len() {
                agent_node_assignments[i]
            } else {
                0 // Fallback to node 0 for switch-based networks
            };

            let agent_ip = get_agent_ip(AgentType::UserAgent, &agent_id, i, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
            let _agent_port = 28080;

            // Use standard RPC ports for all agents
            let agent_rpc_port = 28081;

            // Use standard wallet RPC port for all agents
            // Since each agent has its own IP address, they can all use the same port
            let wallet_rpc_port = 28082;
            let p2p_port = 28080;

            let mut processes = Vec::new();

            // Add Monero daemon process with appropriate connections
            let mut daemon_args_base = vec![
                format!("--data-dir=/tmp/monero-{}", agent_id),
                "--log-file=/dev/stdout".to_string(),
                "--log-level=1".to_string(),
                "--simulation".to_string(),
                "--disable-dns-checkpoints".to_string(),
                "--prep-blocks-threads=1".to_string(),
                "--max-concurrency=1".to_string(),
                "--no-zmq".to_string(),
                "--db-sync-mode=safe".to_string(),
                "--non-interactive".to_string(),
                "--max-connections-per-ip=50".to_string(),
                "--limit-rate-up=1024".to_string(),
                "--limit-rate-down=1024".to_string(),
                "--block-sync-size=1".to_string(),
                format!("--rpc-bind-ip={}", agent_ip),
                format!("--rpc-bind-port={}", agent_rpc_port),
                "--confirm-external-bind".to_string(),
                "--disable-rpc-ban".to_string(),
                "--rpc-access-control-origins=*".to_string(),
                "--regtest".to_string(),
                format!("--p2p-bind-ip={}", agent_ip),
                format!("--p2p-bind-port={}", p2p_port),
                //"--fixed-difficulty=200".to_string(),
                "--allow-local-ip".to_string(),
            ];

            // Only disable built-in seed nodes for miners
            if is_miner {
                daemon_args_base.push("--disable-seed-nodes".to_string());
            }

            // Add initial fixed connections and seed nodes
            if is_miner {
                // Miners connect to other miners
                if let Some(conns) = miner_connections.get(&agent_id) {
                    for conn in conns {
                        daemon_args_base.push(conn.clone());
                    }
                }
            } else if is_seed_node || seed_nodes.iter().any(|(_, _, is_s, _, _, _)| *is_s && agent_info[i].0 == i) {
                // Seed nodes connect to miners and other seeds
                if let Some(conns) = seed_connections.get(&agent_id) {
                    for conn in conns {
                        daemon_args_base.push(conn.clone());
                    }
                }
            } else {
                // Regular agents will get peer connections based on peer_mode below
            }

            // For regular agents, add peer connections based on peer mode
            let is_actual_seed_node = seed_nodes.iter().any(|(idx, _, _, _, _, _)| *idx == i);
            if !is_miner && !is_actual_seed_node {
                // Add seed node connections for all modes
                for seed_node in seed_agents.iter() {
                    if !seed_node.starts_with(&format!("{}:", agent_ip)) {
                        let peer_arg = if matches!(peer_mode, PeerMode::Dynamic) {
                            format!("--seed-node={}", seed_node)
                        } else {
                            format!("--add-priority-node={}", seed_node)
                        };
                        daemon_args_base.push(peer_arg);
                    }
                }

                // For Hybrid mode, also add topology-based connections
                if matches!(peer_mode, PeerMode::Hybrid) {
                    if let Some(topo) = topology {
                        let topology_connections = generate_topology_connections(topo, i, &all_agent_ips, &agent_ip);
                        for conn in topology_connections {
                            daemon_args_base.push(conn);
                        }
                    }
                }
            }

            let daemon_args = daemon_args_base.join(" ");

            processes.push(ShadowProcess {
                path: "/bin/bash".to_string(),
                args: format!(
                    "-c 'rm -rf /tmp/monero-{} && {} {}'",
                    agent_id, monerod_path, daemon_args
                ),
                environment: monero_environment.clone(),
                start_time: start_time_daemon,
            });

            // Add wallet process if wallet is specified
            if user_agent_config.wallet.is_some() {
                add_wallet_process(
                    &mut processes,
                    &agent_id,
                    &agent_ip,
                    agent_rpc_port,
                    wallet_rpc_port,
                    wallet_path,
                    environment,
                    i,
                    &wallet_start_time,
                );
            }

            // Add user agent script if specified
            let user_script = user_agent_config.user_script.clone().unwrap_or_else(|| {
                if is_miner {
                    "agents.regular_user".to_string()
                } else {
                    "agents.regular_user".to_string()
                }
            });

            if !user_script.is_empty() {
                add_user_agent_process(
                    &mut processes,
                    &agent_id,
                    &agent_ip,
                    agent_rpc_port,
                    wallet_rpc_port,
                    p2p_port,
                    &user_script,
                    user_agent_config.attributes.as_ref(),
                    environment,
                    shared_dir,
                    current_dir,
                    i,
                    environment.get("stop_time").map(|s| s.as_str()).unwrap_or("1800"),
                    Some(&agent_start_time), // Pass the calculated agent start time
                );
            }

            // Only add the host if it has any processes
            if !processes.is_empty() {
                // Determine network node ID based on GML assignment or fallback
                let network_node_id = if i < agent_node_assignments.len() {
                    agent_node_assignments[i]
                } else {
                    0 // Fallback to node 0 for switch-based networks
                };
                
                hosts.insert(agent_id.clone(), ShadowHost {
                    network_node_id,
                    ip_addr: Some(agent_ip.clone()),
                    processes,
                    bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
                    bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
                });
                // Note: next_ip is already incremented in get_agent_ip function
            }
        }
    }

    Ok(())
}

/// Process block controller agent
pub fn process_block_controller(
    agents: &AgentDefinitions,
    hosts: &mut HashMap<String, ShadowHost>,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    _stop_time: &str,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    agent_offset: usize,
    peer_mode: &PeerMode,
) -> color_eyre::eyre::Result<()> {
    if let Some(block_controller_config) = &agents.block_controller {
        let block_controller_id = "blockcontroller";
        // Assign block controller to node 0 (which has bandwidth info in GML)
        let network_node_id = 0;
        let block_controller_ip = get_agent_ip(AgentType::BlockController, block_controller_id, agent_offset, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
        let mut processes = Vec::new();

        let mut agent_args = vec![
            format!("--id {}", block_controller_id),
            format!("--shared-dir {}", shared_dir.to_str().unwrap()),
            format!("--log-level DEBUG"),
        ];

        if let Some(args) = &block_controller_config.arguments {
            agent_args.extend(args.iter().cloned());
        }

        // Simplified command for block controller
        let python_cmd = if block_controller_config.script.contains('.') && !block_controller_config.script.contains('/') && !block_controller_config.script.contains('\\') {
            format!("python3 -m {} {}", block_controller_config.script, agent_args.join(" "))
        } else {
            format!("python3 {} {}", block_controller_config.script, agent_args.join(" "))
        };

        // Create a simple wrapper script for block controller
        let wrapper_script = format!(
            r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:/usr/local/bin"

echo "Starting block controller..."
{} 2>&1
"#,
            current_dir,
            current_dir,
            python_cmd
        );

        // Write wrapper script to a temporary file and execute it
        let script_path = format!("/tmp/{}_wrapper.sh", block_controller_id);

        // Determine execution start time (optimized)
        let block_controller_start_time = if matches!(peer_mode, PeerMode::Dynamic) {
            "10s".to_string() // Dynamic mode: block controller starts at 10s (reduced from 20s)
        } else {
            "15s".to_string() // Other modes: reduced from 90s
        };

        // Calculate script creation time (1 second before execution)
        let script_creation_time = if let Ok(exec_seconds) = parse_duration_to_seconds(&block_controller_start_time) {
            format!("{}s", exec_seconds.saturating_sub(1))
        } else {
            // Fallback if parsing fails
            "89s".to_string()
        };

        // Process 1: Create wrapper script
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: format!("-c 'cat > {} << \\EOF\n{}\\EOF'", script_path, wrapper_script),
            environment: environment.clone(),
            start_time: script_creation_time,
        });

        // Process 2: Execute wrapper script
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: script_path.clone(),
            environment: environment.clone(),
            start_time: block_controller_start_time,
        });

        hosts.insert(block_controller_id.to_string(), ShadowHost {
            network_node_id, // Use the assigned GML node with bandwidth info
            ip_addr: Some(block_controller_ip),
            processes,
            bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
            bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
        });
        // Note: next_ip is already incremented in get_agent_ip function
    }

    Ok(())
}

/// Process miner distributor agent
pub fn process_miner_distributor(
    agents: &AgentDefinitions,
    hosts: &mut HashMap<String, ShadowHost>,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    _stop_time: &str,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    agent_offset: usize,
    peer_mode: &PeerMode,
) -> color_eyre::eyre::Result<()> {
    if let Some(miner_distributor_config) = &agents.miner_distributor {
        let miner_distributor_id = "minerdistributor";
        // Assign miner distributor to node 0 (which has bandwidth info in GML)
        let network_node_id = 0;
        let miner_distributor_ip = get_agent_ip(AgentType::BlockController, miner_distributor_id, agent_offset, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
        let mut processes = Vec::new();

        let mut agent_args = vec![
            format!("--id {}", miner_distributor_id),
            format!("--shared-dir {}", shared_dir.to_str().unwrap()),
            format!("--log-level DEBUG"),
        ];

        // Add attributes from config
        if let Some(attrs) = &miner_distributor_config.attributes {
            for (key, value) in attrs {
                agent_args.push(format!("--attributes {} {}", key, value));
            }
        }

        // Simplified command for miner distributor
        let python_cmd = if miner_distributor_config.script.contains('.') && !miner_distributor_config.script.contains('/') && !miner_distributor_config.script.contains('\\') {
            format!("python3 -m {} {}", miner_distributor_config.script, agent_args.join(" "))
        } else {
            format!("python3 {} {}", miner_distributor_config.script, agent_args.join(" "))
        };

        // Create a simple wrapper script for miner distributor
        let wrapper_script = format!(
            r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:/usr/local/bin"

echo "Starting miner distributor..."
{} 2>&1
"#,
            current_dir,
            current_dir,
            python_cmd
        );

        // Write wrapper script to a temporary file and execute it
        let script_path = format!("/tmp/{}_wrapper.sh", miner_distributor_id);

        // Determine execution start time (keeping original for block maturity)
        let miner_distributor_start_time = if matches!(peer_mode, PeerMode::Dynamic) {
            "3900s".to_string() // Dynamic mode: miner distributor starts at 65 minutes (block reward maturity)
        } else {
            "3900s".to_string() // Other modes: also start at 65 minutes (block reward maturity)
        };

        // Calculate script creation time (1 second before execution)
        let script_creation_time = if let Ok(exec_seconds) = parse_duration_to_seconds(&miner_distributor_start_time) {
            format!("{}s", exec_seconds.saturating_sub(1))
        } else {
            // Fallback if parsing fails
            "89s".to_string()
        };

        // Process 1: Create wrapper script
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: format!("-c 'cat > {} << \\EOF\n{}\\EOF'", script_path, wrapper_script),
            environment: environment.clone(),
            start_time: script_creation_time,
        });

        // Process 2: Execute wrapper script
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: script_path.clone(),
            environment: environment.clone(),
            start_time: miner_distributor_start_time,
        });

        hosts.insert(miner_distributor_id.to_string(), ShadowHost {
            network_node_id, // Use the assigned GML node with bandwidth info
            ip_addr: Some(miner_distributor_ip),
            processes,
            bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
            bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
        });
        // Note: next_ip is already incremented in get_agent_ip function
    }

    Ok(())
}

/// Process pure script agents
pub fn process_pure_script_agents(
    agents: &AgentDefinitions,
    hosts: &mut HashMap<String, ShadowHost>,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    _stop_time: &str,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    agent_offset: usize,
) -> color_eyre::eyre::Result<()> {
    if let Some(pure_script_agents) = &agents.pure_script_agents {
        for (i, pure_script_config) in pure_script_agents.iter().enumerate() {
            let script_id = format!("script{:03}", i);
            // Assign pure scripts to node 0 (which has bandwidth info in GML)
            let network_node_id = 0;
            let script_ip = get_agent_ip(AgentType::PureScriptAgent, &script_id, agent_offset + i, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
            let mut processes = Vec::new();

            let mut script_args = vec![
                format!("--id {}", script_id),
                format!("--shared-dir {}", shared_dir.to_str().unwrap()),
                format!("--log-level DEBUG"),
            ];

            if let Some(args) = &pure_script_config.arguments {
                script_args.extend(args.iter().cloned());
            }

            // Simplified command for pure script agents
            let python_cmd = format!("python3 {} {}", pure_script_config.script, script_args.join(" "));

            // Create a simple wrapper script for pure script agents
            let wrapper_script = format!(
                r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:/usr/local/bin"

echo "Starting pure script agent {}..."
{} 2>&1
"#,
                current_dir,
                current_dir,
                script_id,
                python_cmd
            );

            // Write wrapper script to a temporary file and execute it
            let script_path = format!("/tmp/{}_wrapper.sh", script_id);
            let script_creation_time = format!("{}s", 5 + i * 2);
            let script_execution_time = format!("{}s", 6 + i * 2);

            // Process 1: Create wrapper script
            processes.push(ShadowProcess {
                path: "/bin/bash".to_string(),
                args: format!("-c 'cat > {} << \\EOF\n{}\\EOF'", script_path, wrapper_script),
                environment: environment.clone(),
                start_time: script_creation_time,
            });

            // Process 2: Execute wrapper script
            processes.push(ShadowProcess {
                path: "/bin/bash".to_string(),
                args: script_path.clone(),
                environment: environment.clone(),
                start_time: script_execution_time,
            });

            hosts.insert(script_id.clone(), ShadowHost {
                network_node_id, // Use the assigned GML node with bandwidth info
                ip_addr: Some(script_ip),
                processes,
                bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
                bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
            });
            // Note: next_ip is already incremented in get_agent_ip function
        }
    }

    Ok(())
}

/// Process simulation monitor agent
///
/// Creates a Shadow host configuration for the simulation monitor agent,
/// which provides real-time monitoring and logging of simulation progress.
///
/// # Parameters
/// - `agents`: Agent definitions from configuration
/// - `hosts`: Mutable map to store created Shadow hosts
/// - `subnet_manager`: IP subnet manager for address allocation
/// - `ip_registry`: Global IP registry for address allocation
/// - `environment`: Environment variables for the process
/// - `shared_dir`: Shared directory for inter-agent communication
/// - `current_dir`: Current working directory
/// - `_stop_time`: Simulation stop time (unused)
/// - `gml_graph`: Optional GML topology graph
/// - `using_gml_topology`: Whether GML topology is being used
/// - `agent_offset`: Offset for IP allocation to avoid conflicts
///
/// # Returns
/// Result indicating success or failure of simulation monitor processing
pub fn process_simulation_monitor(
    agents: &AgentDefinitions,
    hosts: &mut HashMap<String, ShadowHost>,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    environment: &HashMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    _stop_time: &str,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    agent_offset: usize,
) -> color_eyre::eyre::Result<()> {
    if let Some(simulation_monitor_config) = &agents.simulation_monitor {
        let simulation_monitor_id = "simulation-monitor";
        // Assign simulation monitor to node 0 (which has bandwidth info in GML)
        let network_node_id = 0;
        let simulation_monitor_ip = get_agent_ip(AgentType::PureScriptAgent, simulation_monitor_id, agent_offset, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
        let mut processes = Vec::new();

        let mut agent_args = vec![
            format!("--id simulation_monitor"),  // Keep original ID for agent consistency
            format!("--shared-dir {}", shared_dir.to_str().unwrap()),
            format!("--log-level DEBUG"),
        ];

        // Add configuration-specific arguments
        if let Some(poll_interval) = simulation_monitor_config.poll_interval {
            agent_args.push(format!("--poll-interval {}", poll_interval));
        }
        
        if let Some(status_file) = &simulation_monitor_config.status_file {
            agent_args.push(format!("--status-file {}", status_file));
        }
        
        if simulation_monitor_config.enable_alerts.unwrap_or(false) {
            agent_args.push("--enable-alerts".to_string());
        }
        
        if simulation_monitor_config.detailed_logging.unwrap_or(false) {
            agent_args.push("--detailed-logging".to_string());
        }

        // Add any additional arguments from the configuration
        if let Some(args) = &simulation_monitor_config.arguments {
            agent_args.extend(args.iter().cloned());
        }

        // Simplified command for simulation monitor agent
        let python_cmd = if simulation_monitor_config.script.contains('.') && !simulation_monitor_config.script.contains('/') && !simulation_monitor_config.script.contains('\\') {
            format!("python3 -m {} {}", simulation_monitor_config.script, agent_args.join(" "))
        } else {
            format!("python3 {} {}", simulation_monitor_config.script, agent_args.join(" "))
        };

        // Create a wrapper script for simulation monitor agent
        let wrapper_script = format!(
            r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:/usr/local/bin"

echo "Starting simulation monitor agent..."
{} 2>&1
"#,
            current_dir,
            current_dir,
            python_cmd
        );

        // Write wrapper script to a temporary file and execute it
        let script_path = "/tmp/simulation_monitor_wrapper.sh".to_string();

        // Determine execution start time (start early to monitor from beginning)
        let simulation_monitor_start_time = "5s".to_string();

        // Calculate script creation time (1 second before execution)
        let script_creation_time = "4s".to_string();

        // Process 1: Create wrapper script
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: format!("-c 'cat > {} << \\EOF\n{}\\EOF'", script_path, wrapper_script),
            environment: environment.clone(),
            start_time: script_creation_time,
        });

        // Process 2: Execute wrapper script
        processes.push(ShadowProcess {
            path: "/bin/bash".to_string(),
            args: script_path.clone(),
            environment: environment.clone(),
            start_time: simulation_monitor_start_time,
        });

        hosts.insert("simulation-monitor".to_string(), ShadowHost {
            network_node_id, // Use the assigned GML node with bandwidth info
            ip_addr: Some(simulation_monitor_ip),
            processes,
            bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
            bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
        });
        // Note: next_ip is already incremented in get_agent_ip function
    }

    Ok(())
}

/// Generate a Shadow configuration with agent support
pub fn generate_agent_shadow_config(
    config: &Config,
    output_path: &Path,
) -> color_eyre::eyre::Result<()> {
    const SHARED_DIR: &str = "/tmp/monerosim_shared";
    let shared_dir_path = Path::new(SHARED_DIR);

    let current_dir = std::env::current_dir()
        .map_err(|e| color_eyre::eyre::eyre!("Failed to get current directory: {}", e))?
        .to_string_lossy()
        .to_string();

    // Load and validate GML graph if specified
    let gml_graph = if let Some(Network::Gml { path, .. }) = &config.network {
        let graph = parse_gml_file(path)?;
        validate_topology(&graph).map_err(|e| color_eyre::eyre::eyre!("GML validation failed: {}", e))?;
        println!("Loaded GML topology from '{}' with {} nodes and {} edges",
                 path, graph.nodes.len(), graph.edges.len());
        Some(graph)
    } else {
        None
    };

    let mut hosts: HashMap<String, ShadowHost> = HashMap::new();

    // Common environment variables
    let mut environment: HashMap<String, String> = [
        ("MALLOC_MMAP_THRESHOLD_".to_string(), "131072".to_string()),
        ("MALLOC_TRIM_THRESHOLD_".to_string(), "131072".to_string()),
        ("GLIBC_TUNABLES".to_string(), "glibc.malloc.arena_max=1".to_string()),
        ("MALLOC_ARENA_MAX".to_string(), "1".to_string()),
        ("PYTHONUNBUFFERED".to_string(), "1".to_string()), // Ensure Python output is unbuffered
    ].iter().cloned().collect();

    // Add MONEROSIM_LOG_LEVEL if specified in config
    if let Some(log_level) = &config.general.log_level {
        environment.insert("MONEROSIM_LOG_LEVEL".to_string(), log_level.to_uppercase());
    }

    // Monero-specific environment variables
    let mut monero_environment = environment.clone();
    monero_environment.insert("MONERO_BLOCK_SYNC_SIZE".to_string(), "1".to_string());
    monero_environment.insert("MONERO_DISABLE_DNS".to_string(), "1".to_string());
    monero_environment.insert("MONERO_MAX_CONNECTIONS_PER_IP".to_string(), "20".to_string());

    // Create centralized IP registry for robust IP management
    let mut ip_registry = GlobalIpRegistry::new();

    // Create AS-aware subnet manager for GML topology compatibility
    let mut subnet_manager = AsSubnetManager::new();

    // Helper to get absolute path for binaries
    let monerod_path = "/usr/local/bin/monerod".to_string();
    let wallet_path = "/usr/local/bin/monero-wallet-rpc".to_string();

    // Store seed nodes for P2P connections
    let mut seed_nodes: Vec<String> = Vec::new();

    // Determine if we're actually using GML topology based on network configuration
    let using_gml_topology = if let Some(Network::Gml { path: _, .. }) = &config.network {
        true // We're using GML topology
    } else {
        false // We're using switch topology
    };

    // Extract peer mode, seed nodes, and topology from configuration
    let (peer_mode, seed_node_list, topology) = match &config.network {
        Some(Network::Gml { peer_mode, seed_nodes, topology, .. }) => {
            let mode = peer_mode.as_ref().unwrap_or(&PeerMode::Dynamic).clone();
            let seeds = seed_nodes.as_ref().unwrap_or(&Vec::new()).clone();
            let topo = topology.as_ref().unwrap_or(&Topology::Dag).clone();
            (mode, seeds, Some(topo))
        }
        Some(Network::Switch { peer_mode, seed_nodes, topology, .. }) => {
            let mode = peer_mode.as_ref().unwrap_or(&PeerMode::Dynamic).clone();
            let seeds = seed_nodes.as_ref().unwrap_or(&Vec::new()).clone();
            let topo = topology.as_ref().unwrap_or(&Topology::Dag).clone();
            (mode, seeds, Some(topo))
        }
        None => {
            // Default to Dynamic mode with no seed nodes and DAG topology
            (PeerMode::Dynamic, Vec::new(), Some(Topology::Dag))
        }
    };

    // Validate topology configuration
    if let Some(topo) = &topology {
        if let Some(user_agents) = &config.agents.user_agents {
            if let Err(e) = validate_topology_config(topo, user_agents.len()) {
                println!("Warning: Topology validation failed: {}", e);
                // Continue with default DAG topology
            }
        }
    }

    // Use the configured seed nodes, or collect miner IPs if not provided
    let effective_seed_nodes = if seed_node_list.is_empty() {
        // Collect actual miner IPs for seed nodes
        let mut miner_ips = Vec::new();
        if let Some(user_agents) = &config.agents.user_agents {
            for (i, user_agent_config) in user_agents.iter().enumerate() {
                if user_agent_config.is_miner_value() {
                    let agent_id = format!("user{:03}", i);
                    // For seed node IP calculation, use node 0 (switch topology assumption)
                    // This ensures consistent IP assignment for miners
                    let network_node_id = 0;
                    let agent_ip = get_agent_ip(AgentType::UserAgent, &agent_id, i, network_node_id, gml_graph.as_ref(), using_gml_topology, &mut subnet_manager, &mut ip_registry);
                    miner_ips.push(format!("{}:28080", agent_ip));
                }
            }
        }
        println!("Using {} miner IPs as seed nodes: {:?}", miner_ips.len(), miner_ips);
        miner_ips
    } else {
        println!("Using configured seed nodes: {:?}", seed_node_list);
        seed_node_list
    };

    // Process all agent types from the configuration
    process_user_agents(
        &config.agents,
        &mut hosts,
        &mut seed_nodes,
        &effective_seed_nodes,
        &mut subnet_manager,
        &mut ip_registry,
        &monerod_path,
        &wallet_path,
        &environment,
        &monero_environment,
        shared_dir_path,
        &current_dir,
        gml_graph.as_ref(),
        using_gml_topology,
        &peer_mode,
        topology.as_ref(),
    )?;


    // Calculate offset for block controller and script agents to avoid IP collisions
    // Use a larger offset to ensure clear separation between agent types
    let user_agent_count = config.agents.user_agents.as_ref().map(|ua| ua.len()).unwrap_or(0);
    let block_controller_offset = user_agent_count + 100; // Reserve 100 IPs for user agents
    let script_offset = user_agent_count + 200; // Reserve another 100 IPs for block controller and other uses

    process_block_controller(
        &config.agents,
        &mut hosts,
        &mut subnet_manager,
        &mut ip_registry,
        &environment,
        shared_dir_path,
        &current_dir,
        &config.general.stop_time,
        gml_graph.as_ref(),
        using_gml_topology,
        block_controller_offset,
        &peer_mode,
    )?;

    process_miner_distributor(
        &config.agents,
        &mut hosts,
        &mut subnet_manager,
        &mut ip_registry,
        &environment,
        shared_dir_path,
        &current_dir,
        &config.general.stop_time,
        gml_graph.as_ref(),
        using_gml_topology,
        block_controller_offset + 10, // Offset from block controller
        &peer_mode,
    )?;

    process_pure_script_agents(
        &config.agents,
        &mut hosts,
        &mut subnet_manager,
        &mut ip_registry,
        &environment,
        shared_dir_path,
        &current_dir,
        &config.general.stop_time,
        gml_graph.as_ref(),
        using_gml_topology,
        script_offset,
    )?;

    process_simulation_monitor(
        &config.agents,
        &mut hosts,
        &mut subnet_manager,
        &mut ip_registry,
        &environment,
        shared_dir_path,
        &current_dir,
        &config.general.stop_time,
        gml_graph.as_ref(),
        using_gml_topology,
        script_offset + 50, // Offset from other script agents
    )?;

    // Create agent registry
    let mut agent_registry = AgentRegistry {
        agents: Vec::new(),
    };

    // Populate agent registry from all agent types
    // Extract IPs from the already created hosts instead of generating new ones

    // Add user agents to registry
    if let Some(user_agents) = &config.agents.user_agents {
        for (i, user_agent_config) in user_agents.iter().enumerate() {
            let agent_id = format!("user{:03}", i);

            // Get IP from the corresponding host that was already created
            let agent_ip = hosts.get(&agent_id)
                .and_then(|host| host.ip_addr.clone())
                .unwrap_or_else(|| {
                    // Fallback to geographic IP assignment
                    format!("192.168.10.{}", 10 + i)
                });

            let mut attributes = user_agent_config.attributes.clone().unwrap_or_default();

            // Add computed is_miner attribute to the agent registry
            let is_miner = user_agent_config.is_miner_value();
            attributes.insert("is_miner".to_string(), is_miner.to_string());

            let agent_info = AgentInfo {
                id: agent_id,
                ip_addr: agent_ip,
                daemon: true,
                wallet: user_agent_config.wallet.is_some(),
                user_script: user_agent_config.user_script.clone(),
                attributes,
                wallet_rpc_port: if user_agent_config.wallet.is_some() { Some(28082) } else { None },
                daemon_rpc_port: Some(28081),
            };
            agent_registry.agents.push(agent_info);
        }
    }

    // Add block controller to registry
    if config.agents.block_controller.is_some() {
        let block_controller_id = "blockcontroller".to_string();

        // Get IP from the corresponding host that was already created
        let block_controller_ip = hosts.get(&block_controller_id)
            .and_then(|host| host.ip_addr.clone())
            .unwrap_or_else(|| {
                // Fallback to geographic IP assignment for block controller
                format!("192.168.20.{}", 10 + block_controller_offset)
            });

        let agent_info = AgentInfo {
            id: block_controller_id,
            ip_addr: block_controller_ip,
            daemon: false, // Block controller does not run a daemon
            wallet: false, // Block controller does not have a wallet
            user_script: config.agents.block_controller.as_ref().map(|c| c.script.clone()),
            attributes: HashMap::new(), // No specific attributes for block controller
            wallet_rpc_port: None,
            daemon_rpc_port: None,
        };
        agent_registry.agents.push(agent_info);
    }

    // Add miner distributor to registry
    if config.agents.miner_distributor.is_some() {
        let miner_distributor_id = "minerdistributor".to_string();

        // Get IP from the corresponding host that was already created
        let miner_distributor_ip = hosts.get(&miner_distributor_id)
            .and_then(|host| host.ip_addr.clone())
            .unwrap_or_else(|| {
                // Fallback to geographic IP assignment for miner distributor
                format!("192.168.21.{}", 10 + block_controller_offset)
            });

        let agent_info = AgentInfo {
            id: miner_distributor_id,
            ip_addr: miner_distributor_ip,
            daemon: false, // Miner distributor does not run a daemon
            wallet: false, // Miner distributor does not have a wallet
            user_script: config.agents.miner_distributor.as_ref().map(|c| c.script.clone()),
            attributes: config.agents.miner_distributor.as_ref()
                .and_then(|c| c.attributes.clone())
                .unwrap_or_default(),
            wallet_rpc_port: None,
            daemon_rpc_port: None,
        };
        agent_registry.agents.push(agent_info);
    }

    // Add pure script agents to registry
    if let Some(pure_script_agents) = &config.agents.pure_script_agents {
        for (i, pure_script_config) in pure_script_agents.iter().enumerate() {
            let script_id = format!("script{:03}", i);

            // Get IP from the corresponding host that was already created
            let script_ip = hosts.get(&script_id)
                .and_then(|host| host.ip_addr.clone())
                .unwrap_or_else(|| {
                    // Fallback to geographic IP assignment for script agents
                    format!("192.168.30.{}", 10 + (i % 245))
                });

            let agent_info = AgentInfo {
                id: script_id,
                ip_addr: script_ip,
                daemon: false, // Pure script agents do not run a daemon
                wallet: false, // Pure script agents do not have a wallet
                user_script: Some(pure_script_config.script.clone()),
                attributes: HashMap::new(), // No specific attributes for pure script agents
                wallet_rpc_port: None,
                daemon_rpc_port: None,
            };
            agent_registry.agents.push(agent_info);
        }
    }

    // Add simulation monitor agent to registry
    if config.agents.simulation_monitor.is_some() {
        let simulation_monitor_id = "simulation_monitor".to_string();
        let simulation_monitor_hostname = "simulation-monitor".to_string();

        // Get IP from the corresponding host that was already created
        let simulation_monitor_ip = hosts.get(&simulation_monitor_hostname)
            .and_then(|host| host.ip_addr.clone())
            .unwrap_or_else(|| {
                // Fallback to geographic IP assignment for simulation monitor
                format!("192.168.31.{}", 10 + ((script_offset + 50) % 245))
            });

        let agent_info = AgentInfo {
            id: simulation_monitor_id,
            ip_addr: simulation_monitor_ip,
            daemon: false, // Simulation monitor does not run a daemon
            wallet: false, // Simulation monitor does not have a wallet
            user_script: config.agents.simulation_monitor.as_ref().map(|c| c.script.clone()),
            attributes: HashMap::new(), // No specific attributes for simulation monitor
            wallet_rpc_port: None,
            daemon_rpc_port: None,
        };
        agent_registry.agents.push(agent_info);
    }

    // Write agent registry to file
    let agent_registry_path = shared_dir_path.join("agent_registry.json");
    let agent_registry_json = serde_json::to_string_pretty(&agent_registry)?;
    std::fs::write(&agent_registry_path, &agent_registry_json)?;

    // Create miner registry
    let mut miner_registry = MinerRegistry {
        miners: Vec::new(),
    };

    // Populate miner registry from user_agents that are miners
    if let Some(user_agents) = &config.agents.user_agents {
        for (i, user_agent_config) in user_agents.iter().enumerate() {
            if user_agent_config.is_miner_value() {
                let agent_id = format!("user{:03}", i);
                // Find the IP address from the already populated agent_registry
                let agent_ip = agent_registry.agents.iter()
                    .find(|a| a.id == agent_id)
                    .map(|a| a.ip_addr.clone())
                    .unwrap_or_else(|| {
                        // Geographic IP assignment for miners
                        format!("192.168.10.{}", 10 + i)
                    }); // Fallback

                // Determine miner weight (hashrate)
                // If no valid hashrate is specified, default to 10 (for even distribution)
                let weight = user_agent_config.attributes
                    .as_ref()
                    .and_then(|attrs| attrs.get("hashrate"))
                    .and_then(|h| h.parse::<u32>().ok())
                    .unwrap_or(10); // Default to 10 instead of 0 for better distribution
                
                let miner_info = MinerInfo {
                    agent_id: agent_id.clone(),
                    ip_addr: agent_ip,
                    wallet_address: None, // Will be populated by the block controller
                    weight,
                };
                miner_registry.miners.push(miner_info);
            }
        }
    }

    // Validate the miner registry before writing
    if miner_registry.miners.is_empty() {
        println!("Warning: No miners were found in the configuration. Mining will not work correctly.");
    } else {
        // Calculate total weight to ensure it's positive
        let total_weight: u32 = miner_registry.miners.iter().map(|m| m.weight).sum();
        if total_weight == 0 {
            println!("Warning: Total mining hashrate weight is zero. Setting default weights of 10 for each miner.");
            // Set default weights if total is zero
            for miner in miner_registry.miners.iter_mut() {
                miner.weight = 10;
            }
        } else {
            println!("Mining weight distribution: {} miners with total weight {}",
                     miner_registry.miners.len(), total_weight);
        }
    }

    // Write miner registry to file
    let miner_registry_path = shared_dir_path.join("miners.json");
    let miner_registry_json = serde_json::to_string_pretty(&miner_registry)?;
    std::fs::write(&miner_registry_path, &miner_registry_json)?;

    // For GML topologies, ensure all nodes in the GML file have corresponding hosts in Shadow
    // This is required because Shadow expects a 1:1 mapping between GML nodes and hosts
    if let Some(gml) = &gml_graph {
        if using_gml_topology {
            for node in &gml.nodes {
                let dummy_host_name = format!("gml-node-{}", node.id);
                if !hosts.contains_key(&dummy_host_name) {
                    // Create a dummy host for this GML node with no processes
                    let dummy_host = ShadowHost {
                        network_node_id: node.id,
                        ip_addr: None, // No IP needed for dummy hosts
                        processes: Vec::new(), // No processes to run
                        bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
                        bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
                    };
                    hosts.insert(dummy_host_name, dummy_host);
                    log::debug!("Created dummy host for GML node {}", node.id);
                }
            }
        }
    }

    // Sort hosts by key to ensure consistent ordering in the output file
    let mut sorted_hosts: Vec<(String, ShadowHost)> = hosts.into_iter().collect();
    sorted_hosts.sort_by(|(a, _), (b, _)| a.cmp(b));
    let sorted_hosts_map: HashMap<String, ShadowHost> = sorted_hosts.into_iter().collect();

    // Parse stop_time to seconds
    let stop_time_seconds = parse_duration_to_seconds(&config.general.stop_time)
        .map_err(|e| color_eyre::eyre::eyre!("Failed to parse stop_time '{}': {}", config.general.stop_time, e))?;

    // Create final Shadow configuration
    let shadow_config = ShadowConfig {
        general: ShadowGeneral {
            stop_time: stop_time_seconds,
            model_unblocked_syscall_latency: true,
            log_level: config.general.log_level.clone().unwrap_or("trace".to_string()),
        },
        experimental: ShadowExperimental {
            runahead: None,
            use_dynamic_runahead: true,
        },
        network: ShadowNetwork {
            graph: match &config.network {
                Some(Network::Gml { path, .. }) => {
                    // Use the loaded and validated GML graph to generate network config
                    if let Some(ref gml) = gml_graph {
                        // Pass both the GML graph and the path to the file
                        generate_gml_network_config(gml, path)?
                    } else {
                        // Fallback to switch if GML loading failed
                        ShadowGraph {
                            graph_type: "1_gbit_switch".to_string(),
                            file: None,
                            nodes: None,
                            edges: None,
                        }
                    }
                },
                Some(Network::Switch { network_type, .. }) => ShadowGraph {
                    graph_type: network_type.clone(),
                    file: None,
                    nodes: None,
                    edges: None,
                },
                None => ShadowGraph {
                    graph_type: "1_gbit_switch".to_string(),
                    file: None,
                    nodes: None,
                    edges: None,
                },
            },
        },
        hosts: sorted_hosts_map,
    };

    // Write configuration
    let config_yaml = serde_yaml::to_string(&shadow_config)?;
    std::fs::write(output_path, config_yaml)?;

    println!("Generated Agent-based Shadow configuration at {:?}", output_path);
    println!("  - Simulation time: {}", config.general.stop_time);
    println!("  - Total hosts: {}", shadow_config.hosts.len());
    
    // Show network topology information
    match &config.network {
        Some(Network::Gml { path, .. }) => {
            if let Some(ref gml) = gml_graph {
                println!("  - Network topology: GML from '{}' ({} nodes, {} edges)",
                         path, gml.nodes.len(), gml.edges.len());

                // Show autonomous systems if available
                let as_groups = get_autonomous_systems(gml);
                if as_groups.len() > 1 {
                    println!("  - Autonomous systems: {} groups", as_groups.len());
                }
            }
        },
        Some(Network::Switch { network_type, .. }) => {
            println!("  - Network topology: Switch ({})", network_type);
        },
        None => {
            println!("  - Network topology: Default switch (1_gbit_switch)");
        }
    }
    
    println!("  - Agent registry created at {:?}", agent_registry_path);
    println!("  - Miner registry created at {:?}", miner_registry_path);

    // Log IP allocation statistics
    let ip_stats = ip_registry.get_allocation_stats();
    println!("  - IP Allocation Summary:");
    for (subnet, count) in ip_stats {
        println!("    - {}: {} IPs assigned", subnet, count);
    }
    println!("  - Total IPs assigned: {}", ip_registry.get_all_assigned_ips().len());

    Ok(())
}
