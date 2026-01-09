# Shadow Simulation Status Checker

## Overview

The `check_shadow_status.sh` script provides a robust solution for monitoring Shadow simulation completion. It addresses the unreliability of the previous method by using multiple indicators to determine if a simulation is still running.

## Features

### Multiple Detection Methods

1. **PID-based Detection**: Tracks the Shadow process ID using a PID file
2. **Process Name Detection**: Searches for Shadow processes by name pattern
3. **Log Activity Detection**: Monitors log file modification times
4. **Completion Status Detection**: Looks for completion markers in log files

### Robust Error Handling

- Handles stale PID files automatically
- Detects when simulation stops without proper completion
- Provides detailed status information
- Color-coded output for easy reading

## Usage

### Wait for Completion (Default)

```bash
./check_shadow_status.sh
# or explicitly
./check_shadow_status.sh wait
```

This mode will:
- Check simulation status every 30 seconds
- Display periodic status updates
- Exit when simulation completes or stops
- Clean up PID files automatically

### Check Current Status

```bash
./check_shadow_status.sh check
```

This mode provides an immediate status report without waiting.

### Help

```bash
./check_shadow_status.sh help
```

## Integration with Memory Bank

This script should be used instead of the previous unreliable command:

### Old Method (Unreliable)
```bash
while ps aux | grep -q "shadow.*shadow_agents.yaml"; do sleep 30; done; echo "Simulation completed"
```

### New Method (Recommended)
```bash
./check_shadow_status.sh wait
```

## How It Works

### Detection Logic

The script uses a combination of checks to determine simulation status:

1. **Primary Indicators**:
   - PID file exists and process is running
   - Process name pattern matches running processes
   - Log file has been modified recently (within 2 minutes)

2. **Completion Detection**:
   - Looks for "Simulation terminated" in log
   - Recognizes "managed processes in unexpected final state" (normal Shadow behavior)

3. **Failure Detection**:
   - If no indicators show activity for a full check cycle
   - Simulation is considered stopped even without completion markers

### Status Updates

The script provides periodic updates showing:
- Which detection methods are active
- Check count to monitor progress
- Color-coded status indicators

## Configuration

The script can be customized by modifying these variables at the top:

```bash
SHADOW_CONFIG="shadow_output/shadow_agents.yaml"  # Shadow config file
LOG_FILE="shadow.log"                              # Shadow log file
PID_FILE="shadow.pid"                              # PID file location
CHECK_INTERVAL=30                                  # Seconds between checks
```

## Examples

### Basic Usage

```bash
# Start simulation in background
rm -rf shadow.data shadow.log && nohup shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &

# Wait for completion
./check_shadow_status.sh wait
```

### Status Check

```bash
./check_shadow_status.sh check
```

Output example:
```
Shadow Simulation Status Check:
==============================
PID Check: Running (12345)
Process Check: Running
Log Activity: Active
Completion Status: Not Completed
```

## Troubleshooting

### Simulation Appears Stopped

If the script reports the simulation has stopped but you believe it should still be running:

1. Check the log file directly:
   ```bash
   tail shadow.log
   ```

2. Verify Shadow processes:
   ```bash
   ps aux | grep shadow
   ```

3. Check for error messages:
   ```bash
   grep -i error shadow.log
   ```

### False Positives

The script may incorrectly detect completion if:
- Log file rotation occurs
- Shadow process forks into child processes
- System time changes significantly

In these cases, use the `check` command to verify all indicators.

## Integration with Other Tools

This script works well with:

1. **Log Processing**: Run after simulation completes
   ```bash
   ./check_shadow_status.sh wait && python3 scripts/log_processor.py
   ```

2. **Analysis Scripts**: Chain multiple analysis steps
   ```bash
   ./check_shadow_status.sh wait && python3 scripts/analyze_success_criteria.py .
   ```

3. **Automated Workflows**: Use in CI/CD pipelines
   ```bash
   ./check_shadow_status.sh wait && ./post_run_analysis.sh
   ```

## Advantages Over Previous Method

1. **Multiple Indicators**: More reliable than single process check
2. **Completion Detection**: Recognizes when simulation finishes properly
3. **Error Handling**: Graceful handling of edge cases
4. **Status Information**: Detailed feedback during monitoring
5. **Cleanup**: Automatic removal of temporary files
6. **Flexibility**: Can be used for both waiting and status checking

## Memory Bank Integration

This script should be added to the memory bank as the standard method for monitoring Shadow simulations. It replaces the previous unreliable method and provides a more robust solution for determining simulation completion.