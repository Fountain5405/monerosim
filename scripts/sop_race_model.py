#!/usr/bin/env python3
"""scripts/sop_race_model.py: probability/race models for MRL #146 ("Share or
Perish") Security section claims, and a Monte Carlo of our window_stubborn
attacker.

Work objects (blocks or workshares) arrive as a Poisson process with total
rate w/T per second (T = block target, seconds; w = objects per block on
average). Each object independently belongs to the attacker with probability
alpha. Each object is a block with probability 1/w, otherwise a workshare, so
a side mining continuously produces w-1 shares per block on average.

Difficulty is assumed CONSTANT throughout (no DAA response to the attack);
this matches tevador's closed-form treatment in [4], which also assumes a
fixed hashpower share for the duration of the "meta attack".

Model A (tevador's claims, `tevador` subcommand) evaluates three ways of
reading MRL #146's "at least 48 work objects faster than the honest
majority" race, using the classic Nakamoto race (Grunspan & Perez-Marco
regularized-incomplete-beta Theorem 1) and Rucknium's Strategy 2 formula
from [4] (https://github.com/monero-project/research-lab/issues/102,
mrl102_tevador_attack_probability.md in this repo), both in "objects" units
(z = 48) and in "blocks" units (z = 3, since 48 objects = k*w = 3*16 blocks
worth of work on average).

Model B (`sweep`/`deep` subcommands) simulates our window_stubborn attacker
event-by-event: honest/attacker suffixes since the fork, pending-share
counters, give-up/withhold/reveal/hold decisions per the spec. It draws
objects at a fixed total rate (cfg.days of 720 blocks found), but per-day
rates are reported per CANONICAL day (720 canonical blocks). Real Monero, and
the simulator, retarget difficulty on the canonical chain. So when an attack
orphans a fraction f of all blocks, (1 - f)^-1 times as many get found per
day: about 1.45x under SoP at alpha 0.33, where the 240 h sim run found
~1050 blocks a day (2026-10-03). Before that, per-day rates were per
fixed-rate day and too low by that factor. Compare with the simulator per
block found (`reveals_per_1000_found`).

`hunt` (2026-10-19) runs Model B for a deep-reorg hunter, the simulator's
deep_hunt: it withholds until the honest branch holds `release_depth`
blocks, then reveals if heavier, under SoP or stock, giving up d blocks
behind or (SoP) more than N objects behind (tevador's attacker: 5).

`reconcile` (2026-10-19) compares Model B with tevador's simulator
(github.com/tevador/scratchpad, share-or-perish/blockhain-sim.py, commit
59d6094c of 2026-10-17), the source of MRL #146's "about 1 reorg of 10+
blocks per 3 years". It switches his attacker's five differences on one at a
time (SimConfig.equal_start, early_honest_shares with positional_shares,
either_window, tie_win_prob). Its last row keeps every early honest share (a
union), as his UNIQUE_SHARES = False does. SoP's slot rule forbids that (one
share per slot), so that row only checks the mechanics.

`hunt --honest-shares` (2026-10-19) gives the SoP attacker the honest shares the
slot rule lets it use: those found before either side's first block, in its own
first block, and a level restart after a give-up. Under a block-count give-up
(dN) the level restart changes nothing, because give-ups happen at honest blocks,
when no honest share is pending.
"""
from __future__ import annotations

import argparse
import math
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

T_BLOCK_S = 120.0       # Monero target block time, seconds
W_DEFAULT = 16          # work objects per block window (spec default)
K_DEFAULT = 3           # confirmation depth in blocks (spec default)
SECONDS_PER_DAY = 86400.0


def objects_per_day(w: int = W_DEFAULT, t_block: float = T_BLOCK_S) -> float:
    """Total (attacker + honest) work objects arriving per day."""
    return SECONDS_PER_DAY * w / t_block


# ---------------------------------------------------------------------------
# Regularized incomplete beta function (stdlib-only; no scipy/numpy needed).
# ---------------------------------------------------------------------------

def _betacf(x: float, a: float, b: float) -> float:
    """Continued fraction for the incomplete beta function (Numerical
    Recipes, betacf), used by reg_incomplete_beta."""
    MAXIT, EPS, FPMIN = 200, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def reg_incomplete_beta(x: float, a: float, b: float) -> float:
    """I_x(a, b), the regularized incomplete beta function, 0 <= x <= 1."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_beta = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
               + a * math.log(x) + b * math.log(1.0 - x))
    front = math.exp(ln_beta)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(x, a, b) / a
    return 1.0 - front * _betacf(1.0 - x, b, a) / b


def binom_sf_ge(n: int, k: int, p: float) -> float:
    """P(Binomial(n, p) >= k), exact via math.comb (k, n small in our use)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
               for i in range(k, n + 1))


# ---------------------------------------------------------------------------
# Model A: tevador's claims, three readings.
# ---------------------------------------------------------------------------

@dataclass
class RaceResult:
    name: str
    p_success: float
    expected_cycle_objects: float
    expected_days_between_successes: float
    mean_reorg_blocks: Optional[float] = None


def simulate_race_to_k(alpha: float, K: int, rng: random.Random):
    """Draw a Bernoulli(alpha) sequence and stop as soon as either count
    hits K. Returns (attacker_won, length_objects, hon_count_at_stop)."""
    a = h = 0
    n = 0
    while a < K and h < K:
        n += 1
        if rng.random() < alpha:
            a += 1
        else:
            h += 1
    return (a == K, n, h)


def a1_race_to_k(alpha: float, K: int, w: int = W_DEFAULT, trials: int = 100000,
                  seed: int = 1) -> RaceResult:
    """Classic Nakamoto race to K: attacker succeeds iff it reaches K objects
    strictly before the honest side does.
    Exact success probability (Grunspan & Perez-Marco style reflection):
    P = P(Binomial(2K-1, alpha) >= K). Expected cycle length (objects) and
    mean reorg depth (honest objects accumulated at the moment the attacker
    hits K, i.e. the reorg depth) are estimated by Monte Carlo of the actual
    stopping race, since the closed form for the stopping time is not as
    simple as the win probability."""
    n = 2 * K - 1
    p = binom_sf_ge(n, K, alpha)
    rng = random.Random(seed)
    lengths = []
    hon_at_success = []
    wins = 0
    for _ in range(trials):
        won, length, hon = simulate_race_to_k(alpha, K, rng)
        lengths.append(length)
        if won:
            wins += 1
            hon_at_success.append(hon)
    exp_cycle = sum(lengths) / len(lengths)
    # Rate from the EXACT per-cycle probability: at alpha = 0.33 a 1e5-trial
    # Monte Carlo sees ~31 wins (+-18 %), too few to set the rate.
    days_between = (exp_cycle / p) / objects_per_day() if p > 0 else math.inf
    r = RaceResult("A1 race-to-K", p, exp_cycle, days_between)
    r.mean_reorg_blocks = exact_reorg_blocks_given_win(alpha, K, w)
    return r


def exact_reorg_blocks_given_win(alpha: float, K: int, w: int = W_DEFAULT) -> float:
    """Expected honest blocks replaced when the attacker wins the race to K.
    The attacker wins with the honest side at j < K objects with probability
    C(K-1+j, j) alpha^K (1-alpha)^j, and each honest object is a block with
    probability 1/w, so E[blocks | win] = E[j | win] / w. Computed in log
    space; exact up to float rounding."""
    logs = [math.lgamma(K + j) - math.lgamma(j + 1) - math.lgamma(K) + j * math.log1p(-alpha)
            for j in range(K)]
    top = max(logs)
    weights = [math.exp(v - top) for v in logs]
    return sum(j * t for j, t in enumerate(weights)) / sum(weights) / w


def a2_strategy2_objects(alpha: float, K: int) -> RaceResult:
    """Rucknium Strategy 2 re-expressed directly in objects: the cycle ends
    when the honest side reaches K objects; attacker succeeds iff it then has
    >= K+1 objects (strictly longer). Exact:
    P = P(Binomial(2K, alpha) >= K+1)."""
    n = 2 * K
    p = binom_sf_ge(n, K + 1, alpha)
    exp_cycle = K / (1 - alpha) if alpha < 1 else math.inf  # objects to get K honest
    days_between = (exp_cycle / p) / objects_per_day() if p > 0 else math.inf
    return RaceResult("A2 strategy-2 (objects)", p, exp_cycle, days_between)


def a3_strategy2_formula(alpha: float, z: int, objects_per_z_unit: float = 1.0
                          ) -> RaceResult:
    """Rucknium's own Strategy-2 formula from [4] (Section "Strategy 2"):
    Pr(x >= z) = I_alpha(z, z) per attack attempt, where z is the stopping
    depth (in whatever unit the caller passes: objects or blocks). Expected
    cycle length (units of the same z-quantum) is z + (1-alpha)/alpha, per
    [4]'s w formula (one "meta attack" attempt = one full cycle)."""
    p = reg_incomplete_beta(alpha, z, z)
    cycle_units = z + (1 - alpha) / alpha if alpha > 0 else math.inf
    cycle_objects = cycle_units * objects_per_z_unit
    days_between = (cycle_objects / p) / objects_per_day() if p > 0 else math.inf
    return RaceResult(f"A3 Rucknium-formula (z={z})", p, cycle_objects, days_between)


def run_model_a(alpha: float = 0.33, w: int = W_DEFAULT, k: int = K_DEFAULT,
                 seed: int = 1) -> List[RaceResult]:
    K = k * w
    a1 = a1_race_to_k(alpha, K, w=w, seed=seed)
    # A2/A3 do not have their own closed-form reorg-depth result (they model
    # a different stopping rule than A1's "race to K"); report A1's
    # Monte-Carlo reorg depth alongside them for comparison, noted as such.
    results = [
        a1,
        a2_strategy2_objects(alpha, K),
        a3_strategy2_formula(alpha, K, objects_per_z_unit=1.0),
        a3_strategy2_formula(alpha, k, objects_per_z_unit=float(w)),
    ]
    for r in results[1:]:
        r.mean_reorg_blocks = a1.mean_reorg_blocks
    return results


# ---------------------------------------------------------------------------
# Model B: window_stubborn event-by-event simulation.
# ---------------------------------------------------------------------------

@dataclass
class SimConfig:
    alpha: float
    d: int
    rule: str              # "sop" or "stock"
    attacker_embeds: bool
    days: float
    seed: int
    w: int = W_DEFAULT
    K_objects: int = K_DEFAULT * W_DEFAULT
    # Variants for the 2026-10-08 decomposition of the reveal rate
    # (results doc 4.1). Defaults reproduce Model B exactly.
    count_honest_pending: bool = False   # honest shares found but in no block count as honest weight
    give_up_objects: int = -1            # >= 0: give up once honest is more than this many objects
                                         # ahead (counted since the fork), instead of d blocks behind
    release_depth: int = 0               # >= 1: reveal only once the honest branch holds this many
                                         # blocks (deep_hunt, 2026-10-19); 0 = at the first chance
    # tevador's attacker (blockhain-sim.py, 2026-10-17), for `reconcile`. Defaults reproduce Model B.
    equal_start: bool = False            # after a give-up the attacker adopts honest's pending shares
    early_honest_shares: bool = False    # honest shares found before either side has a block since the
                                         # fork sit on the fork point, so the attacker's first block embeds them too
    either_window: bool = False          # SoP window ends once EITHER branch holds (K - w) objects past
                                         # its first block, not once the attacker's holds K
    tie_win_prob: float = 0.0            # chance the attacker wins an exact weight tie; a lost tie ends
                                         # the attack (tevador: GAMMA = 0.5)
    positional_shares: bool = False      # SoP's slot rule, as tevador's UNIQUE_SHARES: a share's ID is its
                                         # slot (its position in the finder's pending set), so an early honest
                                         # share adds to the attacker only if it lacks that slot (needs equal_start)
    count_attacker_pending: bool = False  # MRL #146 2026-10-20: the attacker's own shares on its
                                          # tip count for it under the objective score (it publishes
                                          # them at the reveal)
    cap_blocks: int = 0                   # scripts/sop_mdp.py truncation (2026-10-25): once either
                                          # side holds this many blocks since the fork the attacker is
                                          # forced to act: publish if honest has none, reveal if the
                                          # network accepts, else give up. 0 = no cap (Model B).
    d_cap: int = 0                        # SopEnv far truncation for a learned policy (2026-10-25):
                                          # |attacker weight - honest weight| >= d_cap makes HOLD
                                          # illegal. 0 = none. (With equal_start the old loop reaches
                                          # |D| > 200 in 60 d, so the default must stay 0.)
    deficit_cap: int = 0                  # same, for honest objects ahead since the fork. 0 = none.


# MRL #146 rule versions for the SoP rule (the stock rule ignores them).
RULE_PRESETS = {
    "20261015": {},
    "20261020": {"either_window": True, "count_honest_pending": True,
                 "count_attacker_pending": True},
    # 20261020 without count_attacker_pending: the attacker does NOT count its
    # own tip shares in the reveal test (under "fork choice runs only on a new
    # block or chain" they reach the network only after the switch). Matches
    # the count_own_tip_shares "false" attacker (2026-10-22 follow-up cell).
    "20261020_noown": {"either_window": True, "count_honest_pending": True},
}


@dataclass
class SimStats:
    reveals: int = 0
    reorg_depths: List[int] = field(default_factory=list)  # honest blocks orphaned, per reveal
    att_final_blocks: int = 0
    hon_final_blocks: int = 0
    att_orphaned_blocks: int = 0
    sim_days: float = 0.0   # fixed-rate days: the object budget (720 blocks found per day)

    @property
    def canonical_days(self) -> float:
        """Days of a chain retargeting on its canonical blocks: 720 per day."""
        return (self.att_final_blocks + self.hon_final_blocks) * T_BLOCK_S / SECONDS_PER_DAY

    @property
    def blocks_found(self) -> int:
        """Every block found and settled: final, plus orphaned on both sides
        (in-flight blocks at the end are dropped, as in the accounting)."""
        return (self.att_final_blocks + self.hon_final_blocks
                + self.att_orphaned_blocks + sum(self.reorg_depths))

    @property
    def reveals_per_day(self) -> float:
        return self.reveals / self.canonical_days if self.canonical_days else 0.0

    @property
    def reveals_per_1000_found(self) -> float:
        return 1000.0 * self.reveals / self.blocks_found if self.blocks_found else 0.0

    @property
    def mean_reorg_depth(self) -> float:
        return sum(self.reorg_depths) / len(self.reorg_depths) if self.reorg_depths else 0.0

    @property
    def max_reorg_depth(self) -> int:
        return max(self.reorg_depths) if self.reorg_depths else 0

    def count_ge(self, n: int) -> int:
        return sum(1 for d in self.reorg_depths if d >= n)

    @property
    def rate_ge10_per_year(self) -> float:
        per_day = self.count_ge(10) / self.canonical_days if self.canonical_days else 0.0
        return per_day * 365.25

    @property
    def attacker_revenue_share(self) -> float:
        total = self.att_final_blocks + self.hon_final_blocks
        return self.att_final_blocks / total if total else 0.0

    @property
    def attacker_orphan_fraction(self) -> float:
        total_att = self.att_final_blocks + self.att_orphaned_blocks
        return self.att_orphaned_blocks / total_att if total_att else 0.0


# ---------------------------------------------------------------------------
# Step API (2026-10-25): the Model B loop as an environment an attacker policy
# drives one object at a time. simulate() below runs it with stubborn_policy
# and reproduces the pre-refactor loop bit for bit (scripts/test_sop_race_model
# PINNED). Used by scripts/sop_rl.py to train a policy; design in
# docs/superpowers/specs/2026-10-25-sop-rl-attacker-design.md.
# ---------------------------------------------------------------------------

HOLD, PUBLISH, REVEAL, GIVE_UP = 0, 1, 2, 3        # same values as scripts/sop_mdp.py
ACTION_NAMES = ["hold", "publish", "reveal", "give_up"]
WINDOW_OBS = K_DEFAULT * W_DEFAULT - W_DEFAULT     # 32: the observation's window-counter cap
FAR_CAP = 200        # the d_cap / deficit_cap a learned policy's environment uses (sop_rl.race_env)
Obs = Tuple[int, int, int, int, int, int, int]     # a, D, xa, pa, h, xh, ph (scripts/sop_mdp.py State)


def observation(att_blocks: List[int], hon_blocks: List[int], att_pending: int, hon_pending: int,
                window: int = WINDOW_OBS) -> Obs:
    """The exact-MDP state of a fork: blocks per side, weight difference in
    objects (blocks plus embedded shares; honest pending NOT included), the
    window counters (objects a branch holds past its FIRST block, capped at
    the window ((K - 1) * w, 32 by default) and both collapsed to it once
    either passes) and the pending shares."""
    a, h = len(att_blocks), len(hon_blocks)
    d = sum(1 + n for n in att_blocks) - sum(1 + m for m in hon_blocks)
    xa = min(sum(1 + n for n in att_blocks[1:]), window)
    xh = min(sum(1 + m for m in hon_blocks[1:]), window)
    if xa >= window or xh >= window:
        xa = xh = window
    return (a, d, xa, att_pending, h, xh, hon_pending)


class SopEnv:
    """Model B as reset()/step(): after every object the attacker chooses
    hold, publish (its blocks become final; only with no honest block),
    reveal (only when the network accepts) or give up. Nothing is forced
    except the truncations: cfg.cap_blocks and the far caps cfg.d_cap /
    cfg.deficit_cap make HOLD illegal (GIVE_UP stays legal everywhere;
    the old loop gives up on the objects deficit even at a cap). The objects give-up (give_up_objects) is
    NOT an environment rule here: it is part of stubborn_policy.

    Acceptance (and the tie draw of tie_win_prob) is evaluated lazily, at
    most once per decision point and only when asked for (REVEAL legality),
    so the RNG stream equals the old loop's as long as the policy asks
    exactly where the old loop decided (stubborn_policy does)."""

    def __init__(self, cfg: SimConfig):
        if cfg.positional_shares and not cfg.equal_start:
            raise ValueError("positional_shares needs equal_start (his share IDs assume a level start)")
        self.cfg = cfg
        self.n_objects = int(cfg.days * SECONDS_PER_DAY * (cfg.w / T_BLOCK_S))
        self.window_obs = cfg.K_objects - cfg.w     # the observation's window cap: (K - 1) * w objects
        self.obj_mode = cfg.give_up_objects >= 0
        self.rng = random.Random(cfg.seed)
        self.stats = SimStats(sim_days=cfg.days)
        self.att_blocks: List[int] = []
        self.hon_blocks: List[int] = []
        self.att_pending = 0
        self.hon_pending = 0
        self.att_fork = self.hon_fork = 0
        # running sums so every decision is O(1): objects per branch (blocks +
        # embedded shares) and objects past each branch's first block
        self.att_w = self.hon_w = self.att_x = self.hon_x = 0
        self.objects = 0
        self.done = True
        self.last_is_block = False
        self.last_is_attacker = False
        self.tie_lost = False
        self._acc: Optional[bool] = None

    # -- lifecycle -----------------------------------------------------------
    def reset(self, seed: int) -> Obs:
        self.rng = random.Random(seed)
        self.stats = SimStats(sim_days=self.cfg.days)
        self.att_blocks, self.hon_blocks = [], []
        self.att_pending = self.hon_pending = 0
        self.att_fork = self.hon_fork = 0
        self.att_w = self.hon_w = self.att_x = self.hon_x = 0
        self.objects = 0
        self.done = self.n_objects == 0
        if not self.done:
            self._draw()
        return self.obs()

    def obs(self) -> Obs:
        W = self.window_obs
        xa, xh = min(self.att_x, W), min(self.hon_x, W)
        if xa >= W or xh >= W:
            xa = xh = W
        return (len(self.att_blocks), self.att_w - self.hon_w, xa, self.att_pending,
                len(self.hon_blocks), xh, self.hon_pending)

    # -- the decision point --------------------------------------------------
    def _a_h(self) -> Tuple[int, int]:
        return len(self.att_blocks), len(self.hon_blocks)

    def forced(self) -> bool:
        """HOLD is illegal here: at cfg.cap_blocks or at a far cap."""
        a, h = self._a_h()
        cfg = self.cfg
        if cfg.cap_blocks > 0 and (a >= cfg.cap_blocks or h >= cfg.cap_blocks):
            return True
        if cfg.d_cap > 0 and abs(self.att_w - self.hon_w) >= cfg.d_cap:
            return True
        return cfg.deficit_cap > 0 and (self.hon_fork - self.att_fork) > cfg.deficit_cap

    def accepted(self) -> bool:
        """Would the network accept a reveal now (past the window and the
        attacker's weight wins)? Evaluated once per decision point; a tie
        (tie_win_prob > 0) draws the RNG here and sets tie_lost."""
        if self._acc is not None:
            return self._acc
        cfg = self.cfg
        a, h = self._a_h()
        if cfg.rule == "sop":
            att_objects = self.att_w
            att_weight = att_objects
            hon_weight = self.hon_w
            if cfg.count_honest_pending:
                hon_weight += self.hon_pending
            K = cfg.K_objects
        else:  # stock
            att_objects = a
            att_weight = a
            hon_weight = h
            K = 0
        past_window = att_objects >= K
        if cfg.either_window and cfg.rule == "sop":
            past_window = max(self.att_x, self.hon_x) >= cfg.K_objects - cfg.w
        if cfg.count_attacker_pending and cfg.rule == "sop" and past_window:
            att_weight += self.att_pending
        wins = att_weight > hon_weight
        if past_window and not wins and att_weight == hon_weight and cfg.tie_win_prob > 0:
            wins = self.rng.random() < cfg.tie_win_prob
            self.tie_lost = not wins
        self._acc = past_window and wins
        return self._acc

    def legal(self) -> Tuple[bool, bool, bool, bool]:
        a, h = self._a_h()
        forced = self.forced()
        return (not forced,
                a >= 1 and h == 0,
                h >= 1 and self.accepted(),     # a == 0 can win under count_attacker_pending + equal_start
                True)

    def _check(self, action: int) -> None:
        a, h = self._a_h()
        if action == HOLD:
            ok = not self.forced()
        elif action == PUBLISH:
            ok = a >= 1 and h == 0
        elif action == REVEAL:
            ok = h >= 1 and self.accepted()
        elif action == GIVE_UP:
            ok = True
        else:
            raise ValueError(f"unknown action {action}")
        if not ok:
            raise ValueError(f"illegal action {ACTION_NAMES[action]} at a={a} h={h} obs={self.obs()}")

    # -- settlements (verbatim from the old loop) ----------------------------
    def _reset_fork(self) -> None:
        self.hon_blocks.clear()
        self.att_blocks.clear()
        self.att_w = self.hon_w = self.att_x = self.hon_x = 0

    def _give_up(self) -> Tuple[int, int]:
        a, h = self._a_h()
        self.stats.hon_final_blocks += h
        self.stats.att_orphaned_blocks += a
        self._reset_fork()
        self.att_pending = self.hon_pending if self.cfg.equal_start else 0
        self.att_fork, self.hon_fork = self.att_pending, self.hon_pending
        return 0, h

    def _reveal(self) -> Tuple[int, int]:
        a, h = self._a_h()
        self.stats.reveals += 1
        self.stats.reorg_depths.append(h)
        self.stats.att_final_blocks += a
        self._reset_fork()
        self.hon_pending = 0
        self.att_fork, self.hon_fork = self.att_pending, 0
        return a, 0

    def _publish(self) -> Tuple[int, int]:
        a, _ = self._a_h()
        self.stats.att_final_blocks += a
        self._reset_fork()
        self.att_fork, self.hon_fork = self.att_pending, self.hon_pending
        return a, 0

    def step(self, action: int) -> Tuple[Obs, int, int]:
        if self.done:
            raise ValueError("episode is over; call reset()")
        self._check(action)
        fa, fh = self._apply(action)
        return self.obs(), fa, fh

    def _apply(self, action: int) -> Tuple[int, int]:
        """step() without the legality check and the observation: the fast
        path simulate() uses with stubborn_policy (legal by construction)."""
        if action == HOLD:
            fa, fh = 0, 0
        elif action == GIVE_UP:
            fa, fh = self._give_up()
        elif action == REVEAL:
            fa, fh = self._reveal()
        else:
            fa, fh = self._publish()
        if self.objects < self.n_objects:
            self._draw()
        else:
            self.done = True
        return fa, fh

    # -- the per-object draw (verbatim from the old loop) ---------------------
    def _draw(self) -> None:
        cfg = self.cfg
        is_attacker = self.rng.random() < cfg.alpha
        is_block = self.rng.random() < (1.0 / cfg.w)
        self.objects += 1
        self.last_is_block, self.last_is_attacker = is_block, is_attacker
        self._acc = None
        self.tie_lost = False
        if self.obj_mode:
            if is_attacker:
                self.att_fork += 1
            else:
                self.hon_fork += 1
        if not is_block:
            if is_attacker:
                self.att_pending += 1
            else:
                # tevador: the attacker embeds it too; with positional IDs only if it
                # lacks this share's position (hon_pending before the increment)
                if cfg.early_honest_shares and not self.att_blocks and not self.hon_blocks \
                        and (not cfg.positional_shares or self.hon_pending >= self.att_pending):
                    self.att_pending += 1
                    self.att_fork += 1
                self.hon_pending += 1
            return
        if is_attacker:
            embed = self.att_pending if cfg.attacker_embeds else 0
            if self.att_blocks:
                self.att_x += 1 + embed
            self.att_blocks.append(embed)
            self.att_w += 1 + embed
            self.att_pending = 0
        else:
            if self.hon_blocks:
                self.hon_x += 1 + self.hon_pending
            self.hon_blocks.append(self.hon_pending)
            self.hon_w += 1 + self.hon_pending
            self.hon_pending = 0


def stubborn_policy(env: SopEnv) -> int:
    """The old loop's decisions, as a policy over SopEnv: the objects give-up
    at every event (also with no block held, where it drops the attacker's
    pending shares), the d-mode give-up after blocks, withhold while there is
    no honest block (publish only when cap_blocks forces it), release_depth,
    reveal when the network accepts, a lost tie ends the attack, and at
    cap_blocks give up when the network would not accept."""
    cfg = env.cfg
    a, h = len(env.att_blocks), len(env.hon_blocks)
    if not env.last_is_block:
        if env.obj_mode and env.hon_fork - env.att_fork > cfg.give_up_objects:
            return GIVE_UP
        return HOLD
    if env.obj_mode:
        give_up = env.hon_fork - env.att_fork > cfg.give_up_objects
    else:
        give_up = (a == 0 and h > 0) or (h - a >= cfg.d)
    if give_up:
        return GIVE_UP
    forced = cfg.cap_blocks > 0 and (a >= cfg.cap_blocks or h >= cfg.cap_blocks)
    if h == 0:
        return PUBLISH if forced else HOLD
    if h < cfg.release_depth and not forced:
        return HOLD
    accepted = env.accepted()
    if env.tie_lost:
        return GIVE_UP
    if accepted:
        return REVEAL
    if forced:
        return GIVE_UP
    return HOLD


def simulate(cfg: SimConfig) -> SimStats:
    env = SopEnv(cfg)
    env.reset(cfg.seed)
    while not env.done:
        env._apply(stubborn_policy(env))
    # end of run: whatever is left in-flight is neither final nor orphaned;
    # it is dropped from the accounting (boundary effect, negligible for
    # long enough runs).
    return env.stats


def invariant_ok(stats: SimStats, total_att_blocks: int, total_hon_blocks: int) -> bool:
    return (stats.att_final_blocks + stats.att_orphaned_blocks <= total_att_blocks
            and stats.hon_final_blocks <= total_hon_blocks)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def days_to_even_odds(mean_days_between: float) -> float:
    """Horizon at which at least one success has probability 1/2, for
    successes arriving as a Poisson process: ln 2 x the mean interval. This
    is the quantity Rucknium's Strategy 2 reports ("possess the hashpower for
    N hours to achieve a 50 percent attack success probability"), which
    tevador cites as "on average once per 10 days"."""
    return math.log(2) * mean_days_between


def _print_tevador(alpha: float, w: int, k: int) -> None:
    results = run_model_a(alpha=alpha, w=w, k=k)
    print(f"# Model A: tevador's claims at alpha={alpha}, w={w}, k={k}, K={k*w} objects\n")
    print("tevador's claims: P(success) < 0.06%, ~once per 10 days, ~3-block reorg\n")
    print("| variant | P(success) | mean days between successes | days to a 50% chance | mean reorg (honest blocks) |")
    print("|:--|--:|--:|--:|--:|")
    for r in results:
        print(f"| {r.name} | {r.p_success*100:.5f}% | {r.expected_days_between_successes:.3f} "
              f"| {days_to_even_odds(r.expected_days_between_successes):.3f} "
              f"| {r.mean_reorg_blocks:.3f} |")
    print()
    print("A3 (z=48) is Rucknium's Strategy 2 counted in work objects: attempts per duration")
    print("w = d / (z + (1-q)/q), success per attempt I_q(z, z). Its 50%-chance horizon is the")
    print("'once per 10 days'; the mean interval between successes is ln 2 larger.")


def _sweep(days: float, seed: int, alphas: Optional[List[float]] = None,
           ds: Optional[List[int]] = None, honest_shares: bool = False,
           rule_version: str = "20261015") -> None:
    alphas = alphas or [0.30, 0.33, 0.40, 0.45]
    ds = ds or [1, 2, 3]
    variants = [("sop", True, False), ("sop", False, False), ("stock", False, False)]
    if honest_shares:
        # The window_stubborn attacker using the honest shares the slot rule
        # lets it use (2026-10-20). Under the d give-up, equal_start changes
        # nothing (give-ups happen at honest blocks, when no honest share is
        # pending); positional_shares needs it set.
        variants.append(("sop", True, True))
    print(f"# Model B sweep: days={days} (fixed-rate), seed={seed}")
    print(f"# rule version: {rule_version}")
    if honest_shares:
        print("# 'True + honest shares': the SoP attacker's first block after a fork also embeds the "
              "honest shares found on the fork point, one per slot.")
    print("# Per-day and per-year rates are per CANONICAL day (difficulty retargets on the\n"
          "# canonical chain); 'canon days' shows how many of those the run covered.\n")
    print("| alpha | d | rule | embeds | reveals | canon days | reveals/day | per 1000 found | "
          "mean reorg | max reorg | #>=3 | #>=10 | rate>=10/yr | revenue share | orphan frac |")
    print("|--:|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for alpha in alphas:
        for d in ds:
            for rule, embeds, slot in variants:
                cfg = SimConfig(alpha=alpha, d=d, rule=rule, attacker_embeds=embeds,
                                 days=days, seed=seed, equal_start=slot,
                                 early_honest_shares=slot, positional_shares=slot,
                                 **(RULE_PRESETS[rule_version] if rule == "sop" else {}))
                s = simulate(cfg)
                label = "True + honest shares" if slot else embeds
                print(f"| {alpha} | {d} | {rule} | {label} | {s.reveals} | "
                      f"{s.canonical_days:.1f} | {s.reveals_per_day:.4f} | "
                      f"{s.reveals_per_1000_found:.3f} | {s.mean_reorg_depth:.3f} | "
                      f"{s.max_reorg_depth} | {s.count_ge(3)} | {s.count_ge(10)} | "
                      f"{s.rate_ge10_per_year:.4f} | {s.attacker_revenue_share:.4f} | "
                      f"{s.attacker_orphan_fraction:.4f} |")


def _deep(years: float, seed: int) -> None:
    alpha = 0.33
    ds = [2, 3, 5, 10, 20]
    days = years * 365.25
    print(f"# Model B deep-reorg estimate: alpha={alpha}, years={years} "
          f"({days:.1f} fixed-rate days), rule=sop, attacker_embeds=True")
    print("# Rates are per canonical year (difficulty retargets on the canonical chain).\n")
    print("tevador's claim: about 1 reorg of 10+ blocks per 3 years of stubborn mining.\n")
    print("| d | canon years | #>=10 reorgs | rate>=10/yr | years/reorg |")
    print("|--:|--:|--:|--:|--:|")
    for d in ds:
        cfg = SimConfig(alpha=alpha, d=d, rule="sop", attacker_embeds=True,
                         days=days, seed=seed)
        s = simulate(cfg)
        n10 = s.count_ge(10)
        rate = s.rate_ge10_per_year
        years_per = (1.0 / rate) if rate > 0 else math.inf
        print(f"| {d} | {s.canonical_days / 365.25:.2f} | {n10} | {rate:.4f} | {years_per:.3f} |")


def _reconcile(alpha: float, days: float, seed: int, give_up_objects: int, release_depth: int) -> None:
    steps = [
        (f"Model B (o{give_up_objects}, release_depth {release_depth})", {}),
        ("+ equal start after a give-up", {"equal_start": True}),
        ("+ embeds early honest shares, positional IDs",
         {"early_honest_shares": True, "positional_shares": True}),
        ("+ window on either branch", {"either_window": True}),
        ("+ wins half of exact ties (= tevador)", {"tie_win_prob": 0.5}),
        ("union of early honest shares (his UNIQUE_SHARES = False; the slot rule forbids it)",
         {"positional_shares": False}),
    ]
    print(f"# Model B against tevador's simulator: alpha={alpha:.4f}, SoP, attacker embeds, "
          f"days={days} (fixed-rate), seed={seed}")
    print("# Switches are cumulative. Rates per CANONICAL day/year.\n")
    print("| attacker | reveals | canon days | #>=10 | days per | per year |")
    print("|:--|--:|--:|--:|--:|--:|")
    acc = {}
    for label, extra in steps:
        acc.update(extra)
        s = simulate(SimConfig(alpha=alpha, d=1, rule="sop", attacker_embeds=True, days=days, seed=seed,
                               give_up_objects=give_up_objects, release_depth=release_depth, **acc))
        n10 = s.count_ge(10)
        per_day = n10 / s.canonical_days if s.canonical_days else 0.0
        days_per = (1.0 / per_day) if per_day > 0 else math.inf
        print(f"| {label} | {s.reveals} | {s.canonical_days:.0f} | {n10} | {days_per:.0f} | "
              f"{per_day * 365.25:.3f} |")


def _give_up_token(s: str) -> str:
    """`hunt` give-up: "dN" (honest N blocks ahead, N >= 1) or "oN" (honest
    more than N work objects ahead since the fork)."""
    if len(s) < 2 or s[0] not in "do" or not s[1:].isdigit() or (s[0] == "d" and int(s[1:]) < 1):
        raise argparse.ArgumentTypeError(f"give-up must be dN (N >= 1) or oN, got {s!r}")
    return s


def _hunt(alphas: List[float], rules: List[str], give_ups: List[str], release_depth: int,
          days: float, seed: int, honest_shares: bool = False,
          rule_version: str = "20261015", cap_blocks: int = 0) -> None:
    print(f"# Model B deep-reorg hunter: release_depth={release_depth}, days={days} "
          f"(fixed-rate), seed={seed}" + (f", cap_blocks={cap_blocks}" if cap_blocks else ""))
    print(f"# rule version: {rule_version}")
    if honest_shares:
        print("# SoP attacker uses honest shares as the slot rule allows: its first block embeds the "
              "honest shares found before either side's first block, and it restarts level after a give-up.")
    print("# Every reveal orphans >= release_depth honest blocks. Rates are per CANONICAL "
          "day/year; the object give-up (oN) is SoP-only.\n")
    print("| alpha | rule | give-up | reveals | canon days | #>=10 | per day | per year | "
          "days per | mean reorg | max reorg | revenue share | orphan frac |")
    print("|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for alpha in alphas:
        for rule in rules:
            for g in give_ups:
                kind, n = g[0], int(g[1:])
                if kind == "o" and rule != "sop":
                    continue
                slot = honest_shares and rule == "sop"
                cfg = SimConfig(alpha=alpha, d=n if kind == "d" else 1, rule=rule,
                                attacker_embeds=(rule == "sop"), days=days, seed=seed,
                                give_up_objects=n if kind == "o" else -1,
                                release_depth=release_depth, equal_start=slot,
                                early_honest_shares=slot, positional_shares=slot,
                                cap_blocks=cap_blocks,
                                **(RULE_PRESETS[rule_version] if rule == "sop" else {}))
                s = simulate(cfg)
                n10 = s.count_ge(10)
                per_day = n10 / s.canonical_days if s.canonical_days else 0.0
                days_per = (1.0 / per_day) if per_day > 0 else math.inf
                print(f"| {alpha} | {rule} | {g} | {s.reveals} | {s.canonical_days:.1f} | {n10} | "
                      f"{per_day:.4f} | {per_day * 365.25:.3f} | {days_per:.2f} | "
                      f"{s.mean_reorg_depth:.2f} | {s.max_reorg_depth} | "
                      f"{s.attacker_revenue_share:.4f} | {s.attacker_orphan_fraction:.4f} |")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_tev = sub.add_parser("tevador", help="Model A: tevador's claims at alpha=0.33")
    p_tev.add_argument("--alpha", type=float, default=0.33)
    p_tev.add_argument("--w", type=int, default=W_DEFAULT)
    p_tev.add_argument("--k", type=int, default=K_DEFAULT)

    p_sw = sub.add_parser("sweep", help="Model B sweep over alpha/d/rule")
    p_sw.add_argument("--days", type=float, default=2000.0)
    p_sw.add_argument("--seed", type=int, default=1)
    p_sw.add_argument("--alphas", type=float, nargs="+", default=None,
                      help="default 0.30 0.33 0.40 0.45")
    p_sw.add_argument("--ds", type=int, nargs="+", default=None, help="give-up depths, default 1 2 3")
    p_sw.add_argument("--honest-shares", action="store_true",
                      help="add a row per cell for the SoP attacker that embeds the honest shares the "
                           "slot rule lets it use (SimConfig.equal_start, early_honest_shares, "
                           "positional_shares)")

    p_sw.add_argument("--rule-version", choices=list(RULE_PRESETS), default="20261015")

    p_deep = sub.add_parser("deep", help="Model B deep-reorg (10+) rate estimate")
    p_deep.add_argument("--years", type=float, default=3.0)
    p_deep.add_argument("--seed", type=int, default=1)

    p_hunt = sub.add_parser("hunt", help="Model B deep-reorg hunter (deep_hunt), SoP and stock")
    p_hunt.add_argument("--alphas", type=float, nargs="+", default=[0.33, 0.40, 0.45])
    p_hunt.add_argument("--rules", nargs="+", choices=["sop", "stock"], default=["sop", "stock"])
    p_hunt.add_argument("--give-ups", nargs="+", type=_give_up_token, default=["d1", "d2", "o5"])
    p_hunt.add_argument("--release-depth", type=int, default=10)
    p_hunt.add_argument("--days", type=float, default=2000.0)
    p_hunt.add_argument("--seed", type=int, default=1)
    p_hunt.add_argument("--honest-shares", action="store_true",
                        help="SoP attacker embeds the honest shares the slot rule lets it use "
                             "(SimConfig.equal_start, early_honest_shares, positional_shares)")

    p_hunt.add_argument("--rule-version", choices=list(RULE_PRESETS), default="20261015")
    p_hunt.add_argument("--cap-blocks", type=int, default=0,
                        help="sop_mdp.py truncation: forced publish/reveal/give-up once a side holds "
                             "this many blocks since the fork (0 = none)")

    p_rec = sub.add_parser("reconcile", help="Model B against tevador's deep-reorg simulator")
    p_rec.add_argument("--alpha", type=float, default=1 / 3)   # his ATTACK_HR 3 of 9
    p_rec.add_argument("--give-up-objects", type=int, default=5)   # his STUBBORNNESS
    p_rec.add_argument("--release-depth", type=int, default=10)    # his MIN_REORG_DEPTH
    p_rec.add_argument("--days", type=float, default=20000.0)
    p_rec.add_argument("--seed", type=int, default=1)

    args = parser.parse_args(argv)
    t0 = time.time()
    if args.cmd == "tevador":
        _print_tevador(args.alpha, args.w, args.k)
    elif args.cmd == "sweep":
        _sweep(args.days, args.seed, args.alphas, args.ds, args.honest_shares, args.rule_version)
    elif args.cmd == "deep":
        _deep(args.years, args.seed)
    elif args.cmd == "reconcile":
        _reconcile(args.alpha, args.days, args.seed, args.give_up_objects, args.release_depth)
    elif args.cmd == "hunt":
        _hunt(args.alphas, args.rules, args.give_ups, args.release_depth, args.days, args.seed,
              args.honest_shares, args.rule_version, cap_blocks=args.cap_blocks)
    print(f"\n(elapsed: {time.time() - t0:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
