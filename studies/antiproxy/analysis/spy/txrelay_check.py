#!/usr/bin/env python3
"""Rebuild Dandelion++ ground truth from --sim-log-txrelay logs and check it.

Reads every daemon_logs/<node>/txrelay.jsonl in an archived run
(docs/TXRELAY_LOG.md), maps peer IPs to agents with
transaction_registry/agent_registry.json, and for every transaction in
transaction_registry/transactions.json reports:

  - origin: the node whose log has a `send` with method `local` for it, and
    whether that matches the recorded sender;
  - stem path: origin -> each `stem` event's destination, hop by hop, and how
    it ended: `epoch` / `no_stem` fluff, `embargo` timer, `loop` (the stem
    reached a node that already held it; monerod then fluffs), or
    `unlogged_node` (sent to a daemon without the flag, e.g. stock seeds);
  - consistency: every stem send has a matching `rx` (fluff false) at the
    destination.

Plus per-node epoch counts and the share of fluff epochs (stock: 20%).

Usage:
    python3 analysis/spy/txrelay_check.py <archive_dir> [--json out.json]
"""

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path


def node_name(log_path):
    """daemon_logs/monero-relay-001/txrelay.jsonl -> relay-001."""
    name = log_path.parent.name
    return name[len("monero-"):] if name.startswith("monero-") else name


def load_logs(run_dir):
    """{node: [event, ...]} sorted by time."""
    logs = {}
    for path in sorted(Path(run_dir, "daemon_logs").glob("*/txrelay.jsonl")):
        events = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        events.sort(key=lambda e: e["t"])
        logs[node_name(path)] = events
    return logs


def load_ip_map(run_dir):
    with open(Path(run_dir, "transaction_registry", "agent_registry.json")) as f:
        agents = json.load(f)["agents"]
    return {a["ip_addr"]: a["id"] for a in agents if a.get("ip_addr")}


def load_senders(run_dir):
    """{tx_hash: sender_id} from the run's transaction records."""
    path = Path(run_dir, "transaction_registry", "transactions.json")
    if not path.exists():
        return {}
    with open(path) as f:
        records = json.load(f)
    senders = {}
    for r in records:
        for h in r.get("tx_hashes") or [r.get("tx_hash")]:
            if h:
                senders[h] = r.get("sender_id")
    return senders


def ip_of(addr):
    return addr.rsplit(":", 1)[0] if addr else ""


def index(logs):
    """Per-tx views of the events that matter for origin and stem paths."""
    origin = defaultdict(set)          # tx -> nodes with a local send
    stems = defaultdict(dict)          # tx -> {node: (t, dest addr)} first stem send
    rx_stem = defaultdict(set)         # tx -> nodes that received it as a stem
    ends = defaultdict(dict)           # tx -> {node: reason} where it was fluffed
    epochs = {}
    for node, events in logs.items():
        n_epochs = n_fluff = 0
        for e in events:
            ev = e["ev"]
            if ev == "epoch":
                n_epochs += 1
                n_fluff += bool(e["fluff"])
            elif ev == "send" and e["method"] == "local":
                for tx in e["txs"]:
                    origin[tx].add(node)
            elif ev == "stem":
                for tx in e["txs"]:
                    stems[tx].setdefault(node, (e["t"], e["to"]["addr"]))
            elif ev == "rx" and not e["fluff"]:
                rx_stem[e["tx"]].add(node)
            elif ev == "fluff":
                for tx in e["txs"]:
                    ends[tx].setdefault(node, e["reason"])
            elif ev == "pool_relay" and e["was"] in ("stem", "forward"):
                ends[e["tx"]].setdefault(node, "embargo")
        epochs[node] = (n_epochs, n_fluff)
    return origin, stems, rx_stem, ends, epochs


def stem_path(tx, start, stems, ends, ip_map, logged):
    """Follow `stem` sends from `start`. Returns (nodes, end reason)."""
    path = [start]
    node = start
    while True:
        if node in ends.get(tx, {}):
            return path, ends[tx][node]
        hop = stems.get(tx, {}).get(node)
        if hop is None:
            return path, "unlogged"
        nxt = ip_map.get(ip_of(hop[1]))
        if nxt is None:
            return path, "unknown_peer"
        if nxt in path:
            return path, "loop"
        path.append(nxt)
        if nxt not in logged:
            return path, "unlogged_node"
        node = nxt


def check(run_dir):
    logs = load_logs(run_dir)
    ip_map = load_ip_map(run_dir)
    senders = load_senders(run_dir)
    origin, stems, rx_stem, ends, epochs = index(logs)

    counts = Counter(e["ev"] for events in logs.values() for e in events)
    txs = sorted(senders) if senders else sorted(origin)
    report = {"logs": len(logs), "events": dict(counts), "txs": len(txs)}

    found = matched = 0
    hops, end_reasons, unmatched_stems = [], Counter(), 0
    hops_by_end = defaultdict(list)
    for tx in txs:
        nodes = origin.get(tx, set())
        if not nodes:
            continue
        found += 1
        start = sorted(nodes)[0]
        matched += senders.get(tx) in nodes
        path, reason = stem_path(tx, start, stems, ends, ip_map, logs)
        hops.append(len(path) - 1)
        end_reasons[reason] += 1
        hops_by_end[reason].append(len(path) - 1)
        unmatched_stems += sum(1 for n in path[1:] if n in logs and n not in rx_stem.get(tx, set()))

    report.update({
        "origin_found": found,
        "origin_matches_sender": matched if senders else None,
        "stem_hops_mean": round(statistics.mean(hops), 2) if hops else None,
        "stem_hops_hist": dict(sorted(Counter(hops).items())),
        "stem_end": dict(end_reasons),
        "stem_hops_mean_by_end": {k: round(statistics.mean(v), 2) for k, v in sorted(hops_by_end.items())},
        # Each hop onto a new relay is a trial that ends in a fluff epoch with
        # p = 0.2 (stock); loops and missing logs censor paths. p-hat = epoch
        # endings / relay hops, and 1 / p-hat is the uncensored mean length.
        "fluff_per_hop": round(len(hops_by_end["epoch"]) / sum(hops), 3) if sum(hops) else None,
        "stem_hops_without_rx": unmatched_stems,
    })
    total_epochs = sum(n for n, _ in epochs.values())
    total_fluff = sum(f for _, f in epochs.values())
    report["epochs"] = total_epochs
    report["fluff_epoch_share"] = round(total_fluff / total_epochs, 3) if total_epochs else None
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--json", help="also write the report to this file")
    args = ap.parse_args(argv)
    report = check(args.run_dir)
    if not report["logs"]:
        print(f"No daemon_logs/*/txrelay.jsonl under {args.run_dir}", file=sys.stderr)
        return 1
    for k, v in report.items():
        print(f"{k:24} {v}")
    if args.json:
        with open(args.json, "w") as f:
            json.dump(report, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
