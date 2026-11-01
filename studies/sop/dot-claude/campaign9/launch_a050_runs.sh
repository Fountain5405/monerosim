#!/bin/bash
# launch_a050_runs.sh (2026-10-25 ~21:15Z): third attempt at ladder step 3 on
# lithium, alpha 0.50 only, bracket 0.45-0.70 (first bisection step asks for
# > 0.575, i.e. above sim_stubborn's 0.5715): race returns alone, D binned by
# 2 alone (the design's fallback), and both with pending bins. Stops the
# alpha 0.40 one-step run first (stubborn earns 0.06 there against honest's
# 0.40: nothing to learn, nothing to simulate).
set -u
cd /home/selfishmining/monerosim
R=.claude/campaign9/rl_run.sh
echo "stop a040 (pid 1979260) if it is still that run:"
timeout 20 ssh -o BatchMode=yes lithium 'ps -o pid,args -p 1979260 --no-headers | grep -q "alpha 0.40" && kill 1979260 && echo killed-1979260'
common="train --alpha 0.50 --env race --budget 200000000 --behaviour stubborn --lo 0.45 --hi 0.70"
bash $R lithium train_a050_race $common --returns race --out data/sop_rl/policy_noown_a050_race.json.gz
bash $R lithium train_a050_dbin2 $common --d-bin 2 --out data/sop_rl/policy_noown_a050_dbin2.json.gz
bash $R lithium train_a050_race_bin2 $common --returns race --d-bin 2 --p-bin 2 --out data/sop_rl/policy_noown_a050_race_bin2.json.gz
sleep 30
timeout 30 ssh -o BatchMode=yes lithium 'pgrep -af "[s]op_rl.py train" | sed "s/.*sop_rl.py //"; awk "/MemAvailable/{print \"avail GiB\", int(\$2/1048576)}" /proc/meminfo; ls -la ~/monerosim_rl/data/sop_rl/logs/ | grep -v "^total"; tail -n 2 ~/monerosim_rl/data/sop_rl/logs/train_a050_race*.log ~/monerosim_rl/data/sop_rl/logs/train_a050_dbin2.log'
