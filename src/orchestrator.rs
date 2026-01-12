//! Configuration orchestrator.
//!
//! This module coordinates the overall configuration generation process,
//! managing the flow from configuration parsing through Shadow YAML generation.

use crate::config_v2::{Config, Network, PeerMode};
use crate::gml_parser::{self, GmlGraph, validate_topology, get_autonomous_systems};
use crate::shadow::{
    MinerInfo, MinerRegistry, AgentInfo, AgentRegistry,
    PublicNodeInfo, PublicNodeRegistry,
    ShadowConfig, ShadowGeneral, ShadowExperimental, ShadowNetwork, ShadowGraph,
    ShadowFileSource, ShadowHost,
};
use crate::topology::Topology;
use crate::utils::duration::parse_duration_to_seconds;
use crate::utils::validation::{validate_gml_ip_consistency, validate_topology_config, validate_simulation_seed};
use crate::ip::{GlobalIpRegistry, AsSubnetManager, AgentType, get_agent_ip};
use crate::agent::{process_user_agents, process_miner_distributor, process_pure_script_agents, process_simulation_monitor};
use serde_json;
use serde_yaml;
use std::collections::BTreeMap;
use std::path::Path;
use std::fs;

/// Detect the Python site-packages path in the virtual environment.
/// Looks for venv/lib/python*/site-packages and returns the path.
fn detect_venv_site_packages(base_dir: &str) -> Option<String> {
    let venv_lib = format!("{}/venv/lib", base_dir);
    if let Ok(entries) = fs::read_dir(&venv_lib) {
        for entry in entries.flatten() {
            let name = entry.file_name();
            let name_str = name.to_string_lossy();
            if name_str.starts_with("python") {
                let site_packages = format!("{}/{}/site-packages", venv_lib, name_str);
                if Path::new(&site_packages).exists() {
                    return Some(site_packages);
                }
            }
        }
    }
    None
}

/// Generate Shadow network configuration from GML graph
pub fn generate_gml_network_config(gml_graph: &GmlGraph, _gml_path: &str) -> color_eyre::eyre::Result<ShadowGraph> {
    // Validate the topology first
    validate_topology(gml_graph).map_err(|e| color_eyre::eyre::eyre!("Invalid GML topology: {}", e))?;

    // Validate IP consistency
    validate_gml_ip_consistency(gml_graph).map_err(|e| color_eyre::eyre::eyre!("GML IP validation failed: {}", e))?;

    // Create a temporary GML file with converted attributes (e.g., packet_loss percentages to floats)
    // Use fixed path for determinism (process ID would vary between runs)
    let temp_gml_path = "/tmp/monerosim_gml.gml".to_string();

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

    // Validate simulation seed
    validate_simulation_seed(config.general.simulation_seed)
        .map_err(|e| color_eyre::eyre::eyre!("Simulation seed validation failed: {}", e))?;

    // Mining and agent configuration validation is handled by AgentConfig methods

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

    let mut hosts: BTreeMap<String, ShadowHost> = BTreeMap::new();

    // Get HOME from the current environment for use in simulated processes
    let home_dir = std::env::var("HOME").unwrap_or_else(|_| "/root".to_string());

    // Common environment variables
    let mut environment: BTreeMap<String, String> = [
        ("HOME".to_string(), home_dir), // Required for $HOME expansion in binary paths
        ("MALLOC_MMAP_THRESHOLD_".to_string(), "131072".to_string()),
        ("MALLOC_TRIM_THRESHOLD_".to_string(), "131072".to_string()),
        ("GLIBC_TUNABLES".to_string(), "glibc.malloc.arena_max=1".to_string()),
        ("MALLOC_ARENA_MAX".to_string(), "1".to_string()),
        ("PYTHONUNBUFFERED".to_string(), "1".to_string()), // Ensure Python output is unbuffered
        ("PYTHONHASHSEED".to_string(), "0".to_string()), // Deterministic Python hash() for reproducibility
        ("SIMULATION_SEED".to_string(), config.general.simulation_seed.to_string()), // Add simulation seed for all agents
        ("DIFFICULTY_CACHE_TTL".to_string(), config.general.difficulty_cache_ttl.to_string()), // TTL for miner difficulty caching
        ("PROCESS_THREADS".to_string(), config.general.process_threads.unwrap_or(1).to_string()), // Thread count for monerod/wallet-rpc
    ].iter().cloned().collect();

    // Add MONEROSIM_LOG_LEVEL if specified in config
    if let Some(log_level) = &config.general.log_level {
        environment.insert("MONEROSIM_LOG_LEVEL".to_string(), log_level.to_uppercase());
    }

    // Monero-specific environment variables
    let mut monero_environment = environment.clone();
    monero_environment.insert("MONERO_BLOCK_SYNC_SIZE".to_string(), "1".to_string());
    monero_environment.insert("MONERO_MAX_CONNECTIONS_PER_IP".to_string(), "20".to_string());

    // Create centralized IP registry for robust IP management
    let mut ip_registry = GlobalIpRegistry::new();

    // Create AS-aware subnet manager for GML topology compatibility
    let mut subnet_manager = AsSubnetManager::new();

    // DNS server configuration - allocate IP from node 0's subnet for proper routing
    let enable_dns_server = config.general.enable_dns_server.unwrap_or(false);
    let dns_server_ip: Option<String> = if enable_dns_server {
        // Allocate DNS server IP from node 0's subnet (AS "0") for GML routing compatibility
        // This ensures the DNS server is reachable from all other nodes via the GML topology
        let dns_ip = get_agent_ip(
            AgentType::Infrastructure,
            "dnsserver",
            0,  // agent index
            0,  // network_node_id 0
            gml_graph.as_ref(),
            gml_graph.is_some(),  // using_gml_topology
            &mut subnet_manager,
            &mut ip_registry,
        );
        Some(dns_ip)
    } else {
        None
    };

    // Set DNS configuration based on whether DNS server is enabled
    if let Some(ref dns_ip) = dns_server_ip {
        // Use our DNS server for peer discovery
        monero_environment.insert("DNS_PUBLIC".to_string(), format!("tcp://{}", dns_ip));
    } else {
        // Disable DNS (legacy behavior)
        monero_environment.insert("MONERO_DISABLE_DNS".to_string(), "1".to_string());
    }

    // Helper to get absolute path for binaries (installed to ~/.monerosim/bin by setup.sh)
    let monerod_path = "$HOME/.monerosim/bin/monerod".to_string();
    let wallet_path = "$HOME/.monerosim/bin/monero-wallet-rpc".to_string();

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
    // Count user agents (agents with daemon or wallet)
    let user_agent_count = config.agents.agents.iter()
        .filter(|(_, cfg)| cfg.has_local_daemon() || cfg.has_remote_daemon() || cfg.has_wallet())
        .count();

    if let Some(topo) = &topology {
        if let Err(e) = validate_topology_config(topo, user_agent_count) {
            println!("Warning: Topology validation failed: {}", e);
            // Continue with default DAG topology
        }
    }

    // Use the configured seed nodes, or collect miner IPs if not provided
    let effective_seed_nodes = if seed_node_list.is_empty() {
        // Collect actual miner IPs for seed nodes
        let mut miner_ips = Vec::new();
        for (i, (agent_id, agent_config)) in config.agents.agents.iter()
            .filter(|(_, cfg)| cfg.has_local_daemon() || cfg.has_remote_daemon() || cfg.has_wallet())
            .enumerate()
        {
            if agent_config.is_miner() {
                // For seed node IP calculation, use node 0 (switch topology assumption)
                let network_node_id = 0;
                let agent_ip = get_agent_ip(AgentType::UserAgent, agent_id, i, network_node_id, gml_graph.as_ref(), using_gml_topology, &mut subnet_manager, &mut ip_registry);
                miner_ips.push(format!("{}:18080", agent_ip));
            }
        }
        println!("Using {} miner IPs as seed nodes: {:?}", miner_ips.len(), miner_ips);
        miner_ips
    } else {
        println!("Using configured seed nodes: {:?}", seed_node_list);
        seed_node_list
    };

    // Create DNS server host if enabled
    if let Some(ref dns_ip) = dns_server_ip {
        let dns_agent_id = "dnsserver";  // No underscore - Shadow requires RFC-compliant hostnames

        // Create DNS server process
        let dns_script = "agents.dns_server";
        let dns_args = format!(
            "--id {} --bind-ip {} --port 53 --shared-dir {} --log-level DEBUG",
            dns_agent_id, dns_ip, shared_dir_path.to_str().unwrap()
        );

        let dns_python_cmd = format!("python3 -m {} {}", dns_script, dns_args);

        // Path to virtual environment site-packages (for dnslib and other dependencies)
        // Dynamically detect Python version in venv, fallback to python3 if not found
        let venv_site_packages = detect_venv_site_packages(&current_dir)
            .unwrap_or_else(|| format!("{}/venv/lib/python3/site-packages", current_dir));

        // Create wrapper script for DNS server
        let dns_wrapper_script = format!(
            r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}:{}"
export PATH="${{PATH}}:$HOME/.monerosim/bin"

echo "Starting DNS server..."
{} 2>&1
"#,
            current_dir,
            current_dir,
            venv_site_packages,
            dns_python_cmd
        );

        let dns_script_path = format!("/tmp/dns_server_wrapper.sh");

        let dns_processes = vec![
            // Create wrapper script
            crate::shadow::ShadowProcess {
                path: "/bin/bash".to_string(),
                args: format!("-c 'cat > {} << '\"'\"'EOF'\"'\"'\n{}EOF'", dns_script_path, dns_wrapper_script),
                environment: environment.clone(),
                start_time: "0s".to_string(), // Start immediately
                shutdown_time: None,
                expected_final_state: None,
            },
            // Execute wrapper script
            crate::shadow::ShadowProcess {
                path: "/bin/bash".to_string(),
                args: dns_script_path.clone(),
                environment: environment.clone(),
                start_time: "1s".to_string(), // Start after script creation
                shutdown_time: None,
                expected_final_state: None,
            },
        ];

        hosts.insert(dns_agent_id.to_string(), ShadowHost {
            network_node_id: 0, // DNS server on first network node
            ip_addr: Some(dns_ip.clone()),
            processes: dns_processes,
            bandwidth_down: Some("1000000000".to_string()),
            bandwidth_up: Some("1000000000".to_string()),
        });

        log::info!("Created DNS server at {}", dns_ip);
    }

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
        enable_dns_server,
    )?;


    // Calculate offset for script agents to avoid IP collisions
    // Use a larger offset to ensure clear separation between agent types
    // Count all agents in the map for offset calculation
    let total_agent_count = config.agents.agents.len();
    let distributor_offset = total_agent_count + 100; // Reserve 100 IPs for user agents
    let script_offset = total_agent_count + 200; // Reserve another 100 IPs for miner distributor and other uses

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
        distributor_offset,
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

    // Add all agents to registry from the named agents map
    for (agent_id, agent_config) in config.agents.agents.iter() {
        // Get IP from the corresponding host that was already created
        let agent_ip = hosts.get(agent_id)
            .and_then(|host| host.ip_addr.clone())
            .unwrap_or_else(|| {
                // Fallback - should rarely happen
                format!("192.168.10.10")
            });

        let mut attributes = agent_config.attributes.clone().unwrap_or_default();

        // Add computed is_miner attribute to the agent registry
        let is_miner = agent_config.is_miner();
        attributes.insert("is_miner".to_string(), is_miner.to_string());

        // Add hashrate if present
        if let Some(hashrate) = agent_config.hashrate {
            attributes.insert("hashrate".to_string(), hashrate.to_string());
        }

        // Add can_receive_distributions if true
        if agent_config.can_receive_distributions() {
            attributes.insert("can_receive_distributions".to_string(), "true".to_string());
        }

        // Determine agent type characteristics
        let has_local_daemon = agent_config.has_local_daemon();
        let has_wallet = agent_config.has_wallet();
        let is_public_node = attributes.get("is_public_node")
            .map(|v| v.to_lowercase() == "true")
            .unwrap_or(false);

        // Get remote daemon info for wallet-only agents
        let remote_daemon = agent_config.remote_daemon_address().map(|s| s.to_string());
        let daemon_selection_strategy = agent_config.daemon_selection_strategy()
            .map(|s| format!("{:?}", s).to_lowercase());

        let agent_info = AgentInfo {
            id: agent_id.clone(),
            ip_addr: agent_ip,
            daemon: has_local_daemon,
            wallet: has_wallet,
            user_script: agent_config.script.clone(),
            attributes,
            wallet_rpc_port: if has_wallet { Some(18082) } else { None },
            daemon_rpc_port: if has_local_daemon { Some(18081) } else { None },
            is_public_node: if is_public_node { Some(true) } else { None },
            remote_daemon,
            daemon_selection_strategy,
        };
        agent_registry.agents.push(agent_info);
    }

    // Note: miner_distributor, simulation_monitor, and pure_script agents are now
    // part of the unified agents map and are handled above

    // Write agent registry to file
    let agent_registry_path = shared_dir_path.join("agent_registry.json");
    let agent_registry_json = serde_json::to_string_pretty(&agent_registry)?;
    
    // DEBUG: Log registry structure before writing
    log::info!("Agent registry has {} agents", agent_registry.agents.len());
    log::info!("Agent registry JSON preview (first 500 chars): {}",
               &agent_registry_json.chars().take(500).collect::<String>());
    
    std::fs::write(&agent_registry_path, &agent_registry_json)?;
    
    // DEBUG: Verify file was written
    let written_size = std::fs::metadata(&agent_registry_path)?.len();
    log::info!("Wrote agent registry to {:?}, size: {} bytes", agent_registry_path, written_size);

    // Create public node registry for wallet-only agents
    let mut public_node_registry = PublicNodeRegistry {
        nodes: Vec::new(),
        version: 1,
    };

    // Populate public node registry from agents with is_public_node attribute
    for agent in &agent_registry.agents {
        if agent.is_public_node == Some(true) && agent.daemon {
            let public_node = PublicNodeInfo {
                agent_id: agent.id.clone(),
                ip_addr: agent.ip_addr.clone(),
                rpc_port: agent.daemon_rpc_port.unwrap_or(18081),
                p2p_port: Some(18080),
                status: "available".to_string(),
                registered_at: 0.0, // Will be updated at runtime
                attributes: Some(agent.attributes.clone()),
            };
            public_node_registry.nodes.push(public_node);
        }
    }

    // Write public node registry to file
    let public_nodes_path = shared_dir_path.join("public_nodes.json");
    let public_nodes_json = serde_json::to_string_pretty(&public_node_registry)?;
    std::fs::write(&public_nodes_path, &public_nodes_json)?;
    log::info!("Wrote public node registry to {:?} with {} nodes",
               public_nodes_path, public_node_registry.nodes.len());

    // Create miner registry
    let mut miner_registry = MinerRegistry {
        miners: Vec::new(),
    };

    // Populate miner registry from agents that are miners
    for (agent_id, agent_config) in config.agents.agents.iter() {
        if agent_config.is_miner() {
            // Find the IP address from the already populated agent_registry
            let agent_ip = agent_registry.agents.iter()
                .find(|a| a.id == *agent_id)
                .map(|a| a.ip_addr.clone())
                .unwrap_or_else(|| {
                    // Fallback IP
                    format!("192.168.10.10")
                });

            // Determine miner weight (hashrate)
            // Use hashrate field if available, otherwise check attributes, default to 10
            let weight = agent_config.hashrate
                .or_else(|| {
                    agent_config.attributes.as_ref()
                        .and_then(|attrs| attrs.get("hashrate"))
                        .and_then(|h| h.parse::<u32>().ok())
                })
                .unwrap_or(10); // Default to 10 for better distribution

            let miner_info = MinerInfo {
                agent_id: agent_id.clone(),
                ip_addr: agent_ip,
                wallet_address: None, // Will be populated by the block controller
                weight,
            };
            miner_registry.miners.push(miner_info);
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

    // Note: GML topologies do NOT require a 1:1 mapping between nodes and Shadow hosts.
    // Shadow only requires that each host's network_node_id references a valid GML node.
    // Multiple hosts can share the same network_node_id, and GML nodes without hosts are fine.
    // Previously, dummy hosts were created for every GML node, causing significant overhead
    // in large-scale simulations (1200 empty hosts for a 1200-node GML file).

    // BTreeMap is already sorted by key, ensuring consistent ordering in output

    // Parse stop_time to seconds
    let stop_time_seconds = parse_duration_to_seconds(&config.general.stop_time)
        .map_err(|e| color_eyre::eyre::eyre!("Failed to parse stop_time '{}': {}", config.general.stop_time, e))?;

    // Create final Shadow configuration
    let shadow_config = ShadowConfig {
        general: ShadowGeneral {
            stop_time: stop_time_seconds,
            seed: config.general.simulation_seed,  // Shadow uses this to seed all RNGs for determinism
            parallelism: config.general.parallelism,  // 0=auto, 1=deterministic, N=N threads
            model_unblocked_syscall_latency: true,
            log_level: config.general.shadow_log_level.clone(),  // Use shadow_log_level (default: "info")
            bootstrap_end_time: config.general.bootstrap_end_time.clone(),  // High bandwidth period for network settling
            progress: config.general.progress.unwrap_or(true),  // Show simulation progress on stderr (default: true)
        },
        experimental: ShadowExperimental {
            runahead: config.general.runahead.clone(),  // Optional runahead for performance tuning
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
        hosts,
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
