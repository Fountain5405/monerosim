# MoneroSim Python Scripts Guide

This comprehensive guide covers all Python scripts in the MoneroSim project, including testing scripts, monitoring tools, and the agent framework.

## Table of Contents

1. [Overview](#overview)
2. [Environment Setup](#environment-setup)
3. [Agent Discovery System](#agent-discovery-system)
4. [Core Testing Scripts](#core-testing-scripts)
5. [Monitoring Scripts](#monitoring-scripts)
6. [Agent Framework](#agent-framework)
7. [Supporting Modules](#supporting-modules)
8. [Usage Examples](#usage-examples)
9. [Testing and Quality Assurance](#testing-and-quality-assurance)
10. [Migration from Bash](#migration-from-bash)
11. [Migration from Legacy Network Configuration](#migration-from-legacy-network-configuration)
12. [Best Practices](#best-practices)

## Overview

MoneroSim uses Python scripts as the primary implementation for testing, monitoring, and simulating cryptocurrency network behavior. These scripts provide:

- **Reliability**: Comprehensive error handling and retry logic
- **Maintainability**: Clean code structure with type hints
- **Testability**: 95%+ unit test coverage
- **Cross-platform**: Works on Linux, macOS, and Windows
- **Performance**: Efficient RPC communication and resource usage

## Environment Setup

### Prerequisites

- Python 3.6 or higher (3.8+ recommended)
- pip package manager
- Virtual environment support

### Installation

```bash
# Navigate to MoneroSim directory
cd /path/to/monerosim

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r scripts/requirements.txt
```

### Required Packages

```txt
# scripts/requirements.txt
requests>=2.25.0      # HTTP library for RPC calls
pytest>=6.0.0         # Testing framework
pytest-cov>=2.10.0    # Coverage reporting
black>=20.8b1         # Code formatter
pylint>=2.6.0         # Code linter
mypy>=0.790           # Type checker
```

## Agent Discovery System

MoneroSim now uses a dynamic agent discovery system that replaces the legacy hardcoded network configuration. The new system automatically discovers agents and their configurations from shared state files.

### Key Components

- **agent_discovery.py**: Core module for dynamic agent discovery
- **Shared State Files**: JSON files in `/tmp/monerosim_shared/` that store agent information
- **Agent Registry**: Central registry of all agents in the simulation

### Benefits of Agent Discovery

1. **Dynamic Configuration**: No hardcoded IP addresses or ports
2. **Scalability**: Automatically adapts to different simulation sizes
3. **Flexibility**: Supports different agent types and attributes
4. **Maintainability**: Easier to modify and extend the system

For detailed information about the agent discovery system, see [scripts/README_agent_discovery.md](scripts/README_agent_discovery.md).

## Core Testing Scripts

### simple_test.py

**Purpose**: Validates basic Monero network functionality including mining and synchronization.

**Location**: `scripts/simple_test.py`

**Features**:
- Daemon readiness verification
- Block generation testing
- Network synchronization checking
- Block hash consistency validation

**Usage**:
```bash
python3 scripts/simple_test.py
```

**Configuration**:
- Uses `agent_discovery.py` for dynamic agent discovery
- Configurable timeouts and retry attempts
- Supports custom RPC endpoints via environment variables

**Example Output**:
```
[INFO] Starting simple test for Monero network
[INFO] Checking daemon readiness...
[INFO] A0 daemon is ready at height 100
[INFO] A1 daemon is ready at height 100
[INFO] ✅ SUCCESS: Nodes are synchronized
[INFO] ✅ Basic mining and synchronization test PASSED
```

### block_controller.py (DEPRECATED)

**Purpose**: Manages continuous block generation for mining nodes. **This script is deprecated in favor of the `BlockControllerAgent` (defined in `agents/block_controller.py`) which is part of the unified agent-based simulation framework.** This standalone script will only use the first discovered miner for block generation. For advanced, scalable block generation with weighted random selection, please use the agent-based simulation by configuring `block_controller` in your `config.yaml`.

**Location**: `scripts/block_controller.py`

**Features**:
- Dynamic agent discovery (limited to first miner)
- Automatic configuration of daemon and wallet endpoints
- Basic block generation control
- Robust error handling

**Usage**:
```bash
# Run with default settings (uses first discovered miner)
python3 scripts/block_controller.py

# Custom configuration
python3 scripts/block_controller.py --block-interval 60 --blocks-per-generation 2
```

**Command-line Options**:
- `--block-interval`: Time in seconds between block generations (default: 120)
- `--blocks-per-generation`: Number of blocks to generate each time (default: 1)
- `--max-attempts`: Maximum number of attempts for connection and operations (default: 30)
- `--retry-delay`: Base delay in seconds between retries (default: 2)
- `--test-mode`: Run in test mode (discover agents but don't start block generation)

### sync_check.py

**Purpose**: Verifies that all nodes in the network are synchronized.

**Location**: `scripts/sync_check.py`

**Features**:
- Configurable synchronization checking
- Height difference threshold validation
- Continuous monitoring mode
- Detailed sync status reporting

**Usage**:
```bash
# Single check
python3 scripts/sync_check.py

# Continuous monitoring
python3 scripts/sync_check.py --continuous

# Custom parameters
python3 scripts/sync_check.py --wait-time 30 --height-threshold 5
```

**Command-line Options**:
- `--wait-time`: Seconds between checks (default: 10)
- `--max-attempts`: Maximum retry attempts (default: 30)
- `--height-threshold`: Maximum acceptable height difference (default: 2)
- `--continuous`: Run continuously until interrupted

### transaction_script.py

**Purpose**: Handles wallet operations and transaction sending between nodes.

**Location**: `scripts/transaction_script.py`

**Features**:
- Wallet creation and management
- Balance checking with retry logic
- Transaction creation and sending
- Automatic dust sweeping
- Comprehensive error handling

**Usage**:
```bash
python3 scripts/transaction_script.py
```

**Transaction Flow**:
1. Opens or creates wallets on different nodes
2. Waits for mining wallet to have sufficient balance
3. Sends transaction from wallet1 to wallet2
4. Reports transaction details and status

### test_p2p_connectivity.py

**Purpose**: Verifies P2P connections between Monero nodes.

**Location**: `scripts/test_p2p_connectivity.py`

**Features**:
- Daemon readiness checking
- Bidirectional connection verification
- Connection detail reporting
- Retry logic for transient failures

**Usage**:
```bash
# Must run within Shadow environment
python3 scripts/test_p2p_connectivity.py
```

**Note**: This script requires execution within the Shadow simulation environment as it needs access to the private network.

## Monitoring Scripts

### monitor.py

**Purpose**: Provides real-time monitoring of Monero nodes.

**Location**: `scripts/monitor.py`

**Features**:
- Multi-node status monitoring
- Real-time updates with configurable refresh rate
- Comprehensive metrics display
- Color-coded status indicators

**Usage**:
```bash
# Default monitoring (continuous)
python3 scripts/monitor.py

# Single status check
python3 scripts/monitor.py --once

# Custom refresh rate (seconds)
python3 scripts/monitor.py --refresh 5

# Monitor specific nodes
python3 scripts/monitor.py --nodes A0=http://11.0.0.1:18081/json_rpc A1=http://11.0.0.2:18081/json_rpc
```

**Displayed Metrics**:
- Node synchronization status
- Blockchain height
- Peer connections (in/out)
- Transaction pool status
- Mining status (if applicable)
- Network difficulty
- Block time statistics

## Agent Framework

The agent framework enables realistic cryptocurrency network simulations with autonomous participants.

### Base Agent (base_agent.py)

**Purpose**: Abstract base class for all agent types.

**Location**: `agents/base_agent.py`

**Features**:
- Lifecycle management (setup, run, cleanup)
- RPC connection handling
- Shared state management
- Signal handling for graceful shutdown
- Logging configuration

**Key Methods**:
```python
class BaseAgent(ABC):
    @abstractmethod
    def setup(self):
        """Initialize agent state"""
        pass
    
    @abstractmethod
    def run(self):
        """Main agent behavior loop"""
        pass
    
    def cleanup(self):
        """Clean up resources"""
        pass
```

### Regular User Agent (regular_user.py)

**Purpose**: Simulates typical Monero users sending transactions.

**Location**: `agents/regular_user.py`

**Features**:
- Personal wallet management
- Configurable transaction patterns
- Balance monitoring

**Usage**:
```bash
python3 agents/regular_user.py \
    --name user001 \
    --daemon-url http://11.0.0.1:18081/json_rpc \
    --wallet-port 28091 \
    --transaction-interval 300
```


### Block Controller Agent (block_controller.py)

**Purpose**: Orchestrates mining.

**Location**: `agents/block_controller.py`

**Features**:
- Mining signal generation
- Blockchain progress monitoring
- Consistent block generation

**Usage**:
```bash
python3 agents/block_controller.py \
    --daemon-url http://11.0.0.1:18081/json_rpc \
    --block-interval 120
```

### Monero RPC Client (monero_rpc.py)

**Purpose**: Provides clean Python interface to Monero RPC APIs.

**Location**: `agents/monero_rpc.py`

**Features**:
- Daemon RPC methods
- Wallet RPC methods
- Automatic retry logic
- Error handling
- Type-safe responses

**Example Usage**:
```python
from monero_rpc import MoneroRPC

# Daemon RPC
daemon = MoneroRPC("http://11.0.0.1:18081/json_rpc")
info = daemon.get_info()
print(f"Height: {info['height']}")

# Wallet RPC
wallet = MoneroRPC("http://11.0.0.1:28091/json_rpc")
balance = wallet.get_balance()
print(f"Balance: {balance['balance']}")
```

## Supporting Modules

### agent_discovery.py

**Purpose**: Dynamic agent discovery system for all scripts.

**Location**: `scripts/agent_discovery.py`

**Features**:
- Discovers agents from shared state files
- Provides agent information (IP, port, RPC URL)
- Handles different agent types (miners, users, wallets)
- Includes caching for performance

**Usage**:
```python
from agent_discovery import AgentDiscovery, AgentDiscoveryError

# Create agent discovery instance
ad = AgentDiscovery()

# Get all agents
registry = ad.get_agent_registry()
print(f"Found {len(registry['agents'])} agents")

# Get miner agents
miners = ad.get_miner_agents()
print(f"Found {len(miners)} miner agents")

# Get wallet agents
wallets = ad.get_wallet_agents()
print(f"Found {len(wallets)} wallet agents")

# Get agent by ID
agent = ad.get_agent_by_id("user001")
if agent:
    print(f"Agent {agent['id']} found at {agent['ip_addr']}")
```

For detailed API documentation, see [scripts/README_agent_discovery.md](scripts/README_agent_discovery.md).

### error_handling.py

**Purpose**: Common error handling and logging utilities.

**Location**: `scripts/error_handling.py`

**Features**:
- Structured logging with colors
- RPC call wrapper with retry logic
- Exponential backoff implementation
- Consistent error reporting

**Usage**:
```python
from error_handling import setup_logging, make_rpc_call, log_info, log_error

# Setup logging
logger = setup_logging("my_script")

# Make RPC call with retry
result = make_rpc_call(url, method, params, max_retries=3)

# Log messages
log_info("Operation successful")
log_error("Operation failed", exc_info=True)
```

## Usage Examples

### Running a Complete Test Suite

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests in sequence
python3 scripts/simple_test.py && \
python3 scripts/sync_check.py && \
python3 scripts/transaction_script.py

# Run with monitoring
python3 scripts/monitor.py &
MONITOR_PID=$!
python3 scripts/simple_test.py
kill $MONITOR_PID
```

### Shadow Configuration Integration

```yaml
# In shadow.yaml
hosts:
  controller:
    processes:
    - path: /usr/bin/python3
      args: scripts/block_controller.py
      start_time: 60s
      
    - path: /usr/bin/python3
      args: scripts/monitor.py --refresh 10
      start_time: 30s
```

### Agent-Based Simulation

```bash
# Generate agent configuration
./target/release/monerosim --config config_agents_medium.yaml --output shadow_agents_output

# Run simulation
shadow shadow_agents_output/shadow_agents.yaml

# Monitor agent activity
watch -n 1 'ls -la /tmp/monerosim_shared/*.json'
```

## Testing and Quality Assurance

### Running Unit Tests

```bash
# Run all tests
python -m pytest scripts/test_*.py -v

# Run specific test file
python -m pytest scripts/test_simple_test.py -v

# Run with coverage
python -m pytest scripts/test_*.py --cov=scripts --cov-report=html

# View coverage report
open scripts/htmlcov/index.html
```

### Code Quality Tools

```bash
# Format code
black scripts/*.py agents/*.py

# Lint code
pylint scripts/*.py agents/*.py

# Type checking
mypy scripts/*.py agents/*.py
```

### Test Coverage Summary

| Module | Test File | Coverage |
|--------|-----------|----------|
| simple_test.py | test_simple_test.py | 98% |
| block_controller.py | test_block_controller.py | 96% |
| sync_check.py | test_sync_check.py | 95% |
| transaction_script.py | test_transaction_script.py | 97% |
| test_p2p_connectivity.py | test_test_p2p_connectivity.py | 94% |
| monitor.py | test_monitor.py | 92% |
| error_handling.py | test_error_handling.py | 99% |

## Migration from Bash

### Comparison

| Feature | Bash Scripts | Python Scripts |
|---------|--------------|----------------|
| Error Handling | Basic | Comprehensive with retry logic |
| Type Safety | None | Full type hints |
| Testing | Manual | 95%+ automated coverage |
| Cross-platform | Limited | Full support |
| Debugging | Difficult | Easy with proper tooling |
| Performance | Variable | Consistent and optimized |

### Migration Path

1. **Identify Dependencies**: Check which bash scripts your workflow uses
2. **Update Configurations**: Replace bash script paths with Python equivalents
3. **Test Thoroughly**: Run Python scripts in test environment
4. **Monitor Performance**: Compare results with legacy scripts
5. **Remove Legacy References**: Update documentation and configurations

## Migration from Legacy Network Configuration

MoneroSim has migrated from the legacy hardcoded network configuration approach to the new `agent_discovery.py` system with dynamic discovery. This migration provides:

1. **Dynamic Configuration**: No hardcoded IP addresses or ports
2. **Better Scalability**: Automatically adapts to different simulation sizes
3. **Improved Flexibility**: Supports different agent types and attributes
4. **Enhanced Maintainability**: Easier to modify and extend the system

### Migration Example

**Legacy approach (hardcoded configuration)**:
```python
# Note: This approach has been removed and replaced with Agent Discovery
# Legacy hardcoded network configuration approach has been removed from the project
```

**New approach (agent_discovery.py)**:
```python
from agent_discovery import AgentDiscovery, AgentDiscoveryError

try:
    ad = AgentDiscovery()
    
    # Get miner agents (dynamic)
    miners = ad.get_miner_agents()
    if miners:
        print(f"Miner RPC URL: {miners[0]['daemon_rpc_url']}")
    
    # Get wallet agents (dynamic)
    wallets = ad.get_wallet_agents()
    if wallets:
        print(f"Wallet RPC URL: {wallets[0]['wallet_rpc_url']}")
except AgentDiscoveryError as e:
    print(f"Agent discovery failed: {e}")
```

### Migration Steps

1. **Replace Imports**: Change legacy hardcoded configuration imports to `from agent_discovery import ...`
2. **Update Code Patterns**: Replace hardcoded node/wallet references with dynamic discovery
3. **Add Error Handling**: Use try/except blocks to handle `AgentDiscoveryError`
4. **Test Thoroughly**: Ensure all scripts work with the new discovery system
5. **Update Documentation**: Reflect changes in all documentation files

## Best Practices

### Script Development

1. **Use Type Hints**:
   ```python
   def get_block_count(daemon_url: str) -> int:
       """Get current block count from daemon"""
       pass
   ```

2. **Handle Errors Gracefully**:
   ```python
   try:
       result = make_rpc_call(url, method, params)
   except RPCError as e:
       log_error(f"RPC call failed: {e}")
       return None
   ```

3. **Use Agent Discovery Module**:
    ```python
    from agent_discovery import AgentDiscovery, AgentDiscoveryError
    try:
        ad = AgentDiscovery()
        agents = ad.get_miner_agents()
        # Don't hardcode URLs, use dynamic discovery
    except AgentDiscoveryError as e:
        # Handle discovery errors
        pass
    ```

4. **Add Logging**:
   ```python
   from error_handling import setup_logging, log_info
   logger = setup_logging(__name__)
   log_info("Starting operation")
   ```

### Agent Development

1. **Inherit from BaseAgent**:
   ```python
   from base_agent import BaseAgent
   
   class MyAgent(BaseAgent):
       def setup(self):
           super().setup()
           # Custom initialization
   ```


3. **Handle Signals**:
   ```python
   def signal_handler(signum, frame):
       self.cleanup()
       sys.exit(0)
   ```

### Performance Optimization

1. **Batch Operations**: Group multiple RPC calls when possible
2. **Cache Results**: Store frequently accessed data
3. **Use Async Operations**: For I/O-bound operations
4. **Monitor Resource Usage**: Track memory and CPU usage

### Security Considerations

1. **Validate Input**: Always validate RPC responses
2. **Use Secure Connections**: HTTPS for remote RPC
3. **Limit Permissions**: Run with minimal required privileges
4. **Audit Logs**: Monitor script activities

## Troubleshooting

### Common Issues

1. **Import Errors**:
   ```bash
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/scripts"
   ```

2. **RPC Connection Failed**:
   - Check daemon is running
   - Verify agent discovery is working
   - Check shared state files in `/tmp/monerosim_shared/`
   - Test with curl manually

3. **Virtual Environment Issues**:
   ```bash
   deactivate
   rm -rf venv
   python3 -m venv venv
   source venv/bin/activate
   pip install -r scripts/requirements.txt
   ```

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
python3 scripts/simple_test.py
```

### Getting Help

1. Check individual script documentation (README_*.md files)
2. Review [scripts/README_agent_discovery.md](scripts/README_agent_discovery.md) for agent discovery information
3. Review test files for usage examples
4. Enable debug logging for detailed output
5. Check Shadow simulation logs
6. Verify shared state files in `/tmp/monerosim_shared/`

## Future Enhancements

### Planned Features

1. **WebSocket Support**: Real-time monitoring via web interface
2. **Metrics Export**: Prometheus/Grafana integration
3. **Advanced Agents**: Exchange and merchant agents
4. **Performance Profiling**: Built-in profiling tools
5. **Configuration UI**: Web-based configuration interface

### Contributing

When contributing new scripts or features:

1. Follow existing code patterns
2. Include comprehensive tests
3. Add documentation
4. Update this guide
5. Run quality checks before submitting

## Conclusion

The MoneroSim Python scripts provide a robust, reliable, and maintainable framework for cryptocurrency network simulation and testing. With comprehensive error handling, extensive testing, and clear documentation, these scripts form the foundation for advanced blockchain research and development.