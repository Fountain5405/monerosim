#!/bin/bash
cd /home/lever65/monerosim_dev/monerosim
export PYTHONPATH=/home/lever65/monerosim_dev/monerosim
export PATH=/usr/local/bin:/usr/bin:/bin:/home/lever65/.monerosim/bin

python3 -m agents.regular_user --id miner-002 --shared-dir /tmp/monerosim_shared --rpc-host 192.168.10.11 --log-level DEBUG --agent-rpc-port 18081 --wallet-rpc-port 18082 --p2p-port 18080 --attributes can_receive_distributions true --attributes hashrate 40 --attributes is_miner true 2>&1
