# Mining Shim Usage Guide

## Overview

The Mining Shim is a C shared library (`libminingshim.so`) that intercepts Monero's mining functions and replaces computationally expensive Proof-of-Work calculations with deterministic probabilistic modeling. This enables efficient, scalable Monero network simulations in the Shadow discrete-event simulator.

## Key Benefits

- **Performance**: Eliminates CPU-intensive mining calculations
- **Determinism**: Identical results across runs with same seed
- **Scalability**: Efficient simulation of large mining networks
- **Accuracy**: Mathematical model matches real-world mining behavior
- **Integration**: Seamless replacement for traditional block controller

## Architecture

### How It Works

The mining shim uses `LD_PRELOAD` to intercept these Monero daemon functions:
- `start_mining()` - Begins probabilistic mining loop
- `stop_mining()` - Stops mining operations
- `handle_new_block_notify()` - Handles peer block notifications

### Probabilistic Mining Model

Mining follows an exponential distribution where block discovery time `T` is calculated as:
```
T = -ln(1-U) / λ
```
Where:
- `λ = hashrate / difficulty` (mining success rate)
- `U` is a deterministic random number from seeded PRNG

## Quick Start

### 1. Build and Install

```bash
# Build the mining shim
cd mining_shim
make clean && make

# Install system-wide
sudo make install
```

### 2. Basic Configuration

```yaml
general:
  stop_time: "5m"
  simulation_seed: 42  # Required for deterministic mining

network:
  type: "1_gbit_switch"

agents:
  user_agents:
    # Single miner
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "10000000"  # 10 MH/s
```

### 3. Run Simulation

```bash
# Generate Shadow configuration
./target/release/monerosim --config config.yaml --output shadow_output

# Run simulation
shadow shadow_output/shadow_agents.yaml
```

## Configuration

### Required Environment Variables

For each miner agent, set these environment variables:

```bash
MINER_HASHRATE=10000000    # Agent hashrate in H/s
AGENT_ID=1                 # Unique agent identifier (1, 2, 3, ...)
SIMULATION_SEED=42         # Global seed for deterministic results
```

### Optional Environment Variables

```bash
MININGSHIM_LOG_LEVEL=INFO     # DEBUG|INFO|WARN|ERROR
MININGSHIM_LOG_FILE=/tmp/miningshim_agent1.log  # Default: /tmp/miningshim_agent{ID}.log
```

### Monerosim Configuration Fields

```yaml
general:
  simulation_seed: 42        # Required for deterministic mining
  mining_shim_path: "./mining_shim/libminingshim.so"  # Optional, auto-detected

agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "25000000"  # 25 MH/s - determines mining probability
```

## Usage Examples

### Single Miner Setup

```yaml
general:
  stop_time: "10m"
  simulation_seed: 12345

network:
  type: "1_gbit_switch"

agents:
  user_agents:
    # Miner
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "10000000"

    # Observer node
    - daemon: "monerod"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "30"
```

### Multi-Miner Network

```yaml
general:
  stop_time: "15m"
  simulation_seed: 99999

agents:
  user_agents:
    # Miner 1 - 40% of network hashrate
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "40000000"

    # Miner 2 - 35% of network hashrate
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "35000000"

    # Miner 3 - 25% of network hashrate
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "25000000"

    # Regular user
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "60"
```

### Large-Scale Mining Pool

```yaml
general:
  stop_time: "30m"
  simulation_seed: 77777

agents:
  user_agents:
    # 10 miners with equal hashrate
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "10000000"
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "10000000"
    # ... repeat for 8 more miners

    # Multiple observers
    - daemon: "monerod"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "120"
    # ... more observers
```

## Monitoring and Debugging

### Log Files

Each miner creates a log file at `/tmp/miningshim_agent{ID}.log`:

```
[1698765432.123456] [INFO] [SHIM:1] Mining shim initialized successfully
[1698765432.234567] [INFO] [SHIM:1] start_mining intercepted: wallet=4A..., threads=1
[1698765432.345678] [INFO] [SHIM:1] Mining loop started
[1698765450.456789] [INFO] [SHIM:1] Block found after 18111111111 ns
```

### Metrics Export

After simulation, metrics are exported to `/tmp/miningshim_metrics_agent{ID}.json`:

```json
{
  "agent_id": 1,
  "blocks_found": 42,
  "mining_iterations": 150,
  "peer_blocks_received": 38,
  "total_mining_time_ns": 3600000000000,
  "average_block_time_ns": 85714285714,
  "hashrate": 25000000
}
```

### Real-time Monitoring

Monitor mining activity during simulation:

```bash
# Watch log file
tail -f /tmp/miningshim_agent1.log

# Check metrics periodically
watch -n 10 'cat /tmp/miningshim_metrics_agent1.json | jq .blocks_found'
```

## Performance Considerations

### Hashrate Configuration

- **Realistic Values**: Use actual mining hardware hashrates (e.g., 10-50 MH/s per GPU)
- **Network Proportion**: Distribute hashrate to reflect real mining power distribution
- **Total Hashrate**: Sum of all miner hashrates determines network difficulty

### Simulation Time

- **Block Time**: Average ~2 minutes with default Monero difficulty
- **Scale Factor**: Mining shim enables 10-100x faster simulation vs real-time
- **Memory Usage**: Minimal additional memory overhead

### Shadow Integration

- **Time Advancement**: Uses `pthread_cond_timedwait` for efficient simulation
- **No CPU Waste**: Mining calculations don't consume real CPU time
- **Deterministic**: Same seed always produces identical results

## Troubleshooting

### Common Issues

#### Mining Shim Not Loaded

**Symptoms**: Mining doesn't start, no shim logs
**Solution**:
```bash
# Verify library exists
ls -la ./mining_shim/libminingshim.so

# Check LD_PRELOAD in Shadow config
grep "LD_PRELOAD" shadow_output/shadow_agents.yaml
```

#### Missing Environment Variables

**Symptoms**: Shim fails to initialize
**Solution**:
```bash
# Check required variables are set
echo "MINER_HASHRATE: $MINER_HASHRATE"
echo "AGENT_ID: $AGENT_ID"
echo "SIMULATION_SEED: $SIMULATION_SEED"
```

#### Non-Deterministic Results

**Symptoms**: Different results across runs
**Solution**:
- Ensure `SIMULATION_SEED` is set consistently
- Verify all agents have unique `AGENT_ID` values
- Check that `AGENT_ID` starts from 1 and increments

#### No Blocks Found

**Symptoms**: Mining runs but no blocks are created
**Solution**:
- Verify hashrate is reasonable (not too low)
- Check network difficulty is appropriate
- Ensure miner has wallet configured
- Review shim logs for errors

### Debug Mode

Enable detailed logging:

```bash
# Set environment variable
export MININGSHIM_LOG_LEVEL=DEBUG

# Or in Shadow config
environment:
  MININGSHIM_LOG_LEVEL: "DEBUG"
```

### Verification Steps

1. **Check Library Loading**:
   ```bash
   # Verify symbol interception
   nm -D ./mining_shim/libminingshim.so | grep start_mining
   ```

2. **Validate Configuration**:
   ```bash
   # Check Shadow YAML contains shim
   grep -A 5 "LD_PRELOAD" shadow_output/shadow_agents.yaml
   ```

3. **Monitor Initialization**:
   ```bash
   # Watch for initialization messages
   tail -f /tmp/miningshim_agent1.log | grep "initialized"
   ```

## Best Practices

### Configuration

1. **Use Realistic Hashrates**: Base on actual mining hardware capabilities
2. **Distribute Mining Power**: Model real-world mining distribution
3. **Set Appropriate Seeds**: Use different seeds for different scenarios
4. **Unique Agent IDs**: Ensure each agent has a unique identifier

### Monitoring

1. **Log Analysis**: Regularly review shim logs for anomalies
2. **Metrics Tracking**: Monitor block production rates and mining efficiency
3. **Performance Profiling**: Track simulation performance vs real-time

### Scaling

1. **Large Networks**: Use mining shim for networks >10 miners
2. **Long Simulations**: Mining shim essential for >1 hour simulations
3. **Research Studies**: Deterministic results enable reproducible research

## Migration from Block Controller

### Key Differences

| Aspect | Block Controller | Mining Shim |
|--------|------------------|-------------|
| Architecture | Python agent coordination | C library interception |
| Performance | Python overhead | Native C performance |
| Determinism | Limited | Full determinism |
| Scalability | Limited to small networks | Scales to 100+ miners |
| Maintenance | Complex Python logic | Simple mathematical model |

### Migration Steps

1. **Remove Block Controller**:
   ```yaml
   # Remove this section
   agents:
     block_controller:
       script: "agents.block_controller"
   ```

2. **Add Mining Shim**:
   ```yaml
   # Add mining_shim_path to general
   general:
     mining_shim_path: "./mining_shim/libminingshim.so"
     simulation_seed: 42  # Required for determinism
   ```

3. **Update Miner Configuration**:
   ```yaml
   agents:
     user_agents:
       - daemon: "monerod"
         wallet: "monero-wallet-rpc"
         attributes:
           is_miner: true
           hashrate: "25000000"  # Add hashrate attribute
   ```

4. **Test Migration**:
   - Run short simulation (1-2 minutes)
   - Verify blocks are being mined
   - Check deterministic behavior with same seed

## Advanced Usage

### Custom Hashrate Distributions

Model real-world mining pool distributions:

```yaml
agents:
  user_agents:
    # Large miner (30% of network)
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "30000000"

    # Medium miners (20% each)
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "20000000"
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "20000000"

    # Small miners (10% each)
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "10000000"
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "10000000"
```

### Research Applications

The mining shim enables various research scenarios:

- **Mining Pool Economics**: Study reward distribution mechanisms
- **Network Attacks**: Simulate 51% attacks with controlled hashrate
- **Consensus Research**: Test protocol modifications under various mining distributions
- **Scalability Studies**: Evaluate network performance with large miner populations

## Technical Details

### Mathematical Model

The mining shim implements the memoryless property of Poisson processes. Block discovery follows exponential distribution:

```
f(t) = λe^(-λt)
F(t) = 1 - e^(-λt)
```

Where `λ` is the mining rate (hashrate/difficulty).

### Deterministic PRNG

Uses `drand48_r` with seed combination:
```
agent_seed = global_seed + agent_id
```

This ensures:
- Same global seed + agent ID = identical behavior
- Different agent IDs = different but deterministic sequences
- Reproducible across simulation runs

### Shadow Time Integration

The shim leverages Shadow's discrete-event simulation by using `pthread_cond_timedwait` with absolute timeouts. This allows Shadow to advance simulation time efficiently without consuming real CPU time for mining calculations.

## Support

For issues or questions:

1. **Check Logs**: Review mining shim log files for error messages
2. **Verify Configuration**: Ensure all required environment variables are set
3. **Test Determinism**: Run same configuration multiple times to verify consistency
4. **Review Documentation**: Check this guide and related documentation

## Version History

- **v1.0** (2025-11-03): Initial release with core mining interception
- Features: Probabilistic mining, deterministic PRNG, Shadow integration, comprehensive logging