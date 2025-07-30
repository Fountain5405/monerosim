# Monerosim Python Scripts

This directory contains the primary Python scripts for testing, monitoring, and managing Monero nodes within the Shadow network simulation environment. These scripts have been fully migrated from Bash to Python and are now the official implementation, providing improved reliability, maintainability, and cross-platform compatibility.

## 📋 Table of Contents

- [Overview](#overview)
- [Available Scripts](#available-scripts)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Script Descriptions](#script-descriptions)
- [Common Modules](#common-modules)
- [Testing](#testing)
- [Migration Information](#migration-information)
- [Troubleshooting](#troubleshooting)

## Overview

The Monerosim Python scripts are the primary implementation for:
- Testing Monero network functionality
- Monitoring node status and synchronization
- Managing block generation and transactions
- Verifying P2P connectivity

All scripts share common modules for configuration and error handling, ensuring consistent behavior across the toolkit. The legacy Bash scripts have been moved to `legacy_scripts/` directory and are deprecated.

## Available Scripts

### Core Testing Scripts

| Script | Purpose | Documentation |
|--------|---------|---------------|
| [`simple_test.py`](#simple_testpy) | Basic mining and synchronization test | [README](README_simple_test.md) |
| [`block_controller.py`](#block_controllerpy) | Continuous block generation control | [README](README_block_controller.md) |
| [`sync_check.py`](#sync_checkpy) | Network synchronization verification | [README](README_sync_check.md) |
| [`transaction_script.py`](#transaction_scriptpy) | Transaction sending and wallet management | [README](README_transaction_script.md) |
| [`test_p2p_connectivity.py`](#test_p2p_connectivitypy) | P2P connection verification | [README](README_test_p2p_connectivity.md) |

### Monitoring Scripts

| Script | Purpose | Documentation |
|--------|---------|---------------|
| [`monitor.py`](#monitorpy) | Real-time node monitoring dashboard | [README](README_monitor.md) |

### Supporting Modules

| Module | Purpose | Used By |
|--------|---------|---------|
| [`network_config.py`](#network_configpy) | Centralized network configuration | All scripts |
| [`error_handling.py`](#error_handlingpy) | Common error handling and logging | All scripts |

## Installation

### Prerequisites

- Python 3.6 or higher
- pip (Python package manager)
- Access to Monerosim project directory

### Setup Steps

1. **Navigate to the Monerosim directory:**
   ```bash
   cd /home/lever65/monerosim_dev/monerosim
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install required packages:**
   ```bash
   pip install -r scripts/requirements.txt
   ```

## Quick Start

### Running a Basic Test

```bash
# Test mining and synchronization
python3 scripts/simple_test.py

# Monitor nodes in real-time
python3 scripts/monitor.py

# Check synchronization status
python3 scripts/sync_check.py
```

### Running Within Shadow Simulation

Most scripts are designed to run within the Shadow simulation environment. They are typically configured in the Shadow YAML file and executed automatically during simulation.

## Script Descriptions

### simple_test.py

**Purpose:** Validates basic Monero network functionality including mining and synchronization.

**Features:**
- Verifies daemon readiness
- Tests block generation
- Checks network synchronization
- Validates block hash consistency

**Usage:**
```bash
python3 scripts/simple_test.py
```

**Example Output:**
```
[INFO] Starting simple test for Monero network
[INFO] ✅ SUCCESS: Nodes are synchronized
[INFO] ✅ Basic mining and synchronization test PASSED
```

---

### block_controller.py

**Purpose:** Manages continuous block generation for mining nodes.

**Features:**
- Creates and manages mining wallet
- Generates blocks at regular intervals (default: 2 minutes)
- Handles wallet RPC operations
- Graceful shutdown on interruption

**Usage:**
```bash
python3 scripts/block_controller.py
```

**Key Configuration:**
- Block interval: 120 seconds
- Wallet name: "mining_wallet"
- Default ports: Daemon (18081), Wallet (28091)

---

### sync_check.py

**Purpose:** Verifies that all nodes in the network are synchronized.

**Features:**
- Configurable sync checking intervals
- Height difference threshold checking
- Continuous monitoring mode
- Detailed sync status reporting

**Usage:**
```bash
# Single check
python3 scripts/sync_check.py

# Continuous monitoring
python3 scripts/sync_check.py --continuous --wait-time 30

# Custom parameters
python3 scripts/sync_check.py --max-attempts 50 --height-threshold 5
```

**Command-line Options:**
- `--wait-time`: Seconds between checks (default: 10)
- `--max-attempts`: Maximum retry attempts (default: 30)
- `--height-threshold`: Maximum acceptable height difference (default: 2)
- `--continuous`: Run continuously

---

### transaction_script.py

**Purpose:** Handles wallet operations and transaction sending between nodes.

**Features:**
- Wallet creation and management
- Balance checking with retry logic
- Transaction sending with automatic dust sweeping
- Comprehensive error handling

**Usage:**
```bash
python3 scripts/transaction_script.py
```

**Transaction Flow:**
1. Opens/creates wallets
2. Waits for sufficient balance
3. Sends transaction from wallet1 to wallet2
4. Reports transaction details

---

### test_p2p_connectivity.py

**Purpose:** Verifies P2P connections between Monero nodes.

**Features:**
- Daemon readiness checking
- Bidirectional connection verification
- Connection detail reporting
- Retry logic for transient failures

**Usage:**
```bash
# Must run within Shadow environment
python3 scripts/test_p2p_connectivity.py
```

**Note:** This script must be executed within the Shadow simulation environment as it needs access to the private network.

---

### monitor.py

**Purpose:** Provides real-time monitoring of Monero nodes.

**Features:**
- Multi-node monitoring
- Real-time status updates
- Comprehensive metrics display
- Configurable refresh intervals

**Usage:**
```bash
# Default monitoring
python3 scripts/monitor.py

# Single status check
python3 scripts/monitor.py --once

# Custom refresh rate
python3 scripts/monitor.py --refresh 5

# Monitor specific nodes
python3 scripts/monitor.py --nodes A0=http://11.0.0.1:18081/json_rpc A1=http://11.0.0.2:18081/json_rpc
```

**Displayed Metrics:**
- Node synchronization status
- Blockchain height
- Peer connections
- Transaction pool status
- Mining information (when available)

---

### network_config.py

**Purpose:** Centralized configuration for all scripts.

**Features:**
- Network topology definition
- Node IP addresses and ports
- Wallet configurations
- Common parameters

**Usage:**
```python
from network_config import NetworkConfig

config = NetworkConfig()
daemon_url = config.get_daemon_url("A0")
```

---

### error_handling.py

**Purpose:** Common error handling and logging utilities.

**Features:**
- Structured logging with colors
- RPC call wrapper with retry logic
- Exponential backoff implementation
- Consistent error reporting

**Usage:**
```python
from error_handling import setup_logging, make_rpc_call, log_info

logger = setup_logging("my_script")
log_info("Starting operation")
result = make_rpc_call(url, method, params)
```

## Testing

### Running Unit Tests

All scripts include comprehensive unit tests:

```bash
# Run all tests
python -m pytest scripts/test_*.py -v

# Run tests for a specific script
python -m pytest scripts/test_simple_test.py -v

# Run with coverage
python -m pytest scripts/test_*.py --cov=scripts --cov-report=html
```

### Test Files

| Test File | Tests For | Test Count |
|-----------|-----------|------------|
| `test_simple_test.py` | simple_test.py | 10 |
| `test_block_controller.py` | block_controller.py | 10 |
| `test_sync_check.py` | sync_check.py | 3 |
| `test_transaction_script.py` | transaction_script.py | 12 |
| `test_test_p2p_connectivity.py` | test_p2p_connectivity.py | 9 |
| `test_monitor.py` | monitor.py | 6 |
| `test_network_config.py` | network_config.py | 8 |
| `test_error_handling.py` | error_handling.py | 7 |

## Migration Information

The Python scripts have been successfully migrated from the original Bash scripts and are now the primary implementation. The migration is complete and verified in production use.

- [Migration Guide](MIGRATION_GUIDE.md) - Comprehensive migration documentation
- [Migration Summary](MIGRATION_SUMMARY.md) - Statistics and benefits analysis
- Individual migration summaries in script directories

**Note**: The original Bash scripts are deprecated and have been moved to the `legacy_scripts/` directory for historical reference only.

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure correct Python path
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/scripts"
   ```

2. **Connection Refused**
   - Ensure Shadow simulation is running
   - Verify node IP addresses in network_config.py
   - Check firewall settings

3. **Module Not Found**
   ```bash
   # Activate virtual environment
   source venv/bin/activate
   
   # Reinstall requirements
   pip install -r scripts/requirements.txt
   ```

4. **Permission Denied**
   ```bash
   # Make scripts executable
   chmod +x scripts/*.py
   ```

### Debug Mode

Most scripts support verbose logging:
```bash
# Set log level via environment variable
export LOG_LEVEL=DEBUG
python3 scripts/simple_test.py
```

### Getting Help

1. Check individual script documentation (README_*.md files)
2. Review test summaries (*_TEST_SUMMARY.md files)
3. Examine unit tests for usage examples
4. Check Shadow logs in `shadow.data/hosts/*/`

## Contributing

When adding new scripts or modifying existing ones:

1. Follow the established patterns for error handling and logging
2. Use type hints for all functions
3. Include comprehensive docstrings
4. Write unit tests for new functionality
5. Update relevant documentation

## Python Scripts vs Legacy Bash Scripts

### Current Status

- **Python Scripts**: Primary implementation, fully tested and verified
- **Bash Scripts**: Deprecated, moved to `legacy_scripts/` directory

### Why Python?

1. **Better Error Handling**: Comprehensive exception handling and retry logic
2. **Cross-Platform**: Works consistently across different operating systems
3. **Type Safety**: Type hints improve code clarity and catch errors early
4. **Testing**: Extensive unit test coverage (95%+)
5. **Maintainability**: Cleaner code structure and better modularity

### Migration Path

If you have custom scripts or workflows using the old Bash scripts:

1. Review the Python equivalents in this directory
2. Update your Shadow configuration files to use Python scripts
3. Test thoroughly in your environment
4. Remove references to legacy Bash scripts

## License

These scripts are part of the Monerosim project and follow the same license terms as the main project.