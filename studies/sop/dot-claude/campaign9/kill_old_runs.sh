#!/bin/bash
# kill_old_runs.sh <box> <min_elapsed_s>: stop MY OWN sim processes on a lane box whose
# elapsed time exceeds <min_elapsed_s> (an earlier round still running beside a newer one),
# by explicit pid: driver (run_lane.py) first, then selfish_matrix, then shadow, then the
# surviving daemons/agents. Only processes owned by the login user; nothing else is touched.
set -u
box=$1; min=$2
timeout 120 ssh -o BatchMode=yes $box "
me=\$(id -un)
list() { ps -u \$me -o pid=,etimes=,comm=,args= | awk -v m=$min '\$2>m && \$3 ~ /^(python|python3|shadow|shadow-worker|monerod-sim|monero-wallet-rpc|bash)\$/' ; }
echo '--- candidates (pid elapsed comm args):'; list | cut -c1-120
for pat in 'run_lane[.]py' 'selfish_matrix[.]py' '^ *[0-9]+ +[0-9]+ +shadow '; do
  pids=\$(list | grep -E \"\$pat\" | awk '{print \$1}')
  [ -n \"\$pids\" ] && { echo \"TERM \$pat: \$pids\"; kill -TERM \$pids 2>/dev/null; sleep 5; }
done
sleep 10
rest=\$(list | awk '{print \$1}')
[ -n \"\$rest\" ] && { echo \"KILL remaining: \$(echo \$rest | wc -w) pids\"; kill -KILL \$rest 2>/dev/null; sleep 3; }
echo '--- survivors older than the threshold:'; list | wc -l
echo '--- live sim processes now (elapsed s, comm) grouped:'; ps -u \$me -o etimes=,comm= | awk '\$2 ~ /monerod-sim|shadow|python|selfish/ {b=int(\$1/600)*10; c[b\" min: \"\$2]++} END{for(k in c) print c[k], k}' | sort -k2 -n
free -g | sed -n 2p
"
