#!/bin/bash
# commit_specs_12.sh: dry-run the three changed specs, commit on sop-research,
# push via tr, pull on the idle lane boxes.
set -eu
cd /home/selfishmining/monerosim
for s in sop_v4_o5_stock_72h sop_v4_o5_alpha_72h sop_v4_o5_72h; do
  printf "%s: " $s; venv/bin/python scripts/selfish_matrix.py test_configs/matrix/$s.yaml --dry-run 2>&1 | tail -1
done
venv/bin/python scripts/selfish_matrix.py test_configs/matrix/sop_v4_o5_stock_72h.yaml --dry-run 2>&1 | grep -oE '^share_stock_[a-z0-9_]+' | tr '\n' ' '; echo
grep -cE 'weigh: difficulty|give_up_objects: .-1.' matrix_runs/sop_v4_o5_stock_72h/configs/share_stock_a045_s1.yaml | sed 's/^/stock attrs in generated config: /'
git add test_configs/matrix/sop_v4_o5_stock_72h.yaml test_configs/matrix/sop_v4_o5_alpha_72h.yaml test_configs/matrix/sop_v4_o5_72h.yaml
git commit -q -m "$(cat <<'EOF'
SoP: 12-cell round 2 for the o5 attacker (stock control, crossing point, more a045 draws)

sop_v4_o5_stock_72h (new): the stock-rule control, alpha 0.33/0.40/0.45,
two draws; weigh difficulty, window off, objects give-up disabled (no
shares on a stock network), block give-up 5 kept.
sop_v4_o5_alpha_72h: alpha 0.48 and 0.50 added (crossing point).
sop_v4_o5_72h: samples s3 and s4 added (headline a045 cell, noise ~0.03).
All three dry-run.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
echo "committed $(git rev-parse --short HEAD)"
git push -q tr:/scratch/monerosim_dev/monerosim sop-research:sop-research
ssh -o BatchMode=yes tr "cd /scratch/monerosim_dev/monerosim && git -c credential.helper='!gh auth git-credential' push -q origin sop-research && echo origin/sop-research=\$(git rev-parse --short origin/sop-research)"
git fetch -q origin; git status -sb | head -1
for h in box80 box82; do printf "%s: " $h; ssh -o BatchMode=yes $h 'cd ~/monerosim && git pull -q --ff-only && git log --oneline -1'; done
