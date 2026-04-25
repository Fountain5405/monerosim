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
//! `general.seed_nodes`:
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

use crate::config_v2::{AgentConfig, AgentDefinitions, DaemonConfig, SeedNodesMode};
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
    mode: SeedNodesMode,
    user_agents: &AgentDefinitions,
    ip_registry: &mut GlobalIpRegistry,
    repo_dir: &Path,
) -> (AgentDefinitions, usize) {
    if matches!(mode, SeedNodesMode::Off) {
        return (clone_agent_definitions(user_agents), 0);
    }

    let ips = resolve_fallback_ips(repo_dir);

    match mode {
        SeedNodesMode::Off => unreachable!(),
        SeedNodesMode::Auto => prepare_auto(&ips, user_agents, ip_registry),
        SeedNodesMode::Custom => prepare_custom(&ips, user_agents, ip_registry),
    }
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
    MONERO_FALLBACK_SEED_IPS.iter().map(|s| s.to_string()).collect()
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
                    ip, agent_id, e
                );
                continue;
            }
            mark_as_seed_node(cfg);
            pinned += 1;
            continue;
        }

        // Otherwise inject a synthesized daemon-only seed.
        if let Err(e) = ip_registry.register_pre_allocated_ip(ip, &agent_id) {
            log::warn!(
                "Could not reserve fallback IP {} for {}: {}. Skipping.",
                ip, agent_id, e
            );
            continue;
        }
        agents.agents.insert(agent_id.clone(), build_seed_agent());
        pinned += 1;
    }

    if pinned > 0 {
        log::info!(
            "Auto-injected {} Monero fallback-seed hosts (monero-seed-001..{:03})",
            pinned, pinned
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
            log::warn!(
                "Could not pin fallback IP {} to {}: {}",
                ip, agent_id, e
            );
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
fn build_seed_agent() -> AgentConfig {
    let mut attrs = BTreeMap::new();
    attrs.insert("is_seed_node".to_string(), "true".to_string());
    AgentConfig {
        daemon: Some(DaemonConfig::Local("monerod".to_string())),
        wallet: None,
        script: None,
        daemon_options: None,
        wallet_options: None,
        start_time: Some("0s".to_string()),
        hashrate: None,
        transaction_interval: None,
        activity_start_time: None,
        can_receive_distributions: None,
        wait_time: None,
        initial_fund_amount: None,
        max_transaction_amount: None,
        min_transaction_amount: None,
        transaction_frequency: None,
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
    }
}

fn clone_agent_definitions(src: &AgentDefinitions) -> AgentDefinitions {
    AgentDefinitions {
        agents: src.agents.iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect::<BTreeMap<_, _>>(),
    }
}
