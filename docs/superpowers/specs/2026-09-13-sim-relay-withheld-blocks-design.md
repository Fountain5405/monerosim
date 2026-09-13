# Sim-Only Relay of Withheld Blocks (γ>0 selfish mining) — Design (2026-09-13)

## Goal

Add a **sim-only, default-off `monerod-sim` flag** that lets the attacker's
bridge relay a *withheld, equal-height* block it receives via `submit_block` —
which stock monerod refuses to do ("never relay alternative blocks"). This is the
one missing piece that makes **γ>0 selfish mining** reproducible: with the tie
block actually propagating, the attacker can win a fraction of 1-1 ties (γ),
which lowers the profitability threshold below α≈1/3. Combined with the
`topology_node` placement knob (already shipped) it makes γ a tunable, measurable
outcome instead of the structural ≈0 of phases 1–3.

## Why this is in scope (ethics / dual-use)

The apparatus was deliberately built on stock RPCs + `--offline` to avoid
shipping a reusable selfish-mining weapon (a `--withholding monerod` flag).
Phase-3 established, at the source level, that γ>0 is unreachable without the
daemon relaying the attacker's competing block — i.e. a real selfish miner **runs
a modified daemon**. Leaving that unmodeled means the simulator cannot reproduce
the *realistic* threat. Modeling it here is **defensive research** on a private
simulator: the output is knowledge (the γ curve, and eventually detection
signatures), not a deployed attack. The guardrails that keep this a research
artifact rather than a weapon:

- **Default off.** Stock behavior is unchanged unless `--sim-relay-alt-blocks` is
  explicitly set. The flag is `sim-*` namespaced and documented "simulation only."
- **Minimal blast radius.** The relay change lives only in `handle_block_found`,
  which is reached **only** from local submission (`submit_block` RPC + the miner
  thread) — never from P2P (`handle_incoming_block` is a separate path). So the
  flag makes the daemon relay only blocks *it was asked to submit*, not amplify
  arbitrary alternative blocks from the network.
- **Patched binary only.** The flag exists only in `monerod-sim` (the already-
  patched sim binary), never in a stock `monerod` build.
- **Isolated + unreleased.** Stays on `feat/native-mining`, unmerged, not in any
  released binary; documented as research tooling. It is less turnkey against a
  real network than a standalone P2P injector would be (needs the sim build + the
  whole apparatus to be useful).
- **Not detection-evasion.** The purpose includes studying *how detectable* the
  attack is; the relayed alt-blocks are anomalous and attributable.

## Background (source-confirmed, monero v0.18.5.1)

- **The barrier.** `cryptonote::core::handle_block_found`
  (`src/cryptonote_core/cryptonote_core.cpp:1310-1338`) builds a
  `NOTIFY_NEW_FLUFFY_BLOCK` **from the passed-in block `b`** and relays it via
  `m_pprotocol->relay_block(...)`, but **only** inside `if(bvc.m_added_to_main_chain)`.
  A submitted block that doesn't extend the tip is added by
  `handle_alternative_block` with `m_added_to_main_chain == false` → **no relay**
  (source comment: "never relay alternative blocks", `blockchain.cpp:4685`).
- **`block_verification_context`** (`verification_context.h:65-74`) has
  `m_added_to_main_chain`, `m_verifivation_failed`, `m_already_exists`,
  `m_marked_as_orphaned`, `m_bad_pow`, `m_missing_txs` — but **no**
  `m_added_to_alt_chain`. An accepted alt-block is therefore signalled by
  *absence*: `!m_verifivation_failed && !m_already_exists && !m_added_to_main_chain`.
- **Callers of `handle_block_found`:** only `miner.cpp:594`,
  `core_rpc_server.cpp:2236` (`on_submitblock`), and `:3584`
  (`on_rpc_access_submit_nonce`). All local. P2P blocks never reach it.
- **Reorg rule:** an alternative chain replaces main only on **strictly greater**
  cumulative difficulty (`blockchain.cpp:2096`); an equal-height tie never
  reorgs. (Unchanged — honest nodes keep their normal first-seen behavior; only
  *relay* of the attacker's block is added.)
- **Bridge binary today:** `agents.selfish_bridge` runs **stock `monerod`** —
  `is_native_miner_script` (`src/utils/mining.rs:30-31`) matches only
  `autonomous_miner`/`selfish_miner` ("selfish_bridge is intentionally excluded —
  it is a relay, not a miner"). So today's bridges cannot carry a `--sim-*` flag.
- **Patch pipeline:** `setup.sh install_sim_monerod` (~1131-1211) `git worktree`s
  the pinned monero, `git apply`s `patches/monero-fakechain-hardforks.patch` then
  `patches/monero-sim-mining.patch` (fail-if-not-applied tripwire), builds, and
  installs `~/.monerosim/bin/monerod-sim` (+ `monerod-hf` symlink alias).
- **Flag-adding pattern** (from `patches/monero-sim-mining.patch`, 4 touch
  points): declare an `arg_descriptor`, `command_line::add_arg` in the module's
  `init_options()`, `command_line::get_arg` in `init()`, store a member.

## Design

### 1. The patch — `patches/monero-sim-selfish-relay.patch`

A new, separate patch (kept apart from the mining patch so it's independently
legible and toggleable), applied to `monerod-sim` after the existing two.

- **New flag `--sim-relay-alt-blocks`** (bool, default `false`), added to
  `cryptonote::core` via the 4-touch pattern: `arg_descriptor` +
  `add_arg` in `core::init_options()`, `get_arg` in `core::init()`, stored as
  `m_sim_relay_alt_blocks`.
- **Relay-gate relaxation** in `handle_block_found`: change

  ```cpp
  if(bvc.m_added_to_main_chain)
  ```
  to

  ```cpp
  if(bvc.m_added_to_main_chain ||
     (m_sim_relay_alt_blocks && !bvc.m_verifivation_failed && !bvc.m_already_exists))
  ```
  so an accepted alt-block (from a local submit) is relayed. The relay body is
  unchanged — it already builds the fluffy block from `b`, which is valid for an
  alt-block.
- **Reorg-guard relaxation** for the alt case: the existing early-return
  `if(missed_txs.size() && get_block_id_by_height(get_block_height(b)) != get_block_hash(b))`
  ("reorganize just happened, do not relay") is a *main-chain* sanity check; for a
  deliberately-relayed alt-block it would wrongly fire whenever the block carries
  txs (the main chain holds a different block at that height). The patch skips
  this guard when relaying under the flag. Attacker blocks in the experiment are
  empty (no tx agents), so tx-bearing relay is a **caveat to validate**, not a
  blocker — consistent with the phase-1 "blocks move as bare blobs" caveat.

The patch does **not** touch the reorg rule, `handle_incoming_block`, or any P2P
path. Honest nodes (stock monerod) are unchanged: they receive the attacker's
relayed block and apply normal first-seen — which is exactly the γ race we want
to measure.

### 2. Wiring — bridges must run the patched binary + set the flag

The relay flag exists only in `monerod-sim`, and stock `monerod` would reject the
unknown `--sim-relay-alt-blocks` arg, so a bridge using it must run `monerod-sim`.
Two options; the plan picks after confirming binary-name resolution:

- **Preferred — config-only.** Point the attacker's bridge daemons at the patched
  binary directly in the phase-4 config (`daemon: monerod-hf`, the installed
  monerod-sim alias) plus `daemon_options: {sim-relay-alt-blocks: true}`
  (daemon_options already pass through to the CLI). **No Rust change; existing
  configs and all four goldens stay byte-identical** (only phase-4 configs opt
  in). This is the target design if `monerod-hf`/`monerod-sim` resolves as a
  daemon binary in config (hard-fork configs already use `daemon: monerod-hf`).
- **Fallback — surgical substitution.** If a bare binary name doesn't resolve,
  add a narrow rule at the binary-substitution site (`user_agents.rs` ~1114-1130):
  a daemon whose `daemon_options` contains `sim-relay-alt-blocks` is upgraded to
  `monerod-sim`. Still leaves flag-free configs (phases 1–3) on stock monerod, so
  their goldens are unaffected; only relay-enabled bridges change.

Either way, `is_native_miner_script` is **not** broadened (the bridge stays "a
relay, not a miner" — it gets the sim *binary* for the flag, not miner treatment).

### 3. The γ>0 experiment (phase 4)

A config that combines the two levers, α=0.40, `fixed-difficulty: 1200`,
`eyal_sirer`:

- **Relay flag** on the attacker's bridges (`sim-relay-alt-blocks: true`), so the
  withheld tie-block actually propagates.
- **Placement** via `topology_node`: bridges spread near a chosen honest subset,
  honest finder(s) far, detector central; small `reaction_delay_ms`. The relay
  removes barrier 2 (propagation); placement + fast reaction attack barrier 1
  (winning the first-seen race at those honest nodes).
- **Measure** realized γ with the existing `scripts/selfish_mining_analysis.py`
  (no analysis change — it already computes honest-resolved tie wins). Expect
  γ measurably > 0 now (vs the phase-1/2/3 ≈0). A small sweep (e.g. bridge
  count / spread, or reaction) to show γ trending is a plus.
- **Success = γ clearly above the ≈0 baseline**, with attacker share rising
  toward the Eyal–Sirer γ curve. Report honestly; if the relay works but
  placement still can't win races, that itself is a result (relay is necessary,
  timing still binds).

## Testing

- **Patch builds:** `setup.sh --hardfork` (or the sim-binary build) applies the
  new patch through the existing tripwire (build fails if `git apply` fails) and
  produces `monerod-sim` with `--sim-relay-alt-blocks --help` present. A one-line
  smoke check (`monerod-sim --help | grep sim-relay-alt-blocks`).
- **Config generation:** a golden or targeted test that a bridge configured with
  `daemon: monerod-hf` + `daemon_options: {sim-relay-alt-blocks: true}` emits the
  patched binary path and the `--sim-relay-alt-blocks` flag in the Shadow config.
- **No regression:** the four existing goldens (`orchestrator_selfish/native/
  quickstart/smoke`) stay byte-identical (the change is opt-in per the wiring
  design); full `cargo test` + `pytest` green.
- **End-to-end (empirical):** the phase-4 run shows the attacker's tie-block
  reaching honest daemons (a forensic like phase 2's, but now the orphaned/relayed
  block *does* appear in honest logs) and realized γ > 0.

## Global constraints

- Branch `feat/native-mining`; **local only — never push/merge without explicit go.**
- The flag is default-off, sim-only, `monerod-sim`-only, and relays only
  locally-submitted blocks. Stock monerod and all non-opt-in configs unchanged.
- Python apparatus + `realized_gamma` analysis unchanged (already γ-ready).
- Shared box: scope process ops to `lever65`; `nice` long runs; no `agents/*.py`
  or `venv/` edits while a sim is live.
- Rebuilding `monerod-sim` requires `setup.sh` (adds ~a monero build); schedule it
  when the box is free and no sim is running.

## Risks

- **Tx-bearing alt-block relay** is unvalidated (the fluffy `missed_txs` path);
  the experiment uses empty blocks, so this is a caveat, not a blocker.
- **γ may still be modest** — relay removes barrier 2, but the attacker is still
  reactive, so winning the race needs good placement + low reaction. The
  experiment measures how far the two levers together get.
- **`monerod-sim` rebuild** is a real build step (minutes) and must not run
  against a live sim's binary; do it on a free box.
- **Determinism:** `native_preemption: true` keeps ~0.05 share noise (experiment
  property, not a patch concern).

## Non-goals

- No change to stock `monerod`, to the reorg rule, or to any P2P-received-block
  path. No general "relay all alt-blocks" behavior (only locally-submitted).
- Not merged, not released, not a mainnet tool.
- No new analysis (realized_gamma already measures the outcome).
