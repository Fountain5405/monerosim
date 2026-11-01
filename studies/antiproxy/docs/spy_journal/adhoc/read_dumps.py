#!/usr/bin/env python3
"""User peer-list dump read for the wl70 adversary cells: spy entry counts,
spy/honest entry ages, newest-20 cut composition (clauses (b) and (c)).
Committed 2026-10-28 (E59/E60 quote its output; until now it lived in /tmp
on the boxes)."""
import json
import statistics
import sys
import yaml
from pathlib import Path
from collections import Counter

run = Path(sys.argv[1])
H = yaml.safe_load(open(run / "shadow_agents.yaml"))["hosts"]
spy_ip = {v["ip_addr"] for k, v in H.items() if k.startswith("spy")}

rows_out = []
for f in sorted((run / "daemon_logs").glob("monero-user-*/peerlist_dump.jsonl")):
    rows = [json.loads(l) for l in open(f)]
    if not rows:
        continue
    r = rows[-1]
    t = r["t"]
    ent = [(e[0].rsplit(":", 1)[0], e[1]) for e in r["white"]]
    sp = [a for a, ls in ent if a in spy_ip]
    ho = [ls for a, ls in ent if a not in spy_ip]
    spa = [ls for a, ls in ent if a in spy_ip]
    newest = sorted(ent, key=lambda e: -e[1])[:20]
    rows_out.append({
        "node": f.parent.name, "white": len(ent), "spy": len(sp),
        "spy_age_med": (t - statistics.median(spa)) if spa else None,
        "honest_age_med": (t - statistics.median(ho)) if ho else None,
        "honest_age_p10": (t - sorted(ho)[len(ho)//10]) if ho else None,
        "honest_age_p90": (t - sorted(ho)[-max(1, len(ho)//10)]) if ho else None,
        "newest20_spy": sum(1 for a, _ in newest if a in spy_ip),
    })

n = len(rows_out)
whites = [r["white"] for r in rows_out]
spies = [r["spy"] for r in rows_out]
sp_age = [r["spy_age_med"] for r in rows_out if r["spy_age_med"] is not None]
ho_med = [r["honest_age_med"] for r in rows_out if r["honest_age_med"] is not None]
ho_p10 = [r["honest_age_p10"] for r in rows_out if r["honest_age_p10"] is not None]
ho_p90 = [r["honest_age_p90"] for r in rows_out if r["honest_age_p90"] is not None]
n20 = [r["newest20_spy"] for r in rows_out]
def rng(v): return "None" if not v else "%.0f-%.0f (med %.0f)" % (min(v), max(v), statistics.median(v))
print(json.dumps({
    "run": str(run), "users": n,
    "white_size": "%d-%d" % (min(whites), max(whites)),
    "spy_entries": "%d-%d (med %.0f) of white" % (min(spies), max(spies), statistics.median(spies)),
    "spy_entry_age_med_s": rng(sp_age),
    "honest_age_med_s": rng(ho_med),
    "honest_age_p10_s": rng(ho_p10),
    "honest_age_p90_s": rng(ho_p90),
    "newest20_spy": "%d-%d (med %.1f)" % (min(n20), max(n20), statistics.median(n20)),
}, indent=2))
