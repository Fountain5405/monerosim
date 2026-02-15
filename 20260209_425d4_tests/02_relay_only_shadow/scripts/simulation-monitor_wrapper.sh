#!/bin/bash
cd /home/lever65/monerosim_dev/monerosim
export PYTHONPATH=/home/lever65/monerosim_dev/monerosim
export PATH=/usr/local/bin:/usr/bin:/bin:/home/lever65/.monerosim/bin

python3 -m agents.simulation_monitor --id simulation-monitor --shared-dir /tmp/monerosim_shared --output-dir /home/lever65/monerosim_dev/monerosim/20260209_425d4_tests/02_relay_only_shadow --log-level DEBUG --poll-interval 300 --status-file /tmp/monerosim_shared/monerosim_monitor.log 2>&1
