//! The scenario expander (scripts/scenario_parser.py) writes undeclared
//! fallback seeds into the expanded config with the values the Rust injector
//! uses. Declared and injected seeds must generate byte-identical Shadow
//! configs, or the two copies of the seed defaults have drifted.

use monerosim::{config_loader, orchestrator};
use std::path::Path;
use tempfile::TempDir;

fn generate(yaml_text: &str, tmp: &Path) -> String {
    let cfg_path = tmp.join("cfg.yaml");
    std::fs::write(&cfg_path, yaml_text).unwrap();
    let out = tmp.join("shadow_agents.yaml");
    let shared = tmp.join("shared");
    std::fs::create_dir_all(&shared).unwrap();
    std::fs::create_dir_all(tmp.join("scripts")).unwrap();
    let mut config = config_loader::load_config(&cfg_path).expect("fixture loads");
    config.general.shared_dir = shared.to_string_lossy().to_string();
    config.general.daemon_data_dir = "/tmp".to_string();
    orchestrator::generate_agent_shadow_config(&config, &out).expect("orchestrator generates");
    std::fs::read_to_string(&out)
        .unwrap()
        .replace(tmp.to_string_lossy().as_ref(), "TMPDIR")
}

#[test]
fn declared_seeds_generate_the_same_config_as_injected_seeds() {
    let base = std::fs::read_to_string("tests/fixtures/quickstart.yaml").unwrap();
    assert!(
        !base.contains("monero-seed-"),
        "fixture must rely on auto injection"
    );
    // quickstart.yaml ends with its agents: block, so appended entries land there.
    let mut declared = base.clone();
    if !declared.ends_with('\n') {
        declared.push('\n');
    }
    for i in 0..6 {
        declared.push_str(&format!(
            "  monero-seed-{:03}:\n    daemon: monerod\n    start_time: {}s\n",
            i + 1,
            i
        ));
    }

    let a = TempDir::new().unwrap();
    let b = TempDir::new().unwrap();
    let injected = generate(&base, a.path());
    let explicit = generate(&declared, b.path());
    assert!(injected.contains("monero-seed-006"));
    assert_eq!(injected, explicit);
}
