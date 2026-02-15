#!/bin/bash
cd /home/lever65/monerosim_dev/monerosim
export PYTHONPATH=/home/lever65/monerosim_dev/monerosim
export PATH=/usr/local/bin:/usr/bin:/bin:/home/lever65/.monerosim/bin

python3 -m agents.miner_distributor --id miner-distributor --shared-dir /tmp/monerosim_shared --log-level DEBUG --attributes transaction_frequency 30 --attributes min_transaction_amount 0.5 --attributes max_transaction_amount 2.0 --attributes initial_wait_time 0 --attributes md_n_recipients 8 --attributes md_out_per_tx 2 --attributes md_output_amount 5 2>&1
