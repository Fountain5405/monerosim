//! Difficulty-preload chain snapshot resolution, preflight and
//! materialization (native mining only). See docs/CHAIN_SNAPSHOT.md and
//! docs/superpowers/specs/2026-09-23-difficulty-preload-design.md Sec 5.
//!
//! Cache-key derivation (sha256 of D0, monero_pin, hf_schedule, network_id,
//! height) lives in `scripts/chain_snapshot.py` and is never duplicated
//! here: [`ensure_template`] always shells out to its `build-template`
//! subcommand (a cheap no-op on a cache hit) and parses the resulting cache
//! directory from its stdout, rather than recomputing the key in Rust.

use serde::Deserialize;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Shadow's simulated clock starts at 2000-01-01 00:00 UTC.
pub const SHADOW_EPOCH: i64 = 946_684_800;
/// Preflight's max allowed gap between a snapshot's tip and the Shadow epoch.
pub const MAX_TIP_GAP_SECONDS: i64 = 1800;

/// `manifest.json`, as written by `scripts/chain_snapshot.py export`.
#[derive(Debug, Deserialize, Clone, PartialEq)]
pub struct SnapshotManifest {
    pub height: u64,
    #[serde(rename = "D0")]
    pub d0: u64,
    pub total_hashrate: u64,
    pub monero_pin: String,
    #[serde(default)]
    pub hf_schedule: Option<String>,
    pub network_id: String,
    #[allow(dead_code)]
    pub genesis_hash: String,
    pub tip_timestamp: i64,
    #[allow(dead_code)]
    pub tip_hash: String,
    #[allow(dead_code)]
    pub generated_by_run: String,
    #[allow(dead_code)]
    pub created_at: String,
}

/// Result of resolving `general.mining.chain_snapshot`.
#[derive(Debug, Clone, PartialEq)]
pub enum ChainSnapshotSelection {
    Off,
    Preset(PathBuf),
}

/// Resolve `general.mining.chain_snapshot`'s string value to a concrete
/// preset directory (or [`ChainSnapshotSelection::Off`]).
///
/// - `off` -> Off.
/// - contains `/` -> used as a path, as-is.
/// - `auto` -> scan `<repo_root>/chain_snapshots/*/manifest.json` for the
///   preset whose `total_hashrate` and `monero_pin` match this run.
/// - anything else -> `<repo_root>/chain_snapshots/<value>/`.
///
/// `repo_root` anchors relative lookups (`chain_snapshots/<name>/`,
/// `monero.pin`) — pass the process's current directory (monerosim is
/// always run from the repo root, matching `current_dir` elsewhere in this
/// codebase).
pub fn resolve_chain_snapshot(
    value: &str,
    repo_root: &Path,
    total_hashrate: u64,
) -> Result<ChainSnapshotSelection, String> {
    if value == "off" {
        return Ok(ChainSnapshotSelection::Off);
    }
    if value.contains('/') {
        return Ok(ChainSnapshotSelection::Preset(PathBuf::from(value)));
    }
    if value == "auto" {
        return resolve_auto(repo_root, total_hashrate);
    }
    Ok(ChainSnapshotSelection::Preset(
        repo_root.join("chain_snapshots").join(value),
    ))
}

fn resolve_auto(
    repo_root: &Path,
    total_hashrate: u64,
) -> Result<ChainSnapshotSelection, String> {
    let monero_pin = read_monero_pin(repo_root)?;
    let base = repo_root.join("chain_snapshots");
    let mut matches: Vec<PathBuf> = Vec::new();
    if let Ok(entries) = fs::read_dir(&base) {
        for entry in entries.flatten() {
            let preset_dir = entry.path();
            if !preset_dir.is_dir() {
                continue;
            }
            let manifest_path = preset_dir.join("manifest.json");
            let manifest = match load_manifest(&manifest_path) {
                Ok(m) => m,
                Err(_) => continue, // not a preset (or unreadable): skip silently
            };
            if manifest.total_hashrate == total_hashrate && manifest.monero_pin == monero_pin {
                matches.push(preset_dir);
            }
        }
    }
    match matches.len() {
        0 => Err(format!(
            "general.mining.chain_snapshot: auto found no preset under {} matching total \
             hashrate {} h/s and monero_pin {}. Generate one (see docs/CHAIN_SNAPSHOT.md): \
             venv/bin/python scripts/chain_snapshot.py export ...",
            base.display(),
            total_hashrate,
            monero_pin
        )),
        1 => Ok(ChainSnapshotSelection::Preset(matches.remove(0))),
        _ => {
            let names: Vec<String> = matches.iter().map(|p| p.display().to_string()).collect();
            Err(format!(
                "general.mining.chain_snapshot: auto found {} matching presets under {}: {}. \
                 Pick one explicitly (general.mining.chain_snapshot: <name>).",
                names.len(),
                base.display(),
                names.join(", ")
            ))
        }
    }
}

/// Read and trim `<repo_root>/monero.pin`.
pub fn read_monero_pin(repo_root: &Path) -> Result<String, String> {
    let path = repo_root.join("monero.pin");
    fs::read_to_string(&path)
        .map(|s| s.trim().to_string())
        .map_err(|e| format!("could not read {}: {}", path.display(), e))
}

/// Load and parse a preset's `manifest.json`.
pub fn load_manifest(manifest_path: &Path) -> Result<SnapshotManifest, String> {
    let data = fs::read_to_string(manifest_path)
        .map_err(|e| format!("{}: {}", manifest_path.display(), e))?;
    serde_json::from_str(&data).map_err(|e| format!("{}: {}", manifest_path.display(), e))
}

/// Preflight: manifest present, `monero_pin` matches, `hf_schedule` matches
/// (or both empty/absent), and the tip lands just before the Shadow epoch
/// (strictly before it, and no more than [`MAX_TIP_GAP_SECONDS`] earlier).
pub fn preflight_check(
    preset_dir: &Path,
    monero_pin: &str,
    hf_schedule: Option<&str>,
) -> Result<SnapshotManifest, String> {
    let manifest_path = preset_dir.join("manifest.json");
    if !manifest_path.is_file() {
        return Err(format!(
            "chain snapshot preset {} has no manifest.json",
            preset_dir.display()
        ));
    }
    let manifest = load_manifest(&manifest_path)?;

    if manifest.monero_pin != monero_pin {
        return Err(format!(
            "chain snapshot {} was built for monero_pin '{}' but this run's monero.pin is '{}'",
            preset_dir.display(),
            manifest.monero_pin,
            monero_pin
        ));
    }

    // Empty string and absent both mean "no schedule" — treat them the same.
    let manifest_hf = manifest.hf_schedule.as_deref().filter(|s| !s.is_empty());
    let cfg_hf = hf_schedule.filter(|s| !s.is_empty());
    if manifest_hf != cfg_hf {
        return Err(format!(
            "chain snapshot {} was built with hf_schedule {:?} but this run's is {:?}",
            preset_dir.display(),
            manifest_hf,
            cfg_hf
        ));
    }

    if manifest.tip_timestamp >= SHADOW_EPOCH {
        return Err(format!(
            "chain snapshot {} tip_timestamp {} is not before the Shadow epoch {}",
            preset_dir.display(),
            manifest.tip_timestamp,
            SHADOW_EPOCH
        ));
    }
    let gap = SHADOW_EPOCH - manifest.tip_timestamp;
    if gap > MAX_TIP_GAP_SECONDS {
        return Err(format!(
            "chain snapshot {} tip is {}s before the Shadow epoch, exceeds the {}s max gap",
            preset_dir.display(),
            gap,
            MAX_TIP_GAP_SECONDS
        ));
    }

    Ok(manifest)
}

/// Ensure the preset's LMDB template is cached locally, invoking
/// `scripts/chain_snapshot.py build-template` (a cheap no-op on a cache
/// hit). Returns the cache directory, parsed from the script's own
/// "Cache hit: " / "Built template cache: " stdout line — the cache-key
/// derivation is never duplicated in Rust.
pub fn ensure_template(preset_dir: &Path, repo_root: &Path) -> Result<PathBuf, String> {
    let python = repo_root.join("venv/bin/python");
    let script = repo_root.join("scripts/chain_snapshot.py");
    let cmd_display = format!(
        "{} {} build-template --preset {}",
        python.display(),
        script.display(),
        preset_dir.display()
    );
    log::info!("Chain snapshot: ensuring template cache ({})", cmd_display);
    let output = Command::new(&python)
        .arg(&script)
        .arg("build-template")
        .arg("--preset")
        .arg(preset_dir)
        .output()
        .map_err(|e| format!("failed to run `{}`: {}", cmd_display, e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
    let stderr = String::from_utf8_lossy(&output.stderr).into_owned();
    if !output.status.success() {
        return Err(format!(
            "`{}` failed (exit {:?}):\nstdout: {}\nstderr: {}",
            cmd_display,
            output.status.code(),
            stdout,
            stderr
        ));
    }
    for line in stdout.lines() {
        if let Some(path) = line.strip_prefix("Cache hit: ") {
            return Ok(PathBuf::from(path.trim()));
        }
        if let Some(path) = line.strip_prefix("Built template cache: ") {
            return Ok(PathBuf::from(path.trim()));
        }
    }
    Err(format!(
        "`{}` succeeded but did not print a cache path:\nstdout: {}",
        cmd_display, stdout
    ))
}

/// Copy a cached template's LMDB data into a daemon's data dir
/// (`cp --sparse=always -r`, preserving LMDB sparse holes), excluding the
/// cache's own `manifest.json` (a debugging aid, not part of a monerod data
/// dir). Returns the number of (logical, not on-disk) bytes copied.
pub fn copy_template_into(cache_dir: &Path, dest_data_dir: &Path) -> Result<u64, String> {
    fs::create_dir_all(dest_data_dir)
        .map_err(|e| format!("failed to create {}: {}", dest_data_dir.display(), e))?;

    // Trailing "/." copies the cache dir's CONTENTS into the already-created
    // destination, rather than nesting an extra directory level inside it.
    let status = Command::new("cp")
        .arg("--sparse=always")
        .arg("-r")
        .arg(format!("{}/.", cache_dir.display()))
        .arg(dest_data_dir)
        .status()
        .map_err(|e| format!("failed to run cp: {}", e))?;
    if !status.success() {
        return Err(format!(
            "cp --sparse=always -r {} -> {} failed (exit {:?})",
            cache_dir.display(),
            dest_data_dir.display(),
            status.code()
        ));
    }

    let stray_manifest = dest_data_dir.join("manifest.json");
    if stray_manifest.is_file() {
        let _ = fs::remove_file(&stray_manifest);
    }

    Ok(dir_size_bytes(dest_data_dir))
}

fn dir_size_bytes(path: &Path) -> u64 {
    let mut total = 0u64;
    let mut stack = vec![path.to_path_buf()];
    while let Some(p) = stack.pop() {
        let meta = match fs::symlink_metadata(&p) {
            Ok(m) => m,
            Err(_) => continue,
        };
        if meta.is_dir() {
            if let Ok(entries) = fs::read_dir(&p) {
                for entry in entries.flatten() {
                    stack.push(entry.path());
                }
            }
        } else {
            total += meta.len();
        }
    }
    total
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;
    use std::io::Write;

    fn write_manifest(dir: &Path, overrides: &[(&str, serde_json::Value)]) {
        let mut m = serde_json::json!({
            "height": 10,
            "D0": 6000,
            "total_hashrate": 50,
            "monero_pin": "v0.18.5.1",
            "hf_schedule": null,
            "network_id": "regtest-fakechain",
            "genesis_hash": "a".repeat(64),
            "tip_timestamp": SHADOW_EPOCH - 600,
            "tip_hash": "b".repeat(64),
            "generated_by_run": "test",
            "created_at": "2026-09-23T00:00:00Z",
        });
        for (k, v) in overrides {
            m[k] = v.clone();
        }
        fs::create_dir_all(dir).unwrap();
        let mut f = File::create(dir.join("manifest.json")).unwrap();
        f.write_all(serde_json::to_string(&m).unwrap().as_bytes())
            .unwrap();
    }

    #[test]
    fn resolve_off_is_off() {
        let tmp = tempfile::tempdir().unwrap();
        assert_eq!(
            resolve_chain_snapshot("off", tmp.path(), 50).unwrap(),
            ChainSnapshotSelection::Off
        );
    }

    #[test]
    fn resolve_path_used_as_is() {
        let tmp = tempfile::tempdir().unwrap();
        let sel = resolve_chain_snapshot("some/dir/h50", tmp.path(), 50).unwrap();
        assert_eq!(sel, ChainSnapshotSelection::Preset(PathBuf::from("some/dir/h50")));
    }

    #[test]
    fn resolve_bare_name_under_chain_snapshots() {
        let tmp = tempfile::tempdir().unwrap();
        let sel = resolve_chain_snapshot("h50", tmp.path(), 50).unwrap();
        assert_eq!(
            sel,
            ChainSnapshotSelection::Preset(tmp.path().join("chain_snapshots").join("h50"))
        );
    }

    #[test]
    fn resolve_auto_no_match_errors_with_recipe_pointer() {
        let tmp = tempfile::tempdir().unwrap();
        fs::write(tmp.path().join("monero.pin"), "v0.18.5.1\n").unwrap();
        let err = resolve_chain_snapshot("auto", tmp.path(), 50).unwrap_err();
        assert!(err.contains("no preset"), "{err}");
        assert!(err.contains("docs/CHAIN_SNAPSHOT.md"), "{err}");
    }

    #[test]
    fn resolve_auto_single_match() {
        let tmp = tempfile::tempdir().unwrap();
        fs::write(tmp.path().join("monero.pin"), "v0.18.5.1\n").unwrap();
        let preset = tmp.path().join("chain_snapshots").join("h50");
        write_manifest(&preset, &[]);
        let sel = resolve_chain_snapshot("auto", tmp.path(), 50).unwrap();
        assert_eq!(sel, ChainSnapshotSelection::Preset(preset));
    }

    #[test]
    fn resolve_auto_ignores_pin_mismatch() {
        let tmp = tempfile::tempdir().unwrap();
        fs::write(tmp.path().join("monero.pin"), "v0.18.5.1\n").unwrap();
        let preset = tmp.path().join("chain_snapshots").join("h50");
        write_manifest(&preset, &[("monero_pin", serde_json::json!("v0.18.0.0"))]);
        let err = resolve_chain_snapshot("auto", tmp.path(), 50).unwrap_err();
        assert!(err.contains("no preset"), "{err}");
    }

    #[test]
    fn resolve_auto_ambiguous_errors_listing_both() {
        let tmp = tempfile::tempdir().unwrap();
        fs::write(tmp.path().join("monero.pin"), "v0.18.5.1\n").unwrap();
        write_manifest(&tmp.path().join("chain_snapshots").join("h50"), &[]);
        write_manifest(&tmp.path().join("chain_snapshots").join("h50b"), &[]);
        let err = resolve_chain_snapshot("auto", tmp.path(), 50).unwrap_err();
        assert!(err.contains("found 2 matching presets"), "{err}");
    }

    #[test]
    fn preflight_pass() {
        let tmp = tempfile::tempdir().unwrap();
        let preset = tmp.path().join("h50");
        write_manifest(&preset, &[]);
        let manifest = preflight_check(&preset, "v0.18.5.1", None).unwrap();
        assert_eq!(manifest.height, 10);
    }

    #[test]
    fn preflight_missing_manifest() {
        let tmp = tempfile::tempdir().unwrap();
        let err = preflight_check(tmp.path(), "v0.18.5.1", None).unwrap_err();
        assert!(err.contains("no manifest.json"), "{err}");
    }

    #[test]
    fn preflight_pin_mismatch() {
        let tmp = tempfile::tempdir().unwrap();
        let preset = tmp.path().join("h50");
        write_manifest(&preset, &[]);
        let err = preflight_check(&preset, "v0.18.0.0", None).unwrap_err();
        assert!(err.contains("monero_pin"), "{err}");
    }

    #[test]
    fn preflight_hf_schedule_mismatch() {
        let tmp = tempfile::tempdir().unwrap();
        let preset = tmp.path().join("h50");
        write_manifest(&preset, &[("hf_schedule", serde_json::json!("1:0,14:1"))]);
        let err = preflight_check(&preset, "v0.18.5.1", None).unwrap_err();
        assert!(err.contains("hf_schedule"), "{err}");
        // Matching schedules pass.
        assert!(preflight_check(&preset, "v0.18.5.1", Some("1:0,14:1")).is_ok());
    }

    #[test]
    fn preflight_both_hf_schedule_absent_ok() {
        let tmp = tempfile::tempdir().unwrap();
        let preset = tmp.path().join("h50");
        write_manifest(&preset, &[("hf_schedule", serde_json::json!(""))]);
        assert!(preflight_check(&preset, "v0.18.5.1", None).is_ok());
    }

    #[test]
    fn preflight_tip_in_future_rejected() {
        let tmp = tempfile::tempdir().unwrap();
        let preset = tmp.path().join("h50");
        write_manifest(&preset, &[("tip_timestamp", serde_json::json!(SHADOW_EPOCH + 10))]);
        let err = preflight_check(&preset, "v0.18.5.1", None).unwrap_err();
        assert!(err.contains("not before the Shadow epoch"), "{err}");
    }

    #[test]
    fn preflight_tip_too_old_rejected() {
        let tmp = tempfile::tempdir().unwrap();
        let preset = tmp.path().join("h50");
        write_manifest(
            &preset,
            &[("tip_timestamp", serde_json::json!(SHADOW_EPOCH - 3600))],
        );
        let err = preflight_check(&preset, "v0.18.5.1", None).unwrap_err();
        assert!(err.contains("max gap"), "{err}");
    }

    #[test]
    fn copy_template_into_n_fake_dirs() {
        let tmp = tempfile::tempdir().unwrap();
        let cache_dir = tmp.path().join("cache");
        fs::create_dir_all(&cache_dir).unwrap();
        fs::write(cache_dir.join("data.mdb"), b"fake lmdb data").unwrap();
        fs::write(cache_dir.join("manifest.json"), b"{}").unwrap();

        for id in ["miner-001", "relay-001", "user-001"] {
            let dest = tmp.path().join("daemon_data").join(format!("monero-{id}"));
            let bytes = copy_template_into(&cache_dir, &dest).unwrap();
            assert!(dest.join("data.mdb").is_file());
            // manifest.json must NOT be copied into a node's data dir.
            assert!(!dest.join("manifest.json").exists());
            assert_eq!(bytes, b"fake lmdb data".len() as u64);
        }
    }
}
