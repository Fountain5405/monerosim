#!/usr/bin/env python3
"""Spy-side stem receipts: what the fleet buys, per cell (the X3b primary
metric, pre-registered with P55-P59; written 2026-10-28).

From --sim-log-txrelay logs (spies = agents whose id starts with 'spy'):

  spy_stem_rx            rx events at spies with fluff false (every stem
                         receipt is logged, so this counts hops, not txs)
  spy_stem_rx_dir        the same split by `dir` (in = the spy was dialed,
                         out = the spy dialed): the connection-direction
                         check the hidden pole needs
  stem_txs_at_spies      distinct txs some spy received as a stem
  stem_tx_share          stem_txs_at_spies / locally originated txs
  hop1_stem_txs          distinct txs whose stem reached a spy straight from
                         the originating node (the first-hop exposure sp_r
                         scores); hop1_user_txs restricts to user origins
  virtual_rx / virtual_rx_share
                         of spy stem receipts from an x3 adopter, how many
                         arrived while the spy's IP sat in the sender's
                         latest x3 virtual list (the stemmable re-entry, by
                         time-ordered join on the sender's x3 events); the
                         remainder rode a real outgoing connection
  per_spy                stem receipts per spy: min / median / max / zeros

Usage: python3 spy_stem_receipts.py <archive_dir> [--json out.json]
"""
import argparse
import bisect
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "analysis" / "spy"))
from txrelay_check import load_logs, load_ip_map, ip_of  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archive")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    logs = load_logs(a.archive)
    ip_map = load_ip_map(a.archive)
    node_ip = {n: ip for ip, n in ip_map.items()}

    origin = {}
    x3_t, x3_v = defaultdict(list), defaultdict(list)  # node -> times, -> virtual ip sets
    for node, events in logs.items():
        for e in events:
            if e["ev"] == "send" and e["method"] == "local":
                for tx in e["txs"]:
                    origin.setdefault(tx, node)
            elif e["ev"] == "x3":
                ips = set()
                for v in e.get("virtual", []):
                    if isinstance(v, dict):
                        ips.add(ip_of(v.get("addr", "")))
                x3_t[node].append(e["t"])
                x3_v[node].append(ips)

    spies = [n for n in logs if n.startswith("spy")]
    rx_total = 0
    rx_dir = Counter()
    per_spy = Counter({s: 0 for s in spies})
    stem_txs, hop1_txs = set(), set()
    virt_rx = virt_eligible = 0
    for spy in spies:
        spy_ip = node_ip.get(spy, "")
        for e in logs[spy]:
            if e["ev"] != "rx" or e["fluff"]:
                continue
            rx_total += 1
            rx_dir[e.get("dir", "?")] += 1
            per_spy[spy] += 1
            stem_txs.add(e["tx"])
            sender = ip_map.get(ip_of(e.get("addr", "")))
            if sender is None:
                continue
            if origin.get(e["tx"]) == sender:
                hop1_txs.add(e["tx"])
            if sender in x3_t:
                virt_eligible += 1
                i = bisect.bisect_right(x3_t[sender], e["t"]) - 1
                if i >= 0 and spy_ip in x3_v[sender][i]:
                    virt_rx += 1

    counts = sorted(per_spy.values())
    out = {
        "archive": str(a.archive),
        "spies": len(spies),
        "local_txs": len(origin),
        "spy_stem_rx": rx_total,
        "spy_stem_rx_dir": dict(rx_dir),
        "stem_txs_at_spies": len(stem_txs),
        "stem_tx_share": round(len(stem_txs) / len(origin), 4) if origin else None,
        "hop1_stem_txs": len(hop1_txs),
        "hop1_user_txs": sum(1 for tx in hop1_txs if origin[tx].startswith("user-")),
        "user_txs": sum(1 for n in origin.values() if n.startswith("user-")),
        "x3_adopters": len(x3_t),
        "rx_from_adopters": virt_eligible,
        "virtual_rx": virt_rx,
        "virtual_rx_share": round(virt_rx / virt_eligible, 4) if virt_eligible else None,
        "per_spy": {"min": counts[0] if counts else None,
                    "median": statistics.median(counts) if counts else None,
                    "max": counts[-1] if counts else None,
                    "zeros": sum(1 for c in counts if c == 0)},
    }
    print(json.dumps(out, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
