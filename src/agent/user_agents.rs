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
use crate::utils::options::{merge_options, translate_daemon_log_level};
use std::collections::{BTreeMap, HashMap, HashSet};
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
    /// Node-implementation selection: maps an implementation id (e.g.
    /// `"cuprated"`) to the fraction of eligible relay nodes that run it. Empty
    /// => every node runs monerod (generated output unchanged).
    pub node_implementations: &'a BTreeMap<String, f64>,
    /// Opt into placing cuprate nodes before their P3b seed override (they boot
    /// but find no peers) — boot-testing only; otherwise cuprate is rejected.
    pub experimental_cuprate_boot: bool,
    /// Simulation stop time in seconds — bounds turnover session generation.
    pub simulation_stop_secs: u64,
    /// Peer-turnover config (None = no turnover; relays stay always-on).
    pub turnover: Option<&'a crate::config::TurnoverConfig>,
    /// Block-production mode (generateblocks vs native monerod-sim mining).
    pub mining: crate::config::MiningConfig,
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

/// A node that explicitly pins `hide-my-port: false` in its *own* daemon_options
/// is declaring itself an always-reachable hub (the supernode / infrastructure
/// convention). Such a node is never firewalled, never hidden, and never cycled
/// by turnover — it stays a stable, dialable backbone node regardless of the
/// global reachability/hidden fractions.
fn is_pinned_reachable(cfg: &AgentConfig) -> bool {
    cfg.daemon_options
        .as_ref()
        .and_then(|o| o.get("hide-my-port"))
        .map_or(false, |v| matches!(v, OptionValue::Bool(false)))
}

/// Assign a node implementation to eligible daemon agents by seeded hash.
///
/// Eligible = non-seed, non-miner, phase-less daemon nodes. Wallet-bearing user
/// nodes ARE eligible: cuprate backing a real monero-wallet-rpc (sync + send) is
/// runtime-proven — see docs/20260724_cuprate_wallet_rpc.md. MINERS still stay
/// monerod (cuprate's GenerateBlocks is a stub), so a capability mismatch can't
/// arise. `fractions` maps impl_id -> fraction of the
/// eligible pool; entries are applied in id order over a seeded-hash ordering of
/// the pool, partitioning it into disjoint sets (fractions are of the TOTAL
/// eligible pool; sum <= 1.0 expected, over-assignment is clamped to what's
/// left). monerod is the implicit default and never appears in the returned map.
/// Returns agent_id -> impl_id. Empty / all-monerod `fractions` => empty map.
///
/// BREAKING (2026-09-23): the sort key is now `finalize_hash(seeded_hash(...))`
/// instead of the raw FNV-1a value. FNV's high bits are dominated by the
/// leading bytes of the id, so sorting on the raw hash picked contiguous
/// id/name blocks (e.g. always the same numeric range of `relay-NNN`) rather
/// than a well-mixed sample. Same seed still reproduces the same assignment,
/// but assignments from prior runs will differ.
fn compute_node_impl_set(
    user_agents: &[(&String, &AgentConfig)],
    seed: u64,
    fractions: &BTreeMap<String, f64>,
) -> HashMap<String, String> {
    let mut assignment = HashMap::new();
    if fractions
        .iter()
        .all(|(id, f)| id == "monerod" || *f <= 0.0)
    {
        return assignment;
    }
    let mut eligible: Vec<String> = Vec::new();
    for (id, cfg) in user_agents {
        if cfg.is_miner() {
            continue; // mines via generateblocks — monerod only
        }
        if cfg.has_daemon_phases() {
            continue; // upgrade-phase node — monerod only
        }
        let is_seed = cfg
            .attributes
            .as_ref()
            .map(|a| a.get("is_seed_node").map_or(false, |v| v == "true"))
            .unwrap_or(false);
        if is_seed {
            continue; // bootstrap backbone — monerod only
        }
        eligible.push(id.to_string());
    }
    eligible.sort_by_key(|id| finalize_hash(seeded_hash(seed, &format!("nodeimpl:{}", id))));

    let n = eligible.len();
    let mut cursor = 0usize;
    for (impl_id, frac) in fractions {
        if impl_id == "monerod" {
            continue; // implicit default
        }
        let frac = frac.clamp(0.0, 1.0);
        if frac <= 0.0 {
            continue;
        }
        let remaining = n.saturating_sub(cursor);
        let count = ((frac * n as f64).round() as usize).min(remaining);
        for id in eligible.iter().skip(cursor).take(count) {
            assignment.insert(id.clone(), impl_id.clone());
        }
        cursor += count;
    }
    assignment
}

/// Decide which non-seed agents are unreachable. This set drives BOTH the
/// synthetic firewall (`blocked_inbound_ports`) and, via a second call with
/// `hidden_fraction`, the `--hide-my-port` set. Roles: `user` (has a wallet) and
/// `relay` (daemon-only). Seeds and miners are always reachable and excluded
/// entirely (bootstrap backbone); so are nodes that pin `hide-my-port: false`
/// (always-reachable hubs — see [`is_pinned_reachable`]). `reachable` is the
/// global fraction; `by_role` overrides it per role (override semantics, NOT
/// multiply). For each role, `round((1 - r) * count)` agents are marked
/// unreachable, chosen deterministically by seeded hash so runs reproduce.
///
/// BREAKING (2026-09-23): the sort key is now `finalize_hash(seeded_hash(...))`
/// instead of the raw FNV-1a value — see [`compute_node_impl_set`]'s doc for
/// why (contiguous id blocks, not a uniform sample). Same seed still
/// reproduces the same set, but the set itself differs from prior runs.
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
        if is_pinned_reachable(cfg) {
            continue; // explicit hide-my-port:false = always-reachable hub (supernode)
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
        ids.sort_by_key(|id| finalize_hash(seeded_hash(seed, id)));
        let n_unreach = (((1.0 - r) * ids.len() as f64).round() as usize).min(ids.len());
        for id in ids.into_iter().take(n_unreach) {
            unreachable.insert(id);
        }
    }
    unreachable
}

/// splitmix64 finalizer: any 1-bit input change flips ~half the output bits,
/// giving well-distributed top bits regardless of key layout.
///
/// FNV-1a's avalanche in its *high* bits is poor when only a trailing byte
/// changes (e.g. the session index in `cs:<id>:<k>`, or a numeric id suffix in
/// `relay-001` vs `relay-002`) — sorting or bucketing on the raw FNV value
/// selects contiguous blocks of keys instead of a uniform sample. Always run
/// `seeded_hash` output through this finalizer before using it as a sort key
/// or a uniform draw.
fn finalize_hash(mut h: u64) -> u64 {
    h ^= h >> 30;
    h = h.wrapping_mul(0xbf58_476d_1ce4_e5b9);
    h ^= h >> 27;
    h = h.wrapping_mul(0x94d0_49bb_1331_11eb);
    h ^= h >> 31;
    h
}

/// Map a seeded hash to a uniform float in (0, 1), nudged off the exact
/// endpoints so the inverse-CDF `ln()` below is always finite.
fn seeded_unit(seed: u64, s: &str) -> f64 {
    let h = finalize_hash(seeded_hash(seed, s));
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
///
/// BREAKING (2026-09-23): the sort key is now `finalize_hash(seeded_hash(...))`
/// instead of the raw FNV-1a value — see [`compute_node_impl_set`]'s doc for
/// why (contiguous id blocks, not a uniform sample). Same seed still
/// reproduces the same set, but the set itself differs from prior runs.
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
        if is_pinned_reachable(cfg) {
            continue; // supernodes / explicitly-reachable infra stay always-on
        }
        eligible.push(id.to_string());
    }
    eligible.sort_by_key(|id| finalize_hash(seeded_hash(seed, &format!("turnover:{}", id))));
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

/// The monerod CLI knob (added by patches/monero-fakechain-hardforks.patch)
/// that overrides the regtest hard fork schedule. Stock monerod exits on the
/// unknown option, so any agent given it must run a patched binary — see
/// `binary_supports_hf_schedule`.
const HF_SCHEDULE_KNOB: &str = "fakechain-hard-forks";

/// True if any raw daemon arg sets --fakechain-hard-forks (legacy
/// `daemon_args` or per-phase `daemon_N_args`).
fn args_mention_hf_knob(args: Option<&Vec<String>>) -> bool {
    args.map(|v| v.iter().any(|a| a.contains("--fakechain-hard-forks")))
        .unwrap_or(false)
}

/// Capability probe: does `binary --help` list --fakechain-hard-forks?
/// A version check can't tell — the patched build prints the same tag as
/// vanilla. Cached per path so a 300-agent config spawns the probe once
/// per distinct binary, not per agent.
fn binary_supports_hf_schedule(path: &str, cache: &mut HashMap<String, bool>) -> bool {
    if let Some(v) = cache.get(path) {
        return *v;
    }
    let supported = std::process::Command::new(path)
        .arg("--help")
        .output()
        .map(|o| {
            let mut text = o.stdout;
            text.extend_from_slice(&o.stderr);
            String::from_utf8_lossy(&text).contains(HF_SCHEDULE_KNOB)
        })
        .unwrap_or(false);
    cache.insert(path.to_string(), supported);
    supported
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
        node_implementations,
        experimental_cuprate_boot,
        simulation_stop_secs,
        turnover,
        mining,
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
    let mut agent_node_assignments = if let Some(gml) = gml_graph {
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

    // Per-agent topology pins override the index-based distribution. This must run
    // before build_peer_topology / IP allocation consume agent_node_assignments,
    // since those read the (now-overridden) node ids. See
    // docs/superpowers/specs/2026-09-13-per-agent-topology-placement-design.md.
    let valid_node_ids: std::collections::HashSet<u32> = gml_graph
        .map(|gml| gml.nodes.iter().map(|n| n.id).collect())
        .unwrap_or_default();
    crate::topology::placement::apply_topology_pins(
        &mut agent_node_assignments,
        &user_agents,
        &valid_node_ids,
        using_gml_topology,
    )
    .map_err(|e| color_eyre::eyre::eyre!(e))?;

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
        agent_endpoints,
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

    // Assign alternate node implementations (e.g. cuprate) to eligible relay
    // nodes. Empty node_implementations => empty map => every node is monerod.
    let node_impl_assignment =
        compute_node_impl_set(&user_agents, simulation_seed, node_implementations);
    if !node_impl_assignment.is_empty() {
        log::info!(
            "Node implementations: {} node(s) assigned a non-monerod implementation",
            node_impl_assignment.len()
        );
    }

    // Custom hard fork schedules are monerod-only in this version. Cuprate's
    // FakeChain table is compiled in (all forks at height 1) and
    // CupratedImpl::render silently drops daemon options it doesn't know, so
    // mixing the two would produce cuprate nodes that reject the forked chain
    // with no error at generation OR boot time. Refuse up front.
    let hf_knob_used = daemon_defaults
        .map(|d| d.contains_key(HF_SCHEDULE_KNOB))
        .unwrap_or(false)
        || user_agents.iter().any(|(_, cfg)| {
            cfg.daemon_options
                .as_ref()
                .map(|o| o.contains_key(HF_SCHEDULE_KNOB))
                .unwrap_or(false)
                || args_mention_hf_knob(cfg.daemon_args.as_ref())
                || cfg
                    .daemon_phases
                    .as_ref()
                    .map(|phases| {
                        phases
                            .values()
                            .any(|p| args_mention_hf_knob(p.args.as_ref()))
                    })
                    .unwrap_or(false)
        });
    if hf_knob_used && !node_impl_assignment.is_empty() {
        return Err(color_eyre::eyre::eyre!(
            "fakechain-hard-forks is set but general.node_implementations assigns \
             non-monerod nodes: cuprate has no custom hard fork schedule support, \
             so those nodes would reject the forked chain. Remove \
             node_implementations or the hard fork schedule."
        ));
    }
    // Probe results for binary_supports_hf_schedule, shared across all agents.
    let mut hf_capability_cache: HashMap<String, bool> = HashMap::new();

    // Native mining: monerod's own miner thread mines, throttled by
    // --sim-hash-interval-ms, instead of a Python agent firing generateblocks.
    // See docs/NATIVE_MINING.md.
    use crate::utils::mining::{
        args_mention_sim_knob, binary_supports_sim_mining, equilibrium_difficulty,
        hash_interval_ms, is_native_miner_script, SIM_HASH_INTERVAL_KNOB, SIM_RX_FULL_DATASET_KNOB,
    };
    let native_mining = mining.is_native();
    let mut sim_capability_cache: HashMap<String, bool> = HashMap::new();
    if native_mining {
        let total: u64 = user_agents
            .iter()
            .filter_map(|(_, cfg)| cfg.hashrate.map(|h| h as u64))
            .sum();
        log::info!(
            "Native mining: {} miner(s), total hashrate {} h/s, equilibrium difficulty ~{}",
            user_agents.iter().filter(|(_, c)| c.is_miner()).count(),
            total,
            equilibrium_difficulty(total)
        );
    }
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

        // Hard fork schedule: the knob may live in the merged options OR in raw
        // daemon args, but not both — options_to_args() and the raw args are
        // both emitted, and monerod (boost::program_options) aborts on a
        // duplicated scalar option.
        let hf_in_options = merged_daemon_options.contains_key(HF_SCHEDULE_KNOB);

        // The sim-mining knobs are derived (mode + hashrate), never set by
        // the user directly, and native mining doesn't support daemon
        // phases on miners yet (the knob is injected into the single
        // daemon launch only).
        let sim_in_options = merged_daemon_options.contains_key(SIM_HASH_INTERVAL_KNOB)
            || merged_daemon_options.contains_key(SIM_RX_FULL_DATASET_KNOB);
        let sim_in_raw_args = args_mention_sim_knob(user_agent_config.daemon_args.as_ref())
            || user_agent_config
                .daemon_phases
                .as_ref()
                .map(|phases| phases.values().any(|p| args_mention_sim_knob(p.args.as_ref())))
                .unwrap_or(false);
        if sim_in_options || sim_in_raw_args {
            return Err(color_eyre::eyre::eyre!(
                "Agent '{}': {} / {} is set directly in daemon options/args. It is derived \
                 from general.mining (mode: native) and the agent's hashrate; remove it.",
                agent_id, SIM_HASH_INTERVAL_KNOB, SIM_RX_FULL_DATASET_KNOB
            ));
        }
        if native_mining && is_miner && has_daemon_phases {
            return Err(color_eyre::eyre::eyre!(
                "Agent '{}': native mining does not support daemon phases on miners in this \
                 release (the mining knob is injected into the single daemon launch only).",
                agent_id
            ));
        }
        if native_mining && is_miner {
            let hs = user_agent_config.hashrate.unwrap_or(1);
            merged_daemon_options.insert(
                SIM_HASH_INTERVAL_KNOB.to_string(),
                OptionValue::Number(hash_interval_ms(hs) as i64),
            );
            if mining.rx_full_dataset {
                merged_daemon_options
                    .insert(SIM_RX_FULL_DATASET_KNOB.to_string(), OptionValue::Bool(true));
            }
        }

        let hf_in_raw_args = args_mention_hf_knob(user_agent_config.daemon_args.as_ref())
            || user_agent_config
                .daemon_phases
                .as_ref()
                .map(|phases| {
                    phases
                        .values()
                        .any(|p| args_mention_hf_knob(p.args.as_ref()))
                })
                .unwrap_or(false);
        if hf_in_options && hf_in_raw_args {
            return Err(color_eyre::eyre::eyre!(
                "Agent '{}': fakechain-hard-forks is set in daemon_options/daemon_defaults \
                 AND in raw daemon args; monerod aborts on duplicate options. Set it in \
                 exactly one place (for phase-based upgrades: per-phase args only).",
                agent_id
            ));
        }

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

        // Peer/connection args (pre-formatted monerod flag strings), computed
        // once. Lifted verbatim from the former build_daemon_args_base closure so
        // MonerodImpl::render can append them after the DNS flags in the exact
        // historical order (the tests/golden/* snapshots enforce byte-identity).
        let is_eclipsed = user_agent_config
            .attributes
            .as_ref()
            .map(|attrs| attrs.get("eclipsed").map_or(false, |v| v == "true"))
            .unwrap_or(false);
        let peer_args: Vec<String> = {
            let mut pa: Vec<String> = Vec::new();
            // Initial fixed connections for miners / seeds. Eclipsed agents
            // have no ring/seed links (build_peer_topology skipped them);
            // their only peering comes from the `peers:` pins below.
            if is_miner && !is_eclipsed {
                if let Some(conns) = miner_connections.get(*agent_id) {
                    for conn in conns {
                        pa.push(conn.clone());
                    }
                }
            } else if is_seed_node || seed_nodes.iter().any(|e| e.is_seed_node && e.index == i) {
                if let Some(conns) = seed_connections.get(*agent_id) {
                    for conn in conns {
                        pa.push(conn.clone());
                    }
                }
            }
            // Peer connections for regular agents. Eclipsed agents bootstrap
            // nowhere: no --seed-node list, no topology links — whoever they
            // talk to must be pinned explicitly via `peers:`.
            let is_actual_seed_node = seed_nodes.iter().any(|e| e.index == i);
            if !is_miner && !is_actual_seed_node && !is_eclipsed {
                for seed_node in seed_agents.iter() {
                    if !seed_node.starts_with(&format!("{}:", agent_ip)) {
                        let peer_arg = if matches!(peer_mode, PeerMode::Dynamic) {
                            format!("--seed-node={}", seed_node)
                        } else {
                            format!("--add-priority-node={}", seed_node)
                        };
                        pa.push(peer_arg);
                    }
                }
                if matches!(peer_mode, PeerMode::Hybrid) {
                    if let Some(topo) = topology {
                        let topology_connections =
                            generate_topology_connections(topo, i, &all_agent_ips, &agent_ip);
                        for conn in topology_connections {
                            pa.push(conn);
                        }
                    }
                }
            }
            // Explicit `peers:` pins — agent-id references resolved to
            // ip:port. Eclipsed or not, any agent may pin peers; unknown ids
            // are a hard error (a typo'd pin silently isolates a node).
            if let Some(peers) = user_agent_config.peers.as_ref() {
                if let Some(exclusive) = peers.exclusive.as_ref() {
                    for id in exclusive {
                        let endpoint = agent_endpoints.get(id).ok_or_else(|| {
                            color_eyre::eyre::eyre!(
                                "Agent '{}': peers.exclusive references unknown agent '{}'",
                                agent_id,
                                id
                            )
                        })?;
                        if id == agent_id.as_str() {
                            return Err(color_eyre::eyre::eyre!(
                                "Agent '{}': peers.exclusive references itself",
                                agent_id
                            ));
                        }
                        pa.push(format!("--add-exclusive-node={}", endpoint));
                    }
                }
                if let Some(priority) = peers.priority.as_ref() {
                    for id in priority {
                        let endpoint = agent_endpoints.get(id).ok_or_else(|| {
                            color_eyre::eyre::eyre!(
                                "Agent '{}': peers.priority references unknown agent '{}'",
                                agent_id,
                                id
                            )
                        })?;
                        if id == agent_id.as_str() {
                            return Err(color_eyre::eyre::eyre!(
                                "Agent '{}': peers.priority references itself",
                                agent_id
                            ));
                        }
                        pa.push(format!("--add-priority-node={}", endpoint));
                    }
                }
            }
            pa
        };
        // in/out peer caps from `peers:` ride in daemon_options (scalar
        // flags), merged so an explicit daemon_options setting still wins.
        if let Some(peers) = user_agent_config.peers.as_ref() {
            if let Some(n) = peers.in_peers {
                merged_daemon_options
                    .entry("in-peers".to_string())
                    .or_insert(OptionValue::Number(n));
            }
            if let Some(n) = peers.out_peers {
                merged_daemon_options
                    .entry("out-peers".to_string())
                    .or_insert(OptionValue::Number(n));
            }
        }
        // Raw peer addresses (ip:port) extracted from the monerod-format peer
        // args, for implementations (cuprate) that take a seed list rather than
        // per-peer CLI flags. `--flag=ip:port` -> `ip:port`.
        let peer_addrs: Vec<String> = peer_args
            .iter()
            .filter_map(|a| a.rsplit_once('=').map(|(_, addr)| addr.to_string()))
            .collect();

        // Node implementation for this agent. P1: always monerod — the
        // `node_implementations` selection lands in a follow-up (empty => monerod,
        // keeping output byte-identical). The spec is implementation-independent;
        // the impl renders it into concrete args (+ any config files).
        // Select this agent's node implementation (default monerod). Assignment
        // is empty unless general.node_implementations was set, so the monerod
        // path is unchanged.
        let impl_id: &str = node_impl_assignment
            .get(*agent_id)
            .map(|s| s.as_str())
            .unwrap_or("monerod");
        let node_implementation =
            crate::agent::node_impl::resolve_node_impl(impl_id).ok_or_else(|| {
                color_eyre::eyre::eyre!(
                    "Agent '{}': unknown node implementation '{}'",
                    agent_id,
                    impl_id
                )
            })?;
        let launch_spec = crate::agent::node_impl::NodeLaunchSpec {
            data_dir: format!("{}/monero-{}", daemon_data_dir, agent_id),
            config_dir: format!("{}/cuprate-{}", daemon_data_dir, agent_id),
            agent_ip: agent_ip.as_str(),
            rpc_port: daemon_rpc_port,
            p2p_port,
            process_threads,
            enable_dns_server,
            is_miner,
            daemon_options: &merged_daemon_options,
            peer_args: peer_args.as_slice(),
            peer_addrs: peer_addrs.as_slice(),
        };
        // Gate unsupported placements, then materialize any config files the
        // implementation needs (cuprate's Cuprated.toml) into the stable
        // config_dir (survives the pre-sim `monero-*` cleanup). monerod:
        // preflight Ok + no config files => no-op, output unchanged.
        {
            use crate::agent::node_impl::NodeImplementation;
            if let Err(reason) = node_implementation.preflight(&launch_spec) {
                if !experimental_cuprate_boot {
                    return Err(color_eyre::eyre::eyre!(
                        "Agent '{}': node implementation '{}' cannot be placed: {} \
                         Set general.experimental_cuprate_boot: true to override \
                         (boot-testing only).",
                        agent_id,
                        impl_id,
                        reason
                    ));
                }
                log::warn!(
                    "Agent '{}': placing '{}' despite preflight ({})",
                    agent_id,
                    impl_id,
                    reason
                );
            }
            let rendered = node_implementation.render(&launch_spec, None);
            if !rendered.config_files.is_empty() {
                std::fs::create_dir_all(&launch_spec.config_dir).map_err(|e| {
                    color_eyre::eyre::eyre!(
                        "Agent '{}': create config dir '{}': {}",
                        agent_id,
                        launch_spec.config_dir,
                        e
                    )
                })?;
                for cf in &rendered.config_files {
                    let path = format!("{}/{}", launch_spec.config_dir, cf.rel_path);
                    std::fs::write(&path, &cf.contents).map_err(|e| {
                        color_eyre::eyre::eyre!("Agent '{}': write '{}': {}", agent_id, path, e)
                    })?;
                }
            }
        }
        let build_daemon_args_base = |phase_args: Option<&Vec<String>>| -> Vec<String> {
            use crate::agent::node_impl::NodeImplementation;
            node_implementation.render(&launch_spec, phase_args).args
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

                // Every phase inherits the merged daemon options, so a schedule
                // set there must be understood by every phase's binary; a
                // schedule set in this phase's own args by this phase's binary.
                if (hf_in_options || args_mention_hf_knob(phase.args.as_ref()))
                    && !binary_supports_hf_schedule(&daemon_binary_path, &mut hf_capability_cache)
                {
                    return Err(color_eyre::eyre::eyre!(
                        "Agent '{}' phase {}: fakechain-hard-forks is set but '{}' does not \
                         support it (stock monerod exits on unknown options). Build the \
                         patched binary with ./setup.sh --hardfork and use it for this phase.",
                        agent_id,
                        phase_num,
                        daemon_binary_path
                    ));
                }

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
            // Assigned a non-monerod implementation => use that impl's binary
            // (ignoring any explicit `daemon:` name, which defaults to monerod in
            // configs). Otherwise keep the historical resolution exactly.
            let daemon_binary_path = if impl_id != "monerod" {
                use crate::agent::node_impl::NodeImplementation;
                resolve_binary_path_for_shadow(node_implementation.default_binary()).map_err(
                    |e| {
                        color_eyre::eyre::eyre!(
                            "Agent '{}': failed to resolve '{}' binary: {}",
                            agent_id,
                            node_implementation.default_binary(),
                            e
                        )
                    },
                )?
            } else {
                let is_native_miner = native_mining && is_miner;
                match &user_agent_config.daemon {
                    // Native miners on an unnamed/stock daemon run the patched build.
                    Some(DaemonConfig::Local(path)) if is_native_miner && (path == "monerod") => {
                        log::info!(
                            "Agent '{}': native mining -> daemon monerod-sim (was '{}')",
                            agent_id,
                            path
                        );
                        resolve_binary_path_for_shadow("monerod-sim").map_err(|e| {
                            color_eyre::eyre::eyre!(
                                "Agent '{}': failed to resolve monerod-sim: {}",
                                agent_id,
                                e
                            )
                        })?
                    }
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
                    _ if is_native_miner => {
                        log::info!(
                            "Agent '{}': native mining -> daemon monerod-sim (was unset)",
                            agent_id
                        );
                        resolve_binary_path_for_shadow("monerod-sim").map_err(|e| {
                            color_eyre::eyre::eyre!(
                                "Agent '{}': failed to resolve monerod-sim: {}",
                                agent_id,
                                e
                            )
                        })?
                    }
                    _ => monerod_path.to_string(),
                }
            };

            // A schedule reaches this daemon via merged options or raw
            // daemon_args; either way the binary must actually know the flag
            // (stock monerod exits on unknown options, taking the whole run
            // with it — one host at a time).
            if (hf_in_options || args_mention_hf_knob(user_agent_config.daemon_args.as_ref()))
                && !binary_supports_hf_schedule(&daemon_binary_path, &mut hf_capability_cache)
            {
                return Err(color_eyre::eyre::eyre!(
                    "Agent '{}': fakechain-hard-forks is set but '{}' does not support it \
                     (stock monerod exits on unknown options). Build the patched binary \
                     with ./setup.sh --hardfork and set daemon: monerod-hf for this agent.",
                    agent_id,
                    daemon_binary_path
                ));
            }

            if native_mining
                && is_miner
                && !binary_supports_sim_mining(&daemon_binary_path, &mut sim_capability_cache)
            {
                return Err(color_eyre::eyre::eyre!(
                    "Agent '{}': general.mining.mode is native but '{}' does not support \
                     --sim-hash-interval-ms. Build the patched daemon with ./setup.sh --sim-binary \
                     (miners default to monerod-sim; an explicit daemon: must point at it).",
                    agent_id,
                    daemon_binary_path
                ));
            }

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

            // Issue #4 (wallet persistence): SIGTERM script agents 2
            // sim-minutes before stop_time so base_agent's cleanup can
            // store + close its wallet while wallet-rpc is still alive.
            // The wallet-rpc PROCESS itself is deliberately never signaled:
            // a wedged wallet-rpc ignores SIGTERM (docs/UPGRADE_WALLET_SIGKILL.md),
            // which would turn rare wallet hangs into false run-failures.
            // Skipped for agents that start inside that window.
            let agent_shutdown_time: Option<String> = {
                let start_secs = parse_duration_to_seconds(&agent_start_time).unwrap_or(0);
                simulation_stop_secs
                    .checked_sub(120)
                    .filter(|t| *t > start_secs + 30)
                    .map(|t| format!("{}s", t))
            };

            if is_miner && is_native_miner_script(&script) {
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
                if native_mining {
                    merged_attributes.insert("mining_mode".to_string(), "native".to_string());
                    if let Some(hs) = user_agent_config.hashrate {
                        merged_attributes.insert(
                            "hash_interval_ms".to_string(),
                            hash_interval_ms(hs).to_string(),
                        );
                    }
                    merged_attributes.insert(
                        "daemon_log_path".to_string(),
                        format!("{}/monero-{}/bitmonero.log", daemon_data_dir, agent_id),
                    );
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
                    shutdown_time: agent_shutdown_time.clone(),
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
                    shutdown_time: agent_shutdown_time.clone(),
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
                    shutdown_time: agent_shutdown_time.clone(),
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

/// Regression tests for the 2026-09-23 fix: sort keys for
/// `compute_node_impl_set` / `compute_unreachable_set` / `compute_turnover_set`
/// were the raw `seeded_hash` value, whose high bits are dominated by an id's
/// leading bytes — sorting on it selects contiguous id/name blocks instead of
/// a uniform sample. The fix runs the hash through `finalize_hash` first.
#[cfg(test)]
mod finalize_hash_tests {
    use super::*;

    /// Minimal relay AgentConfig (daemon, no wallet, no hashrate) via YAML —
    /// AgentConfig's fields are all Option so a tiny fragment deserializes.
    fn relay_cfg() -> AgentConfig {
        serde_yaml::from_str("daemon: monerod\n").expect("relay config parses")
    }

    /// Minimal user AgentConfig (daemon + wallet, no hashrate).
    fn user_cfg() -> AgentConfig {
        serde_yaml::from_str("daemon: monerod\nwallet: monero-wallet-rpc\n")
            .expect("user config parses")
    }

    // --- seeded_unit regression: hand-computed against the pre-refactor
    // implementation (raw FNV-1a run through the same splitmix64 finalizer
    // inline) so the extraction into `finalize_hash` is proven bit-identical.
    #[test]
    fn seeded_unit_regression_values() {
        let cases: &[(u64, &str, f64)] = &[
            (12345, "relay-001", 0.3673475940312304),
            (12345, "cs:relay-042:0", 0.7416440006449243),
            (999, "turnover:user-007", 0.4060010101044802),
        ];
        for (seed, key, expected) in cases {
            let got = seeded_unit(*seed, key);
            assert!(
                (got - expected).abs() < 1e-12,
                "seeded_unit({seed}, {key:?}) = {got}, expected {expected}"
            );
        }
    }

    /// Sorting `relay-001..relay-790` by the raw seeded_hash concentrates the
    /// unreachable selection into a couple of ten numeric-suffix deciles
    /// (empirically [79,40,0,0,0,0,0,0,0,0] of 119) because FNV's high bits
    /// track the leading "relay-0"/"relay-1"/... bytes. finalize_hash must
    /// spread the same selection roughly evenly across all ten deciles.
    #[test]
    fn uniformity_finalized_sort_key_spreads_across_deciles() {
        let ids: Vec<(String, AgentConfig)> =
            (1..=790).map(|i| (format!("relay-{i:03}"), relay_cfg())).collect();
        let refs: Vec<(&String, &AgentConfig)> =
            ids.iter().map(|(id, cfg)| (id, cfg)).collect();

        let unreachable = compute_unreachable_set(&refs, 12345, 0.85, None);
        // reachable=0.85 => round((1-0.85)*790) == 119 unreachable.
        assert_eq!(unreachable.len(), 119, "expected round(15% of 790) selected");

        let mut deciles = [0usize; 10];
        for id in &unreachable {
            let num: usize = id.trim_start_matches("relay-").parse().unwrap();
            let idx = ((num - 1) * 10 / 790).min(9);
            deciles[idx] += 1;
        }
        for (i, count) in deciles.iter().enumerate() {
            assert!(
                (3..=30).contains(count),
                "decile {i} has {count} of 119 selected (raw hash gives \
                 [79,40,0,0,0,0,0,0,0,0]) — selection is not uniform"
            );
        }
    }

    /// A prefix/name-based sort must not let group identity determine
    /// selection: with three "medium-*" groups plus a "relay-*" pool, a 13%
    /// selection must include at least one and not all of every group.
    #[test]
    fn prefix_independence_no_group_all_or_nothing() {
        let mut ids: Vec<(String, AgentConfig)> = Vec::new();
        for i in 1..=42 {
            ids.push((format!("medium-a-{i:03}"), user_cfg()));
        }
        for i in 1..=42 {
            ids.push((format!("medium-b-{i:03}"), user_cfg()));
        }
        for i in 1..=41 {
            ids.push((format!("medium-c-{i:03}"), user_cfg()));
        }
        for i in 1..=645 {
            ids.push((format!("relay-{i:03}"), relay_cfg()));
        }
        let refs: Vec<(&String, &AgentConfig)> = ids.iter().map(|(id, cfg)| (id, cfg)).collect();

        // reachable=0.87 => 13% unreachable, split independently per role
        // (relay vs user) inside compute_unreachable_set, so check via the
        // turnover set instead: it treats all non-seed/non-miner ids as one
        // pool, which is what this test wants to exercise.
        let selected = compute_turnover_set(&refs, 777, 0.13);
        assert_eq!(selected.len(), 100, "expected 13% of 770 == 100 selected");

        for prefix in ["medium-a", "medium-b", "medium-c", "relay"] {
            let group_total = ids.iter().filter(|(id, _)| id.starts_with(prefix)).count();
            let group_selected = selected.iter().filter(|id| id.starts_with(prefix)).count();
            assert!(
                group_selected > 0 && group_selected < group_total,
                "group {prefix} selected {group_selected}/{group_total} \
                 (0% or 100% means the sort key still tracks name prefix)"
            );
        }
    }

    #[test]
    fn determinism_same_seed_same_set_different_seed_differs() {
        let ids: Vec<(String, AgentConfig)> =
            (1..=200).map(|i| (format!("relay-{i:03}"), relay_cfg())).collect();
        let refs: Vec<(&String, &AgentConfig)> =
            ids.iter().map(|(id, cfg)| (id, cfg)).collect();

        let a = compute_turnover_set(&refs, 42, 0.3);
        let b = compute_turnover_set(&refs, 42, 0.3);
        assert_eq!(a, b, "same seed must reproduce the same set");

        let c = compute_turnover_set(&refs, 43, 0.3);
        assert_ne!(c, a, "different seed must (overwhelmingly likely) differ");

        let impl_a = compute_node_impl_set(&refs, 42, &BTreeMap::from([("cuprated".into(), 0.3)]));
        let impl_b = compute_node_impl_set(&refs, 42, &BTreeMap::from([("cuprated".into(), 0.3)]));
        assert_eq!(impl_a, impl_b, "same seed must reproduce the same node-impl assignment");
    }
}
