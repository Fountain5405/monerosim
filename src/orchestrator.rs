//! Configuration orchestrator.
//!
//! This module coordinates the overall configuration generation process,
//! managing the flow from configuration parsing through Shadow YAML generation.

use crate::config::{Config, DistributionStrategy, Network, PeerMode, RegionWeights};
use crate::gml_parser::{self, GmlGraph, validate_topology, get_autonomous_systems};
use crate::shadow::{
    MinerInfo, MinerRegistry, AgentInfo, AgentRegistry,
    PublicNodeInfo, PublicNodeRegistry,
    ShadowConfig, ShadowGeneral, ShadowExperimental, ShadowNetwork, ShadowGraph,
    ShadowFileSource, ShadowHost,
};
use crate::topology::Topology;
use crate::utils::duration::parse_duration_to_seconds;
use crate::utils::validation::{validate_gml_ip_consistency, validate_topology_config};
use crate::ip::{GlobalIpRegistry, AsSubnetManager, AgentType, get_agent_ip};
use crate::agent::{process_user_agents, UserAgentProcessContext, process_miner_distributor, process_pure_script_agents, process_simulation_monitor, prepare_fallback_seeds};
use serde_json;
use serde_yaml;
use std::collections::BTreeMap;
use std::path::Path;
use std::fs;

/// Convert a bandwidth string like "10Gbit" or "500Mbit" to a numeric Mbit string.
/// Passes through values that are already plain numbers.
fn convert_bandwidth_value(value: &str) -> String {
    if value.ends_with("Gbit") {
        if let Ok(gbit) = value.trim_end_matches("Gbit").parse::<f64>() {
            return format!("{}", gbit * 1000.0);
        }
    } else if value.ends_with("Mbit") {
        return value.trim_end_matches("Mbit").to_string();
    }
    value.to_string()
}

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
pub fn generate_gml_network_config(gml_graph: &GmlGraph, _gml_path: &str, output_dir: &Path) -> color_eyre::eyre::Result<ShadowGraph> {
    // Validate the topology first
    validate_topology(gml_graph).map_err(|e| color_eyre::eyre::eyre!("Invalid GML topology: {}", e))?;

    // Validate IP consistency
    validate_gml_ip_consistency(gml_graph).map_err(|e| color_eyre::eyre::eyre!("GML IP validation failed: {}", e))?;

    // Create a GML file with converted attributes (e.g., packet_loss percentages to floats)
    // Place in output directory alongside the Shadow config for locality and cleanup
    let temp_gml_path = output_dir.join("topology.gml").to_string_lossy().to_string();

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
            let (processed_value, needs_quotes) = if key == "bandwidth" {
                (convert_bandwidth_value(value), false)
            } else {
                (value.clone(), true)
            };
            if needs_quotes {
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
            let (processed_value, needs_quotes) = if key == "packet_loss" {
                (value.clone(), false)
            } else if key == "bandwidth" {
                (convert_bandwidth_value(value), false)
            } else {
                (value.clone(), true)
            };
            if needs_quotes {
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

/// Compose the per-agent environment maps and (optionally) allocate the DNS
/// server's IP from node 0's subnet. Returns the base `environment`, the
/// Monero-specific environment (a clone of `environment` with extra keys), the
/// DNS server IP if enabled, and the resolved venv site-packages path.
///
/// `subnet_manager` and `ip_registry` are mutated when DNS is enabled because
/// the DNS host requires an IP allocation pinned to network node 0.
fn compose_base_environment(
    config: &Config,
    current_dir: &str,
    home_dir: &str,
    gml_graph: Option<&GmlGraph>,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
) -> (BTreeMap<String, String>, BTreeMap<String, String>, Option<String>, String) {
    // Common environment variables
    let mut environment: BTreeMap<String, String> = [
        ("HOME".to_string(), home_dir.to_string()), // Required for $HOME expansion in binary paths
        ("MALLOC_MMAP_THRESHOLD_".to_string(), crate::MALLOC_THRESHOLD.to_string()),
        ("MALLOC_TRIM_THRESHOLD_".to_string(), crate::MALLOC_THRESHOLD.to_string()),
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

    // Detect venv site-packages path for Python dependency resolution (e.g. requests)
    let venv_site_packages = detect_venv_site_packages(current_dir)
        .unwrap_or_else(|| format!("{}/venv/lib/python3/site-packages", current_dir));
    environment.insert("VENV_SITE_PACKAGES".to_string(), venv_site_packages.clone());

    // Monero-specific environment variables
    let mut monero_environment = environment.clone();
    monero_environment.insert("MONERO_BLOCK_SYNC_SIZE".to_string(), "1".to_string());
    // (Previously set MONERO_MAX_CONNECTIONS_PER_IP=20 here, but monerod
    // doesn't read that env var — it only honors the CLI flag
    // `--max-connections-per-ip`. The env var was a no-op for years, so for
    // a while we ran at monerod's actual default of 1. That turned out to
    // break P2P at every scale: monerod's post-handshake reachability probe
    // opens a second connection from the same source IP, which the cap-of-1
    // refuses, dropping the original connection and looping forever. The
    // floor is now injected as the CLI flag in user_agents.rs
    // (build_daemon_args_base) so it applies to every daemon agent without
    // per-config opt-in. See docs/20260605_max_connections_per_ip_bug.md.)

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
            gml_graph,
            gml_graph.is_some(),  // using_gml_topology
            subnet_manager,
            ip_registry,
            None,  // No subnet_group for infrastructure
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

    (environment, monero_environment, dns_server_ip, venv_site_packages)
}

/// Extract peer mode, configured seed-node list, topology, and GML
/// distribution config from the optional `network` block. The defaults match
/// the legacy fall-throughs (Dynamic peer mode, no seeds, DAG topology, no
/// distribution overrides).
fn extract_network_topology_config(
    config: &Config,
) -> (PeerMode, Vec<String>, Option<Topology>, Option<DistributionStrategy>, Option<RegionWeights>) {
    match &config.network {
        Some(Network::Gml { peer_mode, seed_nodes, topology, distribution, .. }) => {
            let mode = peer_mode.as_ref().unwrap_or(&PeerMode::Dynamic).clone();
            let seeds = seed_nodes.as_ref().unwrap_or(&Vec::new()).clone();
            let topo = topology.as_ref().unwrap_or(&Topology::Dag).clone();
            // Extract distribution config (defaults to Global strategy)
            let (strategy, weights) = match distribution {
                Some(dist) => (Some(dist.strategy.clone()), dist.weights.clone()),
                None => (None, None), // Will default to Global in distribution.rs
            };
            (mode, seeds, Some(topo), strategy, weights)
        }
        Some(Network::Switch { peer_mode, seed_nodes, topology, .. }) => {
            let mode = peer_mode.as_ref().unwrap_or(&PeerMode::Dynamic).clone();
            let seeds = seed_nodes.as_ref().unwrap_or(&Vec::new()).clone();
            let topo = topology.as_ref().unwrap_or(&Topology::Dag).clone();
            // Switch topology doesn't use distribution config
            (mode, seeds, Some(topo), None, None)
        }
        None => {
            // Default to Dynamic mode with no seed nodes and DAG topology
            (PeerMode::Dynamic, Vec::new(), Some(Topology::Dag), None, None)
        }
    }
}

/// Build the DNS server wrapper script and ShadowHost, inserting the host
/// into `hosts` under the agent id `dnsserver`. Pinned to network node 0 so
/// it's reachable from every node in the GML topology.
fn emit_dns_server_host(
    dns_ip: &str,
    scripts_dir: &Path,
    shared_dir_path: &Path,
    current_dir: &str,
    home_dir: &str,
    venv_site_packages: &str,
    environment: &BTreeMap<String, String>,
    hosts: &mut BTreeMap<String, ShadowHost>,
) -> color_eyre::eyre::Result<()> {
    let dns_agent_id = "dnsserver";  // No underscore - Shadow requires RFC-compliant hostnames

    // Create DNS server process
    let dns_script = "agents.dns_server";
    let dns_args = format!(
        "--id {} --bind-ip {} --port 53 --shared-dir {} --log-level DEBUG",
        dns_agent_id, dns_ip, shared_dir_path.to_string_lossy()
    );

    // `exec` so bash is replaced by python3 — see add_user_agent_process.
    let dns_python_cmd = format!("exec python3 -m {} {}", dns_script, dns_args);

    // Create wrapper script for DNS server with fully-resolved paths
    let dns_wrapper_script = format!(
        r#"#!/bin/bash
cd {}
export PYTHONPATH={}:{}
export PATH="$PATH:{}/.monerosim/bin"

{} 2>&1
"#,
        current_dir,
        current_dir,
        venv_site_packages,
        home_dir,
        dns_python_cmd
    );

    let dns_process = crate::utils::script::write_wrapper_script(
        scripts_dir,
        "dns_server_wrapper.sh",
        &dns_wrapper_script,
        environment,
        "1s".to_string(),
        None,
        Some(crate::shadow::ExpectedFinalState::Running),
    )?;
    let dns_processes = vec![dns_process];

    hosts.insert(dns_agent_id.to_string(), ShadowHost {
        network_node_id: 0, // DNS server on first network node
        ip_addr: Some(dns_ip.to_string()),
        processes: dns_processes,
        bandwidth_down: Some(crate::DEFAULT_BANDWIDTH_BPS.to_string()),
        bandwidth_up: Some(crate::DEFAULT_BANDWIDTH_BPS.to_string()),
    });

    log::info!("Created DNS server at {}", dns_ip);
    Ok(())
}

/// Build the agent registry by joining the (already populated) `hosts` map
/// with the effective agent definitions. Reads each agent's IP from the host
/// entry rather than re-allocating, so the registry agrees with what Shadow
/// will run.
fn build_agent_registry(
    effective_agents: &crate::config::AgentDefinitions,
    hosts: &BTreeMap<String, ShadowHost>,
) -> AgentRegistry {
    let mut agent_registry = AgentRegistry {
        agents: Vec::new(),
    };

    // Populate agent registry from all agent types
    // Extract IPs from the already created hosts instead of generating new ones

    // Add all agents to registry from the effective agents map (so
    // auto-injected fallback-seed hosts appear here too — DNS server
    // and other consumers read this file).
    for (agent_id, agent_config) in effective_agents.agents.iter() {
        // Get IP from the corresponding host that was already created
        let agent_ip = hosts.get(agent_id)
            .and_then(|host| host.ip_addr.clone())
            .unwrap_or_else(|| {
                log::warn!("Agent '{}' has no host entry with an IP address; using placeholder 0.0.0.0", agent_id);
                "0.0.0.0".to_string()
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
            wallet_rpc_port: if has_wallet { Some(crate::MONERO_WALLET_RPC_PORT) } else { None },
            daemon_rpc_port: if has_local_daemon { Some(crate::MONERO_RPC_PORT) } else { None },
            is_public_node: if is_public_node { Some(true) } else { None },
            remote_daemon,
            daemon_selection_strategy,
        };
        agent_registry.agents.push(agent_info);
    }

    agent_registry
}

/// Build the public-node registry from agents flagged as `is_public_node`
/// that also run a local daemon. Wallet-only agents in the registry are
/// excluded because they have no daemon to advertise.
fn build_public_node_registry(agent_registry: &AgentRegistry) -> PublicNodeRegistry {
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
                rpc_port: agent.daemon_rpc_port.unwrap_or(crate::MONERO_RPC_PORT),
                p2p_port: Some(crate::MONERO_P2P_PORT),
                status: "available".to_string(),
                registered_at: 0.0, // Will be updated at runtime
                attributes: Some(agent.attributes.clone()),
            };
            public_node_registry.nodes.push(public_node);
        }
    }

    public_node_registry
}

/// Build and validate the miner registry. Reads each miner's IP from the
/// already-populated `agent_registry` so it matches what Shadow will run, and
/// upgrades a zero-total-weight registry to default per-miner weights of 10
/// (preserving the legacy stdout warning text).
fn build_miner_registry(
    config_agents: &crate::config::AgentDefinitions,
    agent_registry: &AgentRegistry,
) -> MinerRegistry {
    let mut miner_registry = MinerRegistry {
        miners: Vec::new(),
    };

    // Populate miner registry from agents that are miners
    for (agent_id, agent_config) in config_agents.agents.iter() {
        if agent_config.is_miner() {
            // Find the IP address from the already populated agent_registry
            let agent_ip = agent_registry.agents.iter()
                .find(|a| a.id == *agent_id)
                .map(|a| a.ip_addr.clone())
                .unwrap_or_else(|| {
                    log::warn!("Miner '{}' not found in agent registry; using placeholder 0.0.0.0", agent_id);
                    "0.0.0.0".to_string()
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

    miner_registry
}

/// Choose the Shadow network graph type based on the configured network
/// block. GML configurations defer to `generate_gml_network_config` for the
/// emitted topology file; switch / unset configurations build a synthetic
/// switch graph inline.
fn build_shadow_network_graph(
    network: &Option<Network>,
    gml_graph: Option<&GmlGraph>,
    output_dir: &Path,
) -> color_eyre::eyre::Result<ShadowGraph> {
    let graph = match network {
        Some(Network::Gml { path, .. }) => {
            // Use the loaded and validated GML graph to generate network config
            if let Some(gml) = gml_graph {
                // Pass both the GML graph and the output dir for topology.gml
                generate_gml_network_config(gml, path, output_dir)?
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
    };
    Ok(graph)
}

/// Emit the post-generation summary to stdout: simulation time, host count,
/// network topology summary, registry paths, and per-subnet IP allocation
/// counts. Also runs the IP-subnet diversity validation, which can fail and
/// abort the run.
fn log_generation_summary(
    config: &Config,
    output_path: &Path,
    shadow_config: &ShadowConfig,
    gml_graph: Option<&GmlGraph>,
    ip_registry: &GlobalIpRegistry,
    agent_registry_path: &Path,
    miner_registry_path: &Path,
) -> color_eyre::eyre::Result<()> {
    println!("Generated Agent-based Shadow configuration at {:?}", output_path);
    println!("  - Simulation time: {}", config.general.stop_time);
    println!("  - Total hosts: {}", shadow_config.hosts.len());

    // Show network topology information
    match &config.network {
        Some(Network::Gml { path, .. }) => {
            if let Some(gml) = gml_graph {
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
    let mut sorted_stats: Vec<_> = ip_stats.iter().collect();
    sorted_stats.sort_by_key(|(subnet, _)| (*subnet).clone());
    for (subnet, count) in sorted_stats {
        println!("    - {}: {} IPs assigned", subnet, count);
    }
    let all_ips_map = ip_registry.get_all_assigned_ips();
    let all_ips: Vec<String> = all_ips_map.keys().cloned().collect();
    println!("  - Total IPs assigned: {}", all_ips.len());

    // Validate IP subnet diversity for Monero P2P compatibility
    crate::utils::validate_ip_subnet_diversity(&all_ips, shadow_config.hosts.len())
        .map_err(|e| color_eyre::eyre::eyre!("IP diversity validation failed: {}", e))?;

    Ok(())
}

/// Generate a Shadow configuration with agent support
pub fn generate_agent_shadow_config(
    config: &Config,
    output_path: &Path,
) -> color_eyre::eyre::Result<()> {
    let shared_dir_path = Path::new(&config.general.shared_dir);

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

    // Create centralized IP registry for robust IP management
    let mut ip_registry = GlobalIpRegistry::new();

    // Create AS-aware subnet manager for GML topology compatibility
    let mut subnet_manager = AsSubnetManager::new();

    // Compose base + Monero-specific environment maps and (optionally)
    // allocate the DNS server IP from node 0's subnet.
    let (environment, monero_environment, dns_server_ip, venv_site_packages) =
        compose_base_environment(
            config,
            &current_dir,
            &home_dir,
            gml_graph.as_ref(),
            &mut subnet_manager,
            &mut ip_registry,
        );
    let enable_dns_server = config.general.enable_dns_server.unwrap_or(false);

    // Fully-resolved binary paths (installed to ~/.monerosim/bin by setup.sh)
    let monerod_path = format!("{}/.monerosim/bin/monerod", home_dir);
    let wallet_path = format!("{}/.monerosim/bin/monero-wallet-rpc", home_dir);

    // Store seed nodes for P2P connections
    let mut seed_nodes: Vec<String> = Vec::new();

    // Determine if we're actually using GML topology based on network configuration
    let using_gml_topology = if let Some(Network::Gml { path: _, .. }) = &config.network {
        true // We're using GML topology
    } else {
        false // We're using switch topology
    };

    // Extract peer mode, seed nodes, topology, and distribution config from configuration
    let (peer_mode, seed_node_list, topology, distribution_strategy, distribution_weights) =
        extract_network_topology_config(config);

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
    // Note: This is computed for the informative print statement below
    let _effective_seed_nodes = if seed_node_list.is_empty() {
        // Collect actual miner IPs for seed nodes
        let mut miner_ips = Vec::new();
        for (i, (agent_id, agent_config)) in config.agents.agents.iter()
            .filter(|(_, cfg)| cfg.has_local_daemon() || cfg.has_remote_daemon() || cfg.has_wallet())
            .enumerate()
        {
            if agent_config.is_miner() {
                // For seed node IP calculation, use node 0 (switch topology assumption)
                let network_node_id = 0;
                let subnet_group = agent_config.subnet_group.as_deref();
                let agent_ip = get_agent_ip(AgentType::UserAgent, agent_id, i, network_node_id, gml_graph.as_ref(), using_gml_topology, &mut subnet_manager, &mut ip_registry, subnet_group);
                miner_ips.push(format!("{}:{}", agent_ip, crate::MONERO_P2P_PORT));
            }
        }
        println!("Using {} miner IPs as seed nodes: {:?}", miner_ips.len(), miner_ips);
        miner_ips
    } else {
        println!("Using configured seed nodes: {:?}", seed_node_list);
        seed_node_list
    };

    // Create scripts directory for wrapper scripts (used by all agent types)
    let scripts_dir = output_path.parent()
        .ok_or_else(|| color_eyre::eyre::eyre!("Output path has no parent directory"))?
        .join("scripts");
    fs::create_dir_all(&scripts_dir)
        .map_err(|e| color_eyre::eyre::eyre!("Failed to create scripts directory: {}", e))?;
    let scripts_dir = fs::canonicalize(&scripts_dir)
        .map_err(|e| color_eyre::eyre::eyre!("Failed to canonicalize scripts directory: {}", e))?;

    // Create DNS server host if enabled
    if let Some(ref dns_ip) = dns_server_ip {
        emit_dns_server_host(
            dns_ip,
            &scripts_dir,
            shared_dir_path,
            &current_dir,
            &home_dir,
            &venv_site_packages,
            &environment,
            &mut hosts,
        )?;
    }

    // Reserve Monero fallback-seed IPs (and inject synthesized seed
    // hosts in `auto` mode) before the main allocation loop so that
    // `get_agent_ip()`'s Priority 0 lookup honors the pinning. The IP
    // list is extracted live from the Monero source tree at
    // `<repo>/sibling_repos/monero` (or sibling layouts), with the
    // hardcoded constant as a fallback.
    let repo_dir = std::path::Path::new(&current_dir);
    let (effective_agents, _seed_count) = prepare_fallback_seeds(
        config.general.fallback_seeds,
        &config.agents,
        &mut ip_registry,
        repo_dir,
    );

    // Process all agent types from the configuration
    process_user_agents(UserAgentProcessContext {
        agents: &effective_agents,
        hosts: &mut hosts,
        seed_agents: &mut seed_nodes,
        subnet_manager: &mut subnet_manager,
        ip_registry: &mut ip_registry,
        monerod_path: &monerod_path,
        wallet_path: &wallet_path,
        environment: &environment,
        monero_environment: &monero_environment,
        shared_dir: shared_dir_path,
        current_dir: &current_dir,
        gml_graph: gml_graph.as_ref(),
        using_gml_topology,
        peer_mode: &peer_mode,
        topology: topology.as_ref(),
        enable_dns_server,
        daemon_defaults: config.general.daemon_defaults.as_ref(),
        wallet_defaults: config.general.wallet_defaults.as_ref(),
        distribution_strategy: distribution_strategy.as_ref(),
        distribution_weights: distribution_weights.as_ref(),
        scripts_dir: &scripts_dir,
        daemon_data_dir: &config.general.daemon_data_dir,
        simulation_seed: config.general.simulation_seed,
        reachable_fraction: config.general.reachable_fraction,
        reachable_by_role: config.general.reachable_by_role.as_ref(),
    })?;


    // Calculate offset for script agents to avoid IP collisions
    // Use a larger offset to ensure clear separation between agent types
    // Count all agents in the map for offset calculation (use the
    // effective set so injected seeds are accounted for).
    let total_agent_count = effective_agents.agents.len();
    let distributor_offset = total_agent_count + crate::DISTRIBUTOR_IP_OFFSET;
    let script_offset = total_agent_count + crate::SCRIPT_IP_OFFSET;

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
        &scripts_dir,
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
        &scripts_dir,
    )?;

    // Get output directory from output_path (parent of output file)
    // Ensure it's an absolute path so the monitor can find it regardless of working directory
    let output_dir = output_path.parent()
        .ok_or_else(|| color_eyre::eyre::eyre!("Output path has no parent directory"))?;
    let output_dir = if output_dir.is_absolute() {
        output_dir.to_path_buf()
    } else {
        std::env::current_dir()?.join(output_dir)
    };

    process_simulation_monitor(
        &config.agents,
        &mut hosts,
        &mut subnet_manager,
        &mut ip_registry,
        &environment,
        shared_dir_path,
        &current_dir,
        &output_dir,
        &config.general.stop_time,
        gml_graph.as_ref(),
        using_gml_topology,
        script_offset + 50, // Offset from other script agents
        &scripts_dir,
    )?;

    // Build agent registry from the effective agents and the (already
    // populated) hosts map.
    let agent_registry = build_agent_registry(&effective_agents, &hosts);

    // Note: miner_distributor, simulation_monitor, and pure_script agents are now
    // part of the unified agents map and are handled above

    // Write agent registry to file
    let agent_registry_path = shared_dir_path.join("agent_registry.json");
    let agent_registry_json = serde_json::to_string_pretty(&agent_registry)?;

    // DEBUG: Log registry structure before writing
    log::info!("Agent registry has {} agents", agent_registry.agents.len());
    log::info!("Agent registry JSON preview (first {} chars): {}",
               crate::REGISTRY_PREVIEW_CHARS,
               &agent_registry_json.chars().take(crate::REGISTRY_PREVIEW_CHARS).collect::<String>());

    std::fs::write(&agent_registry_path, &agent_registry_json)?;

    // DEBUG: Verify file was written
    let written_size = std::fs::metadata(&agent_registry_path)?.len();
    log::info!("Wrote agent registry to {:?}, size: {} bytes", agent_registry_path, written_size);

    // Build public-node registry from the agent registry (wallet-only agents
    // are excluded — they have no daemon to advertise).
    let public_node_registry = build_public_node_registry(&agent_registry);

    // Write public node registry to file
    let public_nodes_path = shared_dir_path.join("public_nodes.json");
    let public_nodes_json = serde_json::to_string_pretty(&public_node_registry)?;
    std::fs::write(&public_nodes_path, &public_nodes_json)?;
    log::info!("Wrote public node registry to {:?} with {} nodes",
               public_nodes_path, public_node_registry.nodes.len());

    // Build + validate the miner registry from agents flagged as miners.
    let miner_registry = build_miner_registry(&config.agents, &agent_registry);

    // Write miner registry to file
    let miner_registry_path = shared_dir_path.join("miners.json");
    let miner_registry_json = serde_json::to_string_pretty(&miner_registry)?;
    std::fs::write(&miner_registry_path, &miner_registry_json)?;

    // Pre-create wallet directories for all agents that have wallets.
    // This replaces the per-agent bash cleanup processes that previously ran
    // inside the simulation to `rm -rf && mkdir -p && chmod 755` wallet dirs.
    // Since main.rs already cleans /tmp/monerosim_shared/ before generation,
    // we just need to create fresh directories with correct permissions.
    for (agent_id, agent_config) in config.agents.agents.iter() {
        if agent_config.has_wallet() || agent_config.has_wallet_phases() {
            let wallet_dir = shared_dir_path.join(format!("{}_wallet", agent_id));
            fs::create_dir_all(&wallet_dir)
                .map_err(|e| color_eyre::eyre::eyre!("Failed to create wallet dir {:?}: {}", wallet_dir, e))?;
            // Set permissions explicitly (monero-wallet-rpc can create files with restrictive perms)
            let mut perms = fs::metadata(&wallet_dir)?.permissions();
            use std::os::unix::fs::PermissionsExt;
            perms.set_mode(0o755);
            fs::set_permissions(&wallet_dir, perms)?;
        }
    }

    // Note: GML topologies do NOT require a 1:1 mapping between nodes and Shadow hosts.
    // Shadow only requires that each host's network_node_id references a valid GML node.
    // Multiple hosts can share the same network_node_id, and GML nodes without hosts are fine.
    // Previously, dummy hosts were created for every GML node, causing significant overhead
    // in large-scale simulations (1200 empty hosts for a 1200-node GML file).

    // BTreeMap is already sorted by key, ensuring consistent ordering in output

    // Parse stop_time to seconds
    let stop_time_seconds = parse_duration_to_seconds(&config.general.stop_time)
        .map_err(|e| color_eyre::eyre::eyre!("Failed to parse stop_time '{}': {}", config.general.stop_time, e))?;

    // Build Shadow's network graph from the configured network block.
    let shadow_graph = build_shadow_network_graph(&config.network, gml_graph.as_ref(), &output_dir)?;

    // Create final Shadow configuration
    let shadow_config = ShadowConfig {
        general: ShadowGeneral {
            stop_time: stop_time_seconds,
            seed: config.general.simulation_seed,  // Shadow uses this to seed all RNGs for determinism
            parallelism: config.general.parallelism,  // 0=auto, 1=deterministic, N=N threads
            model_unblocked_syscall_latency: config.performance.model_unblocked_syscall_latency,
            log_level: config.general.shadow_log_level.clone(),  // Use shadow_log_level (default: "info")
            bootstrap_end_time: config.general.bootstrap_end_time.clone(),  // High bandwidth period for network settling
            progress: config.general.progress.unwrap_or(true),  // Show simulation progress on stderr (default: true)
        },
        experimental: ShadowExperimental {
            runahead: config.general.runahead.clone(),  // Optional runahead for performance tuning
            use_dynamic_runahead: true,
            native_preemption_enabled: config.general.native_preemption,  // Pass through config (Shadow default false when unset)
        },
        network: ShadowNetwork {
            graph: shadow_graph,
            // Pass DNS server IP to Shadow for getaddrinfo() UDP query support
            dns_server: dns_server_ip.clone(),
        },
        hosts,
    };

    // Write configuration
    let config_yaml = serde_yaml::to_string(&shadow_config)?;
    std::fs::write(output_path, config_yaml)?;

    log_generation_summary(
        config,
        output_path,
        &shadow_config,
        gml_graph.as_ref(),
        &ip_registry,
        &agent_registry_path,
        &miner_registry_path,
    )?;

    Ok(())
}
