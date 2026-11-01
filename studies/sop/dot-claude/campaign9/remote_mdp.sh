#!/bin/bash
# remote_mdp.sh <bound> <alpha> <a> <h> <d> <p> <deficit>: on the box, start one SoP MDP solve
# detached (same pattern as remote_launch.sh), log to data/sop_mdp/bounds_<caps>_a<alpha>_<bound>.log.
cd ~/monerosim || exit 1
bound=$1; alpha=$2; a=$3; h=$4; d=$5; p=$6; dfc=$7
tag="${a}_${h}_${d}_${p}_${dfc}"
mkdir -p data/sop_mdp
log="data/sop_mdp/bounds_${tag}_a${alpha}_${bound}.log"
setsid nohup nice -n 5 venv/bin/python scripts/sop_mdp.py solve --alpha "$alpha" --bound "$bound" \
  --a-max "$a" --h-max "$h" --d-max "$d" --p-max "$p" --deficit "$dfc" --verbose \
  >> "$log" 2>&1 < /dev/null &
echo "started $bound alpha=$alpha caps=$tag -> $log"
