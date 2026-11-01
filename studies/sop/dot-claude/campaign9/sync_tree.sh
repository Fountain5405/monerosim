#!/bin/bash
# sync_tree.sh <box>: copy this checkout's agents/, scripts/, test_configs/ and gml_processing/
# into <box>:~/monerosim/ (no --delete) so a lane box runs the local commit
# without a push (owner 2026-10-26: pushing parked). Prints the local commit
# for the run's record; the box's own HEAD stays what it was.
set -u
box=$1
cd /home/selfishmining/monerosim
echo "local commit: $(git rev-parse --short HEAD) ($(git status --short | wc -l) dirty files)"
rsync -a --exclude __pycache__ --ignore-missing-args agents scripts test_configs gml_processing $box:monerosim/
ssh -o BatchMode=yes $box 'cd ~/monerosim && echo "box HEAD $(git rev-parse --short HEAD); synced files differing from it: $(git status --short | wc -l)"'
