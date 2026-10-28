#!/usr/bin/env python3
"""X3 cover census for the stemmable-inbound cells (E62's supporting numbers,
written 2026-10-28 after the review found no working artifact behind them).

From --sim-log-txrelay logs of a --stemmable cell:

  x3_events               epoch events the patch logs (one per adopter epoch)
  virtual_epoch_share     share of x3 events whose virtual candidate list is
                          non-empty (candidates existed that epoch)
  union_*                 the edge-2 union size at epoch build (min/med/max)
  edge2_virtual_share     of the epochs logging two stem targets, the share
                          whose second target is one of that epoch's virtual
                          candidates (string join on the addr; misses counted)
  relayed_stems_at_users  stem receipts at user nodes for a tx originated by
                          another node (the cover the proposal exists to add)
  users_reached           user nodes with at least one relayed stem
  user_own_sends          local sends by user nodes (the dilution denominator)

Usage: python3 x3_census.py <archive_dir> [--json out.json]
"""
import argparse
import json
import statistics
import sys
from collections import defaultdict
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

    origin = {}
    for node, events in logs.items():
        for e in events:
            if e["ev"] == "send" and e["method"] == "local":
                for tx in e["txs"]:
                    origin.setdefault(tx, node)

    x3 = virtual_epochs = 0
    unions = []
    edge2_total = edge2_virtual = edge2_miss = 0
    last_virtual = {}  # node -> virtual addr strings from its latest x3 event
    for node, events in logs.items():
        for e in events:
            if e["ev"] == "x3":
                x3 += 1
                virt = e.get("virtual", [])
                if virt:
                    virtual_epochs += 1
                unions.append(int(e.get("union", 0)))
                last_virtual[node] = set(virt)
            elif e["ev"] == "epoch":
                stems = e.get("stems", [])
                if len(stems) >= 2:
                    edge2_total += 1
                    lv = last_virtual.get(node)
                    if not lv:
                        edge2_miss += 1
                        continue
                    addr = stems[1].get("addr", "")
                    if addr in lv or ip_of(addr) in {ip_of(v) for v in lv}:
                        edge2_virtual += 1

    relayed = defaultdict(int)
    for node, events in logs.items():
        if not node.startswith("user-"):
            continue
        for e in events:
            if e["ev"] == "rx" and not e["fluff"]:
                o = origin.get(e["tx"])
                if o is not None and o != node:
                    relayed[node] += 1

    users = [n for n in logs if n.startswith("user-")]
    out = {
        "archive": str(a.archive),
        "x3_events": x3,
        "virtual_epoch_share": round(virtual_epochs / x3, 3) if x3 else None,
        "union_min": min(unions) if unions else None,
        "union_median": statistics.median(unions) if unions else None,
        "union_max": max(unions) if unions else None,
        "edge2_epochs": edge2_total,
        "edge2_join_misses": edge2_miss,
        "edge2_virtual": edge2_virtual,
        "edge2_virtual_share": round(edge2_virtual / edge2_total, 3) if edge2_total else None,
        "relayed_stems_at_users": sum(relayed.values()),
        "users_reached": len(relayed),
        "users_total": len(users),
        "user_own_sends": sum(1 for tx, n in origin.items() if n.startswith("user-")),
        "relayed_per_user": {k: relayed[k] for k in sorted(relayed)},
    }
    print(json.dumps(out, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
