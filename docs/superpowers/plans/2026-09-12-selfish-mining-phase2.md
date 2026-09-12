# Selfish-Mining Phase 2 — Implementation Plan (γ-lifting + stubborn variants)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lift the selfish-miner's tie-break advantage γ above zero with multiple publisher bridges, and add the three stubborn-mining strategy variants, measuring γ and each strategy's realized revenue.

**Architecture:** Extend the phase-1 `SelfishMinerAgent` to a list of bridges (read from the first, release to all) so a released block reaches honest nodes that have not yet seen the honest block, lifting γ. Give `SelfishStrategy` one new output, `forward_to` (the honest height up to which the agent feeds honest blocks into the offline miner), so a stubborn strategy can keep the miner on a non-longest private branch. Add trail/equal-fork/lead stubborn policies over that. The analysis measures realized γ and compares revenue to the Eyal–Sirer curve at the measured γ. No monerod patch, no orchestrator change.

**Tech Stack:** Python 3 agents (stdlib + `requests`), pytest, YAML configs, Shadow, monerod/monerod-sim. Python tests via `venv/bin/python -m pytest`; Rust via `cargo test` (no global `MONEROSIM_SKIP_SIM_BINARY_CHECK`).

**Spec:** `docs/superpowers/specs/2026-09-12-selfish-mining-phase2-design.md`.

## Global Constraints

- **No monerod patch, stock RPCs only** (`get_block`, `submit_block`, `get_info`, `--offline`). No orchestrator change.
- **Base branch `feat/native-mining`**. Do not merge/push; do not touch `main`.
- **Backward compatibility (load-bearing):** `honest` and `eyal_sirer` must return `forward_to = None` in every branch, and a one-element bridge list must behave exactly as phase-1's single `bridge_agent`. The phase-1 micro result (attacker ≈0.47 at α=0.4, single bridge) must be unchanged.
- **Document for human verification (explicit user goal):** every file gets comments a reviewer can follow; the stubborn rules are unit-tested by asserting the full `(release_to, forward_to, adopt_public)` triple per transition; and Task 7 writes a results doc a human uses to reproduce and validate every run.
- **Shared box:** scope process ops to `lever65`; this plan runs unit tests and generation only. Experiment sims are launched by the operator, nice'd.
- **TDD, frequent commits**, attribution trailers as on recent commits.

---

## File Structure

- `agents/selfish_miner.py` — **modify**: single bridge → list; honor `decision.forward_to` in the forwarder; reorder `run_iteration` to decide before forwarding.
- `agents/selfish_strategy.py` — **modify**: add `forward_to` to `ReleaseDecision`; add `trail_stubborn`/`equal_fork_stubborn`/`lead_stubborn` to `update()`; accept `trail_depth`.
- `agents/test_selfish_miner.py`, `agents/test_selfish_strategy.py` — **modify**: multi-bridge, forward_to, and per-variant transition tests.
- `scripts/selfish_mining_analysis.py`, `scripts/test_selfish_mining_analysis.py` — **modify**: `realized_gamma`, revenue-at-measured-γ.
- `test_configs/selfish_phase2/` — **create**: γ-fanout sweep (`fanout_1/3/6.yaml`) + stubborn set (`stub_trail.yaml`, `stub_equalfork.yaml`, `stub_lead.yaml`).
- `scripts/test_selfish_phase2_configs.py` — **create**: config invariants.
- `docs/SELFISH_MINING.md`, `docs/20260912_selfish_mining_results.md`, `CHANGELOG.md` — **modify/create**: docs + results writeup.

---

## Task 1: Multi-bridge `SelfishMinerAgent`

**Files:** Modify `agents/selfish_miner.py`; Test `agents/test_selfish_miner.py`.

**Interfaces produced:** `self.bridge_agent_ids: list[str]` (from `bridges` attr, comma-separated, or the single `bridge_agent` alias); `self.bridge_rpcs: list[MoneroRPC]` with `self.bridge_rpc = bridge_rpcs[0]`; `_connect_bridges() -> bool` (True when all connected); `_release_up_to` submits each block to every bridge.

- [ ] **Step 1: Failing tests** — append to `agents/test_selfish_miner.py`:

```python
def test_bridges_attribute_parsed_as_list():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1, b2 ,b3"]])
    a.logger = MagicMock()
    assert a.bridge_agent_ids == ["b1", "b2", "b3"]

def test_bridge_agent_is_single_element_alias():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridge_agent", "only"]])
    a.logger = MagicMock()
    assert a.bridge_agent_ids == ["only"]

def test_connect_bridges_all_and_read_source():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1,b2"]])
    a.logger = MagicMock()
    a.read_shared_state = MagicMock(return_value={"agents": [
        {"id": "b1", "ip_addr": "10.0.0.1", "daemon_rpc_port": 28081},
        {"id": "b2", "ip_addr": "10.0.0.2", "daemon_rpc_port": 28082}]})
    assert a._connect_bridges() is True
    assert [r.url for r in a.bridge_rpcs] == [
        "http://10.0.0.1:28081/json_rpc", "http://10.0.0.2:28082/json_rpc"]
    assert a.bridge_rpc.url == "http://10.0.0.1:28081/json_rpc"

def test_connect_bridges_retries_missing():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1,b2"]])
    a.logger = MagicMock()
    a.read_shared_state = MagicMock(return_value={"agents": [
        {"id": "b1", "ip_addr": "10.0.0.1", "daemon_rpc_port": 28081}]})
    assert a._connect_bridges() is False and len(a.bridge_rpcs) == 1
    a.read_shared_state = MagicMock(return_value={"agents": [
        {"id": "b1", "ip_addr": "10.0.0.1", "daemon_rpc_port": 28081},
        {"id": "b2", "ip_addr": "10.0.0.2", "daemon_rpc_port": 28082}]})
    assert a._connect_bridges() is True and len(a.bridge_rpcs) == 2

def test_release_submits_to_all_bridges():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1,b2"]])
    a.logger = MagicMock(); a.daemon_rpc = MagicMock()
    a.daemon_rpc.get_block.side_effect = lambda height: {"blob": f"p{height}"}
    b1, b2 = MagicMock(), MagicMock(); a.bridge_rpcs = [b1, b2]; a.bridge_rpc = b1
    a._release_up_to(0, 1)
    assert [c.args[0] for c in b1.submit_block.call_args_list] == ["p0", "p1"]
    assert [c.args[0] for c in b2.submit_block.call_args_list] == ["p0", "p1"]
```
Also UPDATE the existing single-bridge tests: `test_release_up_to_submits_private_blocks_to_bridge` and `test_release_tolerates_rejected_alt` must set `a.bridge_rpcs = [a.bridge_rpc]` after setting `a.bridge_rpc` (since `_release_up_to` now iterates `bridge_rpcs`). Rename `_connect_bridge`→`_connect_bridges` in `test_connect_bridge_reads_registry` (still asserts `a.bridge_rpc.url == "http://11.0.0.2:28082/json_rpc"`) and `test_connect_bridge_missing_returns_false` (asserts `_connect_bridges() is False`, `a.bridge_rpcs == []`).

- [ ] **Step 2: Run → fail.** `venv/bin/python -m pytest agents/test_selfish_miner.py -v` (names undefined).

- [ ] **Step 3: Implement.** In `__init__` replace the single-bridge lines with:
```python
        bridges_attr = self.attributes.get("bridges") or self.attributes.get("bridge_agent") or ""
        self.bridge_agent_ids = [b.strip() for b in bridges_attr.split(",") if b.strip()]
        self.bridge_rpcs = []
        self.bridge_rpc = None
        self._connected_ids = set()
```
Replace `_connect_bridge` with `_connect_bridges` (connects any missing bridge found in the registry, sets `bridge_rpc = bridge_rpcs[0]`, returns True when `len(_connected_ids) == len(bridge_agent_ids) > 0`). In `_release_up_to`, wrap the submit in `for rpc in self.bridge_rpcs:` (each in its own try/except RPCError). In `run_iteration`, replace the connect guard with:
```python
        if len(self.bridge_rpcs) < len(self.bridge_agent_ids):
            self._connect_bridges()
        if not self.bridge_rpcs:
            return 1.0
```
(Full bodies were specified in the prior plan revision and in the spec §3; implement to the tests above.)

- [ ] **Step 4: Run → pass.** `venv/bin/python -m pytest agents/test_selfish_miner.py -v`; then `venv/bin/python -m pytest agents/ -q`.

- [ ] **Step 5: Commit.** `git add agents/selfish_miner.py agents/test_selfish_miner.py` / `git commit -m "feat(selfish): multi-bridge attacker (release floods all bridges)"`.

---

## Task 2: `forward_to` plumbing (strategy output + agent honors it)

**Files:** Modify `agents/selfish_strategy.py`, `agents/selfish_miner.py`; Test both test files.

**Interfaces produced:** `ReleaseDecision.forward_to: Optional[int] = None`. `honest`/`eyal_sirer` set it to `None` in every branch (no behavior change). `SelfishMinerAgent._forward_public_blocks(self, pub_height, tip_hash=None, forward_to=None)` forwards only up to `effective_tip = pub_height if forward_to is None else min(pub_height, forward_to)`. `run_iteration` decides *before* forwarding and passes `decision.forward_to`.

- [ ] **Step 1: Failing tests.**
Strategy (append to `agents/test_selfish_strategy.py`):
```python
def test_eyal_sirer_forward_to_is_none():
    s = SelfishStrategy("eyal_sirer", start_height=0)
    for pub, priv in [(0, 2), (1, 2), (2, 2), (3, 2)]:
        assert s.update(pub, priv).forward_to is None

def test_honest_forward_to_is_none():
    s = SelfishStrategy("honest", start_height=0)
    assert s.update(5, 5).forward_to is None
```
Agent (append to `agents/test_selfish_miner.py`):
```python
def test_forward_to_caps_forwarding():
    a = SelfishMinerAgent(agent_id="atk", attributes=[["bridges", "b1"]])
    a.logger = MagicMock(); a.daemon_rpc = MagicMock(); a.bridge_rpc = MagicMock()
    a.bridge_rpcs = [a.bridge_rpc]
    a.bridge_rpc.get_block.side_effect = lambda height: {"blob": f"h{height}"}
    a._forward_public_blocks(pub_height=5, tip_hash=None, forward_to=2)  # cap at index 1
    submitted = [c.args[0] for c in a.daemon_rpc.submit_block.call_args_list]
    assert submitted == ["h0", "h1"]          # indexes 0,1 only (forward_to=2 => heights <2)
    assert a._forwarded_index == 1
```

- [ ] **Step 2: Run → fail.** `venv/bin/python -m pytest agents/test_selfish_strategy.py agents/test_selfish_miner.py -v` (forward_to unknown / not capped).

- [ ] **Step 3: Implement.**
In `agents/selfish_strategy.py`: add `forward_to: Optional[int] = None` to `ReleaseDecision`; in `update()` add `forward_to=None` to every `ReleaseDecision(...)` return (honest + all eyal_sirer branches). No logic change for those two strategies.
In `agents/selfish_miner.py`: change `_forward_public_blocks` signature to accept `forward_to=None` and compute `effective_tip = pub_height if forward_to is None else min(pub_height, forward_to)`, then use `effective_tip` everywhere the body currently uses `pub_height` (the new-block loop bound, the `floor`/`hi` reorg window, the `_forwarded_index = effective_tip - 1` update, and the stale-hash cleanup threshold). Reorder `run_iteration`: read heights → `decision = self.strategy.update(pub_height, priv_height)` → `self._forward_public_blocks(pub_height, pub_tip_hash, decision.forward_to)` → release per decision. (Deciding before forwarding is required so `forward_to` can gate the forward; `update()` already uses only the heights read at the top of the tick.)

- [ ] **Step 4: Run → pass.** Both test files, then `venv/bin/python -m pytest agents/ -q` (phase-1 behavior unchanged: eyal_sirer forward_to None ⇒ effective_tip = pub_height).

- [ ] **Step 5: Commit.** `git add agents/selfish_strategy.py agents/selfish_miner.py agents/test_selfish_strategy.py agents/test_selfish_miner.py` / `git commit -m "feat(selfish): forward_to — strategy gates how far honest blocks reach the miner"`.

---

## Task 3: Stubborn strategy variants

**Files:** Modify `agents/selfish_strategy.py`; Test `agents/test_selfish_strategy.py`.

**Interfaces produced:** `SelfishStrategy.__init__` accepts `name ∈ {honest, eyal_sirer, trail_stubborn, equal_fork_stubborn, lead_stubborn}` and `trail_depth: int = 1`; `update()` implements the §4.2 rules, returning the `(release_to, forward_to, adopt_public)` triple. Heights: `a = priv − old_fork`, `h = pub − old_fork`.

**Decision rules (verbatim target — the tests assert these):**

*trail_stubborn(j)* — same as eyal_sirer except:
- `a == 0 and h > 0`, or `h − a > j`: adopt (`forward_to=None`, `fork=pub`, `adopt_public=True`, `release_to=None`).
- `0 < h − a ≤ j`: hold — `release_to=None`, `forward_to=old_fork`, `adopt_public=False` (miner keeps its branch).
- `a ≥ h`: eyal_sirer rules (`forward_to=None`).

*equal_fork_stubborn* — eyal_sirer plus a `self._was_tie` bit:
- set `self._was_tie=True` whenever it returns a tie contest (`a == h ≥ 1`).
- `a < h`: if `self._was_tie and h − a == 1`: hold (`release_to=None`, `forward_to=old_fork`), keep `_was_tie=True`. Else adopt (`forward_to=None`, `fork=pub`), set `_was_tie=False`.
- `a ≥ h`: eyal_sirer rules; clear `_was_tie` except when returning the tie contest.

*lead_stubborn* — eyal_sirer except on the override step `a − h == 1`:
- release only to the honest tip: `release_to = pub_height − 1`, `forward_to=None`, `fork` unchanged (keep the top block hidden and keep mining).
- all other states: eyal_sirer rules. Adopt only when `a < h`.

- [ ] **Step 1: Failing tests** — append to `agents/test_selfish_strategy.py`. Cover each variant's distinctive transitions, asserting the full triple:
```python
def _triple(d):
    return (d.release_to, d.forward_to, d.adopt_public)

def test_trail_stubborn_holds_within_depth_then_concedes():
    s = SelfishStrategy("trail_stubborn", start_height=0); s.trail_depth = 2
    s.update(0, 1)                         # lead 1, withhold
    assert _triple(s.update(2, 1)) == (None, 0, False)   # behind 1 (<=2): hold, forward_to=fork(0)
    assert _triple(s.update(3, 1)) == (None, 0, False)   # behind 2 (<=2): still hold
    d = s.update(4, 1)                     # behind 3 (>2): concede
    assert d.adopt_public is True and d.forward_to is None and s.fork == 4

def test_trail_stubborn_depth_zero_is_eyal_sirer():
    s0 = SelfishStrategy("trail_stubborn", start_height=0); s0.trail_depth = 0
    e = SelfishStrategy("eyal_sirer", start_height=0)
    for pub, priv in [(0, 2), (1, 2), (2, 1), (2, 3)]:
        assert _triple(s0.update(pub, priv)) == _triple(e.update(pub, priv))

def test_equal_fork_stubborn_holds_one_round_out_of_tie():
    s = SelfishStrategy("equal_fork_stubborn", start_height=0)
    s.update(0, 1)                         # lead 1
    assert _triple(s.update(1, 1)) == (0, None, False)   # tie: contest (release match), _was_tie set
    assert _triple(s.update(2, 1)) == (None, 0, False)   # honest +1 out of tie: hold one round
    d = s.update(3, 1)                     # honest 2 ahead: concede
    assert d.adopt_public is True and s.fork == 3

def test_lead_stubborn_override_reveals_only_to_tip():
    s = SelfishStrategy("lead_stubborn", start_height=0)
    s.update(0, 2)                         # lead 2, withhold
    d = s.update(1, 2)                     # a-h==1 override: reveal only to honest tip
    assert d.release_to == 0 and d.forward_to is None and s.fork == 0   # top (idx1) kept hidden
```

- [ ] **Step 2: Run → fail.** `venv/bin/python -m pytest agents/test_selfish_strategy.py -v` (`ValueError: unknown strategy` then assertion failures).

- [ ] **Step 3: Implement** the three branches in `update()` per the rules above; extend the `__init__` name whitelist and add `self.trail_depth = int(...)` and `self._was_tie = False`. Keep honest/eyal_sirer exactly as-is (they already set `forward_to=None` after Task 2). Factor the eyal_sirer body into a helper the stubborn branches can call for their `a ≥ h` / fallthrough cases to avoid duplication.

- [ ] **Step 4: Run → pass.** `venv/bin/python -m pytest agents/test_selfish_strategy.py -v`; then `venv/bin/python -m pytest agents/ -q`.

- [ ] **Step 5: Commit.** `git add agents/selfish_strategy.py agents/test_selfish_strategy.py` / `git commit -m "feat(selfish): trail/equal-fork/lead stubborn strategy variants"`.

---

## Task 4: Realized-γ estimator in the analysis

Exactly as in the prior plan revision. `realized_gamma(found, chain, attacker_ids) -> (float, int)` over tie heights (both an attacker- and honest-found block at the same height); report `realized gamma` + `num ties`; add a revenue-vs-`es_revenue_share(α, γ_measured)` verdict.

- [ ] **Step 1: Failing tests** (append to `scripts/test_selfish_mining_analysis.py`):
```python
def test_realized_gamma_counts_tie_wins():
    from scripts.selfish_mining_analysis import realized_gamma
    found = [{"hash":"a2","height":2,"miner":"attacker-miner"},{"hash":"h2","height":2,"miner":"honest-001"},
             {"hash":"a3","height":3,"miner":"attacker-miner"},{"hash":"h3","height":3,"miner":"honest-002"},
             {"hash":"h4","height":4,"miner":"honest-001"}]
    chain = [{"height":2,"hash":"a2"},{"height":3,"hash":"h3"},{"height":4,"hash":"h4"}]
    g, ties = realized_gamma(found, chain, {"attacker-miner"})
    assert ties == 2 and abs(g - 0.5) < 1e-9

def test_realized_gamma_zero_when_no_ties():
    from scripts.selfish_mining_analysis import realized_gamma
    g, ties = realized_gamma([{"hash":"a1","height":1,"miner":"attacker-miner"}],
                             [{"height":1,"hash":"a1"}], {"attacker-miner"})
    assert ties == 0 and g == 0.0
```

- [ ] **Step 2: Run → fail.** `venv/bin/python -m pytest scripts/test_selfish_mining_analysis.py -v`.

- [ ] **Step 3: Implement** `realized_gamma` (group `found` by height; a tie = a height with both an attacker and a non-attacker finder; win = the canonical hash at that height was found by an attacker). Wire `gamma, n_ties = realized_gamma(found, chain, attacker_ids)` into `main()`; add `theory_at_gamma = es_revenue_share(alpha, gamma)`; add a verdict `abs(share - theory_at_gamma) <= 0.10`; print `realized gamma`, `num ties`, and `theory at measured gamma` in `_render`.

- [ ] **Step 4: Run → pass.** `venv/bin/python -m pytest scripts/test_selfish_mining_analysis.py -v`.

- [ ] **Step 5: Commit.** `git add scripts/selfish_mining_analysis.py scripts/test_selfish_mining_analysis.py` / `git commit -m "feat(selfish): realized-gamma estimator + revenue-at-measured-gamma"`.

---

## Task 5: Phase-2 configs (γ-fanout sweep + stubborn set)

**Files:** Create `test_configs/selfish_phase2/{fanout_1,fanout_3,fanout_6,stub_trail,stub_equalfork,stub_lead}.yaml`; Test `scripts/test_selfish_phase2_configs.py`.

**Topology (shared by all):** 3 honest miners (hashrate 2 each) + 12 relays (staggered starts) + attacker (hashrate 4 → α=0.4, `daemon_options:{offline:true}`) + N publisher bridges (`script: agents.selfish_bridge`, `daemon_options:{out-peers:16}`) + monitor; `simulation_seed:12345`, `reaction_delay_ms:"50"`. The larger honest network gives latency spread so γ is measurable (spec §7).
- `fanout_1/3/6.yaml`: 1/3/6 bridges (attacker `bridges` attr lists exactly them), `strategy: eyal_sirer`.
- `stub_trail.yaml` / `stub_equalfork.yaml` / `stub_lead.yaml`: copies of `fanout_6.yaml` with `strategy:` set to `trail_stubborn` (`attributes.trail_depth:"2"`) / `equal_fork_stubborn` / `lead_stubborn`.

- [ ] **Step 1: Failing config test** (`scripts/test_selfish_phase2_configs.py`): parametrized over the six configs — assert exactly the expected bridge count, the attacker `bridges` attr lists exactly the bridge ids, `daemon_options.offline is True`, `mining.mode == native`, α≈0.4, and the `strategy` matches the filename intent (`stub_trail` ⇒ `trail_stubborn`, etc.). (Same shape as `scripts/test_selfish_configs.py`.)

- [ ] **Step 2: Run → fail** (configs missing).

- [ ] **Step 3: Write the six configs** per the topology above.

- [ ] **Step 4: Run → pass**, then a generation smoke on one: `MONEROSIM_SKIP_SIM_BINARY_CHECK=1 MONEROSIM_SHARED_DIR=/tmp/p2g cargo run --quiet --bin monerosim -- --config test_configs/selfish_phase2/fanout_1.yaml --output /tmp/p2g_out 2>&1 | tail -15` → exit 0; remove temp dirs.

- [ ] **Step 5: Commit.** `git add test_configs/selfish_phase2/ scripts/test_selfish_phase2_configs.py` / `git commit -m "test(selfish): phase-2 fanout sweep + stubborn config set"`.

---

## Task 6: `docs/SELFISH_MINING.md` phase-2 section + CHANGELOG

- [ ] **Step 1:** Add a phase-2 section to `docs/SELFISH_MINING.md` (real content): the multi-bridge attacker and `bridges` attribute; the `forward_to` mechanism (why stubborn needs it); each stubborn variant's rule, in the §4.2 words, with what it bets on; how γ is lifted by fan-out not position (the reframe + reason); how to run the fanout sweep and the stubborn set and read `realized gamma`/`num ties`/`theory at measured gamma`; and that γ is small without latency spread (hence the larger topology). 
- [ ] **Step 2:** CHANGELOG entry under `## [Unreleased]` after the phase-1 selfish line (multi-bridge γ-lifting + forward_to + stubborn variants + realized-γ).
- [ ] **Step 3:** `grep -n "forward_to\|stub_\|fanout_\|realized gamma\|bridges" docs/SELFISH_MINING.md` — confirm references exist.
- [ ] **Step 4: Commit.** `git add docs/SELFISH_MINING.md CHANGELOG.md` / `git commit -m "docs(selfish): phase-2 section (multi-bridge, forward_to, stubborn, gamma)"`.

---

## Task 7: Results & validation writeup (human entry point)

**Files:** Create `docs/20260912_selfish_mining_results.md`.

This is the document a human reads to validate the whole apparatus without re-deriving it. It is written AFTER the experiments are run (the operator runs the sims; this task records and interprets them). It must contain, for every run actually performed:
- the exact command and config, the archived run-dir id, and the `selfish_mining_analysis.py` command to reproduce the numbers;
- the measured attacker share, the Eyal–Sirer theory (at γ=0 and at the measured γ), the realized γ, orphan rates, and the verdict;
- interpretation: the α-threshold finding, the idealized-curve-is-an-upper-bound gap at high α (with the orphan-rate evidence and the reaction-delay hypothesis), whether γ lifted with fan-out, and how each stubborn variant compared to eyal_sirer;
- a "how to verify this yourself" section: re-run one config, re-run the analysis, and check the number against the theory formula.

- [ ] **Step 1:** Write the doc with the phase-1 runs already archived (micro `20260912_131855_selfish_micro_t1`; sweep `…_exp_sw0300/sw0400/sw0450`; honest + long runs) and leave clearly-marked slots for the phase-2 fanout/stubborn runs, filled once those sims complete.
- [ ] **Step 2:** Cross-check every run-dir id and command against what exists on disk (`ls archived_runs/`), and every theory number against `es_revenue_share`.
- [ ] **Step 3: Commit.** `git add docs/20260912_selfish_mining_results.md` / `git commit -m "docs(selfish): results and validation writeup"`.

---

## Final verification (after all tasks)

- [ ] Python: `venv/bin/python -m pytest agents/ scripts/test_selfish_mining_analysis.py scripts/test_selfish_configs.py scripts/test_selfish_phase2_configs.py -q` — all pass.
- [ ] Rust: `cargo test` — all pass.
- [ ] Phase-1 regression: single-bridge path unchanged (phase-1 selfish tests pass; `eyal_sirer`/`honest` return `forward_to=None`; `selfish_micro.yaml` still generates).
- [ ] Operator runs the phase-2 sims (fanout 1/3/6 for the γ curve; the three stubborn configs at fanout 6), then fills Task 7's doc slots and re-runs the analysis.
- [ ] Then `superpowers:finishing-a-development-branch` (keep local, do not merge/push).

## Self-review notes (author)

- **Spec coverage:** §3 multi-bridge → Task 1; §3/§4.1 forward_to → Task 2; §4.2 stubborn → Task 3; §5 realized-γ → Task 4; §6/§7 experiments+topology → Task 5; §9 docs → Tasks 6–7 (results doc = the human-verification goal).
- **Placeholder scan:** none — each code step has the edit or the decision rules + tests; configs specified by exact agent/field lists. (Task 1's full bodies reference the spec §3 and the prior revision, with the tests as the precise contract.)
- **Type consistency:** `ReleaseDecision(release_to, adopt_public, release_from, forward_to)`; `update()` returns it for all strategies; agent `_forward_public_blocks(pub_height, tip_hash, forward_to)` honors it; `bridges`→`bridge_agent_ids`→`bridge_rpcs`/`bridge_rpc`. Backward-compat asserted in Tasks 1–2 (single bridge; forward_to None).
