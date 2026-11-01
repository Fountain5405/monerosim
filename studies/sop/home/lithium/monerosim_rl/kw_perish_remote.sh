cd ~/monerosim_rl
A="0.46 0.47 0.48"
run() { ~/monerosim/venv/bin/python scripts/sop_attacker_search.py --K $1 --w $2 --alphas $A --days 2000 --seeds 1 2 3 --workers 16 --grid "$3" --fixed "L=1 M=1 Z=1" --perish --out data/sop_search/kw_perish_047.jsonl --top 3; }
run 2 8  "G=2,3,4 R=1"
run 2 16 "G=3,4,6,8 R=1"
run 6 16 "G=4,6,8 R=1,3"
run 3 32 "G=6,8,12,16 R=1"
echo "=== kw perish done"
