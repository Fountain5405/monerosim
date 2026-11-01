#!/usr/bin/env python3
"""Parse a monerod log stream (stdin, oldest file first; tab-separated lines
"ts  [thread]  LEVEL  category  src:line  message") into one TSV row per event.

Rows written to argv[1]:
  main  height  hash  t_added_ms  proc_ms  weight
  alt   height  hash  t_added_ms  -        -
  reorg height  -     t_ms        -        -
  txmin minute_epoch_s  count  -  -  -      (txpool "Transaction added to pool" lines per minute)
main: "+++++ BLOCK SUCCESSFULLY ADDED" then id / HEIGHT lines, closed by the
--show-time-stats line "Height: N coinbase weight: c cumm: W p/t: P (...)":
W = block weight (bytes), P = block processing time (ms) at this node.
"""
import sys, re
from datetime import datetime, timezone

def ems(s):
    return int(datetime.strptime(s[:23], "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc).timestamp() * 1000)

out = open(sys.argv[1], "w")
cur = None
txmin = {}
counts = {"main": 0, "alt": 0, "reorg": 0}
for raw in sys.stdin.buffer:
    line = raw.decode("utf-8", "replace").rstrip("\n")
    f = line.split("\t", 5)
    if len(f) < 6 or len(f[0]) < 23:
        continue
    ts, msg = f[0], f[5]
    if "Transaction added to pool" in msg:
        try:
            k = ems(ts) // 60000
            txmin[k] = txmin.get(k, 0) + 1
        except ValueError:
            pass
        continue
    if "BLOCK SUCCESSFULLY ADDED" in msg:
        cur = {"kind": "main", "t": ems(ts)}; continue
    if "BLOCK ADDED AS ALTERNATIVE" in msg:
        h = re.search(r"HEIGHT (\d+)", msg)
        cur = {"kind": "alt", "t": ems(ts), "height": h.group(1) if h else ""}; continue
    if "REORGANIZE SUCCESS" in msg:
        h = re.search(r"height:?\s*(\d+)", msg)
        out.write(f"reorg\t{h.group(1) if h else ''}\t-\t{ems(ts)}\t-\t-\n"); counts["reorg"] += 1
        continue
    if cur is None:
        continue
    m = re.match(r"id:\s*<([0-9a-f]{64})>", msg)
    if m:
        cur["hash"] = m.group(1)
        if cur["kind"] == "alt":
            out.write(f"alt\t{cur.get('height','')}\t{cur['hash']}\t{cur['t']}\t-\t-\n"); counts["alt"] += 1
            cur = None
        continue
    m = re.match(r"HEIGHT (\d+), difficulty", msg)
    if m:
        cur["height"] = m.group(1); continue
    m = re.match(r"Height: (\d+) coinbase weight: \d+ cumm: (\d+) p/t: (\d+)", msg)
    if m and cur.get("hash"):
        out.write(f"main\t{cur.get('height', m.group(1))}\t{cur['hash']}\t{cur['t']}\t{m.group(3)}\t{m.group(2)}\n"); counts["main"] += 1
        cur = None
for k, c in sorted(txmin.items()):
    out.write(f"txmin\t{k*60}\t{c}\t-\t-\t-\n")
out.close()
print(f"rows: {counts}, tx minutes: {len(txmin)}", file=sys.stderr)
