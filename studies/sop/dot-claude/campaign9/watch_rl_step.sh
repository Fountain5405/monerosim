#!/bin/bash
# watch_rl_step.sh <min_lines> [hours]: poll lithium every 10 min; exit (so
# the control-box shell notifies) once the four warm-started train logs hold
# at least <min_lines> "rho=" bisection lines in total. Prints the last line
# of each log. One ssh per poll.
need=${1:-5}; hours=${2:-4}
end=$((SECONDS + hours*3600))
while [ $SECONDS -lt $end ]; do
  n=$(timeout 40 ssh -o BatchMode=yes lithium 'cat ~/monerosim_rl/data/sop_rl/logs/train_a0*.log 2>/dev/null | grep -c "^  rho="')
  if [ "${n:-0}" -ge "$need" ]; then
    echo "$(date -u +%FT%TZ) bisection lines: $n"
    timeout 40 ssh -o BatchMode=yes lithium 'cd ~/monerosim_rl/data/sop_rl/logs; for f in train_a0*.log; do echo "$f: $(grep "^  rho=" $f | tail -1)"; done'
    exit 0
  fi
  sleep 600
done
echo "watch_rl_step: no step within $hours h (lines: ${n:-?})"
