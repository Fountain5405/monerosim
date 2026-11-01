#!/bin/bash
# memguard_rl_lithium.sh: every 5 min check lithium's MemAvailable; under
# 3 GiB kill ONE of my sop_rl.py train runs by pid (memguard_rl_pick.sh
# chooses: a045, a048, one-step a050, then the newest) and report; keep
# guarding. Exits when no train run is left or after 16 h. Touches
# nothing but my own sop_rl.py processes.
dir=$(dirname "$0")
end=$((SECONDS + 16*3600))
while [ $SECONDS -lt $end ]; do
  out=$(timeout 20 ssh -o BatchMode=yes lithium 'echo "n=$(pgrep -c -f "[s]op_rl.py train") avail=$(awk "/MemAvailable/{print int(\$2/1048576)}" /proc/meminfo)"')
  n=$(echo "$out" | grep -oE 'n=[0-9]+' | cut -d= -f2); avail=$(echo "$out" | grep -oE 'avail=[0-9]+' | cut -d= -f2)
  [ "${n:-1}" = "0" ] && { echo "$(date -u +%FT%TZ) no train run left; $out"; exit 0; }
  if [ -n "$avail" ] && [ "$avail" -lt 8 ]; then   # 8 GiB: lithium also runs the owner's stressnet monerod (2026-10-26)
    pid=$(timeout 20 ssh -o BatchMode=yes lithium bash -s < "$dir/memguard_rl_pick.sh" | head -1)
    if [ -n "$pid" ]; then
      timeout 20 ssh -o BatchMode=yes lithium "ps -o pid,etime,args -p $pid --no-headers | cut -c1-150; kill $pid"
      echo "$(date -u +%FT%TZ) KILLED train pid $pid because $out"
    fi
    sleep 120
  fi
  sleep 300
done
echo "memguard_rl timed out; last: $out"
