//! Pure script agents processing.
//!
//! This module handles the configuration and processing of pure script agents,
//! which are standalone Python scripts that run without daemon or wallet processes.
//! These agents are typically used for monitoring, analysis, or specialized tasks
//! that don't require blockchain interaction.

use crate::config::AgentDefinitions;
use crate::gml_parser::GmlGraph;
use crate::ip::{get_agent_ip, AgentType, AsSubnetManager, GlobalIpRegistry};
use crate::shadow::ShadowHost;
use crate::utils::duration::parse_duration_to_seconds;
use crate::utils::script::write_wrapper_script;
use std::collections::BTreeMap;
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

    for (i, (agent_id, pure_script_config)) in pure_scripts.iter().enumerate() {
        let script_id = agent_id.as_str();
        // Spread script agents across DISTINCT GML nodes so each gets a distinct
        // AS -> distinct /24. The old code pinned EVERY script agent to node 0,
        // i.e. one /24 (AS 0 -> 3.0.0.0/24); Monero's /24 outbound-diversity
        // filter then caps the entire fleet at a SINGLE outbound connection, so a
        // multi-IP attacker fleet (e.g. the eclipse fake peers) could never be
        // held as outbound. `agent_offset` is already past every daemon/user
        // agent and node ids are contiguous 0..N-1, so this yields distinct
        // nodes -> distinct subnets. Host bandwidth is set explicitly below, so
        // we no longer need node 0 just for its GML bandwidth attribute.
        let network_node_id: u32 = match gml_graph {
            Some(g) if using_gml_topology && !g.nodes.is_empty() => {
                ((agent_offset + i) % g.nodes.len()) as u32
            }
            _ => 0,
        };
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
                network_node_id, // distinct GML node per script agent (distinct AS/subnet)
                ip_addr: Some(script_ip),
                blocked_inbound_ports: None,
                processes: vec![process],
                bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
                bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
            },
        );
    }

    Ok(())
}
