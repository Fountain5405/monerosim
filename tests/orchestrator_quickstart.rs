//! Output-equivalence test for the orchestrator against the GML quickstart fixture.
//!
//! Mirrors `orchestrator_smoke.rs` but uses a snapshot of the larger
//! `quickstart.yaml` (DNS server enabled, GML topology, multiple miners
//! and users). Cargo runs tests from the crate root, so the relative
//! `gml_processing/...` path inside the fixture resolves correctly.

use monerosim::{config_loader, orchestrator};
use regex::Regex;
use std::path::Path;
use tempfile::TempDir;

/// Redact machine-local paths so the golden diff is portable across hosts.
fn normalize(yaml: &str) -> String {
    // /tmp/<random>/ tempdirs from the test run.
    let yaml = Regex::new(r"/tmp/[A-Za-z0-9_.-]+/")
        .unwrap()
        .replace_all(yaml, "TMPDIR/")
        .into_owned();
    // Repo absolute path embeds in wrapper scripts / data-dir paths.
    let cwd = std::env::current_dir().unwrap().to_string_lossy().to_string();
    let yaml = yaml.replace(&cwd, "REPO_ROOT");
    // $HOME embeds in resolved monerod / wallet paths.
    if let Ok(home) = std::env::var("HOME") {
        if !home.is_empty() {
            return yaml.replace(&home, "HOME");
        }
    }
    yaml
}

#[test]
fn quickstart_fixture_yaml_matches_golden() {
    let tmp = TempDir::new().unwrap();
    let output_yaml = tmp.path().join("shadow_agents.yaml");
    let shared_dir = tmp.path().join("shared");
    std::fs::create_dir_all(&shared_dir).unwrap();
    std::fs::create_dir_all(tmp.path().join("scripts")).unwrap();

    let mut config = config_loader::load_config(Path::new("tests/fixtures/quickstart.yaml"))
        .expect("quickstart fixture loads");
    config.general.shared_dir = shared_dir.to_string_lossy().to_string();

    orchestrator::generate_agent_shadow_config(&config, &output_yaml)
        .expect("orchestrator generates");

    let actual = normalize(&std::fs::read_to_string(&output_yaml).unwrap());
    let golden_path = Path::new("tests/golden/quickstart.yaml");

    if std::env::var("UPDATE_GOLDEN").is_ok() {
        std::fs::write(golden_path, &actual).unwrap();
        return;
    }

    let expected = std::fs::read_to_string(golden_path).expect(
        "tests/golden/quickstart.yaml exists; run with UPDATE_GOLDEN=1 to refresh",
    );
    assert_eq!(
        actual, expected,
        "Generated shadow_agents.yaml diverged from tests/golden/quickstart.yaml.\n\
         Inspect the diff and either fix the orchestrator or regenerate the golden\n\
         with UPDATE_GOLDEN=1 cargo test --test orchestrator_quickstart",
    );
}
