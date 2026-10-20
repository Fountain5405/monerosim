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

Usage:
    python3 scripts/spy_ban_list.py <expanded_config.yaml> -o <ban_list.txt> [--prefix spy]
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
MONEROSIM_BIN = REPO / "target" / "release" / "monerosim"


def spy_subnets(config_path, prefix="spy"):
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
        subnets = set()
        for name, h in hosts.items():
            if name.startswith(prefix) and h.get("ip_addr"):
                a, b, c, _ = h["ip_addr"].split(".")
                subnets.add(f"{a}.{b}.{c}.0/24")
        return sorted(subnets, key=lambda s: tuple(int(x) for x in s.split("/")[0].split(".")))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", help="expanded monerosim config (scripts/generate_config.py output)")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--prefix", default="spy")
    args = ap.parse_args(argv)
    subnets = spy_subnets(args.config, args.prefix)
    if not subnets:
        sys.exit(f"No hosts whose id starts with '{args.prefix}'")
    Path(args.output).write_text("".join(s + "\n" for s in subnets))
    print(f"{len(subnets)} spy /24s -> {args.output}: {', '.join(subnets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
