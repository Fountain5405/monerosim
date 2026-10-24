// tests/orchestrator_script_pins.rs
//
// `topology_node` on script-only agents (e.g. eclipse fake peers): the pin is
// honoured and validated like a daemon pin, and every agent pinned to a node
// gets an address inside that node's /24.
use monerosim::{config_loader, orchestrator};
use std::collections::HashSet;
use tempfile::TempDir;

/// Generate a Shadow config from inline YAML. Returns the `hosts` mapping, or
/// the generator's error.
fn generate(yaml: &str) -> Result<serde_yaml::Mapping, String> {
    std::env::set_var("MONEROSIM_SKIP_SIM_BINARY_CHECK", "1");
    let tmp = TempDir::new().unwrap();
    let config_path = tmp.path().join("config.yaml");
    std::fs::write(&config_path, yaml).unwrap();
    let output_yaml = tmp.path().join("shadow_agents.yaml");
    let shared_dir = tmp.path().join("shared");
    std::fs::create_dir_all(&shared_dir).unwrap();
    std::fs::create_dir_all(tmp.path().join("scripts")).unwrap();

    let mut config = config_loader::load_config(&config_path).map_err(|e| format!("{e:?}"))?;
    config.general.shared_dir = shared_dir.to_string_lossy().to_string();
    config.general.daemon_data_dir = "/tmp".to_string();
    orchestrator::generate_agent_shadow_config(&config, &output_yaml)
        .map_err(|e| format!("{e:?}"))?;

    let doc: serde_yaml::Value =
        serde_yaml::from_str(&std::fs::read_to_string(&output_yaml).unwrap()).unwrap();
    Ok(doc
        .get("hosts")
        .and_then(|h| h.as_mapping())
        .expect("hosts mapping")
        .clone())
}

fn node_of(hosts: &serde_yaml::Mapping, id: &str) -> u64 {
    hosts
        .get(id)
        .and_then(|h| h.get("network_node_id"))
        .and_then(|n| n.as_u64())
        .unwrap_or_else(|| panic!("host {id} has a network_node_id"))
}

fn ip_of(hosts: &serde_yaml::Mapping, id: &str) -> String {
    hosts
        .get(id)
        .and_then(|h| h.get("ip_addr"))
        .and_then(|n| n.as_str())
        .unwrap_or_else(|| panic!("host {id} has an ip_addr"))
        .to_string()
}

fn slash24(ip: &str) -> &str {
    &ip[..ip.rfind('.').unwrap()]
}

/// A GML run with one daemon pinned well away from the nodes the tests use.
const GML_HEADER: &str = "\
general:
  stop_time: 10m
  simulation_seed: 12345
  enable_dns_server: true
network:
  path: gml_processing/1200_nodes_caida_with_loops.gml
  peer_mode: Dynamic
agents:
  plain-node:
    daemon: monerod
    start_time: 0s
    topology_node: 3
";

/// Same, without the auto fallback seeds, so node 600 holds only what a test
/// pins there.
const QUIET_GML_HEADER: &str = "\
general:
  stop_time: 10m
  simulation_seed: 12345
  enable_dns_server: true
  fallback_seeds: off
network:
  path: gml_processing/1200_nodes_caida_with_loops.gml
  peer_mode: Dynamic
agents:
  plain-node:
    daemon: monerod
    start_time: 0s
    topology_node: 3
";

fn fleet(n: usize, pin: u32) -> String {
    (1..=n)
        .map(|k| fake_peer(&format!("fake-{k:03}"), Some(pin)))
        .collect()
}

fn fake_peer(id: &str, pin: Option<u32>) -> String {
    let mut s = format!("  {id}:\n    script: agents.eclipse_fakepeer\n    start_time: 60s\n");
    if let Some(n) = pin {
        s.push_str(&format!("    topology_node: {n}\n"));
    }
    s.push_str("    attributes:\n      eclipse_role: attacker\n");
    s
}

#[test]
fn pinned_script_agents_land_on_their_node_and_share_its_slash24() {
    let yaml = format!(
        "{GML_HEADER}{}{}{}",
        fake_peer("fake-001", Some(500)),
        fake_peer("fake-002", Some(500)),
        fake_peer("fake-003", None)
    );
    let hosts = generate(&yaml).expect("generates");

    assert_eq!(node_of(&hosts, "fake-001"), 500);
    assert_eq!(node_of(&hosts, "fake-002"), 500);
    let (a, b) = (ip_of(&hosts, "fake-001"), ip_of(&hosts, "fake-002"));
    assert_ne!(a, b, "co-located agents still get distinct addresses");
    assert_eq!(
        slash24(&a),
        slash24(&b),
        "agents pinned to one node share its /24"
    );
    assert_ne!(
        node_of(&hosts, "fake-003"),
        500,
        "an unpinned script agent is not moved onto the pinned node"
    );
}

#[test]
fn script_agent_pin_to_a_missing_node_is_an_error() {
    let yaml = format!("{GML_HEADER}{}", fake_peer("fake-001", Some(999_999)));
    let Err(err) = generate(&yaml) else {
        panic!("a pin to a node that is not in the GML must fail");
    };
    assert!(
        err.contains("fake-001") && err.contains("999999"),
        "error names the agent and the node: {err}"
    );
}

#[test]
fn script_agent_pin_without_a_gml_topology_is_an_error() {
    let yaml = format!(
        "general:\n  stop_time: 10m\n  simulation_seed: 12345\n\
         network:\n  type: 1_gbit_switch\n  peer_mode: Dynamic\n\
         agents:\n  plain-node:\n    daemon: monerod\n    start_time: 0s\n{}",
        fake_peer("fake-001", Some(1))
    );
    let Err(err) = generate(&yaml) else {
        panic!("a pin needs a GML topology to pin to");
    };
    assert!(
        err.contains("fake-001") && err.contains("GML"),
        "error names the agent and the missing GML: {err}"
    );
}

#[test]
fn a_node_takes_245_pinned_script_agents_in_its_slash24() {
    // A node's /24 hands out .10-.254: 245 addresses.
    let hosts = generate(&format!("{QUIET_GML_HEADER}{}", fleet(245, 600)))
        .expect("245 agents fit in one node's /24");
    let subnets: HashSet<String> = (1..=245)
        .map(|k| slash24(&ip_of(&hosts, &format!("fake-{k:03}"))).to_string())
        .collect();
    assert_eq!(
        subnets.len(),
        1,
        "all 245 share node 600's /24: {subnets:?}"
    );
}

#[test]
fn pinning_more_agents_than_a_node_slash24_holds_is_an_error() {
    let Err(err) = generate(&format!("{QUIET_GML_HEADER}{}", fleet(246, 600))) else {
        panic!("the 246th agent on one node must not silently get an address outside its /24");
    };
    assert!(
        err.contains("fake-246") && err.contains("topology_node=600"),
        "error names the overflowing agent and the node: {err}"
    );
}
