#!/bin/bash
# memguard_lanes.sh "<box> <box>..." [gib=8] [hours=80]: every 3 min read each box's
# MemAvailable; under <gib> stop MY sim lane on that box (TERM to run_lane.py,
# selfish_matrix.py and shadow, by pid; shadow takes its daemons down) and exit so the
# control-box shell notifies. The owner's stressnet monerod (user monero) is never
# touched (2026-10-26 rule: keep ~8 GiB free on lithium and phantom). Exits when no
# lane driver is left on any guarded box, or after <hours>.
boxes=$1; gib=${2:-8}; hours=${3:-80}
end=$((SECONDS + hours*3600))
while [ $SECONDS -lt $end ]; do
  alive=0
  for b in $boxes; do
    out=$(timeout 30 ssh -o BatchMode=yes $b 'echo "n=$(pgrep -u $(id -un) -c -f "[r]un_lane[.]py") avail=$(awk "/MemAvailable/{print int(\$2/1048576)}" /proc/meminfo)"')
    n=$(echo "$out" | grep -oE 'n=[0-9]+' | cut -d= -f2); avail=$(echo "$out" | grep -oE 'avail=[0-9]+' | cut -d= -f2)
    [ "${n:-1}" != "0" ] && alive=1
    if [ -n "$avail" ] && [ "$avail" -lt "$gib" ] && [ "${n:-0}" != "0" ]; then
      echo "$(date -u +%FT%TZ) $b: MemAvailable ${avail} GiB < ${gib}: stopping my lane"
      timeout 60 ssh -o BatchMode=yes $b 'me=$(id -un); for pat in "[r]un_lane[.]py" "[s]elfish_matrix[.]py" "^[^ ]*/shadow "; do p=$(pgrep -u $me -f "$pat" | tr "\n" " "); [ -n "$p" ] && { echo "TERM $pat: $p"; kill -TERM $p; sleep 5; }; done; sleep 20; echo "left: $(pgrep -u $me -c monerod-sim) monerod-sim"; free -g | sed -n 2p'
      exit 0
    fi
  done
  [ $alive = 0 ] && { echo "$(date -u +%FT%TZ) no lane driver left on $boxes"; exit 0; }
  sleep 180
done
echo "memguard_lanes timed out"
