// tests/orchestrator_topology_pins.rs
use monerosim::{config_loader, orchestrator};
use std::path::Path;
use tempfile::TempDir;

#[test]
fn topology_node_pins_agent_to_gml_node() {
    std::env::set_var("MONEROSIM_SKIP_SIM_BINARY_CHECK", "1");
    let tmp = TempDir::new().unwrap();
    let output_yaml = tmp.path().join("shadow_agents.yaml");
    let shared_dir = tmp.path().join("shared");
    std::fs::create_dir_all(&shared_dir).unwrap();
    std::fs::create_dir_all(tmp.path().join("scripts")).unwrap();

    let mut config = config_loader::load_config(Path::new("tests/fixtures/topology_pins.yaml"))
        .expect("topology_pins fixture loads");
    config.general.shared_dir = shared_dir.to_string_lossy().to_string();

    orchestrator::generate_agent_shadow_config(&config, &output_yaml)
        .expect("orchestrator generates");

    let doc: serde_yaml::Value =
        serde_yaml::from_str(&std::fs::read_to_string(&output_yaml).unwrap()).unwrap();
    let hosts = doc.get("hosts").and_then(|h| h.as_mapping()).expect("hosts mapping");

    let mut checked = 0;
    for (k, v) in hosts {
        let name = k.as_str().unwrap_or("");
        if name.contains("pinned-bridge") {
            let nid = v
                .get("network_node_id")
                .and_then(|n| n.as_u64())
                .expect("pinned host has network_node_id");
            assert_eq!(nid, 5, "pinned-bridge host '{name}' must be at node 5");
            checked += 1;
        }
    }
    assert!(checked > 0, "pinned-bridge host present in generated config");
}
