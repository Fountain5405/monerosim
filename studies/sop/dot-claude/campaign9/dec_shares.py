"""Per-reveal weight accounting at an honest node, from its SIM-SoP-DEC records.
For each fork point (hf) keep the LAST decision; call it an attacker reveal when most alt
blocks were seen more than d after the main block at their height (late). Report, over
those reveals: blocks and embedded shares per side, pool shares counted per side, the
daemon's object counts (n_alt / n_main), regime and how often the alt branch won.
Usage: dec_shares.py DAEMON_STDOUT [DAEMON_STDOUT...]"""
import json
import statistics as st
import sys

for path in sys.argv[1:]:
    last = {}
    with open(path, errors="replace") as fh:
        for ln in fh:
            i = ln.find("SIM-SoP-DEC {")
            if i < 0:
                continue
            try:
                r = json.loads(ln[i + len("SIM-SoP-DEC "):])
            except ValueError:
                continue
            if r.get("reinsert"):
                continue
            last[r["hf"]] = r
    rev = []
    for hf, r in last.items():
        d = r["d_ms"]
        alt = r["alt"]
        late = sum(1 for b in alt if b.get("seen") is not None and b.get("ref") is not None and b["seen"] - b["ref"] > d)
        if not alt or late * 2 < len(alt):
            continue
        rev.append(r)
    print(f"== {path.split('/hosts/')[-1] if '/hosts/' in path else path}: {len(last)} forks judged, {len(rev)} late-alt (attacker reveal) forks")
    if not rev:
        continue
    def m(f):
        return st.mean(f(r) for r in rev)
    print(f"  blocks alt/main: {m(lambda r: len(r['alt'])):.2f} / {m(lambda r: len(r['main'])):.2f}")
    print(f"  embedded shares per block alt/main: "
          f"{sum(sum(b['n_sh'] for b in r['alt']) for r in rev) / sum(len(r['alt']) for r in rev):.2f} / "
          f"{sum(sum(b['n_sh'] for b in r['main']) for r in rev) / max(1, sum(len(r['main']) for r in rev)):.2f}")
    print(f"  pool counted alt/main: {m(lambda r: r['pool_alt_counted']):.2f} / {m(lambda r: r['pool_main_counted']):.2f}")
    print(f"  n_alt / n_main: {m(lambda r: r['n_alt']):.1f} / {m(lambda r: r['n_main']):.1f}")
    regimes = {}
    for r in rev:
        regimes[r["regime"]] = regimes.get(r["regime"], 0) + 1
    print(f"  regimes: {regimes}")
    won = sum(1 for r in rev if int(r["w_alt"]) > int(r["w_main"]))
    print(f"  alt heavier (w_alt > w_main): {won} of {len(rev)}")
    # objects per block-interval of work: blocks + embedded shares + pool counted, per side, per block
    a_obj = sum(len(r['alt']) + sum(b['n_sh'] for b in r['alt']) + r['pool_alt_counted'] for r in rev)
    m_obj = sum(len(r['main']) + sum(b['n_sh'] for b in r['main']) + r['pool_main_counted'] for r in rev)
    a_bl = sum(len(r['alt']) for r in rev)
    m_bl = sum(len(r['main']) for r in rev)
    print(f"  counted objects per block alt/main (blocks + embedded + pool): {a_obj / a_bl:.2f} / {m_obj / max(1, m_bl):.2f}")
