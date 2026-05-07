use crate::config_v2::{Config, validate_daemon_phases};
use crate::utils::validation::{validate_mining_config, validate_agent_daemon_config};
use color_eyre::Result;
use color_eyre::eyre::eyre;
use log::info;
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

    // Validate the configuration structure
    config.validate()?;

    // Validate agent configurations
    validate_agent_daemon_config(&config.agents.agents)
        .map_err(|e| eyre!("Agent configuration error: {}", e))?;

    validate_mining_config(&config.agents.agents)
        .map_err(|e| eyre!("Mining configuration error: {}", e))?;

    // Validate daemon phase timing for agents with phases
    for (agent_id, agent_config) in &config.agents.agents {
        if let Some(phases) = &agent_config.daemon_phases {
            if !phases.is_empty() {
                validate_daemon_phases(agent_id, phases)
                    .map_err(|e| eyre!("Phase configuration error: {}", e))?;
            }
        }
    }

    info!("Configuration validated successfully");

    Ok(config)
}
