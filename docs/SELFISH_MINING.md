# Selfish Mining (Phase 1)

**Status:** phase 1 shipped (opt-in) 2026-09-12: the single-bridge, γ≈0
withholding apparatus, the Eyal–Sirer strategy, and the revenue-share
analysis. Every task's unit and golden tests passed at commit time; the
simulation-based validation gates (§6, a-c) require an actual run and are
executed by the user, not as part of building this. Builds on native
mining (`docs/NATIVE_MINING.md`); phase 2 (γ-lifting, stubborn variants,
colluding pool) is not built — see §5.

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
more bridges positioned in the topology; that is phase 2 (§5).

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
  honest nodes *before* the honest block does — a fast detector node plus
  publisher bridges placed away from it. That is a multi-bridge apparatus
  (the `bridges` knob, spec §5) and the γ-vs-position experiment (spec §8,
  experiment 2); phase 1 ships exactly one bridge.
- **Stubborn-mining variants** (`lead_stubborn`, `equal_fork_stubborn`,
  `trail_stubborn(j)`) and the generic
  `generic(lead_k, publish_n, trigger)` policy (spec §5) — the same
  strategy-engine shape, just not implemented as named strategies yet.
- **Colluding pool** (several miner daemons sharing one private tip) and
  **multiple independent attackers** (spec §10) — additive once needed,
  since the agent is already per-attacker.
- **Timestamp games** — needs a template-time offset, a daemon knob, out
  of scope here (spec §10).

See `docs/superpowers/specs/2026-09-12-selfish-mining-apparatus-design.md`
and `docs/superpowers/plans/2026-09-12-selfish-mining-apparatus.md` for the
full design and task history.

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
MONEROSIM_SKIP_SIM_BINARY_CHECK=1 cargo test
```

plus the generation smoke of `test_configs/selfish_micro.yaml` and the
native-mining micro / 5-way split configs (`docs/NATIVE_MINING.md` §7) —
none of which this feature touches.
