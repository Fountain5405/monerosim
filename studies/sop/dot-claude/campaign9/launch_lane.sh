#!/bin/bash
# launch_lane.sh <box> <spec> <cell>...: push remote_launch.sh and start the lane driver there.
set -u
S=/home/selfishmining/monerosim/.claude/campaign9
h=$1; shift
scp -q $S/remote_launch.sh $S/run_lane.py $h:monerosim/.claude/campaign9/ || exit 1
ssh -o BatchMode=yes $h "bash ~/monerosim/.claude/campaign9/remote_launch.sh $*"
