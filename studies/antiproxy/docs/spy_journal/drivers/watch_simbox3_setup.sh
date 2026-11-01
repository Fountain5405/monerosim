#!/bin/bash
# Exit when setup.sh on simbox3 is no longer running; print the log tail.
while ssh -o ConnectTimeout=10 simbox3 'pgrep -f "[s]etup.sh --clean" >/dev/null'; do sleep 120; done
ssh simbox3 'sed "s/\x1b\[[0-9;]*m//g" ~/setup_sim.log | tail -15 | cut -c1-200'
