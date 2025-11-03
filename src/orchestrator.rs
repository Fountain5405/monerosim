//! Configuration orchestrator.
//!
//! This module coordinates the overall configuration generation process,
//! managing the flow from configuration parsing through Shadow YAML generation.

use crate::config_v2::{Config, Network, PeerMode};
use crate::gml_parser::{self, GmlGraph, validate_topology, get_autonomous_systems};
use crate::shadow::{
    MinerInfo, MinerRegistry, AgentInfo, AgentRegistry,
    ShadowConfig, ShadowGeneral, ShadowExperimental, ShadowNetwork, ShadowGraph,
    ShadowFileSource, ShadowHost,
};
use crate::topology::Topology;
use crate::utils::duration::parse_duration_to_seconds;
use crate::utils::validation::{validate_gml_ip_consistency, validate_topology_config};
use crate::ip::{GlobalIpRegistry, AsSubnetManager, AgentType, get_agent_ip};
use crate::agent::{process_user_agents, process_block_controller, process_miner_distributor, process_pure_script_agents, process_simulation_monitor};
use serde_json;
use serde_yaml;
use std::collections::HashMap;
use std::path::Path;

/// Generate Shadow network configuration from GML graph
pub fn generate_gml_network_config(gml_graph: &GmlGraph, _gml_path: &str) -> color_eyre::eyre::Result<ShadowGraph> {
    // Validate the topology first
    validate_topology(gml_graph).map_err(|e| color_eyre::eyre::eyre!("Invalid GML topology: {}", e))?;

    // Validate IP consistency
    validate_gml_ip_consistency(gml_graph).map_err(|e| color_eyre::eyre::eyre!("GML IP validation failed: {}", e))?;

    // Create a temporary GML file with converted attributes (e.g., packet_loss percentages to floats)
    let temp_gml_path = format!("/tmp/monerosim_gml_{}.gml", std::process::id());

    let mut gml_content = String::new();
    gml_content.push_str("graph [\n");

    // Add graph attributes
    for (key, value) in &gml_graph.attributes {
        gml_content.push_str(&format!("  {} {}\n", key, value));
    }

    // Add nodes
    for node in &gml_graph.nodes {
        gml_content.push_str("  node [\n");
        gml_content.push_str(&format!("    id {}\n", node.id));
        if let Some(label) = &node.label {
            gml_content.push_str(&format!("    label \"{}\"\n", label));
        }
        for (key, value) in &node.attributes {
            let (processed_value, quote) = if key == "bandwidth" {
                // Bandwidth is numeric, no quotes needed
                let processed = if value.ends_with("Gbit") {
                    // Convert Gbit to Mbit
                    if let Ok(gbit) = value.trim_end_matches("Gbit").parse::<f64>() {
                        format!("{}", gbit * 1000.0)
                    } else {
                        value.clone()
                    }
                } else if value.ends_with("Mbit") {
                    // Remove "Mbit" suffix
                    value.trim_end_matches("Mbit").to_string()
                } else {
                    value.clone()
                };
                (processed, false)
            } else {
                // String attributes like "region" need to be quoted
                (value.clone(), true)
            };
            if quote {
                gml_content.push_str(&format!("    {} \"{}\"\n", key, processed_value));
            } else {
                gml_content.push_str(&format!("    {} {}\n", key, processed_value));
            }
        }
        gml_content.push_str("  ]\n");
    }

    // Add edges with converted attributes
    for edge in &gml_graph.edges {
        gml_content.push_str("  edge [\n");
        gml_content.push_str(&format!("    source {}\n", edge.source));
        gml_content.push_str(&format!("    target {}\n", edge.target));
        for (key, value) in &edge.attributes {
            let (processed_value, quote) = if key == "packet_loss" || key == "bandwidth" {
                // These are numeric values, no quotes
                let processed = if key == "bandwidth" {
                    if value.ends_with("Gbit") {
                        // Convert Gbit to Mbit
                        if let Ok(gbit) = value.trim_end_matches("Gbit").parse::<f64>() {
                            format!("{}", gbit * 1000.0)
                        } else {
                            value.clone()
                        }
                    } else if value.ends_with("Mbit") {
                        // Remove "Mbit" suffix
                        value.trim_end_matches("Mbit").to_string()
                    } else {
                        value.clone()
                    }
                } else {
                    value.clone()
                };
                (processed, false)
            } else {
                // Keep latency as string with unit, quoted
                (value.clone(), true)
            };
            if quote {
                gml_content.push_str(&format!("    {} \"{}\"\n", key, processed_value));
            } else {
                gml_content.push_str(&format!("    {} {}\n", key, processed_value));
            }
        }
        gml_content.push_str("  ]\n");
    }

    gml_content.push_str("]\n");

    // Write the temporary GML file
    std::fs::write(&temp_gml_path, &gml_content)
        .map_err(|e| color_eyre::eyre::eyre!("Failed to write temporary GML file: {}", e))?;

    Ok(ShadowGraph {
        graph_type: "gml".to_string(),
        file: Some(ShadowFileSource {
            path: temp_gml_path,
        }),
        nodes: None,
        edges: None,
    })
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
        let graph = gml_parser::parse_gml_file(path)?;
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
