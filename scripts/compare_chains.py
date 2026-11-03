#!/usr/bin/env python3
"""compare_chains.py - do two runs have the same chain, node by node?

Reads each daemon node's block ids per height from its bitmonero.log in both
runs (<run>/daemon_logs/<node>/bitmonero.log, gzipped or not: the
"+++++ BLOCK SUCCESSFULLY ADDED" record, whose "id:" and "HEIGHT N" lines
follow it; the last block added at a height is the one the node ended on),
and compares them over the heights both runs reached.

    scripts/compare_chains.py RUN_A RUN_B [--node NAME ...] [--min-common N] [--json OUT]

Exit 0: every compared node is identical over its common heights.
Exit 1: some node's chain diverges (the first such height is printed).
Exit 2: a node is missing or has no blocks in one run, or fewer than
        --min-common heights (default 1) are common.

For two runs of the SAME daemon binary (a before/after of the agents, the
generator or the runner). Two different binaries never share block ids, even
when they behave the same: the coinbase key is drawn from the daemon's random
stream, which any change to the binary shifts. For that comparison use
scripts/compare_block_timeline.py (as scripts/stock_equivalence.sh does).
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ADDED = "+++++ BLOCK SUCCESSFULLY ADDED"
ID_RE = re.compile(r"\bid:\s*<?([0-9a-f]{64})>?")
HEIGHT_RE = re.compile(r"\bHEIGHT (\d+)")


def chain_from_log(path: Path) -> dict[int, str]:
    """{height: block id} from one bitmonero.log(.gz); last added at a height wins."""
    opener = gzip.open if str(path).endswith(".gz") else open
    chain: dict[int, str] = {}
    height = block_id = None
    in_record = False
    with opener(path, "rt", errors="replace") as fh:
        for line in fh:
            if ADDED in line:
                in_record, height, block_id = True, None, None
                continue
            if not in_record:
                continue
            m = ID_RE.search(line)
            if m:
                block_id = m.group(1)
            m = HEIGHT_RE.search(line)
            if m:
                height = int(m.group(1))
            if height is not None and block_id is not None:
                chain[height] = block_id
                in_record = False
    return chain


def node_log(run: Path, node: str) -> Path | None:
    logs = sorted((run / "daemon_logs" / node).glob("bitmonero.log*"))
    return logs[0] if logs else None


def daemon_nodes(run: Path) -> list[str]:
    """Node names under <run>/daemon_logs/ that have a bitmonero.log, sorted."""
    d = run / "daemon_logs"
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir() and node_log(run, p.name))


@dataclass
class NodeResult:
    node: str
    top_a: int | None
    top_b: int | None
    common: int
    first_divergence: int | None
    same_below: int | None
    error: str | None

    @property
    def identical(self) -> bool:
        return self.error is None and self.first_divergence is None


def compare_node(run_a: Path, run_b: Path, node: str) -> NodeResult:
    chains = []
    for run in (run_a, run_b):
        log = node_log(run, node)
        if log is None:
            return NodeResult(node, None, None, 0, None, None, f"no daemon log in {run}")
        chains.append(chain_from_log(log))
    a, b = chains
    if not a or not b:
        which = run_a if not a else run_b
        return NodeResult(node, max(a, default=None), max(b, default=None), 0, None, None,
                          f"no blocks added in {which}")
    common = sorted(set(a) & set(b))
    first = next((h for h in common if a[h] != b[h]), None)
    same_below = None if first is None else sum(1 for h in common if h < first)
    return NodeResult(node, max(a), max(b), len(common), first, same_below, None)


def compare_runs(run_a: Path, run_b: Path, nodes: list[str] | None = None) -> list[NodeResult]:
    """One result per node: the given ones, else every node with a log in either run."""
    run_a, run_b = Path(run_a), Path(run_b)
    if not nodes:
        nodes = sorted(set(daemon_nodes(run_a)) | set(daemon_nodes(run_b)))
    return [compare_node(run_a, run_b, n) for n in nodes]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_a")
    p.add_argument("run_b")
    p.add_argument("--node", action="append", default=[], help="compare only this node (repeatable)")
    p.add_argument("--min-common", type=int, default=1,
                   help="fewer common heights than this on any node is exit 2 (default 1)")
    p.add_argument("--json", type=Path, help="also write the results here")
    args = p.parse_args(argv)

    results = compare_runs(Path(args.run_a), Path(args.run_b), args.node or None)
    if not results:
        print(f"no daemon logs found under {args.run_a} or {args.run_b}", file=sys.stderr)
        return 2

    rc = 0
    for r in results:
        if r.error:
            print(f"{r.node}: ERROR {r.error}")
            rc = 2
        elif r.common < args.min_common:
            print(f"{r.node}: only {r.common} common heights (need {args.min_common}); tops {r.top_a} / {r.top_b}")
            rc = 2
        elif r.first_divergence is None:
            print(f"{r.node}: identical over {r.common} common heights (tops {r.top_a} / {r.top_b})")
        else:
            print(f"{r.node}: DIVERGED at height {r.first_divergence} "
                  f"({r.same_below} heights identical below it; tops {r.top_a} / {r.top_b})")
            rc = max(rc, 1)

    identical = [r for r in results if r.identical]
    verdict = "ERROR" if rc == 2 else ("IDENTICAL" if rc == 0 else "DIVERGED")
    print(f"{verdict}: {len(identical)} of {len(results)} nodes identical over their common heights")
    if args.json:
        args.json.write_text(json.dumps({
            "run_a": str(args.run_a), "run_b": str(args.run_b), "verdict": verdict,
            "nodes": [asdict(r) for r in results],
        }, indent=2) + "\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
