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
counters, give-up/withhold/reveal/hold decisions per the spec.
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


@dataclass
class SimStats:
    reveals: int = 0
    reorg_depths: List[int] = field(default_factory=list)  # honest blocks orphaned, per reveal
    att_final_blocks: int = 0
    hon_final_blocks: int = 0
    att_orphaned_blocks: int = 0
    sim_days: float = 0.0

    @property
    def reveals_per_day(self) -> float:
        return self.reveals / self.sim_days if self.sim_days else 0.0

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
        per_day = self.count_ge(10) / self.sim_days if self.sim_days else 0.0
        return per_day * 365.25

    @property
    def attacker_revenue_share(self) -> float:
        total = self.att_final_blocks + self.hon_final_blocks
        return self.att_final_blocks / total if total else 0.0

    @property
    def attacker_orphan_fraction(self) -> float:
        total_att = self.att_final_blocks + self.att_orphaned_blocks
        return self.att_orphaned_blocks / total_att if total_att else 0.0


def simulate(cfg: SimConfig) -> SimStats:
    rng = random.Random(cfg.seed)
    rate = cfg.w / T_BLOCK_S  # objects/sec total
    n_objects = int(cfg.days * SECONDS_PER_DAY * rate)

    stats = SimStats(sim_days=cfg.days)

    hon_blocks: List[int] = []  # embedded-share count per honest block since fork
    att_blocks: List[int] = []  # embedded-share count per attacker block since fork
    hon_pending = 0
    att_pending = 0

    def reset_fork():
        hon_blocks.clear()
        att_blocks.clear()

    for _ in range(n_objects):
        is_attacker = rng.random() < cfg.alpha
        is_block = rng.random() < (1.0 / cfg.w)

        if not is_block:
            if is_attacker:
                att_pending += 1
            else:
                hon_pending += 1
            continue

        if is_attacker:
            embed = att_pending if cfg.attacker_embeds else 0
            att_blocks.append(embed)
            att_pending = 0
        else:
            hon_blocks.append(hon_pending)
            hon_pending = 0

        a = len(att_blocks)
        h = len(hon_blocks)

        # Decision, only evaluated after a block event (honest or attacker).
        if (a == 0 and h > 0) or (h - a >= cfg.d):
            # give up: attacker suffix orphaned, honest suffix final
            stats.hon_final_blocks += h
            stats.att_orphaned_blocks += a
            reset_fork()
            att_pending = 0
            # hon_pending carries on (not reset)
            continue

        if h == 0:
            continue  # withhold

        if cfg.rule == "sop":
            att_objects = sum(1 + n for n in att_blocks)
            att_weight = att_objects
            hon_weight = sum(1 + m for m in hon_blocks)
            K = cfg.K_objects
        else:  # stock
            att_objects = a
            att_weight = a
            hon_weight = h
            K = 0

        if att_objects >= K and att_weight > hon_weight:
            # reveal: attacker suffix final, honest suffix orphaned
            stats.reveals += 1
            stats.reorg_depths.append(h)
            stats.att_final_blocks += a
            stats.att_orphaned_blocks += 0  # attacker blocks became final, not orphaned
            reset_fork()
            hon_pending = 0
            # att_pending carries on
            continue

        # else: hold

    # end of run: whatever is left in-flight is neither final nor orphaned;
    # it is dropped from the accounting (boundary effect, negligible for
    # long enough runs).
    return stats


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


def _sweep(days: float, seed: int) -> None:
    alphas = [0.30, 0.33, 0.40, 0.45]
    ds = [1, 2, 3]
    variants = [("sop", True), ("sop", False), ("stock", False)]
    print(f"# Model B sweep: days={days}, seed={seed}\n")
    print("| alpha | d | rule | embeds | reveals | reveals/day | mean reorg | max reorg | "
          "#>=3 | #>=10 | rate>=10/yr | revenue share | orphan frac |")
    print("|--:|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for alpha in alphas:
        for d in ds:
            for rule, embeds in variants:
                cfg = SimConfig(alpha=alpha, d=d, rule=rule, attacker_embeds=embeds,
                                 days=days, seed=seed)
                s = simulate(cfg)
                print(f"| {alpha} | {d} | {rule} | {embeds} | {s.reveals} | "
                      f"{s.reveals_per_day:.4f} | {s.mean_reorg_depth:.3f} | "
                      f"{s.max_reorg_depth} | {s.count_ge(3)} | {s.count_ge(10)} | "
                      f"{s.rate_ge10_per_year:.4f} | {s.attacker_revenue_share:.4f} | "
                      f"{s.attacker_orphan_fraction:.4f} |")


def _deep(years: float, seed: int) -> None:
    alpha = 0.33
    ds = [2, 3, 5, 10, 20]
    days = years * 365.25
    print(f"# Model B deep-reorg estimate: alpha={alpha}, years={years} "
          f"({days:.1f} days), rule=sop, attacker_embeds=True\n")
    print("tevador's claim: about 1 reorg of 10+ blocks per 3 years of stubborn mining.\n")
    print("| d | #>=10 reorgs | rate>=10/yr | years/reorg |")
    print("|--:|--:|--:|--:|")
    for d in ds:
        cfg = SimConfig(alpha=alpha, d=d, rule="sop", attacker_embeds=True,
                         days=days, seed=seed)
        s = simulate(cfg)
        n10 = s.count_ge(10)
        rate = s.rate_ge10_per_year
        years_per = (1.0 / rate) if rate > 0 else math.inf
        print(f"| {d} | {n10} | {rate:.4f} | {years_per:.3f} |")


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

    p_deep = sub.add_parser("deep", help="Model B deep-reorg (10+) rate estimate")
    p_deep.add_argument("--years", type=float, default=3.0)
    p_deep.add_argument("--seed", type=int, default=1)

    args = parser.parse_args(argv)
    t0 = time.time()
    if args.cmd == "tevador":
        _print_tevador(args.alpha, args.w, args.k)
    elif args.cmd == "sweep":
        _sweep(args.days, args.seed)
    elif args.cmd == "deep":
        _deep(args.years, args.seed)
    print(f"\n(elapsed: {time.time() - t0:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
