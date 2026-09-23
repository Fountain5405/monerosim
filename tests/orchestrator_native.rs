//! Output-equivalence test for the orchestrator's native-mining wiring.
//!
//! Generates `shadow_agents.yaml` from `tests/fixtures/native.yaml`, normalizes
//! machine-local absolute paths via regex, and byte-diffs against
//! `tests/golden/native.yaml`. Run with `UPDATE_GOLDEN=1` to refresh the
//! checked-in golden file after intentional output changes.

use monerosim::{config_loader, orchestrator};
use regex::Regex;
use std::path::Path;
use tempfile::TempDir;

/// Redact machine-local paths so the golden diff is portable across hosts.
/// Order matters: longer/more-specific patterns first.
fn normalize(yaml: &str) -> String {
    // /tmp/<random>/ tempdirs from the test run.
    let yaml = Regex::new(r"/tmp/[A-Za-z0-9_.-]+/")
        .unwrap()
        .replace_all(yaml, "TMPDIR/")
        .into_owned();
    // The repo's absolute path embeds in wrapper script / data-dir paths.
    let cwd = std::env::current_dir()
        .unwrap()
        .to_string_lossy()
        .to_string();
    let yaml = yaml.replace(&cwd, "REPO_ROOT");
    // The user's $HOME embeds in resolved monerod / wallet paths.
    if let Ok(home) = std::env::var("HOME") {
        if !home.is_empty() {
            return yaml.replace(&home, "HOME");
        }
    }
    yaml
}

#[test]
fn native_fixture_yaml_matches_golden() {
    // The capability probe needs a built monerod-sim; the golden covers
    // rendering, not the probe, so skip it here.
    std::env::set_var("MONEROSIM_SKIP_SIM_BINARY_CHECK", "1");
    let tmp = TempDir::new().unwrap();
    let output_yaml = tmp.path().join("shadow_agents.yaml");
    let shared_dir = tmp.path().join("shared");
    std::fs::create_dir_all(&shared_dir).unwrap();
    std::fs::create_dir_all(tmp.path().join("scripts")).unwrap();

    let mut config = config_loader::load_config(Path::new("tests/fixtures/native.yaml"))
        .expect("native fixture loads");
    config.general.shared_dir = shared_dir.to_string_lossy().to_string();
    // Pin the daemon-data-dir default too (was already deterministic "/tmp";
    // now the library generates a fresh per-process namespace when unset,
    // so pin explicitly to keep this golden byte-diff stable).
    config.general.daemon_data_dir = "/tmp".to_string();

    orchestrator::generate_agent_shadow_config(&config, &output_yaml)
        .expect("orchestrator generates");

    let actual = normalize(&std::fs::read_to_string(&output_yaml).unwrap());

    // Structural assertions that do not depend on the golden file.
    assert!(actual.contains("--sim-hash-interval-ms=50"), "miner-001 (20 h/s) interval");
    assert!(actual.contains("--sim-hash-interval-ms=333"), "miner-002 (3 h/s) interval");
    assert!(actual.contains("--sim-rx-full-dataset"), "full dataset on by default");
    assert!(actual.contains("HOME/.monerosim/bin/monerod-sim"), "miners substituted to monerod-sim");
    assert_eq!(actual.matches("--sim-hash-interval-ms=").count(), 2, "only the two miners get the knob");

    // Agent attributes are baked into the per-agent wrapper scripts (scripts/),
    // not shadow_agents.yaml — same as the pre-existing hashrate/is_miner
    // attributes.
    let scripts_dir = tmp.path().join("scripts");
    let mut wrappers = String::new();
    let mut mining_mode_files = 0usize;
    for entry in std::fs::read_dir(&scripts_dir).unwrap() {
        let path = entry.unwrap().path();
        let contents = std::fs::read_to_string(&path).unwrap();
        if contents.contains("mining_mode") {
            mining_mode_files += 1;
        }
        wrappers.push_str(&contents);
    }
    assert!(wrappers.contains("mining_mode"), "mining_mode attribute passed to the miner agents");
    assert!(wrappers.contains("hash_interval_ms"), "hash_interval_ms attribute passed to the miner agents");
    assert!(wrappers.contains("daemon_log_path"), "daemon_log_path attribute passed to the miner agents");
    // relay-001 is daemon-only (no wallet/script) and gets no wrapper script at
    // all, so there's nothing to assert "does not contain mining_mode" on
    // directly; instead confirm exactly the miners' wrappers carry it. Each
    // autonomous-miner agent gets TWO wrapper scripts (regular_user, for the
    // wallet, plus the mining_script itself — see the HYBRID APPROACH comment
    // in user_agents.rs), both fed the same merged_attributes, so 2 miners
    // means 4 wrapper files.
    assert_eq!(mining_mode_files, 4, "only the two miners' wrapper scripts carry mining_mode");

    let golden_path = Path::new("tests/golden/native.yaml");
    if std::env::var("UPDATE_GOLDEN").is_ok() {
        std::fs::write(golden_path, &actual).unwrap();
        return;
    }
    let expected = std::fs::read_to_string(golden_path)
        .expect("tests/golden/native.yaml exists; run with UPDATE_GOLDEN=1 to refresh");
    assert_eq!(actual, expected, "regenerate with UPDATE_GOLDEN=1 cargo test --test orchestrator_native");
}
