#!/bin/bash
# score_pool.sh <spec>...: pull each spec's cell JSONs from the pool (all boxes)
# into this checkout's matrix_runs/<spec>/cells/, rebuild table.md with
# --reanalyze, print the table, then stuck time per pooled run dir and each
# run's check summary line.
set -u
cd /home/selfishmining/monerosim
POOL=/mnt/remote_spinny/20261024_monerosim_research_effort
for spec in "$@"; do
  echo "################ $spec ################"
  mkdir -p matrix_runs/$spec/cells
  n=0
  for j in $POOL/*/matrix_runs/$spec/cells/*.json; do [ -f "$j" ] || continue; cp "$j" matrix_runs/$spec/cells/; n=$((n+1)); done
  echo "cell JSONs pulled: $n"
  venv/bin/python scripts/selfish_matrix.py test_configs/matrix/$spec.yaml --reanalyze 2>&1 | tail -3
  echo "--- table.md ---"; cat matrix_runs/$spec/table.md
  echo "--- stuck time (hours with no concession/reveal, gaps > 2 h) ---"
  dirs=$(ls -d $POOL/*/archived_runs/*_${spec}__* 2>/dev/null)
  [ -n "$dirs" ] && venv/bin/python scripts/selfish_mining/sop_stuck_time.py $dirs 2>&1 | tail -12
  echo "--- check summaries ---"
  for d in $POOL/*/campaign9/*_${spec}__*/; do [ -f "$d/summary.txt" ] && { printf "%s: " "$(basename $d | sed 's/.*__//')"; tail -1 "$d/summary.txt" | cut -c1-200; }; done
done
echo "################ a033_s1 gate failure detail ################"
D=$(ls -d $POOL/box80-host/campaign9/*a033_s1 2>/dev/null | head -1)
[ -n "$D" ] && { echo "--- summary.txt ---"; cat $D/summary.txt | cut -c1-200; echo "--- reveals.out (tail) ---"; tail -15 $D/reveals.out | cut -c1-200; echo "--- a3.out (tail) ---"; tail -8 $D/a3.out | cut -c1-200; }
