# Selfish-Mining Phase 2 — Design (γ-lifting + stubborn variants)

**Status:** design for review (2026-09-12)
**Base branch:** `feat/native-mining` (holds phase-1; phase-2 builds on it).
**Depends on:** `docs/superpowers/specs/2026-09-12-selfish-mining-apparatus-design.md` (phase 1) and `docs/SELFISH_MINING.md`. Phase 1 validated: attacker share 0.471 vs γ=0 theory 0.484 at α=0.4.

## 1. Goal

Lift the tie-break advantage γ above zero and add the stubborn-mining strategy variants, so the apparatus can explore the full Eyal–Sirer / stubborn-mining parameter space, and measure γ as a function of the attacker's network advantage.

## 2. Key constraint (found during design) and the reframe

monerosim does **not** expose per-agent topology *position*: node placement on the GML graph is assigned globally by the distribution strategy (`src/topology/distribution.rs`), deterministic and identical for all agents. So the original "detector near the honest miners, publisher bridges far away" placement is not achievable per-agent.

What *is* per-agent controllable: **connectivity** — a bridge's outbound degree (`daemon_options: {out-peers: N}`) and its explicit peers (`daemon_args: ["--add-priority-node=ip:port", ...]`), plus reachability (`hide-my-port`). Therefore γ is lifted by **connectivity and fan-out**, not position, and the second experiment is **γ vs attacker connectivity/fan-out** rather than γ vs position. This is still γ as a *measured network outcome* (the attacker's advantage emerges from how widely and quickly it can inject a competing block), which is the scientific point.

**γ mechanism without position control.** The attacker runs N publisher bridges, each priority-connected to honest nodes. On a tie (it has a block at the honest tip's height), the agent — having detected the honest block at a well-connected bridge — immediately `submit_block`s its own block to *all* N publishers via local RPC. A publisher that has not yet received the honest block over P2P adds the attacker's block to its main chain and relays it, racing the honest block onward. With more publishers and a lower `reaction_delay_ms`, more publishers are "ahead" at submit time, so a larger fraction of the honest network builds on the attacker's block: γ rises. γ is small on a tiny low-latency network (margins are sub-millisecond), so phase-2 configs use a larger honest network with latency spread (§7).

## 3. Architecture (delta from phase 1)

Phase 1 already has: the offline miner, one bridge, `SelfishMinerAgent`, `SelfishStrategy`, the bridge's `canonical_chain.json` recorder, and the analysis. Phase 2 changes:

- **`SelfishMinerAgent` → multiple bridges.** `bridge_agent` (one id) becomes `bridges` (a comma-separated list of bridge agent ids). The agent connects to all of them via the registry. It reads the honest tip and forwards honest blocks using the first reachable bridge (they converge on the honest chain). On release it submits each block to *every* bridge. Everything else (the strategy, the forwarder, the offline miner) is unchanged.
- **Bridge connectivity knobs.** Each bridge node in the config carries `daemon_options: {out-peers: N, hide-my-port: false}` and `daemon_args: ["--add-priority-node=<honest ip:port>", ...]` to pin its fan-out. (The attacker config author sets these; the orchestrator already renders them.)
- **`SelfishStrategy` → stubborn variants.** Add `lead_stubborn`, `equal_fork_stubborn`, `trail_stubborn` to the existing `honest`/`eyal_sirer` policy. No new mechanism; these are different release/adopt rules over the same primitive.
- **Analysis → γ + stubborn curves.** Add a realized-γ estimate and the stubborn revenue curves to `selfish_mining_analysis.py`.

No monerod patch, no orchestrator change beyond what phase 1 already does (the multi-bridge wiring is config + the Python agent reading a list; priority-node/out-peers are existing daemon knobs). The one open item is whether the agent needs a richer way to learn honest-node IPs for the `--add-priority-node` lists; phase-1 bridges already join the honest mesh via seeds, so priority nodes are an *optional* amplifier, not required for correctness.

## 4. Stubborn-mining variants

Defined over the same `(private lead a, honest progress h since fork)` state the phase-1 `eyal_sirer` uses (see `agents/selfish_strategy.py`). At γ>0 these differ from classic selfish mining:

- **lead_stubborn:** never give up a lead of 1 — when honest draws even (a becomes 0 after a fork), keep mining on the private block rather than adopting, betting on γ. Publishes to match, never concedes a 1-block race.
- **equal_fork_stubborn:** on a tie (a == h == 1 after the fork), always publish to contest and keep mining privately, never adopting the honest block first.
- **trail_stubborn(j):** keep mining the private chain even when *behind* by up to `j` blocks, abandoning only when the honest lead exceeds `j`. `j` is a strategy parameter.

Each is a branch in `SelfishStrategy.update`, selected by the `strategy` attribute, with parameters from the attributes (e.g. `trail_depth`). The γ=0 single-bridge regime makes all of them collapse toward the honest outcome (ties are lost), so stubborn variants are only interesting at the lifted-γ configs.

## 5. γ measurement

`selfish_mining_analysis.py` gains:
- **realized γ:** over all *ties* (heights where both an attacker-found and an honest-found block exist in the miners' logs at the same height — a race), the fraction the attacker won on the canonical chain. This is the network-level γ the attacker achieved.
- **revenue vs theory at that γ:** compare the measured attacker share to `es_revenue_share(α, γ_measured)` (the existing formula already takes γ), not just the γ=0 curve.
- a γ-vs-configuration table across a sweep of publisher counts.

## 6. Experiments

1. **γ vs fan-out.** Fix α (0.4), vary the number of publisher bridges (e.g. 1, 3, 6) and their priority connections; measure realized γ. Expect γ to rise with fan-out.
2. **Revenue vs α at lifted γ.** At a fixed high-fan-out config, sweep α and compare to the Eyal–Sirer curve at the measured γ (should sit above the γ=0 curve).
3. **Stubborn vs selfish.** At a lifted-γ config and a fixed α, compare `eyal_sirer` against the stubborn variants; reproduce the known ordering (stubborn beats selfish in the γ regime where it should).

## 7. Topology for measurable γ

The phase-1 micro (2 honest miners + 2 relays + 6 seeds, low latency) gives γ ≈ 0 by construction *and* leaves almost no timing margin to lift it. Phase-2 configs use a larger honest network — on the order of 20–40 honest nodes (a mix of miners and relays) drawn across the GML topology so inter-node latencies span a useful range — and several attacker publisher bridges. This is a new config family (`test_configs/selfish_phase2/`), not a change to the micro.

## 8. Validation gates

- **a. γ lifts.** Realized γ at the multi-bridge high-fan-out config is measurably > the single-bridge γ (≈0) at the same α, and rises monotonically with publisher count across the sweep.
- **b. Determinism A/A.** Same seed → identical honest chain.
- **c. Stubborn sanity.** Each stubborn variant runs without wedging and its attacker share matches its theoretical curve at the measured γ within a band; at γ≈0 they do not beat honest.
- **d. Existing suites.** `cargo test`, the full Python suite, and the phase-1 selfish tests still pass; the phase-1 micro result is unchanged (multi-bridge code must not regress the single-bridge path — a one-element `bridges` list behaves exactly as phase-1's `bridge_agent`).

## 9. Deliverables

- `agents/selfish_miner.py`: `bridges` list (multi-bridge connect + release-to-all); keep `bridge_agent` as a one-element alias for backward compatibility with phase-1 configs. Tests.
- `agents/selfish_strategy.py`: the three stubborn variants + parameters. Tests for each transition.
- `scripts/selfish_mining_analysis.py`: realized-γ estimate, revenue-at-measured-γ, γ-vs-config table. Tests.
- `test_configs/selfish_phase2/`: a larger honest-network base + a publisher-count sweep + a stubborn-variant set.
- `docs/SELFISH_MINING.md`: a phase-2 section (multi-bridge, stubborn, γ measurement, the connectivity-not-position reframe). CHANGELOG entry.

## 10. Scope and deferrals

- **In:** multi-bridge γ-lifting via connectivity, the three stubborn variants, realized-γ measurement, the larger topology, the three experiments.
- **Deferred (increment 3):** colluding pool (multiple miner daemons, one private chain), timestamp games (need a template-time offset), and precise topology-position control (would need an orchestrator feature to pin agents to GML vertices).
