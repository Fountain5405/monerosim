#!/usr/bin/env python3
"""Reconstruct a node's FINAL main chain from its daemon log and write it as a
canonical_chain JSON (the format agents/selfish_bridge.py dumps), so the
selfish-mining analysis can use an HONEST node's view as its reference.

Why (review 2026-09-26): the analysis's default reference is the bridge's
main chain. The bridge daemon is unflagged and follows stock cumulative
difficulty; in SoP / PoP cells the honest network uses a different fork
choice, so at the end of a run the bridge can sit on an attacker branch the
honest nodes rejected — those attacker blocks then count as canonical.
The archived LMDBs cannot serve as the reference (Shadow stops daemons hard
and `db-sync-mode: fastest` leaves them at genesis), but at log-level
`monitor` every daemon logs each main-chain addition:

    +++++ BLOCK SUCCESSFULLY ADDED
    id:\t<hash>
    HEIGHT N, difficulty:\tD

and every reorganization re-adds the switched-in blocks through the same
path. The final chain is therefore the LAST id added at each height, for
heights up to the height of the last addition (a switch to a shorter but
heavier chain lowers the tip). Grafted chain-snapshot blocks are never
"added" during the run, so they are naturally excluded.

Usage:
  venv/bin/python scripts/honest_chain_from_log.py <run_dir> [--node honest-001] [--out PATH]
  -> <run_dir>/transaction_registry/canonical_chain_<node>_log.json
  venv/bin/python scripts/selfish_mining_analysis.py <run_dir> --chain <that file>
"""
import argparse
import json
import re
import sys
from pathlib import Path

RE_LINE = re.compile(r"^(?P<ts>\S+ \S+)\t\s*(?P<tag>\[[^\]]*\]|\S+)\t")
RE_ID = re.compile(r"\tid:\t<([0-9a-f]+)>")
RE_HEIGHT = re.compile(r"\tHEIGHT (\d+), difficulty:")
ADDED = "+++++ BLOCK SUCCESSFULLY ADDED"


def parse_main_chain(text: str) -> list:
    """[{height, hash}] for heights 1..tip, last-added-per-height, from one
    daemon log. Pending (id, height) pairs are keyed by the logging thread's
    tag so interleaved threads cannot mix an id with another block's height."""
    last_by_height: dict = {}
    pending: dict = {}          # tag -> {"id": ..., "height": ...}
    tip = None
    for line in text.splitlines():
        m = RE_LINE.match(line)
        tag = m.group("tag") if m else ""
        if ADDED in line:
            pending[tag] = {}
            continue
        p = pending.get(tag)
        if p is None:
            continue
        mi = RE_ID.search(line)
        if mi and "id" not in p:
            p["id"] = mi.group(1)
            continue
        mh = RE_HEIGHT.search(line)
        if mh and "id" in p:
            h = int(mh.group(1))
            last_by_height[h] = p["id"]
            tip = h
            del pending[tag]
    if tip is None:
        return []
    return [{"height": h, "hash": last_by_height[h]}
            for h in sorted(last_by_height) if 1 <= h <= tip]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--node", default="honest-001", help="daemon_logs/monero-<node>/bitmonero.log")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    log = run_dir / "daemon_logs" / f"monero-{args.node}" / "bitmonero.log"
    if not log.is_file():
        print(f"ERROR: {log} not found", file=sys.stderr)
        return 2
    chain = parse_main_chain(log.read_text(errors="replace"))
    if not chain:
        print(f"ERROR: no main-chain additions found in {log}", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else run_dir / "transaction_registry" / f"canonical_chain_{args.node}_log.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"observer": args.node, "source": "daemon-log", "chain": chain}))
    print(f"wrote {out}: {len(chain)} blocks, heights {chain[0]['height']}..{chain[-1]['height']}, tip {chain[-1]['hash'][:16]}")
    bridge = next(iter(sorted(run_dir.glob("**/canonical_chain_attacker-bridge.json"))), None)
    if bridge:
        b = {x["height"]: x["hash"] for x in json.loads(bridge.read_text()).get("chain", [])}
        h = {x["height"]: x["hash"] for x in chain}
        common = sorted(set(b) & set(h))
        diff = [k for k in common if b[k] != h[k]]
        print(f"vs bridge dump: bridge tip {max(b) if b else '-'}, honest tip {max(h)}, "
              f"common heights {len(common)}, differing {len(diff)}"
              + (f" (first at {diff[0]})" if diff else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
