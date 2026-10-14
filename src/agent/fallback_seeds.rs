//! Fallback seed-node management.
//!
//! Monero's binary contains a hardcoded list of fallback seed IPs at
//! `src/p2p/net_node.inl`. When DNS seeds and configured `--seed-node`
//! peers fail to provide enough connections, monerod tries those IPs
//! directly. In Shadow's virtual network those real-internet IPs don't
//! resolve, producing `Attempting to connect to address 'X' for which
//! no host exists` warnings.
//!
//! This module pins those IPs to dedicated in-sim hosts so the fallback
//! path resolves inside the simulation. Behavior is controlled by
//! `general.fallback_seeds`:
//!
//! - `Auto`: 6 daemon-only hosts named `monero-seed-001..006` are
//!   auto-injected, each pinned to one fallback IP.
//! - `Custom`: agents named `monero-seed-NNN` declared by the user are
//!   pinned to fallback IPs in declaration order.
//! - `Off`: no pinning; legacy behavior.
//!
//! Pre-registration in the IP registry happens before the main agent
//! allocation loop runs, so `get_agent_ip()` returns the pinned IP via
//! its Priority 0 lookup.

use std::collections::BTreeMap;
use std::path::Path;

use crate::config::{AgentConfig, AgentDefinitions, DaemonConfig, FallbackSeedsMode};
use crate::ip::GlobalIpRegistry;
use crate::utils::extract_mainnet_seed_ips_from_repo;
use crate::{fallback_seed_agent_id, MONERO_FALLBACK_SEED_IPS};

/// Process fallback-seed configuration: pre-register pinned IPs and, in
/// auto mode, return an `AgentDefinitions` containing the synthesized
/// seed agents.
///
/// `repo_dir` is the monerosim repository root, used to find the Monero
/// source tree for live IP extraction. If extraction fails (e.g., no
/// source on disk), we fall back to the baked-in
/// `MONERO_FALLBACK_SEED_IPS` constant.
///
/// Returns `(effective_agents, pinned_count)` — `pinned_count` is the
/// number of fallback IPs actually claimed (for logging).
pub fn prepare_fallback_seeds(
    mode: FallbackSeedsMode,
    user_agents: &AgentDefinitions,
    ip_registry: &mut GlobalIpRegistry,
    repo_dir: &Path,
) -> (AgentDefinitions, usize) {
    if matches!(mode, FallbackSeedsMode::Off) {
        return (clone_agent_definitions(user_agents), 0);
    }

    let ips = resolve_fallback_ips(repo_dir);

    let (agents, pinned) = match mode {
        FallbackSeedsMode::Off => unreachable!(),
        FallbackSeedsMode::Auto => prepare_auto(&ips, user_agents, ip_registry),
        FallbackSeedsMode::Custom => prepare_custom(&ips, user_agents, ip_registry),
    };
    if let Some(msg) = stock_seed_warning(&agents) {
        log::warn!("{}", msg);
    }
    (agents, pinned)
}

/// Warn when the fallback seeds run stock `monerod` but no other daemon
/// does: stock seeds can reject a modified network's blocks (stock monerod
/// rejects SoP blocks with fewer than 16 workshares on its hard-fork vote
/// check). Compares the `daemon` field only;
/// `daemon_phases` are ignored, so upgrade configs that start everyone on
/// `monerod` stay quiet. `Remote` and daemon-less agents are not counted.
pub fn stock_seed_warning(agents: &AgentDefinitions) -> Option<String> {
    let is_seed =
        |id: &str| (1..=MONERO_FALLBACK_SEED_IPS.len()).any(|n| fallback_seed_agent_id(n) == id);
    let local_binary = |cfg: &AgentConfig| match &cfg.daemon {
        Some(DaemonConfig::Local(b)) => Some(b.clone()),
        _ => None,
    };

    let stock_seeds: Vec<&str> = agents
        .agents
        .iter()
        .filter(|(id, cfg)| is_seed(id) && local_binary(cfg).as_deref() == Some("monerod"))
        .map(|(id, _)| id.as_str())
        .collect();
    if stock_seeds.is_empty() {
        return None;
    }
    let others: std::collections::BTreeSet<String> = agents
        .agents
        .iter()
        .filter(|(id, _)| !is_seed(id))
        .filter_map(|(_, cfg)| local_binary(cfg))
        .collect();
    if others.is_empty() || others.contains("monerod") {
        return None;
    }
    let example = others.iter().next().cloned().unwrap_or_default();
    Some(format!(
        "Fallback seeds {} run stock monerod, but every other daemon runs {}. \
         Stock seeds may reject this network's blocks. To give the seeds the \
         network's binary, declare them in the scenario:\n  \
         monero-seed-{{001..006}}:\n    daemon: {}\n    start_time: 0s\n    \
         start_time_stagger: 1s",
        stock_seeds.join(", "),
        others.into_iter().collect::<Vec<_>>().join(", "),
        example
    ))
}

/// Try to extract IPs from the live Monero source; fall back to the
/// hardcoded constant if the source isn't reachable.
fn resolve_fallback_ips(repo_dir: &Path) -> Vec<String> {
    if let Some(ips) = extract_mainnet_seed_ips_from_repo(repo_dir) {
        if !ips.is_empty() {
            return ips;
        }
        log::warn!("Source extraction returned no IPs; falling back to hardcoded list");
    } else {
        log::info!(
            "Could not locate Monero source tree (set MONERO_SRC_DIR or place source at <repo>/sibling_repos/monero); using hardcoded fallback IP list"
        );
    }
    MONERO_FALLBACK_SEED_IPS
        .iter()
        .map(|s| s.to_string())
        .collect()
}

fn prepare_auto(
    ips: &[String],
    user_agents: &AgentDefinitions,
    ip_registry: &mut GlobalIpRegistry,
) -> (AgentDefinitions, usize) {
    let mut agents = clone_agent_definitions(user_agents);
    let mut pinned = 0;

    for (i, ip) in ips.iter().enumerate() {
        let agent_id = fallback_seed_agent_id(i + 1);

        // If the user already declared a host with this name, leave it
        // alone — they've effectively switched to custom mode for that
        // slot. Still pin its IP and stamp it as a seed node so the DNS
        // server picks it up.
        if let Some(cfg) = agents.agents.get_mut(&agent_id) {
            if let Err(e) = ip_registry.register_pre_allocated_ip(ip, &agent_id) {
                log::warn!(
                    "Could not pin fallback IP {} to user-declared {}: {}",
                    ip,
                    agent_id,
                    e
                );
                continue;
            }
            mark_as_seed_node(cfg);
            pinned += 1;
            continue;
        }

        // Otherwise inject a synthesized daemon-only seed. Start time
        // is staggered (0s, 1s, 2s, ...) to match the miner pattern
        // and avoid all 6 daemons booting on the same simulated tick.
        if let Err(e) = ip_registry.register_pre_allocated_ip(ip, &agent_id) {
            log::warn!(
                "Could not reserve fallback IP {} for {}: {}. Skipping.",
                ip,
                agent_id,
                e
            );
            continue;
        }
        agents.agents.insert(agent_id.clone(), build_seed_agent(i));
        pinned += 1;
    }

    if pinned > 0 {
        log::info!(
            "Auto-injected {} Monero fallback-seed hosts (monero-seed-001..{:03})",
            pinned,
            pinned
        );
    }
    (agents, pinned)
}

fn prepare_custom(
    ips: &[String],
    user_agents: &AgentDefinitions,
    ip_registry: &mut GlobalIpRegistry,
) -> (AgentDefinitions, usize) {
    let mut agents = clone_agent_definitions(user_agents);
    let mut pinned = 0;

    // Walk the slots in canonical order; pin only the slots the user
    // actually declared. (BTreeMap iterates in key order, so
    // `monero-seed-001` < `monero-seed-002` < ...)
    for (i, ip) in ips.iter().enumerate() {
        let agent_id = fallback_seed_agent_id(i + 1);
        let Some(cfg) = agents.agents.get_mut(&agent_id) else {
            continue;
        };
        if let Err(e) = ip_registry.register_pre_allocated_ip(ip, &agent_id) {
            log::warn!("Could not pin fallback IP {} to {}: {}", ip, agent_id, e);
            continue;
        }
        mark_as_seed_node(cfg);
        pinned += 1;
    }

    if pinned > 0 {
        log::info!(
            "Pinned {} user-declared fallback-seed hosts to Monero IPs",
            pinned
        );
    }
    (agents, pinned)
}

/// Stamp `is_seed_node = "true"` onto the agent's attributes so the
/// agent registry exposes it and the DNS server can prefer these hosts
/// over miners when answering Monero seed-domain queries.
fn mark_as_seed_node(cfg: &mut AgentConfig) {
    let attrs = cfg.attributes.get_or_insert_with(BTreeMap::new);
    attrs.insert("is_seed_node".to_string(), "true".to_string());
}

/// Build a daemon-only `AgentConfig` for a synthesized seed host.
/// All other fields default to `None` so it behaves like a minimal relay.
/// `seed_index` (0..5 for the 6 fallback slots) is used to stagger
/// daemon start times so they come up on consecutive simulated seconds
/// rather than all on tick 0.
fn build_seed_agent(seed_index: usize) -> AgentConfig {
    let mut attrs = BTreeMap::new();
    attrs.insert("is_seed_node".to_string(), "true".to_string());
    AgentConfig {
        daemon: Some(DaemonConfig::Local("monerod".to_string())),
        wallet: None,
        script: None,
        daemon_options: None,
        wallet_options: None,
        start_time: Some(format!("{}s", seed_index)),
        hashrate: None,
        transaction_interval: None,
        activity_start_time: None,
        can_receive_distributions: None,
        wait_time: None,
        initial_fund_amount: None,
        max_transaction_amount: None,
        min_transaction_amount: None,
        md_n_recipients: None,
        md_out_per_tx: None,
        md_output_amount: None,
        poll_interval: None,
        status_file: None,
        enable_alerts: None,
        detailed_logging: None,
        daemon_phases: None,
        wallet_phases: None,
        daemon_args: None,
        wallet_args: None,
        daemon_env: None,
        wallet_env: None,
        attributes: Some(attrs),
        subnet_group: None,
        topology_node: None,
        turnover: None,
        peers: None,
    }
}

fn clone_agent_definitions(src: &AgentDefinitions) -> AgentDefinitions {
    AgentDefinitions {
        agents: src
            .agents
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect::<BTreeMap<_, _>>(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn node(binary: &str) -> AgentConfig {
        let mut a = build_seed_agent(0);
        a.attributes = None;
        a.daemon = Some(DaemonConfig::Local(binary.to_string()));
        a
    }

    fn script_only() -> AgentConfig {
        let mut a = build_seed_agent(0);
        a.attributes = None;
        a.daemon = None;
        a.script = Some("agents.simulation_monitor".to_string());
        a
    }

    /// Six seeds on `seed_binary` plus the given non-seed agents.
    fn network(seed_binary: &str, others: Vec<(&str, AgentConfig)>) -> AgentDefinitions {
        let mut agents: BTreeMap<String, AgentConfig> = others
            .into_iter()
            .map(|(k, v)| (k.to_string(), v))
            .collect();
        for i in 0..6 {
            let mut seed = build_seed_agent(i);
            seed.daemon = Some(DaemonConfig::Local(seed_binary.to_string()));
            agents.insert(fallback_seed_agent_id(i + 1), seed);
        }
        AgentDefinitions { agents }
    }

    #[test]
    fn warning_fires_when_only_seeds_are_stock() {
        let d = network(
            "monerod",
            vec![("relay-001", node("monerod-sim")), ("relay-002", node("monerod-sim"))],
        );
        let msg = stock_seed_warning(&d).expect("should warn");
        assert!(msg.contains("monero-seed-001"));
        assert!(msg.contains("monero-seed-006"));
        assert!(msg.contains("daemon: monerod-sim"));
        assert!(msg.contains("monero-seed-{001..006}:"));
    }

    #[test]
    fn warning_silent_when_a_non_seed_runs_monerod() {
        let d = network(
            "monerod",
            vec![("relay-001", node("monerod-sim")), ("miner-001", node("monerod"))],
        );
        assert_eq!(stock_seed_warning(&d), None);
    }

    #[test]
    fn warning_silent_when_seeds_are_not_stock() {
        let d = network("monerod-sim", vec![("relay-001", node("monerod-sim"))]);
        assert_eq!(stock_seed_warning(&d), None);
    }

    #[test]
    fn warning_silent_without_non_seed_daemons() {
        let d = network("monerod", vec![("simulation-monitor", script_only())]);
        assert_eq!(stock_seed_warning(&d), None);
    }

    #[test]
    fn warning_ignores_remote_daemons() {
        let mut wallet = script_only();
        wallet.daemon = Some(DaemonConfig::Remote {
            address: "auto".to_string(),
            strategy: None,
        });
        let d = network("monerod", vec![("wallet-001", wallet)]);
        assert_eq!(stock_seed_warning(&d), None);
    }
}
