//! Binary path resolution and validation utilities.
//!
//! This module handles resolving binary paths from shorthand names or explicit paths,
//! and validating that binaries exist and are executable.

use std::env;
use std::path::{Path, PathBuf};
use std::os::unix::fs::PermissionsExt;

/// Default directory for monerosim binaries
const DEFAULT_BIN_DIR: &str = ".monerosim/bin";

/// Errors that can occur during binary resolution or validation
#[derive(Debug, thiserror::Error)]
pub enum BinaryError {
    #[error("Binary not found: {path}")]
    NotFound { path: String },

    #[error("Binary is not executable: {path}")]
    NotExecutable { path: String },

    #[error("Cannot determine home directory")]
    NoHomeDir,

    #[error("Invalid path: {path}")]
    InvalidPath { path: String },
}

/// Get the user's home directory from the HOME environment variable
fn get_home_dir() -> Result<PathBuf, BinaryError> {
    env::var("HOME")
        .map(PathBuf::from)
        .map_err(|_| BinaryError::NoHomeDir)
}

/// Resolve a binary path from a shorthand name or explicit path.
///
/// Resolution rules:
/// 1. If path contains `/` or starts with `~`: treat as explicit path
/// 2. Otherwise: expand shorthand to `~/.monerosim/bin/{name}`
///
/// The `~` is expanded to the user's home directory.
///
/// # Examples
///
/// ```ignore
/// // Shorthand names
/// resolve_binary_path("monerod") -> ~/.monerosim/bin/monerod
/// resolve_binary_path("monerod-v18") -> ~/.monerosim/bin/monerod-v18
///
/// // Explicit paths (returned as-is with ~ expansion)
/// resolve_binary_path("~/.local/bin/monerod") -> /home/user/.local/bin/monerod
/// resolve_binary_path("/opt/monero/monerod") -> /opt/monero/monerod
/// ```
pub fn resolve_binary_path(name_or_path: &str) -> Result<PathBuf, BinaryError> {
    let home_dir = get_home_dir()?;

    if name_or_path.contains('/') || name_or_path.starts_with('~') {
        // Explicit path - expand ~ if present
        let expanded = if name_or_path.starts_with('~') {
            home_dir.join(&name_or_path[2..]) // Skip "~/"
        } else {
            PathBuf::from(name_or_path)
        };
        Ok(expanded)
    } else {
        // Shorthand name - expand to default bin directory
        Ok(home_dir.join(DEFAULT_BIN_DIR).join(name_or_path))
    }
}

/// Resolve a binary path and return it as a fully-resolved absolute path string.
///
/// All paths are resolved at generation time - no shell variable expansion needed.
pub fn resolve_binary_path_for_shadow(name_or_path: &str) -> Result<String, BinaryError> {
    let home_dir = get_home_dir()?;
    let home_str = home_dir.to_string_lossy();

    if name_or_path.contains('/') || name_or_path.starts_with('~') {
        // Explicit path - resolve ~ to actual home directory
        if name_or_path.starts_with('~') {
            Ok(format!("{}{}", home_str, &name_or_path[1..]))
        } else {
            Ok(name_or_path.to_string())
        }
    } else {
        // Shorthand name - expand to default bin directory with resolved home
        Ok(format!("{}/{}/{}", home_str, DEFAULT_BIN_DIR, name_or_path))
    }
}

/// Validate that a binary exists and is executable.
///
/// This should be called at startup before launching Shadow to catch
/// configuration errors early.
pub fn validate_binary(path: &Path) -> Result<(), BinaryError> {
    if !path.exists() {
        return Err(BinaryError::NotFound {
            path: path.display().to_string(),
        });
    }

    let metadata = path.metadata().map_err(|_| BinaryError::InvalidPath {
        path: path.display().to_string(),
    })?;

    // Check if file is executable (any execute bit set)
    let permissions = metadata.permissions();
    let mode = permissions.mode();
    if mode & 0o111 == 0 {
        return Err(BinaryError::NotExecutable {
            path: path.display().to_string(),
        });
    }

    Ok(())
}

/// Validate a binary specified by name or path.
///
/// Combines resolution and validation in one step.
pub fn validate_binary_spec(name_or_path: &str) -> Result<PathBuf, BinaryError> {
    let resolved = resolve_binary_path(name_or_path)?;
    validate_binary(&resolved)?;
    Ok(resolved)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_resolve_shorthand() {
        let result = resolve_binary_path("monerod").unwrap();
        assert!(result.ends_with(".monerosim/bin/monerod"));
    }

    #[test]
    fn test_resolve_shorthand_with_version() {
        let result = resolve_binary_path("monerod-v18").unwrap();
        assert!(result.ends_with(".monerosim/bin/monerod-v18"));
    }

    #[test]
    fn test_resolve_explicit_tilde() {
        let result = resolve_binary_path("~/.local/bin/monerod").unwrap();
        assert!(result.ends_with(".local/bin/monerod"));
    }

    #[test]
    fn test_resolve_explicit_absolute() {
        let result = resolve_binary_path("/opt/monero/monerod").unwrap();
        assert_eq!(result, PathBuf::from("/opt/monero/monerod"));
    }

    #[test]
    fn test_shadow_path_shorthand() {
        let result = resolve_binary_path_for_shadow("monerod").unwrap();
        // Should resolve to actual home directory, not $HOME
        assert!(result.ends_with("/.monerosim/bin/monerod"));
        assert!(!result.contains("$HOME"));
    }

    #[test]
    fn test_shadow_path_tilde() {
        let result = resolve_binary_path_for_shadow("~/.local/bin/monerod").unwrap();
        assert!(result.ends_with("/.local/bin/monerod"));
        assert!(!result.contains("$HOME"));
        assert!(!result.starts_with('~'));
    }

    #[test]
    fn test_shadow_path_absolute() {
        let result = resolve_binary_path_for_shadow("/opt/monero/monerod").unwrap();
        assert_eq!(result, "/opt/monero/monerod");
    }
}
