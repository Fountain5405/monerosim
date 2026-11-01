#!/bin/bash
# watch_rl.sh: poll lithium every 10 min; exit (so the control-box shell
# notifies) when any sop_rl train log prints its final "alpha=" line, when
# the alpha-0.50 3/3/48/20/20 exact solve prints its optimum, or after 12 h.
# Prints the triggering lines. Memory-light: one ssh per poll.
end=$((SECONDS + 12*3600))
while [ $SECONDS -lt $end ]; do
  out=$(timeout 40 ssh -o BatchMode=yes lithium '
    for f in ~/monerosim_rl/data/sop_rl/logs/train_*.log; do
      l=$(grep -E "^alpha=" "$f" 2>/dev/null | tail -1); [ -n "$l" ] && echo "DONE $(basename $f): $l"
    done
    :
    echo "trains running: $(pgrep -c -f "[s]op_rl.py train")  avail $(awk "/MemAvailable/{print int(\$2/1048576)}" /proc/meminfo) GiB"')
  if echo "$out" | grep -qE "^DONE|^SOLVE050"; then echo "$(date -u +%FT%TZ)"; echo "$out"; exit 0; fi
  sleep 600
done
echo "watch_rl timed out; last: $out"
