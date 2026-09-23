//! Resolve a run directory and its `run_env.sh` breadcrumb for post-hoc,
//! read-only tools (`tx_analyzer`, ad-hoc analysis scripts) that need to
//! locate a run's `shared_dir` / `daemon_data_dir` *after* the run has
//! finished.
//!
//! Since 1b885af6, `shared_dir()` / `default_daemon_data_dir()` (in the
//! crate root) mint a fresh, empty per-process `/tmp` namespace whenever the
//! `MONEROSIM_*` env vars are unset — the right behaviour for a *new* run,
//! but wrong for a tool inspecting an *existing* one: it would silently look
//! in a directory nothing ever wrote to. Post-hoc tools must instead follow
//! the run-dir contract documented in `docs/20260904_per_run_directories.md`
//! and implemented for shell/Python tooling in `scripts/run_dir_lib.sh` /
//! `scripts/run_dirs.py` (keep this module in sync with those):
//!
//! 1. an explicit path given by the caller;
//! 2. `--run-dir <path>` / `$MONEROSIM_RUN_DIR`;
//! 3. the newest run directory under the archive base
//!    (`$MONEROSIM_ARCHIVE_BASE`, default `archived_runs`);
//! 4. otherwise, fail with a message naming all three options.
//!
//! Once a run directory is known, its `shadow_output/run_env.sh` breadcrumb
//! (written by `run_sim.sh`, see `run_env.sh` near line 1053) holds the
//! actual `MONEROSIM_SHARED_DIR` / `MONEROSIM_DAEMON_DATA_DIR` paths that run
//! used, even though those env vars aren't set in the *current* process.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

/// `run_sim.sh` exports this to its own children; a caller with it set is
/// pointing us at a specific live or archived run.
pub const RUN_DIR_ENV: &str = "MONEROSIM_RUN_DIR";
/// Overrides the default `archived_runs` base when hunting for the newest run.
pub const ARCHIVE_BASE_ENV: &str = "MONEROSIM_ARCHIVE_BASE";
/// Path of the breadcrumb file relative to a run directory.
pub const RUN_ENV_RELATIVE: &str = "shadow_output/run_env.sh";

/// The `KEY="value"` lines from a run's `run_env.sh`.
#[derive(Debug, Default, Clone)]
pub struct RunEnv(HashMap<String, String>);

impl RunEnv {
    pub fn get(&self, key: &str) -> Option<&str> {
        self.0.get(key).map(String::as_str)
    }
}

/// Parse `KEY="value"` lines (as written by `run_sim.sh`'s `run_env.sh`
/// breadcrumb). Non-matching lines (blank, comments, malformed) are ignored,
/// mirroring `scripts/run_dirs.py::read_run_env`.
pub fn parse_run_env(text: &str) -> RunEnv {
    let mut vars = HashMap::new();
    for line in text.lines() {
        let line = line.trim();
        if let Some((key, value)) = split_key_value(line) {
            vars.insert(key.to_string(), value.to_string());
        }
    }
    RunEnv(vars)
}

/// Split a single `KEY="value"` line. `KEY` must be `[A-Z_][A-Z0-9_]*`;
/// `value` is whatever sits between the first and last `"` on the line.
fn split_key_value(line: &str) -> Option<(&str, &str)> {
    let eq = line.find('=')?;
    let key = &line[..eq];
    if key.is_empty()
        || !key
            .chars()
            .next()
            .is_some_and(|c| c == '_' || c.is_ascii_uppercase())
        || !key
            .chars()
            .all(|c| c == '_' || c.is_ascii_uppercase() || c.is_ascii_digit())
    {
        return None;
    }
    let rest = &line[eq + 1..];
    let rest = rest.strip_prefix('"')?;
    let value = rest.strip_suffix('"')?;
    Some((key, value))
}

/// Read and parse `<run_dir>/shadow_output/run_env.sh`. Returns an empty
/// `RunEnv` (not an error) if the file doesn't exist, matching
/// `scripts/run_dirs.py::read_run_env`.
pub fn read_run_env(run_dir: &Path) -> RunEnv {
    match std::fs::read_to_string(run_dir.join(RUN_ENV_RELATIVE)) {
        Ok(text) => parse_run_env(&text),
        Err(_) => RunEnv::default(),
    }
}

fn default_archive_base() -> PathBuf {
    std::env::var(ARCHIVE_BASE_ENV)
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("archived_runs"))
}

/// `YYYYMMDD_HHMMSS_` prefix used by every `run_sim.sh` run directory.
fn is_run_dir_name(name: &str) -> bool {
    let bytes = name.as_bytes();
    bytes.len() > 16
        && bytes[..8].iter().all(u8::is_ascii_digit)
        && bytes[8] == b'_'
        && bytes[9..15].iter().all(u8::is_ascii_digit)
        && bytes[15] == b'_'
}

fn newest_run_dir(base: &Path) -> Option<PathBuf> {
    let mut names: Vec<String> = std::fs::read_dir(base)
        .ok()?
        .filter_map(|e| e.ok())
        .filter(|e| e.path().is_dir())
        .filter_map(|e| e.file_name().into_string().ok())
        .filter(|n| is_run_dir_name(n))
        .collect();
    names.sort();
    names.pop().map(|n| base.join(n))
}

/// Resolve which run directory to use: `explicit` > `$MONEROSIM_RUN_DIR` >
/// newest under the archive base. Returns a clear, actionable error message
/// (not just "not found") when none apply.
pub fn resolve_run_dir(explicit: Option<&Path>) -> Result<PathBuf, String> {
    if let Some(p) = explicit {
        return if p.is_dir() {
            Ok(p.to_path_buf())
        } else {
            Err(format!("not a directory: {}", p.display()))
        };
    }
    if let Ok(from_env) = std::env::var(RUN_DIR_ENV) {
        if !from_env.is_empty() {
            let p = PathBuf::from(&from_env);
            return if p.is_dir() {
                Ok(p)
            } else {
                Err(format!("${RUN_DIR_ENV}={from_env} is not a directory"))
            };
        }
    }
    let base = default_archive_base();
    newest_run_dir(&base).ok_or_else(|| {
        format!(
            "no run directory: pass one explicitly, set ${RUN_DIR_ENV}, \
             or point ${ARCHIVE_BASE_ENV} at a base containing one \
             (nothing usable under {})",
            base.display()
        )
    })
}

/// Resolve a single directory (`shared_dir` or `daemon_data_dir`) for a
/// post-hoc tool: `explicit` if given, else the value of `breadcrumb_key`
/// from the resolved run's `run_env.sh`. Never falls back to a freshly
/// generated `/tmp` namespace.
pub fn resolve_dir(
    explicit: Option<PathBuf>,
    run_dir: Option<&Path>,
    breadcrumb_key: &str,
) -> Result<PathBuf, String> {
    if let Some(p) = explicit {
        return Ok(p);
    }
    let run_dir = resolve_run_dir(run_dir)?;
    let env = read_run_env(&run_dir);
    env.get(breadcrumb_key).map(PathBuf::from).ok_or_else(|| {
        format!(
            "{} has no {breadcrumb_key} (missing breadcrumb, or this run predates it); \
             pass the path explicitly",
            run_dir.join(RUN_ENV_RELATIVE).display()
        )
    })
}

/// Resolve a post-hoc data directory (`shared_dir` or the daemon log dir)
/// that survives archiving: `explicit` if given, else the archived copy
/// `<run_dir>/<archived_relative>` if it exists (`run_sim.sh`'s
/// `archive_transaction_registry` moves `shared_dir`'s registry/wallet/ringdb
/// files there under `transaction_registry/`, and daemon logs land under
/// `daemon_logs/`), else the live `/tmp` path named by `breadcrumb_key` in
/// `run_env.sh` *if that path still exists* (a run whose `/tmp` namespace
/// hasn't been cleaned up yet, e.g. still live or archived with `--no-cleanup`).
/// A finished, normally-archived run has had its `/tmp` namespace `rm -rf`'d
/// by `run_sim.sh`, so the breadcrumb path alone is not enough — this is why
/// `resolve_dir` (breadcrumb-only) isn't sufficient for this case. If neither
/// candidate exists, fails naming both paths that were tried.
pub fn resolve_data_dir(
    explicit: Option<PathBuf>,
    run_dir: Option<&Path>,
    archived_relative: &str,
    breadcrumb_key: &str,
) -> Result<PathBuf, String> {
    if let Some(p) = explicit {
        return Ok(p);
    }
    let run_dir = resolve_run_dir(run_dir)?;
    let archived = run_dir.join(archived_relative);
    if archived.is_dir() {
        return Ok(archived);
    }
    let env = read_run_env(&run_dir);
    let breadcrumb = env.get(breadcrumb_key).map(PathBuf::from);
    if let Some(live) = &breadcrumb {
        if live.is_dir() {
            return Ok(live.clone());
        }
    }
    let breadcrumb_desc = match &breadcrumb {
        Some(p) => format!("{} (${breadcrumb_key})", p.display()),
        None => format!("<not set in run_env.sh> (${breadcrumb_key})"),
    };
    Err(format!(
        "no {breadcrumb_key} data for run {}: tried the archived {} (not a directory) \
         and the live breadcrumb {breadcrumb_desc} (not a directory); pass the path explicitly",
        run_dir.display(),
        archived.display(),
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn write_run_env(run_dir: &Path, contents: &str) {
        let shadow_output = run_dir.join("shadow_output");
        std::fs::create_dir_all(&shadow_output).unwrap();
        std::fs::write(shadow_output.join("run_env.sh"), contents).unwrap();
    }

    #[test]
    fn parses_key_value_lines() {
        let env = parse_run_env(
            "MONEROSIM_RUN_ID=\"20260923_120000_quickstart\"\n\
             MONEROSIM_SHARED_DIR=\"/tmp/monerosim-x/shared\"\n\
             # a comment\n\
             \n\
             not a kv line\n\
             MONEROSIM_DAEMON_DATA_DIR=\"/tmp/monerosim-x\"\n",
        );
        assert_eq!(
            env.get("MONEROSIM_SHARED_DIR"),
            Some("/tmp/monerosim-x/shared")
        );
        assert_eq!(
            env.get("MONEROSIM_DAEMON_DATA_DIR"),
            Some("/tmp/monerosim-x")
        );
        assert_eq!(
            env.get("MONEROSIM_RUN_ID"),
            Some("20260923_120000_quickstart")
        );
        assert_eq!(env.get("MISSING"), None);
    }

    #[test]
    fn read_run_env_missing_file_is_empty_not_error() {
        let dir = tempdir().unwrap();
        let env = read_run_env(dir.path());
        assert_eq!(env.get("MONEROSIM_SHARED_DIR"), None);
    }

    #[test]
    fn resolve_run_dir_prefers_explicit_over_env_and_newest() {
        let _lock = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let explicit = tempdir().unwrap();
        let base = tempdir().unwrap();
        std::fs::create_dir_all(base.path().join("20260101_000000_a")).unwrap();

        let _guard = EnvVarGuard::set(RUN_DIR_ENV, "/does/not/matter");
        let resolved = resolve_run_dir(Some(explicit.path())).unwrap();
        assert_eq!(resolved, explicit.path());
    }

    #[test]
    fn resolve_run_dir_prefers_env_over_newest() {
        let _lock = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let env_dir = tempdir().unwrap();
        let base = tempdir().unwrap();
        std::fs::create_dir_all(base.path().join("20260101_000000_a")).unwrap();

        let _archive_guard = EnvVarGuard::set(ARCHIVE_BASE_ENV, base.path().to_str().unwrap());
        let _run_guard = EnvVarGuard::set(RUN_DIR_ENV, env_dir.path().to_str().unwrap());
        let resolved = resolve_run_dir(None).unwrap();
        assert_eq!(resolved, env_dir.path());
    }

    #[test]
    fn resolve_run_dir_falls_back_to_newest_archived_run() {
        let _lock = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let base = tempdir().unwrap();
        std::fs::create_dir_all(base.path().join("20260101_000000_a")).unwrap();
        std::fs::create_dir_all(base.path().join("20260922_235959_b")).unwrap();
        std::fs::create_dir_all(base.path().join("not_a_run_dir")).unwrap();

        let _archive_guard = EnvVarGuard::set(ARCHIVE_BASE_ENV, base.path().to_str().unwrap());
        let _run_guard = EnvVarGuard::unset(RUN_DIR_ENV);
        let resolved = resolve_run_dir(None).unwrap();
        assert_eq!(resolved, base.path().join("20260922_235959_b"));
    }

    #[test]
    fn resolve_run_dir_fails_clearly_with_nothing_to_go_on() {
        let _lock = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let base = tempdir().unwrap();
        let _archive_guard = EnvVarGuard::set(ARCHIVE_BASE_ENV, base.path().to_str().unwrap());
        let _run_guard = EnvVarGuard::unset(RUN_DIR_ENV);
        let err = resolve_run_dir(None).unwrap_err();
        assert!(err.contains(RUN_DIR_ENV), "error should name {RUN_DIR_ENV}: {err}");
        assert!(
            err.contains(ARCHIVE_BASE_ENV),
            "error should name {ARCHIVE_BASE_ENV}: {err}"
        );
    }

    #[test]
    fn resolve_dir_explicit_wins() {
        let dir = tempdir().unwrap();
        let explicit = PathBuf::from("/explicit/shared");
        let resolved =
            resolve_dir(Some(explicit.clone()), Some(dir.path()), "MONEROSIM_SHARED_DIR").unwrap();
        assert_eq!(resolved, explicit);
    }

    #[test]
    fn resolve_dir_reads_breadcrumb_from_run_dir() {
        let dir = tempdir().unwrap();
        write_run_env(
            dir.path(),
            "MONEROSIM_SHARED_DIR=\"/tmp/monerosim-run/shared\"\n\
             MONEROSIM_DAEMON_DATA_DIR=\"/tmp/monerosim-run\"\n",
        );
        let shared = resolve_dir(None, Some(dir.path()), "MONEROSIM_SHARED_DIR").unwrap();
        assert_eq!(shared, PathBuf::from("/tmp/monerosim-run/shared"));
        let daemon = resolve_dir(None, Some(dir.path()), "MONEROSIM_DAEMON_DATA_DIR").unwrap();
        assert_eq!(daemon, PathBuf::from("/tmp/monerosim-run"));
    }

    #[test]
    fn resolve_dir_fails_clearly_when_breadcrumb_key_missing() {
        let dir = tempdir().unwrap();
        write_run_env(dir.path(), "MONEROSIM_RUN_ID=\"x\"\n");
        let err = resolve_dir(None, Some(dir.path()), "MONEROSIM_SHARED_DIR").unwrap_err();
        assert!(err.contains("MONEROSIM_SHARED_DIR"), "{err}");
        assert!(err.contains("run_env.sh"), "{err}");
    }

    #[test]
    fn resolve_dir_fails_clearly_when_no_run_dir_at_all() {
        let _lock = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let base = tempdir().unwrap();
        let _archive_guard = EnvVarGuard::set(ARCHIVE_BASE_ENV, base.path().to_str().unwrap());
        let _run_guard = EnvVarGuard::unset(RUN_DIR_ENV);
        let err = resolve_dir(None, None, "MONEROSIM_SHARED_DIR").unwrap_err();
        assert!(err.contains(RUN_DIR_ENV), "{err}");
    }

    #[test]
    fn resolve_data_dir_prefers_archived_copy_when_present() {
        let dir = tempdir().unwrap();
        let archived = dir.path().join("transaction_registry");
        std::fs::create_dir_all(&archived).unwrap();
        // Breadcrumb also present but must lose to the archived copy.
        write_run_env(
            dir.path(),
            "MONEROSIM_SHARED_DIR=\"/does/not/exist/shared\"\n",
        );

        let resolved = resolve_data_dir(
            None,
            Some(dir.path()),
            "transaction_registry",
            "MONEROSIM_SHARED_DIR",
        )
        .unwrap();
        assert_eq!(resolved, archived);
    }

    #[test]
    fn resolve_data_dir_falls_back_to_live_breadcrumb_when_it_still_exists() {
        let dir = tempdir().unwrap();
        // No archived transaction_registry/ — only a live /tmp path that
        // hasn't been cleaned up yet.
        let live = tempdir().unwrap();
        write_run_env(
            dir.path(),
            &format!(
                "MONEROSIM_SHARED_DIR=\"{}\"\n",
                live.path().to_str().unwrap()
            ),
        );

        let resolved = resolve_data_dir(
            None,
            Some(dir.path()),
            "transaction_registry",
            "MONEROSIM_SHARED_DIR",
        )
        .unwrap();
        assert_eq!(resolved, live.path());
    }

    #[test]
    fn resolve_data_dir_fails_clearly_naming_both_paths_when_neither_exists() {
        let dir = tempdir().unwrap();
        write_run_env(
            dir.path(),
            "MONEROSIM_SHARED_DIR=\"/tmp/monerosim-long-gone/shared\"\n",
        );

        let err = resolve_data_dir(
            None,
            Some(dir.path()),
            "transaction_registry",
            "MONEROSIM_SHARED_DIR",
        )
        .unwrap_err();
        assert!(
            err.contains(&dir.path().join("transaction_registry").display().to_string()),
            "should name the archived path: {err}"
        );
        assert!(
            err.contains("/tmp/monerosim-long-gone/shared"),
            "should name the breadcrumb path: {err}"
        );
    }

    // std::env is process-global; the caller (each test above) holds
    // ENV_LOCK for its whole body before creating any guard below — the
    // guards themselves must NOT lock (a single thread creating two guards
    // would then try to re-lock a std::sync::Mutex it already holds and
    // deadlock itself, which in turn wedges every other thread waiting on
    // the same lock). Mirrors src/lib.rs's EnvGuard/ENV_LOCK split.
    use std::sync::Mutex;
    static ENV_LOCK: Mutex<()> = Mutex::new(());

    struct EnvVarGuard {
        key: &'static str,
        prev: Option<String>,
    }

    impl EnvVarGuard {
        fn set(key: &'static str, value: &str) -> Self {
            let prev = std::env::var(key).ok();
            std::env::set_var(key, value);
            Self { key, prev }
        }

        fn unset(key: &'static str) -> Self {
            let prev = std::env::var(key).ok();
            std::env::remove_var(key);
            Self { key, prev }
        }
    }

    impl Drop for EnvVarGuard {
        fn drop(&mut self) {
            match &self.prev {
                Some(v) => std::env::set_var(self.key, v),
                None => std::env::remove_var(self.key),
            }
        }
    }
}
