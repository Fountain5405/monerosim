//! Pure script process configuration.
//!
//! This file handles generation of Shadow process configurations
//! for pure script agents that run without daemon or wallet processes.

use crate::config_v2::AgentDefinitions;
use crate::shadow::ShadowHost;
use crate::ip::{GlobalIpRegistry, AsSubnetManager, AgentType};
use std::collections::HashMap;
use std::path::Path;
use crate::gml_parser::GmlGraph;

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
            let script_ip = crate::ip::get_agent_ip(AgentType::PureScriptAgent, &script_id, agent_offset + i, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
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
            processes.push(crate::shadow::ShadowProcess {
                path: "/bin/bash".to_string(),
                args: format!("-c 'cat > {} << \\EOF\n{}\\EOF'", script_path, wrapper_script),
                environment: environment.clone(),
                start_time: script_creation_time,
            });

            // Process 2: Execute wrapper script
            processes.push(crate::shadow::ShadowProcess {
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