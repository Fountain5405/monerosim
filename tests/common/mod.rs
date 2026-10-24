//! Helpers shared by the orchestrator golden-file tests.
#![allow(dead_code)]

use regex::Regex;

/// Replace the machine-specific parts of generated YAML so it can be compared
/// with a committed golden file. The repo root is the test's working directory.
pub fn normalize(yaml: &str) -> String {
    let cwd = std::env::current_dir()
        .unwrap()
        .to_string_lossy()
        .to_string();
    let home = std::env::var("HOME").unwrap_or_default();
    normalize_paths(yaml, &cwd, &home)
}

/// `normalize` with the repo root and home directory passed in.
pub fn normalize_paths(yaml: &str, repo_root: &str, home: &str) -> String {
    // The repo's absolute path embeds in wrapper script / data-dir paths. It
    // goes first: a checkout can itself sit under /tmp (a scratch worktree),
    // and the tempdir pattern below would otherwise eat its prefix.
    let yaml = yaml.replace(repo_root, "REPO_ROOT");
    // /tmp/<random>/ tempdirs from the test run.
    let yaml = Regex::new(r"/tmp/[A-Za-z0-9_.-]+/")
        .unwrap()
        .replace_all(&yaml, "TMPDIR/")
        .into_owned();
    // The venv's Python version (python3.N, or bare python3 without a venv).
    let yaml = Regex::new(r"venv/lib/python3(\.\d+)?/site-packages")
        .unwrap()
        .replace_all(&yaml, "venv/lib/python3.X/site-packages")
        .into_owned();
    // The user's $HOME embeds in resolved monerod / wallet paths.
    if home.is_empty() {
        return yaml;
    }
    yaml.replace(home, "HOME")
}
