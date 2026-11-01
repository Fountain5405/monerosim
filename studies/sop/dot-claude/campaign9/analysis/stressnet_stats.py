#!/usr/bin/env python3
"""Join two nodes' block-event TSVs (stressnet_parse.py output) and report propagation stats.
Usage: stressnet_stats.py A.tsv B.tsv SINCE_EPOCH_MS
Live blocks = main rows on both nodes, added at or after SINCE, with |t_A - t_B| < 600 s.
"""
import sys, statistics as st

def load(p, since):
    main, alt, reorg, tx = {}, 0, 0, []
    for line in open(p):
        f = line.rstrip("\n").split("\t")
        if f[0] == "main" and int(f[3]) >= since:
            main[f[2]] = (int(f[1]), int(f[3]), int(f[4]), int(f[5]))
        elif f[0] == "alt" and int(f[3]) >= since:
            alt += 1
        elif f[0] == "reorg" and int(f[3]) >= since:
            reorg += 1
        elif f[0] == "txmin" and int(f[1]) * 1000 >= since:
            tx.append(int(f[2]))
    return main, alt, reorg, tx

def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))] if xs else None

A, B, since = sys.argv[1], sys.argv[2], int(sys.argv[3])
ma, alta, reoa, txa = load(A, since)
mb, altb, reob, txb = load(B, since)
common = [h for h in ma if h in mb and abs(ma[h][1] - mb[h][1]) < 600_000]
print(f"live window from {since}: A main {len(ma)} alt {alta} reorg {reoa}; B main {len(mb)} alt {altb} reorg {reob}; common live {len(common)}")
if not common:
    sys.exit()
hs = sorted(ma[h][0] for h in common)
span_h = (max(ma[h][1] for h in common) - min(ma[h][1] for h in common)) / 3.6e6
print(f"heights {hs[0]}..{hs[-1]}, {span_h:.0f} h, {len(common) / span_h:.1f} blocks/h")

dt = [mb[h][1] - ma[h][1] for h in common]                  # B added minus A added (ms)
arr = [(mb[h][1] - mb[h][2]) - (ma[h][1] - ma[h][2]) for h in common]   # arrival-corrected
ad = [abs(x) for x in dt]
print("\n| measure | median | p90 | p99 | max |")
print("|---|---|---|---|---|")
print(f"| |added B - added A| ms | {q(ad,.5)} | {q(ad,.9)} | {q(ad,.99)} | {max(ad)} |")
print(f"| |arrival B - arrival A| ms (added minus processing) | {q([abs(x) for x in arr],.5)} | {q([abs(x) for x in arr],.9)} | {q([abs(x) for x in arr],.99)} | {max(abs(x) for x in arr)} |")
print(f"| processing ms, A | {q([ma[h][2] for h in common],.5)} | {q([ma[h][2] for h in common],.9)} | {q([ma[h][2] for h in common],.99)} | {max(ma[h][2] for h in common)} |")
print(f"| processing ms, B | {q([mb[h][2] for h in common],.5)} | {q([mb[h][2] for h in common],.9)} | {q([mb[h][2] for h in common],.99)} | {max(mb[h][2] for h in common)} |")
w = [ma[h][3] for h in common]
print(f"| block weight bytes | {q(w,.5)} | {q(w,.9)} | {q(w,.99)} | {max(w)} |")
print(f"\nB first (dt > 0 means A added first): A first in {sum(1 for x in dt if x > 0)}, B first in {sum(1 for x in dt if x < 0)}, same ms {sum(1 for x in dt if x == 0)}")
print(f"gaps over 1 s: {sum(1 for x in ad if x > 1000)}, over 2 s: {sum(1 for x in ad if x > 2000)}, over 5 s: {sum(1 for x in ad if x > 5000)}, over 10 s: {sum(1 for x in ad if x > 10000)}")

print("\n| block weight | blocks | processing ms A median / p90 / max | processing ms B median / p90 / max | |added gap| ms median / p90 / max |")
print("|---|---|---|---|---|")
bins = [(0, 10_000), (10_000, 100_000), (100_000, 300_000), (300_000, 1_000_000), (1_000_000, 10**12)]
for lo, hi in bins:
    sel = [h for h in common if lo <= ma[h][3] < hi]
    if not sel:
        continue
    pa = [ma[h][2] for h in sel]; pb = [mb[h][2] for h in sel]; g = [abs(mb[h][1] - ma[h][1]) for h in sel]
    print(f"| {lo//1000}-{hi//1000 if hi < 10**12 else 'inf'} kB | {len(sel)} | {q(pa,.5)} / {q(pa,.9)} / {max(pa)} | {q(pb,.5)} / {q(pb,.9)} / {max(pb)} | {q(g,.5)} / {q(g,.9)} / {max(g)} |")
for tag, tx in (("A", txa), ("B", txb)):
    if tx:
        print(f"\ntx added to pool per minute, {tag} (minutes with any): median {q(tx,.5)}, p90 {q(tx,.9)}, max {max(tx)}, minutes {len(tx)}")
