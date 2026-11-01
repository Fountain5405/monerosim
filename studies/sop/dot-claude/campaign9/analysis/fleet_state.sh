#!/bin/bash
# Fleet state: per box the newest run's progress, process counts, memory, last queue lines.
date -u +%FT%TZ
for b in box80 box81 box82 phantom lithium; do
  echo "=== $b"
  timeout 60 ssh -o BatchMode=yes $b 'cd ~/monerosim; me=$(id -un)
    d=$(ls -dt archived_runs/*/ 2>/dev/null | head -1); echo "newest run: $(basename $d)"
    grep -oE "Progress: [0-9]+%.*realtime: [0-9:]+" $d/shadow_run.log 2>/dev/null | tail -1
    echo "shadow $(pgrep -u $me -c -x shadow) monerod $(pgrep -u $me -c monerod) lane $(pgrep -u $me -f "[r]un_lane.py" | wc -l) make $(pgrep -u $me -c -x make) avail GiB $(free -g | awk "/Mem:/{print \$7}") disk $(df -h ~ | awk "NR==2{print \$4}")"
    tail -n 2 .claude/campaign9/queue.log | cut -c1-150' 2>&1
done
