//! Configuration validation error types.

/// Errors from phase validation
#[derive(Debug, thiserror::Error)]
pub enum PhaseValidationError {
    #[error("Non-sequential phase numbering for {phase_type}: expected {expected}, found {found}")]
    NonSequentialPhases {
        expected: u32,
        found: u32,
        phase_type: String,
    },

    #[error("Missing path for {phase_type} phase {phase_num}")]
    MissingPath {
        phase_num: u32,
        phase_type: String,
    },

    #[error("Missing timing for {phase_type} phase {phase_num}: {detail}")]
    MissingTiming {
        phase_num: u32,
        phase_type: String,
        detail: String,
    },

    #[error("Mixed configuration for {phase_type}: {detail}")]
    MixedConfig {
        phase_type: String,
        detail: String,
    },

    #[error("Insufficient gap between {phase_type} phases {phase_num} and {next_phase_num}: stop={stop_time}, start={start_time}, need at least {min_gap}s gap")]
    GapTooSmall {
        phase_type: String,
        phase_num: u32,
        next_phase_num: u32,
        stop_time: String,
        start_time: String,
        min_gap: u64,
    },

    #[error("Invalid duration format for {phase_type} phase {phase_num}: {detail}")]
    InvalidDuration {
        phase_type: String,
        phase_num: u32,
        detail: String,
    },
}

/// Configuration validation errors
#[derive(Debug, thiserror::Error)]
pub enum ValidationError {
    #[error("Invalid agent configuration: {0}")]
    InvalidAgent(String),
    #[error("Invalid general configuration: {0}")]
    InvalidGeneral(String),
    #[error("Invalid network configuration: {0}")]
    InvalidNetwork(String),
}
