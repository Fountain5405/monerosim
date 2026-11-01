#!/bin/bash
# stage3_run.sh: stage 3 of the attacker search on lithium: the curve over
# alphas 0.40..0.50 (step 0.01) at 2000 d x 3 seeds for the stage-2 winners,
# two G variants of the L=1 family, and the baseline's missing alphas, all
# into one resumable file; the last invocation's report covers every row.
# Sequential invocations (one python per config, 20 workers each).
set -u
cd /home/selfishmining/monerosim
rsync -a --exclude __pycache__ --exclude target --ignore-missing-args scripts agents test_configs pyproject.toml lithium:monerosim_rl/
cat > /tmp/stage3_remote.sh <<'EOF'
cd ~/monerosim_rl
A="0.40 0.41 0.42 0.43 0.44 0.45 0.46 0.47 0.48 0.49 0.50"
for cfg in "" "G=8 L=1 M=1 R=1 Z=1" "G=8 L=1 M=1 R=2 Z=1" "G=6 L=1 M=1 R=1 Z=1" "G=10 L=1 M=1 R=1 Z=1" \
           "G=8 L=0 M=1 R=1 Z=1" "G=20 L=0 M=1 R=3 Z=1" "G=12 L=0 M=1 R=3 Z=1"; do
  echo "=== config: ${cfg:-defaults}"
  ~/monerosim/venv/bin/python scripts/sop_attacker_search.py --alphas $A --days 2000 --seeds 1 2 3 --workers 20 \
      --fixed "$cfg" --out data/sop_search/stage3_curve.jsonl --top 8
done
echo "=== stage 3 done"
EOF
scp -q /tmp/stage3_remote.sh lithium:monerosim_rl/stage3_remote.sh
ssh -o BatchMode=yes lithium 'cd ~/monerosim_rl; mkdir -p data/sop_search/logs; setsid nohup bash stage3_remote.sh > data/sop_search/logs/stage3_curve.log 2>&1 < /dev/null & sleep 3; pgrep -c -f "[s]op_attacker_search.py"; free -g | awk "/Mem:/{print \"avail GiB \"\$7}"; echo log: ~/monerosim_rl/data/sop_search/logs/stage3_curve.log'
