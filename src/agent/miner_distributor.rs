//! Miner distributor agent processing.
//!
//! This module handles the configuration and processing of miner distributor agents,
//! which manage the distribution of mining rewards and coordinate mining activities
//! across the network. Miner distributors typically start after block maturity
//! to handle reward distribution.

use crate::config_v2::{AgentDefinitions, AgentConfig, PeerMode};
use crate::gml_parser::GmlGraph;
use crate::shadow::ShadowHost;
use crate::ip::{GlobalIpRegistry, AsSubnetManager, AgentType, get_agent_ip};
use std::collections::BTreeMap;
use std::path::Path;

/// Process miner distributor agent
pub fn process_miner_distributor(
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
    _peer_mode: &PeerMode,
) -> color_eyre::eyre::Result<()> {
    // Find miner_distributor agent in the named agents map
    let miner_distributor: Option<(&String, &AgentConfig)> = agents.agents.iter()
        .find(|(id, config)| {
            id.contains("miner_distributor") ||
            config.script.as_ref().map_or(false, |s| s.contains("miner_distributor"))
        });

    if let Some((agent_id, miner_distributor_config)) = miner_distributor {
        let miner_distributor_id = agent_id.as_str();
        // Assign miner distributor to node 0 (which has bandwidth info in GML)
        let network_node_id = 0;
        let miner_distributor_ip = get_agent_ip(AgentType::MinerDistributor, miner_distributor_id, agent_offset, network_node_id, gml_graph, using_gml_topology, subnet_manager, ip_registry);
        let mut processes = Vec::new();

        let mut agent_args = vec![
            format!("--id {}", miner_distributor_id),
            format!("--shared-dir {}", shared_dir.to_str().unwrap()),
            format!("--log-level DEBUG"),
        ];

        // Add attributes from config
        if let Some(attrs) = &miner_distributor_config.attributes {
            for (key, value) in attrs {
                agent_args.push(format!("--attributes {} {}", key, value));
            }
        }

        // Simplified command for miner distributor
        let script = miner_distributor_config.script.clone()
            .unwrap_or_else(|| "agents.miner_distributor".to_string());
        let python_cmd = if script.contains('.') && !script.contains('/') && !script.contains('\\') {
            format!("python3 -m {} {}", script, agent_args.join(" "))
        } else {
            format!("python3 {} {}", script, agent_args.join(" "))
        };

        // Create a simple wrapper script for miner distributor
        let wrapper_script = format!(
            r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:$HOME/.monerosim/bin"

echo "Starting miner distributor..."
{} 2>&1
"#,
            current_dir,
            current_dir,
            python_cmd
        );

        // Write wrapper script to a temporary file and execute it
        let script_path = format!("/tmp/{}_wrapper.sh", miner_distributor_id);

        // Determine execution start time from config's wait_time field
        // Default: 14400s (4h) to ensure sufficient blocks for unlock and ring signatures
        let wait_time_seconds = miner_distributor_config.wait_time.unwrap_or(14400);
        let miner_distributor_start_time = format!("{}s", wait_time_seconds);

        // Calculate script creation time (1 second before execution)
        let script_creation_time = if let Ok(exec_seconds) = crate::utils::duration::parse_duration_to_seconds(&miner_distributor_start_time) {
            format!("{}s", exec_seconds.saturating_sub(1))
        } else {
            // Fallback if parsing fails
            "7499s".to_string()
        };

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
            start_time: miner_distributor_start_time,
            shutdown_time: None,
            expected_final_state: None,
        });

        hosts.insert(miner_distributor_id.to_string(), ShadowHost {
            network_node_id, // Use the assigned GML node with bandwidth info
            ip_addr: Some(miner_distributor_ip),
            processes,
            bandwidth_down: Some("1000000000".to_string()), // 1 Gbit/s
            bandwidth_up: Some("1000000000".to_string()),   // 1 Gbit/s
        });
        // Note: next_ip is already incremented in get_agent_ip function
    }

    Ok(())
}
