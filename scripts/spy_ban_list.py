#!/usr/bin/env python3
"""Write a monerod --ban-list file holding the spies' /24s for a config.

Spy IPs are only known once monerosim has placed the hosts, so this runs a
dry generation of the expanded config into a scratch directory, with
shared_dir and daemon_data_dir moved there too (the replica spec's §9 recipe;
never generate into the live /tmp/monerosim dirs on a shared box), reads
shadow_agents.yaml, and writes one `a.b.c.0/24` line per spy /24. Placement is
deterministic, so adding the --ban-list option afterwards does not move the
spies; spy_estimators-style checks can confirm it on the archived run.

Spies are agents whose id starts with --prefix (default `spy`).

--coverage F lists only a fraction F of the spy /24s, as the real list names the
dense fleet and only part of a diversified tail (ban list v2: 14 dense /24s and
322 /24s of 1-3 IPs; xmrnetscan counts hidden spies beyond it). The /24s holding
the most spies are listed first; ties are broken by a shuffle seeded with --seed,
so the same config, coverage and seed give the same list. The default, 1.0, lists
every spy /24.

Usage:
    python3 scripts/spy_ban_list.py <expanded_config.yaml> -o <ban_list.txt> [--prefix spy]
                                    [--coverage 0.5 --seed 12345]
"""

import argparse
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
MONEROSIM_BIN = REPO / "target" / "release" / "monerosim"


def subnet_key(subnet):
    return tuple(int(x) for x in subnet.split("/")[0].split("."))


def listed(counts, coverage=1.0, seed=0):
    """The /24s a ban list with this coverage names, in address order.

    counts: {"a.b.c.0/24": spies in it}. The round(coverage * n) densest /24s, ties by a seeded shuffle."""
    if not 0 < coverage <= 1:
        raise ValueError(f"coverage must be in (0, 1], got {coverage}")
    subnets = sorted(counts, key=subnet_key)
    rng = random.Random(seed)
    tiebreak = {s: rng.random() for s in subnets}
    k = max(1, round(coverage * len(subnets)))
    return sorted(sorted(subnets, key=lambda s: (-counts[s], tiebreak[s]))[:k], key=subnet_key)


def spy_subnets(config_path, prefix="spy"):
    """Sorted spy /24s of a config (every one of them)."""
    return sorted(spy_subnet_counts(config_path, prefix), key=subnet_key)


def spy_subnet_counts(config_path, prefix="spy"):
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    scratch = Path(tempfile.mkdtemp(prefix="spy_ban_list_"))
    try:
        cfg.setdefault("general", {})
        cfg["general"]["shared_dir"] = str(scratch / "shared")
        cfg["general"]["daemon_data_dir"] = str(scratch / "data")
        dry = scratch / "config.yaml"
        with open(dry, "w") as f:
            yaml.safe_dump(cfg, f, sort_keys=False)
        out = scratch / "out"
        r = subprocess.run([str(MONEROSIM_BIN), "--config", str(dry), "--output", str(out)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"monerosim generation failed:\n{r.stderr[-2000:]}")
        with open(out / "shadow_agents.yaml") as f:
            hosts = yaml.safe_load(f)["hosts"]
        counts = {}
        for name, h in hosts.items():
            if name.startswith(prefix) and h.get("ip_addr"):
                a, b, c, _ = h["ip_addr"].split(".")
                subnet = f"{a}.{b}.{c}.0/24"
                counts[subnet] = counts.get(subnet, 0) + 1
        return counts
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", help="expanded monerosim config (scripts/generate_config.py output)")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--prefix", default="spy")
    ap.add_argument("--coverage", type=float, default=1.0,
                    help="fraction of the spy /24s to list, densest first (default 1.0 = all)")
    ap.add_argument("--seed", type=int, default=0, help="breaks ties between equally dense /24s")
    args = ap.parse_args(argv)
    counts = spy_subnet_counts(args.config, args.prefix)
    if not counts:
        sys.exit(f"No hosts whose id starts with '{args.prefix}'")
    if not 0 < args.coverage <= 1:
        ap.error("--coverage must be in (0, 1]")
    subnets = listed(counts, args.coverage, args.seed)
    Path(args.output).write_text("".join(s + "\n" for s in subnets))
    print(f"{len(subnets)} of {len(counts)} spy /24s -> {args.output}: {', '.join(subnets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
