use crate::config_v2::{Config, ValidationError};
use color_eyre::Result;
use log::{info, warn};
use std::fs::File;
use std::path::Path;

/// Load and parse configuration from a YAML file
pub fn load_config(config_path: &Path) -> Result<Config> {
    info!("Loading configuration from: {:?}", config_path);
    
    // Open the configuration file
    let file = File::open(config_path)?;
    
    // Parse the YAML content
    let config: Config = serde_yaml::from_reader(file)?;
    
    // Log that we're using agent mode
    info!("Detected agent-based configuration");
    
    // Validate the configuration
    config.validate()?;
    
    Ok(config)
}

/// CLI arguments for agent mode that can override YAML settings
#[derive(Debug, Clone)]
pub struct AgentCliOverrides {
    pub users: Option<u32>,
    pub tx_frequency: Option<f64>,
}

/// Apply CLI overrides to an agent configuration
pub fn apply_agent_overrides(
    config: &mut Config,
    overrides: &AgentCliOverrides,
) -> Result<()> {
    // Apply user count override
    if let Some(users) = overrides.users {
        info!("User count override is no longer supported in the new configuration format");
        // The new format doesn't have a simple count field, so we can't apply this override
    }
    
    // Apply transaction frequency override
    if let Some(tx_freq) = overrides.tx_frequency {
        info!("Transaction frequency override is no longer supported in the new configuration format");
        // The new format doesn't have a simple transaction_interval field, so we can't apply this override
    }
    
    // Re-validate after applying overrides
    config.validate()?;
    
    Ok(())
}

/// Check if a configuration file exists and warn about deprecated formats
pub fn check_config_compatibility(config_path: &Path) -> Result<()> {
    let content = std::fs::read_to_string(config_path)?;
    
    // Check for dummy nodes workaround
    if content.contains("# Dummy nodes section") || 
       (content.contains("nodes:") && content.contains("agents:")) {
        warn!("Configuration uses deprecated dummy nodes workaround. \
              This will be removed in a future version. \
              Please update to the new format.");
    }
    
    // Check for old-style agent configs that won't parse
    if content.contains("agents:") && !content.contains("nodes:") {
        // This is likely a medium/large config that needs migration
        info!("This appears to be an agent configuration without nodes section. \
              The new parser will handle this correctly.");
    }
    
    Ok(())
}

/// Migrate an old configuration to the new format
pub fn migrate_config(old_config_path: &Path, new_config_path: &Path) -> Result<()> {
    info!("Migrating configuration from {:?} to {:?}", old_config_path, new_config_path);
    
    let content = std::fs::read_to_string(old_config_path)?;
    
    // Check if it's an old agent config with dummy nodes
    if content.contains("# Dummy nodes section") {
        // Remove the dummy nodes section
        let lines: Vec<&str> = content.lines().collect();
        let mut new_lines = Vec::new();
        let mut skip_nodes = false;
        
        for line in lines {
            if line.contains("# Dummy nodes section") || line.trim() == "nodes:" {
                skip_nodes = true;
                continue;
            }
            
            if skip_nodes && !line.starts_with(' ') && !line.starts_with('\t') {
                skip_nodes = false;
            }
            
            if !skip_nodes {
                new_lines.push(line);
            }
        }
        
        let new_content = new_lines.join("\n");
        std::fs::write(new_config_path, new_content)?;
        info!("Migration complete: removed dummy nodes section");
    } else {
        // For other configs, just copy as-is
        std::fs::copy(old_config_path, new_config_path)?;
        info!("Migration complete: configuration was already compatible");
    }
    
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;
    
    #[test]
    fn test_load_agent_config() {
        let yaml = r#"
general:
  stop_time: "30m"
network:
  type: "1_gbit_switch"
agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "regular_user.py"
"#;
        
        let mut temp_file = NamedTempFile::new().unwrap();
        write!(temp_file, "{}", yaml).unwrap();
        
        let config = load_config(temp_file.path()).unwrap();
        assert!(config.is_agent_mode());
    }
    
    #[test]
    fn test_apply_overrides() {
        let yaml = r#"
general:
  stop_time: "30m"
network:
  type: "1_gbit_switch"
agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "regular_user.py"
"#;
        
        let mut temp_file = NamedTempFile::new().unwrap();
        write!(temp_file, "{}", yaml).unwrap();
        
        let mut config = load_config(temp_file.path()).unwrap();
        
        let overrides = AgentCliOverrides {
            users: Some(50),
            tx_frequency: Some(0.5),
        };
        
        // This should not fail, but the overrides won't have any effect
        apply_agent_overrides(&mut config, &overrides).unwrap();
    }
}