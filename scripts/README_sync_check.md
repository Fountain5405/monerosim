# sync_check.py - Synchronization Verification Script

## Overview

`sync_check.py` is a Python script that verifies blockchain synchronization between Monero nodes in the Shadow simulation. It checks that nodes have synchronized their blockchains and are at the same height with matching block hashes.

This script replaces the bash `sync_check.sh` script with improved error handling, better JSON parsing, and more robust verification logic.

## Features

- **Synchronization Verification**: Checks that nodes are at the same blockchain height
- **Block Hash Verification**: Ensures nodes have the same top block hash
- **Configurable Threshold**: Allows setting maximum acceptable height difference
- **Continuous Mode**: Can run continuously to monitor sync status over time
- **Detailed Diagnostics**: Provides comprehensive information about sync failures
- **Retry Logic**: Built-in retry mechanisms for handling transient network issues

## Usage

### Basic Usage

Check synchronization between default nodes (A0 and A1):
```bash
./scripts/sync_check.py
```

### Custom Nodes

Check synchronization between specific nodes:
```bash
./scripts/sync_check.py --node1-url http://11.0.0.1:28090/json_rpc --node1-name A0 \
                        --node2-url http://11.0.0.2:28090/json_rpc --node2-name A1
```

### Continuous Monitoring

Run continuous synchronization checks:
```bash
./scripts/sync_check.py --continuous --check-interval 60
```

### Command Line Options

- `--node1-url`: URL of the first node (default: A0's RPC URL)
- `--node1-name`: Name of the first node (default: A0)
- `--node2-url`: URL of the second node (default: A1's RPC URL)
- `--node2-name`: Name of the second node (default: A1)
- `--sync-threshold`: Maximum allowed height difference (default: 1)
- `--max-attempts`: Maximum number of attempts for each check (default: 30)
- `--retry-delay`: Delay between attempts in seconds (default: 2)
- `--wait-time`: Time to wait before checking sync in seconds (default: 10)
- `--continuous`: Run continuously, checking sync status periodically
- `--check-interval`: Interval between checks in continuous mode (default: 30 seconds)

## Examples

### Example 1: Basic Sync Check
```bash
./scripts/sync_check.py
```

Output:
```
2024-01-15 10:30:00 [INFO] [SYNC_CHECK] === MoneroSim Synchronization Check ===
2024-01-15 10:30:00 [INFO] [SYNC_CHECK] Starting sync check at 2024-01-15 10:30:00
2024-01-15 10:30:00 [INFO] [SYNC_CHECK] Waiting 10 seconds before checking synchronization...
2024-01-15 10:30:10 [INFO] [SYNC_CHECK] Checking synchronization between A0 and A1
2024-01-15 10:30:10 [INFO] [SYNC_CHECK] A0 - Height: 100, Hash: abc123..., Status: OK
2024-01-15 10:30:10 [INFO] [SYNC_CHECK] A1 - Height: 100, Hash: abc123..., Status: OK
2024-01-15 10:30:10 [INFO] [SYNC_CHECK] ✓ Nodes A0 and A1 are synchronized
2024-01-15 10:30:10 [INFO] [SYNC_CHECK] ✅ Synchronization check PASSED
```

### Example 2: Sync Check with Custom Threshold
```bash
./scripts/sync_check.py --sync-threshold 5 --wait-time 0
```

### Example 3: Continuous Monitoring
```bash
./scripts/sync_check.py --continuous --check-interval 30
```

Output:
```
2024-01-15 10:30:00 [INFO] [SYNC_CHECK] Running in continuous mode
2024-01-15 10:30:00 [INFO] [SYNC_CHECK] --- Sync check #1 ---
2024-01-15 10:30:00 [INFO] [SYNC_CHECK] ✓ Nodes A0 and A1 are synchronized
2024-01-15 10:30:00 [INFO] [SYNC_CHECK] ✅ Sync check #1 PASSED
2024-01-15 10:30:00 [INFO] [SYNC_CHECK] Next check in 30 seconds...
```

## Integration with Other Scripts

The sync_check.py script can be used in combination with other MoneroSim scripts:

```bash
# Run simple test first
./scripts/simple_test.py

# Then check synchronization
./scripts/sync_check.py --wait-time 30

# Or use in a test pipeline
./scripts/simple_test.py && ./scripts/sync_check.py && echo "All tests passed!"
```

## Error Handling

The script includes comprehensive error handling:

- **Connection Failures**: Retries with exponential backoff
- **RPC Errors**: Detailed error messages with diagnostic information
- **Sync Failures**: Provides information about height differences and block hashes
- **Timeout Handling**: Configurable timeouts for all RPC calls

## Exit Codes

- `0`: Synchronization check passed
- `1`: Synchronization check failed or error occurred

## Dependencies

- Python 3.6+
- `error_handling.py`: For logging and RPC retry functionality
- `network_config.py`: For network configuration values
- `requests` library: For HTTP/RPC communication

## Troubleshooting

### Nodes Not Synchronizing

If nodes fail to synchronize:

1. Check that both nodes are running:
   ```bash
   curl -X POST http://11.0.0.1:28090/json_rpc -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}'
   curl -X POST http://11.0.0.2:28090/json_rpc -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}'
   ```

2. Verify P2P connectivity between nodes:
   ```bash
   # Check connections on each node
   curl -X POST http://11.0.0.1:28090/json_rpc -d '{"jsonrpc":"2.0","id":"0","method":"get_connections"}'
   ```

3. Increase the sync threshold if nodes are slowly synchronizing:
   ```bash
   ./scripts/sync_check.py --sync-threshold 10 --max-attempts 60
   ```

### Connection Refused Errors

If you get connection refused errors:

1. Ensure the Shadow simulation is running
2. Check that the nodes have started successfully
3. Verify the correct IP addresses and ports in `network_config.py`

## Related Scripts

- `simple_test.py`: Basic functionality test that includes sync checking
- `transaction_test.py`: Transaction testing that relies on synchronized nodes
- `monitor_script.py`: Continuous monitoring of the simulation