#!/bin/bash
cd /home/lever65/monerosim_dev/monerosim
export PYTHONPATH=/home/lever65/monerosim_dev/monerosim
export PATH=/usr/local/bin:/usr/bin:/bin:/home/lever65/.monerosim/bin

python3 -m agents.regular_user --id spy-002 --shared-dir /tmp/monerosim_shared --rpc-host 10.100.0.11 --log-level DEBUG --daemon-rpc-port 18081 --wallet-rpc-port 18082 --p2p-port 18080 --attributes activity_start_time 18249 --attributes can_receive_distributions true --tx-frequency 120 --attributes transaction_interval 120 2>&1
