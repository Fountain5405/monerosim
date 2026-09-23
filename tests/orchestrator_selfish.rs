// tests/orchestrator_selfish.rs
use monerosim::{config_loader, orchestrator};
use regex::Regex;
use std::path::Path;
use tempfile::TempDir;

/// Redact machine-local paths so the golden diff is portable across hosts.
/// Order matters: longer/more-specific patterns first. Copied verbatim from
/// `tests/orchestrator_native.rs` (not a shared module) so the golden here is
/// host-portable too.
fn normalize(yaml: &str) -> String {
    let yaml = Regex::new(r"/tmp/[A-Za-z0-9_.-]+/")
        .unwrap()
        .replace_all(yaml, "TMPDIR/")
        .into_owned();
    let cwd = std::env::current_dir()
        .unwrap()
        .to_string_lossy()
        .to_string();
    let yaml = yaml.replace(&cwd, "REPO_ROOT");
    if let Ok(home) = std::env::var("HOME") {
        if !home.is_empty() {
            return yaml.replace(&home, "HOME");
        }
    }
    yaml
}

#[test]
fn selfish_fixture_yaml_matches_golden() {
    std::env::set_var("MONEROSIM_SKIP_SIM_BINARY_CHECK", "1");
    let tmp = TempDir::new().unwrap();
    let output_yaml = tmp.path().join("shadow_agents.yaml");
    let shared_dir = tmp.path().join("shared");
    std::fs::create_dir_all(&shared_dir).unwrap();
    std::fs::create_dir_all(tmp.path().join("scripts")).unwrap();

    let mut config = config_loader::load_config(Path::new("tests/fixtures/selfish.yaml"))
        .expect("selfish fixture loads");
    config.general.shared_dir = shared_dir.to_string_lossy().to_string();
    // Pin the daemon-data-dir default too (was already deterministic "/tmp";
    // now the library generates a fresh per-process namespace when unset,
    // so pin explicitly to keep this golden byte-diff stable).
    config.general.daemon_data_dir = "/tmp".to_string();

    orchestrator::generate_agent_shadow_config(&config, &output_yaml)
        .expect("orchestrator generates");

    let actual = normalize(&std::fs::read_to_string(&output_yaml).unwrap());

    // Structural assertions independent of the golden.
    assert!(actual.contains("--offline"), "attacker miner daemon gets --offline");
    assert!(actual.contains("--sim-hash-interval-ms=250"), "attacker (4 h/s) interval");
    assert!(actual.contains("--sim-hash-interval-ms=167"), "honest (6 h/s) interval");
    assert_eq!(actual.matches("--sim-hash-interval-ms=").count(), 2,
               "only the two miners (honest + attacker) get the knob");
    assert!(actual.contains("HOME/.monerosim/bin/monerod-sim"),
            "native miners substituted to monerod-sim");

    // Attacker wrapper scripts carry the strategy attributes.
    let scripts_dir = tmp.path().join("scripts");
    let mut wrappers = String::new();
    for entry in std::fs::read_dir(&scripts_dir).unwrap() {
        wrappers.push_str(&std::fs::read_to_string(entry.unwrap().path()).unwrap());
    }
    assert!(wrappers.contains("selfish_miner"), "attacker runs the selfish_miner script");
    assert!(wrappers.contains("selfish_bridge"), "bridge runs the selfish_bridge script");
    assert!(wrappers.contains("eyal_sirer"), "strategy attribute passed to the attacker");
    assert!(wrappers.contains("bridge_agent"), "bridge_agent attribute passed to the attacker");

    let golden_path = Path::new("tests/golden/selfish.yaml");
    if std::env::var("UPDATE_GOLDEN").is_ok() {
        std::fs::write(golden_path, &actual).unwrap();
        return;
    }
    let expected = std::fs::read_to_string(golden_path)
        .expect("tests/golden/selfish.yaml exists; run with UPDATE_GOLDEN=1 to create it");
    assert_eq!(actual, expected,
               "regenerate with UPDATE_GOLDEN=1 cargo test --test orchestrator_selfish");
}
