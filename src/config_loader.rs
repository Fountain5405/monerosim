use crate::config_v2::Config;
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
