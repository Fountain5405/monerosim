#!/bin/bash
# Runs ON lithium (copied there): start the official monerod-sim build with the knob patch,
# detached. Keeps the previous binary and log for comparison.
cd ~/monerosim || exit 1
grep -q "sim-sop-seen-at-notify" patches/monero-sim-pop.patch || { echo "patch lacks the knob; abort"; exit 1; }
cp -p ~/.monerosim/bin/monerod-sim ~/.monerosim/bin/monerod-sim.pre-knob 2>/dev/null && echo "old binary kept as monerod-sim.pre-knob"
[ -f ~/setup.log ] && mv ~/setup.log ~/setup.log.20261024
setsid nohup bash -c 'cd ~/monerosim && yes "" | ./setup.sh --sim-binary; echo SETUP_EXIT=$? >> ~/setup.log' > ~/setup.log 2>&1 < /dev/null &
sleep 5
ps -eo pid,args | grep -F "./setup.sh --sim-binary" | grep -v grep | head -2 | cut -c1-80
tail -n 2 ~/setup.log
