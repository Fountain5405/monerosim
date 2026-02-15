#!/bin/bash
cd /home/lever65/monerosim_dev/monerosim
export PYTHONPATH=/home/lever65/monerosim_dev/monerosim
export PATH=/usr/local/bin:/usr/bin:/bin:/home/lever65/.monerosim/bin

python3 -m agents.regular_user --id user-002 --shared-dir /tmp/monerosim_shared --rpc-host 192.168.10.21 --log-level DEBUG --agent-rpc-port 18081 --wallet-rpc-port 18082 --p2p-port 18080 --attributes activity_start_time 18000 --attributes can_receive_distributions true --tx-frequency 60 --attributes transaction_interval 60 2>&1
