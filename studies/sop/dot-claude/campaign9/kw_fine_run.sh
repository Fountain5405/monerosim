#!/bin/bash
# kw_fine_run.sh: the K/w table's crossings at full precision: for seven
# (K, w) settings, their best attacker from the sweep over alphas 0.44..0.50
# by 0.01, 2000 d x 3 seeds, into data/sop_search/kw_fine.jsonl on lithium
# (sequential invocations, 12 workers each; sop_kw_table.py reads the file).
set -u
cd /home/selfishmining/monerosim
rsync -a --exclude __pycache__ --exclude target --ignore-missing-args scripts agents test_configs pyproject.toml lithium:monerosim_rl/
cat > /tmp/kw_fine_remote.sh <<'EOF'
cd ~/monerosim_rl
A="0.44 0.45 0.46 0.47 0.48 0.49 0.50"
run() { ~/monerosim/venv/bin/python scripts/sop_attacker_search.py --K $1 --w $2 --alphas $A --days 2000 --seeds 1 2 3 --workers 12 --fixed "$3" --out data/sop_search/kw_fine.jsonl --top 2; }
run 2 8  "G=4 L=1 M=1 R=1 Z=1"
run 3 8  "G=4 L=1 M=1 R=1 Z=1"
run 2 16 "G=8 L=1 M=1 R=1 Z=1"
run 3 16 "G=8 L=1 M=1 R=1 Z=1"
run 3 32 "G=16 L=1 M=1 R=1 Z=1"
run 6 16 "G=8 L=1 M=1 R=3 Z=1"
run 6 32 "G=16 L=1 M=1 R=3 Z=1"
echo "=== kw fine done"
EOF
scp -q /tmp/kw_fine_remote.sh lithium:monerosim_rl/kw_fine_remote.sh
ssh -o BatchMode=yes lithium 'cd ~/monerosim_rl; setsid nohup bash kw_fine_remote.sh > data/sop_search/logs/kw_fine.log 2>&1 < /dev/null & sleep 3; pgrep -c -f "[s]op_attacker_search.py"; free -g | awk "/Mem:/{print \"avail GiB \"\$7}"'
