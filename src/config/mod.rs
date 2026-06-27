//! Configuration data model, defaults, and validation.
//!
//! This module is split across several files for separation of concerns:
//!
//! - `types`: top-level configuration data structures (`Config`,
//!   `GeneralConfig`, `Network`, peer/topology/distribution enums,
//!   `DaemonConfig`, `AgentDefinitions`, etc.)
//! - `agent_config`: per-agent configuration (`AgentConfig`, `OptionValue`)
//!   plus its custom `Deserialize` impl and the flat-phase-field parser.
//! - `phases`: `DaemonPhase`, `WalletPhase`, and `MIN_PHASE_GAP_SECONDS`.
//! - `defaults`: serde `default = "..."` value functions.
//! - `validation`: phase-validation logic (`validate_daemon_phases`).
//! - `errors`: `PhaseValidationError` and `ValidationError`.
//!
//! All previously-public items are re-exported below so callers can keep
//! using `use crate::config::SomeType;` unchanged.

mod agent_config;
mod defaults;
mod errors;
mod phases;
mod types;
mod validation;

pub use agent_config::{AgentConfig, OptionValue};
pub use errors::{PhaseValidationError, ValidationError};
pub use phases::{DaemonPhase, WalletPhase, MIN_PHASE_GAP_SECONDS};
pub use types::{
    AgentDefinitions, TurnoverConfig, Config, DaemonConfig, DaemonSelectionStrategy, Distribution,
    DistributionStrategy, FallbackSeedsMode, GeneralConfig, Network, PeerMode,
    PerformanceConfig, RegionWeights, Topology,
};
pub use validation::validate_daemon_phases;
