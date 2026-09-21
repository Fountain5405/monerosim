# scripts/selfish_externality.py
"""Externality and detection metrics for selfish-mining runs.

The revenue-share verdicts in selfish_mining_analysis.py answer "did the
attack pay?". These metrics answer the questions the 2025 Monero literature
actually turned on (see docs/20260920_selfish_mining_literature.md):

- Lee & Kim 2025 (Qubic campaign): the attack was mostly UNPROFITABLE yet
  still damaged the network — orphan storms, multi-block reorgs. Metrics:
  per-hour orphan series, attack-period detection (their Alg. 1), attacker
  run-length x orphan scatter (their Fig. 7, with the y=x-1 / y=x-2 release
  signatures), reorg contest depths (their Fig. 3).
- Li, Yang & Tessone 2020: Miner Sequence Bootstrapping — z-score each
  miner's consecutive canonical-block wins against shuffled sequences;
  MSB > 2 flags withholding. Detection metric with a known false-positive
  confound (propagation latency) that a simulator can decompose.
- Kawaguchi & Noda 2021: SpEC = 5th-percentile / mean of hashrate —
  attackers strike at minima, so security is the minimum.
- Gervais et al. 2016: the stale rate r_s is the scalar that bridges network
  behavior and attack profitability.

All functions are pure and take the same primitives the analysis already
builds: `found` (parsed Found-block log entries) and `chain` (the bridge's
recorded canonical chain).
"""
import math
import random
from datetime import datetime

# ---------------------------------------------------------------- time utils

def found_time_s(entry: dict) -> float:
    """Sim-seconds of a found-block log entry's timestamp (daemon log clock,
    `2000-01-01 HH:MM:SS.mmm` — Shadow's simulated calendar)."""
    ts = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S.%f")
    return (ts - datetime(2000, 1, 1)).total_seconds()


def canonical_times(chain: list, found: list) -> dict:
    """height -> find-time (sim-s) of the canonical block, matched by hash
    against the miners' Found-block logs (every canonical block in these
    configs was found by a logged miner)."""
    t_by_hash = {e["hash"]: found_time_s(e) for e in found}
    return {b["height"]: t_by_hash[b["hash"]] for b in chain if b["hash"] in t_by_hash}


# ------------------------------------------------------------- hourly series

def hourly_series(found: list, canonical_hashes: set, hours: int = None) -> list:
    """One dict per elapsed sim-hour: finds, orphans, orphan rate, canonical
    blocks (by find time), and the canonical inter-block intervals that START
    in that hour. `hours` defaults to ceil(last find / 3600)."""
    if not found:
        return []
    times = [found_time_s(e) for e in found]
    canon_t = sorted(t for t in
                     (found_time_s(e) for e in found if e["hash"] in canonical_hashes))
    intervals = [(canon_t[i + 1] - canon_t[i]) for i in range(len(canon_t) - 1)]
    if hours is None:
        hours = int(max(times)) // 3600 + 1
    out = []
    for hr in range(hours):
        lo, hi = hr * 3600, (hr + 1) * 3600
        f = sum(1 for t in times if lo <= t < hi)
        o = sum(1 for e, t in zip(found, times)
                if lo <= t < hi and e["hash"] not in canonical_hashes)
        c = sum(1 for t in canon_t if lo <= t < hi)
        iv = [x for x, a, b in zip(intervals, canon_t[:-1], canon_t[1:]) if lo <= b < hi]
        out.append({
            "hour": hr, "finds": f, "orphans": o,
            "orphan_rate": (o / f) if f else 0.0,
            "canonical": c,
            "mean_interval": (sum(iv) / len(iv)) if iv else None,
        })
    return out


def detect_selfish_periods(hourly: list, tau_min: int = 2, d_min_h: int = 1,
                           g_max_h: int = 1) -> list:
    """Lee & Kim Alg. 1: contiguous hours whose orphan COUNT clears tau_min,
    at least d_min_h long, merged across gaps <= g_max_h. Their multi-week
    study used tau=2/h, d=4h, g=6h; the defaults here are scaled to a 6 h
    micro run. Returns [(start_hour, end_hour_inclusive), ...]."""
    hot = [h["hour"] for h in hourly if h["orphans"] >= tau_min]
    segs = []
    for hr in hot:
        if segs and hr - segs[-1][1] <= g_max_h:
            segs[-1][1] = hr
        else:
            segs.append([hr, hr])
    return [(s, e) for s, e in segs if e - s + 1 >= d_min_h]


# ------------------------------------------------- attacker runs and contests

def attacker_runs(chain: list, hash_to_miner: dict, attacker_ids: set,
                  found: list, canonical_hashes: set) -> list:
    """Qubic Fig. 7 data: every maximal run of consecutive attacker-mined
    CANONICAL blocks, with the orphaned finds (any miner) at heights inside
    the run — the y=x-1 / y=x-2 reference lines distinguish release-at-lead-1
    (textbook) from release-at-lead-2 (conservative) behaviour. Only runs of
    length >= 2 carry a release signature: a length-1 run sits on y=x-1 with
    zero orphans by definition (no release was needed)."""
    winners = [hash_to_miner.get(b["hash"]) for b in chain]
    heights = [b["height"] for b in chain]
    orphan_heights = [e["height"] for e in found if e["hash"] not in canonical_hashes]
    runs, i = [], 0
    while i < len(winners):
        if winners[i] in attacker_ids:
            j = i
            while j + 1 < len(winners) and winners[j + 1] in attacker_ids:
                j += 1
            lo, hi = heights[i], heights[j]
            runs.append({
                "length": j - i + 1, "start": lo, "end": hi,
                "orphans": sum(1 for hgt in orphan_heights if lo <= hgt <= hi + 1),
            })
            i = j + 1
        else:
            i += 1
    return runs


def reorg_contest_depths(found: list, hash_to_miner: dict, canonical_hashes: set) -> list:
    """Approximate fork lengths (Qubic Fig. 3's 'orphan fork lengths'): for
    every contested height (two miners found there), the number of
    consecutive further non-canonical finds by the losing miner — i.e. how
    deep the losing branch ran. Proxy: branches are inferred from finder x
    height only (branch ids are not in the logs); honest Monero runs are
    almost exclusively depth-1, selfish runs shift multi-block."""
    by_height = {}
    noncanon_by_height = {}
    for e in found:
        by_height.setdefault(e["height"], []).append(e["miner"])
        if e["hash"] not in canonical_hashes:
            noncanon_by_height.setdefault(e["height"], set()).add(e["miner"])
    depths = []
    for height in sorted(by_height):
        miners = by_height[height]
        if len(set(miners)) < 2:
            continue                       # not contested
        losers = noncanon_by_height.get(height, set())
        if not losers:
            continue
        depth = 1
        while (height + depth) in noncanon_by_height and \
                (noncanon_by_height[height + depth] & losers):
            depth += 1
        depths.append(depth)
    return depths


# ----------------------------------------------------------------- detection

def msb_scores(chain: list, hash_to_miner: dict, n_shuffles: int = 1000,
               seed: int = 12345) -> dict:
    """Li-Yang-Tessone Miner Sequence Bootstrapping: for each miner, the
    z-score of its observed count of consecutive canonical-block wins against
    the null of shuffled winner sequences (realized counts fixed). Withholding
    + release inflates consecutive wins without inflating total share, so
    MSB > 2 flags selfish mining; honest runs with latency-induced natural
    forks set the false-positive floor (their admitted confound)."""
    winners = [hash_to_miner.get(b["hash"]) for b in chain]
    winners = [w for w in winners if w is not None]
    if len(winners) < 2:
        return {}
    miners = sorted(set(winners))

    def consecutive(seq, m):
        return sum(1 for a, b in zip(seq, seq[1:]) if a == m and b == m)

    observed = {m: consecutive(winners, m) for m in miners}
    rng = random.Random(seed)
    null = {m: [] for m in miners}
    for _ in range(n_shuffles):
        shuffled = winners[:]
        rng.shuffle(shuffled)
        for m in miners:
            null[m].append(consecutive(shuffled, m))
    out = {}
    for m in miners:
        vals = null[m]
        mu = sum(vals) / len(vals)
        var = sum((v - mu) ** 2 for v in vals) / len(vals)
        sd = math.sqrt(var)
        out[m] = {"observed": observed[m], "expected": mu,
                  "z": ((observed[m] - mu) / sd) if sd > 0 else 0.0}
    return out


def spec(values: list) -> float:
    """Kawaguchi-Noda SpEC: bottom-5th-percentile / mean. Applied to hourly
    find counts it tracks hashrate dips; applied to hourly canonical counts
    it tracks realized-throughput dips (what an attack actually costs the
    chain). Attackers strike at minima; security is the minimum."""
    if not values or sum(values) == 0:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, round(0.05 * (len(s) - 1))))
    return s[k] / (sum(s) / len(s))
