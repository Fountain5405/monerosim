#!/bin/bash
# memguard_lithium.sh: every 5 min check lithium's MemAvailable; if under 3 GiB
# while the MDP enumerate runs, kill that process by pid (sims have priority)
# and exit. Exits quietly when the enumerate is gone. Max 12 h.
end=$((SECONDS + 12*3600))
while [ $SECONDS -lt $end ]; do
  out=$(timeout 20 ssh -o BatchMode=yes lithium 'pid=$(pgrep -f "[s]op_mdp.py enumerate" | head -1); echo "pid=${pid:-none} avail=$(awk "/MemAvailable/{print int(\$2/1048576)}" /proc/meminfo) rss=$( [ -n "$pid" ] && awk "/VmRSS/{print int(\$2/1048576)}" /proc/$pid/status || echo 0)"')
  pid=$(echo "$out" | grep -oE 'pid=[0-9a-z]+' | cut -d= -f2); avail=$(echo "$out" | grep -oE 'avail=[0-9]+' | cut -d= -f2)
  [ "$pid" = "none" ] && { echo "enumerate finished/gone at $(date -u +%FT%TZ); $out"; exit 0; }
  if [ "${avail:-99}" -lt 3 ]; then
    timeout 20 ssh -o BatchMode=yes lithium "kill $pid && sleep 3 && echo killed-$pid; free -g | awk '/Mem:/{print \"avail \"\$7\" GiB\"}'"
    echo "KILLED enumerate pid $pid at $(date -u +%FT%TZ) because $out"; exit 2
  fi
  sleep 300
done
echo "memguard timed out; last: $out"
