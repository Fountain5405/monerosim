#!/bin/bash
# This script is designed to run INSIDE the Shadow simulation
# It will be executed by a Shadow host to test P2P connectivity

echo "P2P Connectivity Test - Running inside Shadow"
echo "Current time: $(date)"
echo "Hostname: $(hostname)"
echo "IP: $(hostname -I)"

# Wait a bit for daemons to stabilize
sleep 10

# Source the network configuration if it exists
if [ -f "$(dirname "$0")/network_config.sh" ]; then
    source "$(dirname "$0")/network_config.sh"
fi

# Test connectivity to A0
echo "Testing connectivity to A0 (11.0.0.1:28090)..."
curl -X POST http://11.0.0.1:28090/json_rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}' \
  --connect-timeout 5 \
  --max-time 10

echo -e "\n\nTesting connectivity to A1 (11.0.0.2:28090)..."
curl -X POST http://11.0.0.2:28090/json_rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}' \
  --connect-timeout 5 \
  --max-time 10

# Now run the Python test script
echo -e "\n\nRunning Python P2P connectivity test..."
cd /home/lever65/monerosim_dev/monerosim
source venv/bin/activate
python3 scripts/test_p2p_connectivity.py

echo "Test completed."