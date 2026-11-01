#!/bin/bash
# search_run.sh <box> <name> <sop_attacker_search.py args...>: rsync the working
# tree to <box>:~/monerosim_rl/ and run scripts/sop_attacker_search.py there,
# detached, logging to ~/monerosim_rl/data/sop_search/logs/<name>.log (the
# --out path is relative to ~/monerosim_rl). Fetch with search_fetch.sh.
# Owner rules: never on the control box; lithium/phantom run the owner's
# stressnet nodes, so keep the worker count modest (each ~80 MB) and check
# free memory first. 2026-10-26.
set -u
box=$1; name=$2; shift 2
cd /home/selfishmining/monerosim
ssh -o BatchMode=yes $box 'mkdir -p ~/monerosim_rl/data/sop_search/logs; free -g | awk "/Mem:/{print \"avail GiB \"\$7}"'
rsync -a --exclude __pycache__ --exclude target --ignore-missing-args scripts agents test_configs pyproject.toml $box:monerosim_rl/
args=$(printf '%q ' "$@")
ssh -o BatchMode=yes $box "cd ~/monerosim_rl; setsid nohup ~/monerosim/venv/bin/python scripts/sop_attacker_search.py $args > data/sop_search/logs/$name.log 2>&1 < /dev/null & sleep 2; pgrep -af '[s]op_attacker_search.py' | grep -c . ; echo log: ~/monerosim_rl/data/sop_search/logs/$name.log"
