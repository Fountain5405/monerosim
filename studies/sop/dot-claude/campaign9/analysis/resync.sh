#!/bin/bash
# Re-run run_lane.sync_run for one finished cell on its own lane box (pool subdir = hostname).
# Usage: resync.sh <box> <spec> <cell>
box=$1; spec=$2; cell=$3
timeout 1200 ssh -o BatchMode=yes $box "cd ~/monerosim
d=\$(ls -dt archived_runs/2*_${spec}__${cell}/ 2>/dev/null | head -1); d=\${d%/}
[ -n \"\$d\" ] || { echo 'no run dir'; exit 1; }
venv/bin/python -c \"import sys; sys.path.insert(0, '.claude/campaign9'); import run_lane; run_lane.sync_run('resync', '$spec', '$cell', '\$PWD/\$d')\"
tail -n 1 .claude/campaign9/queue.log | cut -c1-170"
