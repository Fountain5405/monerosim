use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Peer mode options for network configuration
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub enum PeerMode {
    /// Dynamic peer discovery using network protocols
    Dynamic,
    /// Hardcoded list of peers
    Hardcoded,
    /// Hybrid approach combining dynamic and hardcoded peers
    Hybrid,
}

/// Topology templates for peer connections
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub enum Topology {
    /// Star topology: all nodes connect to a central hub
    Star,
    /// Mesh topology: all nodes connect to all other nodes
    Mesh,
    /// Ring topology: circular connections between nodes
    Ring,
    /// DAG (Directed Acyclic Graph): hierarchical connections
    Dag,
}

/// Unified configuration that supports only agent mode
#[derive(Debug, Serialize, Deserialize)]
pub struct Config {
    pub general: GeneralConfig,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub network: Option<Network>,
    pub agents: AgentDefinitions,
}

impl Config {
    /// Validate the configuration
    pub fn validate(&self) -> Result<(), ValidationError> {
        // Validate general settings
        if self.general.stop_time.is_empty() {
            return Err(ValidationError::InvalidGeneral(
                "stop_time cannot be empty".to_string()
            ));
        }
        
        // Validate network settings
        if let Some(network) = &self.network {
            match network {
                Network::Gml { path, peer_mode, seed_nodes, .. } => {
                    if path.is_empty() {
                        return Err(ValidationError::InvalidNetwork(
                            "GML path cannot be empty".to_string(),
                        ));
                    }
                    Self::validate_peer_config(peer_mode, seed_nodes)?;
                }
                Network::Switch { network_type, peer_mode, seed_nodes, .. } => {
                    if network_type.is_empty() {
                        return Err(ValidationError::InvalidNetwork(
                            "Network type cannot be empty for Switch".to_string(),
                        ));
                    }
                    Self::validate_peer_config(peer_mode, seed_nodes)?;
                }
            }
        }
        
        Ok(())
    }

    /// Validate peer configuration based on peer mode
    fn validate_peer_config(peer_mode: &Option<PeerMode>, seed_nodes: &Option<Vec<String>>) -> Result<(), ValidationError> {
        if let Some(mode) = peer_mode {
            match mode {
                PeerMode::Hardcoded | PeerMode::Hybrid => {
                    if seed_nodes.is_none() || seed_nodes.as_ref().unwrap().is_empty() {
                        return Err(ValidationError::InvalidNetwork(
                            format!("seed_nodes must be provided and non-empty for peer_mode {:?}", mode)
                        ));
                    }
                }
                PeerMode::Dynamic => {
                    // For Dynamic, seed_nodes can be None or empty
                }
            }
        }

        // If seed_nodes is provided, ensure it's not empty
        if let Some(nodes) = seed_nodes {
            if nodes.is_empty() {
                return Err(ValidationError::InvalidNetwork(
                    "seed_nodes cannot be an empty list".to_string()
                ));
            }
        }

        Ok(())
    }

    /// Get the general configuration
    pub fn general(&self) -> &GeneralConfig {
        &self.general
    }
    
    /// Check if this is an agent configuration (always true now)
    pub fn is_agent_mode(&self) -> bool {
        true
    }
}

/// Shared general configuration
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GeneralConfig {
    pub stop_time: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fresh_blockchain: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub python_venv: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub log_level: Option<String>,
    #[serde(default = "default_simulation_seed")]
    pub simulation_seed: u64,
}

fn default_simulation_seed() -> u64 {
    12345
}

/// Agent definitions
#[derive(Debug, Serialize, Deserialize)]
pub struct AgentDefinitions {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_agents: Option<Vec<UserAgentConfig>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub block_controller: Option<BlockControllerConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub miner_distributor: Option<MinerDistributorConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pure_script_agents: Option<Vec<PureScriptAgentConfig>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub simulation_monitor: Option<SimulationMonitorConfig>,
}

/// User agent configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct UserAgentConfig {
    pub daemon: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_script: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mining_script: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_miner: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attributes: Option<HashMap<String, String>>,
    /// Optional start time offset (e.g., "2h", "7200s", "30m")
    /// This offset is added to the normally calculated start time,
    /// allowing agents to join mid-simulation while preserving staggered launches.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub start_time_offset: Option<String>,
}

impl UserAgentConfig {
    /// Check if this agent is a miner based on top-level field or attributes
    /// Returns true if is_miner is true or "is_miner" in attributes is "true" or true
    /// Returns false otherwise
    pub fn is_miner_value(&self) -> bool {
        // Check top-level is_miner field first
        if let Some(is_miner) = self.is_miner {
            return is_miner;
        }

        // Fall back to attributes
        if let Some(attrs) = &self.attributes {
            if let Some(is_miner_value) = attrs.get("is_miner") {
                // Handle string representations
                match is_miner_value.to_lowercase().as_str() {
                    "true" | "1" | "yes" | "on" => return true,
                    "false" | "0" | "no" | "off" => return false,
                    _ => {} // Continue to check other formats
                }

                // Try to parse as boolean directly
                if let Ok(parsed_bool) = is_miner_value.parse::<bool>() {
                    return parsed_bool;
                }
            }
        }
        false
    }
}

/// Block controller agent configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct BlockControllerConfig {
    pub script: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arguments: Option<Vec<String>>,
}

/// Miner distributor agent configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct MinerDistributorConfig {
    pub script: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attributes: Option<HashMap<String, String>>,
}

/// Pure script agent configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct PureScriptAgentConfig {
    pub script: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arguments: Option<Vec<String>>,
}

/// Simulation monitor agent configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct SimulationMonitorConfig {
    pub script: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub poll_interval: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status_file: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub enable_alerts: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub detailed_logging: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arguments: Option<Vec<String>>,
}


/// Network configuration, supporting different topology types
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(untagged)]
pub enum Network {
    Switch {
        #[serde(rename = "type")]
        network_type: String, // e.g., "1_gbit_switch"
        #[serde(skip_serializing_if = "Option::is_none")]
        bandwidth: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        latency: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        peer_mode: Option<PeerMode>,
        #[serde(skip_serializing_if = "Option::is_none")]
        seed_nodes: Option<Vec<String>>,
        #[serde(skip_serializing_if = "Option::is_none")]
        topology: Option<Topology>,
    },
    Gml {
        path: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        peer_mode: Option<PeerMode>,
        #[serde(skip_serializing_if = "Option::is_none")]
        seed_nodes: Option<Vec<String>>,
        #[serde(skip_serializing_if = "Option::is_none")]
        topology: Option<Topology>,
    },
}

/// Configuration validation errors
#[derive(Debug, thiserror::Error)]
pub enum ValidationError {
    #[error("Invalid agent configuration: {0}")]
    InvalidAgent(String),
    #[error("Invalid general configuration: {0}")]
    InvalidGeneral(String),
    #[error("Invalid network configuration: {0}")]
    InvalidNetwork(String),
}


/// Default implementations
impl Default for GeneralConfig {
    fn default() -> Self {
        Self {
            stop_time: "1h".to_string(),
            fresh_blockchain: Some(true),
            python_venv: None,
            log_level: Some("info".to_string()),
            simulation_seed: default_simulation_seed(),
        }
    }
}

impl Default for Network {
    fn default() -> Self {
        Network::Switch {
            network_type: "1_gbit_switch".to_string(),
            bandwidth: None,
            latency: None,
            peer_mode: Some(PeerMode::Dynamic),
            seed_nodes: None,
            topology: Some(Topology::Dag), // Default to DAG for backward compatibility
        }
    }
}




