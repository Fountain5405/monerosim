#!/bin/bash
# relaunch_stock_lithium.sh: after the 20261020/difficulty fix, re-run the stock
# control on lithium: pull, park the invalid markers and run dirs, launch
# a045 s1/s2 + a040 s1/s2 as a second driver (--add) beside the MDP enumerate.
set -u
ssh -o BatchMode=yes lithium '
  cd ~/monerosim || exit 1
  git pull -q --ff-only && git log --oneline -1
  grep -c "len(weights) >= 5:" agents/selfish_strategy.py | sed "s/^/fix present (expect 1): /"
  mkdir -p matrix_runs/_invalid archived_runs/_invalid
  [ -d matrix_runs/sop_v4_o5_stock_72h ] && mv matrix_runs/sop_v4_o5_stock_72h matrix_runs/_invalid/sop_v4_o5_stock_72h_20261024 && echo "parked invalid matrix dir"
  for d in archived_runs/2*_sop_v4_o5_stock_72h__*; do [ -d "$d" ] && mv "$d" archived_runs/_invalid/ && echo "parked $(basename $d)"; done
  free -g | awk "/Mem:/{print \"ram avail \"\$7\" GiB\"}"; pgrep -af "[s]op_mdp.py enumerate" | cut -c1-80 | sed "s/^/enumerate running: /"'
bash /home/selfishmining/monerosim/.claude/campaign9/launch_lane.sh lithium sop_v4_o5_stock_72h share_stock_a045_s1 share_stock_a045_s2 share_stock_a040_s1 share_stock_a040_s2
