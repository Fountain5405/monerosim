#!/usr/bin/env python3
"""Who mined the uncles? (MRL #144 exact cells, 2026-09-27.)

For a run with `sim-pop-uncles-header` honest miners, collect every uncle id
the honest daemons logged as COUNTED (`SIM-PoP: uncle <id> at height H
COUNTED`), de-duplicate across nodes and evaluations, and attribute each to
the miner that found it (the `found` list the selfish-mining analysis already
builds from the miners' own logs). Also counts template-side embeddings and
the refresh hook (F5d) per honest miner.

The question it answers: does the uncle term act on the ATTACKER's blocks
(the point of MRL #144) or only on honest-vs-honest natural ties? At gamma ~ 0
with a stock bridge every counted uncle was honest (the attacker's tie block
never reached an honest template); a relaying bridge should change that.

Usage:
  venv/bin/python scripts/uncle_attribution.py archived_runs/<run> [<run> ...] [--json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.selfish_mining_analysis import (  # noqa: E402
    _attacker_ids, _honest_miner_ids, found_by_hash, load_raw_config, parse_found_blocks,
)

RE_COUNTED = re.compile(r"SIM-PoP: uncle <?([0-9a-f]+)>? at height (\d+) COUNTED")
RE_EMBED = re.compile(r"SIM-PoP: embedding uncle header")
RE_REFRESH = re.compile(r"refreshing the block template for the uncle header")


def scan_log(text: str) -> dict:
    counted = {}
    for m in RE_COUNTED.finditer(text):
        counted.setdefault(m.group(1), int(m.group(2)))
    return {"counted": counted,
            "embedded": len(RE_EMBED.findall(text)),
            "refreshes": len(RE_REFRESH.findall(text))}


def attribute(run_dir) -> dict:
    run_dir = Path(run_dir)
    cfg = load_raw_config(run_dir / "input_config.yaml")
    attackers = _attacker_ids(cfg)
    honest = sorted(_honest_miner_ids(cfg))
    h2m = found_by_hash(parse_found_blocks(run_dir, list(attackers) + honest))
    counted, per_node = {}, {}
    for node in honest:
        log = run_dir / "daemon_logs" / f"monero-{node}" / "bitmonero.log"
        if not log.is_file():
            continue
        r = scan_log(log.read_text(errors="replace"))
        per_node[node] = {"embedded": r["embedded"], "refreshes": r["refreshes"], "counted_ids": len(r["counted"])}
        for uid, h in r["counted"].items():
            counted.setdefault(uid, h)
    by = {"attacker": 0, "honest": 0, "unknown": 0}
    for uid in counted:
        miner = h2m.get(uid)
        by["attacker" if miner in attackers else "honest" if miner else "unknown"] += 1
    return {"run": run_dir.name, "uncles_counted": len(counted), "by_miner": by, "per_node": per_node}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = [attribute(r) for r in args.runs]
    if args.json:
        print(json.dumps(rows, indent=1))
        return 0
    for r in rows:
        emb = sum(n["embedded"] for n in r["per_node"].values())
        ref = sum(n["refreshes"] for n in r["per_node"].values())
        b = r["by_miner"]
        print(f"{r['run']}: uncles counted {r['uncles_counted']} (attacker {b['attacker']}, "
              f"honest {b['honest']}, unknown {b['unknown']}); embedded {emb}; refreshes {ref}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
