#!/bin/bash
# rerun_cell.sh <box> <spec> <cell>...: rerun finished cells on a lane box with
# this checkout's tree (2026-10-26: the pool-count fix 61969161 is not pushed).
# Steps: sync_tree.sh <box>; verify the fix landed (agents/selfish_miner.py has
# _fork_header); delete each cell's done-marker (else selfish_matrix skips the
# cell in 0 s); clear a HALT left by a gate failure (--add keeps it); launch
# with --add when another driver is still running its other cell.
set -u
box=$1; spec=$2; shift 2
cells="$*"
S=/home/selfishmining/monerosim/.claude/campaign9
bash $S/sync_tree.sh $box || exit 1
timeout 60 ssh -o BatchMode=yes $box "cd ~/monerosim
n=\$(grep -c _fork_header agents/selfish_miner.py); echo \"fix markers in agents/selfish_miner.py: \$n\"; [ \"\$n\" -ge 2 ] || exit 3
for c in $cells; do rm -v matrix_runs/$spec/cells/\$c.json 2>/dev/null || echo \"no marker for \$c\"; done
[ -f .claude/campaign9/HALT ] && { echo \"HALT was: \$(cat .claude/campaign9/HALT)\"; rm -f .claude/campaign9/HALT; }
pgrep -af '[r]un_lane[.]py' | cut -c1-120" || { echo "box check failed (rc=$?)"; exit 1; }
running=$(timeout 40 ssh -o BatchMode=yes $box "pgrep -f '[r]un_lane[.]py' | wc -l")
add=""; [ "${running:-0}" -gt 0 ] && add="--add"
echo "launching ($add) $spec: $cells"
bash $S/launch_lane.sh $box $add $spec $cells
