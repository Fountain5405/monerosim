# Monitor Script for MoneroSim

## Overview

The `monitor.py` script provides real-time monitoring of Monero nodes running in the Shadow simulation. It displays comprehensive information about node status, blockchain synchronization, mining activity, peer connections, and transaction pool status.

## Features

- **Real-time Monitoring**: Continuously updates node status at configurable intervals
- **Multi-node Support**: Monitor multiple nodes simultaneously
- **Comprehensive Metrics**: Displays blockchain height, sync status, mining info, connections, and more
- **Node Comparison**: Shows differences between nodes for easy sync verification
- **Flexible Configuration**: Command-line options for customization
- **Single-run Mode**: Option to check status once and exit

## Usage

### Basic Usage

Monitor the default nodes (A0 and A1):
```bash
./scripts/monitor.py
```

### Monitor Specific Nodes

```bash
./scripts/monitor.py --nodes A0=http://11.0.0.1:18081/json_rpc A1=http://11.0.0.2:18081/json_rpc
```

### Single Status Check

Run once and exit:
```bash
./scripts/monitor.py --once
```

### Custom Refresh Interval

Update every 5 seconds:
```bash
./scripts/monitor.py --refresh 5
```

### No Screen Clear

Keep all updates visible (don't clear screen):
```bash
./scripts/monitor.py --no-clear
```

## Command-line Options

- `--nodes`: List of nodes to monitor (format: name=url)
- `--refresh`: Refresh interval in seconds (default: 10)
- `--max-attempts`: Maximum RPC attempts (default: 3)
- `--retry-delay`: Delay between RPC attempts (default: 2)
- `--no-clear`: Don't clear screen between updates
- `--once`: Run once and exit (no continuous monitoring)

## Displayed Information

For each node, the monitor displays:

1. **Basic Status**
   - Node name and status
   - Synchronization state
   - Current height vs target height
   - Sync progress percentage

2. **Mining Information**
   - Mining active/inactive status
   - Current hashrate (if mining)

3. **Network Information**
   - Incoming/outgoing connections
   - White/grey peerlist sizes

4. **Transaction Pool**
   - Current pool size
   - Total transaction count

5. **Blockchain Information**
   - Current difficulty
   - Block reward (if available)

6. **Node Comparison**
   - Height differences between nodes
   - Connection counts
   - Mining status comparison

## Examples

### Monitor with Custom Settings
```bash
# Monitor every 30 seconds with more RPC attempts
./scripts/monitor.py --refresh 30 --max-attempts 5 --retry-delay 3
```

### Quick Status Check
```bash
# Check current status and exit
./scripts/monitor.py --once
```

### Continuous Logging
```bash
# Monitor without clearing screen (useful for logging)
./scripts/monitor.py --no-clear > monitor.log 2>&1
```

## Integration with Shadow

The monitor script is designed to work within the Shadow simulation environment. It uses the network configuration from `network_config.py` and error handling from `error_handling.py`.

## Error Handling

The script includes robust error handling:
- Verifies node availability before monitoring
- Handles RPC failures gracefully
- Displays error messages for unreachable nodes
- Can be interrupted cleanly with Ctrl+C

## Requirements

- Python 3.6+
- Access to Monero daemon RPC endpoints
- `error_handling.py` and `network_config.py` modules

## Troubleshooting

1. **"Node not ready" errors**: Ensure the Shadow simulation is running and nodes are initialized
2. **Connection refused**: Check that the RPC ports are correct and accessible
3. **Import errors**: Ensure the script is run from the correct directory or PYTHONPATH is set

## Related Scripts

- `simple_test.py`: Basic functionality testing
- `sync_check.py`: Dedicated synchronization verification
- `block_controller.py`: Block generation control