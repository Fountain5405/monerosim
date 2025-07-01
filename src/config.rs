use serde::{Deserialize, Serialize};

/// Top-level configuration structure that mirrors the YAML configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct Config {
    /// General simulation configuration
    pub general: General,
    /// Monero-specific configuration
    pub monero: Monero,
}

/// General configuration settings for the simulation
#[derive(Debug, Serialize, Deserialize)]
pub struct General {
    /// Simulation stop time (e.g., "1h", "30m", "3600s")
    pub stop_time: String,
}

/// Monero-specific configuration settings
#[derive(Debug, Serialize, Deserialize)]
pub struct Monero {
    /// List of Monero node types/groups to simulate
    pub nodes: Vec<NodeType>,
}

/// Configuration for a single Monero node type/group
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

/// Default implementation for General
impl Default for General {
    fn default() -> Self {
        Self {
            stop_time: "1h".to_string(),
        }
    }
}

/// Default implementation for Monero
impl Default for Monero {
    fn default() -> Self {
        Self {
            nodes: vec![
                NodeType {
                    count: 5,
                    name: "A".to_string(),
                    base_commit: Some("v0.18.3.1".to_string()),
                    patches: Some(vec!["patches/testnet_from_scratch.patch".to_string()]),
                    base: None,
                    prs: None,
                },
                NodeType {
                    count: 3,
                    name: "B".to_string(),
                    base_commit: None,
                    patches: None,
                    base: Some("A".to_string()),
                    prs: Some(vec![1234]),
                },
            ],
        }
    }
}

/// Default implementation for NodeType
impl Default for NodeType {
    fn default() -> Self {
        Self {
            count: 1,
            name: "A".to_string(),
            base_commit: Some("v0.18.3.1".to_string()),
            patches: None,
            base: None,
            prs: None,
        }
    }
}

/// Default implementation for Config
impl Default for Config {
    fn default() -> Self {
        Self {
            general: General::default(),
            monero: Monero::default(),
        }
    }
} 