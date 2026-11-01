#!/bin/bash
# check_topo.sh [--wait S] <box> <spec> <cell>: connectivity check of a v3 slow / gamma cell: progress,
# memory, and for honest-002 and every relay-chain-* / relay-slow-* host whether the daemon synced
# (HEIGHT lines), its last height, blocks found by each miner, and how many of honest-002's found
# blocks honest-001's daemon added (the honest path works if that is close to honest-002's count).
[ "${1:-}" = "--wait" ] && { sleep "${2:-1500}"; shift 2; }
box=$1; spec=$2; cell=$3
timeout 300 ssh -o BatchMode=yes $box "cd ~/monerosim; d=\$(ls -dt archived_runs/2*_${spec}__$cell/ 2>/dev/null | head -1)
[ -n \"\$d\" ] || { echo 'no run dir'; exit 0; }
echo \"run: \$(basename \$d)\"; grep -oE 'Progress: [0-9]+%.*realtime: [0-9:]+' \$d/shadow_run.log | tail -1
echo \"monerod-sim+monerod: \$(pgrep -u \$(id -un) -c monerod)  avail GiB: \$(free -g | awk '/Mem:/{print \$7}')\"
for h in honest-001 honest-002 \$(ls \$d/shadow.data/hosts | grep -E 'relay-chain|relay-slow'); do
  f=\$(ls -S \$d/shadow.data/hosts/\$h/monerod*.stdout 2>/dev/null | head -1)
  echo \"\$h: HEIGHT lines \$(grep -ac ' HEIGHT ' \$f) last \$(grep -a ' HEIGHT ' \$f | tail -n 1 | grep -oE 'HEIGHT [0-9]+')  found \$(grep -ac 'Found block' \$f)  added \$(grep -ac 'BLOCK SUCCESSFULLY ADDED' \$f)  peers-in-log \$(grep -ac 'NEW CONNECTION\|new connection' \$f)\"
done
a=\$(grep -la SelfishMinerAgent \$d/shadow.data/hosts/attacker-miner/bash.*.stdout 2>/dev/null | head -1)
[ -n \"\$a\" ] && echo \"attacker: bridge switches=\$(grep -ac 'read bridge ->' \$a) reveals=\$(grep -a ' - attacker-miner - ' \$a | grep -cE ': reveal fork=') publishes=\$(grep -a ' - attacker-miner - ' \$a | grep -cE ': publish fork=') concedes=\$(grep -ac 'conceded' \$a)\"
echo \"honest-002 blocks reaching honest-001: \$(f2=\$(ls -S \$d/shadow.data/hosts/honest-002/monerod*.stdout | head -1); f1=\$(ls -S \$d/shadow.data/hosts/honest-001/monerod*.stdout | head -1); grep -a 'Found block' \$f2 | grep -oE '<[0-9a-f]{64}>|[0-9a-f]{64}' | head -200 | sort -u > /tmp/h2_\$\$.txt; n=0; while read id; do id=\${id#<}; id=\${id%>}; grep -aq \"\$id\" \$f1 && n=\$((n+1)); done < /tmp/h2_\$\$.txt; echo \"\$n of \$(wc -l < /tmp/h2_\$\$.txt) sampled\"; rm -f /tmp/h2_\$\$.txt)\""
