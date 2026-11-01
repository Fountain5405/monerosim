#!/bin/bash
# stage_pl.sh: bring phantom and lithium from "setup.sh done" to running lanes.
# pull sop-research, deploy drivers/check gate/KSM tmpfiles/cache warm-up and
# verify (deploy_lane.sh), pool keys, then launch:
#   phantom: stock a033 s1 s2 + stock a040 s1 s2        (4 lanes, one driver)
#   lithium: stock a045 s1 s2 (driver 1) + alpha a048 s1 s2 (driver 2, --add)
set -u
S=/home/selfishmining/monerosim/.claude/campaign9
for h in phantom lithium; do
  echo "################ $h: setup outcome + pull ################"
  ssh -o BatchMode=yes $h 'grep -oE "SETUP_EXIT=[0-9]+" ~/setup.log | tail -1; cd ~/monerosim && git pull -q --ff-only && git log --oneline -1 && ls ~/.monerosim/bin/monerod-sim ~/.monerosim/bin/shadow >/dev/null && echo binaries present'
done
for h in phantom lithium; do bash $S/deploy_lane.sh $h 2>&1 | grep -vE '^  patch:'; done
bash $S/setup_pool_keys.sh phantom lithium 2>&1 | grep -E '####|authorized|pool-write'
echo "################ launch ################"
bash $S/launch_lane.sh phantom sop_v4_o5_stock_72h share_stock_a033_s1 share_stock_a033_s2 share_stock_a040_s1 share_stock_a040_s2
bash $S/launch_lane.sh lithium sop_v4_o5_stock_72h share_stock_a045_s1 share_stock_a045_s2
sleep 200   # let lithium's first driver warm the cache and start both lanes before the second driver
scp -q $S/remote_launch.sh lithium:monerosim/.claude/campaign9/
ssh -o BatchMode=yes lithium "bash ~/monerosim/.claude/campaign9/remote_launch.sh --add sop_v4_o5_alpha_72h share_sop2_a048_s1 share_sop2_a048_s2"
sleep 240
for h in phantom lithium; do
  echo "################ $h ################"
  ssh -o BatchMode=yes $h 'cd ~/monerosim; tail -4 .claude/campaign9/queue.log | cut -c1-160; ls .claude/campaign9/HALT 2>/dev/null; for d in archived_runs/2*/; do printf "%s: " "$(basename $d | cut -c1-70)"; grep -oE "Progress: [0-9]+%.*realtime: [0-9:]+" $d/shadow_run.log 2>/dev/null | tail -1 || echo "(starting)"; done; free -g | awk "/Mem:/{print \"ram used \"\$3\" / \"\$2\" GiB, avail \"\$7}"; uptime | grep -oE "load average.*"'
done
