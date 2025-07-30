#[cfg(test)]
mod tests {
    use crate::config_v2::*;
    use crate::config_loader::*;
    use crate::config_compat::*;
    use std::io::Write;
    use tempfile::NamedTempFile;
    
    #[test]
    fn test_parse_traditional_config() {
        let yaml = r#"
general:
  stop_time: "3h"
  fresh_blockchain: true
  python_venv: "/path/to/venv"
nodes:
  - name: "A0"
    ip: "11.0.0.1"
    port: 28080
    mining: true
    fixed_difficulty: 1
  - name: "A1"
    ip: "11.0.0.2"
    port: 28080
"#;
        
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert!(matches!(config, Config::Traditional(_)));
        assert!(config.is_traditional_mode());
        assert!(!config.is_agent_mode());
        
        // Validate the config
        assert!(config.validate().is_ok());
        
        // Check general settings
        assert_eq!(config.general().stop_time, "3h");
        assert_eq!(config.general().fresh_blockchain, Some(true));
    }
    
    #[test]
    fn test_parse_agent_config() {
        let yaml = r#"
general:
  stop_time: "30m"
  log_level: info
agents:
  regular_users:
    count: 10
    transaction_interval: 60
    min_transaction_amount: 0.1
    max_transaction_amount: 5.0
  marketplaces:
    count: 3
    payment_processing_delay: 5
  mining_pools:
    count: 2
    mining_threads: 1
block_generation:
  interval: 60
  pools_per_round: 1
"#;
        
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert!(matches!(config, Config::Agent(_)));
        assert!(config.is_agent_mode());
        assert!(!config.is_traditional_mode());
        
        // Validate the config
        assert!(config.validate().is_ok());
        
        // Extract agent config
        if let Config::Agent(agent_cfg) = &config {
            assert_eq!(agent_cfg.agents.regular_users.count, 10);
            assert_eq!(agent_cfg.agents.marketplaces.count, 3);
            assert_eq!(agent_cfg.agents.mining_pools.count, 2);
        }
    }
    
    #[test]
    fn test_validation_errors() {
        // Test no nodes in traditional config
        let yaml = r#"
general:
  stop_time: "1h"
nodes: []
"#;
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        let result = config.validate();
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("At least one node"));
        
        // Test zero users in agent config
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
        let result = config.validate();
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("must be greater than 0"));
        
        // Test invalid transaction amounts
        let yaml = r#"
general:
  stop_time: "1h"
agents:
  regular_users:
    count: 10
    min_transaction_amount: 5.0
    max_transaction_amount: 1.0
  marketplaces:
    count: 1
  mining_pools:
    count: 1
"#;
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        let result = config.validate();
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("cannot be greater than max"));
    }
    
    #[test]
    fn test_cli_overrides() {
        let yaml = r#"
general:
  stop_time: "30m"
agents:
  regular_users:
    count: 10
  marketplaces:
    count: 3
  mining_pools:
    count: 2
"#;
        
        let mut temp_file = NamedTempFile::new().unwrap();
        write!(temp_file, "{}", yaml).unwrap();
        
        let mut config = load_config(temp_file.path()).unwrap();
        
        let overrides = AgentCliOverrides {
            users: Some(50),
            marketplaces: Some(5),
            pools: None,
            tx_frequency: Some(0.5),
        };
        
        apply_agent_overrides(&mut config, &overrides).unwrap();
        
        if let Config::Agent(agent_cfg) = config {
            assert_eq!(agent_cfg.agents.regular_users.count, 50);
            assert_eq!(agent_cfg.agents.marketplaces.count, 5);
            assert_eq!(agent_cfg.agents.mining_pools.count, 2); // unchanged
            assert_eq!(agent_cfg.agents.regular_users.transaction_interval, Some(120)); // 60/0.5
        }
    }
    
    #[test]
    fn test_compatibility_conversion() {
        // Test traditional config conversion
        let new_config = Config::Traditional(TraditionalConfig {
            general: GeneralConfig {
                stop_time: "3h".to_string(),
                fresh_blockchain: Some(true),
                python_venv: Some("/path/to/venv".to_string()),
                log_level: None,
            },
            nodes: vec![
                NodeConfig {
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
        
        // Test agent config conversion
        let new_config = Config::Agent(AgentConfig {
            general: GeneralConfig::default(),
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
        assert_eq!(old_config.nodes.len(), 2); // dummy nodes created
        
        let agent_config = extract_agent_config(&new_config).unwrap();
        assert_eq!(agent_config.regular_users, 10);
        assert_eq!(agent_config.transaction_frequency, 1.0); // 60/60
    }
    
    #[test]
    fn test_migration() {
        // Test migrating config with dummy nodes
        let old_yaml = r#"# Small-scale agent-based simulation configuration
# 2 regular users, 1 marketplace, 1 mining pool

general:
  stop_time: 600s
  fresh_blockchain: true
  
# Dummy nodes section (required by parser but ignored in agent mode)
nodes:
  - name: dummy
    ip: 11.0.0.1
    port: 28080

agents:
  regular_users:
    count: 2
"#;
        
        let mut input_file = NamedTempFile::new().unwrap();
        write!(input_file, "{}", old_yaml).unwrap();
        
        let output_file = NamedTempFile::new().unwrap();
        
        migrate_config(input_file.path(), output_file.path()).unwrap();
        
        let migrated_content = std::fs::read_to_string(output_file.path()).unwrap();
        assert!(!migrated_content.contains("# Dummy nodes section"));
        assert!(!migrated_content.contains("nodes:"));
        assert!(migrated_content.contains("agents:"));
    }
    
    #[test]
    fn test_mode_detection() {
        let trad_config = Config::Traditional(TraditionalConfig {
            general: GeneralConfig::default(),
            nodes: vec![NodeConfig::default()],
        });
        
        assert!(!should_use_agent_mode(&trad_config, false));
        assert!(should_use_agent_mode(&trad_config, true)); // force agent mode
        
        let agent_config = Config::Agent(AgentConfig {
            general: GeneralConfig::default(),
            network: None,
            agents: AgentDefinitions {
                regular_users: RegularUserConfig::default(),
                marketplaces: MarketplaceConfig::default(),
                mining_pools: MiningPoolConfig::default(),
                custom_agents: None,
            },
            block_generation: None,
        });
        
        assert!(should_use_agent_mode(&agent_config, false));
        assert!(should_use_agent_mode(&agent_config, true));
    }
    
    #[test]
    fn test_network_config() {
        let yaml = r#"
general:
  stop_time: "30m"
network:
  type: "1_gbit_switch"
  bandwidth: "1Gbps"
  latency: "10ms"
agents:
  regular_users:
    count: 10
  marketplaces:
    count: 3
  mining_pools:
    count: 2
"#;
        
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        if let Config::Agent(agent_cfg) = config {
            assert!(agent_cfg.network.is_some());
            let network = agent_cfg.network.unwrap();
            assert_eq!(network.network_type, "1_gbit_switch");
            assert_eq!(network.bandwidth, Some("1Gbps".to_string()));
            assert_eq!(network.latency, Some("10ms".to_string()));
        } else {
            panic!("Expected agent config");
        }
    }
    
    #[test]
    fn test_block_generation_validation() {
        let yaml = r#"
general:
  stop_time: "30m"
agents:
  regular_users:
    count: 10
  marketplaces:
    count: 3
  mining_pools:
    count: 2
block_generation:
  interval: 20  # Too short
  pools_per_round: 3  # More than available pools
"#;
        
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        let result = config.validate();
        assert!(result.is_err());
        let err_msg = result.unwrap_err().to_string();
        assert!(err_msg.contains("at least 30 seconds"));
    }
}