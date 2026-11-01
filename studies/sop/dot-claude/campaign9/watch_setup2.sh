#!/bin/bash
# watch_setup2.sh <box>...: poll ~/setup.log on each box until all carry
# SETUP_EXIT= (max 4 h); exit early on an exit code other than 0 or 2. Digest at the end.
boxes="$*"
end=$((SECONDS + 4*3600))
while [ $SECONDS -lt $end ]; do
  all=1; bad=0
  for h in $boxes; do
    line=$(timeout 15 ssh -o BatchMode=yes $h 'grep -o "SETUP_EXIT=[0-9]*" ~/setup.log 2>/dev/null | tail -1')
    if [ -z "$line" ]; then all=0; elif [ "$line" != "SETUP_EXIT=0" ] && [ "$line" != "SETUP_EXIT=2" ]; then bad=1; fi
  done
  if [ $all = 1 ] || [ $bad = 1 ]; then break; fi
  sleep 60
done
for h in $boxes; do
  echo "=== $h ==="
  timeout 20 ssh -o BatchMode=yes $h 'L=$(sed "s/\x1b\[[0-9;]*m//g" ~/setup.log); echo "$L" | grep -oE "SETUP_EXIT=[0-9]+" | tail -1; echo "$L" | grep -E "^=== Step|Installed monerod-sim|ready to use|^\[ERROR\]|ERROR|failed" | tail -14 | cut -c1-120; echo "--- tail ---"; echo "$L" | tail -3 | cut -c1-120'
done
