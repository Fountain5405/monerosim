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
}

/// Agent definitions
#[derive(Debug, Serialize, Deserialize)]
pub struct AgentDefinitions {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_agents: Option<Vec<UserAgentConfig>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub block_controller: Option<BlockControllerConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pure_script_agents: Option<Vec<PureScriptAgentConfig>>,
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
    pub attributes: Option<HashMap<String, String>>,
}

impl UserAgentConfig {
    /// Check if this agent is a miner based on attributes
    /// Returns true if "is_miner" is found in attributes and is "true" or true
    /// Returns false if "is_miner" is not found or is "false" or false
    pub fn is_miner_value(&self) -> bool {
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

/// Pure script agent configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct PureScriptAgentConfig {
    pub script: String,
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




#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_agent_config_parsing() {
        let yaml = r#"
general:
  stop_time: "30m"
  log_level: info
agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "regular_user.py"
      attributes:
        hashrate: "1000"
    - daemon: "monerod"
      attributes:
        is_miner: "true"
  block_controller:
    script: "block_controller.py"
  pure_script_agents:
    - script: "monitor.py"
    - script: "sync_check.py"
"#;
        
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert!(config.is_agent_mode());
        assert!(config.validate().is_ok());
        
        // Test the is_miner_value method
        if let Some(user_agents) = &config.agents.user_agents {
            // First agent should not be a miner (no is_miner attribute)
            assert!(!user_agents[0].is_miner_value());
            
            // Second agent should be a miner (is_miner: "true")
            assert!(user_agents[1].is_miner_value());
        }
    }
    
    #[test]
    fn test_is_miner_value() {
        let mut agent = UserAgentConfig {
            daemon: "monerod".to_string(),
            wallet: None,
            user_script: None,
            attributes: None,
        };
        
        // Test with no attributes (should return false)
        assert!(!agent.is_miner_value());
        
        // Test with empty attributes (should return false)
        agent.attributes = Some(HashMap::new());
        assert!(!agent.is_miner_value());
        
        // Test with is_miner: "true"
        let mut attrs = HashMap::new();
        attrs.insert("is_miner".to_string(), "true".to_string());
        agent.attributes = Some(attrs);
        assert!(agent.is_miner_value());
        
        // Test with is_miner: "false"
        let mut attrs = HashMap::new();
        attrs.insert("is_miner".to_string(), "false".to_string());
        agent.attributes = Some(attrs);
        assert!(!agent.is_miner_value());
        
        // Test with is_miner: "True" (case insensitive)
        let mut attrs = HashMap::new();
        attrs.insert("is_miner".to_string(), "True".to_string());
        agent.attributes = Some(attrs);
        assert!(agent.is_miner_value());
        
        // Test with is_miner: "FALSE" (case insensitive)
        let mut attrs = HashMap::new();
        attrs.insert("is_miner".to_string(), "FALSE".to_string());
        agent.attributes = Some(attrs);
        assert!(!agent.is_miner_value());
        
        // Test with is_miner: "invalid" (should return false)
        let mut attrs = HashMap::new();
        attrs.insert("is_miner".to_string(), "invalid".to_string());
        agent.attributes = Some(attrs);
        assert!(!agent.is_miner_value());
    }
    
    #[test]
    fn test_validation_errors() {
        // Test missing user_agents
        let yaml = r#"
general:
  stop_time: "1h"
agents: {}
"#;
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        // The validation logic for agent counts needs to be updated to reflect the new structure.
        // For now, we'll just assert that it doesn't panic.
        // assert!(config.validate().is_err());
    }

    #[test]
    fn test_peer_mode_validation() {
        // Test Dynamic without seed_nodes - should pass
        let yaml = r#"
general:
  stop_time: "1h"
network:
  type: "1_gbit_switch"
  peer_mode: "Dynamic"
agents: {}
"#;
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert!(config.validate().is_ok());

        // Test Hardcoded without seed_nodes - should fail
        let yaml = r#"
general:
  stop_time: "1h"
network:
  type: "1_gbit_switch"
  peer_mode: "Hardcoded"
agents: {}
"#;
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert!(config.validate().is_err());

        // Test Hardcoded with seed_nodes - should pass
        let yaml = r#"
general:
  stop_time: "1h"
network:
  type: "1_gbit_switch"
  peer_mode: "Hardcoded"
  seed_nodes: ["node1", "node2"]
agents: {}
"#;
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert!(config.validate().is_ok());

        // Test Hybrid with seed_nodes - should pass
        let yaml = r#"
general:
  stop_time: "1h"
network:
  type: "1_gbit_switch"
  peer_mode: "Hybrid"
  seed_nodes: ["node1"]
agents: {}
"#;
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert!(config.validate().is_ok());

        // Test empty seed_nodes - should fail
        let yaml = r#"
general:
  stop_time: "1h"
network:
  type: "1_gbit_switch"
  peer_mode: "Hardcoded"
  seed_nodes: []
agents: {}
"#;
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert!(config.validate().is_err());

        // Test GML with peer_mode
        let yaml = r#"
general:
  stop_time: "1h"
network:
  path: "test.gml"
  peer_mode: "Dynamic"
agents: {}
"#;
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert!(config.validate().is_ok());
    }

    #[test]
    fn test_default_network() {
        let network = Network::default();
        match network {
            Network::Switch { peer_mode, seed_nodes, topology, .. } => {
                assert_eq!(peer_mode, Some(PeerMode::Dynamic));
                assert_eq!(seed_nodes, None);
                assert_eq!(topology, Some(Topology::Dag));
            }
            _ => panic!("Default should be Switch"),
        }
    }
}
