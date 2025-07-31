use crate::config::{Config as OldConfig, General, NodeConfig};
use crate::config_v2::{Config as NewConfig, TraditionalConfig, GeneralConfig};
use color_eyre::Result;
use log::{info, warn};

/// Convert new config format to old format for backward compatibility
pub fn convert_to_old_format(new_config: &NewConfig) -> Result<OldConfig> {
    match new_config {
        NewConfig::Traditional(trad_config) => {
            // Direct conversion for traditional configs
            Ok(OldConfig {
                general: General {
                    stop_time: trad_config.general.stop_time.clone(),
                    fresh_blockchain: trad_config.general.fresh_blockchain,
                    python_venv: trad_config.general.python_venv.clone(),
                },
                nodes: vec![],
                mining: None,
            })
        }
        NewConfig::Agent(agent_config) => {
            // For agent configs, create a minimal traditional config
            // This is used when --agents flag forces agent mode
            warn!("Converting agent configuration to traditional format for compatibility");
            
            Ok(OldConfig {
                general: General {
                    stop_time: agent_config.general.stop_time.clone(),
                    fresh_blockchain: agent_config.general.fresh_blockchain,
                    python_venv: agent_config.general.python_venv.clone(),
                },
                nodes: vec![],
                mining: None,
            })
        }
    }
}

/// Extract agent configuration from the new config format
pub fn extract_agent_config(new_config: &NewConfig) -> Option<crate::shadow_agents::AgentConfig> {
    if let NewConfig::Agent(agent_config) = new_config {
        // Convert transaction interval to frequency
        let tx_frequency = if let Some(interval) = agent_config.agents.regular_users.transaction_interval {
            60.0 / interval as f64
        } else {
            0.1 // default
        };
        
        Some(crate::shadow_agents::AgentConfig {
            regular_users: agent_config.agents.regular_users.count,
            marketplaces: agent_config.agents.marketplaces.count,
            mining_pools: agent_config.agents.mining_pools.count,
            transaction_frequency: tx_frequency,
            min_transaction_amount: agent_config.agents.regular_users.min_transaction_amount.unwrap_or(0.1),
            max_transaction_amount: agent_config.agents.regular_users.max_transaction_amount.unwrap_or(1.0),
        })
    } else {
        None
    }
}

/// Check if we should use agent mode based on config and CLI flags
pub fn should_use_agent_mode(config: &NewConfig, force_agents: bool) -> bool {
    config.is_agent_mode() || force_agents
}

/// Create a default agent configuration when forced via CLI
pub fn create_default_agent_config() -> crate::shadow_agents::AgentConfig {
    crate::shadow_agents::AgentConfig {
        regular_users: 10,
        marketplaces: 2,
        mining_pools: 2,
        transaction_frequency: 0.1,
        min_transaction_amount: 0.1,
        max_transaction_amount: 1.0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config_v2::{AgentConfig, AgentDefinitions, RegularUserConfig, MarketplaceConfig, MiningPoolConfig};
    
    #[test]
    fn test_traditional_conversion() {
        let new_config = NewConfig::Traditional(TraditionalConfig {
            general: GeneralConfig {
                stop_time: "3h".to_string(),
                fresh_blockchain: Some(true),
                python_venv: None,
                log_level: None,
            },
            nodes: vec![
                crate::config_v2::NodeConfig {
                    name: "A0".to_string(),
                    ip: "11.0.0.1".to_string(),
                    port: 28080,
                    start_time: Some("0s".to_string()),
                    mining: Some(true),
                    fixed_difficulty: Some(1),
                },
            ],
        });
        
        let old_config = convert_to_old_format(&new_config).unwrap();
        assert_eq!(old_config.general.stop_time, "3h");
        assert_eq!(old_config.nodes.len(), 1);
        assert_eq!(old_config.nodes[0].name, "A0");
    }
    
    #[test]
    fn test_agent_conversion() {
        let new_config = NewConfig::Agent(AgentConfig {
            general: GeneralConfig {
                stop_time: "30m".to_string(),
                fresh_blockchain: Some(true),
                python_venv: None,
                log_level: Some("info".to_string()),
            },
            network: None,
            agents: AgentDefinitions {
                regular_users: RegularUserConfig {
                    count: 10,
                    transaction_interval: Some(60),
                    min_transaction_amount: Some(0.1),
                    max_transaction_amount: Some(5.0),
                    wallet_settings: None,
                },
                marketplaces: MarketplaceConfig {
                    count: 3,
                    payment_processing_delay: None,
                    wallet_settings: None,
                },
                mining_pools: MiningPoolConfig {
                    count: 2,
                    mining_threads: None,
                    pool_fee: None,
                },
                custom_agents: None,
            },
            block_generation: None,
        });
        
        let old_config = convert_to_old_format(&new_config).unwrap();
        assert_eq!(old_config.general.stop_time, "30m");
        assert_eq!(old_config.nodes.len(), 2); // dummy nodes
        
        let agent_config = extract_agent_config(&new_config).unwrap();
        assert_eq!(agent_config.regular_users, 10);
        assert_eq!(agent_config.marketplaces, 3);
        assert_eq!(agent_config.mining_pools, 2);
        assert_eq!(agent_config.transaction_frequency, 1.0); // 60/60
    }
}