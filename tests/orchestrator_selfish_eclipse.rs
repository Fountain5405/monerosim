// tests/orchestrator_selfish_eclipse.rs — the peers/eclipsed peer-pinning
// knobs (experiment 3, eclipse x selfish composition).
use monerosim::{config_loader, orchestrator};
use regex::Regex;
use std::path::Path;
use tempfile::TempDir;

fn normalize(yaml: &str) -> String {
    let yaml = Regex::new(r"/tmp/[A-Za-z0-9_.-]+/")
        .unwrap()
        .replace_all(yaml, "TMPDIR/")
        .into_owned();
    let cwd = std::env::current_dir().unwrap().to_string_lossy().to_string();
    let yaml = yaml.replace(&cwd, "REPO_ROOT");
    if let Ok(home) = std::env::var("HOME") {
        if !home.is_empty() {
            return yaml.replace(&home, "HOME");
        }
    }
    yaml
}

/// The full generated yaml block for one host: from its `  <host>:` line to
/// the next host key, any column-0 key, or end of file. Line-scanned rather
/// than regex-extracted because the regex crate has no look-around.
fn host_block(yaml: &str, host: &str) -> String {
    let needle = format!("  {}:", host);
    let mut out: Vec<&str> = Vec::new();
    let mut in_block = false;
    for line in yaml.lines() {
        if !in_block {
            if line == needle {
                in_block = true;
            }
            continue;
        }
        let trimmed = line.trim_end();
        let is_next_host = line.starts_with("  ")
            && trimmed.ends_with(':')
            && !trimmed.contains(' ')
            && line[2..].starts_with(|c: char| !c.is_whitespace());
        let is_top_level = !line.is_empty() && !line.starts_with(' ');
        if is_next_host || is_top_level {
            break;
        }
        out.push(line);
    }
    out.join("\n")
}

/// Extract the `ip_addr` of a named host block from the generated yaml.
fn host_ip(yaml: &str, host: &str) -> String {
    let block = host_block(yaml, host);
    Regex::new(r"ip_addr: (\S+)")
        .unwrap()
        .captures(&block)
        .map(|c| c[1].to_string())
        .unwrap_or_default()
}

/// The named host's daemon arg lines: from its monerod path line to the
/// `environment:` key — the surface the pins/isolation assertions read.
fn host_args(yaml: &str, host: &str) -> String {
    let block = host_block(yaml, host);
    let mut out = String::new();
    let mut in_args = false;
    for line in block.lines() {
        if !in_args {
            if line.contains("monerod") {
                in_args = true;
            }
            continue;
        }
        if line.trim_start().starts_with("environment:") {
            break;
        }
        out.push_str(line);
        out.push('\n');
    }
    out
}

#[test]
fn eclipse_fixture_pins_and_isolates() {
    std::env::set_var("MONEROSIM_SKIP_SIM_BINARY_CHECK", "1");
    let tmp = TempDir::new().unwrap();
    let output_yaml = tmp.path().join("shadow_agents.yaml");
    let shared_dir = tmp.path().join("shared");
    std::fs::create_dir_all(&shared_dir).unwrap();
    std::fs::create_dir_all(tmp.path().join("scripts")).unwrap();

    let mut config =
        config_loader::load_config(Path::new("tests/fixtures/selfish_eclipse.yaml"))
            .expect("eclipse fixture loads");
    config.general.shared_dir = shared_dir.to_string_lossy().to_string();

    orchestrator::generate_agent_shadow_config(&config, &output_yaml)
        .expect("orchestrator generates");

    let actual = normalize(&std::fs::read_to_string(&output_yaml).unwrap());

    let island_ip = host_ip(&actual, "attacker-island");
    assert!(!island_ip.is_empty(), "island host found");
    let victim_ip = host_ip(&actual, "victim-001");
    assert!(!victim_ip.is_empty(), "victim host found");

    // The victim: exclusive-pinned to the island's resolved ip:port, refuses
    // inbound, still mines (mining knobs intact).
    let victim_args = host_args(&actual, "victim-001");
    assert!(
        victim_args.contains(&format!("--add-exclusive-node={}:18080", island_ip)),
        "victim exclusively dials the island, got: {victim_args}"
    );
    assert!(victim_args.contains("--in-peers=0"), "victim refuses inbound");
    assert!(
        actual.contains("--sim-hash-interval-ms=333"),
        "victim (3 h/s) still mines natively"
    );
    assert!(
        !victim_args.contains("--seed-node="),
        "victim gets no seed list"
    );
    assert!(
        !victim_args.contains("--add-priority-node"),
        "victim gets no ring/seed links"
    );

    // The island: bootstraps nowhere (no seed list, no pins of its own).
    let island_args = host_args(&actual, "attacker-island");
    assert!(
        !island_args.contains("--seed-node=") && !island_args.contains("--add-priority-node"),
        "island is P2P-isolated except for pinned victims' inbound, got: {island_args}"
    );

    // Everyone else: relays' seed lists contain the two free-side miners but
    // NOT the eclipsed victim.
    let relay_args = host_args(&actual, "relay-001");
    assert!(
        !relay_args.contains(&format!("--seed-node={}:18080", victim_ip)),
        "victim absent from relay seed lists"
    );
    assert!(
        relay_args.contains("--seed-node="),
        "relay still bootstraps against miners"
    );

    // Victim wrapper: the eclipsed attribute rides along (analysis reads it
    // for controlled-share attribution).
    let wrappers_dir = tmp.path().join("scripts");
    let mut wrappers = String::new();
    for entry in std::fs::read_dir(&wrappers_dir).unwrap() {
        wrappers.push_str(&std::fs::read_to_string(entry.unwrap().path()).unwrap());
    }
    assert!(wrappers.contains("eclipsed"), "eclipsed attribute passed through");
    assert!(wrappers.contains("islands"), "islands attribute passed to attacker");
}

#[test]
fn peers_reference_to_unknown_agent_is_rejected() {
    std::env::set_var("MONEROSIM_SKIP_SIM_BINARY_CHECK", "1");
    let tmp = TempDir::new().unwrap();
    let output_yaml = tmp.path().join("shadow_agents.yaml");
    let shared_dir = tmp.path().join("shared");
    std::fs::create_dir_all(&shared_dir).unwrap();
    std::fs::create_dir_all(tmp.path().join("scripts")).unwrap();

    let bad = r#"
general:
  stop_time: 5m
  simulation_seed: 1
  mining:
    mode: native
network:
  path: gml_processing/1200_nodes_caida_with_loops.gml
  peer_mode: Dynamic
agents:
  miner-001:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    hashrate: 5
    peers:
      exclusive:
      - no-such-agent
"#;
    let cfg_path = tmp.path().join("bad.yaml");
    std::fs::write(&cfg_path, bad).unwrap();
    let mut config = config_loader::load_config(&cfg_path).expect("bad config parses");
    config.general.shared_dir = shared_dir.to_string_lossy().to_string();

    let err = orchestrator::generate_agent_shadow_config(&config, &output_yaml)
        .err()
        .expect("unknown peers reference must fail generation");
    assert!(
        err.to_string().contains("unknown agent 'no-such-agent'"),
        "error names the bad reference: {err}"
    );
}
