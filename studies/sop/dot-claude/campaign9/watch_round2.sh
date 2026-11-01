#!/bin/bash
# watch_round2.sh: poll the round-2 boxes every 15 min until each has the
# expected number of " sync " lines in its queue.log (box80 4 = 2 round-1 + 2,
# box82 4, phantom 4, lithium 4) or any HALT appears. Max 24 h. Digest at the end.
declare -A NEED=([box80]=4 [box82]=4 [phantom]=4 [lithium]=4)
end=$((SECONDS + 24*3600))
while [ $SECONDS -lt $end ]; do
  done_all=1; halt=""
  for h in "${!NEED[@]}"; do
    out=$(timeout 20 ssh -o BatchMode=yes $h 'cd ~/monerosim; echo "S=$(grep -c " sync " .claude/campaign9/queue.log)"; ls .claude/campaign9/HALT 2>/dev/null && echo HALT')
    s=$(echo "$out" | grep -oE 'S=[0-9]+' | cut -d= -f2)
    [ "${s:-0}" -ge "${NEED[$h]}" ] || done_all=0
    echo "$out" | grep -q HALT && halt="$halt $h"
  done
  if [ -n "$halt" ] || [ $done_all = 1 ]; then break; fi
  sleep 900
done
echo "round-2 watcher exit at $(date -u +%FT%TZ): halt=[${halt:-none}]"
for h in box80 box82 phantom lithium; do
  echo "=== $h ==="
  timeout 30 ssh -o BatchMode=yes $h 'cd ~/monerosim; cat .claude/campaign9/HALT 2>/dev/null | cut -c1-200; grep -E "finished|check|sync|HALT|queue done|stopped" .claude/campaign9/queue.log | tail -10 | cut -c1-230; for d in archived_runs/2*/; do printf "%s: " "$(basename $d | cut -c1-70)"; grep -oE "Progress: [0-9]+%.*realtime: [0-9:]+" $d/shadow_run.log 2>/dev/null | tail -1; done; free -g | awk "/Mem:/{print \"ram used \"\$3\" / \"\$2\" GiB\"}"; df -h / | tail -1 | awk "{print \"disk avail \"\$4}"'
done
