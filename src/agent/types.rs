//! Agent type definitions and related data structures for Monerosim.
//!
//! This module contains the core types used for agent processing and lifecycle management.

use serde::{Deserialize, Serialize};

/// Represents the different types of agents in the simulation
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum AgentType {
    /// User agents that run Monero daemons and wallets
    UserAgent,
    /// Pure script agents that run without daemons
    PureScriptAgent,
}

impl AgentType {
    /// Returns a string representation of the agent type
    pub fn as_str(&self) -> &'static str {
        match self {
            AgentType::UserAgent => "user_agent",
            AgentType::PureScriptAgent => "pure_script_agent",
        }
    }
}

/// Configuration for agent processing parameters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentProcessingConfig {
    /// Base offset for IP allocation to avoid conflicts
    pub ip_offset: usize,
    /// Staggered start time increment between agents
    pub start_time_increment: u64,
    /// Default start time for agents
    pub default_start_time: String,
}

impl Default for AgentProcessingConfig {
    fn default() -> Self {
        Self {
            ip_offset: 0,
            start_time_increment: 2,
            default_start_time: "5s".to_string(),
        }
    }
}

/// Result of agent processing operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentProcessingResult {
    /// Number of agents successfully processed
    pub processed_count: usize,
    /// Number of agents that failed processing
    pub failed_count: usize,
    /// List of agent IDs that were processed
    pub processed_agents: Vec<String>,
    /// Any error messages encountered
    pub errors: Vec<String>,
}

impl AgentProcessingResult {
    /// Creates a new successful result
    pub fn success(processed_count: usize, processed_agents: Vec<String>) -> Self {
        Self {
            processed_count,
            failed_count: 0,
            processed_agents,
            errors: Vec::new(),
        }
    }

    /// Creates a new result with failures
    pub fn with_failures(
        processed_count: usize,
        failed_count: usize,
        processed_agents: Vec<String>,
        errors: Vec<String>,
    ) -> Self {
        Self {
            processed_count,
            failed_count,
            processed_agents,
            errors,
        }
    }

    /// Returns true if all agents were processed successfully
    pub fn is_success(&self) -> bool {
        self.failed_count == 0
    }
}
