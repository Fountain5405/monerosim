#!/bin/bash
# rl_run.sh <box> <name> <sop_rl.py args...>: rsync the working tree to
# <box>:~/monerosim_rl/ (as remote_test.sh does) and run scripts/sop_rl.py
# there, detached, logging to ~/monerosim_rl/data/sop_rl/logs/<name>.log.
# Fetch results back with rl_fetch.sh. Owner rule 2026-10-25: never on the
# control box. 2026-10-25 17:00Z: not on phantom either while it runs sims
# (its owner's testnet monerod was OOM-killed under four lanes).
set -u
box=$1; name=$2; shift 2
cd /home/selfishmining/monerosim
ssh -o BatchMode=yes $box 'mkdir -p ~/monerosim_rl/data/sop_rl/logs'
rsync -a --exclude __pycache__ --exclude target --ignore-missing-args scripts agents test_configs pyproject.toml $box:monerosim_rl/
rsync -a --ignore-missing-args data/sop_rl/README.md $box:monerosim_rl/data/sop_rl/
args=$(printf '%q ' "$@")
ssh -o BatchMode=yes $box "cd ~/monerosim_rl; setsid nohup ~/monerosim/venv/bin/python scripts/sop_rl.py $args > data/sop_rl/logs/$name.log 2>&1 < /dev/null & sleep 2; pgrep -af '[s]op_rl.py' | grep -c . ; echo log: ~/monerosim_rl/data/sop_rl/logs/$name.log"
