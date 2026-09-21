# Selfish Mining

**Status:** phase 1 shipped (opt-in) 2026-09-12: the single-bridge, γ≈0
withholding apparatus, the Eyal–Sirer strategy, and the revenue-share
analysis. Phase 2 shipped (opt-in) 2026-09-12: multi-bridge γ-lifting, the
`forward_to` mechanism, the three stubborn-mining variants, and the
realized-γ estimator — see §8. Every task's unit and golden tests passed at
commit time; the simulation-based validation gates (§6 a-c, §8.6 a-d)
require an actual run and are executed by the user, not as part of building
this. Builds on native mining (`docs/NATIVE_MINING.md`). Colluding pool,
timestamp games, and precise topology-position control remain deferred —
see §8.7.

## 1. What it is

The selfish-mining apparatus adds a block-withholding attacker on top of a
native-mining simulation, so monerosim can run Eyal–Sirer-style
selfish-mining experiments **without a monerod source patch**. The attacker
is two stock daemons plus one Python agent:

- **The miner daemon** is `monerod-sim`, launched with
  `daemon_options: {offline: true}` (renders to the stock `--offline`
  flag) and native throttled RandomX at the attacker's declared hashrate
  (`general.mining.mode: native`, the same mechanism an honest native miner
  uses). `--offline` disables P2P, so every block this daemon finds is
  withheld by construction — there is nowhere for it to relay to. It also
  makes the daemon's `is_synchronized()` true immediately, which is what
  lets `submit_block` pass the readiness gate on an isolated node.
- **The bridge daemon** is an ordinary, fully-connected `monerod` relay with
  zero hashrate. It is the attacker's only read/write path to the honest
  network.
- **`SelfishMinerAgent`** (`agents/selfish_miner.py`) runs on the miner
  daemon's host. It owns the strategy state machine and moves blocks
  between the two daemons over stock JSON-RPC (`get_info`, `get_block`,
  `submit_block`) — the same calls any monerod client can make. Native
  mining's own patch (`patches/monero-sim-mining.patch`) only throttles
  hash-rate and applies identically to attacker and honest miners; the
  withholding mechanism itself needs no daemon change at all.

Phase 1 ships exactly one bridge, which fixes the network-advantage
parameter γ ≈ 0: stock `handle_block_found` only relays a submitted block
once it enters the bridge's *main* chain, and an equal-height alt is stored,
not relayed. So the attacker loses every tied race by construction. That is
not a bug — it is the canonical Eyal–Sirer γ = 0 baseline (profitable above
α ≈ 1/3), and it is the correct phase-1 comparison point. Raising γ needs
more bridges and fan-out (not topology position, §8.4); that is phase 2
(§8).

## 2. How it works

Each tick (`reaction_delay_ms` sim-milliseconds, a config knob) the agent's
`run_iteration`:

1. Drives its own daemon's native-mining lifecycle (inherited from
   `AutonomousMinerAgent._native_run_iteration`) so the offline miner keeps
   hashing.
2. Connects to the bridge if it hasn't yet (discovery below); retries every
   second until the bridge is registered.
3. Reads the honest tip height from the bridge (`get_info().height`) and
   the private tip height from its own daemon.
4. **Forwards** any honest blocks the offline miner hasn't seen yet
   (`_forward_public_blocks`): pulls each new block by height from the
   bridge (`get_block`) and `submit_block`s it into the offline miner. This
   keeps the private chain rooted in the honest chain — while the attacker
   leads, the forwarded block lands as an alt and the miner keeps building
   privately; when honest overtakes, the miner reorgs onto it. Phase 1
   forwards from genesis, so the miner never needs to sync from peers.
5. Asks the strategy for a decision, given the two heights.
6. **Releases** (`_release_up_to`) any private blocks the strategy calls
   for: pulls them by height from its own daemon and `submit_block`s them
   to the bridge, in order. A block the bridge accepts into its main chain
   is relayed to the honest network exactly as a normal P2P block would be.
   A block the bridge rejects (the equal-height alt it already holds — the
   γ=0 tie case) raises an `RPCError` that is logged at debug and skipped;
   that is expected, not a fault.

The strategy (`agents/selfish_strategy.py`, `class SelfishStrategy`) is
pure and holds no RPC state. Its one method,
`update(pub_height, priv_height) -> ReleaseDecision(release_to, adopt_public)`,
is called once per tick. It tracks `fork`, the height at which the two
chains last agreed, and reasons in branch lengths since the fork:
`a = priv_height - fork` (private lead), `h = pub_height - fork` (honest
catch-up).
- `"honest"` always releases everything immediately — the neutral-plumbing
  baseline (gate a, §6).
- `"eyal_sirer"` withholds outright while honest hasn't published anything
  since the fork (`h == 0`) or while its lead is two or more blocks clear
  of honest's catch-up (`a - h >= 2`); adopts the honest chain the moment
  it overtakes (`a < h`, or `a == 0` while `h > 0`); reveals-and-wins as
  soon as honest has closed to exactly one block behind (`a - h == 1`,
  releasing the whole private branch and moving `fork` to `priv_height`);
  and on an exact tie (`a == h >= 1`) also releases the whole private
  branch without moving `fork` — releasing it is what lets the attacker
  still win if it extends the private chain again next tick, since at γ=0
  the tie itself never propagates to the honest network.

**Bridge discovery.** The bridge runs a second, trivial agent,
`SelfishBridgeAgent` (`agents/selfish_bridge.py`), whose only job is to
exist: `BaseAgent.setup()` calls `_register_self()`, which publishes the
bridge's `ip_addr` and `daemon_rpc_port` into the shared
`agent_registry.json`. The attacker's `bridge_agent` attribute names that
agent id; `SelfishMinerAgent._connect_bridge()` reads `agent_registry.json`
and looks it up. A plain relay daemon with no script never runs a Python
process and so never registers — the bridge needs this do-nothing agent
purely to become discoverable.

At cleanup, the bridge agent also records its own final main chain
(`_cleanup_agent`) — height → block hash, from height 1 to tip — to the
shared `canonical_chain.json`. At γ ≈ 0 the bridge's main chain *is* the
honest canonical chain (a lost tie never entered it), so this is the ground
truth the analysis (§4) attributes canonical blocks against.

## 3. Config

`test_configs/selfish_micro.yaml` is the reference config:

```yaml
general:
  mining:
    mode: native              # required: both honest and attacker mine natively
agents:
  honest-001:                 # + honest-002, hashrate 3 each = 6 h/s honest total
    script: agents.autonomous_miner
    hashrate: 3
  attacker-miner:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.selfish_miner
    hashrate: 4                    # alpha = 4 / (4 + 6) = 0.4
    daemon_options:
      offline: true                # the one wiring change: withholds by construction
    attributes:
      strategy: eyal_sirer         # or "honest" for the neutral-plumbing gate
      bridge_agent: attacker-bridge
      attack_start_height: "0"     # withhold from genesis (no warm-up)
      reaction_delay_ms: "200"     # tick every 200 sim-ms
  attacker-bridge:
    daemon: monerod
    script: agents.selfish_bridge  # registration-only; no wallet, no hashrate
```

`daemon_options: {offline: true}` goes through the same generic
options-to-args mechanism as any other daemon flag — nothing
selfish-mining-specific there. The only orchestrator change this feature
needed is recognising `agents.selfish_miner` as a native-mining agent for
the wallet-hybrid path (`src/utils/mining.rs::is_native_miner_script`).

`attributes`, read by `SelfishMinerAgent.__init__` (all optional except
`bridge_agent`):

| Key | Meaning | Default |
|---|---|---|
| `strategy` | `"honest"` or `"eyal_sirer"` | `"honest"` |
| `bridge_agent` | agent id of the bridge node | required |
| `attack_start_height` | block count before which the attacker behaves like `honest` (lets the chain warm up) | `0` |
| `reaction_delay_ms` | tick interval, sim-milliseconds | `200` |

**α = attacker fraction of hashrate** =
`attacker_hashrate / (attacker_hashrate + honest_hashrate_total)`, read
directly off the config's `hashrate` fields (`agents.selfish_miner` vs
`agents.autonomous_miner`) — the same quantity
`scripts/selfish_mining_analysis.py` uses for the theory curve. The
α-sweep set, `test_configs/selfish_sweep/`, holds everything else fixed
(same seed, same shape as `selfish_micro.yaml`) and varies only the split:

| Config | Honest h/s | Attacker h/s | α |
|---|---|---|---|
| `alpha_0300.yaml` | 4 + 3 = 7 | 3 | 0.30 |
| `alpha_0400.yaml` (same split as `selfish_micro.yaml`) | 3 + 3 = 6 | 4 | 0.40 |
| `alpha_0450.yaml` | 6 + 5 = 11 | 9 | 0.45 |

`scripts/test_selfish_configs.py` asserts the offline/bridge/attribute
invariants and the α arithmetic across all four config files.

## 4. Running the micro gate

Generation only, no Shadow run (checks the config renders):

```bash
cargo build --release
./target/release/monerosim --config test_configs/selfish_micro.yaml --output /tmp/selfish_gen_check
```

A real run (shared box — `nice` it, as with any long simulation):

```bash
nice -n10 ./run_sim.sh --config test_configs/selfish_micro.yaml --name selfish_micro --no-monitor
```

Then analyse it:

```bash
venv/bin/python scripts/selfish_mining_analysis.py archived_runs/<run_id>
```

The analysis looks for the bridge's `canonical_chain.json` under the run
directory (or `--chain <path>` to point at it directly), and for every
miner named in the config (`agents.selfish_miner` and
`agents.autonomous_miner`) parses `Found block <hash> at height N` lines
out of `shadow.data/hosts/<miner>/monerod*.stdout` — the same log line and
regex (`scripts.native_mining_check.FOUND`) the native-mining gate uses.
It joins the two: every canonical-chain hash is looked up in the hash→finder map
built from all miners' found-block logs, so `attacker_share_from_chain` is
the fraction of the bridge's actual main chain the attacker found —
including blocks it mined offline and later won by out-lengthening the
honest chain. `orphan_stats` separately reports how many of the attacker's
*found* blocks never made it into that canonical chain — the γ=0 lost-tie
blocks show up here, not in the share.

It writes `<run_dir>/analysis_output/selfish/report.md`, prints the same
report to stdout, and exits 0 if every verdict passes, 1 if any fails, 2 if
required inputs (the config, the canonical chain) are missing.

**What a PASS looks like:** two verdicts, both evaluated at the config's
own α:
- the measured attacker canonical-chain share is within 0.10 (absolute) of
  `es_revenue_share(alpha, gamma=0)`, the Eyal–Sirer γ=0 theory curve;
- if α > 0.34 (comfortably past the ≈1/3 profitability threshold), the
  measured share must also exceed α itself — proof the attacker does
  better than mining honestly.

## 5. What phase 1 does NOT do

Phase 1 is the single-bridge γ≈0 plumbing and the Eyal–Sirer state machine
only. Deferred to increment 2 (design spec §10 "Deferred" and §11 "Scope
split"):

- **γ-lifting.** Raising γ above 0 needs a released tie block to reach
  honest nodes *before* the honest block does. Phase 1 ships exactly one
  bridge, so γ≈0 by construction; phase 2 (§8.1, §8.4) ships the multi-bridge
  `bridges` attribute and lifts γ via fan-out/connectivity rather than the
  originally-envisioned "detector placed away from publishers" position,
  since monerosim assigns topology position globally, not per agent.
- **Stubborn-mining variants** (`lead_stubborn`, `equal_fork_stubborn`,
  `trail_stubborn(j)`) shipped in phase 2 — see §8.3. The generic
  `generic(lead_k, publish_n, trigger)` policy that would parametrize all
  three in one engine (spec §5) is still not implemented; each variant is
  its own branch in `SelfishStrategy.update`.
- **Colluding pool** (several miner daemons sharing one private tip) and
  **multiple independent attackers** (spec §10) — additive once needed,
  since the agent is already per-attacker.
- **Timestamp games** — needs a template-time offset, a daemon knob, out
  of scope here (spec §10).

See `docs/superpowers/specs/2026-09-12-selfish-mining-apparatus-design.md`
and `docs/superpowers/plans/2026-09-12-selfish-mining-apparatus.md` for the
phase-1 design and task history, and
`docs/superpowers/specs/2026-09-12-selfish-mining-phase2-design.md` /
`docs/superpowers/plans/2026-09-12-selfish-mining-phase2.md` for phase 2
(§8 below).

## 6. Validation gates

Design spec §9 defines four gates. Phase 1 shipped the plumbing and
tooling for all four, and Tasks 1-9's own unit/golden tests were run and
passed at commit time; gates a-c below additionally need an actual
simulation run, which is done by the user (§4), not as part of building
this.

**a. Neutral plumbing.** With `attributes.strategy: honest`, the
attacker's canonical-chain share should track its α and its orphan rate
should sit at the network baseline — proof the two-daemon apparatus adds
no advantage by itself. Run `selfish_micro.yaml` with `strategy: honest`
substituted, then
`venv/bin/python scripts/selfish_mining_analysis.py <run_dir>`.

**b. Determinism A/A.** Two same-seed runs of `selfish_micro.yaml` should
produce an identical block-hash sequence on the bridge's canonical chain.
As with native mining generally (`docs/NATIVE_MINING.md` §7, "A/A
determinism"), this requires `general.native_preemption: false` — the
shipped configs set `native_preemption: true` for wall-clock speed, so an
A/A comparison needs a config copy with it turned off.

**c. Eyal–Sirer micro.** At a known α (e.g. `selfish_micro.yaml`'s 0.4)
with the single bridge (γ≈0), the measured attacker share should exceed
the `strategy: honest` baseline from gate a at the same α, and land near
the γ=0 theory curve. `scripts/selfish_mining_analysis.py`'s two built-in
verdicts (§4) are the exact operationalisation of this gate.

**d. Existing suites still pass:**

```bash
venv/bin/python -m pytest agents/ scripts/test_selfish_configs.py scripts/test_selfish_mining_analysis.py -q
cargo test
```

plus the generation smoke of `test_configs/selfish_micro.yaml` and the
native-mining micro / 5-way split configs (`docs/NATIVE_MINING.md` §7) —
none of which this feature touches. Do not set
`MONEROSIM_SKIP_SIM_BINARY_CHECK=1` globally for `cargo test`: the golden
tests set it internally, and forcing it on breaks the sim-binary probe test.

## 7. Caveats for interpreting results

The phase-1 apparatus was reviewed; these residual limitations shape how you
read a run and are not bugs to fix before experimenting:

- **Attribution is ground truth, releases are fire-and-forget.** The agent
  submits releases and moves on without confirming delivery. This is safe
  because the attacker's share is measured from the bridge's recorded
  canonical chain (`canonical_chain.json`), not from what the agent believes
  it released. Under Shadow, RPC is deterministic and local, so a release
  either lands or is a γ=0 alternative (expected).
- **The offline attacker miner is still listed as a network seed.** Miners are
  auto-assigned as seed/priority nodes, and the attacker's miner is offline, so
  honest nodes log failed connection attempts to it. The shipped configs each
  have two online honest miners as seeds, so the honest network bootstraps and
  the bridge joins regardless. Excluding offline nodes from seed assignment is
  a phase-2 orchestrator improvement.
- **Statistical band.** A ~6 h micro run yields on the order of 180 canonical
  blocks, so the attacker-share estimate has roughly a 0.037 standard
  deviation; the analysis uses a ±0.10 verdict band. Treat a single micro run
  as directional and use the α-sweep (and longer runs) for quantitative claims.
- **Canonical snapshot timing.** The bridge records its chain at agent
  shutdown (about two minutes before `stop_time`), so the final block or two
  of a run may be outside `canonical_chain.json`. Negligible at experiment
  scale.
- **Startup edge.** With `attack_start_height: 0` the first withheld block is
  published immediately (a single lost withholding opportunity at genesis),
  negligible over a full run; set a small `attack_start_height` to warm up.

## 8. Phase 2: raising γ and stubborn-mining variants

**Status:** shipped (opt-in) 2026-09-12, on top of phase 1 above. Design:
`docs/superpowers/specs/2026-09-12-selfish-mining-phase2-design.md`; plan:
`docs/superpowers/plans/2026-09-12-selfish-mining-phase2.md`. As with phase
1, unit and config tests passed at commit time; the simulation gates in
§8.6 need an actual run, done by the operator, not part of building this.

### 8.1 Multi-bridge attacker: the `bridges` attribute

Phase 1's single bridge pins γ≈0 by construction (§1): a bridge only relays
a block once it enters its *main* chain, and an equal-height alt is never
relayed, so the attacker loses every tied race. Phase 2 lets the attacker
run several bridges and flood a release to all of them at once — this is
the entire γ-lifting mechanism.

`SelfishMinerAgent.__init__` reads a `bridges` attribute — a comma-separated
list of bridge agent ids — instead of a single `bridge_agent`:

```python
bridges_attr = self.attributes.get("bridges") or self.attributes.get("bridge_agent") or ""
self.bridge_agent_ids = [b.strip() for b in bridges_attr.split(",") if b.strip()]
```

`bridge_agent` still works, as a **one-element alias** — this is what keeps
phase-1 configs (`selfish_micro.yaml`, the α-sweep) running unchanged.
`_connect_bridges()` (renamed from `_connect_bridge`) looks up every id in
`agent_registry.json`, builds `self.bridge_rpcs: list[MoneroRPC]`, and keeps
`self.bridge_rpc = bridge_rpcs[0]` as the read source for the honest tip
height and for forwarding honest blocks (§2) — only *releases* go to every
bridge. `_release_up_to` submits each divergent private block to every RPC
in `bridge_rpcs`, each in its own try/except (a rejection on one bridge —
e.g. the γ=0-style equal-height alt — does not stop the others). A bridge
that has not yet received the honest block over P2P accepts the attacker's
block into its own main chain instead and relays it onward, so with more
publishers racing at submit time, a larger fraction of the honest network
ends up building on the attacker's block instead of the honest one. A
one-element `bridges` list is exactly the phase-1 code path (one connect,
one submit target), so the phase-1 micro result (attacker share 0.471 at
α=0.4, vs the γ=0 theory 0.484) is unchanged.

Each bridge is still the do-nothing `SelfishBridgeAgent` from phase 1 (§2);
phase-2 configs additionally pin its fan-out with
`daemon_options: {out-peers: 16}` on every bridge node.

### 8.2 `forward_to`: why stubborn strategies need it

`honest` and `eyal_sirer` let the offline miner follow the longest chain:
the agent forwards every honest block it sees, and the miner reorgs onto
honest whenever honest is longer. Stubborn strategies need the opposite —
they keep the miner mining a chain that is *not* the longest (trailing
behind, or holding a contested fork). Since monerod always follows the
longest chain it knows, the only way to keep it on a shorter private branch
is to not tell it about the honest lead.

So `SelfishStrategy.update()` returns one new field on `ReleaseDecision`,
`forward_to: Optional[int]`: the honest block height up to which the agent
may forward honest blocks into the offline miner this step. `honest` and
`eyal_sirer` always return `forward_to=None` in every branch (forward
everything up to the honest tip — unchanged from phase 1, required for
backward compatibility). A stubborn variant instead returns
`forward_to=old_fork` while holding, so the miner never sees the competing
honest branch and keeps extending its own.

The agent honors this in `_forward_public_blocks(pub_height, tip_hash,
forward_to)`: `effective_tip = pub_height if forward_to is None else
min(pub_height, forward_to)`, and every bound in the method (the forwarding
loop, the reorg-rescan window, `_forwarded_index`) uses `effective_tip`
instead of `pub_height`. `run_iteration` decides before forwarding
(`decision = self.strategy.update(pub_height, priv_height)` runs first,
then `_forward_public_blocks(..., decision.forward_to)`), since the cap has
to be known before the forward happens.

### 8.3 The three stubborn variants

Implemented in `agents/selfish_strategy.py`, selected by the `strategy`
attribute; a shared `_eyal_sirer_decision` helper backs each variant's
`a >= h` / fallthrough arm so eyal_sirer's own logic isn't duplicated three
times. State is the same as phase 1: `a = priv_height − fork` (attacker's
private lead), `h = pub_height − fork` (honest progress since the fork).
γ>0 (§8.1, §8.4) is what makes these strategies differ from plain selfish
mining at all — at γ≈0 holding a tied or trailing position never pays off
(a released tie never propagates), so all three collapse toward the honest
outcome.

- **`trail_stubborn` (`trail_depth` attribute, default 1).** Identical to
  `eyal_sirer` except it refuses to concede while behind by at most
  `trail_depth`: it holds (`forward_to=old_fork`, release nothing) while
  `0 < h − a <= trail_depth`, and concedes (adopt public, `forward_to=None`)
  once `h − a > trail_depth` (or the attacker has nothing to trail with:
  `a == 0` while `h > 0`). At `a >= h` it is exactly `eyal_sirer`. It bets
  that the honest lead is temporary and the private branch can catch back
  up within the tolerance; `trail_depth=0` reduces exactly to `eyal_sirer`.
- **`equal_fork_stubborn`.** Like `eyal_sirer`, but it never concedes
  *straight out of a tie*: once it has contested a tie (`a == h >= 1`, the
  `_was_tie` flag), if honest then breaks the tie by exactly one block, it
  holds one more round (`forward_to=old_fork`, release nothing) instead of
  adopting, betting it can re-level; falling two or more behind concedes as
  usual.
- **`lead_stubborn`.** Like `eyal_sirer`, but it holds its top block back at
  the overtake threshold. On the override step (`a − h == 1`, where eyal_sirer
  would reveal its whole lead to win outright) it reveals all but the top
  private block (`release_to = priv_height − 2`, equivalently `pub_height − 1`;
  `forward_to=None`, fork unchanged) — a tie that keeps the top hidden and bets
  that γ plus the hidden lead wins more, over time, than a guaranteed
  single-block override. It **cashes** the moment it is ≥2 ahead of an active
  honest chain (`h > 0`, `a − h ≥ 2`): it reveals the whole branch and commits
  the strictly-longer overtake (`fork = priv_height`), a real win. While honest
  has not moved (`h == 0`) it withholds its secret lead as usual, and it
  concedes if honest overtakes (`a < h`). The `a − h ≥ 2` cash is the *winning
  commit path* and is load-bearing: without it (the state before the 2026-09-13
  fix) lead_stubborn could only advance `fork` by conceding, so it never placed
  a block on the canonical chain — realized share 0.000, attacker orphan 1.000
  (see `docs/20260912_selfish_mining_results.md`). At γ≈0 the held tie never
  propagates, so lead_stubborn realizes at or below `eyal_sirer`; the hold only
  pays at γ>0.

Each variant is one bet that pays only with a network advantage — γ>0, or a
poorly-synchronized honest network. See
`docs/20260912_selfish_mining_results.md` for how each actually realized at
γ≈0: trail-stubborn gained (+0.113) via deep reorgs off a fragmented honest
network; equal-fork ≈ eyal_sirer; lead-stubborn needed the 2026-09-13
winning-commit-path fix before it could score at all.
`agents/test_selfish_strategy.py` asserts the full
`(release_to, forward_to, adopt_public)` triple for the distinctive
transition of each variant, so a reviewer can check the rules above
against the tests directly rather than re-deriving them.

### 8.4 γ vs fan-out and topology position

> **Heading corrected (2026-09-18).** This section was originally titled "γ is
> lifted by fan-out, not topology position". The phase-2 measurement did **not**
> find a fan-out lift, and phases 3 and 4 went on to refute position and relay as
> well. See §9 for where the γ question actually landed.

The original idea was to place a "detector" node near the honest miners and
publisher bridges far away in the topology, so a released tie reaches some
of the network before the honest block does. monerosim doesn't support
that: node placement on the GML graph is assigned globally by the
distribution strategy (`src/topology/distribution.rs`), deterministically
and identically for every agent — there is no per-agent position knob.

What *is* per-agent controllable is connectivity: a bridge's outbound
fan-out (`daemon_options: {out-peers: N}`). So phase 2 reframes the γ
experiment as **γ vs. fan-out/connectivity** rather than γ vs. position:
more publisher bridges, each racing to relay the attacker's block the
moment it's released (§8.1), means a larger fraction of the honest network
is already holding the attacker's block at the moment the honest block
arrives over P2P — this is still γ as a *measured* network outcome, just
produced by a different knob. γ is small on a small, low-latency network
(the margins are sub-millisecond), which is why the phase-2 configs (§8.5)
use a larger honest network — 3 miners + 12 relays spread across the GML
topology — so inter-node latencies have enough spread for γ to be
measurable at all.

**Update (2026-09-13): a per-agent position knob now exists.** The
`topology_node: <gml node id>` agent attribute pins an agent to a specific GML
node, overriding the index-based distribution (`apply_topology_pins`,
`src/topology/placement.rs`; validated against the GML node ids). This retracts
the "no per-agent position knob" statement above: γ is now *addressable by
position* — an experiment can place the attacker's detector and publisher
bridges near a chosen honest subset while the honest finder is far. Lifting γ
this way is still empirical (the attacker is reactive, so its block starts the
propagation race late), but the placement lever the text above said was missing
is now available. Design:
`docs/superpowers/specs/2026-09-13-per-agent-topology-placement-design.md`;
phase-3 results land in `docs/20260912_selfish_mining_results.md`.

### 8.5 Configs, running the experiments, and reading the output

`test_configs/selfish_phase2/` (all α=0.4, `simulation_seed: 12345`,
`reaction_delay_ms: "50"`, the 3-miner/12-relay honest network of §8.4):

| Config | Bridges | Strategy |
|---|---|---|
| `fanout_1.yaml` | 1 | `eyal_sirer` |
| `fanout_3.yaml` | 3 | `eyal_sirer` |
| `fanout_6.yaml` | 6 | `eyal_sirer` |
| `stub_trail.yaml` | 6 (= `fanout_6` topology) | `trail_stubborn`, `trail_depth: "2"` |
| `stub_equalfork.yaml` | 6 (= `fanout_6` topology) | `equal_fork_stubborn` |
| `stub_lead.yaml` | 6 (= `fanout_6` topology) | `lead_stubborn` |

`fanout_1/3/6.yaml` are the γ-vs-fan-out sweep at fixed α; the attacker's
`bridges` attribute lists exactly its bridge agent ids (e.g.
`"bridge-1,bridge-2,bridge-3"` for `fanout_3.yaml`). The three `stub_*.yaml`
configs are copies of `fanout_6.yaml`'s topology with only `strategy` (and,
for trail, `trail_depth`) changed, so each stubborn variant is compared
against `eyal_sirer` at identical fan-out. `scripts/test_selfish_phase2_configs.py`
asserts the bridge count, the `bridges` attribute, `--offline`, native
mining mode, α≈0.4, and the strategy name for all six configs.

To run one (shared box — `nice` it, as with any long simulation):

```bash
nice -n10 ./run_sim.sh --config test_configs/selfish_phase2/fanout_3.yaml --name fanout_3 --no-monitor
```

Then analyse it exactly as in §4:

```bash
venv/bin/python scripts/selfish_mining_analysis.py archived_runs/<run_id>
```

The analysis (§4) is unchanged in shape but now also reports, in
`report.md` and on stdout:

- **realized gamma** — `realized_gamma(found, chain, attacker_ids)`: over
  every *tie* height (a height where both an attacker- and an honest-miner
  found a block), the fraction the attacker's block won on the bridge's
  recorded canonical chain. This is the γ the attacker actually achieved on
  the network, not an assumption.
- **num ties** — how many tie heights that estimate is based on; read it
  alongside the number itself (a handful of ties makes the γ estimate
  noisy).
- **theory at measured gamma** — `es_revenue_share(alpha, gamma)` evaluated
  at the *realized* γ above, rather than at γ=0; a third verdict checks the
  measured share against this curve (±0.10, the same band as the γ=0
  verdict).

Reading a run: compare `realized gamma` across `fanout_1/3/6` (expect it to
rise with bridge count — gate a below), and compare each `stub_*` run's
measured share and verdicts against the `fanout_6.yaml` (`eyal_sirer`) run
at the same γ regime.

### 8.6 Validation gates

Phase-2 design spec §8 defines four gates, alongside phase 1's own four
(§6):

- **a. γ lifts.** Realized γ at multi-bridge configs is measurably above
  the single-bridge γ (≈0) at the same α, rising with bridge count across
  `fanout_1` → `fanout_3` → `fanout_6`.
- **b. Determinism A/A.** Same seed → identical honest chain (as §6.b).
- **c. Stubborn sanity.** Each stubborn variant runs without wedging, and
  its attacker share matches its theoretical curve at the measured γ
  within the ±0.10 band; at γ≈0 none of them should beat honest.
- **d. Existing suites still pass**, including the phase-1 micro
  (unaffected by the multi-bridge/`forward_to` changes):

```bash
venv/bin/python -m pytest agents/ scripts/test_selfish_mining_analysis.py scripts/test_selfish_configs.py scripts/test_selfish_phase2_configs.py -q
cargo test
```

### 8.7 What phase 2 still does not do

Deferred to increment 3 (design spec §10):

- **Colluding pool** (several miner daemons sharing one private tip) and
  **multiple independent attackers**.
- **Timestamp games** — needs a template-time offset, a daemon knob.
- ~~**Precise topology-position control**~~ — shipped as `topology_node`
  (§9.1); phase 3 measured it and it does not lift γ.
- The generic `generic(lead_k, publish_n, trigger)` policy that would
  parametrize `trail_stubborn`/`equal_fork_stubborn`/`lead_stubborn` in one
  engine (phase-1 design spec §5) is also not implemented; each variant is
  its own branch.

## 9. Phases 3–4: the γ levers, and why γ is structurally 0

Phase 2 (§8) measured γ against bridge fan-out. Phases 3 and 4 built and measured
the two levers that remained. **Both were built, both were measured, and neither
lifts γ.** Numbers, tie tables and log forensics:
`docs/20260912_selfish_mining_results.md`.

### 9.1 Position — `topology_node` (phase 3)

`topology_node: <gml node id>` pins an agent to a specific GML vertex, overriding
index-based distribution (`src/topology/placement.rs`). Phase 3 gave γ its best
shot with it: honest miners pinned far apart, the attacker's detector central,
publisher bridges spread near each honest region, reaction dropped to 10 ms.
Realized γ: **0.000 over 12 ties**. Position changes latencies, not arrival
*order* — the reactive attacker's block is still second everywhere it lands.

### 9.2 Relay — `--sim-relay-alt-blocks` (phase 4)

Phase 3 hypothesised that a daemon-level relay change might be the missing piece,
so `patches/monero-sim-selfish-relay.patch` provides one. Stock monerod relays a
block it accepted onto the main chain; a locally-submitted block that lands as an
equal-height *alternative* is accepted but never announced, so a withheld
tie-block dies at the bridge that published it. The flag widens that relay
condition.

Properties, by design:

- **Sim-only and default-off.** Absent the flag the daemon is byte-for-byte
  stock in behaviour; the banner `*** SIMULATION: --sim-relay-alt-blocks is ON`
  is logged at startup when it is set, so a run's logs always say which daemons
  had it.
- **Local-submission only.** It widens the relay condition solely for blocks the
  daemon accepted from its own `submit_block` RPC or miner. A block received over
  P2P is never re-relayed through this path, so a patched daemon cannot amplify
  another node's alt-blocks and the change cannot cascade across the network.
- **Orphans excluded.** The gate requires `!m_verifivation_failed &&
  !m_already_exists && !m_marked_as_orphaned`, so a block whose parent is unknown
  is not announced.
- **Config-only wiring.** Set `daemon_options: {sim-relay-alt-blocks: true}` on
  the agents that should publish; no code change per experiment.
- **Requires `monerod-sim`.** Build with `./setup.sh --sim-binary`. `run_sim.sh`
  preflight **fails the run** if a config sets the flag but the binary lacks the
  patch — without that gate the tie-block would silently not relay and the run
  would report γ ≈ 0, which is indistinguishable from the genuine result below.

**Result: γ = 0.000 over 10 ties** — no movement at all versus phase 3. Verified
in the logs rather than assumed: for 10/10 ties, all 3/3 honest nodes received
the attacker's block (`Received NOTIFY_NEW_FLUFFY_BLOCK`) and accepted it
(`BLOCK ADDED AS ALTERNATIVE`), then extended their own block anyway.

**Why: relay is not adoption.** The patch changes what the *sender* announces.
The tie-break lives in the *receiver*, which keeps whichever block it saw first
at that height. Delivering the attacker's block faster or wider does not change
the mind of a node that has already chosen.

### 9.3 Running phase 4

```bash
./setup.sh --sim-binary                      # builds monerod-sim with all patches
./run_sim.sh --config test_configs/selfish_phase4/gamma_relay.yaml --name p4_gamma_relay
python3 scripts/selfish_mining_analysis.py archived_runs/<run_id>
```

The config is `selfish_phase3/gamma_lift.yaml` plus the flag on all five bridges,
so relay is the only variable between the two runs.

### 9.4 What would actually lift γ

Only arrival order. The attacker's block must reach some honest miners *first*,
which needs one-hop peer dominance over a chosen honest subset combined with
near-zero reaction — i.e. a **peer-pinning** knob (`topology_node` sets position,
not the peer graph, which `peer_mode: Dynamic` discovers). That knob does not
exist yet and is the only remaining lever worth building for this question.

The alternative — patching the *receiver* to prefer a later-arriving equal-height
block — would lift γ by construction, but it changes consensus behaviour rather
than relay plumbing, and a network running it would no longer be modelling
Monero. It is deliberately not built.

## 10. Experiment series (feat/selfish-mining-experiments)

Branch for the post-phase-4 experiment programme. Literature context:
`docs/20260920_selfish_mining_literature.md` (moneroresearch.info harvest —
the Qubic campaign study independently measured γ ≈ 0.01–0.06 on real Monero,
validating the structural finding above).

1. **`release_lead` (shipped 2026-09-21).** eyal_sirer's reveal arm is
   parametrized: cash out the private branch once honest closes to within
   `release_lead` blocks (default 1 = textbook; 2 = Qubic's observed
   conservative policy, Lee & Kim 2025). `scripts/selfish_mining_analysis.py`
   adds `mod_revenue_share` (their Eq. 2) and a between-models band verdict
   for release_lead ≥ 2 runs. Results: α=0.4 A/B 0.463 → 0.309 (profit →
   loss) with network damage shrinking too (orphan rate 0.274 → 0.214, reorg
   depths collapse to length-1, MSB detectability drops +6.94 → +3.98); the
   α-sweep (0.30/0.40/0.45, `test_configs/selfish_sweep_release2/`) puts the
   conservative policy's profitability crossover in (0.40, 0.45) and found
   MSB over-flagging HONEST miners under heavy attack (their iid null needs
   attack calibration). Numbers and interpretation:
   `docs/20260921_selfish_release2_results.md`.
2. **Externality/detection metrics (shipped 2026-09-21).**
   `scripts/selfish_externality.py`, rendered as the analysis report's
   "Externality & detection" section: Lee & Kim's per-hour orphan series +
   Alg. 1 attack-period detection + reorg-depth histogram + attacker
   run-length/release-signature scatter; Li et al. 2020 MSB consecutive-wins
   z-scores; Kawaguchi & Noda SpEC; Gervais stale-rate series. The bridge's
   canonical chain dump now records block timestamps (join-free bucketing).
3. **Eclipse×selfish composition (experiment 3, v1 run 2026-09-21).** Two
   orchestrator knobs — `peers:` (agent-id-resolved exclusive/priority peer
   pins + in/out caps) and `attributes.eclipsed` (excluded from the miner
   ring and all seed lists) — plus `islands` attacker attribute: isolated
   island bridges that the agent mirrors its private chain onto (eclipsed
   victims unknowingly extend it) and pulls blocks back from (victim blocks
   join the private branch; the release path cashes the combined chain
   unchanged). Analysis reports CONTROLLED share (attacker + victims) vs
   Eyal–Sirer at α_eff, and never uses island chains as the canonical
   observer. Config: `test_configs/selfish_eclipse/gamma_eclipse.yaml`
   (α=4/15≈0.27 naive, α_eff=7/15≈0.47). **v1 result: hypothesis rejected —
   0.161 controlled vs 0.733 predicted.** The composition has an
   island-resync pathology: once the island branch outruns honest and honest
   then overtakes, the island cannot be resynced (its main chain is longer),
   victims mine a permanently dead branch, and 65% of attacker finds die
   with them — while the network still eats a 0.43 orphan rate. Negative
   result with mechanism and the v2 lifecycle designs (recruitment cap /
   epochs / cash-on-lead):
   `docs/20260921_selfish_eclipse_results.md`.
