#!/bin/bash
cd /home/lever65/monerosim_dev/monerosim
export PYTHONPATH=/home/lever65/monerosim_dev/monerosim
export PATH=/usr/local/bin:/usr/bin:/bin:/home/lever65/.monerosim/bin

python3 -m agents.autonomous_miner --id miner-003 --rpc-host 192.168.10.12 --agent-rpc-port 18081 --shared-dir /tmp/monerosim_shared --log-level DEBUG --wallet-rpc-port 18082 --attributes can_receive_distributions true --attributes hashrate 25 --attributes is_miner true 2>&1
