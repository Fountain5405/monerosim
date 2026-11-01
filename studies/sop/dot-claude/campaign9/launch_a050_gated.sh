#!/bin/bash
# launch_a050_gated.sh (2026-10-25 ~23:40Z): ladder step 3, fifth attempt, on
# lithium beside the four ungated runs: the confidence gate (an action is
# greedy at a key only after n_min updates there; sim_stubborn elsewhere)
# with a faster step-size decay (lr 0.1: 1/(1+0.1 n)), alpha 0.50, bracket
# 0.50-0.60. Three runs: one-step + gate 30, race returns + gate 30, race
# returns + gate 100.
set -u
cd /home/selfishmining/monerosim
R=.claude/campaign9/rl_run.sh
common="train --alpha 0.50 --env race --budget 200000000 --behaviour stubborn --lo 0.50 --hi 0.60 --lr 0.1"
bash $R lithium train_a050_step_g30 $common --n-min 30 --out data/sop_rl/policy_noown_a050_step_g30.json.gz
bash $R lithium train_a050_race_g30 $common --returns race --n-min 30 --out data/sop_rl/policy_noown_a050_race_g30.json.gz
bash $R lithium train_a050_race_g100 $common --returns race --n-min 100 --out data/sop_rl/policy_noown_a050_race_g100.json.gz
sleep 30
timeout 30 ssh -o BatchMode=yes lithium 'pgrep -af "[s]op_rl.py train" | sed "s/.*--out data.sop_rl.//"; awk "/MemAvailable/{print \"avail GiB\", int(\$2/1048576)}" /proc/meminfo; cat ~/monerosim_rl/data/sop_rl/logs/train_a0*.log | grep -c "^  rho="; date -u +%FT%TZ'
