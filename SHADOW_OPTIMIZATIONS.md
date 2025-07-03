# Shadow + Monero Optimization Guide

This document describes the effective optimizations implemented to make Monero work with the Shadow network simulator, based on analysis of Shadow's TCP emulation limitations.

## Problem Analysis

**Root Cause**: Shadow's user-space TCP stack is overwhelmed by Monero's aggressive P2P networking behavior:
- Monero opens many concurrent connections rapidly (8 outbound, 64 inbound by default)
- Complex multi-threaded network operations stress Shadow's discrete-event scheduling
- High bandwidth usage and frequent sync requests overload Shadow's emulated TCP stack
- Simultaneous startup creates "thundering herd" connection storms

## Effective Solutions Implemented

### 1. Monero Application-Level Optimizations (`src/shadow.rs`)

**Connection Limits**:
- `--out-peers=2`: Reduced from default 8 to 2 outbound connections
- `--in-peers=4`: Reduced from default 64 to 4 inbound connections  
- `--max-connections-per-ip=1`: Prevent connection storms

**Bandwidth Throttling**:
- `--limit-rate-up=1024`: 1MB/s upload limit (reduces data volume)
- `--limit-rate-down=1024`: 1MB/s download limit

**Conservative Sync Behavior**:
- `--block-sync-size=1`: Sync 1 block at a time (default: 20)
- `--prep-blocks-threads=1`: Single-threaded block preparation
- `--max-concurrency=1`: Single-threaded operation

**Reduced Peer Connections**:
- Max 2 seed node connections instead of full mesh
- Uses `--add-peer` instead of `--add-exclusive-node` for gentler connections

### 2. Shadow Network Configuration Optimizations

**Staggered Startup Timing**:
- Nodes start at 10-second intervals (`0s`, `10s`, `20s`, etc.)
- Prevents simultaneous connection attempts ("thundering herd")
- Test servers start at `5s`, client at `15s`, monitor at `30s`

**Network Topology**:
- Uses Shadow's built-in `1_gbit_switch` topology (optimized for Shadow)
- Separates Monero nodes (network_node_id: 0) from test infrastructure (network_node_id: 1)
- Enhanced syscall modeling with `model_unblocked_syscall_latency: true`

## Why These Optimizations Work

### Monero Application Tuning (High Impact)
These modifications directly address Shadow's TCP stack limitations by:
- **Reducing concurrent TCP handshakes**: Fewer connections = less stress on Shadow's emulated TCP
- **Lowering data volume**: Bandwidth limits reduce buffer pressure in Shadow's network stack
- **Simplifying threading**: Single-threaded operation reduces complexity for Shadow to manage
- **Conservative sync**: Fewer, smaller requests reduce the frequency of network events

### Shadow Configuration Tuning (High Impact)  
These modifications optimize the simulation environment by:
- **Preventing connection storms**: Staggered startups serialize connection attempts
- **Optimized network model**: Built-in topology is tuned for Shadow's discrete-event scheduler
- **Better resource separation**: Network isolation between Monero and test infrastructure

## What We Removed (Based on Analysis)

### Host System TCP Tuning (Ineffective)
The original plan included host-level TCP parameter tuning via `/proc/sys/net/ipv4/*`. 
**Why this doesn't work**: Shadow intercepts syscalls and uses its own internal TCP implementation, completely bypassing the host's kernel network stack. Host TCP parameters have zero effect on Shadow's simulated network.

## Expected Results

With these optimizations, Monero nodes should:
1. ✅ **Bind successfully** to their assigned IP addresses for both P2P and RPC
2. ✅ **Establish connections** between nodes without "Failed to start connection" errors  
3. ✅ **Exchange data** and sync blockchain state across the P2P network
4. ✅ **Respond to RPC** queries from the monitor for data collection

## Running the Optimized Simulation

```bash
# Generate optimized configuration
cargo run -- --config config.yaml --output shadow_output_optimized

# Run the simulation
shadow shadow_output_optimized/shadow.yaml

# Analyze results
ls shadow.data/hosts/*/  # Check all host logs
grep -r "core RPC server initialized OK" shadow.data/hosts/a*  # RPC status
grep -r "Failed to start connection" shadow.data/hosts/a*     # Connection issues
```

## Technical Implementation Details

The optimizations are implemented in `src/shadow.rs`:
- `generate_monerod_args()`: Applies all Monero-level optimizations
- `generate_shadow_config()`: Implements staggered timing and network separation
- Uses `1_gbit_switch` topology instead of custom GML for maximum Shadow compatibility

These changes transform Monero from an aggressive, highly-concurrent application into a Shadow-friendly, conservative networking application while maintaining core P2P functionality.

## Monitoring and Debugging

**Key Log Files**:
```bash
# Monero node logs
shadow.data/hosts/a*/monerod*.stdout

# Monitor output  
shadow.data/hosts/monitor/monitor*.stdout

# Test connectivity results
shadow.data/hosts/testclient/test_client*.stdout
```

**Success Indicators**:
- Monero logs show successful P2P bindings without "Failed to start connection"
- RPC server responds to monitor queries with node data
- Test servers show successful POST/GET requests
- No immediate "Destructing connection" messages after accept

## Technical References

- [Shadow TCP Emulation Limitations](https://shadow.github.io/docs/guide/)
- [EthShadow Network Optimizations](https://github.com/ethereum/ethshadow)
- [Linux TCP Tuning for Network Simulation](https://fasterdata.es.net/host-tuning/linux/)
- [Monero P2P Network Protocol](https://github.com/monero-project/monero)

## Future Improvements

1. **Adaptive Connection Scaling**: Dynamically adjust peer counts based on simulation size
2. **TCP Flow Control**: Implement application-level flow control for large data transfers  
3. **Connection Pooling**: Reuse TCP connections instead of opening new ones
4. **Shadow-Specific Patches**: Contribute upstream improvements to Shadow's TCP stack
5. **Performance Profiling**: Detailed analysis of Shadow TCP bottlenecks with Monero workloads 