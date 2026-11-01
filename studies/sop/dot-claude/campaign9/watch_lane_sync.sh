#!/bin/bash
# watch_lane_sync.sh <box> [hours]: baseline = the " sync " lines in the box's
# queue.log now; poll every 10 min and exit (so the control-box shell notifies)
# when the count grows, printing the new lines. One ssh per poll.
box=$1; hours=${2:-8}
count() { timeout 40 ssh -o BatchMode=yes $box 'grep -c " sync " ~/monerosim/.claude/campaign9/queue.log 2>/dev/null || echo 0'; }
base=$(count); echo "$(date -u +%FT%TZ) $box baseline sync lines: $base"
end=$((SECONDS + hours*3600))
while [ $SECONDS -lt $end ]; do
  sleep 600
  n=$(count)
  if [ "${n:-0}" -gt "${base:-0}" ]; then
    echo "$(date -u +%FT%TZ) $box: a cell synced ($n lines)"
    timeout 40 ssh -o BatchMode=yes $box 'tail -n 3 ~/monerosim/.claude/campaign9/queue.log | cut -c1-200'
    exit 0
  fi
done
echo "watch_lane_sync: no new sync on $box within $hours h"
