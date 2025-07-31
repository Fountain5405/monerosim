use serde::{Deserialize, Serialize};

/// Configuration for the mining simulation
#[derive(Debug, Serialize, Deserialize)]
pub struct MiningConfig {
    /// Target block time in seconds
    pub block_time: u64,
    /// Number of nodes that will be selected to mine
    pub number_of_mining_nodes: u32,
    /// Hashrate distribution among the mining nodes
    pub mining_distribution: Vec<u32>,
    /// Percentage of hashrate below which a miner is considered a "solo miner"
    pub solo_miner_threshold: f64,
}

/// Top-level configuration structure that mirrors the YAML configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct Config {
    /// General simulation configuration
    pub general: General,
    /// Individual node configurations
    pub nodes: Vec<NodeConfig>,
    /// (Optional) Mining simulation configuration
    #[serde(default)]
    pub mining: Option<MiningConfig>,
}

impl Config {
    /// Validates the configuration
    pub fn validate(&self) -> Result<(), String> {
        if let Some(mining_config) = &self.mining {
            if mining_config.mining_distribution.len() != mining_config.number_of_mining_nodes as usize {
                return Err(format!(
                    "The length of 'mining_distribution' ({}) must match 'number_of_mining_nodes' ({})",
                    mining_config.mining_distribution.len(),
                    mining_config.number_of_mining_nodes
                ));
            }
        }
        Ok(())
    }
}

/// General configuration settings for the simulation
#[derive(Debug, Serialize, Deserialize)]
pub struct General {
    /// Simulation stop time (e.g., "1h", "30m", "3600s")
    pub stop_time: String,
    /// Start with fresh blockchain (clears existing data)
    pub fresh_blockchain: Option<bool>,
    /// (Optional) Absolute path to the Python virtual environment
    pub python_venv: Option<String>,
}

/// Configuration for a single Monero node
#[derive(Debug, Serialize, Deserialize)]
pub struct NodeConfig {
    /// Name of this node
    pub name: String,
    /// IP address for this node
    pub ip: String,
    /// Port for this node
    pub port: u32,
    /// (Optional) Start time for this node (default: "10s")
    pub start_time: Option<String>,
    /// (Optional) Whether this node should mine (default: false)
    pub mining: Option<bool>,
    /// (Optional) Fixed difficulty for mining (default: none)
    pub fixed_difficulty: Option<u32>,
}

/// Legacy node type structure for backwards compatibility
#[derive(Debug, Serialize, Deserialize)]
pub struct NodeType {
    /// Number of nodes of this type
    pub count: u32,
    /// Name of this node type/group
    pub name: String,
    /// (Optional) Commit, tag, or branch to use as the base for this node type
    pub base_commit: Option<String>,
    /// (Optional) List of patch files to apply
    pub patches: Option<Vec<String>>,
    /// (Optional) Name of another node type to use as the base
    pub base: Option<String>,
    /// (Optional) List of PR numbers to merge
    pub prs: Option<Vec<u32>>,
}

/// Legacy Monero configuration for backwards compatibility
#[derive(Debug, Serialize, Deserialize)]
pub struct Monero {
    /// List of Monero node types/groups to simulate
    pub nodes: Vec<NodeType>,
}

/// Default implementation for General
impl Default for General {
    fn default() -> Self {
        Self {
            stop_time: "1h".to_string(),
            fresh_blockchain: None,
            python_venv: None,
        }
    }
}

/// Default implementation for NodeConfig
impl Default for NodeConfig {
    fn default() -> Self {
        Self {
            name: "A0".to_string(),
            ip: "11.0.0.1".to_string(),
            port: 28080,
            start_time: Some("10s".to_string()),
            mining: Some(false),
            fixed_difficulty: None,
        }
    }
}

/// Default implementation for Config
impl Default for Config {
    fn default() -> Self {
        Self {
            general: General::default(),
            nodes: vec![
                NodeConfig {
                    name: "A0".to_string(),
                    ip: "11.0.0.1".to_string(),
                    port: 28080,
                    start_time: Some("10s".to_string()),
                    mining: Some(true),
                    fixed_difficulty: Some(200),
                },
                NodeConfig {
                    name: "A1".to_string(),
                    ip: "11.0.0.2".to_string(),
                    port: 28080,
                    start_time: Some("120s".to_string()),
                    mining: Some(false),
                    fixed_difficulty: None,
                },
            ],
            mining: None,
        }
    }
}