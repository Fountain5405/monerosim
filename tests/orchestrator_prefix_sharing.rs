// tests/orchestrator_prefix_sharing.rs
//
// Gap G5 (honest prefix sharing): generates a small scenario with
// `network.distribution.prefix_sharing` and checks the resulting
// `network_node_id` assignments in the generated shadow_agents.yaml.
use monerosim::{config_loader, orchestrator};
use std::collections::HashMap;
use std::path::Path;
use tempfile::TempDir;

#[test]
fn prefix_sharing_colocates_relays_and_keeps_the_pin_exclusive() {
    std::env::set_var("MONEROSIM_SKIP_SIM_BINARY_CHECK", "1");
    let tmp = TempDir::new().unwrap();
    let output_yaml = tmp.path().join("shadow_agents.yaml");
    let shared_dir = tmp.path().join("shared");
    std::fs::create_dir_all(&shared_dir).unwrap();
    std::fs::create_dir_all(tmp.path().join("scripts")).unwrap();

    let mut config = config_loader::load_config(Path::new("tests/fixtures/prefix_sharing.yaml"))
        .expect("prefix_sharing fixture loads");
    config.general.shared_dir = shared_dir.to_string_lossy().to_string();

    orchestrator::generate_agent_shadow_config(&config, &output_yaml)
        .expect("orchestrator generates");

    let doc: serde_yaml::Value =
        serde_yaml::from_str(&std::fs::read_to_string(&output_yaml).unwrap()).unwrap();
    let hosts = doc
        .get("hosts")
        .and_then(|h| h.as_mapping())
        .expect("hosts mapping");

    // node id -> agent names placed there, for the pin and the 20 relays.
    let mut node_of_pin: Option<u64> = None;
    let mut relay_nodes: HashMap<u64, Vec<String>> = HashMap::new();

    for (k, v) in hosts {
        let name = k.as_str().unwrap_or("");
        let nid = match v.get("network_node_id").and_then(|n| n.as_u64()) {
            Some(n) => n,
            None => continue,
        };
        if name.contains("pinned-bridge") {
            node_of_pin = Some(nid);
        } else if name.starts_with("relay-") {
            relay_nodes.entry(nid).or_default().push(name.to_string());
        }
    }

    let node_of_pin = node_of_pin.expect("pinned-bridge host present");
    assert_eq!(node_of_pin, 5, "pinned-bridge must land on its pinned node 5");

    // The pinned node must never also host a relay (exclusivity).
    assert!(
        !relay_nodes.contains_key(&node_of_pin),
        "node {node_of_pin} is pinned but also holds relay(s): {:?}",
        relay_nodes.get(&node_of_pin)
    );

    // fraction 1.0, per_prefix 4, over 20 eligible relays => exactly 5 shared
    // nodes of 4 relays each, none of them node 5.
    let shared: Vec<(&u64, &Vec<String>)> =
        relay_nodes.iter().filter(|(_, v)| v.len() > 1).collect();
    assert_eq!(shared.len(), 5, "expected 5 shared /24 nodes, got {shared:?}");
    for (node, members) in &shared {
        assert_eq!(members.len(), 4, "node {node} must hold exactly 4 relays");
    }
    let total_shared: usize = shared.iter().map(|(_, v)| v.len()).sum();
    assert_eq!(total_shared, 20, "all 20 relays must be accounted for");
}
