#!/usr/bin/env python3
"""The Monero P2P Observatory's seed series read for OQ8 (2026-10-28): the
flagged fleet's share of each seed's white list against its share of the
seed's outbound connections — mainnet's version of the lab's "x the
ceiling" multiplier (E27 2.2x untrimmed, E45 1.06x trimmed).

Input: a directory holding the observatory's feeds as pulled by
studies/antiproxy/analysis/mainnet/pull_observer.sh (seed_fleet_hist.json: per seed, every
~10 min, <seed>_white_{d,p,all} / <seed>_out_{d,p,all} / _gray_ / _in_ in
percent, d = definitive fingerprint, p = pattern member;
outbound_share_hist.json: adversary share of live outbound per seed;
white_share_hist.json: flagged share of the reachable population per crawl
vantage). Output: per-seed medians over the whole series and the last 7
days, and the per-row out/white ratio's median and p10/p90. Aggregates only
(the feeds carry no addresses; the pull keeps the address-bearing feeds out).

Usage: python3 observer_seed_ratio.py <feed_dir> [--json out.json]
"""
import argparse
import json
import statistics
import time
from pathlib import Path

SEEDS = ("ovhde", "node1", "node2")


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 2) if xs else None


def pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 2) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("feed_dir")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    d = Path(a.feed_dir)
    sf = json.loads((d / "seed_fleet_hist.json").read_text())
    ob = json.loads((d / "outbound_share_hist.json").read_text())
    ws = json.loads((d / "white_share_hist.json").read_text())
    now = sf[-1]["t"]
    out = {
        "feed_dir": str(d),
        "seed_fleet_hist": {"rows": len(sf), "first": time.strftime("%Y-%m-%d", time.gmtime(sf[0]["t"])),
                            "last": time.strftime("%Y-%m-%d %H:%M", time.gmtime(now)),
                            "days": round((now - sf[0]["t"]) / 86400, 1)},
        "windows": {},
    }
    for name, window in (("all", None), ("last_7d", 7 * 86400)):
        rows = [r for r in sf if window is None or r["t"] >= now - window]
        w = {"rows": len(rows), "seeds": {}}
        for s in SEEDS:
            ratios = [r[f"{s}_out_all"] / r[f"{s}_white_all"] for r in rows
                      if r.get(f"{s}_white_all") and r.get(f"{s}_out_all") is not None]
            ratios_d = [r[f"{s}_out_d"] / r[f"{s}_white_d"] for r in rows
                        if r.get(f"{s}_white_d") and r.get(f"{s}_out_d") is not None]
            w["seeds"][s] = {
                "white_all_pct": med(r.get(f"{s}_white_all") for r in rows),
                "white_def_pct": med(r.get(f"{s}_white_d") for r in rows),
                "gray_all_pct": med(r.get(f"{s}_gray_all") for r in rows),
                "in_all_pct": med(r.get(f"{s}_in_all") for r in rows),
                "out_all_pct": med(r.get(f"{s}_out_all") for r in rows),
                "out_def_pct": med(r.get(f"{s}_out_d") for r in rows),
                "out_over_white_all": {"median": med(ratios), "p10": pct(ratios, 0.1), "p90": pct(ratios, 0.9)},
                "out_over_white_def": {"median": med(ratios_d), "p10": pct(ratios_d, 0.1), "p90": pct(ratios_d, 0.9)},
            }
        out["windows"][name] = w
    out["outbound_share_hist"] = {
        "rows": len(ob), "days": round((ob[-1]["t"] - ob[0]["t"]) / 86400, 1),
        "adversary_share_of_outbound_pct_median": {s: med(r.get(s) for r in ob) for s in SEEDS},
        "p90": {s: pct([r.get(s) for r in ob], 0.9) for s in SEEDS},
    }
    out["white_share_hist"] = {
        "rows": len(ws),
        "flagged_share_of_reachable_population_pct_median": {s: med(r.get(s) for r in ws) for s in SEEDS + ("oracle",)},
    }
    print(json.dumps(out, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
