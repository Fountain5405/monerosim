#!/bin/bash
# kw_run.sh: experiment 2 on lithium: the countermeasure's K (window depth in
# blocks) and w (shares per block) swept against the attacker family, each
# (K, w) with its own G grid scaled by w (G in objects), L in 0/1 (withhold
# or not), R in 1/3, Z=1, plus the sim's own rule as the baseline, at alphas
# 0.40/0.45/0.48/0.50, 1000 d x 2 seeds, into one resumable file. The last
# invocation's report lists every (combo, K, w) crossing.
set -u
cd /home/selfishmining/monerosim
rsync -a --exclude __pycache__ --exclude target --ignore-missing-args scripts agents test_configs pyproject.toml lithium:monerosim_rl/
cat > /tmp/kw_remote.sh <<'EOF'
cd ~/monerosim_rl
A="0.40 0.45 0.48 0.50"
OUT=data/sop_search/kw_sweep.jsonl
for K in 2 3 4 6; do
  for w in 8 16 32; do
    half=$((w / 2)); dbl=$((w * 2))
    echo "=== K=$K w=$w baseline"
    ~/monerosim/venv/bin/python scripts/sop_attacker_search.py --K $K --w $w --alphas $A --days 1000 --seeds 1 2 \
        --workers 20 --out $OUT --top 3
    echo "=== K=$K w=$w family"
    ~/monerosim/venv/bin/python scripts/sop_attacker_search.py --K $K --w $w --alphas $A --days 1000 --seeds 1 2 \
        --workers 20 --fixed "Z=1 M=1" --grid "G=$half,$w,$dbl L=0,1 R=1,3" --out $OUT --top 3
  done
done
echo "=== K/w sweep done"
EOF
scp -q /tmp/kw_remote.sh lithium:monerosim_rl/kw_remote.sh
ssh -o BatchMode=yes lithium 'cd ~/monerosim_rl; mkdir -p data/sop_search/logs; setsid nohup bash kw_remote.sh > data/sop_search/logs/kw_sweep.log 2>&1 < /dev/null & sleep 3; pgrep -c -f "[s]op_attacker_search.py"; free -g | awk "/Mem:/{print \"avail GiB \"\$7}"; echo log: ~/monerosim_rl/data/sop_search/logs/kw_sweep.log'
