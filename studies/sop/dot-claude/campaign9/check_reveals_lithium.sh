#!/bin/bash
# check_reveals_lithium.sh: wait 30 min, then count reveal / concede lines in the
# live stock runs' attacker logs on lithium (the fix must show reveals; the
# broken runs had none in 72 h).
sleep 1800
ssh -o BatchMode=yes lithium 'cd ~/monerosim; for d in archived_runs/2*_sop_v4_o5_stock_72h__*/; do f=$d/shadow.data/hosts/attacker-miner/bash.1020.stdout; [ -f "$f" ] || continue; printf "%s: " "$(basename $d | sed "s/.*__//")"; grep -oE "Progress: [0-9]+%.*realtime: [0-9:]+" $d/shadow_run.log | tail -1 | tr "\n" " "; echo "reveals=$(grep -v "attacker-miner - " $f | grep -c "window_stubborn: reveal") conceded=$(grep -v "attacker-miner - " $f | grep -c "strategy conceded") rejected=$(grep -v "attacker-miner - " $f | grep -c "reveal rejected")"; done; free -g | awk "/Mem:/{print \"ram avail \"\$7\" GiB\"}"'
