//! Pure script agents processing.
//!
//! This module handles the configuration and processing of pure script agents,
//! which are standalone Python scripts that run without daemon or wallet processes.
//! These agents are typically used for monitoring, analysis, or specialized tasks
//! that don't require blockchain interaction.

use crate::config_v2::AgentDefinitions;
use crate::gml_parser::GmlGraph;
use crate::shadow::ShadowHost;
use crate::ip::{GlobalIpRegistry, AsSubnetManager, AgentType, get_agent_ip};
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
    let pure_scripts: Vec<(&String, &crate::config_v2::AgentConfig)> = agents.agents.iter()
        .filter(|(id, config)| {
            config.is_script_only() &&
            !id.contains("miner_distributor") &&
            !id.contains("simulation_monitor") &&
            !config.script.as_ref().map_or(false, |s| s.contains("miner_distributor")) &&
            !config.script.as_ref().map_or(false, |s| s.contains("simulation_monitor"))
        })
        .collect();

    for (i, (agent_id, pure_script_config)) in pure_scripts.iter().enumerate() {
        let script_id = agent_id.as_str();
        // Assign pure scripts to node 0 (which has bandwidth info in GML)
        let network_node_id = 0;
        let script_ip = get_agent_ip(AgentType::PureScriptAgent, script_id, agent_offset + i, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry, None);

        let mut script_args = vec![
            format!("--id {}", script_id),
            format!("--shared-dir {}", shared_dir.to_str().unwrap()),
            format!("--log-level DEBUG"),
        ];

        // Add attributes as arguments
        if let Some(attrs) = &pure_script_config.attributes {
            for (key, value) in attrs {
                script_args.push(format!("--{} {}", key, value));
            }
        }

        // Get script path
        let script = pure_script_config.script.clone()
            .unwrap_or_else(|| "agents.pure_script".to_string());

        // Simplified command for pure script agents
        let python_cmd = if script.contains('.') && !script.contains('/') && !script.contains('\\') {
            format!("python3 -m {} {}", script, script_args.join(" "))
        } else {
            format!("python3 {} {}", script, script_args.join(" "))
        };

        // Create a simple wrapper script for pure script agents
        let wrapper_content = format!(
            r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:$HOME/.monerosim/bin"

echo "Starting pure script agent {}..."
{} 2>&1
"#,
            current_dir,
            current_dir,
            script_id,
            python_cmd
        );

        let start_time = format!("{}s", 6 + i * 2);
        let process = write_wrapper_script(
            scripts_dir,
            &format!("{}_wrapper.sh", script_id),
            &wrapper_content,
            environment,
            start_time,
            None,
            Some(crate::shadow::ExpectedFinalState::Running),
        )?;

        hosts.insert(script_id.to_string(), ShadowHost {
            network_node_id, // Use the assigned GML node with bandwidth info
            ip_addr: Some(script_ip),
            processes: vec![process],
            bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
            bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
        });
    }

    Ok(())
}
