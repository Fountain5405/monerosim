# test_p2p_connectivity.py

## Overview

`test_p2p_connectivity.py` is a Python script that tests the peer-to-peer (P2P) connectivity between Monero nodes in a Shadow simulation. It verifies that nodes can establish and maintain bidirectional connections, which is essential for blockchain synchronization and transaction propagation.

This is a Python port of the original `test_p2p_connectivity.sh` bash script, providing the same functionality with improved error handling, better logging, and enhanced maintainability.

## Purpose

The script performs the following key functions:

1. **Daemon Readiness Verification**: Ensures both nodes are running and responsive
2. **Connection State Monitoring**: Tracks incoming and outgoing connections
3. **P2P Connectivity Verification**: Confirms bidirectional connections between nodes
4. **Detailed Connection Analysis**: Provides connection details including state and live time
5. **Diagnostic Information**: Offers troubleshooting guidance when connectivity fails

## Usage

### Basic Usage

```bash
cd /home/lever65/monerosim_dev/monerosim
./scripts/test_p2p_connectivity.py
```

### Prerequisites

- Shadow simulation must be running with at least two Monero nodes
- Python 3.6+ with the `requests` library installed
- Network configuration properly set up in `network_config.py`

## Configuration

The script uses the following configuration parameters:

- `MAX_ATTEMPTS`: Maximum retry attempts for RPC calls (default: 5)
- `RETRY_DELAY`: Base delay between retries in seconds (default: 3)
- `P2P_CHECK_ATTEMPTS`: Maximum attempts for P2P connectivity verification (default: 10)
- `P2P_CHECK_DELAY`: Delay between P2P connectivity checks in seconds (default: 10)

## Output

### Success Case

When P2P connectivity is established:

```
2024-01-15 10:30:00 [INFO] [P2P_TEST] === P2P Connectivity Test ===
2024-01-15 10:30:00 [INFO] [P2P_TEST] Verifying daemon readiness...
2024-01-15 10:30:01 [INFO] [P2P_TEST] A0 (mining node) is ready. Status: OK, Height: 100
2024-01-15 10:30:02 [INFO] [P2P_TEST] A1 (sync node) is ready. Status: OK, Height: 100
2024-01-15 10:30:02 [INFO] [P2P_TEST] Initial connection state:
2024-01-15 10:30:02 [INFO] [P2P_TEST] A0: 1 incoming, 0 outgoing connections
2024-01-15 10:30:02 [INFO] [P2P_TEST] A1: 0 incoming, 1 outgoing connections
2024-01-15 10:30:03 [INFO] [P2P_TEST] ✅ P2P connectivity verified: Bidirectional connection established
2024-01-15 10:30:03 [INFO] [P2P_TEST] 🎉 P2P CONNECTIVITY TEST PASSED: Nodes are properly connected
```

### Failure Case

When P2P connectivity fails:

```
2024-01-15 10:30:00 [ERROR] [P2P_TEST] ❌ P2P CONNECTIVITY TEST FAILED: Nodes are not properly connected
2024-01-15 10:30:00 [INFO] [P2P_TEST] Running diagnostic checks...
2024-01-15 10:30:00 [INFO] [P2P_TEST] A0 P2P port: 18080
2024-01-15 10:30:00 [INFO] [P2P_TEST] A1 P2P port: 18081
2024-01-15 10:30:00 [ERROR] [P2P_TEST] A0 does NOT have A1 in its peer list
2024-01-15 10:30:00 [INFO] [P2P_TEST] Troubleshooting guidance:
2024-01-15 10:30:00 [INFO] [P2P_TEST] 1. Verify that A1 has A0 configured as an exclusive or priority node
```

## Features

### Connection State Monitoring

The script monitors:
- Incoming connections count
- Outgoing connections count
- Connection state (e.g., state=1 for established)
- Live time (duration of the connection)

### Bidirectional Verification

The script ensures that:
- Node A0 has a connection to Node A1
- Node A1 has a connection to Node A0
- Both connections are active and established

### Diagnostic Information

When connectivity fails, the script provides:
- P2P port configuration for each node
- Peer list analysis
- Troubleshooting steps
- Common configuration issues

## Error Handling

The script includes comprehensive error handling:

- **Retry Logic**: Automatic retries with exponential backoff for transient failures
- **Timeout Protection**: Prevents hanging on unresponsive nodes
- **Detailed Logging**: All operations are logged with timestamps and severity levels
- **Graceful Degradation**: Continues diagnostic checks even if some operations fail

## Integration with Other Scripts

This script is designed to work with:

- `simple_test.py`: Can be called as part of the overall simulation test
- `sync_check.py`: P2P connectivity is a prerequisite for synchronization
- `transaction_script.py`: Transactions require P2P connectivity for propagation

## Troubleshooting

### Common Issues

1. **No P2P Connections**
   - Check if nodes are started in the correct order (A0 before A1)
   - Verify exclusive node configuration in Shadow YAML
   - Ensure `--allow-local-ip` flag is set

2. **One-way Connection**
   - Usually indicates firewall or network configuration issues
   - Check if P2P ports are correctly configured and not conflicting

3. **Connection Drops**
   - May indicate resource constraints
   - Check Shadow simulation logs for errors

### Debug Mode

For more detailed debugging, you can modify the logging level in the script or check the Shadow simulation logs in `shadow.data/hosts/*/stdout-*.log`.

## Differences from Bash Version

### Improvements

1. **Better Error Handling**: Python exceptions provide more detailed error information
2. **Type Safety**: Type hints improve code reliability
3. **Structured Data**: JSON parsing is more robust than grep/sed
4. **Modular Design**: Uses shared modules for network config and error handling
5. **Enhanced Logging**: Consistent logging format with severity levels

### Compatibility

The Python version maintains full compatibility with the bash version:
- Same exit codes (0 for success, 1 for failure)
- Same verification logic
- Same diagnostic output format

## Exit Codes

- `0`: P2P connectivity test passed
- `1`: P2P connectivity test failed or error occurred

## See Also

- `network_config.py`: Network configuration module
- `error_handling.py`: Error handling and verification functions
- `test_p2p_connectivity.sh`: Original bash version (kept as fallback)