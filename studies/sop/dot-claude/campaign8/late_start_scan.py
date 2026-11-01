#!/usr/bin/env python3
"""h_0 for late starters. For each node with SoP decisions in archived SoP
runs, find the tip it came online at: its own tip when it first logged "You
are now synchronized with the network" (fallback: the network's tip when
its process started). An --offline node (the attacker's private miner)
counts as synchronized from startup and never logs the banner: it came
online at startup, with its DB tip. In v1/v2 logs it shows as a node that
mined without a banner, since monerod mines only once synchronized
(mined_before_banner counts nodes that mined before their banner: expect
0). Re-judge the decisions with h_0 = that tip (objective before the node
came online, or if it never did) against the after-queue build's test
(h_0 = DB tip, strict h_f), and count regime and outcome changes;
"certify" compares the decisions as run with the spec's rules.

The after-queue build logs "SIM-SoP: online, h0=N (first sync|--offline:
synchronized at startup, DB tip D)" when the node comes online, and its v3
records log "online". Where that line exists the h0 check verifies it: N
must equal the tip at the banner (or D for an --offline node, which logs no
banner), at most one such line per node, and every decision must log D and
online false before the line, N and online true after it. A node without
the line must log online false throughout.

Every line of a multi-line monerod message carries its own timestamp, so the
"HEIGHT n, difficulty:" line after "+++++ BLOCK SUCCESSFULLY ADDED" is a
prefixed line of its own.

Usage: late_start_scan.py [run dir names under archived_runs, or paths]"""
import re
import statistics
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO = Path("/scratch/monerosim_dev/monerosim")
sys.path.insert(0, str(REPO))
from scripts.sop_oracle import decide, parse_log_line  # noqa: E402

TS = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+)")
HEIGHT = re.compile(r"\tHEIGHT (\d+), difficulty:")
ONLINE = re.compile(r"SIM-SoP: online, h0=(\d+) \((first sync|--offline: synchronized at startup), DB tip (\d+)\)")
H_STOP = 1050           # stop reading once the node's main chain passes this
LINE_CAP = 20_000_000   # safety cap per log


def ts(line):
    m = TS.match(line)
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f").timestamp() if m else None


def scan(log):
    start = sync = mined = None
    pend = capped = False
    adds, decs, online = [], [], []
    with open(log, errors="replace") as f:
        for n, line in enumerate(f):
            if start is None:
                start = ts(line)
            if pend:
                m = HEIGHT.search(line)
                if m:
                    pend = False
                    h = int(m.group(1))
                    t = ts(line)
                    adds.append((t, h))
                    if mined is None and "\t[miner " in line:
                        mined = t   # added by this node's own miner thread
                    if h > H_STOP:
                        break
                    continue
            if "BLOCK SUCCESSFULLY ADDED" in line:
                pend = True
            elif sync is None and "You are now synchronized" in line:
                sync = ts(line)
            elif mined is None and "Found block " in line and " at height " in line:
                mined = ts(line)
            elif "SIM-SoP: online, h0=" in line:
                m = ONLINE.search(line)
                if m:
                    online.append((n, int(m.group(1)), m.group(2), int(m.group(3))))
            elif "SIM-SoP-DEC" in line:
                rec = parse_log_line(line)
                if rec is not None:
                    decs.append((ts(line), rec, n))
            if n >= LINE_CAP:
                capped = True
                break
    return start, sync, adds, decs, capped, mined, online


def db_tip(v):
    # The online line logs the DB tip; before it existed h0 stayed the DB tip.
    return v[6][0][3] if v[6] else v[3][0][1]["h0"]


def judged(rec, h0):
    # v1/v2 records test h0 < hf; the spec's strict test H < hf - 1 is h0 = H + 1.
    d = decide(dict(rec, h0=h0 + (1 if rec.get("v", 1) < 3 else 0)))
    return d["regime"], d["expected"]


def check_online(tot, h0bad, run, host, sy, adds, decs, ev):
    """The after-queue build's own h0 event against the log around it."""
    n_ev, h0_ev, why, db_ev = ev[0]
    tot["online_lines"] += 1
    tot["online_lines_extra"] += len(ev) - 1
    if why == "first sync":
        want = max([h for t, h in adds if t is not None and sy is not None and t <= sy] + [db_ev])
        reason_ok = sy is not None
    else:   # --offline: synchronized at startup, never a banner
        want = db_ev
        reason_ok = sy is None
    tot["online_" + ("sync" if why == "first sync" else "offline")] += 1
    tot["online_raised"] += h0_ev > db_ev
    if h0_ev != want or not reason_ok:
        tot["online_bad"] += 1
        h0bad.append((run, host, why, f"h0={h0_ev}", f"db={db_ev}", f"tip_at_banner={want}",
                      f"banner={'yes' if sy is not None else 'no'}"))
    for _, rec, n in decs:
        after = n > n_ev
        ok = rec["h0"] == (h0_ev if after else db_ev)
        tot["h0_logged_ok" if ok else "h0_logged_bad"] += 1
        if not ok:
            h0bad.append((run, host, "decision", f"logged h0={rec['h0']}", f"hf={rec['hf']}",
                          f"want={h0_ev if after else db_ev}"))
        flag_check(tot, h0bad, run, host, rec, after)


def flag_check(tot, h0bad, run, host, rec, want):
    """A v3 record logs whether its node had come online."""
    if rec.get("v", 1) < 3:
        return
    ok = rec.get("online") is want
    tot["online_flag_ok" if ok else "online_flag_bad"] += 1
    if not ok:
        h0bad.append((run, host, "decision", f"logged online={rec.get('online')}", f"hf={rec['hf']}",
                      f"want={want}"))


def main():
    runs = sorted(REPO / "archived_runs" / a for a in sys.argv[1:]) or sorted(
        p for p in (REPO / "archived_runs").iterdir()
        if "sop" in p.name.lower() and (p / "daemon_logs").is_dir())
    tot = Counter()
    hosts = Counter()
    fb = {}
    rows = []
    nobanner, inrange, specdiff, h0bad = [], [], [], []
    t0 = time.time()
    for i, rd in enumerate(runs):
        data = {lg.parent.name: scan(lg) for lg in sorted(rd.glob("daemon_logs/*/bitmonero.log"))}
        for host, v in data.items():
            st, sy, adds, decs, _, mined, ev = v
            # monerod mines only once synchronized: expect 0
            tot["mined_before_banner"] += mined is not None and sy is not None and mined < sy
            if ev:
                check_online(tot, h0bad, rd.name, host, sy, adds, decs, ev)
                continue
            if any(rec.get("v", 1) >= 3 for _, rec, _n in decs) and (sy is not None or mined is not None):
                tot["online_line_missing"] += 1
                h0bad.append((rd.name, host, "no online line", f"banner={'yes' if sy is not None else 'no'}",
                              f"mined={'yes' if mined is not None else 'no'}"))
            for _, rec, _n in decs:   # not online by the daemon's own account
                flag_check(tot, h0bad, rd.name, host, rec, False)
        if not any(v[3] for v in data.values()):
            continue
        n = len(data)
        tot[f"runs_{n}d"] += 1
        tot["capped_logs"] += sum(v[4] for v in data.values())
        t_run = min(v[0] for v in data.values() if v[0] is not None)
        first = {}
        for host_, v in data.items():
            if "attacker-miner" in host_:  # private chain: not the network's tip
                continue
            for t, h in v[2]:
                if t is not None and t < first.get(h, float("inf")):
                    first[h] = t
        dbs = [db_tip(v) for v in data.values() if v[3]]
        fb_t = first.get(min(dbs) + 1)
        if fb_t is not None:
            fb.setdefault(n, []).append(fb_t - t_run)
        late_here = 0
        for host, v in data.items():
            st, sy, adds, decs, _, mined, ev = v
            if not decs:
                continue
            db = db_tip(v)
            tot[f"nodes_{n}d"] += 1
            if fb_t is not None and st is not None and st > fb_t:
                tot[f"started_after_first_block_{n}d"] += 1
            # An --offline node: synchronized from startup, no banner; only it
            # mines without one (v3 logs name it in the online line).
            offline = ev[0][2] != "first sync" if ev else (sy is None and mined is not None)
            t_on = st if offline else sy   # None: never came online
            tot["never_online"] += t_on is None
            if sy is None:
                tot["no_sync_banner"] += 1
                nobanner.append((rd.name, host, len(decs), st and st - t_run,
                                 adds[:2] and [h for _, h in adds[:2]]))
            if offline:
                tot["offline_nodes"] += 1   # online from startup, at the DB tip
                online = db
            elif sy is None:
                online = max([h for h, t in first.items() if t <= st] + [db])
            else:
                online = max([h for t, h in adds if t is not None and t <= sy] + [db])
            if online > db:
                late_here += 1
                tot[f"late_nodes_{n}d"] += 1
                tot[f"late_by_{online - db}"] += 1
                hosts[re.sub(r"[-_]?\d+$", "", host)] += 1
            for t, rec, _n in decs:
                tot["decisions"] += 1
                during = sy is not None and t is not None and t < sy
                before = t_on is None or (t is not None and t < t_on)
                tot["before_online"] += before
                # Certify: as run vs the spec's rules (strict h_f; h_0 = the tip
                # once caught up, objective before the node came online).
                # Outside this range the two agree by construction.
                Hs = 10**9 if before else online
                if rec["hf"] - 1 <= Hs and rec.get("skipped"):
                    # whole_branch reinsert: stored without judging, KEEP either way.
                    tot[("rev2_" if "rev2" in rd.name else "") + "spec_in_range_skipped"] += 1
                elif rec["hf"] - 1 <= Hs:
                    try:
                        a = decide(rec)
                        s = judged(rec, Hs)
                    except Exception:
                        tot["errors"] += 1
                    else:
                        g = "rev2_" if "rev2" in rd.name else ""
                        tot[g + "spec_in_range"] += 1
                        tot[g + "spec_regime_diff"] += a["regime"] != s[0]
                        tot[g + "spec_outcome_diff"] += a["expected"] != s[1]
                        if (a["regime"], a["expected"]) != s:
                            specdiff.append((rd.name, host, f"hf={rec['hf']}", f"db={db}",
                                             f"online={online}", (a["regime"], a["expected"]), s))
                if before:
                    tot["during_sync"] += during
                    H = 10**9
                elif online > db and rec["hf"] - 1 <= online:
                    tot["late_in_range"] += 1
                    H = online
                else:
                    continue
                try:
                    b, p = judged(rec, db), judged(rec, H)
                except Exception:
                    tot["errors"] += 1
                    continue
                tot["regime_change"] += b[0] != p[0]
                tot["outcome_change"] += b[1] != p[1]
                inrange.append((rd.name[:15], host, rec["hf"], online, rec.get("nf"),
                                rec.get("nf_main"), b, p))
                if b != p:
                    rows.append((rd.name, host, f"hf={rec['hf']}", f"db={db}",
                                 f"online={online}", "before online" if before else "late", b, p))
        tot[f"runs_with_late_{n}d"] += late_here > 0
        if (i + 1) % 40 == 0:
            print(f"... {i + 1}/{len(runs)} dirs, {time.time() - t0:.0f} s", flush=True)
    print(f"scanned {len(runs)} dirs in {time.time() - t0:.0f} s")
    for k in sorted(tot):
        print(f"{k:34} {tot[k]}")
    print("late node kinds:", dict(hosts))
    for n, v in sorted(fb.items()):
        v.sort()
        print(f"{n}d first block after start: n={len(v)} min {v[0]:.0f} s, median "
              f"{statistics.median(v):.0f} s, <30 s {sum(x < 30 for x in v)}, "
              f"<60 s {sum(x < 60 for x in v)}, <260 s {sum(x < 260 for x in v)}")
    for r in rows[:40]:
        print(*r)
    print("as run vs spec, differing (run, host, hf, db, online, as run, spec):")
    for r in specdiff[:60]:
        print("  ", *r)
    print("h0 check failures (after-queue build):")
    for r in h0bad[:60]:
        print("  ", *r)
    print("no banner (run, host, decisions, start s, first adds):")
    for r in nobanner:
        print("  ", *r)
    print("in range (run, host, hf, online, nf, nf_main, base, proposed):")
    for r in inrange:
        print("  ", *r)


if __name__ == "__main__":
    main()
