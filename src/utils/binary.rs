//! Binary path resolution and validation utilities.
//!
//! This module handles resolving binary paths from shorthand names or explicit paths,
//! and validating that binaries exist and are executable.

use std::env;
use std::path::PathBuf;

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

    if let Some(rest) = name_or_path.strip_prefix("~/") {
        // Explicit path with home-dir expansion
        Ok(home_dir.join(rest))
    } else if name_or_path.starts_with('~') {
        // Bare "~" or "~user" - unsupported (no username expansion)
        Err(BinaryError::InvalidPath {
            path: name_or_path.to_string(),
        })
    } else if name_or_path.contains('/') {
        // Explicit path, no expansion needed
        Ok(PathBuf::from(name_or_path))
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

    if let Some(rest) = name_or_path.strip_prefix("~/") {
        // Explicit path - resolve ~ to actual home directory
        Ok(format!("{}/{}", home_str, rest))
    } else if name_or_path.starts_with('~') {
        // Bare "~" or "~user" - unsupported (no username expansion)
        Err(BinaryError::InvalidPath {
            path: name_or_path.to_string(),
        })
    } else if name_or_path.contains('/') {
        // Explicit path, already absolute or relative - use as-is
        Ok(name_or_path.to_string())
    } else {
        // Shorthand name - expand to default bin directory with resolved home
        Ok(format!("{}/{}/{}", home_str, DEFAULT_BIN_DIR, name_or_path))
    }
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

    #[test]
    fn test_resolve_bare_tilde_is_error() {
        // Bare "~" and "~user" are malformed (no username expansion support)
        // and must not panic via out-of-bounds slicing.
        assert!(matches!(
            resolve_binary_path("~"),
            Err(BinaryError::InvalidPath { .. })
        ));
        assert!(matches!(
            resolve_binary_path("~monerod"),
            Err(BinaryError::InvalidPath { .. })
        ));
        assert!(matches!(
            resolve_binary_path_for_shadow("~"),
            Err(BinaryError::InvalidPath { .. })
        ));
        assert!(matches!(
            resolve_binary_path_for_shadow("~monerod"),
            Err(BinaryError::InvalidPath { .. })
        ));
    }
}
