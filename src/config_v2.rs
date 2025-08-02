use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Unified configuration that supports only agent mode
#[derive(Debug, Serialize, Deserialize)]
pub struct Config {
    pub general: GeneralConfig,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub network: Option<NetworkConfig>,
    pub agents: AgentDefinitions,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mining: Option<MiningConfig>,
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
        
        // Validate agent counts
        if self.agents.regular_users.count == 0 {
            return Err(ValidationError::InvalidAgent(
                "regular_users.count must be greater than 0".to_string()
            ));
        }
        
        if self.agents.marketplaces.count == 0 {
            return Err(ValidationError::InvalidAgent(
                "marketplaces.count must be greater than 0".to_string()
            ));
        }
        
        if self.agents.mining_pools.count == 0 {
            return Err(ValidationError::InvalidAgent(
                "mining_pools.count must be greater than 0".to_string()
            ));
        }
        
        // Validate transaction amounts
        if let (Some(min), Some(max)) = (
            self.agents.regular_users.min_transaction_amount,
            self.agents.regular_users.max_transaction_amount
        ) {
            if min > max {
                return Err(ValidationError::InvalidAgent(
                    "min_transaction_amount cannot be greater than max_transaction_amount".to_string()
                ));
            }
            if min <= 0.0 {
                return Err(ValidationError::InvalidAgent(
                    "min_transaction_amount must be positive".to_string()
                ));
            }
        }
        
        // Validate mining settings
        if let Some(mining) = &self.mining {
            if mining.block_time < 30 {
                return Err(ValidationError::InvalidAgent(
                    "mining.block_time must be at least 30 seconds".to_string()
                ));
            }
            if mining.number_of_mining_nodes == 0 {
                return Err(ValidationError::InvalidAgent(
                    "mining.number_of_mining_nodes must be greater than 0".to_string()
                ));
            }
            if mining.mining_distribution.len() != mining.number_of_mining_nodes as usize {
                return Err(ValidationError::InvalidAgent(
                    format!(
                        "mining.mining_distribution length ({}) must match number_of_mining_nodes ({})",
                        mining.mining_distribution.len(), mining.number_of_mining_nodes
                    )
                ));
            }
            if mining.solo_miner_threshold <= 0.0 || mining.solo_miner_threshold >= 1.0 {
                return Err(ValidationError::InvalidAgent(
                    "mining.solo_miner_threshold must be between 0.0 and 1.0".to_string()
                ));
            }
        }
        
        // Validate network settings
        if let Some(network) = &self.network {
            if network.network_type.is_empty() {
                return Err(ValidationError::InvalidNetwork(
                    "network type cannot be empty".to_string()
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
    pub regular_users: RegularUserConfig,
    pub marketplaces: MarketplaceConfig,
    pub mining_pools: MiningPoolConfig,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub custom_agents: Option<Vec<CustomAgentConfig>>,
}

/// Regular user agent configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct RegularUserConfig {
    pub count: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transaction_interval: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_transaction_amount: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_transaction_amount: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_settings: Option<WalletSettings>,
}

/// Marketplace agent configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct MarketplaceConfig {
    pub count: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub payment_processing_delay: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_settings: Option<WalletSettings>,
}

/// Mining pool agent configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct MiningPoolConfig {
    pub count: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mining_threads: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pool_fee: Option<f64>,
}

/// Wallet settings for agents
#[derive(Debug, Serialize, Deserialize)]
pub struct WalletSettings {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub initial_balance: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet_name: Option<String>,
}

/// Custom agent configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct CustomAgentConfig {
    #[serde(rename = "type")]
    pub agent_type: String,
    pub count: u32,
    pub script: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parameters: Option<HashMap<String, serde_yaml::Value>>,
}
/// Mining configuration
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MiningConfig {
    pub block_time: u32,
    pub number_of_mining_nodes: u32,
    pub mining_distribution: Vec<u32>,
    pub solo_miner_threshold: f64,
}


/// Network configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct NetworkConfig {
    #[serde(rename = "type")]
    pub network_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bandwidth: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub latency: Option<String>,
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

impl Default for RegularUserConfig {
    fn default() -> Self {
        Self {
            count: 10,
            transaction_interval: Some(60),
            min_transaction_amount: Some(0.1),
            max_transaction_amount: Some(1.0),
            wallet_settings: None,
        }
    }
}

impl Default for MarketplaceConfig {
    fn default() -> Self {
        Self {
            count: 2,
            payment_processing_delay: Some(5),
            wallet_settings: None,
        }
    }
}

impl Default for MiningPoolConfig {
    fn default() -> Self {
        Self {
            count: 2,
            mining_threads: Some(1),
            pool_fee: Some(0.01),
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
  regular_users:
    count: 10
    transaction_interval: 60
  marketplaces:
    count: 3
  mining_pools:
    count: 2
mining:
  block_time: 120
  number_of_mining_nodes: 3
  mining_distribution: [70, 20, 10]
  solo_miner_threshold: 0.05
"#;
        
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert!(config.is_agent_mode());
        assert!(config.validate().is_ok());
    }
    
    #[test]
    fn test_validation_errors() {
        // Test zero agent count
        let yaml = r#"
general:
  stop_time: "1h"
agents:
  regular_users:
    count: 0
  marketplaces:
    count: 1
  mining_pools:
    count: 1
"#;
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert!(config.validate().is_err());
    }
}