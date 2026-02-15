#!/bin/bash
cd /home/lever65/monerosim_dev/monerosim
export PYTHONPATH=/home/lever65/monerosim_dev/monerosim
export PATH=/usr/local/bin:/usr/bin:/bin:/home/lever65/.monerosim/bin

python3 -m agents.miner_distributor --id miner-distributor --shared-dir /tmp/monerosim_shared --log-level DEBUG --attributes transaction_frequency 30 2>&1
