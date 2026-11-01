#!/usr/bin/env python3
"""N4: does the fluff epoch expose the originator? (plan 20261018 section 2.3
point 4, section 5.2 N4) - computed from --sim-log-txrelay logs, no new cells.

The mechanism under test: during a fluff epoch a node stems only its own
transactions (relayed stems are fluffed, reason `epoch`), so a spy stem peer
that can tell the node is in a fluff epoch attributes every stem it receives
from it in that epoch as the node's own.

The spy's cue that X is in a fluff epoch: X hands it a fluff-flagged tx the
spy has not seen fluffed by anyone else before (X is the first fluffer the spy
sees for that tx).  The spy cannot see X's epoch clock (10 min + U(0, 30 s)),
so the inference window after a cue is --window s (default 630, the maximum
epoch length).

Reported:
  premise   own txs are stemmed even in the origin's fluff epochs (the plan's
            claim, checked before anything else)
  mode      the cue's value as a mode detector: window overlap with true fluff
            epochs, and recall over epochs where the spy actually got stems
  attr      stems received inside inferred windows: how many, precision against
            ground truth, senders hit, and the recall gain over the first-hop
            baseline (origin stemmed straight to a spy - the sp cap)
  fluff1    who fluffs first (the sender itself / a spy / a relay) and how
            often a spy sees the first fluff

Usage: python3 n4_fluff_epoch.py <archive_dir> [--window 630] [--json out.json]
"""
import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "analysis" / "spy"))
from txrelay_check import load_logs, load_ip_map, load_senders, ip_of  # noqa: E402


def classify(node):
    if node.startswith("user-"):
        return "user"
    if node.startswith(("relay-", "medium-", "observer-", "miner-")):
        return "reachable"
    return "other"


def epoch_mode(epochs, t):
    """fluff flag of X's epoch containing t, or None before the first."""
    mode = None
    for et, fluff in epochs:
        if et > t:
            break
        mode = fluff
    return mode


def overlap(epochs, a, b):
    """Seconds of [a, b) that fall in X's true fluff epochs."""
    tot = 0
    # epochs are (start, fluff) only; ends come from the next epoch's start
    spans = []
    for i, (et, fluff) in enumerate(epochs):
        end = epochs[i + 1][0] if i + 1 < len(epochs) else float("inf")
        if fluff:
            spans.append((et, end))
    for s, e in spans:
        tot += max(0, min(e, b) - max(s, a))
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archive")
    ap.add_argument("--window", type=int, default=630)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    W = a.window * 1_000_000  # timestamps are microseconds

    logs = load_logs(a.archive)
    ip_map = load_ip_map(a.archive)
    senders = load_senders(a.archive)
    spies = {n for n in logs if n.startswith("spy-")}
    honest = [n for n in logs if not n.startswith("spy-")]

    # X-side: epochs, own sends, and which of X's own txs X stemmed.
    epochs = {}
    own = defaultdict(list)          # node -> [(t, tx)]
    stemmed_own = defaultdict(set)   # node -> own txs it stemmed
    for node, events in logs.items():
        if node in spies:
            continue
        eps = []
        for e in events:
            ev = e["ev"]
            if ev == "epoch":
                eps.append((e["t"], bool(e["fluff"])))
            elif ev == "send" and e["method"] == "local":
                for tx in e["txs"]:
                    own[node].append((e["t"], tx))
            elif ev == "stem":
                for tx in e["txs"]:
                    stemmed_own[node].add(tx)
        epochs[node] = eps

    # Premise: own txs stemmed even in the origin's fluff epochs.
    prem = Counter()
    for node, txs in own.items():
        for t, tx in txs:
            m = epoch_mode(epochs[node], t)
            stemmed = tx in stemmed_own[node]
            prem[(bool(m), stemmed)] += 1
    premise = {
        "own_txs": sum(prem.values()),
        "stemmed": sum(v for (_, s), v in prem.items() if s),
        "in_fluff_epoch": sum(v for (m, _), v in prem.items() if m),
        "in_fluff_epoch_stemmed": prem[(True, True)],
        "in_fluff_epoch_not_stemmed": prem[(True, False)],
    }

    # Spy-side: per spy, first fluff-flagged rx per tx (the cue) and stem rxs.
    cue = defaultdict(list)      # (spy, X) -> [t]
    stem_rx = defaultdict(list)  # (spy, X) -> [(t, tx)]
    for s in spies:
        first = {}               # tx -> (t, peer node)
        for e in logs[s]:
            if e["ev"] != "rx":
                continue
            peer = ip_map.get(ip_of(e.get("addr", "")))
            if peer is None or peer in spies:
                continue
            if e["fluff"]:
                if e["tx"] not in first or e["t"] < first[e["tx"]][0]:
                    first[e["tx"]] = (e["t"], peer)
            else:
                stem_rx[(s, peer)].append((e["t"], e["tx"]))
        for t, peer in first.values():
            cue[(s, peer)].append(t)

    # Mode value: window overlap with true fluff epochs; recall over epochs
    # where the spy got stems (the epochs where the leak could fire).
    win_overlap, win_len = [], []
    recalled = opp = 0
    for (s, x), cues in cue.items():
        cues.sort()
        for tc in cues:
            win_overlap.append(overlap(epochs[x], tc, tc + W) / 1e6)
            win_len.append(a.window)
    # recall: over every (spy, X) stem pair, epochs where the spy got stems
    # (the leak can only fire in those) and whether a cue covered the epoch
    for (s, x), rxs in stem_rx.items():
        cues = sorted(cue.get((s, x), []))
        eps = epochs[x]
        for i, (et, fluff) in enumerate(eps):
            if not fluff:
                continue
            end = eps[i + 1][0] if i + 1 < len(eps) else float("inf")
            if not any(et <= t < end for t, _ in rxs):
                continue
            opp += 1
            if any(et < tc + W and tc < end for tc in cues):
                recalled += 1
    mode = {
        "cues": len(win_overlap),
        "mean_window_in_true_fluff_s": round(statistics.mean(win_overlap), 1) if win_overlap else None,
        "window_s": a.window,
        "window_share_true_fluff": round(sum(win_overlap) / sum(win_len), 3) if win_len else None,
        "fluff_epochs_with_stems": opp,
        "of_which_cued": recalled,
        "cue_epoch_recall": round(recalled / opp, 3) if opp else None,
    }

    # first-hop baseline: origin stemmed straight to a spy (txrelay_check's
    # first_hop_spy cap on sp) - the recall gain is what N4 adds on top.
    first_hop = set()
    stems_by_tx = defaultdict(dict)  # tx -> {node: (t, addr)}
    for node, events in logs.items():
        for e in events:
            if e["ev"] == "stem":
                for tx in e["txs"]:
                    stems_by_tx[tx].setdefault(node, (e["t"], e["to"]["addr"]))
    for tx, by in stems_by_tx.items():
        o = senders.get(tx)
        if o in by and ip_map.get(ip_of(by[o][1])) in spies:
            first_hop.add(tx)

    # Oracle: perfect mode knowledge.  Stems received from X during one of
    # X's true fluff epochs are X's own by the premise; this is the ceiling on
    # any mode-detection attack, however good the detector is.
    oracle = []
    for (s, x), rxs in stem_rx.items():
        for tt, tx in rxs:
            if epoch_mode(epochs[x], tt):
                oracle.append((x, tx))
    oracle_tx = {tx for _, tx in oracle}

    # Attribution: stems inside an inferred window are called X's own.
    attr = []
    for (s, x), rxs in stem_rx.items():
        cues = sorted(cue.get((s, x), []))
        if not cues:
            continue
        for t, tx in rxs:
            if any(tc <= t < tc + W for tc in cues):
                attr.append((s, x, t, tx))
    correct = sum(senders.get(tx) == x for _, x, _, tx in attr)
    attr_tx = {tx for _, _, _, tx in attr}
    per_node = Counter(x for _, x, _, _ in attr)
    per_node_ok = Counter(x for _, x, _, tx in attr if senders.get(tx) == x)
    hit_classes = Counter(classify(senders.get(tx)) for _, x, _, tx in attr if senders.get(tx) == x)
    senders_n = Counter(classify(v) for v in senders.values())
    oracle_correct = sum(senders.get(tx) == x for x, tx in oracle)
    attribution = {
        "oracle_stem_rx": len(oracle),
        "oracle_precision": round(oracle_correct / len(oracle), 3) if oracle else None,
        "oracle_distinct_txs": len(oracle_tx),
        "oracle_txs_beyond_first_hop": len(oracle_tx - first_hop),
        "oracle_users_correct": sum(1 for x in {x for x, tx in oracle if senders.get(tx) == x} if classify(x) == "user"),
        "attributed_stem_rx": len(attr),
        "precision": round(correct / len(attr), 3) if attr else None,
        "distinct_txs": len(attr_tx),
        "txs_beyond_first_hop": len(attr_tx - first_hop),
        "senders_hit": len(per_node),
        "senders_hit_classes": dict(hit_classes),
        "senders_total_classes": dict(senders_n),
        "users_hit_correct": sum(1 for n in per_node_ok if classify(n) == "user"),
        "false_positives": len(attr) - correct,
    }

    # fluff1: who fluffs first, and does a spy see it first?
    fluffer = {}  # tx -> (t, node)
    for node, events in logs.items():
        for e in events:
            if e["ev"] == "fluff":
                for tx in e["txs"]:
                    if tx not in fluffer or e["t"] < fluffer[tx][0]:
                        fluffer[tx] = (e["t"], node)
            elif e["ev"] == "pool_relay" and e["was"] in ("stem", "forward"):
                if e["tx"] not in fluffer or e["t"] < fluffer[e["tx"]][0]:
                    fluffer[e["tx"]] = (e["t"], node)
    who = Counter()
    for tx, (t, node) in fluffer.items():
        o = senders.get(tx)
        if node == o:
            who["sender"] += 1
        elif node in spies:
            who["spy"] += 1
        else:
            who["relay"] += 1
    fluff1 = {"txs": len(fluffer), "first_fluffer": dict(who)}

    rep = {
        "archive": a.archive,
        "nodes": len(logs),
        "spies": len(spies),
        "premise": premise,
        "mode": mode,
        "attribution": attribution,
        "fluff1": fluff1,
    }
    print(json.dumps(rep, indent=2))
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=2) + "\n")


if __name__ == "__main__":
    main()
