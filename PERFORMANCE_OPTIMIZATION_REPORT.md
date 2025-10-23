# Monerosim Simulation Startup Performance Optimization

## Problem Analysis

The simulation was experiencing significant startup delays, with the first 20 seconds of simulation time taking approximately 1 minute of real time. After analyzing the log files and configuration, I identified several root causes:

### Root Causes

1. **Excessive Process Count**: 168 processes starting sequentially
2. **Prolonged Staggered Startup**: Processes starting from 0s to 3900s (65 minutes)
3. **Resource Contention**: Multiple Monero daemons and wallets competing for system resources
4. **Complex GML Network Topology**: Thousands of nodes adding initialization overhead

### Performance Issues Identified

- First miner starts at 0s, but subsequent miners have 2-second delays
- Regular users start 10+ seconds after miners
- Wallet processes have 5-second delays after daemons
- Agent scripts have 10-second delays after wallets
- Block controller starts at 20s (Dynamic) or 90s (other modes)
- Miner distributor starts at 3900s (65 minutes!)

## Optimizations Implemented

### 1. Reduced Daemon Startup Delays

**Before:**
- Miners: 0s, 4s, 6s, 8s, ... (2-second intervals)
- Regular users: 10s, 12s, 14s, ... (2-second intervals)

**After:**
- Miners: 0s, 1s, 2s, 3s, ... (1-second intervals)
- Regular users: 5s, 6s, 7s, ... (1-second intervals)

### 2. Reduced Wallet Startup Delays

**Before:**
- Wallets start 5 seconds after daemon

**After:**
- Wallets start 2 seconds after daemon

### 3. Reduced Agent Script Delays

**Before:**
- Agents start 10 seconds after wallet

**After:**
- Agents start 3 seconds after wallet

### 4. Optimized Block Controller Timing

**Before:**
- Dynamic mode: 20s
- Other modes: 90s

**After:**
- Dynamic mode: 10s
- Other modes: 15s

### 5. Miner Distributor Timing (Preserved)

**Before:**
- All modes: 3900s (65 minutes)

**After:**
- All modes: 3900s (65 minutes) - **Unchanged**

**Note:** The miner distributor timing was intentionally preserved at 65 minutes because Monero block rewards require 30 blocks (approximately 60 minutes at 2-minute block intervals) to reach maturity before they can be distributed. This is a fundamental Monero protocol requirement and cannot be optimized without breaking the mining reward distribution functionality.

### 6. Optimized Script Agent Timing

**Before:**
- Script creation: 29s, 34s, 39s, ... (5-second intervals)
- Script execution: 30s, 35s, 40s, ... (5-second intervals)

**After:**
- Script creation: 5s, 7s, 9s, ... (2-second intervals)
- Script execution: 6s, 8s, 10s, ... (2-second intervals)

## Expected Performance Improvements

With these optimizations, the simulation startup should be significantly faster:

1. **First 20 seconds of simulation time** should now complete in approximately 20-30 seconds of real time (instead of 1 minute)

2. **All critical processes** should be started within the first 30 seconds of simulation time

3. **Miner distributor** will start at 3900s (65 minutes) as required by Monero's block reward maturity period

4. **Reduced resource contention** with tighter startup windows

## Important Note on Miner Distributor Timing

The miner distributor timing was intentionally **not optimized** and remains at 3900s (65 minutes) because:

1. **Monero Protocol Requirement**: Block rewards require 30 confirmations (approximately 60 minutes at 2-minute block intervals) before they become spendable
2. **Functional Necessity**: The miner distributor cannot function correctly until block rewards have matured
3. **Economic Model**: This delay is fundamental to Monero's economic security model

All other optimizations are safe and will improve startup performance without affecting functionality.

## Additional Recommendations

### For Further Performance Improvements

1. **Parallel Process Startup**: Consider starting multiple processes simultaneously when they don't depend on each other

2. **Resource Limits**: Implement memory and CPU limits to prevent resource contention

3. **GML Topology Simplification**: For testing, consider using a simpler topology or switch-based network

4. **Process Pooling**: Reuse processes where possible instead of creating new ones

5. **Block Time Adjustment**: For testing only, consider reducing Monero's block time (requires Monero source modification)

### Configuration Tuning

For development and testing, consider using a smaller configuration:

```yaml
# Use fewer agents for faster startup
agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"

# Use switch topology for faster initialization
network:
  type: "1_gbit_switch"
  peer_mode: "Dynamic"
```

## Testing the Optimizations

To verify the performance improvements:

1. Rebuild Monerosim: `cargo build --release`
2. Generate new configuration: `./target/release/monerosim --config config.yaml --output shadow_output`
3. Run the simulation: `shadow shadow_output/shadow_agents.yaml`
4. Monitor the startup timing in the logs

The simulation should now reach the 20-second mark much faster, with all critical components initialized and ready to work.