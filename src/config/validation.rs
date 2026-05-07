//! Phase validation logic for daemon upgrade scenarios.

use std::collections::BTreeMap;

use crate::utils::duration::parse_duration_to_seconds;

use super::errors::PhaseValidationError;
use super::phases::{DaemonPhase, MIN_PHASE_GAP_SECONDS};

/// Validate daemon phases for an agent, ensuring sufficient gaps between phases.
/// Returns Ok(()) if valid, or an error describing the validation failure.
pub fn validate_daemon_phases(
    agent_id: &str,
    phases: &BTreeMap<u32, DaemonPhase>,
) -> Result<(), PhaseValidationError> {
    let phase_nums: Vec<u32> = phases.keys().copied().collect();

    // Check sequential numbering
    for (i, &phase_num) in phase_nums.iter().enumerate() {
        if phase_num != i as u32 {
            return Err(PhaseValidationError::NonSequentialPhases {
                expected: i as u32,
                found: phase_num,
                phase_type: format!("daemon (agent {})", agent_id),
            });
        }
    }

    // Check each phase has required fields and validate gaps
    for (i, (&phase_num, phase)) in phases.iter().enumerate() {
        // Check path is not empty
        if phase.path.is_empty() {
            return Err(PhaseValidationError::MissingPath {
                phase_num,
                phase_type: format!("daemon (agent {})", agent_id),
            });
        }

        // Check start time exists
        if phase.start.is_none() {
            return Err(PhaseValidationError::MissingTiming {
                phase_num,
                phase_type: format!("daemon (agent {})", agent_id),
                detail: "missing start time".to_string(),
            });
        }

        // For non-final phases, check stop time and gap to next phase
        if i < phases.len() - 1 {
            let next_phase_num = phase_nums[i + 1];
            let next_phase = &phases[&next_phase_num];

            // Current phase needs stop time
            let stop_time = match &phase.stop {
                Some(t) => t,
                None => {
                    return Err(PhaseValidationError::MissingTiming {
                        phase_num,
                        phase_type: format!("daemon (agent {})", agent_id),
                        detail: "non-final phase must have stop time".to_string(),
                    });
                }
            };

            // Next phase needs start time
            let next_start_time = match &next_phase.start {
                Some(t) => t,
                None => {
                    return Err(PhaseValidationError::MissingTiming {
                        phase_num: next_phase_num,
                        phase_type: format!("daemon (agent {})", agent_id),
                        detail: "missing start time".to_string(),
                    });
                }
            };

            // Parse and compare times
            let stop_seconds = parse_duration_to_seconds(stop_time).map_err(|e| {
                PhaseValidationError::InvalidDuration {
                    phase_type: format!("daemon (agent {})", agent_id),
                    phase_num,
                    detail: format!("stop time: {}", e),
                }
            })?;

            let start_seconds = parse_duration_to_seconds(next_start_time).map_err(|e| {
                PhaseValidationError::InvalidDuration {
                    phase_type: format!("daemon (agent {})", agent_id),
                    phase_num: next_phase_num,
                    detail: format!("start time: {}", e),
                }
            })?;

            // Check gap is sufficient
            if start_seconds < stop_seconds + MIN_PHASE_GAP_SECONDS {
                return Err(PhaseValidationError::GapTooSmall {
                    phase_type: format!("daemon (agent {})", agent_id),
                    phase_num,
                    next_phase_num,
                    stop_time: stop_time.clone(),
                    start_time: next_start_time.clone(),
                    min_gap: MIN_PHASE_GAP_SECONDS,
                });
            }
        }
    }

    Ok(())
}
