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
