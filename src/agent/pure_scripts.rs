//! Pure script agents processing.
//!
//! This module handles the configuration and processing of pure script agents,
//! which are standalone Python scripts that run without daemon or wallet processes.
//! These agents are typically used for monitoring, analysis, or specialized tasks
//! that don't require blockchain interaction.

use crate::config::AgentDefinitions;
use crate::gml_parser::GmlGraph;
use crate::ip::allocator::node_subnet_base;
use crate::ip::{get_agent_ip, AgentType, AsSubnetManager, GlobalIpRegistry};
use crate::shadow::ShadowHost;
use crate::topology::placement::apply_topology_pins;
use crate::utils::duration::parse_duration_to_seconds;
use crate::utils::script::write_wrapper_script;
use std::collections::{BTreeMap, HashSet};
use std::path::Path;

/// Process pure script agents
/// These are agents that have a script but no daemon or wallet
pub fn process_pure_script_agents(
    agents: &AgentDefinitions,
    hosts: &mut BTreeMap<String, ShadowHost>,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    environment: &BTreeMap<String, String>,
    shared_dir: &Path,
    current_dir: &str,
    _stop_time: &str,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    agent_offset: usize,
    scripts_dir: &Path,
) -> color_eyre::eyre::Result<()> {
    // Find pure script agents (script-only, no daemon/wallet)
    // Exclude miner_distributor and simulation_monitor which have their own processing
    let pure_scripts: Vec<(&String, &crate::config::AgentConfig)> = agents
        .agents
        .iter()
        .filter(|(id, config)| {
            config.is_script_only()
                && !id.contains("miner_distributor")
                && !id.contains("simulation_monitor")
                && !config
                    .script
                    .as_ref()
                    .map_or(false, |s| s.contains("miner_distributor"))
                && !config
                    .script
                    .as_ref()
                    .map_or(false, |s| s.contains("simulation_monitor"))
        })
        .collect();

    // Spread script agents across DISTINCT GML nodes so each gets a distinct
    // AS -> distinct /24. The old code pinned EVERY script agent to node 0,
    // i.e. one /24 (AS 0 -> 3.0.0.0/24); Monero's /24 outbound-diversity
    // filter then caps the entire fleet at a SINGLE outbound connection, so a
    // multi-IP attacker fleet (e.g. the eclipse fake peers) could never be
    // held as outbound. `agent_offset` is already past every daemon/user
    // agent and node ids are contiguous 0..N-1, so this yields distinct
    // nodes -> distinct subnets. Host bandwidth is set explicitly below, so
    // we no longer need node 0 just for its GML bandwidth attribute.
    let mut network_node_ids: Vec<u32> = (0..pure_scripts.len())
        .map(|i| match gml_graph {
            Some(g) if using_gml_topology && !g.nodes.is_empty() => {
                ((agent_offset + i) % g.nodes.len()) as u32
            }
            _ => 0,
        })
        .collect();
    // A `topology_node` pin overrides the spread and is validated exactly like
    // a daemon pin (the node must exist; pinning needs a GML topology). Agents
    // pinned to one node share its AS, hence its /24, which is how an attacker
    // fleet is packed k per /24. Script agents' pins used to be ignored.
    let valid_node_ids: HashSet<u32> = gml_graph
        .map(|g| g.nodes.iter().map(|n| n.id).collect())
        .unwrap_or_default();
    apply_topology_pins(
        &mut network_node_ids,
        &pure_scripts,
        &valid_node_ids,
        using_gml_topology,
    )
    .map_err(|e| color_eyre::eyre::eyre!(e))?;

    for (i, (agent_id, pure_script_config)) in pure_scripts.iter().enumerate() {
        let script_id = agent_id.as_str();
        let network_node_id = network_node_ids[i];
        let script_ip = get_agent_ip(
            AgentType::PureScriptAgent,
            script_id,
            agent_offset + i,
            network_node_id,
            gml_graph,
            using_gml_topology,
            subnet_manager,
            ip_registry,
            None,
        )?;
        // Once a node's /24 is used up the allocator silently falls back to an
        // unrelated address, which would quietly break k-per-/24 packing.
        if pure_script_config.topology_node.is_some() {
            if let Some(base) = gml_graph.and_then(|g| node_subnet_base(g, network_node_id)) {
                if !script_ip.starts_with(&format!("{base}.")) {
                    return Err(color_eyre::eyre::eyre!(
                        "agent '{script_id}' pins topology_node={network_node_id}, but that \
                         node's /24 ({base}.0/24) is full: a node's /24 holds 245 hosts \
                         (.10-.254), so this agent would get {script_ip} instead. Spread the \
                         pinned agents over more nodes."
                    ));
                }
            }
        }

        let mut script_args = vec![
            format!("--id {}", script_id),
            format!("--shared-dir {}", shared_dir.to_string_lossy()),
            format!("--log-level DEBUG"),
        ];

        // Add attributes as arguments
        if let Some(attrs) = &pure_script_config.attributes {
            for (key, value) in attrs {
                script_args.push(format!("--{} {}", key, value));
            }
        }

        // Get script path
        let script = pure_script_config
            .script
            .clone()
            .unwrap_or_else(|| "agents.pure_script".to_string());

        // `exec` so bash is replaced by python3 — see add_user_agent_process.
        let python_cmd = if script.contains('.') && !script.contains('/') && !script.contains('\\')
        {
            format!("exec python3 -m {} {}", script, script_args.join(" "))
        } else {
            format!("exec python3 {} {}", script, script_args.join(" "))
        };

        // Include venv site-packages in PYTHONPATH so pip-installed deps (e.g. requests) are found
        let home_dir = environment
            .get("HOME")
            .cloned()
            .unwrap_or_else(|| std::env::var("HOME").unwrap_or_else(|_| "/root".to_string()));
        let venv_sp = environment
            .get("VENV_SITE_PACKAGES")
            .map(String::as_str)
            .unwrap_or("");

        // Create a simple wrapper script for pure script agents
        let wrapper_content = format!(
            r#"#!/bin/bash
cd {}
export PYTHONPATH={}:{}
export PATH="$PATH:{}/.monerosim/bin"

echo "Starting pure script agent {}..."
{} 2>&1
"#,
            current_dir, current_dir, venv_sp, home_dir, script_id, python_cmd
        );

        // Honor the agent's configured start_time (the expanded config already
        // carries each agent's final, staggered value) so pure-script agents can
        // be scheduled like daemon/user agents — e.g. onboard-first eclipse
        // attackers that must start only after the benign network is established.
        // Fall back to the legacy stagger formula when no valid start_time is set.
        let start_time = match pure_script_config
            .start_time
            .as_deref()
            .and_then(|t| parse_duration_to_seconds(t).ok())
        {
            // Normalize to whole seconds ("Ns"), matching the daemon path, so a
            // config value like "20m" becomes "1200s" (Shadow wants seconds here).
            Some(secs) => format!("{}s", secs),
            None => format!("{}s", 6 + i * 2),
        };
        let process = write_wrapper_script(
            scripts_dir,
            &format!("{}_wrapper.sh", script_id),
            &wrapper_content,
            environment,
            start_time,
            None,
            Some(crate::shadow::ExpectedFinalState::Running),
        )?;

        hosts.insert(
            script_id.to_string(),
            ShadowHost {
                network_node_id, // spread (distinct AS/subnet) unless pinned via topology_node
                ip_addr: Some(script_ip),
                blocked_inbound_ports: None,
                processes: vec![process],
                bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
                bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
            },
        );
    }

    // Report where pinned script agents went, so a mis-packed fleet shows up in
    // the generator log before a long run, and flag any other host that shares
    // a pinned node (and so its /24) with them.
    let mut pinned_per_node: BTreeMap<u32, usize> = BTreeMap::new();
    let mut pinned_ids: HashSet<&str> = HashSet::new();
    for (i, (agent_id, cfg)) in pure_scripts.iter().enumerate() {
        if cfg.topology_node.is_some() {
            *pinned_per_node.entry(network_node_ids[i]).or_default() += 1;
            pinned_ids.insert(agent_id.as_str());
        }
    }
    if !pinned_per_node.is_empty() {
        log::info!(
            "topology_node: {} script agents pinned onto {} nodes (up to {} per node, i.e. per /24)",
            pinned_ids.len(),
            pinned_per_node.len(),
            pinned_per_node.values().max().copied().unwrap_or(0)
        );
        for (host_id, host) in hosts.iter() {
            if let Some(n) = pinned_per_node.get(&host.network_node_id) {
                if !pinned_ids.contains(host_id.as_str()) {
                    log::warn!(
                        "topology_node={}: host '{}' also sits on this node, so it shares \
                         the /24 of the {} script agents pinned there",
                        host.network_node_id,
                        host_id,
                        n
                    );
                }
            }
        }
    }

    Ok(())
}
