#!/bin/bash
# Wrapper script to run monitor.py inside Shadow simulation

# Source the network configuration
source "$(dirname "$0")/network_config.sh"

# Wait a bit for nodes to start
sleep 10

# Activate the Python virtual environment
source /home/lever65/monerosim_dev/monerosim/venv/bin/activate

# Run the monitor script in single-run mode
echo "Running monitor.py in single-run mode..."
python3 /home/lever65/monerosim_dev/monerosim/scripts/monitor.py --once

# Run the monitor script in continuous mode for a short time
echo "Running monitor.py in continuous mode..."
timeout 30 python3 /home/lever65/monerosim_dev/monerosim/scripts/monitor.py --refresh 5 --no-clear

# Run the monitor script in verbose mode
echo "Running monitor.py in verbose mode..."
python3 /home/lever65/monerosim_dev/monerosim/scripts/monitor.py --once --no-clear

echo "Monitor wrapper completed"