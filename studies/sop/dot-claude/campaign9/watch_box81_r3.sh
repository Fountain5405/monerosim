#!/bin/bash
# watch_box81.sh: poll box81 every 10 min until the round-3 noown a040 cells have synced
# (4 " sync " lines: 2 from round 1 + 2) or a HALT appears there. Max 14 h.
end=$((SECONDS + 14*3600))
while [ $SECONDS -lt $end ]; do
  out=$(timeout 20 ssh -o BatchMode=yes box81 'cd ~/monerosim; echo "S=$(grep -c " sync " .claude/campaign9/queue.log)"; ls .claude/campaign9/HALT 2>/dev/null && echo HALT')
  s=$(echo "$out" | grep -oE 'S=[0-9]+' | cut -d= -f2)
  if echo "$out" | grep -q HALT || [ "${s:-0}" -ge 4 ]; then break; fi
  sleep 600
done
echo "box81 watcher exit at $(date -u +%FT%TZ): synced=${s:-?}"
timeout 30 ssh -o BatchMode=yes box81 'cd ~/monerosim; cat .claude/campaign9/HALT 2>/dev/null | cut -c1-200; grep -E "finished|check|sync|HALT|queue" .claude/campaign9/queue.log | tail -8 | cut -c1-230; for d in archived_runs/2*/; do printf "%s: " "$(basename $d)"; grep -oE "Progress: .*" $d/shadow_run.log 2>/dev/null | tail -1; done'
