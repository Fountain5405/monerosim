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
        let mut processes = Vec::new();

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
        let wrapper_script = format!(
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

        // Write wrapper script to a temporary file and execute it
        let script_path = format!("/tmp/{}_wrapper.sh", script_id);
        let script_creation_time = format!("{}s", 5 + i * 2);
        let script_execution_time = format!("{}s", 6 + i * 2);

        // Process 1: Create wrapper script
        processes.push(crate::shadow::ShadowProcess {
            path: "/bin/bash".to_string(),
            args: format!("-c 'cat > {} << \\EOF\n{}EOF'", script_path, wrapper_script),
            environment: environment.clone(),
            start_time: script_creation_time,
            shutdown_time: None,
            expected_final_state: None,
        });

        // Process 2: Execute wrapper script
        processes.push(crate::shadow::ShadowProcess {
            path: "/bin/bash".to_string(),
            args: script_path.clone(),
            environment: environment.clone(),
            start_time: script_execution_time,
            shutdown_time: None,
            expected_final_state: None,
        });

        hosts.insert(script_id.to_string(), ShadowHost {
            network_node_id, // Use the assigned GML node with bandwidth info
            ip_addr: Some(script_ip),
            processes,
            bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
            bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
        });
        // Note: next_ip is already incremented in get_agent_ip function
    }

    Ok(())
}
