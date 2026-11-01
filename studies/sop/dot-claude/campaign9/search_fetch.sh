#!/bin/bash
# search_fetch.sh <box>: copy the attacker-search results and logs produced by
# search_run.sh on <box> (~/monerosim_rl/data/sop_search/) into data/sop_search/.
set -u
box=$1
cd /home/selfishmining/monerosim
mkdir -p data/sop_search
rsync -a --ignore-missing-args $box:monerosim_rl/data/sop_search/ data/sop_search/
ls -la data/sop_search/ data/sop_search/logs/ | grep -v "^total"
