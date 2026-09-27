#!/usr/bin/env python3
"""Usage: venv/bin/python scripts/uncle_parents.py archived_runs/<run> [...]

For each uncle-header embedding on an honest miner, who mined the template's PARENT
(the miner's main block at H-1 at that moment) and who mined the embedded sibling
(the displaced/other block at H-1)? Tracks the node's main chain through adds and reorgs."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.selfish_mining_analysis import _attacker_ids, _honest_miner_ids, load_raw_config, parse_found_blocks, found_by_hash
RE_ID = re.compile(r"\tid:\t<([0-9a-f]+)>")
RE_H = re.compile(r"HEIGHT (\d+), difficulty")
RE_ALT = re.compile(r"BLOCK ADDED AS ALTERNATIVE ON HEIGHT (\d+)")
RE_RE = re.compile(r"REORGANIZE SUCCESS! on height: (\d+), new blockchain size: (\d+)")
RE_EMB = re.compile(r"SIM-PoP: embedding uncle header \(\d+ B\) at height (\d+)")
def scan(text, h2m, att):
    cur, alts = {}, {}
    mode = None; pend = None; out = []
    for line in text.splitlines():
        if "+++++ BLOCK SUCCESSFULLY ADDED" in line: mode, pend = "main", None; continue
        m = RE_ALT.search(line)
        if m: mode, pend, alt_h = "alt", None, int(m.group(1)); continue
        m = RE_ID.search(line)
        if m and mode:
            pend = m.group(1)
            if mode == "alt": alts.setdefault(alt_h, []).append(pend); mode = None
            continue
        m = RE_H.search(line)
        if m and mode == "main" and pend:
            cur[int(m.group(1))] = pend; mode = None; continue
        m = RE_RE.search(line)
        if m:
            lo, size = int(m.group(1)), int(m.group(2))
            # the new main blocks at lo..size-1 are the most recent alts at those heights; the
            # displaced main blocks become alts
            for h in range(lo, size):
                if alts.get(h):
                    new = alts[h][-1]
                    if h in cur and cur[h] != new: alts[h].append(cur[h])
                    cur[h] = new
            continue
        m = RE_EMB.search(line)
        if m:
            H = int(m.group(1)); p = cur.get(H - 1)
            sib = [a for a in alts.get(H - 1, []) if a != p]
            cls = lambda x: "A" if h2m.get(x) in att else ("H" if x in h2m else "?")
            out.append((H, cls(p) if p else "?", "".join(sorted(set(cls(s) for s in sib))) or "-"))
    return out
for rd in [Path(a) for a in sys.argv[1:]]:
    cfg = load_raw_config(rd / "input_config.yaml"); att = _attacker_ids(cfg); hon = sorted(_honest_miner_ids(cfg))
    h2m = found_by_hash(parse_found_blocks(rd, list(att) + hon))
    tally = {}
    for node in hon:
        for H, par, sib in scan((rd / "daemon_logs" / f"monero-{node}" / "bitmonero.log").read_text(errors="replace"), h2m, att):
            tally[(par, sib)] = tally.get((par, sib), 0) + 1
    print(rd.name[16:], "embeddings by (parent miner, sibling miners):", dict(sorted(tally.items())))
