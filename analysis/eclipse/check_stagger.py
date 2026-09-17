#!/usr/bin/env python3
"""Confirm attacker onboarding is staggered in the expanded config."""
import sys
import yaml

cfg = yaml.safe_load(open(sys.argv[1]))
agents = cfg.get("agents", {})
sts = []
for name, a in agents.items():
    if not name.startswith("relay-"):
        continue
    role = ((a or {}).get("attributes") or {}).get("eclipse_role")
    if role != "attacker":
        continue
    st = a.get("start_time", 0)
    # normalize to seconds
    if isinstance(st, str):
        s = st.strip()
        if s.endswith("s"):
            st = int(float(s[:-1]))
        elif s.endswith("m"):
            st = int(float(s[:-1]) * 60)
        elif s.endswith("h"):
            st = int(float(s[:-1]) * 3600)
        else:
            st = int(float(s))
    sts.append(int(st))
sts.sort()
n = len(sts)
print("attacker agents: %d" % n)
print("start_time min=%ss max=%ss (%.0f min)" % (sts[0], sts[-1], sts[-1] / 60))
# distribution: how many up by each 20-min mark
for m in range(0, int(sts[-1] / 60) + 21, 20):
    c = sum(1 for s in sts if s <= m * 60)
    print("  by %3dm: %4d attackers up" % (m, c))
print("all-at-zero?" , "YES (BAD — would OOM)" if sts[-1] == 0 else "no (staggered, good)")
