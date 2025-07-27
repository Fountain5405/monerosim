# Simple Test Script - Python Version

## Overview

`simple_test.py` is a Python equivalent of the original `simple_test.sh` bash script. It performs the same basic mining and synchronization functionality tests for the MoneroSim Shadow network simulation.

## Features

The script tests:
1. **Daemon Readiness**: Verifies both A0 and A1 daemons are ready and responsive
2. **Block Generation**: Confirms the mining node (A0) can generate blocks
3. **Network Synchronization**: Ensures the sync node (A1) synchronizes with the mining node

## Usage

### With Virtual Environment (Recommended)
```bash
cd /home/lever65/monerosim_dev/monerosim
source venv/bin/activate
python3 scripts/simple_test.py
```

### Without Virtual Environment
```bash
cd /home/lever65/monerosim_dev/monerosim
PYTHONPATH=/home/lever65/monerosim_dev/monerosim python3 scripts/simple_test.py
```

## Configuration

The script uses the same configuration parameters as the bash version:
- `MAX_ATTEMPTS`: 30 - Maximum retry attempts for RPC calls
- `RETRY_DELAY`: 2 - Delay between retry attempts (seconds)
- `SYNC_WAIT_TIME`: 30 - Time to wait for synchronization (seconds)
- `SYNC_THRESHOLD`: 0 - Maximum allowed height difference (0 = exact match)
- `NUM_BLOCKS`: 3 - Number of blocks to generate in the test

## Dependencies

The script depends on:
- `scripts/error_handling.py` - For logging and verification functions
- `scripts/network_config.py` - For network configuration values
- Python 3.6+ with the `requests` library

## Differences from Bash Version

While functionally equivalent, the Python version offers:
- Better error handling with Python exceptions
- Type hints for improved code clarity
- More structured code organization
- Easier to extend and maintain

## Exit Codes

- `0`: Test completed successfully
- `1`: Test failed (check logs for details)

## Example Output

```
2025-01-26 13:00:00 [INFO] [SIMPLE_TEST] === MoneroSim Simple Test ===
2025-01-26 13:00:00 [INFO] [SIMPLE_TEST] Starting simple test at 2025-01-26 13:00:00
2025-01-26 13:00:00 [INFO] [SIMPLE_TEST] Step 1: Verifying daemon readiness
...
2025-01-26 13:00:30 [INFO] [SIMPLE_TEST] ✅ SUCCESS: Nodes are synchronized
2025-01-26 13:00:30 [INFO] [SIMPLE_TEST] ✅ Basic mining and synchronization test PASSED
2025-01-26 13:00:30 [INFO] [SIMPLE_TEST] === Simple test completed ===