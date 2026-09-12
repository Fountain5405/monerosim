# Selfish-Mining Apparatus — Design

**Status:** approved for planning (2026-09-12)
**Base branch:** `feat/native-mining` (this work builds on native mining and lives on
`feat/selfish-mining`).
**Depends on:** the native-mining spec, `docs/superpowers/specs/2026-09-10-native-mining-design.md`
(this realises its §10 phase-2 seam, but by a different mechanism — see §2).

## 1. Goal

Give monerosim a block-withholding attacker so we can run selfish-mining and stubborn-mining
experiments on a Monero-like network: measure attacker revenue share against hashrate, and
measure the network-advantage parameter γ as a function of the attacker's position in the
topology. The apparatus must expose every parameter of the mechanism as a knob.

## 2. Key decision: no daemon patch

The obvious mechanism is a `--withholding` flag in the daemon that gates the relay in
`core::handle_block_found`. We reject it. A withholding flag compiled into a Monero daemon
is a general-purpose selfish-mining weapon and a working reference implementation anyone
could lift, even though our sim daemon is a separate `monerod-sim` binary. We build the
attacker entirely from stock RPCs that monerod already exposes, driven by a Python agent.

This is also the cleaner engineering choice: private-chain height never leaks, because the
withholding daemon never talks to the honest network, so the height-masking work the daemon
patch would have needed (`public_tip` clamps on handshake, timed sync, chain requests,
object requests, fluffy-block height) does not exist here.

**The one wiring change:** the attacker's miner daemon must be launched with `--offline`.
That is a stock monerod flag. It disables P2P (so mined blocks never relay) and, because
`t_cryptonote_protocol_handler` initialises its `m_synchronized` member directly from the
offline flag, it also makes the daemon report `is_synchronized() == true` immediately, which
is what lets `submit_block` pass its `CHECK_CORE_READY()` gate on an isolated node. The sim
today passes `--regtest` but not `--offline`; the orchestrator will add `--offline` for
attacker miner daemons only.

Verified against monero v0.18.5.1:
- `submit_block` → `on_submitblock` → `core::handle_block_found` → `add_new_block`, then
  `relay_block` when the block enters the main chain. Identical path to a P2P block.
- `--offline` only disables P2P; the internal miner still runs; `submit_block` still works.
- `is_synchronized()` returns `!no_sync() && m_synchronized`, and `m_synchronized` is
  constructed from the offline arg, so an offline daemon is "synchronized" from the start.
- `get_block` returns a hex `blob` of the full block, re-submittable via `submit_block`.
- A submitted higher-cumulative-difficulty alt reaches `handle_alternative_block` and
  `switch_to_alternative_blockchain` exactly as a P2P block does.

## 3. Architecture

The attacker is two stock daemons plus one Python agent.

- **Miner daemon** — `monerod-sim` launched `--offline`, native throttled RandomX at the
  attacker's hashrate α·H. Its main chain *is* the private chain, so its block templates
  extend the private chain automatically. Because it is offline, every block it finds is
  withheld by construction.
- **Bridge daemon(s)** — ordinary honest-connected `monerod` nodes with zero hashrate. They
  are the attacker's read path (the honest tip) and write path (block injection). Phase 1
  ships one bridge; the γ experiment adds more at chosen topology positions.
- **`SelfishMinerAgent`** — Python, a subclass of the native miner agent. It owns the
  strategy state machine and moves blocks between miner and bridge over RPC.

```
   honest network  <--relay--  [bridge daemon] <--submit_block-- agent --get_block--> [offline miner]
        |                            ^                              |                   (private chain,
        |  new honest block          |  release private blocks      |  inject honest      native mining)
        +---- get_info/tip ----------+                              +   blocks
```

## 4. Data flow and state

The agent runs a control loop on a sim-time tick (`reaction_delay_ms`, a knob).

1. **Read state.** `get_info` on the bridge gives the honest tip height and cumulative
   difficulty. `get_info` on the miner gives the private tip. The **lead** is the private
   chain's advantage; a **race** is live when the attacker has just matched a freshly
   published honest block at equal height.
2. **Keep the private chain rooted in the honest chain.** When the honest tip advances, the
   agent pulls each new honest block (`get_block` → blob) and `submit_block`s it into the
   offline miner. When the attacker leads, that block lands as an alt and the miner keeps
   mining privately; when honest overtakes, the miner reorgs onto it. Both are correct
   states and both are automatic. Phase 1 forwards honest blocks from genesis, so the
   miner never needs to sync from peers.
3. **Withhold.** Blocks the offline miner finds are detected the way native mode already
   detects them (log scan / `get_block` by height) and held.
4. **Release.** On the strategy trigger the agent pulls the withheld private blocks by
   height and `submit_block`s them, in order, to every bridge. Each bridge relays to the
   honest network. Releasing a matching block into a live race is how the attacker forces
   the honest network to choose (the γ event).

## 5. The strategy engine (all the knobs)

The mechanism gives one primitive — *read the state; release private blocks up to height H*
— and every strategy is a pure Python policy over it. A policy maps
`(private_lead, race_live, just_saw_honest_block)` to an action in
`{do nothing, release up to H, adopt honest / abandon private}`.

Strategies (phase 1 ships honest + Eyal–Sirer; the rest are increment 2, same engine):
- **honest** — never withhold. Baseline; proves the plumbing adds no advantage.
- **eyal_sirer** — the canonical selfish-mining state machine (lead 0 mine on public;
  lead 1 and honest publishes → release the match to start a race; lead 2 and honest
  publishes → release both and win; lead > 2 → release one to keep the lead).
- **lead_stubborn, equal_fork_stubborn, trail_stubborn(j)** — the stubborn-mining variants.
- **generic(lead_k, publish_n, trigger)** — the superset the named strategies specialise.

Knobs, all YAML, all per-attacker:
- `hashrate` (α·H, native h/s) — attacker mining power.
- `strategy` and its parameters (`k`, `n`, `j`, trigger).
- `reaction_delay_ms` — modelled attacker reaction time to an honest block. Under Shadow
  this is deterministic sim time, not a polling artefact; default small.
- `attack_start_height` — let the chain warm up before withholding begins.
- `bridges` — count and topology placement of bridge daemons (the γ lever, increment 2).

## 6. γ is measured, not assumed

γ is the fraction of honest hashpower that builds on the attacker's block when the two
chains are tied. Here it is an outcome: on release, the attacker's block and the honest
block propagate through the real Shadow topology, and each honest miner extends whichever it
saw first. The analysis reads, for each race, which parent the honest network's next block
extended, and reports the realised γ. Raising the attacker's connectivity — more bridges,
more out-peers, better placement — raises γ, which is exactly the second experiment.

## 7. Metrics and analysis

A new analysis script, `scripts/selfish_mining_analysis.py` (stdlib + the existing analysis
deps), over the per-block ledger and each daemon's final chain:
- attacker main-chain block share vs α, plotted against the Eyal–Sirer and stubborn revenue
  curves evaluated at the γ measured in-sim;
- realised γ per race and its distribution;
- orphan / stale rate, reorg depth distribution, honest revenue loss;
- a machine-readable summary and a verdict block for the gate.

## 8. Experiments (chosen)

1. **Revenue share vs α.** Sweep α across a config set, one strategy, plot realised
   main-chain share against theory at the measured γ. Locates the profitability threshold on
   a Monero-like network.
2. **γ vs network position.** Fix α, vary bridge count / out-peers / placement, measure the
   tie-win fraction. Turns γ from an assumed constant into a topology result.

## 9. Validation gates

- **a. Neutral plumbing.** With `strategy: honest`, attacker main-chain share tracks α and
  orphan rate stays at baseline. Proves the two-daemon apparatus adds no advantage by itself.
- **b. Determinism A/A.** Two runs, same seed → identical block-hash sequence on the honest
  chain.
- **c. Eyal–Sirer micro.** At a known α and a topology that pins γ near a known value,
  realised attacker share matches the Eyal–Sirer curve within a stated band.
- **d. Existing suites.** `cargo test`, Python tests, generation smoke, and the native
  micro / 5-way configs still pass.

## 10. Deferred (generalises without redesign)

- **Colluding pool.** Several miner daemons sharing one private tip via a coordinator. The
  agent is per-miner, so this is additive.
- **Multiple independent attackers.** Two or more `SelfishMinerAgent`s with separate
  strategies; free once the policy is per-agent.
- **Timestamp games.** Need a template-time offset, which is a daemon knob; out of scope
  here.

## 11. Scope split

- **Increment 1 (this plan):** the two-daemon plumbing, the `--offline` orchestrator wiring,
  the `SelfishMinerAgent` with honest + Eyal–Sirer policies, the honest-block forwarder, the
  micro config, the revenue-vs-α experiment and its analysis, gates a/b/c/d.
- **Increment 2 (next plan):** stubborn variants, multi-bridge γ lever, the γ-vs-position
  experiment, and the full knob surface.

## 12. Deliverables (increment 1)

- Orchestrator: attacker role in the config schema (`general` / per-agent), `--offline` for
  attacker miner daemons, bridge-daemon wiring; Rust unit tests + a golden.
- Python: `agents/selfish_miner.py` (`SelfishMinerAgent`), any missing RPC wrappers in
  `agents/monero_rpc.py` (`get_block`, `submit_block`, `get_info`,
  `get_block_header_by_height`), unit tests with a mocked RPC covering the Eyal–Sirer state
  transitions and the forwarder.
- Configs: `test_configs/selfish_micro.yaml` and the α-sweep set.
- Analysis: `scripts/selfish_mining_analysis.py` + tests.
- Docs: `docs/SELFISH_MINING.md`; CHANGELOG entry; a pointer from `docs/NATIVE_MINING.md`.
