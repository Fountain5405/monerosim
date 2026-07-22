//! User agent processing.
//!
//! This module handles the configuration and processing of user agents,
//! including regular users and miners with their daemon and wallet settings.
//! It manages peer discovery, IP allocation, and process configuration for
//! user agents within the Shadow network simulator environment.

use crate::config::{AgentConfig, AgentDefinitions, DaemonConfig, OptionValue, PeerMode};
use crate::gml_parser::GmlGraph;
use crate::ip::{AsSubnetManager, GlobalIpRegistry};
use crate::process::{
    add_user_agent_process, add_wallet_process, build_wallet_args, create_mining_agent_process,
    DaemonAddress, MiningAgentProcessArgs, UserAgentProcessArgs, WalletProcessArgs,
};
use crate::shadow::{ExpectedFinalState, ShadowHost};
use crate::topology::{
    build_peer_topology, distribute_agents_across_topology, generate_topology_connections,
    PeerTopology, Topology,
};
use crate::utils::binary::resolve_binary_path_for_shadow;
use crate::utils::duration::parse_duration_to_seconds;
use crate::utils::options::{merge_options, options_to_args, translate_daemon_log_level};
use std::collections::{BTreeMap, HashSet};
use std::path::Path;

/// Context bundle for `process_user_agents`.
pub struct UserAgentProcessContext<'a> {
    pub agents: &'a AgentDefinitions,
    pub hosts: &'a mut BTreeMap<String, ShadowHost>,
    pub seed_agents: &'a mut Vec<String>,
    pub subnet_manager: &'a mut AsSubnetManager,
    pub ip_registry: &'a mut GlobalIpRegistry,
    pub monerod_path: &'a str,
    pub wallet_path: &'a str,
    pub environment: &'a BTreeMap<String, String>,
    pub monero_environment: &'a BTreeMap<String, String>,
    pub shared_dir: &'a Path,
    pub current_dir: &'a str,
    pub gml_graph: Option<&'a GmlGraph>,
    pub using_gml_topology: bool,
    pub peer_mode: &'a PeerMode,
    pub topology: Option<&'a Topology>,
    pub enable_dns_server: bool,
    pub daemon_defaults: Option<&'a BTreeMap<String, OptionValue>>,
    pub wallet_defaults: Option<&'a BTreeMap<String, OptionValue>>,
    pub distribution_strategy: Option<&'a crate::config::DistributionStrategy>,
    pub distribution_weights: Option<&'a crate::config::RegionWeights>,
    pub scripts_dir: &'a Path,
    pub daemon_data_dir: &'a str,
    /// Deterministic seed for selecting which nodes are unreachable.
    pub simulation_seed: u64,
    /// Global fraction of non-seed nodes that are reachable (1.0 = all).
    pub reachable_fraction: f64,
    /// Per-role overrides for `reachable_fraction` (override semantics).
    pub reachable_by_role: Option<&'a BTreeMap<String, f64>>,
    /// Global fraction of non-seed nodes that run `--hide-my-port` (0.0 = none).
    pub hidden_fraction: f64,
    /// Simulation stop time in seconds — bounds turnover session generation.
    pub simulation_stop_secs: u64,
    /// Peer-turnover config (None = no turnover; relays stay always-on).
    pub turnover: Option<&'a crate::config::TurnoverConfig>,
}

/// Process user agents
/// Stable FNV-1a hash of (seed, id) — deterministic and reproducible
/// without depending on std's (unstable across versions) hasher, so the
/// same binary + seed always selects the same unreachable nodes.
fn seeded_hash(seed: u64, s: &str) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325 ^ seed;
    for b in s.bytes() {
        h ^= b as u64;
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }
    h
}

/// Decide which non-seed agents are unreachable (get `--hide-my-port`).
/// Roles: `user` (has a wallet) and `relay` (daemon-only). Seeds and miners
/// are always reachable and excluded entirely (bootstrap backbone). `reachable`
/// is the global fraction; `by_role` overrides it per role (override semantics,
/// NOT multiply). For each role, `round((1 - r) * count)` agents are marked
/// unreachable, chosen deterministically by seeded hash so runs reproduce.
fn compute_unreachable_set(
    user_agents: &[(&String, &AgentConfig)],
    seed: u64,
    reachable: f64,
    by_role: Option<&BTreeMap<String, f64>>,
) -> HashSet<String> {
    let mut by_role_ids: BTreeMap<&str, Vec<String>> = BTreeMap::new();
    for (id, cfg) in user_agents {
        let is_miner = cfg.is_miner();
        let is_seed = is_miner
            || cfg
                .attributes
                .as_ref()
                .map(|a| a.get("is_seed_node").map_or(false, |v| v == "true"))
                .unwrap_or(false);
        if is_seed {
            continue; // seeds + miners always reachable
        }
        let role = if cfg.has_wallet() { "user" } else { "relay" };
        by_role_ids.entry(role).or_default().push(id.to_string());
    }

    let mut unreachable = HashSet::new();
    for (role, mut ids) in by_role_ids {
        let r = by_role
            .and_then(|m| m.get(role))
            .copied()
            .unwrap_or(reachable)
            .clamp(0.0, 1.0);
        if r >= 1.0 {
            continue; // every node of this role stays reachable
        }
        ids.sort_by_key(|id| seeded_hash(seed, id));
        let n_unreach = (((1.0 - r) * ids.len() as f64).round() as usize).min(ids.len());
        for id in ids.into_iter().take(n_unreach) {
            unreachable.insert(id);
        }
    }
    unreachable
}

/// Map a seeded hash to a uniform float in (0, 1), nudged off the exact
/// endpoints so the inverse-CDF `ln()` below is always finite.
///
/// FNV-1a's avalanche in its *high* bits is poor when only the trailing byte
/// changes (e.g. the session index in `cs:<id>:<k>`), and we extract the top
/// 53 bits — so consecutive keys would otherwise yield near-identical draws
/// (every session the same length). Run the FNV output through a splitmix64
/// finalizer first: any 1-bit input change then flips ~half the output bits,
/// giving well-distributed top bits regardless of key layout.
fn seeded_unit(seed: u64, s: &str) -> f64 {
    let mut h = seeded_hash(seed, s);
    h ^= h >> 30;
    h = h.wrapping_mul(0xbf58_476d_1ce4_e5b9);
    h ^= h >> 27;
    h = h.wrapping_mul(0x94d0_49bb_1331_11eb);
    h ^= h >> 31;
    let u = (h >> 11) as f64 / (1u64 << 53) as f64; // top 53 bits → [0,1)
    u.clamp(1e-9, 1.0 - 1e-9)
}

/// Exponentially-distributed draw with the given `mean` (memoryless turnover),
/// clamped to [min, max]. Deterministic in (seed, key).
fn exp_draw(seed: u64, key: &str, mean: f64, min: f64, max: f64) -> f64 {
    let u = seeded_unit(seed, key);
    (-mean * (1.0 - u).ln()).clamp(min, max) // inverse-CDF of Exp(mean)
}

/// Decide which nodes participate in turnover. Eligible = every non-seed,
/// non-miner daemon node (relays AND users) that is NOT pinned always-on via
/// an explicit `hide-my-port: false` in its own daemon_options (the supernode
/// / infrastructure convention). Only the daemon cycles; a user's wallet-rpc
/// and tx-agent stay up and reconnect on restart (regular_user.py has
/// daemon-down recovery). `fraction` of the eligible set is selected
/// deterministically by a turnover-namespaced seeded hash, so reachability and
/// turnover membership are independent.
fn compute_turnover_set(
    user_agents: &[(&String, &AgentConfig)],
    seed: u64,
    fraction: f64,
) -> HashSet<String> {
    let frac = fraction.clamp(0.0, 1.0);
    let mut set = HashSet::new();
    if frac <= 0.0 {
        return set;
    }
    let mut eligible: Vec<String> = Vec::new();
    for (id, cfg) in user_agents {
        if cfg.is_miner() {
            continue;
        }
        let is_seed = cfg
            .attributes
            .as_ref()
            .map(|a| a.get("is_seed_node").map_or(false, |v| v == "true"))
            .unwrap_or(false);
        if is_seed {
            continue; // seeds stay always-on (bootstrap backbone)
        }
        // NOTE: users (has_wallet) take part too now — only the *daemon* cycles;
        // the wallet-rpc + agent stay up and reconnect. Miners are already
        // excluded above via is_miner().
        let pinned_on = cfg
            .daemon_options
            .as_ref()
            .and_then(|o| o.get("hide-my-port"))
            .map_or(false, |v| matches!(v, OptionValue::Bool(false)));
        if pinned_on {
            continue; // supernodes / explicitly-reachable infra stay always-on
        }
        eligible.push(id.to_string());
    }
    eligible.sort_by_key(|id| seeded_hash(seed, &format!("turnover:{}", id)));
    let n = ((frac * eligible.len() as f64).round() as usize).min(eligible.len());
    for id in eligible.into_iter().take(n) {
        set.insert(id);
    }
    set
}

/// Build a turnover schedule for one node: a list of (start_secs, Option<stop_secs>)
/// online sessions, in time order. `None` stop = the final session runs to
/// simulation end. Sessions and offline gaps are exponential draws
/// (deterministic in seed + id + session index) clamped to the given bounds.
/// Returns a single open-ended session when the node would not cycle at all
/// (start already at/after the end), i.e. effectively no turnover.
#[allow(clippy::too_many_arguments)]
fn build_turnover_schedule(
    seed: u64,
    id: &str,
    start_secs: u64,
    stop_secs: u64,
    mean_session: f64,
    mean_downtime: f64,
    min_session: f64,
    max_session: f64,
    min_downtime: f64,
) -> Vec<(u64, Option<u64>)> {
    const MAX_SESSIONS: usize = 1000; // safety backstop against pathological params
    if start_secs >= stop_secs {
        return vec![(start_secs, None)];
    }
    let mut out: Vec<(u64, Option<u64>)> = Vec::new();
    let mut t = start_secs;
    let mut k = 0usize;
    loop {
        let s = exp_draw(
            seed,
            &format!("cs:{}:{}", id, k),
            mean_session,
            min_session,
            max_session,
        );
        let end = t.saturating_add(s.round() as u64);
        if end >= stop_secs || k + 1 >= MAX_SESSIONS {
            out.push((t, None)); // final session runs to the end
            break;
        }
        out.push((t, Some(end)));
        let d = exp_draw(
            seed,
            &format!("cd:{}:{}", id, k),
            mean_downtime,
            min_downtime,
            f64::INFINITY,
        );
        t = end.saturating_add(d.round() as u64);
        k += 1;
        if t >= stop_secs {
            // Node left and does not return before the end — the last process
            // already carries its shutdown_time; nothing more to emit.
            break;
        }
    }
    out
}

pub fn process_user_agents(ctx: UserAgentProcessContext<'_>) -> color_eyre::eyre::Result<()> {
    let UserAgentProcessContext {
        agents,
        hosts,
        seed_agents,
        subnet_manager,
        ip_registry,
        monerod_path,
        wallet_path,
        environment,
        monero_environment,
        shared_dir,
        current_dir,
        gml_graph,
        using_gml_topology,
        peer_mode,
        topology,
        enable_dns_server,
        daemon_defaults,
        wallet_defaults,
        distribution_strategy,
        distribution_weights,
        scripts_dir,
        daemon_data_dir,
        simulation_seed,
        reachable_fraction,
        reachable_by_role,
        hidden_fraction,
        simulation_stop_secs,
        turnover,
    } = ctx;

    // Filter agents that have daemon or wallet (user agents, not script-only)
    let user_agents: Vec<(&String, &AgentConfig)> = agents
        .agents
        .iter()
        .filter(|(_, config)| {
            config.has_local_daemon() || config.has_remote_daemon() || config.has_wallet()
        })
        .collect();

    // Get agent distribution across GML nodes if available AND we're actually using GML topology
    //
    // Note on AS numbers: The GML topology uses synthetic AS numbers (0 to N-1) that are
    // remapped from real Internet AS numbers. Real AS numbers (e.g., Google AS 15169,
    // Cloudflare AS 13335) range from small values to 400,000+ with large gaps.
    // We remap them to contiguous 0-N because:
    // 1. Shadow requires sequential node IDs for efficient graph traversal
    // 2. Real AS numbers are sparse with huge gaps
    // 3. Simplifies region mapping without external AS-to-country databases
    let agent_node_assignments = if let Some(gml) = gml_graph {
        if !user_agents.is_empty() {
            if using_gml_topology {
                // Extract AS numbers from GML node attributes for distribution
                // The AS attribute contains the synthetic AS number (0 to N-1)
                let as_numbers = gml
                    .nodes
                    .iter()
                    .map(|node| {
                        node.attributes
                            .get("AS")
                            .or_else(|| node.attributes.get("as"))
                            .cloned()
                    })
                    .collect::<Vec<Option<String>>>();
                distribute_agents_across_topology(
                    Some(Path::new("")),
                    user_agents.len(),
                    &as_numbers,
                    distribution_strategy,
                    distribution_weights,
                )
                .into_iter()
                .map(|opt_idx| opt_idx.map_or(0, |idx| idx as u32))
                .collect()
            } else {
                // If we're not using GML topology (fallback to switch), all agents go to node 0
                vec![0; user_agents.len()]
            }
        } else {
            Vec::new()
        }
    } else {
        Vec::new()
    };

    // No phase validation needed for new AgentConfig (simpler structure)

    // Classify user agents into miners / seed nodes / regular agents,
    // allocate per-agent IPs, and build the ring/cross-link
    // --add-priority-node connection maps. Mutates subnet_manager,
    // ip_registry, and seed_agents (the latter receives the seed-source
    // IPs that downstream regular agents bootstrap against).
    let PeerTopology {
        agent_info,
        miners,
        seed_nodes,
        regular_agents,
        all_agent_ips,
        miner_connections,
        seed_connections,
    } = build_peer_topology(
        &user_agents,
        &agent_node_assignments,
        peer_mode,
        gml_graph,
        using_gml_topology,
        subnet_manager,
        ip_registry,
        seed_agents,
    )?;

    // Regular agents will use seed nodes for --seed-node

    // Deterministically select which non-seed nodes are UNREACHABLE, i.e.
    // firewalled: their P2P port gets blocked via Shadow's
    // blocked_inbound_ports, to mimic mainnet's NAT majority. Seeds and
    // miners are always reachable (bootstrap backbone).
    // See docs/20260618_mainnet_topology_targets.md.
    let unreachable_agents = compute_unreachable_set(
        &user_agents,
        simulation_seed,
        reachable_fraction,
        reachable_by_role,
    );
    if !unreachable_agents.is_empty() {
        log::info!(
            "Reachability: {} node(s) marked unreachable via blocked_inbound_ports \
             (global reachable_fraction={}; seeds + miners always reachable)",
            unreachable_agents.len(),
            reachable_fraction
        );
    }

    // Nodes that additionally run --hide-my-port. compute_unreachable_set
    // returns the first (1 - reachable) agents by seeded hash, so passing
    // (1 - hidden_fraction) selects the first `hidden_fraction` of them in the
    // SAME order — hence hidden ⊆ firewalled when hidden_fraction ≤
    // 1 - reachable_fraction. Default hidden_fraction 0.0 => empty set.
    let hidden_agents = compute_unreachable_set(
        &user_agents,
        simulation_seed,
        1.0 - hidden_fraction,
        None,
    );

    // Deterministically select which NODES cycle offline/online (turnover) and
    // pre-parse the turnover timing knobs once. See compute_turnover_set + the
    // per-session emission in the daemon loop below. Empty / None when turnover
    // is disabled (no [general.turnover] and no --turnover-* flag).
    let turnover_set = match turnover {
        Some(c) => compute_turnover_set(&user_agents, simulation_seed, c.fraction),
        None => HashSet::new(),
    };
    let turnover_params: Option<(f64, f64, f64, f64, f64)> = match turnover {
        Some(c) => {
            let mean_session = parse_duration_to_seconds(&c.mean_session).map_err(|e| {
                color_eyre::eyre::eyre!("turnover.mean_session '{}': {}", c.mean_session, e)
            })? as f64;
            let mean_downtime = parse_duration_to_seconds(&c.mean_downtime).map_err(|e| {
                color_eyre::eyre::eyre!("turnover.mean_downtime '{}': {}", c.mean_downtime, e)
            })? as f64;
            let min_session = match &c.min_session {
                Some(s) => parse_duration_to_seconds(s)
                    .map_err(|e| color_eyre::eyre::eyre!("turnover.min_session '{}': {}", s, e))?
                    as f64,
                None => 300.0,
            };
            let max_session = match &c.max_session {
                Some(s) => parse_duration_to_seconds(s)
                    .map_err(|e| color_eyre::eyre::eyre!("turnover.max_session '{}': {}", s, e))?
                    as f64,
                None => f64::INFINITY,
            };
            let min_downtime = match &c.min_downtime {
                Some(s) => parse_duration_to_seconds(s)
                    .map_err(|e| color_eyre::eyre::eyre!("turnover.min_downtime '{}': {}", s, e))?
                    as f64,
                None => 30.0,
            };
            Some((
                mean_session,
                mean_downtime,
                min_session,
                max_session,
                min_downtime,
            ))
        }
        None => None,
    };
    if !turnover_set.is_empty() {
        if let Some(c) = turnover {
            log::info!(
                "Turnover: {} node(s) cycle offline/online (mean_session={}, mean_downtime={}, \
                 fraction={}); miners + seeds + pinned supernodes stay always-on",
                turnover_set.len(),
                c.mean_session,
                c.mean_downtime,
                c.fraction
            );
        }
    }

    // Now process all user agents with staggered start times
    for (i, (agent_id, user_agent_config)) in user_agents.iter().enumerate() {
        // Determine agent type and start time
        let is_miner = user_agent_config.is_miner();
        let is_seed_node = is_miner
            || user_agent_config
                .attributes
                .as_ref()
                .map(|attrs| attrs.get("is_seed_node").map_or(false, |v| v == "true"))
                .unwrap_or(false);

        // Parse start_time if present (e.g., "2h", "7200s", "30m"). We
        // keep this as Option so we can distinguish "user explicitly
        // set 0s" from "user didn't set start_time at all" — the
        // previous version coerced both to 0 and then bumped to a
        // calculated default, silently overriding any user-supplied 0s
        // or otherwise-default-looking value. A bad-format string is
        // still treated as "not set" but emits a warning, since a hard
        // parse error here would require plumbing config-validation
        // upstream.
        let explicit_start_time: Option<u64> = match user_agent_config.start_time.as_ref() {
            None => None,
            Some(s) => match parse_duration_to_seconds(s) {
                Ok(v) => Some(v),
                Err(e) => {
                    log::warn!(
                        "Agent '{}': could not parse start_time={:?} ({}); falling back to calculated default",
                        agent_id, s, e
                    );
                    None
                }
            },
        };

        let base_start_time_seconds = if matches!(peer_mode, PeerMode::Dynamic) {
            if is_miner {
                if i == 0 {
                    0u64
                } else {
                    1 + i as u64
                }
            } else {
                let user_index = i.saturating_sub(miners.len());
                crate::BLOCK_MATURITY_SECONDS + user_index as u64
            }
        } else {
            if is_miner {
                i as u64
            } else if is_seed_node || seed_nodes.iter().any(|e| e.is_seed_node && e.index == i) {
                crate::BLOCK_MATURITY_SECONDS
            } else {
                let user_index = regular_agents
                    .iter()
                    .position(|e| e.index == i)
                    .unwrap_or(0);
                crate::BLOCK_MATURITY_SECONDS + user_index as u64
            }
        };

        // Honor any explicit start_time, including 0. Only fall
        // through to the calculated default when the user didn't
        // supply one at all (or it failed to parse — see warning above).
        let effective_start_time = explicit_start_time.unwrap_or(base_start_time_seconds);
        let start_time_daemon = format!("{}s", effective_start_time);

        // Wallet starts after daemon; agent starts after wallet
        let wallet_start_time =
            if let Ok(daemon_seconds) = parse_duration_to_seconds(&start_time_daemon) {
                format!("{}s", daemon_seconds + crate::WALLET_STARTUP_DELAY_SECS)
            } else {
                format!("{}s", crate::WALLET_STARTUP_DELAY_SECS + i as u64)
            };

        let agent_start_time =
            if let Ok(wallet_seconds) = parse_duration_to_seconds(&wallet_start_time) {
                format!("{}s", wallet_seconds + crate::AGENT_STARTUP_DELAY_SECS)
            } else {
                format!(
                    "{}s",
                    crate::WALLET_STARTUP_DELAY_SECS + crate::AGENT_STARTUP_DELAY_SECS + i as u64
                )
            };

        // Reuse the agent IP from the first pass (stored in agent_info)
        // This avoids calling get_agent_ip twice which would increment the host counter
        let agent_ip = agent_info[i].ip.clone();
        // Use standard Monero ports (mainnet ports for FAKECHAIN/regtest)
        // Since each agent has its own IP address, they can all use the same ports
        let daemon_rpc_port = crate::MONERO_RPC_PORT;
        let wallet_rpc_port = crate::MONERO_WALLET_RPC_PORT;
        let p2p_port = crate::MONERO_P2P_PORT;

        let mut processes = Vec::new();

        // Determine agent type
        let has_local_daemon = user_agent_config.has_local_daemon();
        let has_remote_daemon = user_agent_config.has_remote_daemon();
        let has_wallet = user_agent_config.has_wallet();
        let has_daemon_phases = user_agent_config.has_daemon_phases();
        let has_wallet_phases = user_agent_config.has_wallet_phases();

        // Get process_threads from environment (convenience setting)
        let process_threads: u32 = monero_environment
            .get("PROCESS_THREADS")
            .and_then(|s| s.parse().ok())
            .unwrap_or(0);

        // Merge daemon_defaults with per-agent daemon_options
        let mut merged_daemon_options =
            merge_options(daemon_defaults, user_agent_config.daemon_options.as_ref());
        // Expand symbolic log-level values (e.g., "monitor") into the
        // equivalent monerod category string before they reach the CLI.
        translate_daemon_log_level(&mut merged_daemon_options);

        // monerosim baseline: lift --max-connections-per-ip off monerod's
        // default of 1 (the cap counts simultaneous INCOMING connections
        // per remote IP, enforced at accept). In small/dense scenarios —
        // where node pairs hold mutual connections and exchange try_ping
        // reachability back-pings — a second incoming from the same IP is
        // routine and gets refused at cap 1, preventing a stable mesh
        // (quickstart-15: 31,180 refusals/run, no mesh; 0 with the floor).
        // At large sparse scale the default is nearly harmless, and this
        // floor was verified to change nothing measurable at 1000 nodes.
        // 4 = data conn + back-ping + headroom for cleanup races.
        // See docs/20260605_max_connections_per_ip_bug.md.
        //
        // This is a floor, not a force: merge_options() above has already
        // applied daemon_defaults and per-agent daemon_options, so entry()
        // only fills the value in when the user hasn't set it themselves.
        merged_daemon_options
            .entry("max-connections-per-ip".to_string())
            .or_insert(OptionValue::Number(4));

        // Mainnet-realism: if this node was selected as hidden, inject
        // --hide-my-port (advertise my_port=0). The node still binds/listens
        // and forms its own outbound peers, but is never inserted into
        // anyone's peerlist (white-listing is gated on a successful
        // back-ping, which requires my_port != 0), so it accepts ~no
        // inbound. A user who sets hide-my-port explicitly per-agent still
        // wins (or_insert).
        if hidden_agents.contains(agent_id.as_str()) {
            merged_daemon_options
                .entry("hide-my-port".to_string())
                .or_insert(OptionValue::Bool(true));
        }

        let build_daemon_args_base = |phase_args: Option<&Vec<String>>| -> Vec<String> {
            // Start with required/injected flags that cannot be overridden.
            //
            // --log-file: vanilla monerod's default is ~/.bitmonero/bitmonero.log
            // (per `monerod --help`), NOT <data-dir>/bitmonero.log. The
            // shadowformonero patches we used to apply pinned it to data-dir,
            // but those were dropped in 641bc5a6 (Apr 21 2026). Without an
            // explicit --log-file, monerod silently writes nothing — the
            // monitor's daemon-log discovery and run_sim.sh's archive step
            // both glob /tmp/monero-*/bitmonero.log and turn up empty,
            // leaving the post-run summary reporting "0 nodes / 0 blocks"
            // even on a healthy sim.
            let data_dir = format!("{}/monero-{}", daemon_data_dir, agent_id);
            let mut args = vec![
                format!("--data-dir={}", data_dir),
                format!("--log-file={}/bitmonero.log", data_dir),
                "--regtest".to_string(),
                "--keep-fakechain".to_string(),
            ];

            // Add process_threads flags if set and not overridden in daemon_defaults
            if process_threads > 0 {
                if !merged_daemon_options.contains_key("prep-blocks-threads") {
                    args.push(format!("--prep-blocks-threads={}", process_threads));
                }
                if !merged_daemon_options.contains_key("max-concurrency") {
                    args.push(format!("--max-concurrency={}", process_threads));
                }
            }

            // Add configurable options from merged daemon_defaults + daemon_options
            args.extend(options_to_args(&merged_daemon_options));

            // Add required network binding flags (always injected, use agent-specific values)
            args.extend(vec![
                format!("--rpc-bind-ip={}", agent_ip),
                format!("--rpc-bind-port={}", daemon_rpc_port),
                "--confirm-external-bind".to_string(),
                "--rpc-access-control-origins=*".to_string(),
                format!("--p2p-bind-ip={}", agent_ip),
                format!("--p2p-bind-port={}", p2p_port),
            ]);

            // Add DNS and seed node settings
            if !enable_dns_server {
                args.push("--disable-dns-checkpoints".to_string());
            }
            if is_miner && !enable_dns_server {
                args.push("--disable-seed-nodes".to_string());
            }

            // Add initial fixed connections
            if is_miner {
                if let Some(conns) = miner_connections.get(*agent_id) {
                    for conn in conns {
                        args.push(conn.clone());
                    }
                }
            } else if is_seed_node || seed_nodes.iter().any(|e| e.is_seed_node && e.index == i) {
                if let Some(conns) = seed_connections.get(*agent_id) {
                    for conn in conns {
                        args.push(conn.clone());
                    }
                }
            }

            // Add peer connections for regular agents
            let is_actual_seed_node = seed_nodes.iter().any(|e| e.index == i);
            if !is_miner && !is_actual_seed_node {
                for seed_node in seed_agents.iter() {
                    if !seed_node.starts_with(&format!("{}:", agent_ip)) {
                        let peer_arg = if matches!(peer_mode, PeerMode::Dynamic) {
                            format!("--seed-node={}", seed_node)
                        } else {
                            format!("--add-priority-node={}", seed_node)
                        };
                        args.push(peer_arg);
                    }
                }
                if matches!(peer_mode, PeerMode::Hybrid) {
                    if let Some(topo) = topology {
                        let topology_connections =
                            generate_topology_connections(topo, i, &all_agent_ips, &agent_ip);
                        for conn in topology_connections {
                            args.push(conn);
                        }
                    }
                }
            }

            // Add phase-specific args
            if let Some(custom_args) = phase_args {
                for arg in custom_args {
                    args.push(arg.clone());
                }
            }

            args
        };

        // Add Monero daemon process(es) - either simple or phase-based
        if has_daemon_phases {
            // Phase-based daemon configuration (upgrade scenario).
            // `has_daemon_phases` already verified daemon_phases is Some and non-empty.
            let phases = user_agent_config
                .daemon_phases
                .as_ref()
                .expect("invariant: has_daemon_phases() == true implies daemon_phases.is_some()");
            let phase_count = phases.len();

            for (phase_num, phase) in phases {
                let daemon_args = build_daemon_args_base(phase.args.as_ref());

                // Resolve binary path for this phase
                let daemon_binary_path =
                    resolve_binary_path_for_shadow(&phase.path).map_err(|e| {
                        color_eyre::eyre::eyre!(
                            "Agent '{}': failed to resolve daemon phase binary path '{}': {}",
                            agent_id,
                            phase.path,
                            e
                        )
                    })?;

                // Build environment for this phase
                let mut daemon_env = monero_environment.clone();
                if let Some(custom_env) = &phase.env {
                    for (key, value) in custom_env {
                        daemon_env.insert(key.clone(), value.clone());
                    }
                }

                // Determine start time
                let start_time = if let Some(start) = &phase.start {
                    start.clone()
                } else if *phase_num == 0 {
                    start_time_daemon.clone()
                } else {
                    // Should have been caught by validation
                    start_time_daemon.clone()
                };

                // Determine shutdown time and expected final state
                let (shutdown_time, expected_final_state) = if *phase_num < (phase_count as u32 - 1)
                {
                    // Not the last phase - needs shutdown
                    // Shadow sends SIGTERM at shutdown_time; monerod handles it gracefully
                    // and exits with code 0 (not killed by signal)
                    (phase.stop.clone(), Some(ExpectedFinalState::Exited(0)))
                } else {
                    // Last phase - runs until simulation end
                    (None, Some(ExpectedFinalState::Running))
                };

                // Direct launch — Shadow execs monerod itself, so SIGTERM at
                // shutdown_time goes straight to it. Data directory cleanup
                // is handled pre-simulation by main.rs.
                processes.push(crate::shadow::ShadowProcess {
                    path: daemon_binary_path,
                    args: crate::shadow::ProcessArgs::List(daemon_args),
                    environment: daemon_env,
                    start_time,
                    shutdown_time,
                    shutdown_signal: None,
                    expected_final_state,
                });
            }
        } else if has_local_daemon {
            // Simple daemon configuration (single binary)
            let daemon_args = build_daemon_args_base(user_agent_config.daemon_args.as_ref());

            // Get daemon binary path from config, fall back to default
            let daemon_binary_path = match &user_agent_config.daemon {
                Some(DaemonConfig::Local(path)) => {
                    resolve_binary_path_for_shadow(path).map_err(|e| {
                        color_eyre::eyre::eyre!(
                            "Agent '{}': failed to resolve daemon binary path '{}': {}",
                            agent_id,
                            path,
                            e
                        )
                    })?
                }
                _ => monerod_path.to_string(),
            };

            // Merge custom environment from config with base environment
            let mut daemon_env = monero_environment.clone();
            if let Some(custom_env) = &user_agent_config.daemon_env {
                for (key, value) in custom_env {
                    daemon_env.insert(key.clone(), value.clone());
                }
            }

            // Turnover: if this relay was selected to cycle offline/online,
            // emit one ShadowProcess per online session (each a fresh
            // monerod on the SAME data-dir, so chain state survives the
            // restart). Non-final sessions stop via shutdown_time
            // (SIGTERM → monerod exits 0, mirroring the upgrade path); the
            // final open-ended session runs to simulation end. Otherwise
            // (no turnover) emit the single always-on daemon as before.
            let turnover_schedule =
                match (&turnover_params, turnover_set.contains(agent_id.as_str())) {
                    (Some((ms, md, mins, maxs, mind)), true) => Some(build_turnover_schedule(
                        simulation_seed,
                        agent_id,
                        effective_start_time,
                        simulation_stop_secs,
                        *ms,
                        *md,
                        *mins,
                        *maxs,
                        *mind,
                    )),
                    _ => None,
                };
            match turnover_schedule {
                Some(schedule) => {
                    for (start, stop_opt) in schedule {
                        let (shutdown_time, expected_final_state) = match stop_opt {
                            Some(stop) => (
                                Some(format!("{}s", stop)),
                                Some(ExpectedFinalState::Exited(0)),
                            ),
                            None => (None, Some(ExpectedFinalState::Running)),
                        };
                        processes.push(crate::shadow::ShadowProcess {
                            path: daemon_binary_path.clone(),
                            args: crate::shadow::ProcessArgs::List(daemon_args.clone()),
                            environment: daemon_env.clone(),
                            start_time: format!("{}s", start),
                            shutdown_time,
                            shutdown_signal: None,
                            expected_final_state,
                        });
                    }
                }
                None => {
                    // Direct launch — see phase-daemon comment above.
                    processes.push(crate::shadow::ShadowProcess {
                        path: daemon_binary_path,
                        args: crate::shadow::ProcessArgs::List(daemon_args),
                        environment: daemon_env,
                        start_time: start_time_daemon.clone(),
                        shutdown_time: None,
                        shutdown_signal: None,
                        expected_final_state: Some(ExpectedFinalState::Running),
                    });
                }
            }
        } // End of daemon configuration

        // Add wallet process based on agent type.
        // Wallet-arg construction (defaults merge, log-level translation, and
        // the full flag list) lives in the shared `build_wallet_args` — see
        // both the phase path below and `add_wallet_process`.

        // Track wallet-rpc command for restart capability
        let mut wallet_rpc_cmd: Option<String> = None;

        if has_wallet_phases {
            // Phase-based wallet configuration (upgrade scenario).
            // `has_wallet_phases` already verified wallet_phases is Some and non-empty.
            let phases = user_agent_config
                .wallet_phases
                .as_ref()
                .expect("invariant: has_wallet_phases() == true implies wallet_phases.is_some()");
            let phase_count = phases.len();

            // Phase-based wallets always run against the co-located local
            // daemon; the per-phase args are the only thing that varies.
            let phase_daemon_address = DaemonAddress::Local {
                agent_ip: &agent_ip,
                daemon_rpc_port,
            }
            .format();

            for (phase_num, phase) in phases {
                // Shared wallet-arg builder (single source of truth — see
                // process::wallet::build_wallet_args).
                let wallet_args = build_wallet_args(
                    agent_id,
                    &agent_ip,
                    &phase_daemon_address,
                    wallet_rpc_port,
                    environment,
                    phase.args.as_ref(),
                    wallet_defaults,
                    user_agent_config.wallet_options.as_ref(),
                    &shared_dir.to_string_lossy(),
                );

                // Resolve binary path for this phase
                let wallet_binary_path =
                    resolve_binary_path_for_shadow(&phase.path).map_err(|e| {
                        color_eyre::eyre::eyre!(
                            "Agent '{}': failed to resolve wallet phase binary path '{}': {}",
                            agent_id,
                            phase.path,
                            e
                        )
                    })?;

                // Build environment for this phase
                let mut wallet_env = environment.clone();
                if let Some(custom_env) = &phase.env {
                    for (key, value) in custom_env {
                        wallet_env.insert(key.clone(), value.clone());
                    }
                }

                // Determine start time
                let start_time = if let Some(start) = &phase.start {
                    start.clone()
                } else if *phase_num == 0 {
                    wallet_start_time.clone()
                } else {
                    // Should have been caught by validation
                    wallet_start_time.clone()
                };

                // Determine shutdown time, signal, and expected final state.
                //
                // Non-final wallet phases use SIGKILL rather than the default
                // SIGTERM. monero-wallet-rpc can deadlock during normal
                // operation, and a deadlocked wallet ignores SIGTERM
                // indefinitely — holding port 18082 past shutdown_time and
                // blocking the next-phase binary from binding. SIGKILL is
                // safe in the upgrade context (chain rebuilds wallet state
                // on the next phase's first refresh). Full rationale,
                // tradeoffs, and an escalation-wrapper alternative are in
                // docs/UPGRADE_WALLET_SIGKILL.md.
                let (shutdown_time, shutdown_signal, expected_final_state) =
                    if *phase_num < (phase_count as u32 - 1) {
                        (
                            phase.stop.clone(),
                            Some("SIGKILL".to_string()),
                            Some(ExpectedFinalState::Signaled("SIGKILL".to_string())),
                        )
                    } else {
                        // Last phase - runs until simulation end
                        (None, None, Some(ExpectedFinalState::Running))
                    };

                // Note: wallet directory cleanup is handled pre-simulation by the orchestrator.

                // Shell-quoted form for the WALLET_RPC_CMD env var (consumed
                // by restart_wallet_rpc() via subprocess.Popen(shell=True)).
                // The Shadow process below uses ProcessArgs::List directly.
                let wallet_cmd = format!(
                    "{} {}",
                    crate::utils::options::shell_quote_args(&[wallet_binary_path.clone()]),
                    crate::utils::options::shell_quote_args(&wallet_args),
                );

                processes.push(crate::shadow::ShadowProcess {
                    path: wallet_binary_path,
                    args: crate::shadow::ProcessArgs::List(wallet_args),
                    environment: wallet_env,
                    start_time,
                    shutdown_time,
                    shutdown_signal,
                    expected_final_state,
                });

                // Keep the last phase's command for the agent restart env var
                wallet_rpc_cmd = Some(wallet_cmd);
            }
        } else if has_wallet {
            // Simple wallet configuration (single binary)
            let wallet_binary_path = if let Some(wallet_spec) = &user_agent_config.wallet {
                resolve_binary_path_for_shadow(wallet_spec).map_err(|e| {
                    color_eyre::eyre::eyre!(
                        "Agent '{}': failed to resolve wallet binary path '{}': {}",
                        agent_id,
                        wallet_spec,
                        e
                    )
                })?
            } else {
                wallet_path.to_string()
            };

            let daemon = if has_local_daemon || has_daemon_phases {
                Some(DaemonAddress::Local {
                    agent_ip: &agent_ip,
                    daemon_rpc_port,
                })
            } else if has_remote_daemon {
                Some(DaemonAddress::Remote(
                    user_agent_config.remote_daemon_address(),
                ))
            } else {
                None
            };
            if let Some(daemon) = daemon {
                wallet_rpc_cmd = Some(add_wallet_process(WalletProcessArgs {
                    processes: &mut processes,
                    agent_id: &agent_id,
                    agent_ip: &agent_ip,
                    daemon,
                    wallet_rpc_port,
                    wallet_binary_path: &wallet_binary_path,
                    environment,
                    wallet_start_time: &wallet_start_time,
                    custom_args: user_agent_config.wallet_args.as_ref(),
                    custom_env: user_agent_config.wallet_env.as_ref(),
                    wallet_defaults,
                    wallet_options: user_agent_config.wallet_options.as_ref(),
                    shared_dir: &shared_dir.to_string_lossy(),
                }));
            }
        }

        // Add agent scripts (skip entirely for daemon-only relay agents)
        if !user_agent_config.is_daemon_only() {
            let script = user_agent_config
                .script
                .clone()
                .unwrap_or_else(|| "agents.regular_user".to_string());

            if is_miner && script.contains("autonomous_miner") {
                // HYBRID APPROACH for miners: Run both regular_user (for wallet) AND mining_script

                // Build merged attributes that include typed fields (hashrate, is_miner, can_receive_distributions)
                let mut merged_attributes =
                    user_agent_config.attributes.clone().unwrap_or_default();
                merged_attributes.insert("is_miner".to_string(), "true".to_string());
                if let Some(hashrate) = user_agent_config.hashrate {
                    merged_attributes.insert("hashrate".to_string(), hashrate.to_string());
                }
                if user_agent_config.can_receive_distributions() {
                    merged_attributes
                        .insert("can_receive_distributions".to_string(), "true".to_string());
                }

                // Step 1: Run regular_user.py first for wallet creation and address registration
                add_user_agent_process(UserAgentProcessArgs {
                    processes: &mut processes,
                    agent_id,
                    agent_ip: &agent_ip,
                    daemon_rpc_port: if has_local_daemon {
                        Some(daemon_rpc_port)
                    } else {
                        None
                    },
                    wallet_rpc_port: if has_wallet {
                        Some(wallet_rpc_port)
                    } else {
                        None
                    },
                    p2p_port: if has_local_daemon {
                        Some(p2p_port)
                    } else {
                        None
                    },
                    script: "agents.regular_user",
                    attributes: Some(&merged_attributes),
                    environment,
                    shared_dir,
                    current_dir,
                    index: i,
                    stop_time: environment
                        .get("stop_time")
                        .map(|s| s.as_str())
                        .unwrap_or("1800"),
                    custom_start_time: Some(&agent_start_time),
                    remote_daemon: user_agent_config.remote_daemon_address(),
                    daemon_selection_strategy: user_agent_config
                        .daemon_selection_strategy()
                        .map(|s| s.as_str()),
                    scripts_dir,
                    wallet_rpc_cmd: wallet_rpc_cmd.as_deref(),
                });

                // Step 2: Run mining_script (autonomous_miner.py)
                let mining_start_time =
                    if let Ok(agent_seconds) = parse_duration_to_seconds(&agent_start_time) {
                        format!("{}s", agent_seconds + 10)
                    } else {
                        format!("{}s", 75 + i * 2)
                    };

                let mining_wallet_port = if user_agent_config.wallet.is_some() {
                    Some(wallet_rpc_port)
                } else {
                    None
                };

                let mining_processes = create_mining_agent_process(MiningAgentProcessArgs {
                    agent_id,
                    ip_addr: &agent_ip,
                    daemon_rpc_port,
                    wallet_rpc_port: mining_wallet_port,
                    mining_script: &script,
                    attributes: Some(&merged_attributes),
                    environment,
                    shared_dir,
                    current_dir,
                    index: i,
                    custom_start_time: Some(&mining_start_time),
                    scripts_dir,
                    wallet_rpc_cmd: wallet_rpc_cmd.as_deref(),
                });
                processes.extend(mining_processes);
            } else if !script.is_empty() {
                // Regular user agent script
                // Build merged attributes that include typed config fields
                let mut merged_attributes =
                    user_agent_config.attributes.clone().unwrap_or_default();
                if let Some(activity_start_time) = user_agent_config.activity_start_time {
                    merged_attributes.insert(
                        "activity_start_time".to_string(),
                        activity_start_time.to_string(),
                    );
                }
                if let Some(transaction_interval) = user_agent_config.transaction_interval {
                    merged_attributes.insert(
                        "transaction_interval".to_string(),
                        transaction_interval.to_string(),
                    );
                }
                if user_agent_config.can_receive_distributions() {
                    merged_attributes
                        .insert("can_receive_distributions".to_string(), "true".to_string());
                }

                add_user_agent_process(UserAgentProcessArgs {
                    processes: &mut processes,
                    agent_id,
                    agent_ip: &agent_ip,
                    daemon_rpc_port: if has_local_daemon {
                        Some(daemon_rpc_port)
                    } else {
                        None
                    },
                    wallet_rpc_port: if has_wallet {
                        Some(wallet_rpc_port)
                    } else {
                        None
                    },
                    p2p_port: if has_local_daemon {
                        Some(p2p_port)
                    } else {
                        None
                    },
                    script: &script,
                    attributes: Some(&merged_attributes),
                    environment,
                    shared_dir,
                    current_dir,
                    index: i,
                    stop_time: environment
                        .get("stop_time")
                        .map(|s| s.as_str())
                        .unwrap_or("1800"),
                    custom_start_time: Some(&agent_start_time),
                    remote_daemon: user_agent_config.remote_daemon_address(),
                    daemon_selection_strategy: user_agent_config
                        .daemon_selection_strategy()
                        .map(|s| s.as_str()),
                    scripts_dir,
                    wallet_rpc_cmd: wallet_rpc_cmd.as_deref(),
                });
            }
        } // end daemon-only guard

        // Only add the host if it has any processes
        if !processes.is_empty() {
            // Determine network node ID based on GML assignment or fallback
            let network_node_id = if i < agent_node_assignments.len() {
                agent_node_assignments[i]
            } else {
                0 // Fallback to node 0 for switch-based networks
            };

            hosts.insert(
                agent_id.to_string(),
                ShadowHost {
                    network_node_id,
                    ip_addr: Some(agent_ip.clone()),
                    blocked_inbound_ports: if unreachable_agents.contains(agent_id.as_str()) {
                        Some(vec![crate::MONERO_P2P_PORT])
                    } else {
                        None
                    },
                    processes,
                    bandwidth_down: Some(crate::DEFAULT_BANDWIDTH_BPS.to_string()),
                    bandwidth_up: Some(crate::DEFAULT_BANDWIDTH_BPS.to_string()),
                },
            );
            // Note: next_ip is already incremented in get_agent_ip function
        }
    }

    Ok(())
}

#[cfg(test)]
mod turnover_tests {
    use super::*;
    use std::collections::HashSet as Set;

    #[test]
    fn seeded_unit_varies_on_trailing_index() {
        // Regression: FNV-1a's high bits barely move when only the trailing
        // byte (the session index) changes, and seeded_unit reads the top 53
        // bits — without the splitmix finalizer every session drew the same
        // length. Across 64 consecutive keys the draws must be ~all distinct
        // and spread around 0.5.
        let vals: Vec<f64> = (0..64)
            .map(|k| seeded_unit(42, &format!("cs:relay-001:{k}")))
            .collect();
        let distinct = vals
            .iter()
            .map(|v| (v * 1e6) as u64)
            .collect::<Set<_>>()
            .len();
        assert!(
            distinct >= 60,
            "expected ~all distinct draws, got {distinct}/64"
        );
        let mean = vals.iter().sum::<f64>() / vals.len() as f64;
        assert!((0.3..0.7).contains(&mean), "mean {mean} not ~0.5");
    }

    #[test]
    fn exp_draw_respects_clamps() {
        for k in 0..200 {
            let v = exp_draw(7, &format!("k{k}"), 7200.0, 300.0, 6000.0);
            assert!((300.0..=6000.0).contains(&v), "v={v} out of [300,6000]");
        }
    }

    #[test]
    fn turnover_schedule_sessions_vary_and_are_ordered() {
        let sched = build_turnover_schedule(
            12345,
            "relay-001",
            1200,
            57600,
            7200.0,
            1800.0,
            300.0,
            f64::INFINITY,
            30.0,
        );
        assert!(
            sched.len() >= 2,
            "expected multiple sessions, got {}",
            sched.len()
        );
        // Final session is open-ended (runs to sim end); earlier ones bounded.
        assert_eq!(sched.last().unwrap().1, None);
        // Time-ordered, non-overlapping, with a real downtime gap between.
        for i in 0..sched.len() - 1 {
            let stop_i = sched[i].1.expect("non-final session must have a stop");
            assert!(sched[i].0 < stop_i, "start < stop within a session");
            assert!(sched[i + 1].0 > stop_i, "next start after prev stop");
        }
        // The bug we fixed: bounded session lengths must not all be identical.
        let lens: Vec<u64> = sched[..sched.len() - 1]
            .iter()
            .map(|(s, e)| e.unwrap() - s)
            .collect();
        if lens.len() >= 2 {
            assert!(
                lens.iter().collect::<Set<_>>().len() >= 2,
                "lengths flat: {lens:?}"
            );
        }
    }

    #[test]
    fn turnover_schedule_is_deterministic() {
        let a = build_turnover_schedule(
            99,
            "relay-042",
            0,
            57600,
            7200.0,
            1800.0,
            300.0,
            f64::INFINITY,
            30.0,
        );
        let b = build_turnover_schedule(
            99,
            "relay-042",
            0,
            57600,
            7200.0,
            1800.0,
            300.0,
            f64::INFINITY,
            30.0,
        );
        assert_eq!(a, b);
    }

    #[test]
    fn turnover_schedule_no_cycle_when_start_past_end() {
        let s = build_turnover_schedule(
            1,
            "x",
            60000,
            57600,
            7200.0,
            1800.0,
            300.0,
            f64::INFINITY,
            30.0,
        );
        assert_eq!(s, vec![(60000, None)]);
    }

    #[test]
    fn turnover_schedule_respects_max_session_ceiling() {
        let sched = build_turnover_schedule(
            7, "relay-7", 0, 200_000, 7200.0, 600.0, 300.0, 14400.0, 30.0,
        );
        for (s, e) in &sched {
            if let Some(end) = e {
                assert!(
                    end - s <= 14400,
                    "session {} exceeds the 4h ceiling",
                    end - s
                );
            }
        }
    }
}
