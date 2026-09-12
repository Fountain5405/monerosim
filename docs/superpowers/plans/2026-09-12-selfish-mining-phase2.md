# Selfish-Mining Phase 2 — Implementation Plan (γ-lifting)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lift the selfish-miner's tie-break advantage γ above zero by giving the attacker multiple publisher bridges that flood a released block, and measure γ as a function of fan-out.

**Architecture:** Extend the phase-1 `SelfishMinerAgent` from one bridge to a list: it reads the honest tip from the first and, on release, submits each block to every bridge. A block reaches honest nodes that have not yet seen the honest block through whichever publisher is "ahead", so it wins a fraction γ of ties that rises with fan-out. The analysis measures realized γ from the race outcomes. No monerod patch; no orchestrator change (multi-bridge is config plus the agent reading a list; `out-peers`/priority nodes are existing daemon knobs).

**Tech Stack:** Python 3 agents (`agents/*.py`, stdlib + `requests`), pytest, YAML configs, Shadow, monerod/monerod-sim. Tests via `venv/bin/python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-09-12-selfish-mining-phase2-design.md`.

## Global Constraints

- **No monerod patch, stock RPCs only** (`get_block`, `submit_block`, `get_info`, `--offline`). No orchestrator change.
- **Base branch `feat/native-mining`** (holds phase-1 + this). Do not merge/push; do not touch `main`.
- **Backward compatibility:** a one-element bridge list must behave exactly as phase-1's single `bridge_agent`, so the phase-1 micro result (attacker share 0.471 at α=0.4) is unchanged. Phase-1 configs using `bridge_agent` must keep working.
- **Shared box:** scope process ops to `lever65`; this plan runs unit tests and generation only (the γ sweep is run by the operator afterward, nice'd).
- **Scope:** this plan delivers γ-lifting only. Stubborn-mining variants (lead/equal-fork/trail) are deferred — they require strategy-gating the forwarder to make the miner mine a non-longest chain, and only differ from selfish mining once γ>0 is demonstrated. Revisit them after the γ-vs-fan-out sweep confirms γ lifts.
- **TDD, frequent commits**, attribution trailers as on recent commits.

---

## File Structure

- `agents/selfish_miner.py` — **modify**: single bridge → a list of bridges (connect all, read from the first, release to all). Keep `bridge_agent` as a one-element alias for `bridges`.
- `agents/test_selfish_miner.py` — **modify**: add multi-bridge tests; keep the single-bridge tests green.
- `scripts/selfish_mining_analysis.py` — **modify**: add `realized_gamma(...)`, surface it in the report and add a γ verdict, and compare the measured share to `es_revenue_share(α, γ_measured)` as well as the γ=0 curve.
- `scripts/test_selfish_mining_analysis.py` — **modify**: tests for `realized_gamma`.
- `test_configs/selfish_phase2/base_6bridge.yaml`, `fanout_1.yaml`, `fanout_3.yaml`, `fanout_6.yaml` — **create**: a larger honest network (latency spread) + an attacker publisher-count sweep.
- `scripts/test_selfish_phase2_configs.py` — **create**: config invariants.
- `docs/SELFISH_MINING.md` — **modify**: phase-2 section. `CHANGELOG.md` — **modify**.

---

## Task 1: Multi-bridge `SelfishMinerAgent`

**Files:**
- Modify: `agents/selfish_miner.py`
- Test: `agents/test_selfish_miner.py`

**Interfaces:**
- Consumes (unchanged): `AutonomousMinerAgent`, `MoneroRPC(host, port)`, `RPCError`, `read_shared_state`, `SelfishStrategy`, the existing `_forward_public_blocks`/`_release_up_to`/`run_iteration` structure.
- Produces:
  - `self.bridge_agent_ids: list[str]` — parsed from the `bridges` attribute (comma-separated) or, if absent, the single `bridge_agent` (one-element list).
  - `self.bridge_rpcs: list[MoneroRPC]` — connected bridges; `self.bridge_rpc` is `bridge_rpcs[0]` (the read/forward source) or None.
  - `self._connected_ids: set[str]` — which bridge ids are connected (so missing ones are retried).
  - `_connect_bridges(self) -> bool` — connects any not-yet-connected bridge found in the registry; returns True when every requested bridge is connected.
  - `_release_up_to` submits each block to **every** connected bridge.

- [ ] **Step 1: Write the failing tests** (append to `agents/test_selfish_miner.py`)

```python
def test_bridges_attribute_parsed_as_list():
    a = SelfishMinerAgent(agent_id="atk",
                          attributes=[["strategy", "eyal_sirer"],
                                      ["bridges", "b1, b2 ,b3"]])
    a.logger = MagicMock()
    assert a.bridge_agent_ids == ["b1", "b2", "b3"]


def test_bridge_agent_is_single_element_alias():
    a = SelfishMinerAgent(agent_id="atk",
                          attributes=[["bridge_agent", "only-bridge"]])
    a.logger = MagicMock()
    assert a.bridge_agent_ids == ["only-bridge"]


def test_connect_bridges_connects_all_and_sets_read_source():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1,b2"]])
    a.logger = MagicMock()
    a.read_shared_state = MagicMock(return_value={"agents": [
        {"id": "b1", "ip_addr": "10.0.0.1", "daemon_rpc_port": 28081},
        {"id": "b2", "ip_addr": "10.0.0.2", "daemon_rpc_port": 28082},
    ]})
    assert a._connect_bridges() is True
    assert [r.url for r in a.bridge_rpcs] == [
        "http://10.0.0.1:28081/json_rpc", "http://10.0.0.2:28082/json_rpc"]
    assert a.bridge_rpc.url == "http://10.0.0.1:28081/json_rpc"   # read source = first


def test_connect_bridges_retries_missing():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1,b2"]])
    a.logger = MagicMock()
    a.read_shared_state = MagicMock(return_value={"agents": [
        {"id": "b1", "ip_addr": "10.0.0.1", "daemon_rpc_port": 28081}]})
    assert a._connect_bridges() is False          # b2 missing
    assert len(a.bridge_rpcs) == 1
    a.read_shared_state = MagicMock(return_value={"agents": [
        {"id": "b1", "ip_addr": "10.0.0.1", "daemon_rpc_port": 28081},
        {"id": "b2", "ip_addr": "10.0.0.2", "daemon_rpc_port": 28082}]})
    assert a._connect_bridges() is True           # b2 now present; b1 not re-added
    assert len(a.bridge_rpcs) == 2


def test_release_submits_to_all_bridges():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1,b2"]])
    a.logger = MagicMock()
    a.daemon_rpc = MagicMock()
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"p{height}"}
    b1, b2 = MagicMock(), MagicMock()
    a.bridge_rpcs = [b1, b2]
    a.bridge_rpc = b1
    a._release_up_to(0, 1)                          # indexes 0,1
    assert [c.args[0] for c in b1.submit_block.call_args_list] == ["p0", "p1"]
    assert [c.args[0] for c in b2.submit_block.call_args_list] == ["p0", "p1"]
```

Also UPDATE the existing single-bridge tests that set `a.bridge_rpc` directly: `test_release_up_to_submits_private_blocks_to_bridge` and `test_release_tolerates_rejected_alt` must now also set `a.bridge_rpcs = [a.bridge_rpc]` (since `_release_up_to` iterates `bridge_rpcs`). Add that one line to each. `test_connect_bridge_reads_registry`/`test_connect_bridge_missing_returns_false` call `_connect_bridge`; rename those calls to `_connect_bridges` and adjust: the registry test should assert `a.bridge_rpc.url == "http://11.0.0.2:28082/json_rpc"` still holds (single bridge via `bridge_agent`), and the missing test asserts `_connect_bridges() is False` and `a.bridge_rpcs == []`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/bin/python -m pytest agents/test_selfish_miner.py -v`
Expected: FAIL (`bridge_agent_ids`/`bridge_rpcs`/`_connect_bridges` not defined).

- [ ] **Step 3: Implement multi-bridge in `agents/selfish_miner.py`**

In `__init__`, replace the single-bridge lines:
```python
        self.bridge_agent_id = self.attributes.get("bridge_agent")
        ...
        self.bridge_rpc = None
```
with:
```python
        bridges_attr = self.attributes.get("bridges") or self.attributes.get("bridge_agent") or ""
        self.bridge_agent_ids = [b.strip() for b in bridges_attr.split(",") if b.strip()]
        self.bridge_rpcs = []          # all connected publisher bridges
        self.bridge_rpc = None         # read/forward source = bridge_rpcs[0]
        self._connected_ids = set()
```
Replace `_connect_bridge` with:
```python
    def _connect_bridges(self) -> bool:
        """Connect to every requested bridge found in the registry; retry any
        still missing on later ticks. bridge_rpcs[0] is the read/forward
        source; releases go to all of them (phase-2 gamma-lifting)."""
        registry = self.read_shared_state("agent_registry.json") or {}
        by_id = {a.get("id"): a for a in registry.get("agents", [])}
        for bid in self.bridge_agent_ids:
            if bid in self._connected_ids:
                continue
            a = by_id.get(bid)
            if a and a.get("ip_addr") and a.get("daemon_rpc_port"):
                self.bridge_rpcs.append(MoneroRPC(a["ip_addr"], int(a["daemon_rpc_port"])))
                self._connected_ids.add(bid)
                self.logger.info(f"Bridge connected: {bid} at {a['ip_addr']}:{a['daemon_rpc_port']}")
        if self.bridge_rpcs:
            self.bridge_rpc = self.bridge_rpcs[0]
        return bool(self.bridge_agent_ids) and len(self._connected_ids) == len(self.bridge_agent_ids)
```
In `_release_up_to`, change the single submit to a loop over all bridges:
```python
            try:
                blk = self.daemon_rpc.get_block(height=idx)
                self._warn_if_has_txs(blk, idx, "private")
                blob = blk.get("blob")
                if blob:
                    for rpc in self.bridge_rpcs:
                        try:
                            rpc.submit_block(blob)
                        except RPCError as e:
                            self.logger.debug(f"release block {idx} to a bridge: {e}")
            except RPCError as e:
                self.logger.debug(f"release private block {idx}: fetch {e}")
            self._released_index = max(self._released_index, idx)
```
In `run_iteration`, replace the connect guard:
```python
        if self.bridge_rpc is None and not self._connect_bridge():
            return 1.0
```
with (retry missing bridges each tick, proceed once at least one is up):
```python
        if len(self.bridge_rpcs) < len(self.bridge_agent_ids):
            self._connect_bridges()
        if not self.bridge_rpcs:
            return 1.0
```
Update the module docstring's `bridge_agent` line to mention `bridges` (comma-separated list; `bridge_agent` is the one-element alias).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/bin/python -m pytest agents/test_selfish_miner.py -v`
Expected: PASS (all, including the updated single-bridge tests).

- [ ] **Step 5: Full agent suite (no regression)**

Run: `venv/bin/python -m pytest agents/ -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add agents/selfish_miner.py agents/test_selfish_miner.py
git commit -m "feat(selfish): multi-bridge attacker (release floods all bridges) for gamma-lifting"
```

---

## Task 2: Realized-γ estimator in the analysis

**Files:**
- Modify: `scripts/selfish_mining_analysis.py`
- Test: `scripts/test_selfish_mining_analysis.py`

**Interfaces:**
- Consumes: the `found` list (`{hash,height,miner}` from `parse_found_blocks`), the canonical `chain` list (`{height,hash}`), the attacker id set (`_attacker_ids`).
- Produces: `realized_gamma(found, chain, attacker_ids) -> tuple[float, int]` returning `(gamma_estimate, num_ties)`; the report and verdicts use it.

**Definition:** a *tie* at height h is a height where both an attacker-found block and an honest-found block exist in the miners' logs (a race). γ = fraction of ties the attacker won, where "won" means the canonical block at h was found by the attacker.

- [ ] **Step 1: Write the failing test** (append to `scripts/test_selfish_mining_analysis.py`)

```python
def test_realized_gamma_counts_tie_wins():
    from scripts.selfish_mining_analysis import realized_gamma
    found = [
        {"hash": "a2", "height": 2, "miner": "attacker-miner"},
        {"hash": "h2", "height": 2, "miner": "honest-001"},   # tie at 2
        {"hash": "a3", "height": 3, "miner": "attacker-miner"},
        {"hash": "h3", "height": 3, "miner": "honest-002"},   # tie at 3
        {"hash": "h4", "height": 4, "miner": "honest-001"},   # not a tie
    ]
    chain = [{"height": 2, "hash": "a2"},   # attacker won tie 2
             {"height": 3, "hash": "h3"},   # honest won tie 3
             {"height": 4, "hash": "h4"}]
    gamma, ties = realized_gamma(found, chain, {"attacker-miner"})
    assert ties == 2
    assert abs(gamma - 0.5) < 1e-9


def test_realized_gamma_zero_when_no_ties():
    from scripts.selfish_mining_analysis import realized_gamma
    found = [{"hash": "a1", "height": 1, "miner": "attacker-miner"}]
    chain = [{"height": 1, "hash": "a1"}]
    gamma, ties = realized_gamma(found, chain, {"attacker-miner"})
    assert ties == 0 and gamma == 0.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest scripts/test_selfish_mining_analysis.py -v`
Expected: FAIL (`realized_gamma` not defined).

- [ ] **Step 3: Implement `realized_gamma` and wire it into the report**

Add to `scripts/selfish_mining_analysis.py`:
```python
def realized_gamma(found, chain, attacker_ids):
    """gamma estimate: of the heights where BOTH an attacker- and an
    honest-found block exist (a race/tie), the fraction the attacker won on
    the canonical chain. Returns (gamma, num_ties)."""
    from collections import defaultdict
    canonical_by_height = {b["height"]: b["hash"] for b in chain}
    at_height = defaultdict(list)          # height -> [(miner, hash)]
    for e in found:
        at_height[e["height"]].append((e["miner"], e["hash"]))
    ties = att_wins = 0
    for h, entries in at_height.items():
        has_att = any(m in attacker_ids for m, _ in entries)
        has_hon = any(m not in attacker_ids for m, _ in entries)
        if has_att and has_hon:
            ties += 1
            winner = next((m for m, hh in entries if hh == canonical_by_height.get(h)), None)
            if winner in attacker_ids:
                att_wins += 1
    return (att_wins / ties if ties else 0.0), ties
```
In `main()`, after computing `share`, add:
```python
    gamma, n_ties = realized_gamma(found, chain, attacker_ids)
```
and extend the verdicts: add a theory-at-measured-γ comparison
```python
    theory_at_gamma = es_revenue_share(alpha, gamma)
```
(pass `gamma`, `n_ties`, `theory_at_gamma` into `make_verdicts`/`_render`). In `make_verdicts`, add a verdict that the measured share is within 0.10 of `es_revenue_share(alpha, gamma)`. In `_render`, print `realized gamma`, `num ties`, and `Eyal-Sirer theory at measured gamma`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/bin/python -m pytest scripts/test_selfish_mining_analysis.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfish_mining_analysis.py scripts/test_selfish_mining_analysis.py
git commit -m "feat(selfish): realized-gamma estimator + revenue-at-measured-gamma verdict"
```

---

## Task 3: Larger topology + publisher-count sweep configs

**Files:**
- Create: `test_configs/selfish_phase2/base_6bridge.yaml` (α=0.4, 6 publisher bridges, larger honest net)
- Create: `test_configs/selfish_phase2/fanout_1.yaml`, `fanout_3.yaml`, `fanout_6.yaml` (same honest net, 1/3/6 bridges)
- Test: `scripts/test_selfish_phase2_configs.py`

**Interfaces:** config YAML only; the agent reads `bridges` (Task 1).

**Topology:** a larger honest network gives B_h real propagation distance so the attacker's flood can win some ties. Use 3 honest miners (hashrate 2+2+2=6) + 12 relays + the attacker (hashrate 4 → α=0.4) + N publisher bridges (each `script: agents.selfish_bridge`, `daemon_options: {out-peers: 16}`) + monitor. The attacker's `bridges` attribute lists all N bridge ids. `reaction_delay_ms: "50"` (faster reaction raises γ).

- [ ] **Step 1: Write the failing config test**

```python
# scripts/test_selfish_phase2_configs.py
from pathlib import Path
import yaml, pytest

CONFIGS = {
    "fanout_1": 1, "fanout_3": 3, "fanout_6": 6,
}

@pytest.mark.parametrize("name,nbridges", CONFIGS.items())
def test_fanout_config_has_n_bridges(name, nbridges):
    cfg = yaml.safe_load(open(f"test_configs/selfish_phase2/{name}.yaml"))
    agents = cfg["agents"]
    bridges = [k for k, v in agents.items() if v.get("script") == "agents.selfish_bridge"]
    assert len(bridges) == nbridges, f"{name}: expected {nbridges} bridges"
    att = next(v for v in agents.values() if v.get("script") == "agents.selfish_miner")
    listed = [b.strip() for b in att["attributes"]["bridges"].split(",")]
    assert sorted(listed) == sorted(bridges), "attacker lists exactly its bridges"
    assert att["daemon_options"]["offline"] is True
    assert cfg["general"]["mining"]["mode"] == "native"

def test_alpha_is_0p4_across_fanout():
    for name in CONFIGS:
        cfg = yaml.safe_load(open(f"test_configs/selfish_phase2/{name}.yaml"))
        agents = cfg["agents"]
        att = sum(v["hashrate"] for v in agents.values() if v.get("script") == "agents.selfish_miner")
        hon = sum(v["hashrate"] for v in agents.values() if v.get("script") == "agents.autonomous_miner")
        assert abs(att/(att+hon) - 0.4) < 0.01
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest scripts/test_selfish_phase2_configs.py -v`
Expected: FAIL (configs missing).

- [ ] **Step 3: Write the configs**

Write `fanout_6.yaml` with: `general` as in `test_configs/selfish_micro.yaml` but `stop_time: 6h`, `reaction_delay_ms` lives on the attacker; 3 honest miners `honest-001/002/003` (hashrate 2 each, `script: agents.autonomous_miner`, wallet, start 0s); 12 relays `relay-001`..`relay-012` (`daemon: monerod`, staggered `start_time`); the attacker `attacker-miner` (`script: agents.selfish_miner`, hashrate 4, `daemon_options: {offline: true}`, `attributes: {strategy: eyal_sirer, bridges: "bridge-1,bridge-2,bridge-3,bridge-4,bridge-5,bridge-6", attack_start_height: "0", reaction_delay_ms: "50"}`); 6 bridges `bridge-1`..`bridge-6` (`daemon: monerod`, `script: agents.selfish_bridge`, `daemon_options: {out-peers: 16}`, start 0s); `simulation-monitor`. `fanout_3.yaml` and `fanout_1.yaml` are identical but with 3 / 1 bridges (and the attacker's `bridges` list trimmed to match). `base_6bridge.yaml` = a copy of `fanout_6.yaml` (the canonical α=0.4 lifted-γ config). Keep `simulation_seed: 12345` across all four.

- [ ] **Step 4: Run the config test + a generation smoke**

Run: `venv/bin/python -m pytest scripts/test_selfish_phase2_configs.py -v` → PASS.
Then: `MONEROSIM_SKIP_SIM_BINARY_CHECK=1 MONEROSIM_SHARED_DIR=/tmp/p2gen cargo run --quiet --bin monerosim -- --config test_configs/selfish_phase2/fanout_1.yaml --output /tmp/p2gen_out 2>&1 | tail -15` → exit 0, no error about `selfish_miner`/`bridges`/`offline`. Remove the temp dirs after.

- [ ] **Step 5: Commit**

```bash
git add test_configs/selfish_phase2/ scripts/test_selfish_phase2_configs.py
git commit -m "test(selfish): phase-2 larger-topology publisher-count sweep configs"
```

---

## Task 4: Documentation

**Files:**
- Modify: `docs/SELFISH_MINING.md` (phase-2 section)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add a phase-2 section to `docs/SELFISH_MINING.md`**

Write a real section covering: the multi-bridge attacker (`bridges` attribute, release floods all); that γ is lifted by fan-out/connectivity, not position (the reframe, with the reason); how to run the γ-vs-fan-out sweep (`test_configs/selfish_phase2/fanout_{1,3,6}.yaml`) and read `realized gamma` + `num ties` from the analysis; that the larger topology is needed for γ to be measurable; and that stubborn-mining variants are deferred until the sweep confirms γ lifts. Point at the phase-2 spec.

- [ ] **Step 2: Add the CHANGELOG entry** (inside `## [Unreleased]`, after the phase-1 selfish entry)

```markdown
- Selfish-mining phase 2 (gamma-lifting): the attacker runs multiple publisher
  bridges and floods a released block to all of them, lifting the tie-break
  advantage gamma above zero; `scripts/selfish_mining_analysis.py` now reports
  realized gamma and compares revenue to the Eyal-Sirer curve at the measured
  gamma. Sweep configs in `test_configs/selfish_phase2/`. See docs/SELFISH_MINING.md.
```

- [ ] **Step 3: Sanity-check references**

Run: `grep -n "selfish_phase2\|realized gamma\|bridges" docs/SELFISH_MINING.md` and confirm the referenced paths/attributes exist.

- [ ] **Step 4: Commit**

```bash
git add docs/SELFISH_MINING.md CHANGELOG.md
git commit -m "docs(selfish): phase-2 gamma-lifting section + changelog"
```

---

## Final verification (after all tasks)

- [ ] Python suite: `venv/bin/python -m pytest agents/ scripts/test_selfish_mining_analysis.py scripts/test_selfish_configs.py scripts/test_selfish_phase2_configs.py -q` — all pass.
- [ ] Rust suite: `cargo test` — all pass (no global `MONEROSIM_SKIP_SIM_BINARY_CHECK`).
- [ ] Phase-1 regression: the single-bridge path still works (`test_configs/selfish_micro.yaml` generates; the single-bridge agent tests pass).
- [ ] Then hand to `superpowers:finishing-a-development-branch` (keep local, do not merge/push). The γ-vs-fan-out sweep itself (fanout_1/3/6) is run by the operator afterward, nice'd; the key result is whether realized γ rises with fan-out.

## Self-review notes (author)

- **Spec coverage:** §3 multi-bridge → Task 1. §5 realized-γ + revenue-at-γ → Task 2. §7 larger topology + §6 experiment-1 sweep → Task 3. §9 deliverables/docs → Task 4. Stubborn variants (§4, §6-exp3) deliberately deferred per Global Constraints (mechanism complexity + only-matters-at-γ>0); flagged to the user.
- **Placeholder scan:** none — each code step has the actual edit; config contents are specified by exact agent/field lists.
- **Type consistency:** `bridges` attr → `bridge_agent_ids: list` → `bridge_rpcs: list` / `bridge_rpc` (first), used in Task 1 and relied on by the config's `bridges` attribute in Task 3. `realized_gamma(found, chain, attacker_ids) -> (float, int)` defined and tested in Task 2. Backward-compat: one-element `bridges` == phase-1 single-bridge (Global Constraints, tested in Task 1's updated single-bridge tests).
