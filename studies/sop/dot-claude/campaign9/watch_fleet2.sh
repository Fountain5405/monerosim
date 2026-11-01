#!/bin/bash
# watch_fleet2.sh box:need_sync_lines ... [--mdp lithium:logfile]
# Poll every 15 min until every box has >= its " sync " line count in queue.log
# (or any HALT) and, if given, the MDP log on lithium shows "reachable states"
# or its process is gone. Max 24 h. Digest at the end. Memory-light (ssh + grep).
boxes=(); mdp=""
while [ $# -gt 0 ]; do case "$1" in --mdp) mdp=$2; shift 2;; *) boxes+=("$1"); shift;; esac; done
end=$((SECONDS + 24*3600))
while [ $SECONDS -lt $end ]; do
  all=1; halt=""
  for bn in "${boxes[@]}"; do
    h=${bn%%:*}; need=${bn##*:}
    out=$(timeout 20 ssh -o BatchMode=yes $h 'cd ~/monerosim; echo "S=$(grep -c " sync " .claude/campaign9/queue.log)"; ls .claude/campaign9/HALT 2>/dev/null && echo HALT')
    s=$(echo "$out" | grep -oE 'S=[0-9]+' | cut -d= -f2); [ "${s:-0}" -ge "$need" ] || all=0
    echo "$out" | grep -q HALT && halt="$halt $h"
  done
  if [ -n "$mdp" ]; then
    mh=${mdp%%:*}; ml=${mdp##*:}
    m=$(timeout 20 ssh -o BatchMode=yes $mh "grep -c 'reachable states' $ml 2>/dev/null; pgrep -c -f '[s]op_mdp.py enumerate'")
    done_m=$(echo "$m" | head -1); running=$(echo "$m" | tail -1)
    [ "${done_m:-0}" -ge 1 ] || [ "${running:-0}" -eq 0 ] || all=0
  fi
  if [ -n "$halt" ] || [ $all = 1 ]; then break; fi
  sleep 900
done
echo "fleet2 watcher exit at $(date -u +%FT%TZ): halt=[${halt:-none}]"
for bn in "${boxes[@]}"; do h=${bn%%:*}; echo "=== $h ==="; timeout 30 ssh -o BatchMode=yes $h 'cd ~/monerosim; cat .claude/campaign9/HALT 2>/dev/null | cut -c1-200; grep -E "finished|check|sync|HALT|queue" .claude/campaign9/queue.log | tail -8 | cut -c1-220'; done
if [ -n "$mdp" ]; then mh=${mdp%%:*}; ml=${mdp##*:}; echo "=== $mh MDP ==="; timeout 30 ssh -o BatchMode=yes $mh "grep -vE '^  round' $ml | tail -12; grep -E '^  round' $ml | tail -2; free -g | awk '/Mem:/{print \"ram avail \"\$7\" GiB\"}'"; fi
