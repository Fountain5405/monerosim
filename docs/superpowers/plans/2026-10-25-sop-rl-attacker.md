# SoP learned attacker (RL) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train a tabular policy against the race model that earns more than the hand-written `window_stubborn` noown attacker under Share-or-Perish, and run that policy as a new strategy inside the 12-daemon Shadow simulations.

**Architecture:** The race model (`scripts/sop_race_model.py` Model B) gets a `reset()`/`step()` API with the exact-MDP observation; `simulate()` becomes a wrapper that drives it with the stubborn policy. A second, tiny environment wraps `scripts/sop_mdp.py`'s scalar transition functions so the learner can be checked against the exact solver. `scripts/sop_rl.py` holds relative-value Q-learning, the share bisection, policy evaluation and export (a diff against the sim's stubborn rule). `agents/selfish_strategy.py` gains a `learned` strategy that builds the same observation from the miner's branch weights and looks the action up, falling back to stubborn.

**Tech Stack:** Python 3.12, numpy, standard library only (no new dependencies). pytest.

**Spec:** `docs/superpowers/specs/2026-10-25-sop-rl-attacker-design.md`

## Global Constraints

- No training, evaluation, test suites or Monte Carlo on the control box (owner rule 2026-10-25). Every `Run:` line below executes on a lane box through `.claude/campaign9/remote_test.sh` (Task 1 creates it): phantom while lithium's exact solve runs, lithium afterwards.
- No new dependencies: numpy and the standard library only.
- `simulate()` keeps its signature and its results bit for bit (the 39 tests in `scripts/test_sop_race_model.py` plus the pinned table in Task 1).
- Observation everywhere is the exact-MDP state `(a, D, xa, pa, h, xh, ph)` as `scripts/sop_mdp.py` defines it: window counters capped at `WINDOW = 32` and both collapsed to 32 once either passes; D in objects (blocks plus embedded shares), honest pending NOT in D.
- Actions are `HOLD, PUBLISH, REVEAL, GIVE_UP = 0, 1, 2, 3` with `ACTION_NAMES` from `scripts/sop_mdp.py`; legality: publish only when `a >= 1 and h == 0`; reveal only when `h >= 1` and the network accepts; give up whenever `a >= 1 or h >= 1 or att_pending > 0`; hold always.
- Q-table key = observation with `|D|` clipped to 128 and `pa`, `ph` clipped to 48 (the game itself is uncapped). Coarsening, if ever needed, bins D first, never a or h.
- Share bisection bracket 0.05 to 0.80, tolerance 1e-3; direction from a greedy rollout, never from the learner's estimate.
- "Beats stubborn" = mean share over 5 seeds x 2000 d at least 0.01 above `sim_stubborn`'s; 24 h wall per alpha.
- Training settings for real policies: `RULE_PRESETS["20261020_noown"]`, honest shares via the slot rule (`equal_start`, `early_honest_shares`, `positional_shares` all True), `attacker_embeds` True, `give_up_objects` not used by the environment (it is the stubborn policy's rule), `cap_blocks` 0, far caps `|D| <= 200`, objects deficit `<= 200`.
- Policy files live in `data/sop_rl/` as gzip JSON and are committed.

## Review Focus

1. A `policy_file` that is missing, unreadable, or trained for a different alpha than the cell's: the strategy must raise at construction, never fall back silently on every decision. Test in Task 5.
2. A sim observation outside the key clip (|D| > 128 or pending > 48): the lookup uses the clipped key and counts it; it must not crash or fall back. Test in Task 5.
3. A learned "reveal" in a state where the strategy's own acceptance test fails (the network would refuse): becomes hold and is counted, never a rejected reveal. Test in Task 5.
4. A learned "publish" at h == 0: must release the private blocks without the weight test (no competing branch). Test in Task 5.
5. A bisection whose greedy rollouts never cross rho (learner stalls, share 0): `share_search` terminates after the fixed number of steps and reports the best rollout seen with a `converged: False` flag. Test in Task 4.

---

### Task 1: Race-model step API, stubborn policy, fidelity test

**Files:**
- Modify: `scripts/sop_race_model.py:262-330` (SimConfig), `:367-511` (simulate)
- Test: `scripts/test_sop_race_model.py`
- Create: `.claude/campaign9/remote_test.sh`

**Interfaces:**
- Produces: `class SopEnv` in `scripts/sop_race_model.py`:
  - `__init__(self, cfg: SimConfig)`
  - `reset(self, seed: int) -> Obs` draws the first object and returns the observation at the first decision point.
  - `step(self, action: int) -> Tuple[Obs, int, int]` applies `action` at the current decision point, settles blocks (`fa` attacker, `fh` honest become final), draws the next object, returns `(obs, fa, fh)`. Raises `ValueError` on an illegal action.
  - `legal(self) -> Tuple[bool, bool, bool, bool]` per the Global Constraints.
  - `obs(self) -> Obs` the current observation.
  - `stats: SimStats` (same accounting as `simulate()`), plus `objects: int` drawn so far and `n_objects: int` = `int(cfg.days * SECONDS_PER_DAY * cfg.w / T_BLOCK_S)`, the run length `simulate()` uses.
  - Attributes readable by policies: `att_blocks, hon_blocks, att_pending, hon_pending, att_fork, hon_fork, last_is_block: bool, last_is_attacker: bool`.
- Produces: `def stubborn_policy(env: SopEnv) -> int` reproducing `simulate()`'s rules exactly: objects give-up (`hon_fork - att_fork > give_up_objects`, at every event, including a == 0 where the reset drops the pending shares, honoured by `step` for GIVE_UP at a == 0), d-mode give-up after blocks, hold at h == 0 (publish only when `cap_blocks` forces it), `release_depth`, reveal when past the window and the weight test wins, forced actions at `cap_blocks`, tie handling via `tie_win_prob` (a lost tie is a GIVE_UP chosen by the policy after `env.tie_lost` is set by the draw).
- Produces: `simulate(cfg)` rewritten as `env = SopEnv(cfg); env.reset(cfg.seed); while env.objects < n: env.step(stubborn_policy(env)); return env.stats`, same results as before.
- Produces: `Obs = Tuple[int, int, int, int, int, int, int]` and `def observation(att_blocks, hon_blocks, att_pending, hon_pending) -> Obs` (module-level, pure; D = sum(1+n for att) - sum(1+m for hon), x per branch = sum over blocks[1:] of (1+shares) capped at 32, collapse when either >= 32).

- [ ] **Step 1: Create `.claude/campaign9/remote_test.sh`**

```bash
#!/bin/bash
# remote_test.sh <box> <pytest args...>: rsync the working tree's scripts/, agents/,
# test_configs/, data/sop_rl/ to <box>:~/monerosim_rl/ (a scratch copy; the box's
# ~/monerosim stays the sim tree) and run pytest there with the box's venv.
# Owner rule 2026-10-25: nothing runs on the control box.
box=$1; shift
cd /home/selfishmining/monerosim
ssh -o BatchMode=yes $box 'mkdir -p ~/monerosim_rl/data'
rsync -a --delete --exclude __pycache__ --ignore-missing-args scripts agents test_configs pytest.ini $box:monerosim_rl/
rsync -a --delete --ignore-missing-args data/sop_rl $box:monerosim_rl/data/
ssh -o BatchMode=yes $box "cd ~/monerosim_rl && ~/monerosim/venv/bin/python -m pytest $*"
```

Run: `bash .claude/campaign9/remote_test.sh phantom scripts/test_sop_race_model.py -q`
Expected: `39 passed`

- [ ] **Step 2: Pin the current `simulate()` results**

Run on phantom (through a one-off script rsynced the same way) and paste the output into the test as `PINNED`:

```python
# scratch: pin_simulate.py
from scripts.sop_race_model import SimConfig, RULE_PRESETS, simulate
import json
cases = []
for rv in ("20261015", "20261020", "20261020_noown"):
    for hs in (False, True):
        for cap in (0, 3):
            for seed in (1, 2):
                cfg = SimConfig(alpha=0.45, d=1, rule="sop", attacker_embeds=True, days=60, seed=seed,
                                give_up_objects=5, equal_start=hs, early_honest_shares=hs,
                                positional_shares=hs, cap_blocks=cap, **RULE_PRESETS[rv])
                s = simulate(cfg)
                cases.append([rv, hs, cap, seed, s.att_final_blocks, s.hon_final_blocks, s.reveals,
                              s.att_orphaned_blocks, sum(s.reorg_depths), s.max_reorg_depth])
for d in (1, 2):   # d-mode (block-depth give-up) and stock
    for rule in ("sop", "stock"):
        s = simulate(SimConfig(alpha=0.4, d=d, rule=rule, attacker_embeds=(rule == "sop"), days=60, seed=3,
                               **(RULE_PRESETS["20261020"] if rule == "sop" else {})))
        cases.append([rule, d, 0, 3, s.att_final_blocks, s.hon_final_blocks, s.reveals,
                      s.att_orphaned_blocks, sum(s.reorg_depths), s.max_reorg_depth])
s = simulate(SimConfig(alpha=0.45, d=1, rule="sop", attacker_embeds=True, days=60, seed=4,
                       give_up_objects=5, tie_win_prob=0.5, equal_start=True, **RULE_PRESETS["20261020"]))
cases.append(["tie", True, 0, 4, s.att_final_blocks, s.hon_final_blocks, s.reveals,
              s.att_orphaned_blocks, sum(s.reorg_depths), s.max_reorg_depth])
print(json.dumps(cases))
```

- [ ] **Step 3: Write the failing tests** in `scripts/test_sop_race_model.py`

```python
PINNED = [...]   # pasted from step 2

def _cfg_from(row):
    ...  # rebuild the SimConfig exactly as pin_simulate.py did for that row

def test_simulate_results_are_pinned_across_the_step_api_refactor():
    for row in PINNED:
        s = simulate(_cfg_from(row))
        assert [s.att_final_blocks, s.hon_final_blocks, s.reveals, s.att_orphaned_blocks,
                sum(s.reorg_depths), s.max_reorg_depth] == row[4:], row

def test_step_api_with_stubborn_policy_equals_simulate():
    from scripts.sop_race_model import SopEnv, stubborn_policy
    for row in PINNED:
        cfg = _cfg_from(row)
        env = SopEnv(cfg); env.reset(cfg.seed)
        while env.objects < env.n_objects:
            env.step(stubborn_policy(env))
        s = env.stats
        assert [s.att_final_blocks, s.hon_final_blocks, s.reveals, s.att_orphaned_blocks,
                sum(s.reorg_depths), s.max_reorg_depth] == row[4:], row

def test_observation_matches_sop_mdp_definition():
    from scripts.sop_race_model import observation
    assert observation([], [], 0, 0) == (0, 0, 0, 0, 0, 0, 0)
    assert observation([3], [], 2, 5) == (1, 4, 0, 2, 0, 0, 5)          # D = 1+3; x skips the first block
    assert observation([3, 1], [0], 0, 0) == (2, 6 - 1, 2, 0, 1, 0, 0)   # xa = 1+1
    assert observation([0] + [40], [], 0, 0)[2] == 32                   # capped
    assert observation([0, 40], [0, 0], 0, 0)[5] == 32                   # collapsed once either passes

def test_env_legal_mask_and_illegal_action_raises():
    import pytest
    from scripts.sop_race_model import SopEnv, HOLD, PUBLISH, REVEAL, GIVE_UP
    env = SopEnv(SimConfig(alpha=0.45, d=1, rule="sop", attacker_embeds=True, days=1, seed=1,
                           give_up_objects=5, **RULE_PRESETS["20261020_noown"]))
    env.reset(1)
    while env.obs()[0] == 0 or env.obs()[4] != 0:   # reach a state with a >= 1 and h == 0
        env.step(HOLD)
    assert env.legal() == (True, True, False, True)
    with pytest.raises(ValueError):
        env.step(REVEAL)
```

- [ ] **Step 4: Run the tests to verify the pinned test passes and the other three fail**

Run: `bash .claude/campaign9/remote_test.sh phantom scripts/test_sop_race_model.py -q -k "pinned or step_api or observation or legal"`
Expected: 1 passed, 3 failed with `ImportError`/`cannot import name 'SopEnv'`

- [ ] **Step 5: Implement `observation`, `SopEnv`, `stubborn_policy` in `scripts/sop_race_model.py`, then rewrite `simulate()` on top of them**

Move the body of `simulate()` (`:367-511`) into `SopEnv`: the per-object draw into `_draw()` (same two `rng.random()` calls in the same order; the tie draw stays where it is), the settlement branches into `step()`. `step()` dispatch: GIVE_UP = the existing give-up block (`hon_final += h`, `att_orphaned += a`, reset, `att_pending = hon_pending if equal_start else 0`, fork counters); REVEAL = the existing reveal block; PUBLISH = the existing forced-publish block; HOLD = nothing. Far caps: when `abs(D) >= 200 or (hon_fork - att_fork) > 200`, `legal()` returns only the forced action (reveal if accepted, else publish if h == 0, else give up), the same way `cap_blocks` does. Export `HOLD, PUBLISH, REVEAL, GIVE_UP, ACTION_NAMES` by importing them from `scripts.sop_mdp` is NOT allowed (sop_mdp imports numpy; keep the race model dependency-free): define the four constants in `sop_race_model.py` and have `sop_mdp.py` keep its own identical ones.

- [ ] **Step 6: Run the whole race-model test file**

Run: `bash .claude/campaign9/remote_test.sh phantom scripts/test_sop_race_model.py -q`
Expected: `43 passed`

- [ ] **Step 7: Commit**

```bash
git add scripts/sop_race_model.py scripts/test_sop_race_model.py .claude/campaign9/remote_test.sh
git commit -m "SoP race model: reset/step API (SopEnv) with the exact-MDP observation; simulate() now drives it with stubborn_policy; results pinned bit for bit"
```

### Task 2: MDP-game environment and the shared policy helpers

**Files:**
- Create: `scripts/sop_rl.py`
- Test: `scripts/test_sop_rl.py`

**Interfaces:**
- Consumes: `scripts.sop_mdp.{event, actions, accepted, deficit, at_cap, Caps, START, HOLD, PUBLISH, REVEAL, GIVE_UP, WINDOW, W_SHARES}`; `scripts.sop_race_model.{SopEnv, SimConfig, RULE_PRESETS}`.
- Produces in `scripts/sop_rl.py`:
  - `class MdpEnv`: `__init__(self, alpha: float, caps: Caps, own_pending: bool = False)`, `reset(seed) -> Obs`, `step(action) -> (Obs, fa, fh)`, `legal() -> Tuple[bool,...]`, `obs()`, `objects`, `att_final`, `hon_final`, `reveals`. The state IS the observation; `reset(seed)` makes `random.Random(seed)` and each draw is `is_att = rng.random() < alpha` then `is_blk = rng.random() < 1 / W_SHARES` (that order); transitions are `sop_mdp.event` then the chosen entry of `sop_mdp.actions(s, caps, own_pending)` (so a forced action at a cap is the only legal one); rewards are that entry's `(fa, fh)`. Attributes `objects`, `att_final`, `hon_final`, `reveals`, `reorg_depths`.
  - `def sim_stubborn(obs: Obs, G: int = 5) -> int`: the SIM's `window_stubborn` noown rule over the observation: `a == 0 and h > 0` -> GIVE_UP; `h == 0` -> HOLD; `(-D + ph - pa) > G` -> GIVE_UP; `max(xa, xh) >= WINDOW and D > ph` -> REVEAL; else HOLD. (This is `agents/selfish_strategy.py::_window_stubborn_decision` restated; it is the fallback and the diff reference, and it differs from the race model's `stubborn_policy` in giving up at a == 0 with any honest block and never giving up on objects while h == 0.)
  - `def race_env(alpha: float, days: float, seed: int, cap_blocks: int = 0) -> SopEnv` building the training config from the Global Constraints.
  - `def rollout(env, policy: Callable[[Obs, Tuple[bool,...]], int], n_objects: int) -> dict` with keys `share, att, hon, reveals, mean_reorg, max_reorg, decisions, stored_hits` (`stored_hits` counts decisions whose key the policy reported as stored; policies return `(action, stored: bool)` when they are `TablePolicy` instances, else `stored` is False).

- [ ] **Step 1: Write the failing tests** in `scripts/test_sop_rl.py`

```python
import random
from scripts import sop_mdp as M
from scripts import sop_rl as RL

def test_mdp_env_follows_event_then_actions():
    caps = M.Caps(3, 3, 40, 12, 12)
    env = RL.MdpEnv(0.45, caps); o = env.reset(7)
    rng = random.Random(7); s = M.START
    s = M.event(s, rng.random() < 0.45, rng.random() < 1 / M.W_SHARES, caps)
    assert o == s
    legal = env.legal()
    assert legal == tuple(any(a == k for a, *_ in M.actions(s, caps, False)) for k in range(4))

def test_mdp_env_stubborn_rollout_matches_scalar_monte_carlo():
    # the 2026-10-25 figure: 0.1334 (VI) / 0.1343 (MC) at 3/3/40/12/12, count/count
    caps = M.Caps(3, 3, 40, 12, 12)
    env = RL.MdpEnv(0.45, caps, own_pending=True)
    env.reset(1)
    pol = lambda o, legal: M.stubborn_action(o, caps, 5, True, True)[0]
    r = RL.rollout(env, pol, int(500 * 720 * M.W_SHARES))
    assert abs(r["share"] - 0.134) < 0.006

def test_sim_stubborn_rule():
    W = M.WINDOW
    assert RL.sim_stubborn((0, -1, 0, 0, 1, 0, 0)) == M.GIVE_UP
    assert RL.sim_stubborn((1, 2, 0, 0, 0, 0, 30)) == M.HOLD          # h == 0: hold even 28 objects behind
    assert RL.sim_stubborn((1, 2, W, 0, 1, 0, 1)) == M.REVEAL
    assert RL.sim_stubborn((1, 2, W, 0, 1, 0, 2)) == M.HOLD           # D == ph: not accepted
    assert RL.sim_stubborn((1, -3, 0, 0, 1, 0, 3)) == M.GIVE_UP       # deficit 6 > 5

def test_race_env_stubborn_reproduces_the_calibration_number():
    env = RL.race_env(0.45, days=2000, seed=1)
    from scripts.sop_race_model import stubborn_policy
    r = RL.rollout(env, lambda o, legal: stubborn_policy(env), env.n_objects)
    assert abs(r["share"] - 0.2806) < 0.003     # hunt --honest-shares, 20261020_noown, o5, seed 1
```

(`race_env` sets `give_up_objects=5` on the config so `stubborn_policy` has its rule; the learner never reads it.)

- [ ] **Step 2: Run to verify they fail**

Run: `bash .claude/campaign9/remote_test.sh phantom scripts/test_sop_rl.py -q`
Expected: 4 failed, `ModuleNotFoundError: scripts.sop_rl`

- [ ] **Step 3: Implement `MdpEnv`, `sim_stubborn`, `race_env`, `rollout` in `scripts/sop_rl.py`**

`rollout` stops after `n_objects` calls to `env.step` (`MdpEnv` counts `objects` the same way).

- [ ] **Step 4: Run to verify they pass**

Run: `bash .claude/campaign9/remote_test.sh phantom scripts/test_sop_rl.py -q`
Expected: `4 passed` (the 2000 d rollout takes ~10 s)

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_rl.py scripts/test_sop_rl.py
git commit -m "SoP RL: MdpEnv over the exact solver's transitions, sim_stubborn reference rule, race_env and rollout helpers"
```

### Task 3: Relative-value Q-learning

**Files:**
- Modify: `scripts/sop_rl.py`
- Test: `scripts/test_sop_rl.py`

**Interfaces:**
- Produces:
  - `def key_of(obs: Obs, d_clip: int = 128, p_clip: int = 48, d_bin: int = 1) -> Obs` (clip D to +-d_clip then integer-divide by d_bin; clip pa, ph to p_clip).
  - `class QTable`: `__init__(self, d_clip=128, p_clip=48, d_bin=1)`; `q: Dict[Obs, List[float]]` (4 floats, created on first visit as `[0.0]*4`); `visits: Dict[Obs, int]`; `key(obs)`; `greedy(obs, legal) -> int` (argmax over legal, ties to the lowest action index); `__len__`.
  - `def train(env, alpha: float, rho: float, budget: int, q: Optional[QTable] = None, lr: float = 0.05, eps_start: float = 0.3, eps_end: float = 0.02, seed: int = 1, ref: Obs = START) -> QTable`: RVI Q-learning for `budget` steps: `r = fa - rho * (fa + fh)`; `target = r - max(q[ref]) + max_legal(q[s'])`; `q[s][a] += lr * (target - q[s][a])`; epsilon decays linearly from `eps_start` to `eps_end` over the budget; illegal actions are never chosen and never maximised over. Reference value is `max(q[ref])`; `ref = START` is reached whenever the fork is settled with nothing pending.
  - `class TablePolicy`: `__init__(self, q: QTable, fallback=sim_stubborn)`; `__call__(obs, legal) -> Tuple[int, bool]` returning the greedy action if `obs`' key was visited (`stored=True`), else `(fallback(obs), False)`; the chosen action is forced to a legal one (fallback result not legal -> HOLD).

- [ ] **Step 1: Write the failing tests**

```python
def test_key_of_clips_and_bins():
    assert RL.key_of((1, 300, 5, 60, 2, 7, 1)) == (1, 128, 5, 48, 2, 7, 1)
    assert RL.key_of((1, -300, 5, 0, 2, 7, 60)) == (1, -128, 5, 0, 2, 7, 48)
    assert RL.key_of((1, 7, 0, 0, 0, 0, 0), d_bin=2) == (1, 3, 0, 0, 0, 0, 0)

def test_train_finds_publish_at_cap_when_window_is_unreachable():
    # 3/3/40/12/12 cannot reach the window (docs/20261025_sop_mdp_notes.md): the exact
    # optimum is honest mining, 0.4500, reached by publishing at a == 3 and giving up otherwise.
    caps = M.Caps(3, 3, 40, 12, 12)
    env = RL.MdpEnv(0.45, caps); env.reset(1)
    q = RL.train(env, 0.45, rho=0.45, budget=2_000_000, seed=1)
    pol = RL.TablePolicy(q)
    env2 = RL.MdpEnv(0.45, caps); env2.reset(2)
    r = RL.rollout(env2, pol, 2_000_000)
    assert r["share"] > 0.43

def test_table_policy_falls_back_and_respects_legality():
    q = RL.QTable()
    pol = RL.TablePolicy(q)
    a, stored = pol((0, -1, 0, 0, 1, 0, 0), (True, False, False, True))
    assert (a, stored) == (M.GIVE_UP, False)
    q.q[q.key((1, 2, 0, 0, 0, 0, 0))] = [0.0, 1.0, 0.0, 0.0]; q.visits[q.key((1, 2, 0, 0, 0, 0, 0))] = 1
    assert pol((1, 2, 0, 0, 0, 0, 0), (True, True, False, True)) == (M.PUBLISH, True)
    assert pol((1, 2, 0, 0, 0, 0, 0), (True, False, False, True))[0] == M.HOLD   # publish illegal -> next best
```

- [ ] **Step 2: Run to verify they fail**

Run: `bash .claude/campaign9/remote_test.sh phantom scripts/test_sop_rl.py -q -k "key_of or train_finds or table_policy"`
Expected: 3 failed, `AttributeError: module ... has no attribute 'key_of'`

- [ ] **Step 3: Implement `key_of`, `QTable`, `train`, `TablePolicy`**

Store Q rows as Python lists, not numpy arrays (the inner loop is per object; numpy scalars are 10x slower here). Greedy with legality: `max((q[i], -i) for i in range(4) if legal[i])`.

- [ ] **Step 4: Run to verify they pass**

Run: `bash .claude/campaign9/remote_test.sh phantom scripts/test_sop_rl.py -q`
Expected: `7 passed` (the 2 M-step training takes ~10 s)

- [ ] **Step 5: Add the slow exact-optimum check (window reachable), marked slow**

```python
@pytest.mark.slow
def test_train_matches_exact_solver_on_a_small_window_reaching_game():
    # Caps(3,3,32,16,16): (3-1)*(1+16) = 34 >= 32, so reveals are possible; exact solve ~minutes.
    caps = M.Caps(3, 3, 32, 16, 16)
    keys = M.enumerate_keys(caps, False)
    rho_exact, _ = M.Compact(keys, caps, False).share(0.45, optimise=True, lo=0.05, hi=0.8, tol=1e-3)
    env = RL.MdpEnv(0.45, caps); env.reset(1)
    q = None
    for rho in (rho_exact,):                                   # fixed rho: the gain must be ~0
        q = RL.train(env, 0.45, rho=rho, budget=40_000_000, q=q, seed=1)
    env2 = RL.MdpEnv(0.45, caps); env2.reset(2)
    r = RL.rollout(env2, RL.TablePolicy(q), 20_000_000)
    assert abs(r["share"] - rho_exact) < 0.01, (r["share"], rho_exact)
```

Register the marker in `pytest.ini`/`pyproject.toml` if not present (check with `grep -n slow pytest.ini pyproject.toml setup.cfg`).

Run: `bash .claude/campaign9/remote_test.sh phantom scripts/test_sop_rl.py -q -m slow`
Expected: `1 passed` (allow 20 min). If it fails by more than 0.01, raise the budget once (80 M); if it still fails, stop and report: the learner, not the model, is wrong.

- [ ] **Step 6: Commit**

```bash
git add scripts/sop_rl.py scripts/test_sop_rl.py pytest.ini
git commit -m "SoP RL: relative-value Q-learning on the MDP observation (QTable, train, TablePolicy); matches the exact solver on a small window-reaching game"
```

### Task 4: Share search, policy export and the CLI

**Files:**
- Modify: `scripts/sop_rl.py`
- Test: `scripts/test_sop_rl.py`

**Interfaces:**
- Produces:
  - `def share_search(make_env: Callable[[int], Env], alpha: float, budget: int, lo: float = 0.05, hi: float = 0.80, tol: float = 1e-3, eval_objects: int = 23_040_000, seeds: Tuple[int, ...] = (11, 12, 13), log=None) -> dict` with keys `rho, share, q, converged, history` (list of `(rho, share, n_states)`). Each step trains at `mid` warm-started from the previous `q`, rolls the greedy policy out on `eval_objects` objects per seed, and sets `lo = mid` if the mean share > mid else `hi = mid`. Stops when `hi - lo <= tol` or after 12 steps; `converged = hi - lo <= tol`; `share` and `q` are from the best rollout seen.
  - `def export_policy(q: QTable, path: str, meta: dict) -> int` writes gzip JSON `{"meta": meta, "key_clip": {"d": .., "p": .., "d_bin": ..}, "fallback": "sim_stubborn", "policy": {"a,D,xa,pa,h,xh,ph": "hold"|"publish"|"reveal"|"give_up"}}` containing ONLY visited keys whose greedy action differs from `sim_stubborn(key)`; returns the number of entries. `meta` must carry `alpha`, `env` (`race`|`mdp`), the training settings and `share`.
  - `def load_policy(path: str) -> Tuple[dict, dict]` returning `(policy_dict_keyed_by_tuple, meta)`; raises `FileNotFoundError`/`ValueError` on a missing or malformed file.
  - `class FilePolicy` built from `load_policy`: `__call__(obs, legal) -> (action, stored)` with `sim_stubborn` fallback and the same legality guard as `TablePolicy`.
  - CLI (`argparse`, subcommands): `train --alpha --env race|mdp [--a-max --h-max --d-max --p-max --deficit] [--cap-blocks] --budget --out PATH [--lo --hi --tol] [--days-eval] [--seed]` (runs `share_search`, prints the history, calls `export_policy`); `eval --policy PATH|none --alpha --days 2000 --seeds 1 2 3 4 5 [--env race|mdp ...]` (prints share per seed, mean, reveals, mean/max reorg, stored-hit fraction, and the same for `sim_stubborn` for comparison; `--policy none` prints the `sim_stubborn` block only).

- [ ] **Step 1: Write the failing tests**

```python
def test_share_search_terminates_and_reports_best_when_nothing_learns():
    # a budget of 0 steps leaves Q empty: every rollout is sim_stubborn through the MDP game
    caps = M.Caps(3, 3, 40, 12, 12)
    out = RL.share_search(lambda seed: RL.MdpEnv(0.45, caps), 0.45, budget=0, eval_objects=200_000, seeds=(1,))
    assert out["converged"] in (True, False) and len(out["history"]) <= 12
    assert 0.0 <= out["share"] <= 1.0

def test_export_only_stores_differences_from_sim_stubborn_and_round_trips(tmp_path):
    q = RL.QTable()
    s_same = (1, -3, 0, 0, 1, 0, 3)           # sim_stubborn gives up; table agrees
    s_diff = (1, 2, M.WINDOW, 0, 1, 0, 1)     # sim_stubborn reveals; table says hold
    for s, row in ((s_same, [0, 0, 0, 1.0]), (s_diff, [1.0, 0, 0, 0])):
        q.q[q.key(s)] = row; q.visits[q.key(s)] = 3
    n = RL.export_policy(q, str(tmp_path / "p.json.gz"), {"alpha": 0.45, "env": "race", "share": 0.3})
    assert n == 1
    pol, meta = RL.load_policy(str(tmp_path / "p.json.gz"))
    assert pol == {s_diff: M.HOLD} and meta["alpha"] == 0.45
    fp = RL.FilePolicy(str(tmp_path / "p.json.gz"))
    assert fp(s_diff, (True, False, True, True)) == (M.HOLD, True)
    assert fp(s_same, (True, False, False, True)) == (M.GIVE_UP, False)

def test_cli_train_and_eval_smoke(tmp_path):
    import subprocess, sys
    out = tmp_path / "p.json.gz"
    subprocess.run([sys.executable, "scripts/sop_rl.py", "train", "--alpha", "0.45", "--env", "mdp",
                    "--a-max", "3", "--h-max", "3", "--d-max", "40", "--p-max", "12", "--deficit", "12",
                    "--budget", "200000", "--days-eval", "2", "--out", str(out)], check=True)
    r = subprocess.run([sys.executable, "scripts/sop_rl.py", "eval", "--policy", str(out), "--alpha", "0.45",
                        "--env", "mdp", "--a-max", "3", "--h-max", "3", "--d-max", "40", "--p-max", "12",
                        "--deficit", "12", "--days", "2", "--seeds", "1"], check=True, capture_output=True, text=True)
    assert "share" in r.stdout and "sim_stubborn" in r.stdout
```

- [ ] **Step 2: Run to verify they fail**

Run: `bash .claude/campaign9/remote_test.sh phantom scripts/test_sop_rl.py -q -k "share_search or export or cli"`
Expected: 3 failed

- [ ] **Step 3: Implement `share_search`, `export_policy`, `load_policy`, `FilePolicy`, and `main()`**

`eval` with `--env race` builds `race_env(alpha, days, seed)`; with `--env mdp` builds `MdpEnv(alpha, Caps(...))`. The stored-hit fraction is `stored_hits / decisions` from `rollout`.

- [ ] **Step 4: Run to verify they pass**

Run: `bash .claude/campaign9/remote_test.sh phantom scripts/test_sop_rl.py -q`
Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_rl.py scripts/test_sop_rl.py
git commit -m "SoP RL: share bisection on greedy rollouts, gzip-JSON policy export as a diff against sim_stubborn, train/eval CLI"
```

### Task 5: The `learned` strategy in the simulator's attacker

**Files:**
- Modify: `agents/selfish_miner.py:293-360` (`_branch_weights`), `:183-199` and `:238-263` (attributes, `strategy_kwargs`, `_ensure_strategy`), `:22-72` and `:117-121` (docstring)
- Modify: `agents/selfish_strategy.py:72-112` (`__init__`, valid names), `:137-140` (dispatch), new `_learned_decision`
- Test: `agents/test_selfish_strategy.py`, `agents/test_selfish_miner.py`

**Interfaces:**
- Consumes: `scripts.sop_rl.{load_policy, sim_stubborn, key_of}` imported lazily inside the learned path (agents must not import numpy at module load; `sop_rl` imports `sop_mdp` which imports numpy, so import `scripts.sop_rl` only when `name == "learned"`). If that import cost is unacceptable in the agent, move `load_policy`, `key_of` and `sim_stubborn` into a numpy-free module `scripts/sop_policy.py` and have `sop_rl` re-export them; the tests below do not care which.
- Produces:
  - `_branch_weights` returns an 8-tuple: the existing 7 fields plus `[7] hon_objects` (honest blocks + embedded shares since the fork, the objects behind `hon_weight`, without pending). Existing callers use indices 0-6 and `len(weights) >= 5` / `< 7` tests, so they are unaffected.
  - `SelfishStrategy.__init__(..., give_up_objects: int = -1, policy_file: Optional[str] = None)`; `"learned"` added to the valid names; with `name == "learned"`, `policy_file` is required and loaded at construction (relative paths resolved against the repository root, `Path(__file__).resolve().parents[1]`); `ValueError` if missing, unreadable, or `meta["alpha"]` differs from the `alpha` attribute when one is given (`alpha: Optional[float] = None` parameter, passed by the miner from attribute `alpha` if present).
  - `SelfishStrategy.observation(a, h, weights) -> Obs`: `(a, weights[0] - weights[7], min(weights[3], 32), weights[5] - weights[0], h, min(weights[4], 32), weights[6] - weights[7])` with both x collapsed to 32 when either is >= 32.
  - `_learned_decision(self, old_fork, pub_height, priv_height, a, h, branch_weights) -> ReleaseDecision`: weights = `branch_weights(old_fork, priv_height, pub_height)`; if `None` or `len < 8` -> hold; obs -> clipped key -> action from the policy dict, else `sim_stubborn(obs)` (fallback, counted in `self.fallback_decisions`); counters `self.learned_decisions`, `self.clipped_decisions` (key != obs), `self.suppressed_reveals`. Mapping to `ReleaseDecision`: HOLD -> hold (`forward_to=old_fork`); GIVE_UP -> give up (`adopt_public=True`, `self.fork = pub_height`); PUBLISH (only if h == 0 and a >= 1, else hold) -> release (`release_from=old_fork, release_to=priv_height - 1, self.fork = priv_height`) with NO weight test; REVEAL -> release only if `max(weights[3], weights[4]) >= self.window_objects and weights[1] > weights[2]` (the strategy's own acceptance test, identical to `_window_stubborn_decision`'s), else hold and `self.suppressed_reveals += 1`.
  - Miner: attributes `policy_file` (string) and `alpha` (float, optional) read next to `count_own_tip_shares` (`:197`), passed through `strategy_kwargs`/`_ensure_strategy`; docstring entries in the style of `:42-50`. The reveal log line (`:991-994`) is reused unchanged; at every learned decision the miner logs at debug `learned: obs=<tuple> key=<tuple> action=<name> stored=<bool>` and at the end of the run (where it logs the other counters) `learned: decisions=N stored=N fallback=N clipped=N suppressed_reveals=N`.

- [ ] **Step 1: Write the failing strategy tests** in `agents/test_selfish_strategy.py`

```python
def _policy_file(tmp_path, entries, alpha=0.45):
    import gzip, json
    p = tmp_path / "p.json.gz"
    with gzip.open(p, "wt") as f:
        json.dump({"meta": {"alpha": alpha, "env": "race"}, "key_clip": {"d": 128, "p": 48, "d_bin": 1},
                   "fallback": "sim_stubborn", "policy": entries}, f)
    return str(p)

def test_learned_requires_a_loadable_policy_file(tmp_path):
    with pytest.raises(ValueError):
        SelfishStrategy("learned", start_height=0)
    with pytest.raises(ValueError):
        SelfishStrategy("learned", start_height=0, policy_file=str(tmp_path / "missing.json.gz"))
    with pytest.raises(ValueError):
        SelfishStrategy("learned", start_height=0, policy_file=_policy_file(tmp_path, {}, alpha=0.40), alpha=0.45)

def test_learned_observation_matches_sop_mdp():
    from scripts import sop_mdp as M
    # fork at 100; attacker 2 blocks (3 and 1 embedded shares), 2 pending; honest 1 block (0 shares), 5 pending
    w = (6, 6, 1, 2, 0, 8, 6, 1)
    assert SelfishStrategy.observation(2, 1, w) == (2, 5, 2, 2, 1, 0, 5)
    s = M.event(M.event(M.event(M.START, True, True, M.Caps()), True, False, M.Caps()), True, False, M.Caps())
    # one attacker block then two attacker shares: a=1, D=1, pa=2
    assert SelfishStrategy.observation(1, 0, (1, 1, 0, 0, 0, 3, 0, 0)) == s

def test_learned_uses_table_then_falls_back_to_sim_stubborn(tmp_path):
    s = SelfishStrategy("learned", start_height=0, window_objects=32, window_rule="20261020",
                        give_up_objects=5, policy_file=_policy_file(tmp_path, {"1,2,32,0,1,32,1": "hold"}))   # both x collapse to 32
    s.fork = 100
    # stored state says hold where sim_stubborn would reveal
    d = s.update(pub_height=101, priv_height=101, branch_weights=lambda f, p, q: (3, 3, 1, 32, 0, 3, 2, 1))
    assert d.release_to is None and s.learned_decisions == 1 and s.fallback_decisions == 0
    # unseen state: sim_stubborn reveals (past window, D 3 > ph 1)
    d = s.update(pub_height=101, priv_height=101, branch_weights=lambda f, p, q: (4, 4, 1, 32, 0, 4, 2, 1))
    assert d.release_to == 100 and s.fallback_decisions == 1

def test_learned_reveal_is_suppressed_when_own_test_fails_and_publish_skips_it(tmp_path):
    pf = _policy_file(tmp_path, {"1,2,32,0,1,32,3": "reveal", "1,2,0,0,0,0,10": "publish"})
    s = SelfishStrategy("learned", start_height=0, window_objects=32, window_rule="20261020", give_up_objects=5, policy_file=pf)
    s.fork = 100
    d = s.update(pub_height=101, priv_height=101, branch_weights=lambda f, p, q: (3, 3, 4, 32, 0, 3, 4, 1))   # weight 3 <= 4
    assert d.release_to is None and s.suppressed_reveals == 1
    s.fork = 100
    d = s.update(pub_height=100, priv_height=101, branch_weights=lambda f, p, q: (3, 3, 10, 0, 0, 3, 11, 1))  # h == 0, honest pending heavy
    assert d.release_to == 100 and d.release_from == 100

def test_learned_clips_out_of_range_observations(tmp_path):
    pf = _policy_file(tmp_path, {"1,128,0,0,1,0,48": "give_up"})
    s = SelfishStrategy("learned", start_height=0, window_objects=32, window_rule="20261020", give_up_objects=5, policy_file=pf)
    s.fork = 100
    d = s.update(pub_height=101, priv_height=101, branch_weights=lambda f, p, q: (300, 300, 1, 0, 0, 300, 100, 1))
    assert d.adopt_public is True and s.clipped_decisions == 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `bash .claude/campaign9/remote_test.sh phantom agents/test_selfish_strategy.py -q -k learned`
Expected: 5 failed (`ValueError: unknown strategy: learned` / `TypeError: unexpected keyword 'policy_file'`)

- [ ] **Step 3: Implement the strategy side** (`policy_file`, `alpha`, `"learned"`, `observation`, `_learned_decision`, counters, dispatch at `:137`)

- [ ] **Step 4: Run the strategy tests**

Run: `bash .claude/campaign9/remote_test.sh phantom agents/test_selfish_strategy.py -q`
Expected: `63 passed`

- [ ] **Step 5: Write the failing miner test** in `agents/test_selfish_miner.py`, next to the test at `:1163` that drives a real fork through `_branch_weights`

```python
def test_branch_weights_eighth_field_is_honest_objects_without_pending(<same fixture as the :1163 test>):
    ... build the same fork as that test (attacker 2 blocks, honest 1 block, known pending counts) ...
    w = miner._branch_weights(fork, priv_height, pub_height)
    assert len(w) == 8
    assert w[7] == <honest blocks + embedded shares>          # the objects behind w[2]
    assert w[6] - w[7] == <honest pending tip-pool shares>
```

and `test_learned_strategy_attributes_are_plumbed`: construct the miner with attributes `strategy=learned, policy_file=<tmp policy>, alpha=0.45, window_rule=20261020, window_objects=32, give_up_objects=5, weigh=sop, count_own_tip_shares=false` and assert `miner.strategy.name == "learned"` and `miner.strategy.alpha == 0.45`.

- [ ] **Step 6: Run to verify they fail, implement the miner side, run again**

Run: `bash .claude/campaign9/remote_test.sh phantom agents/test_selfish_miner.py -q -k "eighth or plumbed"`
Expected first: 2 failed. Then after implementing: `2 passed`, and `bash .claude/campaign9/remote_test.sh phantom agents/ scripts/test_selfish_matrix.py -q` -> all pass, 7 more than before the task.

- [ ] **Step 7: Commit**

```bash
git add agents/selfish_strategy.py agents/selfish_miner.py agents/test_selfish_strategy.py agents/test_selfish_miner.py
git commit -m "Attacker: learned strategy (policy file, exact-MDP observation from branch weights, sim_stubborn fallback, counters); _branch_weights gains hon_objects"
```

### Task 6: Matrix specs for the ladder

**Files:**
- Create: `test_configs/matrix/sop_v4_learned_6h.yaml`, `test_configs/matrix/sop_v4_learned_72h.yaml`
- Create: `data/sop_rl/README.md`

**Interfaces:**
- Consumes: the attributes of `test_configs/matrix/sop_v4_o5_noown_72h.yaml:22-34`; policy paths `data/sop_rl/policy_noown_a040.json.gz`, `..._a045...`, `..._a048...` (produced in Task 7).
- Produces: cells `share_learned_a045_s1` (6 h spec) and `share_learned_a040_s{1,2}`, `share_learned_a045_s{1,2}`, `share_learned_a048_s{1,2}` (72 h spec), countermeasure `sop2_learned`.

- [ ] **Step 1: Write both specs**

Copy the noown spec; attacker attributes: `strategy: learned`, `policy_file` set per alpha under the alpha axis (`a045: {attacker: {hashrate: 4.5, attributes: {policy_file: data/sop_rl/policy_noown_a045.json.gz, alpha: '0.45'}}, honest: ...}`), keep `window_rule '20261020'`, `window_objects '32'`, `weigh sop`, `use_honest_shares 'true'`, `tip_shares 'true'`, `count_own_tip_shares 'false'`, `give_up_depth '5'`, `give_up_objects '5'`, `reject_aware 'true'`, `embedded_shares 'true'`; countermeasure key `sop2_learned`; `stop_time: 6h` / `72h`; samples s1 (6 h) and s1, s2 (72 h); header comment naming this plan. `data/sop_rl/README.md`: what the files are, how they were trained (the `train` command), and that the `policy` map is a diff against `sim_stubborn`.

- [ ] **Step 2: Verify the dry run shows the per-alpha attribute**

Run: `bash .claude/campaign9/remote_test.sh phantom -q scripts/test_selfish_matrix.py` (existing matrix tests still pass) and then `ssh phantom 'cd ~/monerosim_rl && ~/monerosim/venv/bin/python scripts/selfish_matrix.py test_configs/matrix/sop_v4_learned_72h.yaml --dry-run' | grep -c policy_noown_a0`
Expected: the dry run lists 6 cells and the grep prints `6` (one policy path per cell). If the alpha-axis merge does not carry `attributes`, put `policy_file` into the sample axis instead (one sample per alpha) and re-check.

- [ ] **Step 3: Commit**

```bash
git add test_configs/matrix/sop_v4_learned_6h.yaml test_configs/matrix/sop_v4_learned_72h.yaml data/sop_rl/README.md
git commit -m "SoP RL: matrix specs for the learned attacker (6 h smoke, 72 h at 0.40/0.45/0.48)"
```

### Task 7: The validation ladder and the write-up

**Files:**
- Create: `data/sop_rl/policy_noown_a045.json.gz` (then a040, a048), training logs under `data/sop_rl/logs/`
- Create: `docs/20261026_sop_learned_attacker.md`
- Modify: `.claude/HANDOFF.md`

**Interfaces:**
- Consumes: everything above; `.claude/campaign9/launch_lane.sh`, `score_pool.sh`, `push_files.sh`; lithium's exact solve result in `~/monerosim/mdp_out/solve_a0.45_ignore_c4_4_64_24_24.log`.

Each step runs detached on lithium (after its 4/4 solve ends) or phantom: `ssh <box> 'cd ~/monerosim_rl && setsid nohup ~/monerosim/venv/bin/python scripts/sop_rl.py ... > data/sop_rl/logs/<name>.log 2>&1 < /dev/null &'`, polled from the control box. Record every number in the doc as it lands.

- [ ] **Step 1 (ladder 1, fidelity): record the stubborn baselines through the step API**

Run: `scripts/sop_rl.py eval --policy none --alpha 0.45 --env race --days 2000 --seeds 1 2 3 4 5` (with `--policy none` eval reports `sim_stubborn` only).
Expected: `sim_stubborn` mean within 0.02 of 0.281 (the race model's own stubborn) and recorded; if the two stubborn rules differ by more than 0.02 here, note it in the doc as the first finding (the sims run `sim_stubborn`).

- [ ] **Step 2 (ladder 2, learner correctness on a capped game): exact solve at 3/3/48/20/20 noown, then train on `MdpEnv` at the same caps**

Run on lithium (after the 4/4 solve): `scripts/sop_mdp.py solve --alpha 0.45 --own-pending ignore --a-max 3 --h-max 3 --d-max 48 --p-max 20 --deficit 20 --rho-lo 0.05 --rho-hi 0.6 --rho-tol 1e-4 --verbose` (7,981,414 states; ~1-3 h) -> X.
Then: `scripts/sop_rl.py train --alpha 0.45 --env mdp --a-max 3 --h-max 3 --d-max 48 --p-max 20 --deficit 20 --budget 200000000 --out data/sop_rl/check_mdp_c3_3_48_20_20.json.gz`.
Expected: the search's best share within 0.01 of X. If not after one doubling of the budget, stop; the learner is wrong and Task 3 is revisited. Also compare with the 4/4 solve's optimum: train at `--cap-blocks` is not the same game (p saturation, idle shares), so only record it, do not gate on it.

- [ ] **Step 3 (ladder 3): train the real policy at alpha 0.45, then 0.40 and 0.48**

Run: `scripts/sop_rl.py train --alpha 0.45 --env race --budget 200000000 --out data/sop_rl/policy_noown_a045.json.gz` (24 h cap), then `eval --policy data/sop_rl/policy_noown_a045.json.gz --alpha 0.45 --env race --days 2000 --seeds 1 2 3 4 5`.
Expected: mean share >= sim_stubborn's mean + 0.01; record reveals, mean and max reorg, and the stored-hit fraction next to stubborn's. A reorg profile much deeper than stubborn's (mean > 5 or max > 25) is recorded as a model-exploitation warning before any sim time. Commit the policy file and log (`push_files.sh`). Repeat for 0.40 and 0.48 while the sims of step 4-5 run.

- [ ] **Step 4 (ladder 4, smoke): one 6 h cell**

Pull the commit on a free lane box, then `bash .claude/campaign9/launch_lane.sh <box> sop_v4_learned_6h share_learned_a045_s1`. When it syncs: `grep -c "learned: obs" <run>/attacker.log`, the end-of-run counter line, `reveals=` and `rejected=` from `check_run.py`'s summary.
Expected: reveals > 0 in 6 h; rejected reveals 0-2; stored-hit fraction within 0.1 of the race-model `eval`'s; `clipped` under 1 % of decisions. Any of these off stops the ladder and goes in the doc.

- [ ] **Step 5 (ladder 5): 72 h cells and the write-up**

Launch `share_learned_a045_s1 share_learned_a045_s2` (one box), then a048 and a040 on the next free boxes (`sop_v4_learned_72h`). Score with `bash .claude/campaign9/score_pool.sh sop_v4_learned_72h`.
Expected: sim share within 0.02 of the race-model `eval` prediction for the same policy (stubborn's gap was 0.009 at 0.45); a bigger gap is a fidelity finding that stops further learned cells until explained.
Write `docs/20261026_sop_learned_attacker.md`: the ladder's five outcomes with numbers, the learned curve next to stubborn's and the stock control, the crossing estimate from the race model, the policy's shape in words (count of diff entries by action; where it holds a winning reveal, where it gives up earlier/later than o5), and what remains a lower bound. Update `.claude/HANDOFF.md`.

- [ ] **Step 6: Commit and push**

```bash
bash .claude/campaign9/push_files.sh "SoP RL: learned attacker results (ladder 1-5)" data/sop_rl docs/20261026_sop_learned_attacker.md
```
