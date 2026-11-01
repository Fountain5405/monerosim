#!/bin/bash
# launch_a050_runs2.sh (2026-10-25 ~22:10Z): ladder step 3, fourth attempt, on
# lithium, alpha 0.50 only, bracket 0.50-0.60 (first step asks for > 0.55;
# sim_stubborn earns 0.5715) with the bisection now training every step from
# the best table so far. Four runs: one-step control, race returns, D bins
# (the design's fallback), race + bins 2/2. The six earlier runs were stopped
# at 21:55Z (their steps at rho 0.575 / 0.6125 were above the optimum and
# their tables would have seeded the next step).
set -u
cd /home/selfishmining/monerosim
R=.claude/campaign9/rl_run.sh
common="train --alpha 0.50 --env race --budget 200000000 --behaviour stubborn --lo 0.50 --hi 0.60"
bash $R lithium train_a050_step $common --out data/sop_rl/policy_noown_a050_step.json.gz
bash $R lithium train_a050_race $common --returns race --out data/sop_rl/policy_noown_a050_race.json.gz
bash $R lithium train_a050_dbin2 $common --d-bin 2 --out data/sop_rl/policy_noown_a050_dbin2.json.gz
bash $R lithium train_a050_race_bin2 $common --returns race --d-bin 2 --p-bin 2 --out data/sop_rl/policy_noown_a050_race_bin2.json.gz
sleep 30
timeout 30 ssh -o BatchMode=yes lithium 'pgrep -af "[s]op_rl.py train" | sed "s/.*--out data.sop_rl.//"; awk "/MemAvailable/{print \"avail GiB\", int(\$2/1048576)}" /proc/meminfo; cat ~/monerosim_rl/data/sop_rl/logs/train_a0*.log | grep -c "^  rho="; date -u +%FT%TZ'
