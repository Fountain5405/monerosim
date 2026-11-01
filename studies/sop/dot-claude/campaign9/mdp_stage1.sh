#!/bin/bash
# mdp_stage1.sh: sequential (memory!) MDP checks on the control box.
#  1. validation: stubborn chain share vs race-model Monte Carlo, own and noown
#  2. state counts at caps that reach past the window
cd /home/selfishmining/monerosim
L=/home/selfishmining/monerosim/.claude/campaign9/mdp_stage1.log
: > $L
echo "### $(date -u +%FT%TZ) validation: stubborn chain (caps 8/8/160/48/48)" >> $L
for own in count ignore; do
  timeout 2400 venv/bin/python scripts/sop_mdp.py evaluate --alpha 0.45 --give-up-objects 5 \
    --test-own-pending $own --own-pending $own --a-max 8 --h-max 8 --d-max 160 --p-max 48 --deficit 48 >> $L 2>&1
  echo "exit $?" >> $L
done
echo "### $(date -u +%FT%TZ) race model hunt, 2000 d, seed 1" >> $L
venv/bin/python scripts/sop_race_model.py hunt --alphas 0.45 --rules sop --give-ups o5 --release-depth 0 --days 2000 --seed 1 --honest-shares --rule-version 20261020 2>&1 | grep -E '^\| 0.45|^\| alpha' >> $L
venv/bin/python scripts/sop_race_model.py hunt --alphas 0.45 --rules sop --give-ups o5 --release-depth 0 --days 2000 --seed 1 --honest-shares --rule-version 20261020_noown 2>&1 | grep -E '^\| 0.45' >> $L
echo "### $(date -u +%FT%TZ) enumerate 4/4/64/24/24" >> $L
timeout 3000 venv/bin/python scripts/sop_mdp.py enumerate --a-max 4 --h-max 4 --d-max 64 --p-max 24 --deficit 24 --verbose >> $L 2>&1
echo "exit $?" >> $L
echo "### $(date -u +%FT%TZ) enumerate 5/5/96/32/32" >> $L
timeout 3000 venv/bin/python scripts/sop_mdp.py enumerate --a-max 5 --h-max 5 --d-max 96 --p-max 32 --deficit 32 --verbose >> $L 2>&1
echo "exit $?" >> $L
echo "### done $(date -u +%FT%TZ)" >> $L
grep -vE '^  round' $L
