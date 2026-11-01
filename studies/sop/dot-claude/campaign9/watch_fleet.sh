#!/bin/bash
# watch_fleet.sh: poll box80-82 every 15 min until all 6 cells have synced to
# the pool (6 " sync " lines in the boxes' queue.logs) or any HALT appears.
# Max 24 h. Prints a final digest for the notification.
end=$((SECONDS + 24*3600))
while [ $SECONDS -lt $end ]; do
  synced=0; halt=""
  for h in box80 box81 box82; do
    out=$(timeout 20 ssh -o BatchMode=yes $h 'cd ~/monerosim; echo "S=$(grep -c " sync " .claude/campaign9/queue.log)"; ls .claude/campaign9/HALT 2>/dev/null && echo HALT')
    s=$(echo "$out" | grep -oE 'S=[0-9]+' | cut -d= -f2); synced=$((synced + ${s:-0}))
    echo "$out" | grep -q HALT && halt="$halt $h"
  done
  if [ -n "$halt" ] || [ $synced -ge 6 ]; then break; fi
  sleep 900
done
echo "fleet watcher exit at $(date -u +%FT%TZ): synced=$synced halt=[${halt:-none}]"
for h in box80 box81 box82; do
  echo "=== $h ==="
  timeout 30 ssh -o BatchMode=yes $h 'cd ~/monerosim; cat .claude/campaign9/HALT 2>/dev/null | cut -c1-200; grep -E "finished|check|sync|HALT|queue done|stopped" .claude/campaign9/queue.log | tail -8 | cut -c1-230; for d in archived_runs/2*/; do printf "%s: " "$(basename $d)"; grep -oE "Progress: .*" $d/shadow_run.log 2>/dev/null | tail -1 || echo "(no progress line)"; done; free -g | awk "/Mem:/{print \"ram used \"\$3\" / \"\$2\" GiB\"}"; df -h / | tail -1 | awk "{print \"disk avail \"\$4}"'
done
