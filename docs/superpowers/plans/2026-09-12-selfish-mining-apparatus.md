# Selfish-Mining Apparatus — Implementation Plan (Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a block-withholding attacker (single-bridge, γ ≈ 0 regime) that runs Eyal–Sirer selfish mining on the native-mining simulation, plus the analysis to measure attacker revenue share vs hashrate against the γ = 0 theory curve.

**Architecture:** The attacker is two stock daemons plus one Python agent, no monerod patch. An `--offline` miner daemon (native throttled RandomX) withholds blocks by construction because it has no P2P. A normally-connected bridge daemon is the attacker's read/write path to the honest network. A `SelfishMinerAgent` runs the strategy state machine and moves blocks between the two daemons with `get_block` and `submit_block`. It finds its bridge through the existing `agent_registry.json`.

**Tech Stack:** Rust orchestrator (config → Shadow YAML), Python 3 agents (`agents/*.py`, stdlib + `requests`), pytest, `cargo test` with golden-file snapshots, YAML configs, Shadow discrete-event simulator, monerod/monerod-sim (`--regtest --keep-fakechain`).

**Spec:** `docs/superpowers/specs/2026-09-12-selfish-mining-apparatus-design.md` (read it alongside this plan).

## Global Constraints

- **No monerod source patch.** The attacker uses only stock RPCs (`get_block`, `submit_block`, `get_info`) and the stock `--offline` flag. Do not add a daemon flag or patch the relay path.
- **Base branch is `feat/native-mining`.** Work happens on `feat/selfish-mining` (already branched off it). Do not merge or push either branch; do not touch `main`.
- **Shared box, scope process ops to `lever65`.** Any `pgrep`/`pkill` must use `-u lever65`. Never run unscoped kills. This plan runs no long simulations; it only runs unit tests and generation.
- **No blocking `flock` in agents.** Use `agents/file_locking.py` (`acquire_flock` is non-blocking with a sleep loop). Do not call `fcntl.flock(` directly. The bridge/miner agents here do not add new shared-file writers beyond the existing registry.
- **Native mining semantics.** `hashrate` is literal hashes/second in `1..=1000`. `start_mining` is the native-mode call (throttled by `--sim-hash-interval-ms`); `ensure_mining`/`generateblocks` are the legacy mode and must not be used by the attacker.
- **γ ≈ 0 is expected in phase 1.** A single bridge cannot propagate an equal-height tie block (stock `handle_block_found` relays only main-chain additions), so the attacker loses every tie by construction. This is the Eyal–Sirer γ = 0 baseline, not a bug.
- **TDD, frequent commits.** Every task: failing test → run it fail → minimal implementation → run it pass → commit. Commit messages end with the two attribution trailers used on this branch (see any recent commit).

---

## File Structure

- `agents/monero_rpc.py` — **modify**: add `submit_block(block_blob)` to `MoneroRPC`.
- `agents/selfish_strategy.py` — **create**: pure Eyal–Sirer state machine (no RPC, no I/O). One responsibility: given the two chain heights, decide what to release.
- `agents/selfish_bridge.py` — **create** (Task 3) then **extend** (Task 8): a `BaseAgent` subclass that registers itself and idles so the bridge daemon is discoverable, and at cleanup records its main chain (height→hash) to `canonical_chain.json` as the analysis's ground truth.
- `agents/selfish_miner.py` — **create**: `SelfishMinerAgent(AutonomousMinerAgent)` wiring the strategy to RPC (bridge discovery, honest-block forwarder, release executor).
- `src/agent/user_agents.rs` — **modify**: teach the miner wallet-hybrid path that `agents.selfish_miner` is a native-mining agent script.
- `src/utils/mining.rs` — **modify**: add the `is_native_miner_script` helper + unit test.
- `test_configs/selfish_micro.yaml` — **create**: the micro attacker topology (honest miners, relays, offline attacker miner, bridge).
- `test_configs/selfish_sweep/alpha_*.yaml` — **create**: the α-sweep set.
- `tests/fixtures/selfish.yaml`, `tests/golden/selfish.yaml`, `tests/orchestrator_selfish.rs` — **create**: orchestrator golden test for the attacker wiring.
- `agents/test_selfish_strategy.py`, `agents/test_selfish_miner.py` — **create**: Python unit tests.
- `scripts/selfish_mining_analysis.py`, `scripts/test_selfish_mining_analysis.py` — **create** (Task 9): attribution from the ground-truth `canonical_chain.json` joined with miners' found-block hashes; revenue share vs the γ=0 curve + tests.
- `docs/SELFISH_MINING.md` — **create**; `CHANGELOG.md` — **modify**; `docs/NATIVE_MINING.md` — **modify** (pointer).

---

## Task 1: `submit_block` RPC wrapper

**Files:**
- Modify: `agents/monero_rpc.py` (add a method to `class MoneroRPC`, after `get_block_header_by_height`, ~line 300)
- Test: `agents/test_monero_rpc_submit.py`

**Interfaces:**
- Consumes: `MoneroRPC._make_request(self, method, params)` (agents/monero_rpc.py:57) — sends a json_rpc POST; when `params` is truthy it sets `payload["params"] = params`. A Python `list` is accepted verbatim, which is what `submit_block` needs (its params is a positional array of block blobs).
- Produces: `MoneroRPC.submit_block(self, block_blob: str) -> Dict[str, Any]` — submits one hex block blob; returns the daemon's result dict (contains `status`). Raises `RPCError` on an RPC-level error (e.g. block rejected).

- [ ] **Step 1: Write the failing test**

```python
# agents/test_monero_rpc_submit.py
from unittest.mock import MagicMock, patch
import pytest
from agents.monero_rpc import MoneroRPC, RPCError


def _mock_response(json_body, status_code=200):
    resp = MagicMock()
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    resp.status_code = status_code
    return resp


def test_submit_block_sends_positional_list_param():
    rpc = MoneroRPC("10.0.0.5", 28081)
    with patch.object(rpc.session, "post") as post:
        post.return_value = _mock_response({"result": {"status": "OK"}})
        out = rpc.submit_block("deadbeef")
        assert out == {"status": "OK"}
        # The one call's JSON payload must carry params as a LIST [blob].
        _, kwargs = post.call_args
        payload = kwargs["json"]
        assert payload["method"] == "submit_block"
        assert payload["params"] == ["deadbeef"]


def test_submit_block_raises_on_rpc_error():
    rpc = MoneroRPC("10.0.0.5", 28081)
    with patch.object(rpc.session, "post") as post:
        post.return_value = _mock_response({"error": {"code": -7, "message": "Block not accepted"}})
        with pytest.raises(RPCError):
            rpc.submit_block("00")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest agents/test_monero_rpc_submit.py -v`
Expected: FAIL with `AttributeError: 'MoneroRPC' object has no attribute 'submit_block'`.

- [ ] **Step 3: Add the method**

```python
# agents/monero_rpc.py — inside class MoneroRPC, after get_block_header_by_height
    def submit_block(self, block_blob: str) -> Dict[str, Any]:
        """Submit a single mined block (hex blob) to the daemon.

        submit_block's params is a POSITIONAL array of block blobs, unlike the
        object-params of other json_rpc methods; _make_request forwards a list
        verbatim. On success the daemon adds the block and (if it enters the
        main chain) relays it to peers exactly as a P2P block. Raises RPCError
        if the block is rejected.
        """
        return self._make_request("submit_block", [block_blob])
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest agents/test_monero_rpc_submit.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agents/monero_rpc.py agents/test_monero_rpc_submit.py
git commit -m "feat(rpc): add submit_block wrapper to MoneroRPC"
```

---

## Task 2: Pure Eyal–Sirer strategy state machine

**Files:**
- Create: `agents/selfish_strategy.py`
- Test: `agents/test_selfish_strategy.py`

**Interfaces:**
- Consumes: nothing (pure module, stdlib only).
- Produces:
  - `class ReleaseDecision` with fields `release_to: Optional[int]` (release private blocks up to and including this block index, or `None` to release nothing) and `adopt_public: bool` (the attacker abandoned its private branch this step).
  - `class SelfishStrategy`:
    - `__init__(self, name: str, start_height: int)` — `name` is `"honest"` or `"eyal_sirer"`; `start_height` is the block **count** (height) at which withholding begins and is used as the initial fork.
    - `fork` (int attribute) — the block **count** of the last block common to both chains (i.e. the index of the first divergent block).
    - `update(self, pub_height: int, priv_height: int) -> ReleaseDecision` — call each tick with the honest chain height (block count from the bridge) and the private chain height (block count from the offline miner). Returns the release decision and mutates internal state.

**Height convention:** `pub_height`/`priv_height` are block **counts** (monerod `get_info` `height`, i.e. top index + 1). `fork` is also a count: shared block indexes are `0..fork-1`, the attacker's divergent block indexes are `fork..priv_height-1`. `release_to` is a block **index** (the highest divergent index to submit).

**Strategy semantics (γ = 0 regime, outcome-equivalent to textbook Eyal–Sirer at γ = 0):**
Let `a = priv_height - fork` (private branch length) and `h = pub_height - fork` (honest branch length since fork).
- `honest`: always `release_to = priv_height - 1` (publish everything immediately; the apparatus behaves as a normal miner). Never adopts.
- `eyal_sirer`:
  - Before `start_height` (i.e. `pub_height < start_height`): behave as `honest` (warm-up, no withholding).
  - `h == 0`: withhold (`release_to = None`).
  - `a < h`, or (`h > 0` and `a == 0`): the honest chain has overtaken; adopt public — set `fork = pub_height`, return `adopt_public = True`, `release_to = None`.
  - `a == h` (`>= 1`): tie/race — `release_to = priv_height - 1` (submit the whole private branch; at γ = 0 an equal-height block does not propagate, so the attacker only wins if it later extends). Do **not** move `fork`.
  - `a - h == 1`: honest has caught to within one — reveal-and-win: `release_to = priv_height - 1`, then set `fork = priv_height` (the attacker chain becomes public).
  - `a - h >= 2`: withhold (`release_to = None`). (The lead-preserving partial reveal of textbook ES is inert at γ = 0 and is deferred to phase 2.)

- [ ] **Step 1: Write the failing tests**

```python
# agents/test_selfish_strategy.py
from agents.selfish_strategy import SelfishStrategy, ReleaseDecision


def test_honest_always_releases_everything():
    s = SelfishStrategy("honest", start_height=0)
    d = s.update(pub_height=5, priv_height=5)
    assert d.release_to == 4 and d.adopt_public is False
    d = s.update(pub_height=5, priv_height=7)
    assert d.release_to == 6


def test_withholds_while_strictly_ahead():
    s = SelfishStrategy("eyal_sirer", start_height=0)
    # fork starts at 0; honest hasn't moved (h==0), attacker mined 2 -> withhold
    d = s.update(pub_height=0, priv_height=2)
    assert d.release_to is None and d.adopt_public is False
    assert s.fork == 0


def test_lead_two_then_honest_catches_one_reveals_and_wins():
    s = SelfishStrategy("eyal_sirer", start_height=0)
    s.update(pub_height=0, priv_height=2)          # lead 2, withhold
    d = s.update(pub_height=1, priv_height=2)        # a=2,h=1 -> a-h==1 -> reveal all
    assert d.release_to == 1                          # release indexes 0..1
    assert s.fork == 2                                # attacker chain is now public
    assert d.adopt_public is False


def test_tie_then_attacker_extends_wins():
    s = SelfishStrategy("eyal_sirer", start_height=0)
    s.update(pub_height=0, priv_height=1)            # lead 1, withhold (h==0)
    d = s.update(pub_height=1, priv_height=1)         # a==h==1 -> tie, release match
    assert d.release_to == 0
    assert s.fork == 0                                # fork not moved on a tie
    d = s.update(pub_height=1, priv_height=2)         # a=2,h=1 -> reveal-and-win
    assert d.release_to == 1 and s.fork == 2


def test_tie_then_honest_extends_adopts():
    s = SelfishStrategy("eyal_sirer", start_height=0)
    s.update(pub_height=0, priv_height=1)
    s.update(pub_height=1, priv_height=1)            # tie
    d = s.update(pub_height=2, priv_height=1)         # a=1,h=2 -> a<h -> adopt
    assert d.adopt_public is True and d.release_to is None
    assert s.fork == 2


def test_honest_overtakes_from_lead_adopts():
    s = SelfishStrategy("eyal_sirer", start_height=0)
    s.update(pub_height=0, priv_height=1)            # lead 1, withhold
    d = s.update(pub_height=2, priv_height=1)         # honest jumped 2 -> a<h -> adopt
    assert d.adopt_public is True and s.fork == 2


def test_warmup_before_start_height_behaves_honestly():
    s = SelfishStrategy("eyal_sirer", start_height=10)
    d = s.update(pub_height=4, priv_height=6)         # below start_height -> honest
    assert d.release_to == 5 and d.adopt_public is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest agents/test_selfish_strategy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.selfish_strategy'`.

- [ ] **Step 3: Implement the module**

```python
# agents/selfish_strategy.py
"""Pure Eyal-Sirer selfish-mining state machine (no RPC, no I/O).

Heights are block COUNTS (monerod get_info 'height' = top index + 1). `fork`
is the count of blocks common to both chains; the attacker's divergent block
indexes are fork..priv_height-1. `release_to` in the returned decision is a
block INDEX (the highest divergent index to submit to the bridge), or None.

This is the gamma=0 regime: a single bridge cannot propagate an equal-height
tie block, so the attacker loses every tie unless it extends its own branch.
That is outcome-equivalent to textbook Eyal-Sirer at gamma=0; the
lead-preserving partial reveal (which only matters at gamma>0) is deferred to
phase 2. See docs/superpowers/specs/2026-09-12-selfish-mining-apparatus-design.md.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ReleaseDecision:
    release_to: Optional[int] = None   # highest divergent block INDEX to release, or None
    adopt_public: bool = False         # attacker abandoned its private branch this step


class SelfishStrategy:
    def __init__(self, name: str, start_height: int):
        if name not in ("honest", "eyal_sirer"):
            raise ValueError(f"unknown strategy: {name}")
        self.name = name
        self.start_height = int(start_height)
        self.fork = int(start_height)

    def update(self, pub_height: int, priv_height: int) -> ReleaseDecision:
        # Honest, or eyal_sirer during warm-up: publish everything immediately.
        if self.name == "honest" or pub_height < self.start_height:
            self.fork = pub_height
            return ReleaseDecision(
                release_to=(priv_height - 1) if priv_height > 0 else None,
                adopt_public=False,
            )

        a = priv_height - self.fork   # private branch length
        h = pub_height - self.fork    # honest branch length since fork

        # Honest overtook (or attacker has nothing on the branch): adopt public.
        if a < h or (h > 0 and a == 0):
            self.fork = pub_height
            return ReleaseDecision(release_to=None, adopt_public=True)

        # Honest has not moved since the fork: keep withholding.
        if h == 0:
            return ReleaseDecision(release_to=None, adopt_public=False)

        # a >= h >= 1 from here.
        if a == h:
            # Tie/race: submit the whole private branch. At gamma=0 the
            # equal-height tip does not propagate; the attacker only wins if it
            # later extends (handled next tick as a-h==1). Fork is NOT moved.
            return ReleaseDecision(release_to=priv_height - 1, adopt_public=False)

        if a - h == 1:
            # Honest caught to within one: reveal all -> strictly longer -> win.
            self.fork = priv_height
            return ReleaseDecision(release_to=priv_height - 1, adopt_public=False)

        # a - h >= 2: still comfortably ahead; withhold.
        return ReleaseDecision(release_to=None, adopt_public=False)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest agents/test_selfish_strategy.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add agents/selfish_strategy.py agents/test_selfish_strategy.py
git commit -m "feat(selfish): pure Eyal-Sirer strategy state machine (gamma=0 regime)"
```

---

## Task 3: Trivial bridge agent

**Files:**
- Create: `agents/selfish_bridge.py`
- Test: `agents/test_selfish_bridge.py`

**Interfaces:**
- Consumes: `BaseAgent.__init__(...)` (agents/base_agent.py:70); `BaseAgent.setup()` (agents/base_agent.py:196) which calls `_register_self()` at line 241, writing this agent's `ip_addr`, `daemon_rpc_port`, `p2p_port`, `wallet_rpc_port` into `agent_registry.json`; `BaseAgent.create_argument_parser(description)` (agents/base_agent.py:780); `BaseAgent.run_iteration` is abstract and must be implemented.
- Produces: `class SelfishBridgeAgent(BaseAgent)` with `run_iteration(self) -> float` returning a long idle interval; a `main()` entry point mirroring `agents/autonomous_miner.py:817-847`.

**Why this exists:** the attacker's bridge is a normal relay daemon. A relay with no script never starts a Python process and so never registers its RPC endpoint. This ~30-line agent starts on the bridge host purely so `_register_self()` publishes the bridge's `ip_addr` + `daemon_rpc_port`, which the `SelfishMinerAgent` looks up. It performs no blockchain actions.

- [ ] **Step 1: Write the failing test**

```python
# agents/test_selfish_bridge.py
from agents.selfish_bridge import SelfishBridgeAgent


def test_run_iteration_returns_long_idle_and_does_no_rpc():
    agent = SelfishBridgeAgent(agent_id="attacker-bridge")
    # A bare instance must not touch RPC in run_iteration.
    interval = agent.run_iteration()
    assert isinstance(interval, float)
    assert interval >= 30.0


def test_is_base_agent_subclass_so_it_registers():
    from agents.base_agent import BaseAgent
    assert issubclass(SelfishBridgeAgent, BaseAgent)
    # setup() -> _register_self is inherited, not overridden away.
    assert SelfishBridgeAgent.setup is BaseAgent.setup
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest agents/test_selfish_bridge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.selfish_bridge'`.

- [ ] **Step 3: Implement the agent**

```python
# agents/selfish_bridge.py
"""Bridge node for the selfish-mining apparatus.

A do-nothing agent whose only job is to run on the attacker's bridge daemon
host so BaseAgent.setup() registers the bridge's RPC endpoint (ip_addr,
daemon_rpc_port) in agent_registry.json. The SelfishMinerAgent looks the
bridge up there. The bridge daemon itself is a stock, fully-connected relay;
this agent issues no blockchain RPCs.
"""
import logging

from agents.base_agent import BaseAgent

BRIDGE_IDLE_INTERVAL_S = 60.0


class SelfishBridgeAgent(BaseAgent):
    def __init__(self, agent_id: str, **kwargs):
        super().__init__(agent_id=agent_id, **kwargs)

    def run_iteration(self) -> float:
        # Registered in setup(); nothing to do but stay alive.
        return BRIDGE_IDLE_INTERVAL_S


def main():
    parser = SelfishBridgeAgent.create_argument_parser("Selfish-mining bridge node")
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    agent = SelfishBridgeAgent(
        agent_id=args.id,
        shared_dir=args.shared_dir,
        daemon_rpc_port=args.daemon_rpc_port,
        wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port,
        rpc_host=args.rpc_host,
        log_level=args.log_level,
        attributes=args.attributes,
    )
    agent.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest agents/test_selfish_bridge.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agents/selfish_bridge.py agents/test_selfish_bridge.py
git commit -m "feat(selfish): bridge agent that registers its RPC endpoint and idles"
```

---

## Task 4: `SelfishMinerAgent`

**Files:**
- Create: `agents/selfish_miner.py`
- Test: `agents/test_selfish_miner.py`

**Interfaces:**
- Consumes:
  - `AutonomousMinerAgent(BaseAgent)` (agents/autonomous_miner.py:27) — subclass it; it already reads `mining_mode`/`hash_interval_ms` (lines 80-85) and provides `_native_run_iteration()` (lines 650-668) which starts native mining on the agent's own daemon and scans found blocks.
  - `self.attributes` dict (agents/base_agent.py:105).
  - `self.daemon_rpc: MoneroRPC` (agents/base_agent.py:204) — the agent's OWN daemon = the offline miner.
  - `self.read_shared_state(filename, use_lock=False)` (agents/base_agent.py:601) → the parsed `agent_registry.json` dict, whose `agents` list carries `{id, ip_addr, daemon_rpc_port, ...}` (written by `_register_self`, agents/base_agent.py:712-723).
  - `MoneroRPC(host, port)` (agents/monero_rpc.py:156), `MoneroRPC.get_info()` (returns dict with `height`), `MoneroRPC.get_block(height=...)` (returns dict with `blob`), `MoneroRPC.submit_block(blob)` (Task 1), `RPCError` (agents/monero_rpc.py).
  - `SelfishStrategy`, `ReleaseDecision` (Task 2).
- Produces: `class SelfishMinerAgent(AutonomousMinerAgent)` and a `main()` entry point (config script name `agents.selfish_miner`).

**Behaviour of `run_iteration`:**
1. Drive the base native-mining lifecycle so the offline miner mines (`self._native_run_iteration()`; ignore its returned interval).
2. If the bridge RPC is not yet connected, try to connect from the registry; if not found, return `1.0` to retry.
3. Lazily create the `SelfishStrategy` once connected.
4. Read `pub_height` (bridge `get_info().height`) and `priv_height` (own `get_info().height`).
5. Forward any new honest blocks (indexes `_forwarded_index+1 .. pub_height-1`) from the bridge into the offline miner via `submit_block` (tolerating "already have"/rejection errors).
6. `decision = strategy.update(pub_height, priv_height)`; if `decision.release_to is not None`, release the attacker's divergent blocks `strategy.fork .. decision.release_to` from the offline miner to the bridge via `submit_block` (skip indexes already released; tolerate errors).
7. Return `self.reaction_delay_ms / 1000.0`.

Blocks whose `submit_block` fails (already present, or an equal-height alt the bridge rejects) are logged at debug and skipped — this is expected and is how γ = 0 manifests.

- [ ] **Step 1: Write the failing tests**

```python
# agents/test_selfish_miner.py
from unittest.mock import MagicMock
import pytest
from agents.selfish_miner import SelfishMinerAgent
from agents.monero_rpc import RPCError


def _make_agent(strategy="eyal_sirer", start_height=0, reaction_ms=200):
    a = SelfishMinerAgent(
        agent_id="attacker-miner",
        attributes=[["strategy", strategy],
                    ["bridge_agent", "attacker-bridge"],
                    ["attack_start_height", str(start_height)],
                    ["reaction_delay_ms", str(reaction_ms)]],
    )
    a.logger = MagicMock()
    # Own daemon (offline miner) and bridge daemon are mocked.
    a.daemon_rpc = MagicMock()
    a.bridge_rpc = MagicMock()
    a.native_started = True            # skip real start_mining
    a._native_run_iteration = MagicMock(return_value=1.0)
    a._ensure_strategy(0)
    return a


def test_reads_attributes():
    a = _make_agent(strategy="eyal_sirer", start_height=5, reaction_ms=150)
    assert a.strategy_name == "eyal_sirer"
    assert a.bridge_agent_id == "attacker-bridge"
    assert a.attack_start_height == 5
    assert abs(a._reaction_interval_s() - 0.15) < 1e-9


def test_connect_bridge_reads_registry(monkeypatch):
    a = SelfishMinerAgent(
        agent_id="attacker-miner",
        attributes=[["strategy", "honest"], ["bridge_agent", "attacker-bridge"]],
    )
    a.logger = MagicMock()
    a.read_shared_state = MagicMock(return_value={
        "agents": [
            {"id": "attacker-miner", "ip_addr": "11.0.0.1", "daemon_rpc_port": 28081},
            {"id": "attacker-bridge", "ip_addr": "11.0.0.2", "daemon_rpc_port": 28082},
        ]
    })
    assert a._connect_bridge() is True
    assert a.bridge_rpc.host == "11.0.0.2"
    assert a.bridge_rpc.port == 28082


def test_connect_bridge_missing_returns_false():
    a = SelfishMinerAgent(agent_id="attacker-miner",
                          attributes=[["bridge_agent", "nope"]])
    a.logger = MagicMock()
    a.read_shared_state = MagicMock(return_value={"agents": []})
    assert a._connect_bridge() is False
    assert a.bridge_rpc is None


def test_forward_public_blocks_submits_new_honest_blocks():
    a = _make_agent()
    a.bridge_rpc.get_block.side_effect = lambda height: {"blob": f"pub{height}"}
    a._forward_public_blocks(pub_height=3)   # indexes 0,1,2
    submitted = [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list]
    assert submitted == ["pub0", "pub1", "pub2"]
    assert a._forwarded_index == 2
    # Idempotent: a second call with no new blocks submits nothing more.
    a.daemon_rpc.submit_block.reset_mock()
    a._forward_public_blocks(pub_height=3)
    a.daemon_rpc.submit_block.assert_not_called()


def test_release_up_to_submits_private_blocks_to_bridge():
    a = _make_agent()
    a.strategy.fork = 1
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"priv{height}"}
    a._release_up_to(3)   # indexes 1,2,3
    submitted = [c.args[0] for c in a.bridge_rpc.submit_block.call_args_list]
    assert submitted == ["priv1", "priv2", "priv3"]
    assert a._released_index == 3


def test_release_tolerates_rejected_alt():
    a = _make_agent()
    a.strategy.fork = 0
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"p{height}"}
    a.bridge_rpc.submit_block.side_effect = [RPCError("Block not accepted"), {"status": "OK"}]
    a._release_up_to(1)   # index 0 rejected (alt), index 1 accepted -> no raise
    assert a._released_index == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest agents/test_selfish_miner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.selfish_miner'`.

- [ ] **Step 3: Implement the agent**

```python
# agents/selfish_miner.py
"""Selfish-mining attacker agent.

Runs on the attacker's OFFLINE miner daemon (native throttled RandomX). Its
own daemon (self.daemon_rpc) withholds by construction because it has no P2P.
A separate, normally-connected bridge daemon (discovered from
agent_registry.json by the `bridge_agent` attribute) is the read/write path to
the honest network. Each tick this agent forwards new honest blocks into the
offline miner and releases private blocks to the bridge per the SelfishStrategy
decision. See docs/SELFISH_MINING.md.

Attributes (via --attributes KEY VALUE):
    strategy            "honest" | "eyal_sirer"  (default "honest")
    bridge_agent        agent id of the bridge node (required)
    attack_start_height block count at which withholding begins (default 0)
    reaction_delay_ms   poll/reaction interval in ms (default 200)
"""
import logging

from agents.autonomous_miner import AutonomousMinerAgent
from agents.monero_rpc import MoneroRPC, RPCError
from agents.selfish_strategy import SelfishStrategy


class SelfishMinerAgent(AutonomousMinerAgent):
    def __init__(self, agent_id: str, **kwargs):
        super().__init__(agent_id=agent_id, **kwargs)
        self.strategy_name = self.attributes.get("strategy", "honest")
        self.bridge_agent_id = self.attributes.get("bridge_agent")
        self.attack_start_height = int(self.attributes.get("attack_start_height", "0") or 0)
        self.reaction_delay_ms = int(self.attributes.get("reaction_delay_ms", "200") or 200)
        self.bridge_rpc = None
        self.strategy = None
        self._forwarded_index = -1     # highest honest block index forwarded to the miner
        self._released_index = -1      # highest private block index released to the bridge

    def _reaction_interval_s(self) -> float:
        return max(self.reaction_delay_ms, 1) / 1000.0

    def _ensure_strategy(self, start_height: int) -> None:
        if self.strategy is None:
            self.strategy = SelfishStrategy(self.strategy_name, start_height)

    def _connect_bridge(self) -> bool:
        registry = self.read_shared_state("agent_registry.json") or {}
        for agent in registry.get("agents", []):
            if agent.get("id") == self.bridge_agent_id:
                host = agent.get("ip_addr")
                port = agent.get("daemon_rpc_port")
                if host and port:
                    self.bridge_rpc = MoneroRPC(host, int(port))
                    self.logger.info(f"Bridge connected: {self.bridge_agent_id} at {host}:{port}")
                    return True
        self.logger.debug(f"Bridge {self.bridge_agent_id} not yet in registry")
        return False

    def _forward_public_blocks(self, pub_height: int) -> None:
        """Submit honest blocks the offline miner has not seen yet."""
        for idx in range(self._forwarded_index + 1, pub_height):
            try:
                blob = self.bridge_rpc.get_block(height=idx).get("blob")
                if blob:
                    self.daemon_rpc.submit_block(blob)
            except RPCError as e:
                self.logger.debug(f"forward honest block {idx}: {e}")
            self._forwarded_index = idx

    def _release_up_to(self, release_index: int) -> None:
        """Submit the attacker's divergent private blocks to the bridge in order."""
        start = max(self.strategy.fork, self._released_index + 1)
        for idx in range(start, release_index + 1):
            try:
                blob = self.daemon_rpc.get_block(height=idx).get("blob")
                if blob:
                    self.bridge_rpc.submit_block(blob)
            except RPCError as e:
                # Expected for equal-height alts (gamma=0) and already-present blocks.
                self.logger.debug(f"release private block {idx}: {e}")
            self._released_index = max(self._released_index, idx)

    def run_iteration(self) -> float:
        # 1. Keep the offline miner mining.
        try:
            self._native_run_iteration()
        except RPCError as e:
            self.logger.warning(f"native mining iteration: {e}")

        # 2. Ensure the bridge is connected.
        if self.bridge_rpc is None and not self._connect_bridge():
            return 1.0

        # 3/4. Read both chain heights.
        try:
            pub_height = int(self.bridge_rpc.get_info().get("height", 0))
            priv_height = int(self.daemon_rpc.get_info().get("height", 0))
        except RPCError as e:
            self.logger.warning(f"height read failed: {e}")
            return self._reaction_interval_s()

        self._ensure_strategy(self.attack_start_height)

        # 5. Forward new honest blocks into the offline miner.
        self._forward_public_blocks(pub_height)

        # 6. Strategy decision -> release.
        decision = self.strategy.update(pub_height, priv_height)
        if decision.release_to is not None:
            self._release_up_to(decision.release_to)

        return self._reaction_interval_s()


def main():
    parser = SelfishMinerAgent.create_argument_parser("Selfish-mining attacker agent")
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    agent = SelfishMinerAgent(
        agent_id=args.id,
        shared_dir=args.shared_dir,
        daemon_rpc_port=args.daemon_rpc_port,
        wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port,
        rpc_host=args.rpc_host,
        log_level=args.log_level,
        attributes=args.attributes,
    )
    agent.run()


if __name__ == "__main__":
    main()
```

Note: `MoneroRPC` stores `self.host`/`self.port` (BaseRPC.__init__, agents/monero_rpc.py:32-ish). The test asserts `bridge_rpc.host`/`.port`; if the attribute names differ, adjust the assertions to the real names (verify by reading `BaseRPC.__init__`). Do not change `BaseRPC`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest agents/test_selfish_miner.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Run the full agent test suite to check for regressions**

Run: `python3 -m pytest agents/ -q`
Expected: all pass (no import breakage in `agents/`).

- [ ] **Step 6: Commit**

```bash
git add agents/selfish_miner.py agents/test_selfish_miner.py
git commit -m "feat(selfish): SelfishMinerAgent (bridge discovery, forwarder, release executor)"
```

---

## Task 5: Orchestrator recognises `selfish_miner` as a native-mining agent

**Files:**
- Modify: `src/utils/mining.rs` (add helper + unit test)
- Modify: `src/agent/user_agents.rs:1422` (use the helper)

**Interfaces:**
- Consumes: `user_agents.rs` local `script: String` (line 1402) and `is_miner: bool`.
- Produces: `pub fn is_native_miner_script(script: &str) -> bool` in `src/utils/mining.rs`.

**Why:** the miner wallet-hybrid path (`user_agents.rs:1422`) fires only when `script.contains("autonomous_miner")`. The attacker miner uses `script: agents.selfish_miner` and still needs the hybrid (wallet creation + address registration) and its `mining_script` step to launch `selfish_miner.py`. Generalising this one predicate is the only Rust change the apparatus needs; the offline flag is pure YAML (`daemon_options: {offline: true}` → `--offline`, verified in `src/utils/options.rs:73`) and bridge discovery is pure Python.

- [ ] **Step 1: Write the failing unit test**

```rust
// src/utils/mining.rs — append to the existing #[cfg(test)] mod tests (or add one)
    #[test]
    fn native_miner_scripts_recognised() {
        assert!(is_native_miner_script("agents.autonomous_miner"));
        assert!(is_native_miner_script("agents.selfish_miner"));
        assert!(!is_native_miner_script("agents.regular_user"));
        assert!(!is_native_miner_script("agents.selfish_bridge"));
    }
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cargo test --lib is_native_miner_script`
Expected: FAIL to compile — `cannot find function is_native_miner_script`.

- [ ] **Step 3: Add the helper**

```rust
// src/utils/mining.rs — add near hash_interval_ms
/// True if `script` is one of the native-mining agent scripts that need the
/// miner wallet-hybrid path in user_agents.rs (autonomous or selfish miner).
/// selfish_bridge is intentionally excluded — it is a relay, not a miner.
pub fn is_native_miner_script(script: &str) -> bool {
    script.contains("autonomous_miner") || script.contains("selfish_miner")
}
```

- [ ] **Step 4: Run the unit test to verify it passes**

Run: `cargo test --lib is_native_miner_script`
Expected: PASS.

- [ ] **Step 5: Use the helper at the hybrid gate**

In `src/agent/user_agents.rs`, ensure the module import is present (add `use crate::utils::mining::is_native_miner_script;` next to the existing `hash_interval_ms` import), then change line 1422 from:

```rust
            if is_miner && script.contains("autonomous_miner") {
```

to:

```rust
            if is_miner && is_native_miner_script(&script) {
```

- [ ] **Step 6: Build and run the existing orchestrator tests to confirm no regression**

Run: `cargo build && MONEROSIM_SKIP_SIM_BINARY_CHECK=1 cargo test --test orchestrator_native`
Expected: PASS (native golden unchanged — that fixture uses `autonomous_miner`, still matched).

- [ ] **Step 7: Commit**

```bash
git add src/utils/mining.rs src/agent/user_agents.rs
git commit -m "feat(selfish): treat agents.selfish_miner as a native-mining agent for the wallet-hybrid"
```

---

## Task 6: Orchestrator golden test for the attacker wiring

**Files:**
- Create: `tests/fixtures/selfish.yaml`
- Create: `tests/orchestrator_selfish.rs`
- Create (generated): `tests/golden/selfish.yaml`

**Interfaces:**
- Consumes: `config_loader::load_config`, `orchestrator::generate_agent_shadow_config` (same as `tests/orchestrator_native.rs:1-98`).
- Produces: a golden proving the attacker miner is substituted to `monerod-sim`, gets `--sim-hash-interval-ms` and `--offline`, its wrapper scripts carry `mining_mode` + `strategy` + `bridge_agent`, and the bridge is a plain relay.

- [ ] **Step 1: Write the fixture**

```yaml
# tests/fixtures/selfish.yaml
general:
  stop_time: 30m
  simulation_seed: 12345
  enable_dns_server: true
  process_threads: 2
  mining:
    mode: native
  daemon_defaults:
    log-level: monitor
    no-zmq: true
    non-interactive: true
network:
  path: gml_processing/1200_nodes_caida_with_loops.gml
  peer_mode: Dynamic
agents:
  honest-001:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    hashrate: 6
    start_time: 0s
  attacker-miner:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.selfish_miner
    hashrate: 4
    start_time: 0s
    daemon_options:
      offline: true
    attributes:
      strategy: eyal_sirer
      bridge_agent: attacker-bridge
      attack_start_height: "0"
      reaction_delay_ms: "200"
  attacker-bridge:
    daemon: monerod
    script: agents.selfish_bridge
    start_time: 0s
  relay-001:
    daemon: monerod
    start_time: 30s
```

- [ ] **Step 2: Write the test (modeled on `tests/orchestrator_native.rs`)**

```rust
// tests/orchestrator_selfish.rs
use monerosim::{config_loader, orchestrator};
use std::path::Path;
use tempfile::TempDir;

// Reuse the same normalize() approach as orchestrator_native.rs. If that helper
// is not shared, copy its body here verbatim.
fn normalize(yaml: &str) -> String { yaml.to_string() }

#[test]
fn selfish_fixture_yaml_matches_golden() {
    std::env::set_var("MONEROSIM_SKIP_SIM_BINARY_CHECK", "1");
    let tmp = TempDir::new().unwrap();
    let output_yaml = tmp.path().join("shadow_agents.yaml");
    let shared_dir = tmp.path().join("shared");
    std::fs::create_dir_all(&shared_dir).unwrap();
    std::fs::create_dir_all(tmp.path().join("scripts")).unwrap();

    let mut config = config_loader::load_config(Path::new("tests/fixtures/selfish.yaml"))
        .expect("selfish fixture loads");
    config.general.shared_dir = shared_dir.to_string_lossy().to_string();

    orchestrator::generate_agent_shadow_config(&config, &output_yaml)
        .expect("orchestrator generates");

    let actual = normalize(&std::fs::read_to_string(&output_yaml).unwrap());

    // Structural assertions independent of the golden.
    assert!(actual.contains("--offline"), "attacker miner daemon gets --offline");
    assert!(actual.contains("--sim-hash-interval-ms=250"), "attacker (4 h/s) interval");
    assert!(actual.contains("--sim-hash-interval-ms=167"), "honest (6 h/s) interval");
    assert_eq!(actual.matches("--sim-hash-interval-ms=").count(), 2,
               "only the two miners (honest + attacker) get the knob");
    assert!(actual.contains("HOME/.monerosim/bin/monerod-sim"),
            "native miners substituted to monerod-sim");

    // Attacker wrapper scripts carry the strategy attributes.
    let scripts_dir = tmp.path().join("scripts");
    let mut wrappers = String::new();
    for entry in std::fs::read_dir(&scripts_dir).unwrap() {
        wrappers.push_str(&std::fs::read_to_string(entry.unwrap().path()).unwrap());
    }
    assert!(wrappers.contains("selfish_miner"), "attacker runs the selfish_miner script");
    assert!(wrappers.contains("selfish_bridge"), "bridge runs the selfish_bridge script");
    assert!(wrappers.contains("eyal_sirer"), "strategy attribute passed to the attacker");
    assert!(wrappers.contains("bridge_agent"), "bridge_agent attribute passed to the attacker");

    let golden_path = Path::new("tests/golden/selfish.yaml");
    if std::env::var("UPDATE_GOLDEN").is_ok() {
        std::fs::write(golden_path, &actual).unwrap();
        return;
    }
    let expected = std::fs::read_to_string(golden_path)
        .expect("tests/golden/selfish.yaml exists; run with UPDATE_GOLDEN=1 to create it");
    assert_eq!(actual, expected,
               "regenerate with UPDATE_GOLDEN=1 cargo test --test orchestrator_selfish");
}
```

If `normalize` in `orchestrator_native.rs` is a private module function, copy its exact body into this file's `normalize` (the golden must be host-portable). Confirm the exact hash-interval values (`250` for 4 h/s, `167` for 6 h/s) by reading `hash_interval_ms`: `round(1000/4)=250`, `round(1000/6)=167`.

- [ ] **Step 3: Run to verify it fails**

Run: `MONEROSIM_SKIP_SIM_BINARY_CHECK=1 cargo test --test orchestrator_selfish`
Expected: FAIL — structural assertions may pass but the golden file does not exist yet (panics on read), or `--offline`/attributes assertions fail if wiring is wrong.

- [ ] **Step 4: Inspect, then generate the golden**

First run with generation and read the output to confirm it is sane (attacker has `--offline` + `monerod-sim` + interval 250; bridge is plain `monerod` with no interval; wrappers contain `eyal_sirer`):

Run: `UPDATE_GOLDEN=1 MONEROSIM_SKIP_SIM_BINARY_CHECK=1 cargo test --test orchestrator_selfish`
Then: `git diff --stat` and open `tests/golden/selfish.yaml` to eyeball the attacker + bridge stanzas.

- [ ] **Step 5: Run to verify it passes against the golden**

Run: `MONEROSIM_SKIP_SIM_BINARY_CHECK=1 cargo test --test orchestrator_selfish`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/selfish.yaml tests/orchestrator_selfish.rs tests/golden/selfish.yaml
git commit -m "test(selfish): orchestrator golden for offline attacker + bridge wiring"
```

---

## Task 7: `selfish_micro.yaml` and the α-sweep configs

**Files:**
- Create: `test_configs/selfish_micro.yaml`
- Create: `test_configs/selfish_sweep/alpha_0300.yaml`, `alpha_0400.yaml`, `alpha_0450.yaml`
- Test: extend `tests/orchestrator_selfish.rs` is not needed; instead add a Python generation smoke assertion file `scripts/test_selfish_configs.py` that loads each YAML and checks the attacker/bridge invariants.

**Interfaces:**
- Consumes: `yaml` (PyYAML), the config schema (agents with `daemon`, `wallet`, `script`, `hashrate`, `daemon_options`, `attributes`).
- Produces: runnable configs. `selfish_micro.yaml` mirrors `test_configs/native_micro.yaml` structure with: several honest native miners, two relays, one offline attacker miner (`script: agents.selfish_miner`, `daemon_options: {offline: true}`), and one bridge (`script: agents.selfish_bridge`). α (attacker fraction) is set by the hashrate split.

**α math:** attacker fraction α = attacker_hashrate / (attacker_hashrate + honest_hashrate_total). For α = 0.4 use attacker 4, honest total 6. Keep total ≤ ~10 h/s so the micro run mines at a workable cadence.

- [ ] **Step 1: Write the failing config-invariant test**

```python
# scripts/test_selfish_configs.py
from pathlib import Path
import yaml
import pytest

CONFIGS = [
    Path("test_configs/selfish_micro.yaml"),
    Path("test_configs/selfish_sweep/alpha_0300.yaml"),
    Path("test_configs/selfish_sweep/alpha_0400.yaml"),
    Path("test_configs/selfish_sweep/alpha_0450.yaml"),
]


def _load(p):
    with open(p) as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.name)
def test_config_has_offline_attacker_and_bridge(path):
    cfg = _load(path)
    agents = cfg["agents"]
    attackers = {k: v for k, v in agents.items()
                 if v.get("script") == "agents.selfish_miner"}
    bridges = {k: v for k, v in agents.items()
               if v.get("script") == "agents.selfish_bridge"}
    assert len(attackers) == 1, f"{path}: exactly one attacker miner"
    assert len(bridges) == 1, f"{path}: exactly one bridge"

    (att_name, att), = attackers.items()
    (bridge_name, _), = bridges.items()
    assert att.get("daemon_options", {}).get("offline") is True, "attacker miner is --offline"
    assert att.get("hashrate", 0) >= 1, "attacker has a native hashrate"
    assert att["attributes"]["bridge_agent"] == bridge_name, "attacker points at the bridge"
    assert att["attributes"]["strategy"] in ("honest", "eyal_sirer")
    assert cfg["general"]["mining"]["mode"] == "native", "native mining mode"


@pytest.mark.parametrize("path,expected_alpha", [
    (Path("test_configs/selfish_sweep/alpha_0300.yaml"), 0.30),
    (Path("test_configs/selfish_sweep/alpha_0400.yaml"), 0.40),
    (Path("test_configs/selfish_sweep/alpha_0450.yaml"), 0.45),
], ids=["a030", "a040", "a045"])
def test_sweep_alpha_matches_hashrate_split(path, expected_alpha):
    cfg = _load(path)
    agents = cfg["agents"]
    att = next(v["hashrate"] for v in agents.values()
               if v.get("script") == "agents.selfish_miner")
    honest = sum(v["hashrate"] for v in agents.values()
                 if v.get("script") == "agents.autonomous_miner")
    alpha = att / (att + honest)
    assert abs(alpha - expected_alpha) < 0.01, f"{path}: alpha {alpha:.3f} != {expected_alpha}"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest scripts/test_selfish_configs.py -v`
Expected: FAIL — config files do not exist (`FileNotFoundError`).

- [ ] **Step 3: Write `test_configs/selfish_micro.yaml`**

```yaml
# Selfish-mining micro gate (docs/SELFISH_MINING.md).
# Honest miners total 6 h/s; the attacker mines 4 h/s (alpha = 0.4) on an
# OFFLINE monerod-sim (withholds by construction). The bridge is a normal
# relay + a registration-only agent; the attacker finds it via the registry.
# Single bridge => gamma ~= 0 (ties never propagate) => the Eyal-Sirer gamma=0
# baseline. Compare against the honest-strategy run at the same alpha.
general:
  stop_time: 6h
  simulation_seed: 12345
  bootstrap_end_time: 10m
  enable_dns_server: true
  shadow_log_level: warning
  progress: true
  process_threads: 2
  native_preemption: true
  mining:
    mode: native
  daemon_defaults:
    log-level: monitor
    max-log-file-size: 0
    db-sync-mode: fastest
    no-zmq: true
    non-interactive: true
  wallet_defaults:
    log-level: 1
network:
  path: gml_processing/1200_nodes_caida_with_loops.gml
  peer_mode: Dynamic
agents:
  honest-001:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    hashrate: 3
    start_time: 0s
  honest-002:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    hashrate: 3
    start_time: 0s
  attacker-miner:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.selfish_miner
    hashrate: 4
    start_time: 0s
    daemon_options:
      offline: true
    attributes:
      strategy: eyal_sirer
      bridge_agent: attacker-bridge
      attack_start_height: "0"
      reaction_delay_ms: "200"
  attacker-bridge:
    daemon: monerod
    script: agents.selfish_bridge
    start_time: 0s
  relay-001:
    daemon: monerod
    start_time: 30s
  relay-002:
    daemon: monerod
    start_time: 60s
  simulation-monitor:
    script: agents.simulation_monitor
    poll_interval: 300
```

- [ ] **Step 4: Write the three sweep configs**

Create `test_configs/selfish_sweep/alpha_0400.yaml` as a copy of `selfish_micro.yaml` (same honest 3+3=6, attacker 4). Then `alpha_0300.yaml` (honest 3+3+3=9 via a third honest miner `honest-003: hashrate 3`… actually to hit 0.30 use honest total 7 and attacker 3: set honest-001=4, honest-002=3, attacker=3 → 3/10 = 0.30) and `alpha_0450.yaml` (honest 3+3=6 wait that's 0.4; for 0.45 use honest 3+3+? ). Use these exact splits so the α test passes:
  - `alpha_0300.yaml`: honest-001 `hashrate: 4`, honest-002 `hashrate: 3`, attacker `hashrate: 3` → 3/10 = 0.30.
  - `alpha_0400.yaml`: honest-001 `3`, honest-002 `3`, attacker `4` → 4/10 = 0.40.
  - `alpha_0450.yaml`: honest-001 `6`, honest-002 `5`, attacker `9` → 9/20 = 0.45.

Each file is otherwise identical to `selfish_micro.yaml` (attacker `script: agents.selfish_miner`, `daemon_options: {offline: true}`, `attributes.bridge_agent: attacker-bridge`, `attributes.strategy: eyal_sirer`, and one `attacker-bridge` with `script: agents.selfish_bridge`). Set `simulation_seed` the same across the sweep so runs are comparable.

- [ ] **Step 5: Run the config-invariant test to verify it passes**

Run: `python3 -m pytest scripts/test_selfish_configs.py -v`
Expected: PASS (7 passed: 4 invariant + 3 α).

- [ ] **Step 6: Confirm the micro config generates (real orchestrator, no run)**

Run: `MONEROSIM_SKIP_SIM_BINARY_CHECK=1 cargo run --quiet -- --config test_configs/selfish_micro.yaml --output /tmp/claude-1006/selfish_gen_check 2>&1 | tail -20` (adjust the CLI flags to match this repo's generation entrypoint — check `run_sim.sh` for the exact invocation; the point is generation must succeed without launching Shadow).
Expected: generation completes, exit 0, no error about `selfish_miner`/`--offline`.

- [ ] **Step 7: Commit**

```bash
git add test_configs/selfish_micro.yaml test_configs/selfish_sweep/ scripts/test_selfish_configs.py
git commit -m "feat(selfish): micro + alpha-sweep configs with offline attacker and bridge"
```

---

## Task 8: Bridge records the canonical chain at cleanup

**Files:**
- Modify: `agents/selfish_bridge.py` (add a `_cleanup_agent` override)
- Modify: `agents/test_selfish_bridge.py` (add one test)

**Why (supersedes the original build_accepted approach):** attribution cannot reuse `scripts/native_daa_analysis.build_accepted`, which dedupes same-height races by **earliest timestamp**. A selfish attacker finds its blocks early and withholds them, so at γ≈0 a tie the attacker *lost* still has the earlier timestamp and would be wrongly credited to the attacker, inflating its measured share. The ground truth is an honest node's actual main chain. The bridge is a fully-connected honest node whose main chain, at γ≈0, equals the honest canonical chain (injected tie blocks stay alternatives and never enter its main chain; attacker reorg-wins enter it exactly as they enter every honest node). So the bridge records its own main chain (height→hash) at cleanup; the analysis (Task 9) joins those hashes with the miners' found-block hashes to attribute each canonical block to its finder.

**Interfaces:**
- Consumes: `BaseAgent.cleanup()` calls `self._cleanup_agent()` (agents/base_agent.py:322); `self.daemon_rpc.get_info()` → dict with `height`; `self.daemon_rpc.get_block_header_by_height(h)` (agents/monero_rpc.py:287) → dict with `hash`; `BaseAgent.write_shared_state(filename, data)` (verify its exact name/signature in base_agent.py — it is the writer paired with `read_shared_state`; if the signature differs, adapt the call, do not change base_agent.py); `RPCError` (agents/monero_rpc.py).
- Produces: a shared file `canonical_chain.json` of the form `{"observer": "<agent_id>", "chain": [{"height": h, "hash": "<hex>"}, ...]}` covering heights `1..top` (genesis at height 0 skipped).

- [ ] **Step 1: Add the failing test to `agents/test_selfish_bridge.py`**

```python
from unittest.mock import MagicMock

def test_cleanup_agent_dumps_canonical_chain():
    agent = SelfishBridgeAgent(agent_id="attacker-bridge")
    agent.logger = MagicMock()
    agent.daemon_rpc = MagicMock()
    agent.daemon_rpc.get_info.return_value = {"height": 3}   # top index 2 -> heights 1,2
    agent.daemon_rpc.get_block_header_by_height.side_effect = lambda h: {"hash": f"h{h}"}
    written = {}
    agent.write_shared_state = lambda name, data: written.__setitem__(name, data)
    agent._cleanup_agent()
    assert written["canonical_chain.json"]["chain"] == [
        {"height": 1, "hash": "h1"},
        {"height": 2, "hash": "h2"},
    ]
    assert written["canonical_chain.json"]["observer"] == "attacker-bridge"
```
(keep the existing two tests and the `from agents.selfish_bridge import SelfishBridgeAgent` import.)

- [ ] **Step 2: Run it to verify it fails**

Run: `venv/bin/python -m pytest agents/test_selfish_bridge.py -v`
Expected: the new test FAILs (`_cleanup_agent` is the inherited no-op, writes nothing).

- [ ] **Step 3: Implement the recorder in `agents/selfish_bridge.py`**

Add the import at the top: `from agents.monero_rpc import RPCError`. Replace the existing no-op `_cleanup_agent` (if the bridge currently has none, add it; keep the `_setup_agent` no-op as is):

```python
    def _cleanup_agent(self):
        """Record this honest node's final main chain (height -> hash) so the
        selfish-mining analysis can attribute each canonical block to its
        finder. At gamma=0 the bridge's main chain IS the honest canonical
        chain. Best-effort: a failure here must not break shutdown."""
        try:
            height = int(self.daemon_rpc.get_info().get("height", 0))
            chain = []
            for h in range(1, height):   # skip genesis (height 0)
                try:
                    header = self.daemon_rpc.get_block_header_by_height(h)
                except RPCError as e:
                    self.logger.warning(f"canonical chain dump stopped at height {h}: {e}")
                    break
                block_hash = header.get("hash")
                if block_hash:
                    chain.append({"height": h, "hash": block_hash})
            self.write_shared_state("canonical_chain.json",
                                    {"observer": self.agent_id, "chain": chain})
            self.logger.info(f"Canonical chain recorded: {len(chain)} blocks")
        except RPCError as e:
            self.logger.warning(f"canonical chain dump failed: {e}")
```

First confirm `write_shared_state` exists with signature `(self, filename, data)` by reading `agents/base_agent.py` (it is paired with `read_shared_state`); if the real name/signature differs, call the real one. Do not modify base_agent.py.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/bin/python -m pytest agents/test_selfish_bridge.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add agents/selfish_bridge.py agents/test_selfish_bridge.py
git commit -m "feat(selfish): bridge records canonical chain (height->hash) at cleanup"
```

---

## Task 9: Analysis — attacker revenue share vs α

**Files:**
- Create: `scripts/selfish_mining_analysis.py`
- Test: `scripts/test_selfish_mining_analysis.py`

**Interfaces:**
- Consumes:
  - `scripts.native_mining_check.FOUND` (a compiled regex; capture group 2 = block hash, group 3 = height) to parse each miner's daemon log for found blocks. Do not modify that module.
  - `scripts.native_daa_analysis.load_config(cfg_path) -> dict` (reuse for `input_config.yaml`). Do not modify that module.
  - `canonical_chain.json` written by the bridge (Task 8): `{"observer": ..., "chain": [{"height", "hash"}, ...]}`.
  - The run archive: each miner's log at `<run_dir>/shadow.data/hosts/<miner>/monerod*.stdout`; the shared file at `<run_dir>/.../shared/canonical_chain.json` (searched for, or passed with `--chain`).
- Produces:
  - `es_revenue_share(alpha: float, gamma: float) -> float` — Eyal–Sirer relative revenue.
  - `parse_found_blocks(run_dir, miner_ids) -> list` of `{"hash", "height", "miner"}` (one per FOUND line).
  - `found_by_hash(found: list) -> dict` mapping block hash → finder miner id.
  - `attacker_share_from_chain(chain: list, hash_to_miner: dict, attacker_ids: set) -> float` — fraction of canonical blocks whose finder is an attacker.
  - `orphan_stats(found: list, canonical_hashes: set, attacker_ids: set) -> dict` — found vs canonical counts and orphan rates (attacker + network).
  - `make_verdicts(alpha, measured_share, stats) -> list`.
  - a `main()` CLI: `python3 scripts/selfish_mining_analysis.py <run_dir> [--chain <path>] [--out <dir>]`, exit 0/1/2 (mirror `native_daa_analysis.main`).

**Eyal–Sirer relative revenue:** `R(α,γ) = [ α(1-α)^2 (4α + γ(1-2α)) - α^3 ] / [ 1 - α(1 + (2-α)α) ]`.

**Attribution:** the canonical chain's block hashes come from `canonical_chain.json` (honest ground truth). Each hash is looked up in the hash→miner map built from all miners' FOUND logs (the attacker's offline-mined winning blocks carry the same hash on the bridge after the reorg, so they match). Attacker share = canonical blocks whose finder is an attacker / total canonical blocks. Orphans = found blocks whose hash is not in the canonical set.

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_selfish_mining_analysis.py
import pytest
from scripts.selfish_mining_analysis import (
    es_revenue_share,
    found_by_hash,
    attacker_share_from_chain,
    orphan_stats,
    parse_found_blocks,
)


def test_es_revenue_share_small_alpha_near_zero():
    assert abs(es_revenue_share(1e-6, 0.0)) < 1e-4


def test_es_revenue_share_crosses_alpha_near_one_third_at_gamma_zero():
    assert es_revenue_share(0.30, 0.0) < 0.30
    assert es_revenue_share(0.40, 0.0) > 0.40


def test_es_revenue_share_monotonic_in_gamma():
    assert es_revenue_share(0.35, 1.0) > es_revenue_share(0.35, 0.0)


def test_found_by_hash_maps_hash_to_finder():
    found = [
        {"hash": "a1", "height": 1, "miner": "attacker-miner"},
        {"hash": "h2", "height": 2, "miner": "honest-001"},
    ]
    assert found_by_hash(found) == {"a1": "attacker-miner", "h2": "honest-001"}


def test_attacker_share_from_canonical_chain():
    chain = [
        {"height": 1, "hash": "h1"},
        {"height": 2, "hash": "a2"},
        {"height": 3, "hash": "a3"},
        {"height": 4, "hash": "h4"},
    ]
    h2m = {"h1": "honest-001", "a2": "attacker-miner", "a3": "attacker-miner", "h4": "honest-002"}
    assert attacker_share_from_chain(chain, h2m, {"attacker-miner"}) == 0.5


def test_orphan_stats_counts_lost_ties_as_orphans():
    # attacker found a1 (canonical) and a2x (orphaned tie loss); honest h2 canonical
    found = [
        {"hash": "a1", "height": 1, "miner": "attacker-miner"},
        {"hash": "a2x", "height": 2, "miner": "attacker-miner"},
        {"hash": "h2", "height": 2, "miner": "honest-001"},
    ]
    canonical_hashes = {"a1", "h2"}
    stats = orphan_stats(found, canonical_hashes, {"attacker-miner"})
    assert stats["attacker_found"] == 2
    assert stats["attacker_canonical"] == 1
    assert abs(stats["attacker_orphan_rate"] - 0.5) < 1e-9


def test_parse_found_blocks_reads_a_log(tmp_path):
    host = tmp_path / "shadow.data" / "hosts" / "attacker-miner"
    host.mkdir(parents=True)
    (host / "monerod.stdout").write_text(
        "2000-01-01 00:00:15.0\tI Found block <deadbeef> at height 1 for difficulty: 2\n"
    )
    found = parse_found_blocks(tmp_path, ["attacker-miner"])
    assert found == [{"hash": "deadbeef", "height": 1, "miner": "attacker-miner"}]
```

- [ ] **Step 2: Run to verify they fail**

Run: `venv/bin/python -m pytest scripts/test_selfish_mining_analysis.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.selfish_mining_analysis'`.

- [ ] **Step 3: Implement the analysis**

```python
# scripts/selfish_mining_analysis.py
#!/usr/bin/env python3
"""Selfish-mining analysis for a finished native-mining run.

Attribution uses an honest node's GROUND-TRUTH canonical chain recorded by the
bridge (canonical_chain.json, Task 8) joined with the block hashes each miner
logged finding. It deliberately does NOT reuse build_accepted, whose
earliest-timestamp dedupe misattributes a selfish attacker's withheld, early-
found, later-lost tie blocks. Computes attacker revenue share vs the
Eyal-Sirer gamma=0 curve, plus orphan rates. See docs/SELFISH_MINING.md.

Usage: python3 scripts/selfish_mining_analysis.py <run_dir> [--chain <path>] [--out <dir>]
Exit: 0 all verdicts pass; 1 a verdict failed; 2 inputs missing / empty.
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.native_mining_check import FOUND          # noqa: E402
from scripts.native_daa_analysis import load_config      # noqa: E402


def es_revenue_share(alpha: float, gamma: float) -> float:
    num = alpha * (1 - alpha) ** 2 * (4 * alpha + gamma * (1 - 2 * alpha)) - alpha ** 3
    den = 1 - alpha * (1 + (2 - alpha) * alpha)
    return num / den


def parse_found_blocks(run_dir, miner_ids) -> list:
    run_dir = Path(run_dir)
    out = []
    for miner in miner_ids:
        for log in sorted(glob.glob(str(run_dir / "shadow.data" / "hosts" / miner / "monerod*.stdout"))):
            with open(log, "r", errors="replace") as f:
                for line in f:
                    m = FOUND.search(line)
                    if m:
                        out.append({"hash": m.group(2), "height": int(m.group(3)), "miner": miner})
    return out


def found_by_hash(found: list) -> dict:
    # First finder wins if a hash somehow repeats (it should not).
    mapping = {}
    for e in found:
        mapping.setdefault(e["hash"], e["miner"])
    return mapping


def attacker_share_from_chain(chain: list, hash_to_miner: dict, attacker_ids: set) -> float:
    if not chain:
        return 0.0
    att = sum(1 for b in chain if hash_to_miner.get(b["hash"]) in attacker_ids)
    return att / len(chain)


def orphan_stats(found: list, canonical_hashes: set, attacker_ids: set) -> dict:
    att_found = sum(1 for e in found if e["miner"] in attacker_ids)
    att_canon = sum(1 for e in found if e["miner"] in attacker_ids and e["hash"] in canonical_hashes)
    tot_found = len(found)
    tot_canon = sum(1 for e in found if e["hash"] in canonical_hashes)
    return {
        "attacker_found": att_found,
        "attacker_canonical": att_canon,
        "attacker_orphan_rate": (1 - att_canon / att_found) if att_found else 0.0,
        "total_found": tot_found,
        "network_orphan_rate": (1 - tot_canon / tot_found) if tot_found else 0.0,
    }


def _attacker_ids(cfg):
    return {aid for aid, a in cfg.get("agents", {}).items() if a.get("script") == "agents.selfish_miner"}


def _honest_miner_ids(cfg):
    return {aid for aid, a in cfg.get("agents", {}).items() if a.get("script") == "agents.autonomous_miner"}


def _alpha_from_config(cfg):
    agents = cfg.get("agents", {})
    att = sum(a.get("hashrate", 0) for a in agents.values() if a.get("script") == "agents.selfish_miner")
    honest = sum(a.get("hashrate", 0) for a in agents.values() if a.get("script") == "agents.autonomous_miner")
    total = att + honest
    return (att / total) if total else 0.0


def make_verdicts(alpha, measured_share, stats) -> list:
    verdicts = []
    theory = es_revenue_share(alpha, 0.0)
    verdicts.append({
        "name": "attacker share vs Eyal-Sirer gamma=0 curve",
        "measured": measured_share, "theory": theory,
        "pass": abs(measured_share - theory) <= 0.10,
    })
    if alpha > 0.34:
        verdicts.append({
            "name": "attacker beats honest baseline (share > alpha)",
            "measured": measured_share, "baseline": alpha,
            "pass": measured_share > alpha,
        })
    return verdicts


def _find_chain_file(run_dir, explicit):
    if explicit:
        return Path(explicit)
    for cand in glob.glob(str(Path(run_dir) / "**" / "canonical_chain.json"), recursive=True):
        return Path(cand)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--chain", default=None, help="path to canonical_chain.json (default: search run_dir)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    cfg_path = run_dir / "input_config.yaml"
    if not cfg_path.exists():
        print(f"ERROR: {cfg_path} missing", file=sys.stderr)
        return 2
    cfg = load_config(cfg_path)
    attacker_ids = _attacker_ids(cfg)
    miner_ids = list(attacker_ids | _honest_miner_ids(cfg))

    chain_path = _find_chain_file(run_dir, args.chain)
    if not chain_path or not chain_path.exists():
        print("ERROR: canonical_chain.json not found (bridge did not record it?)", file=sys.stderr)
        return 2
    chain = json.loads(chain_path.read_text()).get("chain", [])
    if not chain:
        print("ERROR: empty canonical chain", file=sys.stderr)
        return 2

    found = parse_found_blocks(run_dir, miner_ids)
    h2m = found_by_hash(found)
    canonical_hashes = {b["hash"] for b in chain}
    alpha = _alpha_from_config(cfg)
    share = attacker_share_from_chain(chain, h2m, attacker_ids)
    stats = orphan_stats(found, canonical_hashes, attacker_ids)
    verdicts = make_verdicts(alpha, share, stats)

    out_dir = Path(args.out) if args.out else (run_dir / "analysis_output" / "selfish")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = _render(alpha, share, stats, verdicts)
    (out_dir / "report.md").write_text(report)
    print(report)
    return 0 if all(v["pass"] for v in verdicts) else 1


def _render(alpha, share, stats, verdicts) -> str:
    lines = ["# Selfish-mining analysis", "",
             f"- alpha: {alpha:.3f}",
             f"- attacker canonical share (measured): {share:.3f}",
             f"- Eyal-Sirer gamma=0 theory: {es_revenue_share(alpha, 0.0):.3f}",
             f"- attacker orphan rate: {stats['attacker_orphan_rate']:.3f}",
             f"- network orphan rate: {stats['network_orphan_rate']:.3f}",
             "", "## Verdicts", ""]
    for v in verdicts:
        lines.append(f"- {'PASS' if v['pass'] else 'FAIL'}: {v['name']} (measured {v['measured']:.3f})")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/bin/python -m pytest scripts/test_selfish_mining_analysis.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add scripts/selfish_mining_analysis.py scripts/test_selfish_mining_analysis.py
git commit -m "feat(selfish): revenue-share analysis from ground-truth canonical chain"
```

---

## Task 10: Documentation

**Files:**
- Create: `docs/SELFISH_MINING.md`
- Modify: `CHANGELOG.md` (add an entry under the working section)
- Modify: `docs/NATIVE_MINING.md` (one pointer line to the new doc)

**Interfaces:** none (docs only). No test; the "test" is that the commands and file references in the doc match what the earlier tasks created.

- [ ] **Step 1: Write `docs/SELFISH_MINING.md`**

Cover, each as a short section (write real content, no placeholders):
1. **What it is** — the two-daemon attacker (offline miner + connected bridge) and the Python `SelfishMinerAgent`; no monerod patch; γ ≈ 0 single-bridge regime is the Eyal–Sirer baseline.
2. **How it works** — the withhold/forward/release loop; the strategy state machine (`agents/selfish_strategy.py`); bridge discovery via `agent_registry.json`.
3. **Config** — annotate `test_configs/selfish_micro.yaml`: the `daemon_options: {offline: true}` on the attacker, `attributes.strategy`/`bridge_agent`/`attack_start_height`/`reaction_delay_ms`, and the `agents.selfish_bridge` node. Explain the α = hashrate-split formula.
4. **Running the micro gate** — the generation + (manual, nice'd) run command shape and the analysis command `python3 scripts/selfish_mining_analysis.py <run_dir>`, and what a PASS looks like.
5. **What phase 1 does NOT do** — γ-lifting (needs multi-bridge, phase 2), stubborn variants, colluding pool. Point at the spec's §10/§11.
6. **Validation gates** — restate spec §9 (a neutral plumbing, b determinism, c Eyal–Sirer micro, d suites) with the exact test commands from Tasks 1–8.

- [ ] **Step 2: Add the CHANGELOG entry**

```markdown
- Selfish-mining apparatus (phase 1): an offline attacker miner + connected
  bridge + `SelfishMinerAgent` running Eyal-Sirer withholding over stock RPCs
  (no daemon patch); `scripts/selfish_mining_analysis.py` measures attacker
  revenue share vs the gamma=0 theory curve. See docs/SELFISH_MINING.md.
```

- [ ] **Step 3: Add the pointer in `docs/NATIVE_MINING.md`**

Add one line near the top (after the intro) pointing to `docs/SELFISH_MINING.md` as the adversarial extension built on native mining.

- [ ] **Step 4: Sanity-check references**

Run: `grep -n "selfish_mining_analysis\|selfish_micro\|selfish_miner\|selfish_bridge" docs/SELFISH_MINING.md`
Expected: the referenced paths all exist (cross-check against the files created in Tasks 3–8).

- [ ] **Step 5: Commit**

```bash
git add docs/SELFISH_MINING.md docs/NATIVE_MINING.md CHANGELOG.md
git commit -m "docs(selfish): SELFISH_MINING.md, changelog, native-mining pointer"
```

---

## Final verification (run after all tasks)

- [ ] Python suite: `venv/bin/python -m pytest agents/ scripts/test_selfish_configs.py scripts/test_selfish_mining_analysis.py -q` — all pass. (The `agents/` path already covers the selfish strategy, bridge, miner, and submit_block tests.)
- [ ] Rust suite: `MONEROSIM_SKIP_SIM_BINARY_CHECK=1 cargo test` — all pass (native + selfish goldens, mining unit tests).
- [ ] Generation smoke: `test_configs/selfish_micro.yaml` generates without error.
- [ ] Then hand to `superpowers:finishing-a-development-branch`. Do NOT merge or push; the branch stays local per the Global Constraints. A real micro simulation run (gates a/b/c, which needs the bridge's `canonical_chain.json` + the analysis) is executed by the user afterward, not in this plan.

---

## Self-review notes (author)

- **Spec coverage:** §2 no-patch → all tasks use stock RPC + `--offline` (Tasks 1,4,5,7). §3 architecture → Tasks 3,4,7,8. §4 data flow → Task 4 (forward/release). §5 strategy knobs → Tasks 2,4,7. §6 γ≈0 → Tasks 2,9 (documented, tested). §7 metrics → Task 9, sourced from the Task 8 recorder. §8 experiment 1 (revenue vs α) → Tasks 7,9. §9 gates a–d → Task 4 (honest baseline), final verification (determinism/suites), Task 9 (Eyal–Sirer). §12 deliverables → all tasks. Phase-2 items (stubborn, multi-bridge γ, colluding) correctly excluded.
- **Attribution correctness (revised mid-plan):** the original Task 8 reused `build_accepted`, which dedupes races by earliest timestamp and so misattributes a selfish attacker's withheld, early-found, later-lost tie blocks. Replaced by: Task 8 records an honest node's ground-truth canonical chain (bridge `canonical_chain.json`), Task 9 attributes each canonical hash to its finder via the miners' FOUND logs. This is the faithful source at γ≈0.
- **Placeholder scan:** none — every code step has runnable code; the "adjust to match real names" notes (Tasks 4, 6, 8) are explicit verification instructions against named functions, not vague TODOs.
- **Type consistency:** `SelfishStrategy(name, start_height)` / `.update(pub_height, priv_height) -> ReleaseDecision(release_to, adopt_public)` / `.fork` used identically in Tasks 2 and 4. `MoneroRPC.submit_block(blob)` defined in Task 1, used in Task 4. `is_native_miner_script` defined and used in Task 5. `canonical_chain.json` produced by Task 8, consumed by Task 9. `es_revenue_share`/`attacker_share_from_chain`/`orphan_stats` defined and tested together in Task 9. Attacker identified everywhere by `script == "agents.selfish_miner"` (Tasks 6,7,9).
