#!/bin/bash
# rl_fetch.sh <box>: copy policy files and training logs produced by rl_run.sh
# on <box> (~/monerosim_rl/data/sop_rl/) back into this tree's data/sop_rl/.
set -u
box=$1
cd /home/selfishmining/monerosim
rsync -a --ignore-missing-args $box:monerosim_rl/data/sop_rl/ data/sop_rl/
ls -la data/sop_rl/ data/sop_rl/logs/ | grep -v "^total"
