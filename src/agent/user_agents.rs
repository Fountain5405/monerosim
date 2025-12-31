//! User agent processing.
//!
//! This module handles the configuration and processing of user agents,
//! including regular users and miners with their daemon and wallet settings.
//! It manages peer discovery, IP allocation, and process configuration for
//! user agents within the Shadow network simulator environment.

use crate::config_v2::{AgentDefinitions, PeerMode};
use crate::gml_parser::GmlGraph;
use crate::shadow::ShadowHost;
use crate::topology::{distribute_agents_across_topology, Topology, generate_topology_connections};
use crate::utils::duration::parse_duration_to_seconds;
use crate::ip::{GlobalIpRegistry, AsSubnetManager, AgentType, get_agent_ip};
use crate::process::{add_wallet_process, add_remote_wallet_process, add_user_agent_process, create_mining_agent_process};
use std::collections::HashMap;
use std::path::Path;

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
    enable_dns_server: bool,
    miner_seed_ip_map: &HashMap<String, String>,
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

            // Check if this miner has a pre-assigned mainnet seed IP (for bootstrap nodes)
            // Only the first N miners get mainnet seed IPs to act as bootstrap nodes
            let agent_ip = if let Some(seed_ip) = miner_seed_ip_map.get(&agent_id) {
                // Use the pre-assigned mainnet seed IP for this bootstrap miner
                log::info!("Using mainnet seed IP {} for bootstrap miner {}", seed_ip, agent_id);
                seed_ip.clone()
            } else {
                // Use dynamic IP assignment for non-bootstrap nodes
                get_agent_ip(AgentType::UserAgent, &agent_id, i, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry)
            };
            let agent_port = 18080;

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

            // Parse start_time_offset if present (e.g., "2h", "7200s", "30m")
            let start_time_offset_seconds: u64 = user_agent_config.start_time_offset
                .as_ref()
                .and_then(|offset| parse_duration_to_seconds(offset).ok())
                .unwrap_or(0);

            let base_start_time_seconds = if matches!(peer_mode, PeerMode::Dynamic) {
                // Optimized Dynamic mode launch sequence - reduced staggered timing
                if is_miner {
                    if i == 0 {
                        0u64 // First miner (node 0) at t=0s
                    } else {
                        1 + i as u64 // Remaining miners every 1s starting t=1s
                    }
                } else {
                    // Regular users start after miners, with reduced stagger
                    5 + (i.saturating_sub(miners.len())) as u64
                }
            } else {
                // Optimized logic for other modes - reduced timing
                if is_miner {
                    i as u64 // Miners start early, staggered by 1s
                } else if is_seed_node || seed_nodes.iter().any(|(_, _, is_s, _, _, _)| *is_s && agent_info[i].0 == i) {
                    3u64 // Seeds start at 3s
                } else {
                    // Regular agents start after seeds, with reduced stagger
                    let regular_index = regular_agents.iter().position(|(idx, _, _, _, _, _)| *idx == i).unwrap_or(0);
                    6 + regular_index as u64 // Stagger by 1s
                }
            };

            // Apply start_time_offset if specified in config
            let start_time_daemon = format!("{}s", base_start_time_seconds + start_time_offset_seconds);

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

            // Check if this miner has a pre-assigned mainnet seed IP (for bootstrap nodes)
            let agent_ip = if let Some(seed_ip) = miner_seed_ip_map.get(&agent_id) {
                // Use the pre-assigned mainnet seed IP for this bootstrap miner
                seed_ip.clone()
            } else {
                // Use dynamic IP assignment for non-bootstrap nodes
                get_agent_ip(AgentType::UserAgent, &agent_id, i, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry)
            };
            let _agent_port = 18080;

            // Use standard RPC ports for all agents (mainnet ports for FAKECHAIN/regtest)
            let agent_rpc_port = 18081;

            // Use standard wallet RPC port for all agents
            // Since each agent has its own IP address, they can all use the same port
            let wallet_rpc_port = 18082;
            let p2p_port = 18080;

            let mut processes = Vec::new();

            // Determine agent type
            let has_local_daemon = user_agent_config.has_local_daemon();
            let has_remote_daemon = user_agent_config.has_remote_daemon();
            let has_wallet = user_agent_config.has_wallet();
            let _is_script_only = user_agent_config.is_script_only();

            // Add Monero daemon process only if agent has local daemon
            if has_local_daemon {
            let mut daemon_args_base = vec![
                format!("--data-dir=/tmp/monero-{}", agent_id),
                "--log-file=/dev/stdout".to_string(),
                "--log-level=1".to_string(),
                // "--simulation".to_string(), // TEST: Disabled to verify Shadow socket fixes
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

            // When DNS server is NOT enabled, disable DNS checkpoints
            // When DNS server IS enabled, monerod will use DNS_PUBLIC for peer discovery
            if !enable_dns_server {
                daemon_args_base.push("--disable-dns-checkpoints".to_string());
            }

            // Only disable built-in seed nodes for miners when DNS server is not enabled
            // When DNS server is enabled, miners can discover peers via DNS
            if is_miner && !enable_dns_server {
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

            processes.push(crate::shadow::ShadowProcess {
                path: "/bin/bash".to_string(),
                args: format!(
                    "-c 'rm -rf /tmp/monero-{} && {} {}'",
                    agent_id, monerod_path, daemon_args
                ),
                environment: monero_environment.clone(),
                start_time: start_time_daemon.clone(),
            });
            } // End of if has_local_daemon

            // Add wallet process based on agent type
            if has_wallet {
                if has_local_daemon {
                    // Full agent: wallet connects to local daemon
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
                } else if has_remote_daemon {
                    // Wallet-only agent: wallet connects to remote daemon
                    let remote_addr = user_agent_config.remote_daemon_address();
                    add_remote_wallet_process(
                        &mut processes,
                        &agent_id,
                        &agent_ip,
                        remote_addr,
                        wallet_rpc_port,
                        environment,
                        i,
                        &wallet_start_time,
                    );
                }
            }

            // Add agent scripts
            // For hybrid mining approach: run regular_user first (wallet setup), then mining_script
            if let Some(mining_script) = &user_agent_config.mining_script {
                // HYBRID APPROACH: Run both regular_user (for wallet) AND mining_script

                // Step 1: Run regular_user.py first for wallet creation and address registration
                // This handles wallet creation and writes to {agent_id}_miner_info.json
                let wallet_setup_script = user_agent_config.user_script.clone()
                    .unwrap_or_else(|| "agents.regular_user".to_string());

                if !wallet_setup_script.is_empty() {
                    add_user_agent_process(
                        &mut processes,
                        &agent_id,
                        &agent_ip,
                        if has_local_daemon { Some(agent_rpc_port) } else { None },
                        if has_wallet { Some(wallet_rpc_port) } else { None },
                        if has_local_daemon { Some(p2p_port) } else { None },
                        &wallet_setup_script,
                        user_agent_config.attributes.as_ref(),
                        environment,
                        shared_dir,
                        current_dir,
                        i,
                        environment.get("stop_time").map(|s| s.as_str()).unwrap_or("1800"),
                        Some(&agent_start_time),
                        user_agent_config.remote_daemon_address(),
                        user_agent_config.daemon_selection_strategy().map(|s| s.as_str()),
                    );
                }

                // Step 2: Run mining_script (autonomous_miner.py) which polls for the address
                // Start mining script a bit later to give regular_user time to register address
                let mining_start_time = if let Ok(agent_seconds) = parse_duration_to_seconds(&agent_start_time) {
                    format!("{}s", agent_seconds + 10) // Start 10 seconds after regular_user
                } else {
                    format!("{}s", 75 + i * 2) // Fallback timing
                };

                // Pass wallet_rpc_port if wallet is configured
                let mining_wallet_port = if user_agent_config.wallet.is_some() {
                    Some(wallet_rpc_port)
                } else {
                    None
                };

                let mining_processes = create_mining_agent_process(
                    &agent_id,
                    &agent_ip,
                    agent_rpc_port,
                    mining_wallet_port,
                    mining_script,
                    user_agent_config.attributes.as_ref(),
                    environment,
                    shared_dir,
                    current_dir,
                    i,
                    environment.get("stop_time").map(|s| s.as_str()).unwrap_or("1800"),
                    Some(&mining_start_time),
                );
                processes.extend(mining_processes);
            } else {
                // Regular user agent script (no mining_script specified)
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
                        if has_local_daemon { Some(agent_rpc_port) } else { None },
                        if has_wallet { Some(wallet_rpc_port) } else { None },
                        if has_local_daemon { Some(p2p_port) } else { None },
                        &user_script,
                        user_agent_config.attributes.as_ref(),
                        environment,
                        shared_dir,
                        current_dir,
                        i,
                        environment.get("stop_time").map(|s| s.as_str()).unwrap_or("1800"),
                        Some(&agent_start_time),
                        user_agent_config.remote_daemon_address(),
                        user_agent_config.daemon_selection_strategy().map(|s| s.as_str()),
                    );
                }
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
