cd ~/monerosim_rl
A="0.40 0.41 0.42 0.43 0.44 0.45 0.46 0.47 0.48 0.49 0.50"
for cfg in "" "G=8 L=1 M=1 R=1 Z=1" "G=8 L=1 M=1 R=2 Z=1" "G=6 L=1 M=1 R=1 Z=1" "G=10 L=1 M=1 R=1 Z=1" \
           "G=8 L=0 M=1 R=1 Z=1" "G=20 L=0 M=1 R=3 Z=1" "G=12 L=0 M=1 R=3 Z=1"; do
  echo "=== config: ${cfg:-defaults}"
  ~/monerosim/venv/bin/python scripts/sop_attacker_search.py --alphas $A --days 2000 --seeds 1 2 3 --workers 20 \
      --fixed "$cfg" --out data/sop_search/stage3_curve.jsonl --top 8
done
echo "=== stage 3 done"
