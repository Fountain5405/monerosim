//! Block controller agent processing.
//!
//! This module handles the configuration and processing of block controller agents,
//! which coordinate mining activities and block production in the simulation.
//! Block controllers manage the overall mining strategy and reward distribution.

use crate::config_v2::{AgentDefinitions, PeerMode};
use crate::gml_parser::GmlGraph;
use crate::shadow::ShadowHost;
use crate::ip::{GlobalIpRegistry, AsSubnetManager, AgentType, get_agent_ip};
use std::collections::HashMap;
use std::path::Path;

/// Process block controller agent
pub fn process_block_controller(
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
    peer_mode: &PeerMode,
) -> color_eyre::eyre::Result<()> {
    if let Some(block_controller_config) = &agents.block_controller {
        let block_controller_id = "blockcontroller";
        // Assign block controller to node 0 (which has bandwidth info in GML)
        let network_node_id = 0;
        let block_controller_ip = get_agent_ip(AgentType::BlockController, block_controller_id, agent_offset, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
        let mut processes = Vec::new();

        let mut agent_args = vec![
            format!("--id {}", block_controller_id),
            format!("--shared-dir {}", shared_dir.to_str().unwrap()),
            format!("--log-level DEBUG"),
        ];

        if let Some(args) = &block_controller_config.arguments {
            agent_args.extend(args.iter().cloned());
        }

        // Simplified command for block controller
        let python_cmd = if block_controller_config.script.contains('.') && !block_controller_config.script.contains('/') && !block_controller_config.script.contains('\\') {
            format!("python3 -m {} {}", block_controller_config.script, agent_args.join(" "))
        } else {
            format!("python3 {} {}", block_controller_config.script, agent_args.join(" "))
        };

        // Create a simple wrapper script for block controller
        let wrapper_script = format!(
            r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:/usr/local/bin"

echo "Starting block controller..."
{} 2>&1
"#,
            current_dir,
            current_dir,
            python_cmd
        );

        // Write wrapper script to a temporary file and execute it
        let script_path = format!("/tmp/{}_wrapper.sh", block_controller_id);

        // Determine execution start time (optimized)
        let block_controller_start_time = if matches!(peer_mode, PeerMode::Dynamic) {
            "10s".to_string() // Dynamic mode: block controller starts at 10s (reduced from 20s)
        } else {
            "15s".to_string() // Other modes: reduced from 90s
        };

        // Calculate script creation time (1 second before execution)
        let script_creation_time = if let Ok(exec_seconds) = crate::utils::duration::parse_duration_to_seconds(&block_controller_start_time) {
            format!("{}s", exec_seconds.saturating_sub(1))
        } else {
            // Fallback if parsing fails
            "89s".to_string()
        };

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
            start_time: block_controller_start_time,
        });

        hosts.insert(block_controller_id.to_string(), ShadowHost {
            network_node_id, // Use the assigned GML node with bandwidth info
            ip_addr: Some(block_controller_ip),
            processes,
            bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
            bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
        });
        // Note: next_ip is already incremented in get_agent_ip function
    }

    Ok(())
}
