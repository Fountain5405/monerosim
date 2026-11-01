#!/bin/bash
# check_paths.sh [--wait S] <box> <spec> <cell>: block propagation paths in a slow / gamma cell from the
# daemons' "Received NOTIFY_NEW_FLUFFY_BLOCK <id>" lines: for blocks found by honest-001 and honest-002,
# when (median s after finding) and from which peer each other host first received them, plus the
# per-host delivery sources. A joined chain shows honest-002's blocks reaching honest-001 at the
# chain's latency and honest-001's reaching honest-002 the same way; an attacker bridge delivering
# honest blocks means a leak.
[ "${1:-}" = "--wait" ] && { sleep "${2:-1500}"; shift 2; }
box=$1; spec=$2; cell=$3
timeout 300 ssh -o BatchMode=yes $box "cd ~/monerosim; d=\$(ls -dt archived_runs/2*_${spec}__$cell/ 2>/dev/null | head -1)
[ -n \"\$d\" ] || { echo 'no run dir'; exit 0; }
echo \"run: \$(basename \$d)\"; grep -oE 'Progress: [0-9]+%.*realtime: [0-9:]+' \$d/shadow_run.log | tail -1
echo \"monerod: \$(pgrep -u \$(id -un) -c monerod)  avail GiB: \$(free -g | awk '/Mem:/{print \$7}')\"
venv/bin/python - \"\$d\" <<'PY'
import sys,re,glob,os,yaml
from datetime import datetime
d=sys.argv[1]; H=f\"{d}/shadow.data/hosts\"
ipname={v.get(\"ip_addr\"):h for h,v in yaml.safe_load(open(f\"{d}/shadow_agents.yaml\"))[\"hosts\"].items()}
def log(h):
    fs=sorted(glob.glob(f\"{H}/{h}/monerod*.stdout\"), key=os.path.getsize); return fs[-1] if fs else None
ts=lambda line: datetime.strptime(line[:23], \"%Y-%m-%d %H:%M:%S.%f\")
def recv(h):
    out={}; f=log(h)
    if not f: return out
    for line in open(f, errors=\"replace\"):
        if \"Received NOTIFY_NEW_FLUFFY_BLOCK\" in line:
            m=re.search(r\"\\[([\\d.]+):\\d+ (INC|OUT)\\].*<([0-9a-f]{64})>\", line)
            if m and m.group(3) not in out:
                try: out[m.group(3)]=(ts(line), ipname.get(m.group(1), m.group(1)))
                except ValueError: pass
    return out
def found(h):
    out={}; f=log(h)
    if not f: return out
    for line in open(f, errors=\"replace\"):
        if \"Found block\" in line:
            m=re.search(r\"<([0-9a-f]{64})>\", line)
            if m:
                try: out[m.group(1)]=ts(line)
                except ValueError: pass
    return out
hosts=[h for h in sorted(os.listdir(H)) if h.startswith((\"honest\",\"attacker-bridge\",\"relay\",\"monero-seed-001\"))]
R={h:recv(h) for h in hosts}
for src in (\"honest-001\",\"honest-002\"):
    F=found(src); print(f\"blocks found by {src}: {len(F)}\")
    for dst in hosts:
        if dst==src: continue
        rows=sorted((R[dst][b][0]-t).total_seconds() for b,t in F.items() if b in R[dst])
        froms={}
        for b in F:
            if b in R[dst]: froms[R[dst][b][1]]=froms.get(R[dst][b][1],0)+1
        print(f\"  -> {dst:18s} \" + (f\"n={len(rows):3d} median {rows[len(rows)//2]:6.2f} s (min {rows[0]:5.2f} max {rows[-1]:6.2f}) from {froms}\" if rows else \"none\"))
for h in hosts:
    c={}
    for b,(t,frm) in R[h].items(): c[frm]=c.get(frm,0)+1
    print(f\"{h:18s} receives from: {dict(sorted(c.items(), key=lambda x:-x[1]))}\")
PY"
