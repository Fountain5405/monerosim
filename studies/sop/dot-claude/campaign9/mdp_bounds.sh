#!/bin/bash
# mdp_bounds.sh <box> <a_max> <h_max> <d_max> <p_max> <deficit> <alpha>...: run the SoP MDP lower
# and upper bound at the given caps for each alpha on <box>, detached (setsid nohup), logging to
# ~/monerosim/data/sop_mdp/bounds_<caps>_a<alpha>_<bound>.log; prints the pids. The 4/4/64/24/24
# solve needs ~12.4 GB RSS and ~13 h (2026-10-25): only on an idle lane. 3/3 caps are small.
set -u
box=$1; a=$2; h=$3; d=$4; p=$5; dfc=$6; shift 6
tag="${a}_${h}_${d}_${p}_${dfc}"
scp -q .claude/campaign9/remote_mdp.sh $box:monerosim/.claude/campaign9/remote_mdp.sh || exit 1
for alpha in "$@"; do
  for bound in lower upper; do
    timeout 60 ssh -o BatchMode=yes $box "bash ~/monerosim/.claude/campaign9/remote_mdp.sh $bound $alpha $a $h $d $p $dfc"
  done
done
