use std::fs::File;
use serde_yaml;
use std::collections::HashMap;

#[derive(Debug, serde::Deserialize)]
struct UserAgentConfig {
    daemon: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    wallet: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    user_script: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    attributes: Option<HashMap<String, String>>,
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

#[derive(Debug, serde::Deserialize)]
struct AgentDefinitions {
    #[serde(skip_serializing_if = "Option::is_none")]
    user_agents: Option<Vec<UserAgentConfig>>,
}

#[derive(Debug, serde::Deserialize)]
struct Config {
    general: serde_yaml::Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    network: Option<serde_yaml::Value>,
    agents: AgentDefinitions,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Load the configuration
    let file = File::open("config_global_20_agents.yaml")?;
    let config: Config = serde_yaml::from_reader(file)?;

    println!("Loaded configuration successfully");
    println!("Number of user agents: {}", config.agents.user_agents.as_ref().unwrap().len());

    // Check each user agent
    if let Some(user_agents) = &config.agents.user_agents {
        for (i, agent) in user_agents.iter().enumerate() {
            println!("Agent {}: is_miner = {}", i, agent.is_miner_value());
            if let Some(attrs) = &agent.attributes {
                println!("  Attributes: {:?}", attrs);
                if let Some(is_miner_val) = attrs.get("is_miner") {
                    println!("  is_miner attribute value: '{}'", is_miner_val);
                } else {
                    println!("  No is_miner attribute found");
                }
            } else {
                println!("  No attributes found");
            }
        }
    }

    Ok(())
}