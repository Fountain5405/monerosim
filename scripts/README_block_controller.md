# Block Controller Script

## Overview

The `block_controller.py` script is responsible for controlling block generation in the MoneroSim simulation. It connects to the mining node's daemon and generates blocks at regular intervals using the wallet's mining address.

This is a Python port of the original `block_controller.sh` bash script, providing improved error handling, better maintainability, and more robust operation.

## Features

- **Automatic Wallet Management**: Creates or opens the mining wallet automatically
- **Continuous Block Generation**: Generates blocks at configurable intervals (default: 2 minutes)
- **Robust Error Handling**: Includes retry logic and comprehensive error reporting
- **Network Configuration**: Uses centralized network configuration from `network_config.py`
- **Graceful Shutdown**: Handles interruption signals properly

## Usage

### Basic Usage

```bash
# From the monerosim directory
python3 scripts/block_controller.py

# Or make it executable and run directly
./scripts/block_controller.py
```

### Within Shadow Simulation

The script is typically run as part of the Shadow simulation environment. It's configured in the `shadow.yaml` file to start automatically.

## Configuration

The script uses the following configuration parameters:

- **Block Interval**: 120 seconds (2 minutes) between block generations
- **Blocks per Generation**: 1 block generated each time
- **Max Attempts**: 30 attempts for RPC operations
- **Retry Delay**: 2 seconds base delay with exponential backoff

These can be modified by editing the constants at the top of the script:

```python
BLOCK_INTERVAL = 120  # 2 minutes in seconds
BLOCKS_PER_GENERATION = 1  # Number of blocks to generate each time
MAX_ATTEMPTS = 30
RETRY_DELAY = 2
```

## Dependencies

- Python 3.6+
- `error_handling.py`: Provides logging and retry functionality
- `network_config.py`: Provides network configuration values
- `requests` library: For HTTP/RPC communication

## How It Works

1. **Initialization**:
   - Verifies the daemon is ready and responsive
   - Checks and creates the wallet directory if needed
   - Verifies the wallet RPC service is ready

2. **Wallet Setup**:
   - Creates a new wallet or opens an existing one
   - Retrieves the wallet address for mining rewards

3. **Block Generation Loop**:
   - Gets the current blockchain height
   - Generates the specified number of blocks
   - Logs the results and new height
   - Waits for the configured interval before generating more blocks

## Error Handling

The script includes comprehensive error handling:

- **Connection Errors**: Retries with exponential backoff
- **RPC Errors**: Logs detailed error information and retries
- **Wallet Errors**: Handles "wallet already exists" gracefully
- **Unexpected Errors**: Catches and logs all unexpected exceptions

## Logging

All operations are logged with timestamps and severity levels:

- **INFO**: Normal operations and status updates
- **WARNING**: Recoverable issues and retries
- **ERROR**: Failed operations that may affect functionality
- **CRITICAL**: Fatal errors that prevent operation

## Comparison with bash version

The Python version provides several improvements over the original bash script:

1. **Better Error Handling**: More sophisticated retry logic with exponential backoff
2. **Type Safety**: Type hints for better code clarity
3. **Modularity**: Cleaner function separation and reusable components
4. **Cross-platform**: More portable than bash-specific constructs
5. **Easier Testing**: Python functions are easier to unit test

## Troubleshooting

### Script won't start
- Ensure the daemon is running and accessible
- Check that the wallet RPC service is running
- Verify network configuration in `network_config.py`

### Block generation fails
- Check daemon logs for mining-related errors
- Ensure the wallet has a valid address
- Verify the daemon is properly configured for mining

### Connection errors
- Check firewall settings
- Verify IP addresses and ports in configuration
- Ensure Shadow simulation is running

## Example Output

```
2024-01-15 10:30:00 [INFO] [BLOCK_CONTROLLER] Starting block controller script
2024-01-15 10:30:01 [INFO] [BLOCK_CONTROLLER] Verifying Daemon readiness...
2024-01-15 10:30:02 [INFO] [BLOCK_CONTROLLER] Daemon is ready. Status: OK, Height: 100
2024-01-15 10:30:02 [INFO] [BLOCK_CONTROLLER] Creating a new wallet: mining_wallet...
2024-01-15 10:30:03 [INFO] [BLOCK_CONTROLLER] Successfully created new wallet: mining_wallet
2024-01-15 10:30:03 [INFO] [BLOCK_CONTROLLER] Using wallet address: 9tUBn...
2024-01-15 10:30:03 [INFO] [BLOCK_CONTROLLER] Starting block generation with address: 9tUBn...
2024-01-15 10:30:03 [INFO] [BLOCK_CONTROLLER] Generating 1 block(s)...
2024-01-15 10:30:05 [INFO] [BLOCK_CONTROLLER] Block generation successful! Generated 1 blocks
2024-01-15 10:30:05 [INFO] [BLOCK_CONTROLLER] New height: 101
2024-01-15 10:30:05 [INFO] [BLOCK_CONTROLLER] Total blocks generated in this session: 1
2024-01-15 10:30:05 [INFO] [BLOCK_CONTROLLER] Waiting 120 seconds for the next block...