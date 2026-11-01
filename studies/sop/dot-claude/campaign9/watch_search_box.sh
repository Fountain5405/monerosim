#!/bin/bash
# watch_search_box.sh <box> <log name> [hours=12]: poll every 10 min; exit (so the control box
# notifies) when no sop_attacker_search.py runs on <box>, printing the log's last lines.
box=$1; name=$2; hours=${3:-12}
end=$((SECONDS + hours*3600))
while [ $SECONDS -lt $end ]; do
  sleep 600
  n=$(timeout 30 ssh -o BatchMode=yes $box 'pgrep -u $(id -un) -c -f "[s]op_attacker_search[.]py"')
  if [ "${n:-1}" = "0" ]; then
    echo "$(date -u +%FT%TZ) $box: search finished"
    timeout 30 ssh -o BatchMode=yes $box "grep -E 'done \[' ~/monerosim_rl/data/sop_search/logs/$name.log | tail -n 1; tail -n 30 ~/monerosim_rl/data/sop_search/logs/$name.log | cut -c1-200"
    exit 0
  fi
done
echo "watch_search_box: $box still searching after $hours h"
