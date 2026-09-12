#!/usr/bin/env python3
"""Selfish-mining analysis for a finished native-mining run.

Attribution uses an honest node's GROUND-TRUTH canonical chain recorded by the
bridge (canonical_chain.json, Task 8) joined with the block hashes each miner
logged finding. It deliberately does NOT reuse build_accepted, whose
earliest-timestamp dedupe misattributes a selfish attacker's withheld, early-
found, later-lost tie blocks. Computes attacker revenue share vs the
Eyal-Sirer gamma=0 curve, plus orphan rates. See docs/SELFISH_MINING.md.

Usage: python3 scripts/selfish_mining_analysis.py <run_dir> [--chain <path>] [--out <dir>]
Exit: 0 all verdicts pass; 1 a verdict failed; 2 inputs missing / empty.
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

import yaml

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.native_mining_check import FOUND          # noqa: E402


def load_raw_config(cfg_path) -> dict:
    """Load the RAW run config YAML, which carries the per-agent `agents` map
    (script, hashrate). native_daa_analysis.load_config returns a transformed
    dict with NO `agents` key, so using it here made the attacker/honest sets
    empty and every verdict pass vacuously (review C2)."""
    with open(cfg_path, "r") as f:
        return yaml.safe_load(f) or {}


def es_revenue_share(alpha: float, gamma: float) -> float:
    num = alpha * (1 - alpha) ** 2 * (4 * alpha + gamma * (1 - 2 * alpha)) - alpha ** 3
    den = 1 - alpha * (1 + (2 - alpha) * alpha)
    return num / den


def parse_found_blocks(run_dir, miner_ids) -> list:
    run_dir = Path(run_dir)
    out = []
    for miner in miner_ids:
        for log in sorted(glob.glob(str(run_dir / "shadow.data" / "hosts" / miner / "monerod*.stdout"))):
            with open(log, "r", errors="replace") as f:
                for line in f:
                    m = FOUND.search(line)
                    if m:
                        out.append({"hash": m.group(2).strip("<>"), "height": int(m.group(3)), "miner": miner})
    return out


def found_by_hash(found: list) -> dict:
    # First finder wins if a hash somehow repeats (it should not).
    mapping = {}
    for e in found:
        mapping.setdefault(e["hash"], e["miner"])
    return mapping


def attacker_share_from_chain(chain: list, hash_to_miner: dict, attacker_ids: set) -> float:
    if not chain:
        return 0.0
    att = sum(1 for b in chain if hash_to_miner.get(b["hash"]) in attacker_ids)
    return att / len(chain)


def orphan_stats(found: list, canonical_hashes: set, attacker_ids: set) -> dict:
    att_found = sum(1 for e in found if e["miner"] in attacker_ids)
    att_canon = sum(1 for e in found if e["miner"] in attacker_ids and e["hash"] in canonical_hashes)
    tot_found = len(found)
    tot_canon = sum(1 for e in found if e["hash"] in canonical_hashes)
    return {
        "attacker_found": att_found,
        "attacker_canonical": att_canon,
        "attacker_orphan_rate": (1 - att_canon / att_found) if att_found else 0.0,
        "total_found": tot_found,
        "network_orphan_rate": (1 - tot_canon / tot_found) if tot_found else 0.0,
    }


def realized_gamma(found: list, chain: list, attacker_ids: set) -> tuple:
    """Realized gamma: the honest network's tie-break bias toward the attacker.

    A gamma EVENT is a fork at height F (both an attacker- and an honest-found
    block exist at F) that the honest network RESOLVED by mining the canonical
    block at F+1 on one of the two forks. gamma = fraction of such events where
    the honest network extended the ATTACKER's fork (i.e. canonical[F] is
    attacker-found).

    Only forks resolved by an HONEST-found F+1 count: a fork where the
    attacker's own chain overtook (attacker-found canonical F+1) is a reorg win,
    not a tie-break, and is excluded. Counting every coexistence height, or
    attributing by canonical[F] alone, over-reports gamma — the earlier version
    read ~0.70 on a true-gamma~=0 run (review C1). Returns (gamma, num_events).
    """
    miner_by_hash = {}
    miners_at_height = {}
    for e in found:
        miner_by_hash[e["hash"]] = e["miner"]
        miners_at_height.setdefault(e["height"], set()).add(e["miner"])
    canon_hash = {b["height"]: b["hash"] for b in chain}
    events = 0
    attacker_wins = 0
    for height, miners in miners_at_height.items():
        has_attacker = any(m in attacker_ids for m in miners)
        has_honest = any(m not in attacker_ids for m in miners)
        if not (has_attacker and has_honest):
            continue                                  # not a fork
        resolver_miner = miner_by_hash.get(canon_hash.get(height + 1))
        if resolver_miner is None or resolver_miner in attacker_ids:
            continue                                  # unresolved, or attacker's own extension (reorg, not tie-break)
        events += 1
        if miner_by_hash.get(canon_hash.get(height)) in attacker_ids:
            attacker_wins += 1                         # honest network extended the attacker's fork
    gamma = (attacker_wins / events) if events else 0.0
    return gamma, events


def _attacker_ids(cfg):
    return {aid for aid, a in cfg.get("agents", {}).items() if a.get("script") == "agents.selfish_miner"}


def _honest_miner_ids(cfg):
    return {aid for aid, a in cfg.get("agents", {}).items() if a.get("script") == "agents.autonomous_miner"}


def _alpha_from_config(cfg):
    agents = cfg.get("agents", {})
    att = sum(a.get("hashrate", 0) for a in agents.values() if a.get("script") == "agents.selfish_miner")
    honest = sum(a.get("hashrate", 0) for a in agents.values() if a.get("script") == "agents.autonomous_miner")
    total = att + honest
    return (att / total) if total else 0.0


def make_verdicts(alpha, measured_share, stats, theory_at_gamma=None) -> list:
    verdicts = []
    theory = es_revenue_share(alpha, 0.0)
    verdicts.append({
        "name": "attacker share vs Eyal-Sirer gamma=0 curve",
        "measured": measured_share, "theory": theory,
        "pass": abs(measured_share - theory) <= 0.10,
    })
    if theory_at_gamma is not None:
        verdicts.append({
            "name": "attacker share vs Eyal-Sirer theory at measured gamma",
            "measured": measured_share, "theory": theory_at_gamma,
            "pass": abs(measured_share - theory_at_gamma) <= 0.10,
        })
    if alpha > 0.34:
        verdicts.append({
            "name": "attacker beats honest baseline (share > alpha)",
            "measured": measured_share, "baseline": alpha,
            "pass": measured_share > alpha,
        })
    return verdicts


def _find_chain_file(run_dir, explicit):
    if explicit:
        return Path(explicit)
    for cand in glob.glob(str(Path(run_dir) / "**" / "canonical_chain.json"), recursive=True):
        return Path(cand)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--chain", default=None, help="path to canonical_chain.json (default: search run_dir)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    cfg_path = run_dir / "input_config.yaml"
    if not cfg_path.exists():
        print(f"ERROR: {cfg_path} missing", file=sys.stderr)
        return 2
    cfg = load_raw_config(cfg_path)
    attacker_ids = _attacker_ids(cfg)
    miner_ids = list(attacker_ids | _honest_miner_ids(cfg))

    chain_path = _find_chain_file(run_dir, args.chain)
    if not chain_path or not chain_path.exists():
        print("ERROR: canonical_chain.json not found (bridge did not record it?)", file=sys.stderr)
        return 2
    chain = json.loads(chain_path.read_text()).get("chain", [])
    if not chain:
        print("ERROR: empty canonical chain", file=sys.stderr)
        return 2

    found = parse_found_blocks(run_dir, miner_ids)
    h2m = found_by_hash(found)
    canonical_hashes = {b["hash"] for b in chain}
    alpha = _alpha_from_config(cfg)
    share = attacker_share_from_chain(chain, h2m, attacker_ids)
    stats = orphan_stats(found, canonical_hashes, attacker_ids)
    gamma, n_ties = realized_gamma(found, chain, attacker_ids)
    theory_at_gamma = es_revenue_share(alpha, gamma)
    verdicts = make_verdicts(alpha, share, stats, theory_at_gamma)

    out_dir = Path(args.out) if args.out else (run_dir / "analysis_output" / "selfish")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = _render(alpha, share, stats, verdicts, gamma, n_ties, theory_at_gamma)
    (out_dir / "report.md").write_text(report)
    print(report)
    return 0 if all(v["pass"] for v in verdicts) else 1


def _render(alpha, share, stats, verdicts, gamma=0.0, n_ties=0, theory_at_gamma=None) -> str:
    if theory_at_gamma is None:
        theory_at_gamma = es_revenue_share(alpha, gamma)
    lines = ["# Selfish-mining analysis", "",
             f"- alpha: {alpha:.3f}",
             f"- attacker canonical share (measured): {share:.3f}",
             f"- Eyal-Sirer gamma=0 theory: {es_revenue_share(alpha, 0.0):.3f}",
             f"- realized gamma: {gamma:.3f}",
             f"- num ties: {n_ties}",
             f"- theory at measured gamma: {theory_at_gamma:.3f}",
             f"- attacker orphan rate: {stats['attacker_orphan_rate']:.3f}",
             f"- network orphan rate: {stats['network_orphan_rate']:.3f}",
             "", "## Verdicts", ""]
    for v in verdicts:
        lines.append(f"- {'PASS' if v['pass'] else 'FAIL'}: {v['name']} (measured {v['measured']:.3f})")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
