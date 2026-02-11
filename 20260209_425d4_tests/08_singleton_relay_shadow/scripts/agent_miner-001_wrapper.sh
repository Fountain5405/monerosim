#!/bin/bash
cd /home/lever65/monerosim_dev/monerosim
export PYTHONPATH=/home/lever65/monerosim_dev/monerosim
export PATH=/usr/local/bin:/usr/bin:/bin:/home/lever65/.monerosim/bin

python3 -m agents.regular_user --id miner-001 --shared-dir /tmp/monerosim_shared --rpc-host 3.0.0.13 --log-level DEBUG --daemon-rpc-port 18081 --wallet-rpc-port 18082 --p2p-port 18080 --attributes can_receive_distributions true --attributes hashrate 60 --attributes is_miner true 2>&1
