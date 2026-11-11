#!/usr/bin/env python3
"""Classify enforcement refusals as spy vs honest for one archive (run on the box)."""
import collections
import glob
import re
import sys

d = sys.argv[1]
agents = open(f"{d}/shadow_output/shadow_agents.yaml").read()
spy_ips = set(re.findall(r"^\s+spy-[a-z0-9-]+:\n(?:.*\n)*?\s+ip_addr: (\S+)", agents, re.M))
if not spy_ips:
    blocks = re.findall(r"^\s+(\S+):\n((?:[ \t].*\n|\n)*)", agents, re.M)
    spy_ips = {m for name, body in blocks if name.startswith("spy")
               for m in re.findall(r"ip_addr: (\S+)", body)}
cnt = collections.Counter()
tot = 0
hosts = set()
for f in glob.glob(f"{d}/shadow.data/hosts/*/monerod-sim.1000.stdout"):
    try:
        txt = open(f, errors="replace").read()
    except OSError:
        continue
    for adr in re.findall(r"refusing white insertion for (\d+\.\d+\.\d+\.\d+)", txt):
        tot += 1
        hosts.add(f.split("/")[-2])
        cnt["spy" if adr in spy_ips else "HONEST"] += 1
print(f"P77 refusals={tot} hosts={len(hosts)} spy={cnt['spy']} HONEST={cnt['HONEST']}")
print(f"spy_ips_found={len(spy_ips)}")
