#!/bin/bash
# Wrapper script to test P2P connectivity at different stages of the simulation

echo "Starting Shadow simulation..."
cd /home/lever65/monerosim_dev/monerosim
rm -rf shadow.data
shadow shadow_output/shadow.yaml > shadow.log 2>&1 &
SHADOW_PID=$!

echo "Shadow PID: $SHADOW_PID"
echo "Waiting for simulation to start..."
sleep 5

# Check if Shadow is still running
if ! kill -0 $SHADOW_PID 2>/dev/null; then
    echo "Shadow failed to start. Check shadow.log for details."
    exit 1
fi

echo "Waiting for daemons to initialize (60 seconds)..."
sleep 60

# Test 1: Early test (should show daemons starting up)
echo -e "\n=== Test 1: Early daemon check (60s after start) ==="
source venv/bin/activate
python3 scripts/test_p2p_connectivity.py

# Wait a bit more for full initialization
echo -e "\nWaiting 60 more seconds for full initialization..."
sleep 60

# Test 2: After initialization (should show connected nodes)
echo -e "\n=== Test 2: After initialization (120s after start) ==="
python3 scripts/test_p2p_connectivity.py

# Test 3: Test with the original bash script for comparison
echo -e "\n=== Test 3: Original bash script test ==="
./legacy_scripts/test_p2p_connectivity.sh

echo -e "\nKilling Shadow simulation..."
kill $SHADOW_PID 2>/dev/null
wait $SHADOW_PID 2>/dev/null

echo "Test wrapper completed."