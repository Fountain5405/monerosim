#!/bin/bash
# watch_mdp.sh <box> <caps tag> <max minutes>: poll the box every 60 s until every
# data/sop_mdp/bounds_<tag>_*.log carries its result line (or the time is up); print the results,
# the pytest log tail if present, and the remaining solver processes.
box=$1; tag=$2; mins=${3:-120}
for ((i=0; i<mins; i++)); do
  out=$(timeout 60 ssh -o BatchMode=yes $box "cd ~/monerosim; n=0; t=0; for f in data/sop_mdp/bounds_${tag}_*.log; do t=\$((t+1)); grep -q 'share.*at alpha=' \$f && n=\$((n+1)); done; echo \"\$n/\$t\"")
  [ "${out%%/*}" = "${out##*/}" ] && [ "${out##*/}" != "0" ] && break
  sleep 60
done
timeout 90 ssh -o BatchMode=yes $box "cd ~/monerosim; date -u +%H:%MZ; for f in data/sop_mdp/bounds_${tag}_*.log; do echo \"== \$f\"; grep -E 'states:|share.*at alpha=|action counts' \$f | cut -c1-200; done
echo '== pytest (data/sop_mdp/test_full.log tail)'; tail -n 4 data/sop_mdp/test_full.log 2>/dev/null
echo \"== still running: \$(pgrep -u \$(id -un) -fc 'sop_mdp.py solve') solver(s), pytest \$(pgrep -u \$(id -un) -fc 'pytest scripts/test_sop_mdp')\"
echo \"avail GiB: \$(free -g | awk '/Mem:/{print \$7}')  load: \$(cut -d' ' -f1 /proc/loadavg)\""
