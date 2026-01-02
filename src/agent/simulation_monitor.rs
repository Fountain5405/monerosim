//! Simulation monitor agent processing.
//!
//! This module handles the configuration and processing of simulation monitor agents,
//! which provide real-time monitoring and logging of simulation progress. These agents
//! track simulation state, performance metrics, and can trigger alerts based on
//! configurable conditions.

use crate::config_v2::AgentDefinitions;
use crate::gml_parser::GmlGraph;
use crate::shadow::ShadowHost;
use crate::ip::{GlobalIpRegistry, AsSubnetManager, AgentType, get_agent_ip};
use std::collections::BTreeMap;
use std::path::Path;

/// Process simulation monitor agent
///
/// Creates a Shadow host configuration for the simulation monitor agent,
/// which provides real-time monitoring and logging of simulation progress.
///
/// # Parameters
/// - `agents`: Agent definitions from configuration
/// - `hosts`: Mutable map to store created Shadow hosts
/// - `subnet_manager`: IP subnet manager for address allocation
/// - `ip_registry`: Global IP registry for address allocation
/// - `environment`: Environment variables for the process
/// - `shared_dir`: Shared directory for inter-agent communication
/// - `current_dir`: Current working directory
/// - `_stop_time`: Simulation stop time (unused)
/// - `gml_graph`: Optional GML topology graph
/// - `using_gml_topology`: Whether GML topology is being used
/// - `agent_offset`: Offset for IP allocation to avoid conflicts
///
/// # Returns
/// Result indicating success or failure of simulation monitor processing
pub fn process_simulation_monitor(
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
    if let Some(simulation_monitor_config) = &agents.simulation_monitor {
        let simulation_monitor_id = "simulation-monitor";
        // Assign simulation monitor to node 0 (which has bandwidth info in GML)
        let network_node_id = 0;
        let simulation_monitor_ip = get_agent_ip(AgentType::PureScriptAgent, simulation_monitor_id, agent_offset, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
        let mut processes = Vec::new();

        let mut agent_args = vec![
            format!("--id simulation_monitor"),  // Keep original ID for agent consistency
            format!("--shared-dir {}", shared_dir.to_str().unwrap()),
            format!("--log-level DEBUG"),
        ];

        // Add configuration-specific arguments
        if let Some(poll_interval) = simulation_monitor_config.poll_interval {
            agent_args.push(format!("--poll-interval {}", poll_interval));
        }

        if let Some(status_file) = &simulation_monitor_config.status_file {
            agent_args.push(format!("--status-file {}", status_file));
        }

        if simulation_monitor_config.enable_alerts.unwrap_or(false) {
            agent_args.push("--enable-alerts".to_string());
        }

        if simulation_monitor_config.detailed_logging.unwrap_or(false) {
            agent_args.push("--detailed-logging".to_string());
        }

        // Add any additional arguments from the configuration
        if let Some(args) = &simulation_monitor_config.arguments {
            agent_args.extend(args.iter().cloned());
        }

        // Simplified command for simulation monitor agent
        let python_cmd = if simulation_monitor_config.script.contains('.') && !simulation_monitor_config.script.contains('/') && !simulation_monitor_config.script.contains('\\') {
            format!("python3 -m {} {}", simulation_monitor_config.script, agent_args.join(" "))
        } else {
            format!("python3 {} {}", simulation_monitor_config.script, agent_args.join(" "))
        };

        // Create a wrapper script for simulation monitor agent
        let wrapper_script = format!(
            r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:$HOME/.monerosim/bin"

echo "Starting simulation monitor agent..."
{} 2>&1
"#,
            current_dir,
            current_dir,
            python_cmd
        );

        // Write wrapper script to a temporary file and execute it
        let script_path = "/tmp/simulation_monitor_wrapper.sh".to_string();

        // Determine execution start time (start early to monitor from beginning)
        let simulation_monitor_start_time = "5s".to_string();

        // Calculate script creation time (1 second before execution)
        let script_creation_time = "4s".to_string();

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
            start_time: simulation_monitor_start_time,
        });

        hosts.insert("simulation-monitor".to_string(), ShadowHost {
            network_node_id, // Use the assigned GML node with bandwidth info
            ip_addr: Some(simulation_monitor_ip),
            processes,
            bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
            bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
        });
        // Note: next_ip is already incremented in get_agent_ip function
    }

    Ok(())
}
