//! Agent lifecycle management functions for Monerosim.
//!
//! This module handles agent startup, shutdown, and state management logic
//! extracted from the monolithic shadow_agents.rs file.

use crate::config_v2::{AgentDefinitions, Network, PeerMode};
use crate::gml_parser::GmlGraph;
use crate::ip::{GlobalIpRegistry, AsSubnetManager, AgentType, get_agent_ip};
use crate::shadow::ShadowHost;
use crate::topology::Topology;
use crate::utils::duration::parse_duration_to_seconds;
use std::collections::BTreeMap;

/// Manages the lifecycle of agent processes within the simulation.
///
/// This function coordinates the timing and sequencing of agent startup,
/// ensuring proper dependencies between daemons, wallets, and user scripts.
///
/// # Arguments
/// * `config` - The complete simulation configuration
/// * `hosts` - Mutable reference to the hosts map for adding agent processes
/// * `gml_graph` - Optional GML topology graph for network-aware placement
/// * `using_gml_topology` - Whether GML topology is being used
/// * `peer_mode` - The peer discovery mode (Dynamic/Hardcoded/Hybrid)
/// * `topology` - Optional topology configuration
/// * `subnet_manager` - IP subnet allocation manager
/// * `ip_registry` - Global IP address registry
/// * `environment` - Environment variables for processes
/// * `monero_environment` - Monero-specific environment variables
/// * `shared_dir` - Shared directory path for inter-agent communication
/// * `current_dir` - Current working directory
/// * `agent_offset` - IP offset to avoid conflicts with other agent types
///
/// # Returns
/// Result indicating success or failure of lifecycle management
pub fn process_agent_lifecycle(
    config: &crate::config_v2::Config,
    hosts: &mut BTreeMap<String, ShadowHost>,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    peer_mode: &PeerMode,
    topology: Option<&Topology>,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    environment: &BTreeMap<String, String>,
    monero_environment: &BTreeMap<String, String>,
    shared_dir: &std::path::Path,
    current_dir: &str,
    agent_offset: usize,
) -> color_eyre::eyre::Result<()> {
    // Calculate staggered start times based on peer mode and agent type
    let start_times = calculate_agent_start_times(&config.agents, peer_mode);

    // Process user agents with lifecycle management
    process_user_agents_with_lifecycle(
        &config.agents,
        hosts,
        gml_graph,
        using_gml_topology,
        peer_mode,
        topology,
        subnet_manager,
        ip_registry,
        environment,
        monero_environment,
        shared_dir,
        current_dir,
        agent_offset,
        &start_times,
    )?;

    // Process block controller with lifecycle management
    process_block_controller_with_lifecycle(
        &config.agents,
        hosts,
        gml_graph,
        using_gml_topology,
        peer_mode,
        subnet_manager,
        ip_registry,
        environment,
        shared_dir,
        current_dir,
        agent_offset,
        &start_times,
    )?;

    // Process pure script agents with lifecycle management
    process_pure_script_agents_with_lifecycle(
        &config.agents,
        hosts,
        gml_graph,
        using_gml_topology,
        subnet_manager,
        ip_registry,
        environment,
        shared_dir,
        current_dir,
        agent_offset,
        &start_times,
    )?;

    Ok(())
}

/// Calculates optimal start times for different agent types based on peer mode.
///
/// # Arguments
/// * `agents` - Agent configuration definitions
/// * `peer_mode` - The peer discovery mode
///
/// # Returns
/// HashMap mapping agent types to their calculated start times
fn calculate_agent_start_times(
    agents: &AgentDefinitions,
    peer_mode: &PeerMode,
) -> BTreeMap<String, String> {
    let mut start_times = BTreeMap::new();

    // Base timing calculations
    let (miner_start, user_start, controller_start, script_start) = match peer_mode {
        PeerMode::Dynamic => ("0s".to_string(), "5s".to_string(), "10s".to_string(), "15s".to_string()),
        _ => ("0s".to_string(), "3s".to_string(), "15s".to_string(), "20s".to_string()),
    };

    start_times.insert("miner".to_string(), miner_start);
    start_times.insert("user".to_string(), user_start);
    start_times.insert("block_controller".to_string(), controller_start);
    start_times.insert("pure_script".to_string(), script_start);

    start_times
}

/// Processes user agents with proper lifecycle management.
///
/// This includes daemon startup, wallet initialization, and user script execution
/// with appropriate timing dependencies.
fn process_user_agents_with_lifecycle(
    agents: &AgentDefinitions,
    hosts: &mut BTreeMap<String, ShadowHost>,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    peer_mode: &PeerMode,
    topology: Option<&Topology>,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    environment: &BTreeMap<String, String>,
    monero_environment: &BTreeMap<String, String>,
    shared_dir: &std::path::Path,
    current_dir: &str,
    agent_offset: usize,
    start_times: &BTreeMap<String, String>,
) -> color_eyre::eyre::Result<()> {
    // Implementation would include the user agent processing logic
    // with proper lifecycle management, timing, and dependencies

    // This is a placeholder - the actual implementation would be
    // extracted from the process_user_agents function in shadow_agents.rs
    Ok(())
}

/// Processes block controller with lifecycle management.
///
/// Ensures block controller starts after miners are initialized but before
/// heavy transaction activity begins.
fn process_block_controller_with_lifecycle(
    agents: &AgentDefinitions,
    hosts: &mut BTreeMap<String, ShadowHost>,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    peer_mode: &PeerMode,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    environment: &BTreeMap<String, String>,
    shared_dir: &std::path::Path,
    current_dir: &str,
    agent_offset: usize,
    start_times: &BTreeMap<String, String>,
) -> color_eyre::eyre::Result<()> {
    // Implementation would include block controller lifecycle logic
    // This is a placeholder - actual implementation from shadow_agents.rs
    Ok(())
}

/// Processes pure script agents with lifecycle management.
///
/// Pure script agents start later in the simulation lifecycle,
/// typically for monitoring or analysis purposes.
fn process_pure_script_agents_with_lifecycle(
    agents: &AgentDefinitions,
    hosts: &mut BTreeMap<String, ShadowHost>,
    gml_graph: Option<&GmlGraph>,
    using_gml_topology: bool,
    subnet_manager: &mut AsSubnetManager,
    ip_registry: &mut GlobalIpRegistry,
    environment: &BTreeMap<String, String>,
    shared_dir: &std::path::Path,
    current_dir: &str,
    agent_offset: usize,
    start_times: &BTreeMap<String, String>,
) -> color_eyre::eyre::Result<()> {
    // Implementation would include pure script agent lifecycle logic
    // This is a placeholder - actual implementation from shadow_agents.rs
    Ok(())
}

/// Validates agent lifecycle dependencies and timing.
///
/// Ensures that agent startup order respects dependencies between
/// daemons, wallets, and user scripts.
pub fn validate_agent_lifecycle(
    agents: &AgentDefinitions,
    peer_mode: &PeerMode,
) -> color_eyre::eyre::Result<()> {
    // Validate that miners have wallets if required
    if let Some(user_agents) = &agents.user_agents {
        for (idx, agent) in user_agents.iter().enumerate() {
            // Miners require a local daemon
            if agent.is_miner_value() && !agent.has_local_daemon() {
                return Err(color_eyre::eyre::eyre!(
                    "Miner agent at index {} must have a local daemon",
                    idx
                ));
            }
            // Miners require a wallet for reward address
            if agent.is_miner_value() && agent.wallet.is_none() {
                return Err(color_eyre::eyre::eyre!(
                    "Miner agent at index {} must have a wallet configuration",
                    idx
                ));
            }
        }
    }

    // Validate timing constraints for different peer modes
    match peer_mode {
        PeerMode::Dynamic => {
            // Dynamic mode has more relaxed timing requirements
        }
        PeerMode::Hardcoded | PeerMode::Hybrid => {
            // These modes require more precise timing coordination
            if agents.block_controller.is_none() {
                log::warn!("Block controller recommended for Hardcoded/Hybrid peer modes");
            }
        }
    }

    Ok(())
}