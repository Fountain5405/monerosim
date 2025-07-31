use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Unified configuration that supports both traditional and agent modes
#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "mode")]
pub enum Config {
    #[serde(rename = "agent")]
    Agent(AgentConfig),
    #[serde(rename = "traditional")]
    Traditional(TraditionalConfig),
}

/// Traditional mode configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct TraditionalConfig {
    pub general: GeneralConfig,
}

/// Agent mode configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct AgentConfig {
    pub general: GeneralConfig,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub network: Option<NetworkConfig>,
    pub agents: AgentDefinitions,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub block_generation: Option<BlockGenerationConfig>,
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

/// Configuration for a single Monero node (traditional mode)
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct NodeConfig {
    pub name: String,
    pub ip: String,
    pub port: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub start_time: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mining: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fixed_difficulty: Option<u32>,
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

/// Block generation configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct BlockGenerationConfig {
    pub interval: u32,
    pub pools_per_round: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub difficulty_adjustment: Option<String>,
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
    #[error("Invalid node configuration: {0}")]
    InvalidNode(String),
    #[error("Invalid agent configuration: {0}")]
    InvalidAgent(String),
    #[error("Invalid general configuration: {0}")]
    InvalidGeneral(String),
    #[error("Invalid network configuration: {0}")]
    InvalidNetwork(String),
}

impl Config {
    /// Validate the configuration
    pub fn validate(&self) -> Result<(), ValidationError> {
        match self {
            Config::Traditional(cfg) => cfg.validate(),
            Config::Agent(cfg) => cfg.validate(),
        }
    }
    
    /// Get the general configuration
    pub fn general(&self) -> &GeneralConfig {
        match self {
            Config::Traditional(cfg) => &cfg.general,
            Config::Agent(cfg) => &cfg.general,
        }
    }
    
    /// Check if this is an agent configuration
    pub fn is_agent_mode(&self) -> bool {
        matches!(self, Config::Agent(_))
    }
    
    /// Check if this is a traditional configuration
    pub fn is_traditional_mode(&self) -> bool {
        matches!(self, Config::Traditional(_))
    }
}

impl TraditionalConfig {
    fn validate(&self) -> Result<(), ValidationError> {
        // Validate general settings
        if self.general.stop_time.is_empty() {
            return Err(ValidationError::InvalidGeneral(
                "stop_time cannot be empty".to_string()
            ));
        }
        
        
        Ok(())
    }
}

impl AgentConfig {
    fn validate(&self) -> Result<(), ValidationError> {
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
        
        // Validate block generation settings
        if let Some(block_gen) = &self.block_generation {
            if block_gen.interval < 30 {
                return Err(ValidationError::InvalidAgent(
                    "block_generation.interval must be at least 30 seconds".to_string()
                ));
            }
            if block_gen.pools_per_round == 0 {
                return Err(ValidationError::InvalidAgent(
                    "block_generation.pools_per_round must be greater than 0".to_string()
                ));
            }
            if block_gen.pools_per_round > self.agents.mining_pools.count {
                return Err(ValidationError::InvalidAgent(
                    format!(
                        "block_generation.pools_per_round ({}) cannot exceed mining_pools.count ({})",
                        block_gen.pools_per_round, self.agents.mining_pools.count
                    )
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

impl Default for BlockGenerationConfig {
    fn default() -> Self {
        Self {
            interval: 60,
            pools_per_round: 1,
            difficulty_adjustment: Some("fixed".to_string()),
        }
    }
}

impl Default for NodeConfig {
    fn default() -> Self {
        Self {
            name: "node".to_string(),
            ip: "11.0.0.1".to_string(),
            port: 28080,
            start_time: Some("0s".to_string()),
            mining: Some(false),
            fixed_difficulty: None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_traditional_config_parsing() {
        let yaml = r#"
general:
  stop_time: "3h"
  fresh_blockchain: true
nodes:
  - name: "A0"
    ip: "11.0.0.1"
    port: 28080
    mining: true
  - name: "A1"
    ip: "11.0.0.2"
    port: 28080
"#;
        
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert!(config.is_traditional_mode());
        assert!(config.validate().is_ok());
    }
    
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
block_generation:
  interval: 60
  pools_per_round: 1
"#;
        
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert!(config.is_agent_mode());
        assert!(config.validate().is_ok());
    }
    
    #[test]
    fn test_validation_errors() {
        // Test empty nodes
        let yaml = r#"
general:
  stop_time: "1h"
nodes: []
"#;
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert!(config.validate().is_err());
        
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