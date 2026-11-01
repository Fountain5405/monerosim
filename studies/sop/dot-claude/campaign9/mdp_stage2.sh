#!/bin/bash
# mdp_stage2.sh: sequential MDP jobs with the compact solver (control box, 11 GB).
cd /home/selfishmining/monerosim
L=/home/selfishmining/monerosim/.claude/campaign9/mdp_stage2.log
: > $L
echo "### $(date -u +%FT%TZ) validation: stubborn chain, caps 5/5/96/32/32" >> $L
for own in ignore count; do
  timeout 3600 venv/bin/python scripts/sop_mdp.py evaluate --alpha 0.45 --give-up-objects 5 \
    --test-own-pending $own --own-pending $own --a-max 5 --h-max 5 --d-max 96 --p-max 32 --deficit 32 --verbose >> $L 2>&1
  echo "exit $?" >> $L
done
echo "### $(date -u +%FT%TZ) enumerate 4/4/64/24/24" >> $L
timeout 10800 venv/bin/python scripts/sop_mdp.py enumerate --a-max 4 --h-max 4 --d-max 64 --p-max 24 --deficit 24 --verbose >> $L 2>&1
echo "exit $?" >> $L
echo "### $(date -u +%FT%TZ) enumerate 5/5/96/32/32" >> $L
timeout 10800 venv/bin/python scripts/sop_mdp.py enumerate --a-max 5 --h-max 5 --d-max 96 --p-max 32 --deficit 32 --verbose >> $L 2>&1
echo "exit $?" >> $L
echo "### done $(date -u +%FT%TZ)" >> $L
grep -vE '^  round' $L; grep -E '^  round' $L | tail -3
