//! Wrapper script generation utilities.
//!
//! Provides a function to write a wrapper script to disk and create
//! a single ShadowProcess that executes it, replacing the old two-process
//! heredoc pattern (Process 1: create script, Process 2: execute it).

use crate::shadow::ShadowProcess;
use std::collections::BTreeMap;
use std::path::Path;

/// Write a wrapper script to the scripts directory and return a single
/// ShadowProcess that executes it.
///
/// # Parameters
/// - `scripts_dir`: Directory where scripts are written (must already exist)
/// - `script_name`: Filename for the script (e.g., "agent_miner001_wrapper.sh")
/// - `content`: The bash script content
/// - `environment`: Environment variables for the process
/// - `start_time`: When the process should start (e.g., "65s")
/// - `shutdown_time`: Optional shutdown time
/// - `expected_final_state`: Optional expected final state
pub fn write_wrapper_script(
    scripts_dir: &Path,
    script_name: &str,
    content: &str,
    environment: &BTreeMap<String, String>,
    start_time: String,
    shutdown_time: Option<String>,
    expected_final_state: Option<crate::shadow::ExpectedFinalState>,
) -> color_eyre::eyre::Result<ShadowProcess> {
    let script_path = scripts_dir.join(script_name);
    std::fs::write(&script_path, content)
        .map_err(|e| color_eyre::eyre::eyre!("Failed to write script {:?}: {}", script_path, e))?;

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = std::fs::metadata(&script_path)?.permissions();
        perms.set_mode(0o755);
        std::fs::set_permissions(&script_path, perms)?;
    }

    Ok(ShadowProcess {
        path: "/bin/bash".to_string(),
        args: script_path.to_string_lossy().to_string(),
        environment: environment.clone(),
        start_time,
        shutdown_time,
        expected_final_state,
    })
}
