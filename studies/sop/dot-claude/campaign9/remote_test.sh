#!/bin/bash
# remote_test.sh <box> <pytest args...>: rsync the working tree's scripts/, agents/,
# test_configs/, data/sop_rl/ to <box>:~/monerosim_rl/ (a scratch copy; the box's
# ~/monerosim stays the sim tree) and run pytest there with the box's venv.
# Owner rule 2026-10-25: nothing runs on the control box.
box=$1; shift
cd /home/selfishmining/monerosim
ssh -o BatchMode=yes $box 'mkdir -p ~/monerosim_rl/data'
rsync -a --delete --exclude __pycache__ --exclude target --ignore-missing-args scripts agents test_configs src pytest.ini conftest.py pyproject.toml $box:monerosim_rl/
rsync -a --ignore-missing-args data/sop_rl $box:monerosim_rl/data/
# 2026-10-26: 18 tests read fixtures outside those dirs (tests/, patches/, analysis/eclipse/,
# monero.pin, the h10 snapshot manifest); without them the full suite shows 18 spurious failures
ssh -o BatchMode=yes $box 'mkdir -p ~/monerosim_rl/analysis ~/monerosim_rl/chain_snapshots/h10'
rsync -a --max-size=50m --exclude __pycache__ --ignore-missing-args tests patches monero.pin $box:monerosim_rl/
rsync -a --max-size=50m --exclude __pycache__ --ignore-missing-args analysis/eclipse $box:monerosim_rl/analysis/
rsync -a --ignore-missing-args chain_snapshots/h10/manifest.json $box:monerosim_rl/chain_snapshots/h10/
args=$(printf '%q ' "$@")   # keep -k "a or b" and other quoted args intact over ssh
ssh -o BatchMode=yes $box "cd ~/monerosim_rl && ~/monerosim/venv/bin/python -m pytest $args"
