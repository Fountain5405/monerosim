#!/usr/bin/env python3
"""Daemon-log health check for fork-choice experiments.

Review 2026-09-25 (docs/20260925_e4_code_data_review.md): the SoP v2 cells
"worked" on a binary whose every reorganization threw, and both honest
controls never forked. Both facts were in the daemon logs and nothing
looked. This looks, per node:

  reorg_started    '###### REORGANIZE'
  reorg_success    'REORGANIZE SUCCESS'
  exceptions       'Exception at [add_new_block]'
  alt_added        'BLOCK ADDED AS ALTERNATIVE'
  decisions        'SIM-PoP: fork' / 'SIM-SoP: fork' lines (objective / tie / switch)
  share_weighted   decisions where a chain's weight exceeds unit * length:
                   for SoP (unit = diff/w) at least one share counted; for
                   PoP (unit 1) at least one uncle bonus counted

and, per host, in the agents' own output (shadow.data/hosts/<host>/
bash.*.stdout and .stderr; daemon and wallet output is not scanned):

  agent_tracebacks 'Traceback (most recent call last)' lines. An agent can
                   raise on every tick while every daemon stays healthy (the
                   stubborn smoke's stock attacker, 2026-09-30, never
                   published and its cell read "ok"). Lines, not exceptions:
                   an agent logging through two handlers prints each twice.

Also per node:

  stale_ids        'Found block <id>' whose id equals an earlier
                   'SIM-SoP: share <id>' of the same node. The share log's
                   get_block_hash(b) cached the share's id in the mining
                   block object, so a block found before the next template
                   refresh was stored under the SHARE's id while peers
                   hashed the true one: one block, two ids. In a 240 h run
                   it split the network for good (2026-10-03).
  invalid_chain    'Sent invalid chain': a peer's blocks did not match the
                   ids it advertised (how the stale ids showed up in sync).

and across nodes:

  chain agreement  the last height at which every non-attacker node's final
                   main chain holds the same block, compared by PoW (a
                   stale-id block has two ids but one PoW), and how far the
                   longest chain runs past it (split_depth).

A run FAILS when any node has reorg_started != reorg_success or
exceptions > 0, or any agent printed a traceback, or any node found a
stale-id block or logged 'Sent invalid chain' (zero in all 60 healthy runs
since 2026-09-29), or the chains split by more than SPLIT_TOLERANCE blocks. --require-forks also fails when no non-attacker node
accepted an alternative block (a fork-free control validates nothing);
--require-share-weight fails when no subjective SoP decision carried a
share-augmented weight (the share term is inert).

Usage: sop_health_check.py <run_dir> [--unit N | --diff D --w W]
                            [--require-forks] [--require-share-weight] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RE_DECISION = re.compile(
    r"SIM-(PoP|SoP): fork (\d+) (OBJECTIVE )?(alt|TIE) (\d+)/(\d+) vs (?:main )?(\d+)/(\d+)"
    r".*?-> (SWITCH|KEEP)")
RE_HEIGHT_DIFF = re.compile(r"HEIGHT (\d+), difficulty:\s*(\d+)")
RE_ARMED = re.compile(r"weight table armed \(w=(\d+)")
ATTACKER_NODE = re.compile(r"attacker|bridge", re.I)
AGENT_TRACEBACK = b"Traceback (most recent call last)"
RE_SHARE = re.compile(r"SIM-SoP: share <([0-9a-f]{64})>")
RE_FOUND = re.compile(r"Found block <([0-9a-f]{64})>")
RE_POW = re.compile(r"PoW:\s*<([0-9a-f]{64})>")
RE_REORG_DONE = re.compile(r"REORGANIZE SUCCESS! on height: \d+, new blockchain size: (\d+)")
# Nodes still disagreeing more than this many blocks past their last common
# block at the end of a run did not converge (one block in flight is normal).
SPLIT_TOLERANCE = 3


def _suffix_units(diff_by_height: dict, last_diff: int | None, fork: int, length: int, w: int) -> int | None:
    """Sum of per-height units (difficulty // w, floor 1) over the suffix
    fork+1 .. fork+length, from the difficulties the node itself logged when
    it added main-chain blocks; heights it never added (alt blocks above its
    tip) take the latest logged difficulty."""
    total = 0
    for h in range(fork + 1, fork + length + 1):
        d = diff_by_height.get(h, last_diff)
        if d is None:
            return None
        total += max(1, d // w)
    return total


def scan_log_text(text: str, unit: int | None = None) -> dict:
    """Count the health markers in one daemon log.

    Share-weight detection needs the unit (diff / w). With an explicit
    `unit` (the --unit / --diff --w CLI path, fixed-difficulty smokes) a chain
    heavier than unit x length counted a share. Without one — a real-DAA base
    such as the h10 chain snapshot — the unit at each suffix height is that
    height's logged difficulty // w (w from the node's own "weight table
    armed" line), and a chain must exceed length x unit by a further full
    unit, so an alt chain's slightly different difficulty cannot masquerade
    as a share (review 2026-09-26)."""
    n = {"reorg_started": 0, "reorg_success": 0, "exceptions": 0, "alt_added": 0,
         "decisions": 0, "objective": 0, "ties": 0, "switches": 0,
         "sop_subjective": 0, "share_weighted": 0, "stale_ids": 0, "invalid_chain": 0,
         "w": None, "share_weighted_unit_source": "explicit" if unit else None,
         "main_pow": {}}
    diff_by_height: dict = {}
    last_diff = None
    main_pow = n["main_pow"]     # height -> PoW of the node's final main chain
    pending, pending_pow = None, None   # the block being printed: "main" / "alt"
    shares: set = set()
    for line in text.splitlines():
        if "difficulty:" in line and "HEIGHT " in line:
            m = RE_HEIGHT_DIFF.search(line)
            if m:
                diff_by_height[int(m.group(1))] = int(m.group(2))
                last_diff = int(m.group(2))
                if pending == "main" and pending_pow:
                    main_pow[int(m.group(1))] = pending_pow
            pending, pending_pow = None, None
            continue
        if "BLOCK SUCCESSFULLY ADDED" in line:
            pending, pending_pow = "main", None
            continue
        if "PoW:" in line:
            if pending == "main":
                m = RE_POW.search(line)
                pending_pow = m.group(1) if m else None
            continue
        if "SIM-SoP: share <" in line:
            m = RE_SHARE.search(line)
            if m:
                shares.add(m.group(1))
            continue
        if "Found block <" in line:
            m = RE_FOUND.search(line)
            if m and m.group(1) in shares:
                n["stale_ids"] += 1
            continue
        if "Sent invalid chain" in line:
            n["invalid_chain"] += 1
            continue
        if "weight table armed" in line:
            m = RE_ARMED.search(line)
            if m:
                n["w"] = int(m.group(1))
            continue
        if "###### REORGANIZE" in line:
            n["reorg_started"] += 1
        elif "REORGANIZE SUCCESS" in line:
            n["reorg_success"] += 1
            m = RE_REORG_DONE.search(line)
            if m:            # a reorg can leave a SHORTER chain under SoP
                size = int(m.group(1))
                for h in [h for h in main_pow if h >= size]:
                    del main_pow[h]
        elif "Exception at [add_new_block]" in line:
            n["exceptions"] += 1
        elif "BLOCK ADDED AS ALTERNATIVE" in line:
            n["alt_added"] += 1
            pending, pending_pow = "alt", None
        elif "SIM-PoP: fork" in line or "SIM-SoP: fork" in line:
            m = RE_DECISION.search(line)
            if not m:
                continue
            engine, fork, objective, kind, w_alt, l_alt, w_main, l_main, outcome = m.groups()
            n["decisions"] += 1
            if objective:
                n["objective"] += 1
            if kind == "TIE":
                n["ties"] += 1
            if outcome == "SWITCH":
                n["switches"] += 1
            if objective:
                continue
            # A block weighs lb*unit*(1+counted shares) under SoP and
            # lb*(1+uncle bonus) under PoP: any chain heavier than
            # unit*length had a share / uncle counted (weights are always
            # multiples of the unit, so divisibility cannot tell).
            if engine == "PoP":
                if int(w_alt) > int(l_alt) or int(w_main) > int(l_main):
                    n["share_weighted"] += 1
                continue
            n["sop_subjective"] += 1
            if unit:
                if int(w_alt) > unit * int(l_alt) or int(w_main) > unit * int(l_main):
                    n["share_weighted"] += 1
            elif n["w"]:
                fork_h = int(fork)
                ua = _suffix_units(diff_by_height, last_diff, fork_h, int(l_alt), n["w"])
                um = _suffix_units(diff_by_height, last_diff, fork_h, int(l_main), n["w"])
                # margin: one more full unit (the unit at the first suffix height)
                margin = max(1, diff_by_height.get(fork_h + 1, last_diff or 0) // n["w"])
                if ua is not None and um is not None:
                    n["share_weighted_unit_source"] = "logged-difficulty"
                    if int(w_alt) >= ua + margin or int(w_main) >= um + margin:
                        n["share_weighted"] += 1
    return n


def scan_agent_logs(run_dir: Path) -> dict:
    """Traceback lines per host in the agents' output (agents run under bash;
    see the module docstring). Hosts without any are left out."""
    counts: dict[str, int] = {}
    hosts = Path(run_dir) / "shadow.data" / "hosts"
    for f in sorted(hosts.glob("*/bash.*.stdout")) + sorted(hosts.glob("*/bash.*.stderr")):
        with open(f, "rb") as fh:
            c = sum(1 for line in fh if AGENT_TRACEBACK in line)
        if c:
            counts[f.parent.name] = counts.get(f.parent.name, 0) + c
    return counts


def chain_agreement(chains: dict) -> dict:
    """The last height at which every chain ({height: PoW}) holds the same
    block, how far the longest chain runs past it, and each tip."""
    chains = {k: c for k, c in chains.items() if c}
    tips = {k: max(c) for k, c in chains.items()}
    if len(chains) < 2:
        return {"common_height": None, "split_depth": 0, "tips": tips}
    common = None
    for h in sorted(set.intersection(*(set(c) for c in chains.values())), reverse=True):
        if len({c[h] for c in chains.values()}) == 1:
            common = h
            break
    start = min(min(c) for c in chains.values()) - 1
    return {"common_height": common, "split_depth": max(tips.values()) - (start if common is None else common),
            "tips": tips}


def check_run(run_dir: Path, unit: int | None = None) -> dict:
    """Scan every daemon log under <run_dir>/daemon_logs; return the report."""
    run_dir = Path(run_dir)
    nodes: dict[str, dict] = {}
    for log in sorted(run_dir.glob("daemon_logs/*/bitmonero.log")):
        name = log.parent.name.removeprefix("monero-")
        nodes[name] = scan_log_text(log.read_text(errors="replace"), unit)
    problems = []
    for name, n in nodes.items():
        if n["reorg_started"] != n["reorg_success"]:
            problems.append(f"{name}: reorg {n['reorg_success']}/{n['reorg_started']} succeeded")
        if n["exceptions"]:
            problems.append(f"{name}: {n['exceptions']} add_new_block exceptions")
    for name, n in nodes.items():
        if n["stale_ids"]:
            problems.append(f"{name}: {n['stale_ids']} block(s) found under a share's id (stale-id miner bug)")
        if n["invalid_chain"]:
            problems.append(f"{name}: {n['invalid_chain']} 'Sent invalid chain' (a peer's blocks did not match "
                            f"the ids it advertised)")
    chains = {name: n.pop("main_pow") for name, n in nodes.items()}
    chain = chain_agreement({k: c for k, c in chains.items() if not ATTACKER_NODE.search(k)})
    if chain["split_depth"] > SPLIT_TOLERANCE:
        problems.append(f"chains split: the longest runs {chain['split_depth']} blocks past the last common "
                        f"block {chain['common_height']} (tips {chain['tips']})")
    agent_tb = scan_agent_logs(run_dir)
    for host, c in agent_tb.items():
        problems.append(f"{host}: {c} agent traceback lines")
    forks_seen = sum(n["alt_added"] for name, n in nodes.items()
                     if not ATTACKER_NODE.search(name))
    share_weighted = sum(n["share_weighted"] for n in nodes.values())
    totals = {k: sum(n[k] for n in nodes.values()) for k in
              ("reorg_started", "reorg_success", "exceptions", "alt_added", "decisions",
               "sop_subjective", "share_weighted", "stale_ids", "invalid_chain")}
    totals["agent_tracebacks"] = sum(agent_tb.values())
    totals["split_depth"] = chain["split_depth"]
    return {"run_dir": str(run_dir), "nodes": nodes, "totals": totals,
            "agent_tracebacks": agent_tb, "chain": chain,
            "forks_seen": forks_seen, "share_weighted": share_weighted,
            "problems": problems, "ok": not problems and bool(nodes)}


def summarize(report: dict | None) -> str:
    """One short token for a results table."""
    if not report:
        return "-"
    if not report.get("nodes"):
        return "no-logs"
    t = report["totals"]
    parts = []
    if t["reorg_started"] != t["reorg_success"]:
        parts.append(f"REORG {t['reorg_success']}/{t['reorg_started']}")
    if t["exceptions"]:
        parts.append(f"EXC {t['exceptions']}")
    if t.get("agent_tracebacks"):
        parts.append(f"AGENT-TB {t['agent_tracebacks']}")
    if t.get("stale_ids"):
        parts.append(f"STALE-ID {t['stale_ids']}")
    if t.get("invalid_chain"):
        parts.append(f"INVALID-CHAIN {t['invalid_chain']}")
    if t.get("split_depth", 0) > SPLIT_TOLERANCE:
        parts.append(f"SPLIT {t['split_depth']}")
    if not report.get("forks_seen"):
        parts.append("no-forks")
    # SoP nodes made subjective decisions but none ever carried a counted
    # share: the share term is inert (the F2 class the 2026-09-25 review
    # found by hand).
    if t.get("sop_subjective") and not t.get("share_weighted"):
        parts.append("share-term-inert")
    return "; ".join(parts) if parts else "ok"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--unit", type=int, help="SoP unit weight diff/w (share-weight detection)")
    ap.add_argument("--diff", type=int, help="block difficulty (with --w, derives --unit)")
    ap.add_argument("--w", type=int, help="workshare ratio w (with --diff)")
    ap.add_argument("--require-forks", action="store_true")
    ap.add_argument("--require-share-weight", action="store_true")
    ap.add_argument("--json", action="store_true", help="print the full report as JSON")
    a = ap.parse_args(argv)
    unit = a.unit or (a.diff // a.w if a.diff and a.w else None)
    rep = check_run(a.run_dir, unit)
    if a.require_forks and not rep["forks_seen"]:
        rep["problems"].append("no non-attacker node accepted an alternative block (fork-free run)")
        rep["ok"] = False
    if a.require_share_weight and not rep["share_weighted"]:
        rep["problems"].append("no fork decision carried a share/uncle-augmented weight")
        rep["ok"] = False
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        for name, n in rep["nodes"].items():
            print(f"{name:22s} reorg {n['reorg_success']}/{n['reorg_started']}  exc {n['exceptions']}"
                  f"  alt {n['alt_added']}  decisions {n['decisions']} (obj {n['objective']},"
                  f" tie {n['ties']}, switch {n['switches']})  share-weighted {n['share_weighted']}")
        c = rep["chain"]
        print(f"chain: last common block {c['common_height']}, split depth {c['split_depth']}, tips {c['tips']}; "
              f"stale-id blocks {rep['totals']['stale_ids']}, 'Sent invalid chain' {rep['totals']['invalid_chain']}")
        print(f"forks_seen={rep['forks_seen']} share_weighted={rep['share_weighted']}"
              f" -> {'OK' if rep['ok'] else 'FAIL'}")
        for p in rep["problems"]:
            print(f"  ! {p}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
