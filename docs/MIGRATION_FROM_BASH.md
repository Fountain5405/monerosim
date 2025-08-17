# Migration Guide: From Bash Scripts to Python Scripts

This guide helps you transition from the legacy bash scripts to the new Python implementation in Monerosim. The Python migration provides improved reliability, better error handling, and cross-platform compatibility.

## Overview of Changes

The Python migration replaces all bash testing scripts with equivalent Python implementations while maintaining 100% feature parity. The new scripts are located in the `scripts/` directory, while legacy bash scripts have been moved to `legacy_scripts/`.

## Benefits of Python Migration

1. **Better Error Handling**: Comprehensive exception handling with detailed error messages
2. **Cross-Platform Compatibility**: Works consistently across different operating systems
3. **Improved Reliability**: Robust retry logic and connection handling
4. **Enhanced Logging**: Structured, colored logging with configurable levels
5. **Type Safety**: Type hints improve code clarity and catch errors early
6. **Testability**: 95%+ test coverage with comprehensive unit tests
7. **Maintainability**: Cleaner code structure with reusable modules

## Script Mapping

| Legacy Bash Script | New Python Script | Purpose |
|-------------------|-------------------|---------|
| `legacy_scripts/simple_test.sh` | `scripts/simple_test.py` | Basic functionality test |
| `legacy_scripts/sync_check.sh` | `scripts/sync_check.py` | Network synchronization verification |
| `legacy_scripts/block_controller.sh` | `scripts/block_controller.py` (DEPRECATED) | Block generation control (use `BlockControllerAgent` for agent-based simulations) |
| `legacy_scripts/monitor_script.sh` | `scripts/monitor.py` | Real-time simulation monitoring |
| `legacy_scripts/test_p2p_connectivity.sh` | `scripts/test_p2p_connectivity.py` | P2P connection verification |
| N/A | `scripts/transaction_script.py` | Enhanced transaction handling |

## Setting Up Python Environment

### 1. Create Virtual Environment

```bash
cd /home/lever65/monerosim_dev/monerosim
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# or
venv\Scripts\activate  # On Windows
```

### 2. Install Dependencies

```bash
pip install -r scripts/requirements.txt
```

### 3. Verify Installation

```bash
python scripts/simple_test.py --help
```

## Command-Line Differences

### Simple Test

**Old (Bash):**
```bash
./legacy_scripts/simple_test.sh
```

**New (Python):**
```bash
python scripts/simple_test.py
# or with options
python scripts/simple_test.py --log-level DEBUG --timeout 300
```

### Sync Check

**Old (Bash):**
```bash
./legacy_scripts/sync_check.sh
```

**New (Python):**
```bash
python scripts/sync_check.py
# or with custom parameters
python scripts/sync_check.py --max-attempts 20 --check-interval 5
```

### Block Controller (DEPRECATED)

**Old (Bash):**
```bash
./legacy_scripts/block_controller.sh start
./legacy_scripts/block_controller.sh stop
```

**New (Python - DEPRECATED):**
```bash
# This script is deprecated. For agent-based simulations, use BlockControllerAgent.
python scripts/block_controller.py --block-interval 60 --blocks-per-generation 1
```

### Monitor

**Old (Bash):**
```bash
./legacy_scripts/monitor_script.sh
```

**New (Python):**
```bash
python scripts/monitor.py
# or with options
python scripts/monitor.py --interval 5 --show-transactions
```

### Transaction Script

**New (Python only - enhanced functionality):**
```bash
python scripts/transaction_script.py
# or with custom amount
python scripts/transaction_script.py --amount 5.0 --timeout 600
```

## Common Use Cases

### Running a Complete Test Suite

**Old (Bash):**
```bash
# Manual execution of each script
./legacy_scripts/simple_test.sh
./legacy_scripts/sync_check.sh
./legacy_scripts/test_p2p_connectivity.sh
```

**New (Python):**
```bash
# Run all tests with one command
python scripts/run_all_tests.py

# Run with coverage report
python scripts/run_all_tests.py --coverage

# Run specific test categories
python scripts/run_all_tests.py --pattern "test_sync*"
```

### Debugging Failed Tests

**Old (Bash):**
```bash
# Limited debugging options
DEBUG=1 ./legacy_scripts/simple_test.sh
```

**New (Python):**
```bash
# Rich debugging with multiple log levels
python scripts/simple_test.py --log-level DEBUG

# Save logs to file
python scripts/simple_test.py --log-level DEBUG 2>&1 | tee debug.log

# Use Python debugger
python -m pdb scripts/simple_test.py
```

### Custom Network Configuration

**Old (Bash):**
```bash
# Edit hardcoded network configuration directly
# Note: This approach has been removed and replaced with Agent Discovery
# vim legacy_scripts/network_config.sh
```

**New (Python):**
```python
# Use agent_discovery module for dynamic agent discovery
from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError

try:
    # Initialize agent discovery
    ad = AgentDiscovery()
    
    # Discover available agents dynamically
    wallet_agents = ad.get_wallet_agents()
    miner_agents = ad.get_miner_agents()
    block_controllers = ad.get_block_controllers()
    
    # Get specific agent by ID
    specific_agent = ad.get_agent_by_id("agent_id")
    
    # Find agents by type
    user_agents = ad.find_agents_by_type("user")
    
    # Refresh cache if needed
    ad.refresh_cache()
    
except AgentDiscoveryError as e:
    print(f"Agent discovery failed: {e}")
```

For more details on using the agent discovery system, see [`scripts/README_agent_discovery.md`](scripts/README_agent_discovery.md).

**Note:** The legacy hardcoded network configuration approach has been completely removed in favor of the dynamic agent discovery system. All network configuration is now handled automatically at runtime.

## Migration Steps

### Step 1: Backup Current Setup

```bash
# Create backup of any custom scripts
cp -r legacy_scripts/ legacy_scripts_backup/
```

### Step 2: Set Up Python Environment

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r scripts/requirements.txt
```

### Step 3: Test Python Scripts

```bash
# Run simple test to verify setup
python scripts/simple_test.py

# Compare output with bash version
diff <(./legacy_scripts/simple_test.sh 2>&1) <(python scripts/simple_test.py 2>&1)
```

### Step 4: Update Automation Scripts

If you have automation scripts calling the bash versions, update them:

**Old:**
```bash
#!/bin/bash
./legacy_scripts/simple_test.sh
if [ $? -eq 0 ]; then
    ./legacy_scripts/sync_check.sh
fi
```

**New:**
```bash
#!/bin/bash
source venv/bin/activate
python scripts/simple_test.py
if [ $? -eq 0 ]; then
    python scripts/sync_check.py
fi
```

### Step 5: Update Documentation

Update any internal documentation or runbooks to reference the Python scripts.

## Performance Considerations

1. **Startup Time**: Python scripts have slightly higher startup time (~0.5s) due to interpreter initialization
2. **Memory Usage**: Python uses more memory (~20-30MB per script) but provides better memory management
3. **CPU Usage**: Comparable to bash scripts for most operations
4. **Network Operations**: More efficient due to connection pooling and retry logic

## Backward Compatibility

- Legacy bash scripts remain available in `legacy_scripts/` directory
- Both implementations produce compatible output formats
- Network configuration is now handled dynamically through agent discovery
- No changes to Shadow or Monero configuration required

## Troubleshooting

### Common Issues

1. **Module Not Found Error**
   ```bash
   # Solution: Activate virtual environment
   source venv/bin/activate
   ```

2. **Permission Denied**
   ```bash
   # Solution: Make scripts executable
   chmod +x scripts/*.py
   ```

3. **Different Output Format**
   ```bash
   # Python scripts use structured logging
   # Use --log-format simple for bash-like output
   python scripts/simple_test.py --log-format simple
   ```

### Getting Help

1. Check script help:
   ```bash
   python scripts/[script_name].py --help
   ```

2. Review script documentation:
   ```bash
   cat scripts/README_[script_name].md
   ```

3. Run tests to verify functionality:
   ```bash
   python scripts/run_all_tests.py
   ```

## Best Practices

1. **Always use virtual environment** to avoid dependency conflicts
2. **Use appropriate log levels** for debugging vs production
3. **Leverage retry mechanisms** for network operations
4. **Monitor resource usage** for long-running simulations
5. **Keep Python dependencies updated** with `pip install -r scripts/requirements.txt --upgrade`

## Conclusion

The Python migration provides a more robust and maintainable testing infrastructure for Monerosim. While the transition requires some initial setup, the benefits in reliability, debugging capabilities, and cross-platform support make it worthwhile. The legacy bash scripts remain available for reference, but all new development should use the Python implementation.

For questions or issues, refer to the individual script documentation in `scripts/README_*.md` files or run the comprehensive test suite with `python scripts/run_all_tests.py`.