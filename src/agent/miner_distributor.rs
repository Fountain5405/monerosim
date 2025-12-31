//! Miner distributor agent processing.
//!
//! This module handles the configuration and processing of miner distributor agents,
//! which manage the distribution of mining rewards and coordinate mining activities
//! across the network. Miner distributors typically start after block maturity
//! to handle reward distribution.

use crate::config_v2::{AgentDefinitions, PeerMode};
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
    peer_mode: &PeerMode,
) -> color_eyre::eyre::Result<()> {
    if let Some(miner_distributor_config) = &agents.miner_distributor {
        let miner_distributor_id = "minerdistributor";
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
        let python_cmd = if miner_distributor_config.script.contains('.') && !miner_distributor_config.script.contains('/') && !miner_distributor_config.script.contains('\\') {
            format!("python3 -m {} {}", miner_distributor_config.script, agent_args.join(" "))
        } else {
            format!("python3 {} {}", miner_distributor_config.script, agent_args.join(" "))
        };

        // Create a simple wrapper script for miner distributor
        let wrapper_script = format!(
            r#"#!/bin/bash
cd {}
export PYTHONPATH="${{PYTHONPATH}}:{}"
export PATH="${{PATH}}:/usr/local/bin"

echo "Starting miner distributor..."
{} 2>&1
"#,
            current_dir,
            current_dir,
            python_cmd
        );

        // Write wrapper script to a temporary file and execute it
        let script_path = format!("/tmp/{}_wrapper.sh", miner_distributor_id);

        // Determine execution start time (keeping original for block maturity)
        let miner_distributor_start_time = if matches!(peer_mode, PeerMode::Dynamic) {
            "3900s".to_string() // Dynamic mode: miner distributor starts at 65 minutes (block reward maturity)
        } else {
            "3900s".to_string() // Other modes: also start at 65 minutes (block reward maturity)
        };

        // Calculate script creation time (1 second before execution)
        let script_creation_time = if let Ok(exec_seconds) = crate::utils::duration::parse_duration_to_seconds(&miner_distributor_start_time) {
            format!("{}s", exec_seconds.saturating_sub(1))
        } else {
            // Fallback if parsing fails
            "3899s".to_string()
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
            start_time: miner_distributor_start_time,
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
