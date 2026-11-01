#!/bin/bash
# chain_queue.sh <box> [hours=72]: keep <box> busy from a queue file.
# Queue: .claude/campaign9/queues/<box>.txt, one "<spec> <cell>" per line (spec name
# without .yaml); lines may be appended while this runs. Every 2 min: if the box has
# no lane (run_lane.py) and the queue has a line, pop it and launch it with
# rerun_cell.sh; for slow / gamma / dsweep cells start check_paths.sh --wait 1500 in
# the background (output to queues/<box>.paths.log). On phantom / lithium, launch only
# with >= 20 GiB available (stressnet nodes keep >= 8 GiB; a cell takes ~12). Log:
# queues/<box>.log. Exits after <hours> or when the queue file is removed.
box=$1; hours=${2:-72}
D=/home/selfishmining/monerosim/.claude/campaign9
Q=$D/queues/$box.txt; LOG=$D/queues/$box.log
mkdir -p $D/queues; touch $Q
end=$((SECONDS + hours*3600))
say() { echo "$(date -u +%FT%TZ) $*" >> $LOG; }
say "chain start ($(grep -c . $Q) queued)"
while [ $SECONDS -lt $end ] && [ -f $Q ]; do
  sleep 120
  next=$(grep -m1 . $Q 2>/dev/null) || continue
  [ -n "$next" ] || continue
  state=$(timeout 40 ssh -o BatchMode=yes $box 'me=$(id -un); echo "$(pgrep -u $me -f "[r]un_lane.py" | wc -l) $(pgrep -u $me -c -x shadow) $(free -g | awk "/Mem:/{print \$7}")"' 2>/dev/null) || continue
  read lanes shadows avail <<< "$state"
  [ "${lanes:-1}" = 0 ] && [ "${shadows:-1}" = 0 ] || continue
  case $box in phantom|lithium) [ "${avail:-0}" -ge 20 ] || { say "wait: $box avail ${avail} GiB"; continue; } ;; esac
  sed -i '0,/./{/./d}' $Q
  set -- $next; spec=$1; cell=$2
  say "launch $spec $cell"
  bash $D/rerun_cell.sh $box $spec $cell >> $LOG 2>&1
  case $spec in *slow*|*gamma*|*dsweep_slow*|*dsweep_gamma*)
    ( bash $D/check_paths.sh --wait 1500 $box $spec $cell 2>&1 | grep -E "^run:|Progress|^monerod|-> honest-00|-> attacker-bridge" | sed "s/^/[$cell] /" >> $D/queues/$box.paths.log ) & ;;
  esac
done
say "chain exit"
