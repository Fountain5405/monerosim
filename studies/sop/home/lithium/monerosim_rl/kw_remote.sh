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
