//! Node-implementation abstraction.
//!
//! monerosim can launch more than one Monero *node implementation* (monerod
//! today; cuprate's `cuprated` next; a third later). This module separates
//! *what a node needs* (the impl-independent [`NodeLaunchSpec`]) from *how a
//! given daemon is invoked* (a [`NodeImplementation`] that renders the spec into
//! a concrete process — args plus any config files to materialize).
//!
//! Design/rationale: `docs/20260723_multi_node_type_architecture.md`.
//!
//! ## Staging
//! This is the P1 core: [`MonerodImpl`] reproduces the historical monerod
//! argument construction **byte-for-byte** (guarded by the `tests/golden/*`
//! snapshot tests). To keep that guarantee the spec currently carries the
//! already-formatted monerod peer-arg strings in [`NodeLaunchSpec::peer_args`]
//! rather than logical peers; those become a logical `PeerRef` list in P2 when a
//! second implementation ([`CupratedImpl`], not yet added) needs to render peers
//! its own way. Likewise `role`/`network` fields are added when an impl other
//! than monerod needs them.

use crate::config::OptionValue;
use crate::utils::options::options_to_args;
use std::collections::BTreeMap;

/// The implementation-independent description of a node process to launch.
///
/// Built once per agent from values the orchestrator already computes, then
/// handed to a [`NodeImplementation`] to render. Borrows its inputs; lives only
/// for the duration of a render call.
pub struct NodeLaunchSpec<'a> {
    /// The node's runtime data directory (already resolved, e.g.
    /// `<root>/monero-<id>`). Wiped and recreated per run.
    pub data_dir: String,
    /// A STABLE per-agent directory for materialized config files (e.g.
    /// `<root>/cuprate-<id>`) — outside the wiped `monero-*` data dirs, so a
    /// generated config written here at generation time survives the pre-sim
    /// cleanup. Used by implementations that need a config file (cuprate);
    /// ignored by monerod.
    pub config_dir: String,
    /// The agent's own IP address (RPC/P2P bind address).
    pub agent_ip: &'a str,
    /// RPC bind port.
    pub rpc_port: u16,
    /// P2P bind port.
    pub p2p_port: u16,
    /// Convenience thread count (0 = unset). Maps to impl-specific thread flags.
    pub process_threads: u32,
    /// Whether a DNS server is present in the sim (gates DNS/seed flags).
    pub enable_dns_server: bool,
    /// Whether this node is a miner (affects seed-node handling).
    pub is_miner: bool,
    /// Merged daemon options (defaults + per-agent + injected floors) — already
    /// assembled by the caller.
    pub daemon_options: &'a BTreeMap<String, OptionValue>,
    /// Pre-formatted, implementation-specific peer/connection args, in order.
    ///
    /// STAGED: monerod flag strings (`--seed-node=…`, `--add-priority-node=…`)
    /// today; becomes a logical peer list in P2.
    pub peer_args: &'a [String],
    /// Raw peer addresses (`ip:port`) for implementations that take a seed list
    /// (cuprate's `seed_nodes`) rather than per-peer CLI flags. Derived from the
    /// same peers as `peer_args`.
    pub peer_addrs: &'a [String],
}

/// What an implementation *can* do — used to gate role assignment (e.g. never
/// assign a miner/wallet role to an impl that can't) and to fail generation
/// early on an unsupported combination.
#[derive(Debug, Clone, Copy)]
pub struct NodeCaps {
    pub can_mine: bool,
    pub can_wallet: bool,
    /// Supports monerosim's regtest/fixed-difficulty fakechain network.
    pub supports_regtest: bool,
    /// Can be pinned to an explicit peer set.
    pub peer_pinning: bool,
}

/// A config file an implementation wants written next to the node before launch.
#[derive(Debug, Clone)]
pub struct ConfigFile {
    /// Path relative to the node's data directory (e.g. `Cuprated.toml`).
    pub rel_path: String,
    pub contents: String,
}

/// The rendered launch: process args plus any config files to materialize.
#[derive(Debug, Clone, Default)]
pub struct RenderedLaunch {
    pub args: Vec<String>,
    pub config_files: Vec<ConfigFile>,
}

/// A launchable Monero node implementation.
pub trait NodeImplementation {
    /// Stable identifier used in configs/logs (`"monerod"`, `"cuprated"`).
    fn id(&self) -> &'static str;
    /// Default binary shorthand (resolved to `~/.monerosim/bin/<name>`).
    fn default_binary(&self) -> &'static str;
    /// Capability set (see [`NodeCaps`]).
    fn capabilities(&self) -> NodeCaps;
    /// Refuse an unsupported spec (e.g. an impl that can't do regtest). Returns a
    /// human-readable reason on rejection.
    fn preflight(&self, spec: &NodeLaunchSpec) -> Result<(), String>;
    /// Render the spec into concrete process args (+ optional config files).
    /// `phase_args` are per-launch extra args (upgrade phases / custom args).
    fn render(&self, spec: &NodeLaunchSpec, phase_args: Option<&Vec<String>>) -> RenderedLaunch;
}

/// The stock `monerod` implementation.
pub struct MonerodImpl;

impl NodeImplementation for MonerodImpl {
    fn id(&self) -> &'static str {
        "monerod"
    }

    fn default_binary(&self) -> &'static str {
        "monerod"
    }

    fn capabilities(&self) -> NodeCaps {
        NodeCaps {
            can_mine: true,
            can_wallet: true,
            supports_regtest: true,
            peer_pinning: true,
        }
    }

    fn preflight(&self, _spec: &NodeLaunchSpec) -> Result<(), String> {
        Ok(())
    }

    fn render(&self, spec: &NodeLaunchSpec, phase_args: Option<&Vec<String>>) -> RenderedLaunch {
        // NOTE: this reproduces the historical `build_daemon_args_base` closure
        // verbatim; the `tests/golden/*` snapshots enforce byte-identical output.
        // Do not reorder or reformat without regenerating the goldens.
        let data_dir = &spec.data_dir;
        let mut args = vec![
            format!("--data-dir={}", data_dir),
            format!("--log-file={}/bitmonero.log", data_dir),
            "--regtest".to_string(),
            "--keep-fakechain".to_string(),
        ];

        // process_threads flags, unless overridden in the merged options.
        if spec.process_threads > 0 {
            if !spec.daemon_options.contains_key("prep-blocks-threads") {
                args.push(format!("--prep-blocks-threads={}", spec.process_threads));
            }
            if !spec.daemon_options.contains_key("max-concurrency") {
                args.push(format!("--max-concurrency={}", spec.process_threads));
            }
        }

        // Configurable options (merged daemon_defaults + per-agent daemon_options).
        // Honor an explicit rpc-bind-ip override (e.g. 0.0.0.0 so a co-located
        // sidecar can reach this node's RPC over the 127.0.0.1 loopback);
        // otherwise bind the node's sim IP below. Skipping the hardcoded flag in
        // that case avoids emitting --rpc-bind-ip twice (boost::program_options
        // does not accept a duplicated single-value option).
        let has_rpc_bind_ip = spec.daemon_options.contains_key("rpc-bind-ip");
        args.extend(options_to_args(spec.daemon_options));

        // Required network binding flags (agent-specific values).
        if !has_rpc_bind_ip {
            args.push(format!("--rpc-bind-ip={}", spec.agent_ip));
        }
        args.extend(vec![
            format!("--rpc-bind-port={}", spec.rpc_port),
            "--confirm-external-bind".to_string(),
            "--rpc-access-control-origins=*".to_string(),
            format!("--p2p-bind-ip={}", spec.agent_ip),
            format!("--p2p-bind-port={}", spec.p2p_port),
        ]);

        // DNS and seed-node settings.
        if !spec.enable_dns_server {
            args.push("--disable-dns-checkpoints".to_string());
        }
        if spec.is_miner && !spec.enable_dns_server {
            args.push("--disable-seed-nodes".to_string());
        }

        // Peer/connection args (pre-formatted by the caller to preserve the
        // exact historical ordering and mode logic).
        args.extend(spec.peer_args.iter().cloned());

        // Phase-specific / custom args last.
        if let Some(custom_args) = phase_args {
            for arg in custom_args {
                args.push(arg.clone());
            }
        }

        RenderedLaunch {
            args,
            config_files: Vec::new(),
        }
    }
}

/// The cuprate (`cuprated`) implementation.
///
/// Renders a `Cuprated.toml` for a FakeChain (regtest) node plus
/// `--config-file`. cuprate's FakeChain network is consensus-compatible with
/// monerod's `--regtest` (network-id / genesis / hardfork schedule), now proven
/// at runtime: a cuprated node boots FakeChain, completes a bidirectional P2P
/// handshake with monerod, and validates + stores monerod-mined blocks (first
/// cross-impl sim 2026-07-23 — see the design doc). Peers are supplied through
/// `p2p.clear_net.seed_nodes`, which is in CANONICAL upstream cuprate as of
/// `e3a869d` (PR #663, merged 2026-08-01) — **no fork required**. A build older
/// than that cannot join an isolated network at all: `clear_net_seed_nodes()`
/// returns `[]` for FakeChain, and cuprate's `deny_unknown_fields` rejects the
/// key outright at daemon start, so `cuprate.pin` gates the version (enforced by
/// run_sim.sh, but only for configs that actually place cuprate nodes).
/// [`render`](CupratedImpl::render) fills the list from the spec's `peer_addrs`;
/// that is what wires a node into the sim topology.
/// cuprated is still EXPERIMENTAL, so [`preflight`](CupratedImpl::preflight)
/// keeps placement behind the caller's explicit opt-in — but the only real
/// remaining gate is MINING (GenerateBlocks RPC is a stub). It *can* back a real
/// `monero-wallet-rpc`: sync and send are both runtime-proven, local and remote
/// (see `docs/20260724_cuprate_wallet_rpc.md`). Its P2P is a full participant —
/// it ingests monerod's peerlists, discovers and connects to the wider mesh
/// beyond its configured seeds, and syncs blocks (all verified 2026-07-23). The
/// noisy "No peers in peer list" churn seen in tiny test nets is just cuprate
/// trying to reach its 32-outbound target in a sub-32-node network; it goes away
/// at realistic scale. Set `out-peers` in the daemon options to pin that target
/// (see [`render`](CupratedImpl::render)) when degree-matching against monerod.
///
/// The thread/memory knobs are pinned deliberately: under Shadow the `/proc`
/// files a node reads to auto-size reflect the *host* (many cores / much RAM),
/// so an un-pinned cuprated would spawn a host-sized thread pool per sim node.
pub struct CupratedImpl;

impl NodeImplementation for CupratedImpl {
    fn id(&self) -> &'static str {
        "cuprated"
    }

    fn default_binary(&self) -> &'static str {
        "cuprated"
    }

    fn capabilities(&self) -> NodeCaps {
        NodeCaps {
            can_mine: false,          // GenerateBlocks RPC is a stub (P3c)
            // Runtime-proven 2026-07-24: a real monero-wallet-rpc synced AND sent
            // through cuprated's RPC (getblocks.bin / get_outs.bin /
            // get_output_distribution.bin / sendrawtransaction, all HTTP 200).
            // See docs/20260724_cuprate_wallet_rpc.md.
            can_wallet: true,
            supports_regtest: true,   // FakeChain, runtime-verified vs monerod regtest
            peer_pinning: false,      // seed_nodes override gives bootstrap seeds, not persistent peer pins
        }
    }

    fn preflight(&self, _spec: &NodeLaunchSpec) -> Result<(), String> {
        Err("cuprated participation is runtime-proven (boots FakeChain, handshakes \
             with monerod, discovers the wider peer mesh from monerod's peerlists, \
             syncs monerod-mined blocks, and backs a real monero-wallet-rpc through \
             its own RPC — sync and send both verified) but remains EXPERIMENTAL: \
             it cannot MINE (GenerateBlocks RPC is a stub), so miners stay monerod. \
             Placement is gated until mining matures; opt into experimental cuprate \
             boot-testing to place cuprated nodes anyway."
            .to_string())
    }

    fn render(&self, spec: &NodeLaunchSpec, _phase_args: Option<&Vec<String>>) -> RenderedLaunch {
        // Pin thread pools (see struct docs). Fall back to a small default when
        // the convenience process_threads is unset.
        let threads = if spec.process_threads > 0 {
            spec.process_threads
        } else {
            2
        };
        // cuprate takes peers as a `seed_nodes` list (ip:port), not per-peer CLI
        // flags. FakeChain ships no built-in seeds, so this is what lets the node
        // join the sim (requires the seed-override config field — cuprate PR).
        let seed_nodes = spec
            .peer_addrs
            .iter()
            .map(|a| format!("\"{}\"", a))
            .collect::<Vec<_>>()
            .join(", ");

        // Outbound-degree pin, driven by the SAME knob monerod uses (`out-peers`),
        // so one config value degree-matches both implementations. Left unset,
        // each keeps its own default — and those differ a lot: monerod 12
        // (P2P_DEFAULT_CONNECTIONS_COUNT) vs cuprate 32 + up to 8 "extra under
        // load", i.e. up to 40. That gap made cuprate nodes hold ~2.4x more
        // concurrent peers at 300-node scale (docs/20260725_cuprate_connection_matrix.md),
        // which is a confound for any propagation A/B. `extra_outbound_connections`
        // is pinned to 0 alongside it because monerod has no equivalent
        // load-triggered overshoot, so leaving it at 8 would not actually match.
        let outbound_pin = match spec.daemon_options.get("out-peers") {
            Some(OptionValue::Number(n)) => Some(*n),
            Some(OptionValue::String(s)) => s.parse::<i64>().ok(),
            _ => None,
        }
        .filter(|n| *n >= 0)
        .map(|n| {
            format!(
                "outbound_connections = {n}\nextra_outbound_connections = 0\n",
            )
        })
        .unwrap_or_default();
        let cuprated_toml = format!(
            r#"# Generated by monerosim — FakeChain (regtest) cuprate node.
# Thread/memory knobs are pinned: under Shadow, /proc reflects the HOST, so
# cuprated's auto-sizing would size a host-sized pool per sim node.
# The `network` TOML field only accepts Mainnet/Testnet/Stagenet; regtest /
# FakeChain is selected via the --regtest CLI flag (added to args below).
network = "Mainnet"
fast_sync = false

[tracing.stdout]
level = "info"

# Full-fidelity log to a file under the node data dir (<data>/<network>/logs/),
# for cross-impl network analysis. cuprate logs block events at INFO but
# TX-relay, P2P connection, and handshake events only at DEBUG, so the FILE sink
# is DEBUG (stdout stays lean at INFO). Rotates daily; an 8h sim stays in one file.
[tracing.file]
level = "debug"
max_log_files = 7

[tokio]
threads = {threads}

[rayon]
threads = {threads}

[storage]
reader_threads = {threads}

[p2p.clear_net]
enable_inbound = true
listen_on = "{ip}"
p2p_port = {p2p}
seed_nodes = [{seeds}]
{outbound_pin}
[rpc.unrestricted]
enable = true
i_know_what_im_doing_allow_public_unrestricted_rpc = true
address = "{ip}"
port = {rpc}

[rpc.restricted]
enable = false

[fs]
fast_data_directory = "{data}"
slow_data_directory = "{data}"
cache_directory = "{data}/cache"
"#,
            threads = threads,
            ip = spec.agent_ip,
            p2p = spec.p2p_port,
            seeds = seed_nodes,
            outbound_pin = outbound_pin,
            rpc = spec.rpc_port,
            data = spec.data_dir,
        );

        RenderedLaunch {
            // --config-file points at the STABLE config_dir (survives cleanup);
            // the config's fs.* data dirs point at the runtime data_dir.
            args: vec![
                "--config-file".to_string(),
                format!("{}/Cuprated.toml", spec.config_dir),
                // Select the regtest/FakeChain network via CLI: mainnet
                // id/genesis + latest hard-fork at height 1, matching monerod
                // --regtest (the `network` TOML field can't express FakeChain).
                "--regtest".to_string(),
                "--skip-config-warning".to_string(),
            ],
            config_files: vec![ConfigFile {
                rel_path: "Cuprated.toml".to_string(),
                contents: cuprated_toml,
            }],
        }
    }
}

/// A resolved, dispatchable node implementation. Enum (not `dyn`) so selection
/// is a cheap value with static dispatch. Add a variant to register a third type.
pub enum NodeImpl {
    Monerod(MonerodImpl),
    Cuprated(CupratedImpl),
}

/// Resolve an implementation id (`"monerod"`, `"cuprated"`) to a handle.
pub fn resolve_node_impl(id: &str) -> Option<NodeImpl> {
    match id {
        "monerod" => Some(NodeImpl::Monerod(MonerodImpl)),
        "cuprated" | "cuprate" => Some(NodeImpl::Cuprated(CupratedImpl)),
        _ => None,
    }
}

impl NodeImplementation for NodeImpl {
    fn id(&self) -> &'static str {
        match self {
            NodeImpl::Monerod(i) => i.id(),
            NodeImpl::Cuprated(i) => i.id(),
        }
    }
    fn default_binary(&self) -> &'static str {
        match self {
            NodeImpl::Monerod(i) => i.default_binary(),
            NodeImpl::Cuprated(i) => i.default_binary(),
        }
    }
    fn capabilities(&self) -> NodeCaps {
        match self {
            NodeImpl::Monerod(i) => i.capabilities(),
            NodeImpl::Cuprated(i) => i.capabilities(),
        }
    }
    fn preflight(&self, spec: &NodeLaunchSpec) -> Result<(), String> {
        match self {
            NodeImpl::Monerod(i) => i.preflight(spec),
            NodeImpl::Cuprated(i) => i.preflight(spec),
        }
    }
    fn render(&self, spec: &NodeLaunchSpec, phase_args: Option<&Vec<String>>) -> RenderedLaunch {
        match self {
            NodeImpl::Monerod(i) => i.render(spec, phase_args),
            NodeImpl::Cuprated(i) => i.render(spec, phase_args),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;

    fn spec<'a>(
        opts: &'a BTreeMap<String, OptionValue>,
        peers: &'a [String],
        data_dir: &str,
        ip: &'a str,
    ) -> NodeLaunchSpec<'a> {
        NodeLaunchSpec {
            data_dir: data_dir.to_string(),
            config_dir: "/cfg/cuprate-relay-001".to_string(),
            agent_ip: ip,
            rpc_port: 18081,
            p2p_port: 18080,
            process_threads: 2,
            enable_dns_server: false,
            is_miner: false,
            daemon_options: opts,
            peer_args: peers,
            peer_addrs: peers,
        }
    }

    #[test]
    fn cuprated_render_emits_fakechain_config() {
        let opts = BTreeMap::new();
        let peers = vec!["11.0.0.1:18080".to_string()];
        let s = spec(&opts, &peers, "/data/monero-relay-001", "11.0.0.5");
        let r = CupratedImpl.render(&s, None);

        assert_eq!(
            r.args,
            vec![
                "--config-file".to_string(),
                "/cfg/cuprate-relay-001/Cuprated.toml".to_string(),
                "--regtest".to_string(),
                "--skip-config-warning".to_string(),
            ]
        );
        assert_eq!(r.config_files.len(), 1);
        assert_eq!(r.config_files[0].rel_path, "Cuprated.toml");
        let toml = &r.config_files[0].contents;
        // FakeChain/regtest comes from the --regtest CLI flag, not the network field.
        assert!(r.args.iter().any(|a| a == "--regtest"));
        assert!(toml.contains("network = \"Mainnet\""));
        assert!(toml.contains("seed_nodes = [\"11.0.0.1:18080\"]"));
        assert!(toml.contains("threads = 2"));
        assert!(toml.contains("p2p_port = 18080"));
        assert!(toml.contains("port = 18081"));
        assert!(toml.contains("listen_on = \"11.0.0.5\""));
        assert!(toml.contains("fast_data_directory = \"/data/monero-relay-001\""));
        // Debug file sink for cross-impl analysis (tx/connection events are DEBUG).
        assert!(toml.contains("[tracing.file]"));
        assert!(toml.contains("level = \"debug\""));
        // No `out-peers` in these options => cuprate keeps its own default (32+8),
        // so nothing is emitted and existing goldens stay byte-identical.
        assert!(!toml.contains("outbound_connections"));
        assert!(!toml.contains("extra_outbound_connections"));
    }

    #[test]
    fn cuprated_out_peers_pins_outbound_degree() {
        // `out-peers` is monerod's knob; cuprate honours it too so one config value
        // degree-matches both implementations for a propagation A/B.
        let mut opts = BTreeMap::new();
        opts.insert("out-peers".to_string(), OptionValue::Number(12));
        let peers = vec!["11.0.0.1:18080".to_string()];
        let s = spec(&opts, &peers, "/data", "11.0.0.5");
        let toml = CupratedImpl.render(&s, None).config_files[0].contents.clone();
        assert!(toml.contains("outbound_connections = 12"));
        // monerod has no load-triggered overshoot, so cuprate's must go to 0 for
        // the match to be real (its default is 8).
        assert!(toml.contains("extra_outbound_connections = 0"));
        // Must land inside [p2p.clear_net], not a later section.
        let clear = toml.split("[p2p.clear_net]").nth(1).expect("clear_net section");
        let clear = clear.split("\n[").next().unwrap();
        assert!(clear.contains("outbound_connections = 12"), "pin escaped its section: {clear}");

        // A string-typed value works too (YAML may quote it).
        let mut opts_s = BTreeMap::new();
        opts_s.insert("out-peers".to_string(), OptionValue::String("20".into()));
        let s2 = spec(&opts_s, &peers, "/data", "11.0.0.5");
        let toml2 = CupratedImpl.render(&s2, None).config_files[0].contents.clone();
        assert!(toml2.contains("outbound_connections = 20"));
    }

    #[test]
    fn cuprated_is_gated_until_seed_override() {
        let opts = BTreeMap::new();
        let peers: Vec<String> = vec![];
        let s = spec(&opts, &peers, "/d", "1.1.1.1");
        assert!(CupratedImpl.preflight(&s).is_err());
        assert!(MonerodImpl.preflight(&s).is_ok());
        let caps = CupratedImpl.capabilities();
        // Mining is the one remaining hard gate (GenerateBlocks is a stub);
        // wallet backing is runtime-proven, so can_wallet is true.
        assert!(!caps.can_mine && !caps.peer_pinning);
        assert!(caps.can_wallet);
        assert!(caps.supports_regtest);
    }

    #[test]
    fn resolve_maps_ids() {
        assert!(matches!(resolve_node_impl("monerod"), Some(NodeImpl::Monerod(_))));
        assert!(matches!(resolve_node_impl("cuprated"), Some(NodeImpl::Cuprated(_))));
        assert!(matches!(resolve_node_impl("cuprate"), Some(NodeImpl::Cuprated(_))));
        assert!(resolve_node_impl("bogus").is_none());
    }
}
