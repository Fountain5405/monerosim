> Status: design record of 2026-07-23, kept as history; it may not match the current code. Current docs: docs/README.md.

# Multi-node-type architecture: cuprate + generalizable node implementations

**Date:** 2026-07-23
**Status:** P1/P2 DONE (monerosim) · P3a runtime-proven · P3b (seed-override) DONE.
**★ First cuprate ↔ monerod cross-impl sim PASSED 2026-07-23** — see "Cross-implementation
sim — result". P3c (cuprate mining) is the only remaining optional piece.
**Prereq proven:** stock `cuprated` runs under shadowformonero (spike PASS, see below).

## Goal

1. Run **n% cuprate nodes** in a monerosim network alongside monerod nodes.
2. Do it through a **generalizable node-implementation abstraction** so a *third*
   node type is a small addition, not a rewrite.
3. Long-term: add **mining hooks to cuprate** so we can test more-native PoW
   (on-demand block generation / controllable difficulty) instead of relying only
   on monerod's `generateblocks`.

## Feasibility summary (2026-07-23)

The earlier "three fatal blockers" framing was wrong on two of three; corrected
after user pushback + source/spike verification:

- **Shadow compatibility — RETIRED (proven).** We run *vanilla* guest binaries;
  `shadowformonero` is a fork of **Shadow** (`Shadow 3.3.0 — v0.2.4`), not of
  monerod. A **spike** ran stock `cuprated-0.0.9-x86_64-unknown-linux-gnu`
  (unmodified) under `~/.monerosim/bin/shadow` for a full 90 s sim: **exit 0, no
  crash**, tokio's **epoll** reactor + threads + Fjall DB I/O + P2P socket
  bind + 54 outbound connects all worked. So cuprate needs **no fork for Shadow**.
  Kit: `~/basement_monerosim/20260723_cuprate_shadow_spike/`.
  - Caveats (config-handled): Shadow no-ops `umask`; cuprated reads
    `/proc/{meminfo,stat,cgroup}` which reflect the *host*, so the generated
    `Cuprated.toml` MUST pin `[tokio].threads`, `[rayon].threads`,
    `[storage].reader_threads`, `target_max_memory`.
- **Seed-peer injection — SOFT.** Monero P2P needs only one reachable peer, then
  peer-exchange fills the address book (cuprate already has this). The only gap:
  cuprated's seeds are a hardcoded per-network Rust fn (`clear_net_seed_nodes`)
  with no config override. Trivial to expose — rides along on P3.
- **Regtest / fixed difficulty — THE real blocker.** monerosim's chain is a
  regtest fakechain (fixed difficulty, blocks minted via `generateblocks`).
  `cuprated --network` only accepts `mainnet|testnet|stagenet` (hardcoded genesis,
  real RandomX PoW). cuprate would reject the sim's blocks as invalid. **This is
  the substantive P3 work** — a cuprate contribution adding a regtest-equivalent
  private-network / fixed-difficulty mode. Monero core has the reference impl.

Net: the critical path to real cuprate nodes is **P3 (regtest in cuprate)**. P1/P2
are buildable now and independently useful.

## Current monerosim node model (what P1 refactors)

From a code map of the daemon path (anchors are approximate, pre-refactor):

- `AgentConfig.daemon: Option<DaemonConfig>` where `DaemonConfig::Local(String)` is
  a binary shorthand resolved to `~/.monerosim/bin/<name>` — **binary *selection*
  already works** (`daemon: cuprated` already picks the binary).
  (`src/config/types.rs`, `src/config/agent_config.rs`, `src/utils/binary.rs`.)
- **`build_daemon_args_base()` (`src/agent/user_agents.rs:622-720`)** builds the
  monerod CLI flag list from impl-independent inputs (data-dir, ip, ports, peers,
  role, `--regtest --keep-fakechain`, `--hide-my-port`, `--max-connections-per-ip`,
  `--add-priority-node`/`--seed-node`, thread flags, dns flags). **This is the one
  monerod-specific place** and the core of the refactor.
- Three process-assembly sites (phased / turnover / simple daemon) push
  `ShadowProcess { path, args, environment, ... }` — generic once path+args exist
  (`src/agent/user_agents.rs` ~779 / ~848 / ~861).
- Ports hardcoded (`src/lib.rs`: `MONERO_P2P_PORT 18080`, `MONERO_RPC_PORT 18081`,
  `MONERO_WALLET_RPC_PORT 18082`).
- Python agent RPC (`agents/monero_rpc.py`) is mostly implementation-agnostic;
  only `generateblocks` (mining) is monerod-regtest-specific → **cuprate nodes are
  relay-class** (no wallet, no mining) at first.
- Reachability/turnover selection sets (`compute_unreachable_set`,
  `compute_turnover_set` in `src/agent/user_agents.rs`) are the pattern to mirror
  for node-impl selection (seeded-hash assignment over eligible nodes).

## P1 — the `NodeImplementation` abstraction (monerosim)

Separate *what a node needs* (impl-independent) from *how a daemon is invoked*
(impl-specific).

```rust
struct NodeLaunchSpec {          // built from values monerosim already computes
    data_dir, log_file, ip, p2p_port, rpc_port,
    role: NodeRole,              // Miner | Seed | Relay | User
    network: NetworkModel,       // Regtest { fixed_difficulty } (today always this)
    peers: Vec<PeerRef>,         // logical priority/seed/exclusive peers
    hide_port: bool, max_conn_per_ip: u32, threads: usize,
    disable_dns_checkpoints: bool, disable_seed_nodes: bool,
    extra_options: BTreeMap<String, OptionValue>,  // passthrough daemon_options
    log_level,
}
struct RenderedLaunch { args: Vec<String>, config_files: Vec<ConfigFile> }  // + binary from impl

trait NodeImplementation {
    fn id(&self) -> &str;                       // "monerod" | "cuprated"
    fn binary_name(&self) -> &str;              // default ~/.monerosim/bin shorthand
    fn capabilities(&self) -> NodeCaps;         // can_mine, can_wallet, supports_regtest, peer_pinning
    fn preflight(&self, &NodeLaunchSpec) -> Result<(), Vec<Blocker>>;
    fn render(&self, &NodeLaunchSpec) -> RenderedLaunch;
}
```

- **`MonerodImpl::render`** = move `build_daemon_args_base` verbatim → args;
  `config_files` empty. Capabilities: mine✓ wallet✓ regtest✓ peer_pinning=CLI.
  **Goldens byte-identical at 100% monerod** (hard requirement / regression gate).
- **Selection:** `general.node_implementations: { cuprate: 0.10 }` — a map, so a
  third type is one more entry. Assigned by seeded hash over **eligible relay
  nodes** (capabilities refuse miner/wallet roles); per-agent `daemon:` override
  still wins. Fractions sum ≤ 1.0; remainder defaults to monerod.
- **Wiring changes:** replace the inline `daemon_binary_path` + `build_daemon_args_base`
  calls with: pick impl → build `NodeLaunchSpec` → `impl.render()` → write any
  `config_files` into the run tree → push `ShadowProcess`. Collapse the 3 assembly
  sites onto one shared helper.

## P2 — `CupratedImpl` + gating (monerosim)

- `render()` writes a `Cuprated.toml` into the node's data dir (threads/memory
  **pinned** per the spike caveat; `network` from `NetworkModel`; P2P/RPC bind to
  the sim host IP) and returns args `["--config-file", "<dir>/Cuprated.toml",
  "--skip-config-warning"]`.
- `capabilities` (as shipped): `can_mine=false, can_wallet=false,
  supports_regtest=true` (runtime-verified), `peer_pinning=false` (seed_nodes are
  bootstrap seeds, not persistent pins). `preflight` still **hard-errors** behind an
  `experimental_cuprate_boot` opt-in — but now because cuprate can't mine/wallet,
  *not* because it can't sync: with the P3b seed-override a placed cuprate relay
  boots, peers with monerod, and syncs the regtest chain (see the result section).

## P3 — cuprate regtest fork (`Fountain5405/cuprate`)

- **Fork set up** 2026-07-23: `origin = Fountain5405/cuprate`,
  `upstream = Cuprate/cuprate`, cloned to `/home/lever65/monerosim_scale/cuprate`
  (mirrors the shadowformonero convention). Workflow: feature branches on our fork,
  PRs back to upstream where they're generally useful.
- **Scope — MUCH smaller than expected.** A cuprate code map (2026-07-23,
  verified against the clone) found cuprate **already has a `FakeChain` network
  variant**, config-selectable (`network = "FakeChain"`, `config.rs:135` /
  `network.rs:62` / `args.rs:98`) and wired to consensus
  (`Network::FakeChain => ContextConfig::fake_chain()`, `config.rs:338`).
  **`fixed_difficulty` is already implemented** (`consensus/context/difficulty.rs:295‑297`),
  PoW is FakeChain-aware (`consensus/rules/blocks.rs:105‑120`), and tests already
  `generate_block()` with `fixed_difficulty=Some(1)`. FakeChain uses
  `MAINNET_NETWORK_ID` and has an **empty seed list** (`p2p.rs:400`). So the real
  remaining work is:
  1. **Config seed-peer override** — the substantive piece. FakeChain has zero
     hardcoded seeds, so a sim node must be handed a peer. Add a config-provided
     seed/initial-peer list (`binaries/cuprated/src/config/p2p.rs:398‑434` +
     `config.rs`; consumed at `p2p/.../connection_maintainer.rs:106‑109`).
  2. **Verify / align FakeChain ↔ monerod `--regtest --keep-fakechain`** — genesis,
     network-id, difficulty, hardfork schedule must match so blocks validate
     cross-implementation. **✅ RUNTIME-verified 2026-07-23** — cuprate synced
     monerod-mined blocks (matching hashes) to tip; see the result section.
  3. **(Optional) `GenerateBlocks` RPC** (stub at `rpc/.../rpc_handler.rs:74‑86`) —
     only if we want cuprate nodes to *mine* (the native-PoW / mining-hooks goal).
     Relay-class cuprate nodes syncing monerod-mined blocks need only 1 + 2.
- **Build-from-source blocker:** cuprate `main` pulls `sysinfo 0.39.6` which needs
  **rustc ≥ 1.95** (box has 1.92) → run `rustup update` before P3b source work.
  System C/C++ deps (cmake/clang/gcc) are present. The **prebuilt 0.0.9 gnu binary**
  covers P2 boot-testing, so this blocks neither P1 nor P2.

## Cross-implementation sim — result (2026-07-23)

**First successful cuprate ↔ monerod cross-implementation simulation.** After P3b
(the seed-node config override) shipped on the fork, an E2E run on the real GML
topology (`gml_processing/1200_nodes_caida_with_loops.gml`; 15 hosts — 2 monerod
miners/seeds + 4 relays with `node_implementations: {cuprated: 0.5}` +
`experimental_cuprate_boot`, so 2 relays render as `cuprated`) proved the interop
end to end. Shadow exit 0, **0 processes failed**.

- **Boots FakeChain, consensus-aligned with monerod regtest.** cuprated
  initialized at chain-height 1, hard-fork **V16** — matching monerod
  `--regtest --keep-fakechain` exactly.
- **Bidirectional P2P handshake.** monerod logged both `[<cuprate-ip> INC]` and
  `[<cuprate-ip>:18080 OUT]` for each cuprate node — connections both directions.
- **Cross-impl block propagation + validation.** `NOTIFY_NEW_FLUFFY_BLOCK`
  relayed through the cuprate nodes; cuprated logged `incoming_block: Successfully
  added block` for heights 1–5 with hashes **byte-matching** monerod's height-2…6
  blocks. cuprate validated and stored monerod-mined blocks to the tip.

This upgrades **P3a from static-verified to runtime-proven**: network-id, genesis,
and hard-fork schedule are not merely statically identical — a cuprated node
validated and stored a monerod-mined fakechain over live P2P.

Reproducibility: the run was isolated from a concurrent full-scale sim without a
worktree — set `general.daemon_data_dir` / `general.shared_dir` to a private
namespace, invoke `target/release/monerosim --config <cfg> --output <dir>`
directly, then `shadow -d <dir>/shadow.data <dir>/shadow_output/shadow_agents.yaml`.

### Peer discovery — verified working (not a bug)

A debug-level repro (cuprated `[tracing.stdout] level = "debug"`) confirmed cuprate
is a **full P2P participant**, not a seed-pinned leaf. It ingests monerod's
peerlists (`handshaker.rs` → `AddressBook: Received new peer list, length: 7…11`)
and `connect_to_outbound_peer`s to the wider mesh — in the repro, all reachable
peers (both miners, the *other* cuprate node, a monerod relay, and 6 fallback
seeds = 11 distinct). The noisy `No peers in peer list` / `already connected`
churn is **benign**: cuprate trying to fill its 32-outbound target in a
sub-32-node test net; it disappears at realistic scale. (An earlier "stuck on 2
seeds" read was an info-level-logging artifact — the successful
`connect_to_outbound_peer` lines are DEBUG-only.)

One real-but-inconsequential cuprate quirk: `connect_to_random_seeds`
(`p2p/p2p/src/connection_maintainer.rs:141`) opens a throwaway probe connection to
harvest peers and can't re-harvest a seed it is already connected to — cosmetic,
since passive handshake/timed-sync ingestion does the real discovery. Candidate
for a low-priority upstream cleanup (fits the PR-back-to-cuprate workflow).

**Net:** relay-class cuprate nodes — P2P peer + block sync — work today. The only
remaining cuprate gates are **mining** (GenerateBlocks stub, P3c) and **wallet**.

## Phasing & status

| Phase | Where | Status |
|---|---|---|
| Shadow-compat spike | — | ✅ PASS (2026-07-23) |
| Fork setup | Fountain5405/cuprate | ✅ done |
| Cuprate consensus/network code map | cuprate | ✅ done — FakeChain already exists; P3 shrank to seed-override + interop-verify |
| P1 abstraction + selection | monerosim | ✅ done — branch `feat/multi-node-type`; byte-identical goldens; `node_implementations` fraction selection, gated cuprate wiring |
| P2 CupratedImpl render + wiring | monerosim | ✅ done (generation-level) — cuprate relays get cuprated binary + `--config-file` + a materialized FakeChain `Cuprated.toml`; gated by `experimental_cuprate_boot` |
| P2 boot-test (cuprate in a real sim run) | monerosim | ✅ done — cross-impl sim PASS 2026-07-23 (boots, peers, syncs; see result section) |
| P3a verify FakeChain ↔ monerod-regtest interop | cuprate | ✅ RUNTIME-verified 2026-07-23 — cuprate validated+stored monerod-mined blocks (matching hashes) to tip |
| P3b config seed-peer override | cuprate fork | ✅ done — `seed_nodes` on fork branch `feat/config-seed-nodes` (@30dd459), pushed; monerosim wiring emits it into `Cuprated.toml` |
| P3c GenerateBlocks RPC (cuprate mining) | cuprate fork | ⏳ optional / native-PoW |

## Regression gates

- `node_implementations` unset / 100% monerod ⇒ generated `shadow_agents.yaml`
  **byte-identical** to pre-refactor (cargo goldens + quickstart smoke).
- cuprate nodes never assigned miner/wallet roles (capability-enforced).
- With cuprate selected + no `--experimental-cuprate-boot`, generation **fails
  loudly** (preflight) until P3.
