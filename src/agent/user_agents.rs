//! User agent processing.
//!
//! This module handles the configuration and processing of user agents,
//! including regular users and miners with their daemon and wallet settings.
//! It manages peer discovery, IP allocation, and process configuration for
//! user agents within the Shadow network simulator environment.

use crate::config_v2::{AgentDefinitions, AgentConfig, DaemonConfig, PeerMode, OptionValue};
use crate::gml_parser::GmlGraph;
use crate::shadow::{ShadowHost, ExpectedFinalState};
use crate::topology::{distribute_agents_across_topology, Topology, generate_topology_connections};
use crate::utils::duration::parse_duration_to_seconds;

/// Convert OptionValue map to command-line arguments
/// - Bool(true) -> --flag
/// - Bool(false) -> (omitted)
/// - String(s) -> --flag=s
/// - Number(n) -> --flag=n
fn options_to_args(options: &BTreeMap<String, OptionValue>) -> Vec<String> {
    options.iter().filter_map(|(key, value)| {
        match value {
            OptionValue::Bool(true) => Some(format!("--{}", key)),
            OptionValue::Bool(false) => None,
            OptionValue::String(s) => Some(format!("--{}={}", key, s)),
            OptionValue::Number(n) => Some(format!("--{}={}", key, n)),
        }
    }).collect()
}

/// Merge two option maps, with overrides taking precedence over defaults
fn merge_options(
    defaults: Option<&BTreeMap<String, OptionValue>>,
    overrides: Option<&BTreeMap<String, OptionValue>>,
) -> BTreeMap<String, OptionValue> {
    let mut merged = BTreeMap::new();

    // Apply defaults first
    if let Some(defs) = defaults {
        for (k, v) in defs {
            merged.insert(k.clone(), v.clone());
        }
    }

    // Apply overrides (these take precedence)
    if let Some(ovrs) = overrides {
        for (k, v) in ovrs {
            merged.insert(k.clone(), v.clone());
        }
    }

    merged
}
use crate::utils::binary::resolve_binary_path_for_shadow;
use crate::ip::{GlobalIpRegistry, AsSubnetManager, AgentType, get_agent_ip};
use crate::process::{add_wallet_process, add_remote_wallet_process, add_user_agent_process, create_mining_agent_process};
use std::collections::{BTreeMap, HashMap};
use std::path::Path;

/// Process user agents
pub fn process_user_agents(
    agents: &AgentDefinitions,
    hosts: &mut BTreeMap<String, ShadowHost>,
    seed_agents: &mut Vec<String>,
    effective_seed_nodes: &[String],
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    monerod_path: &str,
    wallet_path: &str,
    environment: &BTreeMap<String, String>,
    monero_environment: &BTreeMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    peer_mode: &PeerMode,
    topology: Option<&Topology>,
    enable_dns_server: bool,
    daemon_defaults: Option<&BTreeMap<String, OptionValue>>,
    wallet_defaults: Option<&BTreeMap<String, OptionValue>>,
) -> color_eyre::eyre::Result<()> {
    // Filter agents that have daemon or wallet (user agents, not script-only)
    let user_agents: Vec<(&String, &AgentConfig)> = agents.agents.iter()
        .filter(|(_, config)| config.has_local_daemon() || config.has_remote_daemon() || config.has_wallet())
        .collect();

    // Get agent distribution across GML nodes if available AND we're actually using GML topology
    let agent_node_assignments = if let Some(gml) = gml_graph {
        if !user_agents.is_empty() {
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

    // No phase validation needed for new AgentConfig (simpler structure)

    // First, collect all agent information to build connection graphs
    let mut agent_info = Vec::new();
    let mut all_agent_ips = Vec::new(); // Collect all agent IPs for topology connections
    let mut miners = Vec::new();
    let mut seed_nodes = Vec::new();
    let mut regular_agents = Vec::new();

    for (i, (agent_id, agent_config)) in user_agents.iter().enumerate() {
        let is_miner = agent_config.is_miner();
        let is_seed_node = is_miner || agent_config.attributes.as_ref()
            .map(|attrs| attrs.get("seed-node").map_or(false, |v| v == "true"))
            .unwrap_or(false);

        // Determine network node ID for this agent
        let network_node_id = if i < agent_node_assignments.len() {
            agent_node_assignments[i]
        } else {
            0 // Fallback to node 0 for switch-based networks
        };

        // Get agent IP using dynamic assignment
        let agent_ip = get_agent_ip(AgentType::UserAgent, agent_id, i, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
        let agent_port = 18080;

        // Collect all agent IPs for topology connections
        all_agent_ips.push(format!("{}:{}", agent_ip, agent_port));

        let agent_entry = (i, is_miner, is_seed_node, agent_id.to_string(), agent_ip.clone(), agent_port);

        if is_miner {
            miners.push(agent_entry);
        } else if is_seed_node {
            seed_nodes.push(agent_entry);
        } else {
            regular_agents.push(agent_entry);
        }

        agent_info.push((i, is_miner, is_seed_node, agent_id.to_string(), agent_ip, agent_port));
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
    for (i, (agent_id, user_agent_config)) in user_agents.iter().enumerate() {
        // Determine agent type and start time
        let is_miner = user_agent_config.is_miner();
        let is_seed_node = is_miner || user_agent_config.attributes.as_ref()
            .map(|attrs| attrs.get("seed-node").map_or(false, |v| v == "true"))
            .unwrap_or(false);

        // Parse start_time if present (e.g., "2h", "7200s", "30m")
        let start_time_offset_seconds: u64 = user_agent_config.start_time
            .as_ref()
            .and_then(|offset| parse_duration_to_seconds(offset).ok())
            .unwrap_or(0);

            // Monero coinbase maturity = 60 blocks, block time = 120s (DIFFICULTY_TARGET_V2)
            // Regular users must wait for block maturity before spending: 60 × 120s = 7200s
            const BLOCK_MATURITY_SECONDS: u64 = 7200; // 60 blocks × 120s

            let base_start_time_seconds = if matches!(peer_mode, PeerMode::Dynamic) {
                // Dynamic mode launch sequence
                if is_miner {
                    // Miners start immediately to mine blocks
                    if i == 0 {
                        0u64 // First miner (node 0) at t=0s
                    } else {
                        1 + i as u64 // Remaining miners every 1s starting t=1s
                    }
                } else {
                    // Regular users wait for block maturity (60 blocks), then stagger
                    BLOCK_MATURITY_SECONDS + (i.saturating_sub(miners.len())) as u64
                }
            } else {
                // Other modes
                if is_miner {
                    i as u64 // Miners start early, staggered by 1s
                } else if is_seed_node || seed_nodes.iter().any(|(_, _, is_s, _, _, _)| *is_s && agent_info[i].0 == i) {
                    BLOCK_MATURITY_SECONDS // Seeds start after block maturity
                } else {
                    // Regular agents start after block maturity, with stagger
                    let regular_index = regular_agents.iter().position(|(idx, _, _, _, _, _)| *idx == i).unwrap_or(0);
                    BLOCK_MATURITY_SECONDS + regular_index as u64 // Stagger by 1s
                }
            };

            // Apply start_time_offset: if specified, use it directly (replaces base time)
            // If not specified (0), use the calculated base time
            let effective_start_time = if start_time_offset_seconds > 0 {
                start_time_offset_seconds  // Use explicit offset as absolute start time
            } else {
                base_start_time_seconds  // Use calculated default
            };
            let start_time_daemon = format!("{}s", effective_start_time);

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

            // Determine network node ID for this agent
            let network_node_id = if i < agent_node_assignments.len() {
                agent_node_assignments[i]
            } else {
                0 // Fallback to node 0 for switch-based networks
            };

            // Get agent IP using dynamic assignment
            let agent_ip = get_agent_ip(AgentType::UserAgent, &agent_id, i, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
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
            let has_daemon_phases = user_agent_config.has_daemon_phases();
            let has_wallet_phases = user_agent_config.has_wallet_phases();

            // Get process_threads from environment (convenience setting)
            let process_threads: u32 = monero_environment.get("PROCESS_THREADS")
                .and_then(|s| s.parse().ok())
                .unwrap_or(0);

            // Merge daemon_defaults with per-agent daemon_options
            let merged_daemon_options = merge_options(daemon_defaults, user_agent_config.daemon_options.as_ref());

            let build_daemon_args_base = |phase_args: Option<&Vec<String>>| -> Vec<String> {
                // Start with required/injected flags that cannot be overridden
                let mut args = vec![
                    format!("--data-dir=/tmp/monero-{}", agent_id),
                    "--regtest".to_string(),
                    "--keep-fakechain".to_string(),
                ];

                // Add process_threads flags if set and not overridden in daemon_defaults
                if process_threads > 0 {
                    if !merged_daemon_options.contains_key("prep-blocks-threads") {
                        args.push(format!("--prep-blocks-threads={}", process_threads));
                    }
                    if !merged_daemon_options.contains_key("max-concurrency") {
                        args.push(format!("--max-concurrency={}", process_threads));
                    }
                }

                // Add configurable options from merged daemon_defaults + daemon_options
                args.extend(options_to_args(&merged_daemon_options));

                // Add required network binding flags (always injected, use agent-specific values)
                args.extend(vec![
                    format!("--rpc-bind-ip={}", agent_ip),
                    format!("--rpc-bind-port={}", agent_rpc_port),
                    "--confirm-external-bind".to_string(),
                    "--rpc-access-control-origins=*".to_string(),
                    format!("--p2p-bind-ip={}", agent_ip),
                    format!("--p2p-bind-port={}", p2p_port),
                ]);

                // Add DNS and seed node settings
                if !enable_dns_server {
                    args.push("--disable-dns-checkpoints".to_string());
                }
                if is_miner && !enable_dns_server {
                    args.push("--disable-seed-nodes".to_string());
                }

                // Add initial fixed connections
                if is_miner {
                    if let Some(conns) = miner_connections.get(*agent_id) {
                        for conn in conns {
                            args.push(conn.clone());
                        }
                    }
                } else if is_seed_node || seed_nodes.iter().any(|(_, _, is_s, _, _, _)| *is_s && agent_info[i].0 == i) {
                    if let Some(conns) = seed_connections.get(*agent_id) {
                        for conn in conns {
                            args.push(conn.clone());
                        }
                    }
                }

                // Add peer connections for regular agents
                let is_actual_seed_node = seed_nodes.iter().any(|(idx, _, _, _, _, _)| *idx == i);
                if !is_miner && !is_actual_seed_node {
                    for seed_node in seed_agents.iter() {
                        if !seed_node.starts_with(&format!("{}:", agent_ip)) {
                            let peer_arg = if matches!(peer_mode, PeerMode::Dynamic) {
                                format!("--seed-node={}", seed_node)
                            } else {
                                format!("--add-priority-node={}", seed_node)
                            };
                            args.push(peer_arg);
                        }
                    }
                    if matches!(peer_mode, PeerMode::Hybrid) {
                        if let Some(topo) = topology {
                            let topology_connections = generate_topology_connections(topo, i, &all_agent_ips, &agent_ip);
                            for conn in topology_connections {
                                args.push(conn);
                            }
                        }
                    }
                }

                // Add phase-specific args
                if let Some(custom_args) = phase_args {
                    for arg in custom_args {
                        args.push(arg.clone());
                    }
                }

                args
            };

            // Add Monero daemon process(es) - either simple or phase-based
            if has_daemon_phases {
                // Phase-based daemon configuration (upgrade scenario)
                let phases = user_agent_config.daemon_phases.as_ref().unwrap();
                let phase_count = phases.len();

                for (phase_num, phase) in phases {
                    let daemon_args_base = build_daemon_args_base(phase.args.as_ref());
                    let daemon_args = daemon_args_base.join(" ");

                    // Resolve binary path for this phase
                    let daemon_binary_path = resolve_binary_path_for_shadow(&phase.path)
                        .unwrap_or_else(|_| monerod_path.to_string());

                    // Build environment for this phase
                    let mut daemon_env = monero_environment.clone();
                    if let Some(custom_env) = &phase.env {
                        for (key, value) in custom_env {
                            daemon_env.insert(key.clone(), value.clone());
                        }
                    }

                    // Determine start time
                    let start_time = if let Some(start) = &phase.start {
                        start.clone()
                    } else if *phase_num == 0 {
                        start_time_daemon.clone()
                    } else {
                        // Should have been caught by validation
                        start_time_daemon.clone()
                    };

                    // Determine shutdown time and expected final state
                    let (shutdown_time, expected_final_state) = if *phase_num < (phase_count as u32 - 1) {
                        // Not the last phase - needs shutdown
                        (
                            phase.stop.clone(),
                            Some(ExpectedFinalState::Signaled("SIGTERM".to_string())),
                        )
                    } else {
                        // Last phase - runs until simulation end
                        (None, None)
                    };

                    // For phase 0, include the data directory cleanup
                    let args = if *phase_num == 0 {
                        format!(
                            "-c 'rm -rf /tmp/monero-{} && {} {}'",
                            agent_id, daemon_binary_path, daemon_args
                        )
                    } else {
                        // Later phases reuse the existing data directory
                        format!("-c '{} {}'", daemon_binary_path, daemon_args)
                    };

                    processes.push(crate::shadow::ShadowProcess {
                        path: "/bin/bash".to_string(),
                        args,
                        environment: daemon_env,
                        start_time,
                        shutdown_time,
                        expected_final_state,
                    });
                }
            } else if has_local_daemon {
                // Simple daemon configuration (single binary)
                let daemon_args_base = build_daemon_args_base(user_agent_config.daemon_args.as_ref());
                let daemon_args = daemon_args_base.join(" ");

                // Get daemon binary path from config, fall back to default
                let daemon_binary_path = match &user_agent_config.daemon {
                    Some(DaemonConfig::Local(path)) => {
                        resolve_binary_path_for_shadow(path).unwrap_or_else(|_| monerod_path.to_string())
                    }
                    _ => monerod_path.to_string(),
                };

                // Merge custom environment from config with base environment
                let mut daemon_env = monero_environment.clone();
                if let Some(custom_env) = &user_agent_config.daemon_env {
                    for (key, value) in custom_env {
                        daemon_env.insert(key.clone(), value.clone());
                    }
                }

                processes.push(crate::shadow::ShadowProcess {
                    path: "/bin/bash".to_string(),
                    args: format!(
                        "-c 'rm -rf /tmp/monero-{} && {} {}'",
                        agent_id, daemon_binary_path, daemon_args
                    ),
                    environment: daemon_env,
                    start_time: start_time_daemon.clone(),
                    shutdown_time: None,
                    expected_final_state: None,
                });
            } // End of daemon configuration

            // Add wallet process based on agent type
            // Merge wallet_defaults with per-agent wallet_options
            let merged_wallet_options = merge_options(wallet_defaults, user_agent_config.wallet_options.as_ref());

            if has_wallet_phases {
                // Phase-based wallet configuration (upgrade scenario)
                let phases = user_agent_config.wallet_phases.as_ref().unwrap();
                let phase_count = phases.len();

                // Build base wallet args
                let build_wallet_args = |phase_args: Option<&Vec<String>>| -> Vec<String> {
                    let mut args = vec![
                        format!("--daemon-address=http://{}:{}", agent_ip, agent_rpc_port),
                        format!("--rpc-bind-port={}", wallet_rpc_port),
                        format!("--rpc-bind-ip={}", agent_ip),
                        "--disable-rpc-login".to_string(),
                        "--trusted-daemon".to_string(),
                        format!("--wallet-dir=/tmp/monerosim_shared/{}_wallet", agent_id),
                        "--confirm-external-bind".to_string(),
                        "--allow-mismatched-daemon-version".to_string(),
                    ];

                    // Add process_threads flag if set and not overridden in wallet_defaults
                    if process_threads > 0 && !merged_wallet_options.contains_key("max-concurrency") {
                        args.push(format!("--max-concurrency={}", process_threads));
                    }

                    // Add configurable options from merged wallet_defaults + wallet_options
                    args.extend(options_to_args(&merged_wallet_options));

                    args.push("--daemon-ssl-allow-any-cert".to_string());

                    // Add custom phase args
                    if let Some(custom_args) = phase_args {
                        for arg in custom_args {
                            args.push(arg.clone());
                        }
                    }

                    args
                };

                for (phase_num, phase) in phases {
                    let wallet_args_vec = build_wallet_args(phase.args.as_ref());
                    let wallet_args = wallet_args_vec.join(" ");

                    // Resolve binary path for this phase
                    let wallet_binary_path = resolve_binary_path_for_shadow(&phase.path)
                        .unwrap_or_else(|_| wallet_path.to_string());

                    // Build environment for this phase
                    let mut wallet_env = environment.clone();
                    if let Some(custom_env) = &phase.env {
                        for (key, value) in custom_env {
                            wallet_env.insert(key.clone(), value.clone());
                        }
                    }

                    // Determine start time
                    let start_time = if let Some(start) = &phase.start {
                        start.clone()
                    } else if *phase_num == 0 {
                        wallet_start_time.clone()
                    } else {
                        // Should have been caught by validation
                        wallet_start_time.clone()
                    };

                    // Determine shutdown time and expected final state
                    let (shutdown_time, expected_final_state) = if *phase_num < (phase_count as u32 - 1) {
                        // Not the last phase - needs shutdown
                        (
                            phase.stop.clone(),
                            Some(ExpectedFinalState::Signaled("SIGTERM".to_string())),
                        )
                    } else {
                        // Last phase - runs until simulation end
                        (None, None)
                    };

                    // For phase 0, include the wallet directory cleanup
                    let cleanup_start_time = if let Ok(wallet_seconds) = parse_duration_to_seconds(&start_time) {
                        format!("{}s", wallet_seconds.saturating_sub(2))
                    } else {
                        format!("{}s", 48 + i * 2) // Fallback
                    };

                    if *phase_num == 0 {
                        // Clean up wallet directory before phase 0
                        processes.push(crate::shadow::ShadowProcess {
                            path: "/bin/bash".to_string(),
                            args: format!(
                                "-c 'rm -rf /tmp/monerosim_shared/{}_wallet && mkdir -p /tmp/monerosim_shared/{}_wallet'",
                                agent_id, agent_id
                            ),
                            environment: environment.clone(),
                            start_time: cleanup_start_time,
                            shutdown_time: None,
                            expected_final_state: None,
                        });
                    }

                    processes.push(crate::shadow::ShadowProcess {
                        path: "/bin/bash".to_string(),
                        args: format!("-c '{} {}'", wallet_binary_path, wallet_args),
                        environment: wallet_env,
                        start_time,
                        shutdown_time,
                        expected_final_state,
                    });
                }
            } else if has_wallet {
                // Simple wallet configuration (single binary)
                let wallet_binary_path = if let Some(wallet_spec) = &user_agent_config.wallet {
                    resolve_binary_path_for_shadow(wallet_spec).unwrap_or_else(|_| wallet_path.to_string())
                } else {
                    wallet_path.to_string()
                };

                if has_local_daemon || has_daemon_phases {
                    // Full agent: wallet connects to local daemon
                    add_wallet_process(
                        &mut processes,
                        &agent_id,
                        &agent_ip,
                        agent_rpc_port,
                        wallet_rpc_port,
                        &wallet_binary_path,
                        environment,
                        i,
                        &wallet_start_time,
                        user_agent_config.wallet_args.as_ref(),
                        user_agent_config.wallet_env.as_ref(),
                        wallet_defaults,
                        user_agent_config.wallet_options.as_ref(),
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
                        &wallet_binary_path,
                        environment,
                        i,
                        &wallet_start_time,
                        user_agent_config.wallet_args.as_ref(),
                        user_agent_config.wallet_env.as_ref(),
                        wallet_defaults,
                        user_agent_config.wallet_options.as_ref(),
                    );
                }
            }

            // Add agent scripts
            let script = user_agent_config.script.clone()
                .unwrap_or_else(|| "agents.regular_user".to_string());

            if is_miner && script.contains("autonomous_miner") {
                // HYBRID APPROACH for miners: Run both regular_user (for wallet) AND mining_script

                // Build merged attributes that include typed fields (hashrate, is_miner, can_receive_distributions)
                let mut merged_attributes = user_agent_config.attributes.clone().unwrap_or_default();
                merged_attributes.insert("is_miner".to_string(), "true".to_string());
                if let Some(hashrate) = user_agent_config.hashrate {
                    merged_attributes.insert("hashrate".to_string(), hashrate.to_string());
                }
                if user_agent_config.can_receive_distributions() {
                    merged_attributes.insert("can_receive_distributions".to_string(), "true".to_string());
                }

                // Step 1: Run regular_user.py first for wallet creation and address registration
                add_user_agent_process(
                    &mut processes,
                    agent_id,
                    &agent_ip,
                    if has_local_daemon { Some(agent_rpc_port) } else { None },
                    if has_wallet { Some(wallet_rpc_port) } else { None },
                    if has_local_daemon { Some(p2p_port) } else { None },
                    "agents.regular_user",
                    Some(&merged_attributes),
                    environment,
                    shared_dir,
                    current_dir,
                    i,
                    environment.get("stop_time").map(|s| s.as_str()).unwrap_or("1800"),
                    Some(&agent_start_time),
                    user_agent_config.remote_daemon_address(),
                    user_agent_config.daemon_selection_strategy().map(|s| s.as_str()),
                );

                // Step 2: Run mining_script (autonomous_miner.py)
                let mining_start_time = if let Ok(agent_seconds) = parse_duration_to_seconds(&agent_start_time) {
                    format!("{}s", agent_seconds + 10)
                } else {
                    format!("{}s", 75 + i * 2)
                };

                let mining_wallet_port = if user_agent_config.wallet.is_some() {
                    Some(wallet_rpc_port)
                } else {
                    None
                };

                let mining_processes = create_mining_agent_process(
                    agent_id,
                    &agent_ip,
                    agent_rpc_port,
                    mining_wallet_port,
                    &script,
                    Some(&merged_attributes),
                    environment,
                    shared_dir,
                    current_dir,
                    i,
                    environment.get("stop_time").map(|s| s.as_str()).unwrap_or("1800"),
                    Some(&mining_start_time),
                );
                processes.extend(mining_processes);
            } else if !script.is_empty() {
                // Regular user agent script
                add_user_agent_process(
                    &mut processes,
                    agent_id,
                    &agent_ip,
                    if has_local_daemon { Some(agent_rpc_port) } else { None },
                    if has_wallet { Some(wallet_rpc_port) } else { None },
                    if has_local_daemon { Some(p2p_port) } else { None },
                    &script,
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

            // Only add the host if it has any processes
            if !processes.is_empty() {
                // Determine network node ID based on GML assignment or fallback
                let network_node_id = if i < agent_node_assignments.len() {
                    agent_node_assignments[i]
                } else {
                    0 // Fallback to node 0 for switch-based networks
                };

                hosts.insert(agent_id.to_string(), ShadowHost {
                    network_node_id,
                    ip_addr: Some(agent_ip.clone()),
                    processes,
                    bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
                    bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
                });
                // Note: next_ip is already incremented in get_agent_ip function
            }
    }

    Ok(())
}
