#!/bin/bash
cd /home/lever65/monerosim_dev/monerosim
export PYTHONPATH=/home/lever65/monerosim_dev/monerosim:/home/lever65/monerosim_dev/monerosim/venv/lib/python3.13/site-packages
export PATH=/usr/local/bin:/usr/bin:/bin:/home/lever65/.monerosim/bin

python3 -m agents.dns_server --id dnsserver --bind-ip 3.0.0.10 --port 53 --shared-dir /tmp/monerosim_shared --log-level DEBUG 2>&1
