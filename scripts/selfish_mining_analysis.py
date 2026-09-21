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
from scripts.selfish_externality import (              # noqa: E402
    attacker_runs, detect_selfish_periods, hourly_series, msb_scores,
    reorg_contest_depths, spec,
)


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


def mod_revenue_share(alpha: float, gamma: float) -> float:
    """Lee & Kim 2025 (arXiv:2512.01437) Eq. 2: revenue share of their
    modified selfish-mining Markov model -- the conservative release-at-lead-2
    policy Qubic ran on Monero (release while two clear instead of waiting for
    honest to close to one). Lower bound to eyal_sirer at gamma=0; verified
    against the paper: mod(0.28, 0) = 0.178, mod(0.4, 0) = 0.364."""
    num = alpha * (alpha ** 3 * gamma - 3 * alpha ** 2 * gamma + alpha ** 2
                   + 3 * alpha * gamma - 2 * alpha - gamma)
    den = alpha ** 4 - 2 * alpha ** 3 + alpha - 1
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
                        out.append({"hash": m.group(2).strip("<>"), "height": int(m.group(3)),
                                    "miner": miner, "time": m.group(1)})
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


def realized_gamma(found: list, chain: list, attacker_ids: set,
                   controlled_ids: set = None) -> tuple:
    """Realized gamma: the honest network's tie-break bias toward the attacker.

    A gamma EVENT is a fork at height F (both an attacker- and an honest-found
    block exist at F) that the honest network RESOLVED by mining the canonical
    block at F+1 on one of the two forks. gamma = fraction of such events where
    the honest network extended the ATTACKER's fork (i.e. canonical[F] is
    attacker-found).

    Only forks resolved by an HONEST-found F+1 count: a fork where the
    attacker's own chain overtook (attacker-found canonical F+1) is a reorg win,
    not a tie-break, and is excluded. Under eclipse composition,
    CONTROLLED-found resolvers (eclipsed victims extending the attacker's
    island chain) are attacker-side extensions too and are excluded — counting
    them read gamma = 0.27 on a genuinely gamma~0 network (the v2 first-pass
    artifact). Counting every coexistence height, or attributing by canonical[F]
    alone, over-reports gamma — the earlier version read ~0.70 on a
    true-gamma~=0 run (review C1). Returns (gamma, num_events).
    """
    controlled = controlled_ids if controlled_ids is not None else attacker_ids
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
        has_honest = any(m not in controlled for m in miners)
        if not (has_attacker and has_honest):
            continue                                  # not a fork
        resolver_miner = miner_by_hash.get(canon_hash.get(height + 1))
        if resolver_miner is None or resolver_miner in controlled:
            continue                                  # unresolved, or attacker-/victim-side extension (reorg, not tie-break)
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


def _release_lead_from_config(cfg) -> int:
    """The attacker's release_lead attribute (cash-out threshold); 1 = textbook
    Eyal-Sirer, >=2 = the conservative variant the verdicts treat specially."""
    for a in cfg.get("agents", {}).values():
        if a.get("script") == "agents.selfish_miner":
            try:
                return int(a.get("attributes", {}).get("release_lead", "1") or 1)
            except (TypeError, ValueError):
                return 1
    return 1


def _island_ids_from_config(cfg) -> set:
    """Bridge agent ids acting as ISLANDS (eclipse composition): their recorded
    chains follow the attacker's private view, never the honest network's, so
    they must never be used as the canonical observer."""
    ids = set()
    for a in cfg.get("agents", {}).values():
        if a.get("script") == "agents.selfish_miner":
            for b in (a.get("attributes", {}).get("islands") or "").split(","):
                if b.strip():
                    ids.add(b.strip())
    return ids


def _eclipsed_miner_ids(cfg) -> set:
    """Honest-miner agents the attacker has eclipsed (attributes.eclipsed).
    Their hashrate mines whatever the island shows — during withholding that
    is the attacker's private chain, so they count toward CONTROLLED share."""
    return {aid for aid, a in cfg.get("agents", {}).items()
            if a.get("script") == "agents.autonomous_miner"
            and (a.get("attributes") or {}).get("eclipsed") == "true"}


def _alpha_eff_from_config(cfg) -> float:
    """Effective attacker share under eclipse composition: (attacker +
    eclipsed victim hashrate) / total. With no eclipsed miners this equals
    _alpha_from_config."""
    agents = cfg.get("agents", {})
    eclipsed = _eclipsed_miner_ids(cfg)
    att = sum(a.get("hashrate", 0) for a in agents.values()
              if a.get("script") == "agents.selfish_miner")
    vic = sum(a.get("hashrate", 0) for aid, a in agents.items() if aid in eclipsed)
    honest = sum(a.get("hashrate", 0) for aid, a in agents.items()
                 if a.get("script") == "agents.autonomous_miner" and aid not in eclipsed)
    total = att + vic + honest
    return ((att + vic) / total) if total else 0.0


def make_verdicts(alpha, measured_share, stats, theory_at_gamma=None, release_lead=1,
                  eclipse=None) -> list:
    verdicts = []
    if eclipse:
        # Eclipse composition: the headline is the CONTROLLED share (attacker
        # + eclipsed victims' canonical blocks). With the v2 cash-on-lead
        # lifecycle the composed attack banks every island branch at lead
        # `island_cash_lead` (default 2) — conservative-release semantics —
        # so the comparison curve is the modified model at alpha_eff
        # (recruited hashrate behaves like attacker hashrate). v1 (no
        # lifecycle) measured 0.161 against this ~0.48 prediction and the
        # failure mode is documented in the results doc. Below the majority
        # line the curve is undefined; there the check degrades to
        # "the composed attacker controls the majority".
        controlled, alpha_eff = eclipse
        if alpha_eff >= 0.5:
            verdicts.append({
                "name": f"controlled majority (alpha_eff={alpha_eff:.3f} >= 1/2)",
                "measured": controlled, "theory": 0.5,
                "pass": controlled > 0.5,
            })
            return verdicts
        theory_eff = mod_revenue_share(alpha_eff, 0.0)
        verdicts.append({
            "name": f"controlled share vs modified model at alpha_eff={alpha_eff:.3f}",
            "measured": controlled, "theory": theory_eff,
            "pass": abs(controlled - theory_eff) <= 0.10,
        })
        return verdicts
    if release_lead >= 2:
        # Conservative cash-out (Qubic's policy): Lee & Kim place the attacker
        # "between" their modified model and classical Eyal-Sirer, so the check
        # is a band, not a point. The beats-honest verdict is deliberately not
        # applied: the conservative policy is EXPECTED to realize below honest
        # at gamma~0 (it trades honest waste for tie safety it cannot spend).
        lo, hi = mod_revenue_share(alpha, 0.0), es_revenue_share(alpha, 0.0)
        verdicts.append({
            "name": f"attacker share within modified<->ES band (release_lead={release_lead})",
            "measured": measured_share, "band": (lo, hi),
            "pass": (lo - 0.10) <= measured_share <= (hi + 0.10),
        })
        return verdicts
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


def _find_chain_file(run_dir, explicit, islands=frozenset()):
    if explicit:
        return Path(explicit)
    # Each bridge writes canonical_chain_<agent_id>.json (review C3: multiple
    # bridges must not clobber one file); older single-bridge runs wrote
    # canonical_chain.json. Match both; bridges converge on the honest chain,
    # so any one is the canonical chain — EXCEPT islands (eclipse
    # composition), whose chains follow the attacker's private view.
    # Sorted for determinism.
    cands = sorted(glob.glob(str(Path(run_dir) / "**" / "canonical_chain*.json"), recursive=True))
    for c in cands:
        try:
            observer = json.loads(Path(c).read_text()).get("observer")
        except (OSError, ValueError):
            observer = None
        if observer in islands:
            continue
        return Path(c)
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
    islands = _island_ids_from_config(cfg)
    eclipsed = _eclipsed_miner_ids(cfg)

    chain_path = _find_chain_file(run_dir, args.chain, islands)
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
    release_lead = _release_lead_from_config(cfg)
    share = attacker_share_from_chain(chain, h2m, attacker_ids)
    controlled = attacker_share_from_chain(chain, h2m, attacker_ids | eclipsed)
    alpha_eff = _alpha_eff_from_config(cfg)
    stats = orphan_stats(found, canonical_hashes, attacker_ids)
    gamma, n_ties = realized_gamma(found, chain, attacker_ids, attacker_ids | eclipsed)
    theory_at_gamma = es_revenue_share(alpha, gamma)
    eclipse = (controlled, alpha_eff) if eclipsed else None
    verdicts = make_verdicts(alpha, share, stats, theory_at_gamma, release_lead, eclipse)

    out_dir = Path(args.out) if args.out else (run_dir / "analysis_output" / "selfish")
    out_dir.mkdir(parents=True, exist_ok=True)
    externality = _externality_metrics(found, chain, h2m, attacker_ids, canonical_hashes)
    report = _render(alpha, share, stats, verdicts, gamma, n_ties, theory_at_gamma,
                     release_lead, externality, eclipse)
    (out_dir / "report.md").write_text(report)
    print(report)
    return 0 if all(v["pass"] for v in verdicts) else 1


def _externality_metrics(found, chain, h2m, attacker_ids, canonical_hashes) -> dict:
    """The literature-grounded externality/detection block (Lee & Kim 2025,
    Li 2020, Kawaguchi & Noda 2021, Gervais 2016) — see
    scripts/selfish_externality.py for each metric's source and meaning."""
    hourly = hourly_series(found, canonical_hashes)
    periods = detect_selfish_periods(hourly)
    depths = reorg_contest_depths(found, h2m, canonical_hashes)
    runs = attacker_runs(chain, h2m, attacker_ids, found, canonical_hashes)
    depth_hist = {}
    for d in depths:
        depth_hist[d] = depth_hist.get(d, 0) + 1
    sig1 = sum(1 for r in runs if r["length"] >= 2 and r["orphans"] == r["length"] - 1)
    sig2 = sum(1 for r in runs if r["length"] >= 2 and r["orphans"] == r["length"] - 2)
    run_hist = {}
    for r in runs:
        run_hist[r["length"]] = run_hist.get(r["length"], 0) + 1
    return {
        "hourly": hourly,
        "periods": periods,
        "depth_hist": depth_hist,
        "multi_depth_share": (sum(1 for d in depths if d > 1) / len(depths)) if depths else 0.0,
        "runs": runs,
        "run_length_hist": run_hist,
        "release_sig_lead1": sig1,
        "release_sig_lead2": sig2,
        "msb": msb_scores(chain, h2m),
        "spec_finds": spec([h["finds"] for h in hourly]),
        "spec_canonical": spec([h["canonical"] for h in hourly]),
        "canonical_total": sum(h["canonical"] for h in hourly),
    }


def _render(alpha, share, stats, verdicts, gamma=0.0, n_ties=0, theory_at_gamma=None,
            release_lead=1, externality=None, eclipse=None) -> str:
    if theory_at_gamma is None:
        theory_at_gamma = es_revenue_share(alpha, gamma)
    lines = ["# Selfish-mining analysis", "",
             f"- alpha: {alpha:.3f}",
             f"- release_lead: {release_lead} ({'textbook Eyal-Sirer' if release_lead == 1 else 'conservative cash-out'})",
             f"- attacker canonical share (measured): {share:.3f}"]
    if eclipse:
        controlled, alpha_eff = eclipse
        lines += [f"- eclipse composition: yes",
                  f"- CONTROLLED canonical share (attacker + victims): {controlled:.3f}",
                  f"- alpha_eff (attacker + victims / total): {alpha_eff:.3f}",
                  f"- modified (cash-on-lead) theory at alpha_eff: {mod_revenue_share(alpha_eff, 0.0):.3f}"]
    lines += [f"- honest baseline (alpha): {alpha:.3f}",
              f"- Eyal-Sirer gamma=0 theory: {es_revenue_share(alpha, 0.0):.3f}"]
    if release_lead >= 2:
        lines.append(f"- modified lead-2 theory gamma=0: {mod_revenue_share(alpha, 0.0):.3f}")
    lines += [f"- realized gamma: {gamma:.3f}",
              f"- num ties: {n_ties}",
              f"- theory at measured gamma: {theory_at_gamma:.3f}",
              f"- attacker orphan rate: {stats['attacker_orphan_rate']:.3f}",
              f"- network orphan rate: {stats['network_orphan_rate']:.3f}",
              "", "## Verdicts", ""]
    for v in verdicts:
        detail = f"band {v['band'][0]:.3f}..{v['band'][1]:.3f}" if "band" in v \
            else f"theory {v['theory']:.3f}" if "theory" in v \
            else f"baseline {v['baseline']:.3f}" if "baseline" in v else ""
        lines.append(f"- {'PASS' if v['pass'] else 'FAIL'}: {v['name']} (measured {v['measured']:.3f}"
                     + (f", {detail})" if detail else ")"))
    if externality:
        ex = externality
        lines += ["", "## Externality & detection", "",
                  f"- canonical blocks (total): {ex['canonical_total']}",
                  f"- SpEC hourly finds (p5/mean): {ex['spec_finds']:.3f}",
                  f"- SpEC hourly canonical throughput: {ex['spec_canonical']:.3f}",
                  f"- selfish periods detected (Alg.1, tau=2/h): "
                  f"{len(ex['periods'])} -> {ex['periods'] if ex['periods'] else 'none'}",
                  f"- reorg contest depths: {ex['depth_hist']} "
                  f"(multi-depth share {ex['multi_depth_share']:.2f})",
                  f"- attacker runs: {len(ex['runs'])} (length hist {ex['run_length_hist']}); "
                  f"release signature among runs >=2: "
                  f"y=x-1 (lead-1): {ex['release_sig_lead1']}, "
                  f"y=x-2 (lead-2): {ex['release_sig_lead2']}",
                  "- MSB (consecutive-wins z-score, Li 2020; >2 flags withholding):"]
        for m, s in sorted(ex["msb"].items()):
            lines.append(f"  - {m}: observed {s['observed']} vs expected {s['expected']:.1f}"
                         f" -> z = {s['z']:+.2f}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
