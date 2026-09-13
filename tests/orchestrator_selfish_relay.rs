// tests/orchestrator_selfish_relay.rs
// Proves the config-only wiring for the sim-relay-alt-blocks flag: a bridge with
// `daemon: monerod-hf` + `daemon_options: {sim-relay-alt-blocks: true}` emits the
// flag and resolves to the patched monerod-hf binary in the generated Shadow YAML.
use monerosim::{config_loader, orchestrator};
use std::path::Path;
use tempfile::TempDir;

#[test]
fn selfish_relay_bridge_emits_flag_and_patched_binary() {
    std::env::set_var("MONEROSIM_SKIP_SIM_BINARY_CHECK", "1");
    let tmp = TempDir::new().unwrap();
    let output_yaml = tmp.path().join("shadow_agents.yaml");
    let shared_dir = tmp.path().join("shared");
    std::fs::create_dir_all(&shared_dir).unwrap();
    std::fs::create_dir_all(tmp.path().join("scripts")).unwrap();

    let mut config = config_loader::load_config(Path::new("tests/fixtures/selfish_relay.yaml"))
        .expect("selfish_relay fixture loads");
    config.general.shared_dir = shared_dir.to_string_lossy().to_string();

    orchestrator::generate_agent_shadow_config(&config, &output_yaml)
        .expect("orchestrator generates");

    let actual = std::fs::read_to_string(&output_yaml).unwrap();

    // The relay flag is rendered as a bare flag by options_to_args (Bool(true)).
    let flag_count = actual.matches("--sim-relay-alt-blocks").count();
    assert!(flag_count >= 1, "relay flag emitted for at least one bridge");

    // Bridges resolve to the patched binary via the monerod-hf symlink alias.
    assert!(actual.contains(".monerosim/bin/monerod-hf"),
            "relay bridge daemon resolves to the monerod-hf (monerod-sim) binary");

    // Exactly the bridges get the flag: count matches monerod-hf daemon occurrences.
    let hf_count = actual.matches(".monerosim/bin/monerod-hf").count();
    assert_eq!(flag_count, hf_count,
               "the relay flag appears on exactly the monerod-hf (bridge) daemons, nowhere else");
}
