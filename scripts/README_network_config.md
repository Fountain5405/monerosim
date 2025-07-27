# Network Configuration Module

This directory contains Python modules for MoneroSim, including the network configuration module that provides centralized network settings.

## network_config.py

The `network_config.py` module is a Python equivalent of `network_config.sh`, providing the same configuration values in a Python-friendly format.

### Features

- All network configuration values from the shell script
- Helper functions to get configuration by node/wallet ID
- Type hints for better IDE support
- Integration with the error_handling module for logging

### Usage

#### Direct Import of Variables

```python
from network_config import A0_IP, A0_RPC, WALLET1_RPC, WALLET1_NAME

# Use the variables directly
print(f"Mining node IP: {A0_IP}")
print(f"Mining node RPC URL: {A0_RPC}")
```

#### Using Helper Functions

```python
from network_config import get_daemon_config, get_wallet_config

# Get daemon configuration
mining_node = get_daemon_config("A0")
print(f"Mining node: {mining_node['rpc_url']}")

# Get wallet configuration
wallet1 = get_wallet_config(1)
print(f"Wallet name: {wallet1['name']}")
print(f"Wallet RPC: {wallet1['rpc_url']}")
print(f"Wallet password: {wallet1['password']}")
```

#### Get All Configuration

```python
from network_config import get_all_config

# Get all configuration as a dictionary
config = get_all_config()
for key, value in config.items():
    print(f"{key}: {value}")
```

### Available Variables

**Daemon Nodes:**
- `A0_IP`, `A0_RPC_PORT`, `A0_RPC` - Mining node
- `A1_IP`, `A1_RPC_PORT`, `A1_RPC` - Sync node

**Wallet Nodes:**
- `WALLET1_IP`, `WALLET1_RPC_PORT`, `WALLET1_RPC` - Mining wallet
- `WALLET2_IP`, `WALLET2_RPC_PORT`, `WALLET2_RPC` - Recipient wallet

**Wallet Credentials:**
- `WALLET1_NAME`, `WALLET1_PASSWORD` - Mining wallet credentials
- `WALLET2_NAME`, `WALLET2_PASSWORD` - Recipient wallet credentials

**Fallback Addresses:**
- `WALLET1_ADDRESS_FALLBACK` - Fallback address for wallet 1
- `WALLET2_ADDRESS_FALLBACK` - Fallback address for wallet 2

**Backward Compatibility:**
- `DAEMON_IP`, `DAEMON_RPC_PORT` - Points to A0 (mining node)

### Testing

Run the test script to verify the module is working correctly:

```bash
./venv/bin/python scripts/test_network_config.py
```

### Example

See `example_network_usage.py` for a complete example of how to use the network configuration module in your scripts.

## Migration from Shell Scripts

If you're converting a shell script to Python, here's how to map the variables:

| Shell Variable | Python Import |
|----------------|---------------|
| `$A0_IP` | `from network_config import A0_IP` |
| `$A0_RPC` | `from network_config import A0_RPC` |
| `$WALLET1_RPC` | `from network_config import WALLET1_RPC` |
| etc. | etc. |

The Python module provides the exact same values as the shell script, ensuring compatibility.