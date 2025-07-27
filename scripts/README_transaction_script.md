# Transaction Script for MoneroSim

## Overview

The `transaction_script.py` is a Python script that handles transaction operations in the MoneroSim Shadow network simulation. It provides a robust and reliable way to test transaction functionality between Monero nodes in the simulated environment.

## Features

- **Wallet Management**: Creates or opens wallets for both nodes
- **Address Generation**: Retrieves wallet addresses for transactions
- **Balance Checking**: Waits for sufficient balance before sending transactions
- **Transaction Sending**: Sends transactions with automatic dust sweeping if needed
- **Error Handling**: Comprehensive error handling with retry logic
- **Logging**: Detailed logging using the MoneroSim logging framework

## Prerequisites

- MoneroSim simulation must be running (via Shadow)
- Both daemon nodes (A0 and A1) must be operational
- Wallet RPC services must be accessible
- Python 3.6+ with required dependencies

## Usage

### Basic Usage

```bash
# From the MoneroSim root directory
./scripts/transaction_script.py
```

### Within Shadow Simulation

The script is automatically executed as part of the Shadow simulation when configured in the Shadow YAML file.

## Script Flow

1. **Wallet Initialization**
   - Creates new wallets if they don't exist
   - Opens existing wallets if already created
   - Handles both wallet1 (mining wallet) and wallet2 (recipient wallet)

2. **Address Retrieval**
   - Gets the recipient address from wallet2
   - Uses this address as the destination for transactions

3. **Balance Verification**
   - Checks wallet1 balance
   - Waits for sufficient balance (mining rewards)
   - Configurable timeout and retry attempts

4. **Transaction Execution**
   - Sends 0.1 XMR from wallet1 to wallet2
   - Handles fragmented inputs with automatic dust sweeping
   - Provides transaction details (hash, key, amount, fee)

5. **Result Reporting**
   - Displays transaction success/failure
   - Logs all important transaction details
   - Provides clear exit codes for automation

## Configuration

The script uses configuration from `network_config.py`:

- **Wallet1 (Mining Wallet)**:
  - IP: 11.0.0.3
  - RPC Port: 28091
  - Name: mining_wallet
  - Password: test123

- **Wallet2 (Recipient Wallet)**:
  - IP: 11.0.0.4
  - RPC Port: 28092
  - Name: recipient_wallet
  - Password: test456

- **Transaction Settings**:
  - Amount: 0.1 XMR
  - Ring Size: 7
  - Priority: 0 (default)

## Error Handling

The script includes comprehensive error handling:

- **Wallet Errors**: Handles wallet creation/opening failures
- **Network Errors**: Retries on RPC connection failures
- **Balance Issues**: Waits for sufficient balance with timeout
- **Transaction Errors**: Handles dust sweeping for fragmented inputs
- **Validation**: Verifies all responses before proceeding

## Comparison with send_transaction.py

While `send_transaction.py` exists as a standalone transaction sender, `transaction_script.py` offers:

- Integration with MoneroSim's error handling framework
- Better retry logic and timeout handling
- Consistent logging with other MoneroSim components
- More robust wallet initialization
- Enhanced error reporting

## Exit Codes

- `0`: Success - Transaction completed successfully
- `1`: Failure - Various failure conditions (see logs for details)

## Troubleshooting

### Common Issues

1. **Wallet Creation Fails**
   - Check if wallet RPC services are running
   - Verify network connectivity between nodes
   - Check wallet directory permissions

2. **Insufficient Balance**
   - Ensure mining is working on node A0
   - Wait longer for mining rewards to accumulate
   - Check if blocks are being generated

3. **Transaction Fails with Error -19**
   - This indicates fragmented inputs
   - The script automatically handles this with dust sweeping
   - Wait for the sweep transaction to complete

4. **Connection Timeouts**
   - Verify Shadow simulation is running
   - Check if wallet RPC ports are accessible
   - Review Shadow logs for network issues

### Debug Mode

For more detailed debugging, check the logs in:
- `shadow.data/hosts/wallet1/wallet1.1000.stdout`
- `shadow.data/hosts/wallet2/wallet2.1000.stdout`

## Integration with Other Scripts

This script works in conjunction with:
- `simple_test.py`: Ensures nodes are synchronized before transactions
- `block_controller.py`: Controls block generation for mining rewards
- `monitor.py`: Monitors overall simulation health
- `sync_check.py`: Verifies network synchronization

## Future Enhancements

Potential improvements for future versions:
- Configurable transaction amounts via command-line arguments
- Support for multiple transactions in a single run
- Transaction verification and confirmation checking
- Performance metrics collection
- Support for more complex transaction patterns