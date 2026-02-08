//! Simulation monitor agent processing.
//!
//! This module handles the configuration and processing of simulation monitor agents,
//! which provide real-time monitoring and logging of simulation progress. These agents
//! track simulation state, performance metrics, and can trigger alerts based on
//! configurable conditions.

use crate::config_v2::{AgentDefinitions, AgentConfig};
use crate::gml_parser::GmlGraph;
use crate::shadow::ShadowHost;
use crate::ip::{GlobalIpRegistry, AsSubnetManager, AgentType, get_agent_ip};
use crate::utils::script::write_wrapper_script;
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
/// - `output_dir`: Shadow output directory for daemon logs and status file
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
    output_dir: &Path,
    _stop_time: &str,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    agent_offset: usize,
    scripts_dir: &Path,
) -> color_eyre::eyre::Result<()> {
    // Find simulation_monitor agent in the named agents map
    let simulation_monitor: Option<(&String, &AgentConfig)> = agents.agents.iter()
        .find(|(id, config)| {
            id.contains("simulation_monitor") ||
            config.script.as_ref().map_or(false, |s| s.contains("simulation_monitor"))
        });

    if let Some((agent_id, simulation_monitor_config)) = simulation_monitor {
        let simulation_monitor_id = agent_id.as_str();
        // Assign simulation monitor to node 0 (which has bandwidth info in GML)
        let network_node_id = 0;
        let simulation_monitor_ip = get_agent_ip(AgentType::PureScriptAgent, simulation_monitor_id, agent_offset, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry, None);
        let mut processes = Vec::new();

        // Convert output_dir to absolute path string
        let output_dir_str = output_dir.to_str().unwrap();

        let mut agent_args = vec![
            format!("--id {}", simulation_monitor_id),
            format!("--shared-dir {}", shared_dir.to_str().unwrap()),
            format!("--output-dir {}", output_dir_str),
            format!("--log-level DEBUG"),
        ];

        // Add configuration-specific arguments from AgentConfig fields
        if let Some(poll_interval) = simulation_monitor_config.poll_interval {
            agent_args.push(format!("--poll-interval {}", poll_interval));
        }

        // Status file - use shared directory for portability
        if let Some(status_file) = &simulation_monitor_config.status_file {
            if status_file.starts_with('/') {
                // Absolute path - use as-is
                agent_args.push(format!("--status-file {}", status_file));
            } else {
                // Relative path - put in shared directory
                agent_args.push(format!("--status-file {}/{}", shared_dir.to_str().unwrap(), status_file));
            }
        } else {
            // Default status file in shared directory
            agent_args.push(format!("--status-file {}/monerosim_monitor.log", shared_dir.to_str().unwrap()));
        }

        if simulation_monitor_config.enable_alerts.unwrap_or(false) {
            agent_args.push("--enable-alerts".to_string());
        }

        if simulation_monitor_config.detailed_logging.unwrap_or(false) {
            agent_args.push("--detailed-logging".to_string());
        }

        // Add any additional arguments from attributes
        if let Some(attrs) = &simulation_monitor_config.attributes {
            for (key, value) in attrs {
                agent_args.push(format!("--{} {}", key, value));
            }
        }

        // Get script path
        let script = simulation_monitor_config.script.clone()
            .unwrap_or_else(|| "agents.simulation_monitor".to_string());

        // Simplified command for simulation monitor agent
        let python_cmd = if script.contains('.') && !script.contains('/') && !script.contains('\\') {
            format!("python3 -m {} {}", script, agent_args.join(" "))
        } else {
            format!("python3 {} {}", script, agent_args.join(" "))
        };

        // Resolve HOME for fully-qualified paths (no shell expansion needed)
        let home_dir = environment.get("HOME").cloned()
            .unwrap_or_else(|| std::env::var("HOME").unwrap_or_else(|_| "/root".to_string()));

        // Create wrapper script with fully-resolved paths
        let wrapper_script = format!(
            r#"#!/bin/bash
cd {}
export PYTHONPATH={}
export PATH=/usr/local/bin:/usr/bin:/bin:{}/.monerosim/bin

{} 2>&1
"#,
            current_dir,
            current_dir,
            home_dir,
            python_cmd
        );

        let process = write_wrapper_script(
            scripts_dir,
            &format!("{}_wrapper.sh", simulation_monitor_id),
            &wrapper_script,
            environment,
            "5s".to_string(), // Start early to monitor from beginning
            None,
            Some(crate::shadow::ExpectedFinalState::Running),
        )?;
        processes.push(process);

        hosts.insert(simulation_monitor_id.to_string(), ShadowHost {
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
