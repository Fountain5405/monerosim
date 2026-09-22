#!/usr/bin/env python3
"""MSB calibration study across selfish-mining runs (Li/Yang/Tessone 2020).

Li et al.'s Miner Sequence Bootstraining z-scores flag withholding, but the
null (iid-shuffled winner sequences) ignores two clustering sources a real
network has: propagation latency (their admitted confound) and, as our
alpha-sweep measured, the ATTACK ITSELF — heavy withholding clusters the
honest miners' canonical wins too (honest z up to +3.17 at alpha=0.45).
This tool tabulates MSB z and canonical share for EVERY miner across a set
of runs so an honest-strategy control run (same topology, no withholding)
can calibrate the detector's false-positive floor.

Usage: python3 scripts/msb_study.py <run_dir> [<run_dir> ...] [--out FILE]
Prints a markdown table; exits 0 always (it is a measurement, not a gate).
"""
import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from scripts.selfish_mining_analysis import (   # noqa: E402
    _alpha_eff_from_config, _alpha_from_config, _attacker_ids,
    _eclipsed_miner_ids, _find_chain_file, _honest_miner_ids,
    _island_ids_from_config, _release_lead_from_config, attacker_share_from_chain,
    found_by_hash, load_raw_config, parse_found_blocks,
)
from scripts.selfish_externality import msb_scores   # noqa: E402


def study_run(run_dir: Path) -> dict:
    cfg = load_raw_config(run_dir / "input_config.yaml")
    attacker_ids = _attacker_ids(cfg)
    eclipsed = _eclipsed_miner_ids(cfg)
    islands = _island_ids_from_config(cfg)
    miner_ids = sorted(attacker_ids | _honest_miner_ids(cfg))
    chain_path = _find_chain_file(run_dir, None, islands)
    chain = (load_json(chain_path) or {}).get("chain", []) if chain_path else []
    found = parse_found_blocks(run_dir, miner_ids)
    h2m = found_by_hash(found)
    scores = msb_scores(chain, h2m)
    att_share = attacker_share_from_chain(chain, h2m, attacker_ids)
    controlled = attacker_share_from_chain(chain, h2m, attacker_ids | eclipsed)
    strategy = next((a.get("attributes", {}).get("strategy", "honest")
                     for a in cfg.get("agents", {}).values()
                     if a.get("script") == "agents.selfish_miner"), "honest")
    return {
        "run": run_dir.name,
        "alpha": _alpha_from_config(cfg),
        "alpha_eff": _alpha_eff_from_config(cfg),
        "release_lead": _release_lead_from_config(cfg),
        "strategy": strategy,
        "attack": strategy != "honest",
        "attacker_share": att_share,
        "controlled_share": controlled,
        "chain_len": len(chain),
        "rows": [
            {
                "miner": m,
                "role": ("attacker" if m in attacker_ids
                         else "victim" if m in eclipsed else "honest"),
                "share": attacker_share_from_chain(chain, h2m, {m}),
                "z": scores.get(m, {}).get("z", 0.0),
            }
            for m in miner_ids
        ],
    }


def load_json(p):
    import json
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return None


def render(results: list) -> str:
    lines = ["# MSB calibration study", "",
             "| run | α | α_eff | strategy | r_lead | att share | ctrl share | "
             "miner | role | share | MSB z | flag |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    flagged = {"honest": [0, 0], "attacker": [0, 0], "victim": [0, 0]}
    for r in results:
        for row in r["rows"]:
            flag = "FLAG" if row["z"] > 2 else ""
            flagged[row["role"]][1] += 1
            if row["z"] > 2:
                flagged[row["role"]][0] += 1
            lines.append(
                f"| {r['run']} | {r['alpha']:.3f} | {r['alpha_eff']:.3f} "
                f"| {r['strategy']} | {r['release_lead']} "
                f"| {r['attacker_share']:.3f} | {r['controlled_share']:.3f} "
                f"| {row['miner']} | {row['role']} | {row['share']:.3f} "
                f"| {row['z']:+.2f} | {flag} |")
    lines += ["", "## Flag rates by role (z > 2)", ""]
    for role, (n, d) in flagged.items():
        lines.append(f"- {role}: {n}/{d}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="+")
    ap.add_argument("--out", default=None, help="also write the table here")
    args = ap.parse_args()
    results = []
    for rd in args.run_dirs:
        try:
            results.append(study_run(Path(rd)))
        except Exception as e:                     # noqa: BLE001 - report and continue
            print(f"SKIP {rd}: {e}", file=sys.stderr)
    report = render(results)
    print(report)
    if args.out:
        Path(args.out).write_text(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
