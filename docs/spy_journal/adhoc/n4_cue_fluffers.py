#!/usr/bin/env python3
"""Cue-level first-fluffer classes for the N4 runs (written 2026-10-28).

E58 quotes "first fluffs are handed over by well-connected relays and
miners - 24.5k and 13.6k of them"; no committed n4 artifact carried those
counts (the jsons' fluff1.first_fluffer are per-tx counts with miners pooled
into "reachable"). This recomputes them: for every (spy, tx) pair, the class
of the peer that handed the spy its first fluff-flagged receipt - n4's cue
definition, spy peers excluded as there.

Usage: python3 n4_cue_fluffers.py <archive_dir> [--json out.json]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "analysis" / "spy"))
from txrelay_check import load_logs, load_ip_map, ip_of  # noqa: E402


def classify(node):
    if node.startswith("user-"):
        return "user"
    for pre in ("relay-", "medium-", "observer-", "miner-", "spy-"):
        if node.startswith(pre):
            return pre[:-1]
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archive")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    logs = load_logs(a.archive)
    ip_map = load_ip_map(a.archive)
    spies = {n for n in logs if n.startswith("spy-")}

    cues = Counter()
    for s in spies:
        first = {}  # tx -> (t, peer) earliest fluff rx
        for e in logs[s]:
            if e["ev"] != "rx" or not e["fluff"]:
                continue
            peer = ip_map.get(ip_of(e.get("addr", "")))
            if peer is None or peer in spies:
                continue
            tx = e["tx"]
            if tx not in first or e["t"] < first[tx][0]:
                first[tx] = (e["t"], peer)
        for _, peer in first.values():
            cues[classify(peer)] += 1

    out = {
        "archive": str(a.archive),
        "cues": sum(cues.values()),
        "by_class": dict(cues),
    }
    print(json.dumps(out, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
