#!/bin/bash
# watch_search.sh [hours]: poll lithium every 5 min; exit (so the control-box
# shell notifies) when no sop_attacker_search.py process is left, printing the
# tail of every search log. One ssh per poll; also reports free memory.
hours=${1:-6}; pat=${2:-sop_attacker_search.py}   # the script's name to wait for ("[s]" prefix added here)
pat="[${pat:0:1}]${pat:1}"
end=$((SECONDS + hours*3600))
while [ $SECONDS -lt $end ]; do
  out=$(timeout 40 ssh -o BatchMode=yes lithium "echo \"n=\$(pgrep -c -f '$pat') avail=\$(free -g | awk '/Mem:/{print \$7}')\"")
  n=$(echo "$out" | grep -oE 'n=[0-9]+' | cut -d= -f2)
  if [ "${n:-1}" = "0" ]; then
    echo "$(date -u +%FT%TZ) search jobs finished; $out"
    timeout 60 ssh -o BatchMode=yes lithium 'cd ~/monerosim_rl/data/sop_search/logs; for f in *.log; do echo "== $f"; tail -n 40 "$f"; done'
    exit 0
  fi
  sleep 300
done
echo "watch_search: still running after $hours h; last: $out"
