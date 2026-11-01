#!/bin/bash
# kill_rl_runs.sh <out-name>...: stop my sop_rl.py train runs on lithium by pid,
# matched on their --out file name (e.g. policy_noown_a045.json.gz). Nothing else.
set -u
for o in "$@"; do
  timeout 20 ssh -o BatchMode=yes lithium "p=\$(pgrep -f '[s]op_rl.py train.*$o' | head -1); if [ -n \"\$p\" ]; then kill \$p && echo \"killed \$p ($o)\"; else echo \"no run for $o\"; fi"
done
sleep 3
timeout 20 ssh -o BatchMode=yes lithium 'echo "left: $(pgrep -c -f "[s]op_rl.py train")"; awk "/MemAvailable/{print \"avail GiB\", int(\$2/1048576)}" /proc/meminfo'
