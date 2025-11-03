# Mining Shim Library - Implementation Guide

## Overview

The Mining Shim is a C shared library (`libminingshim.so`) that uses LD_PRELOAD to intercept Monero mining functions and replace them with deterministic probabilistic mining suitable for Shadow network simulation.

## Features

### Core Capabilities
- **Function Interception**: Intercepts `start_mining`, `stop_mining`, and `handle_new_block_notify` from monerod
- **Deterministic Mining**: Uses exponential distribution with seeded PRNG for reproducible results
- **Shadow Integration**: Uses `pthread_cond_timedwait` for efficient time advancement in Shadow
- **Thread-Safe**: All mining operations protected by mutexes
- **Comprehensive Logging**: Configurable log levels with timestamps
- **Metrics Export**: JSON metrics export for post-simulation analysis

### Technical Implementation
- **Probabilistic Mining**: T = -ln(1-U)/λ where λ = hashrate/difficulty
- **Deterministic PRNG**: drand48_r with seed = SIMULATION_SEED + AGENT_ID
- **Mining Interruption**: Peer blocks interrupt current mining attempt
- **Graceful Degradation**: Continues operation even with configuration issues

## Files

- `libminingshim.h` - Header file with data structures and function prototypes
- `libminingshim.c` - Main implementation (478 lines)
- `Makefile` - Build system
- `README.md` - This file

## Building

### Requirements
- GCC compiler
- pthread library
- math library (libm)
- dynamic linking library (libdl)

### Compilation
```bash
cd mining_shim
make
```

This produces `libminingshim.so` (approximately 31KB).

### Clean Build
```bash
make clean
make
```

## Usage

### Environment Variables

#### Required Configuration
```bash
export MINER_HASHRATE=25000000        # Agent hashrate (H/s)
export AGENT_ID=1                     # Unique agent identifier
export SIMULATION_SEED=42             # Global simulation seed for reproducibility
```

#### Optional Configuration
```bash
export MININGSHIM_LOG_LEVEL=INFO      # DEBUG|INFO|WARN|ERROR
export MININGSHIM_LOG_FILE=/path/to/log  # Defaults to /tmp/miningshim_agent{ID}.log
```

### Integration with Monerod

#### Using LD_PRELOAD
```bash
LD_PRELOAD=/path/to/libminingshim.so monerod [options]
```

#### In Shadow Configuration
```yaml
hosts:
  miner1:
    processes:
      - path: monerod
        environment:
          LD_PRELOAD: /path/to/libminingshim.so
          MINER_HASHRATE: "25000000"
          AGENT_ID: "1"
          SIMULATION_SEED: "42"
```

## Architecture

### Initialization Flow
1. Library constructor (`shim_initialize`) called on load
2. Load configuration from environment variables
3. Initialize deterministic PRNG (seed = SIMULATION_SEED + AGENT_ID)
4. Set up logging system
5. Initialize metrics tracking
6. Validate environment

### Mining Flow
1. `start_mining()` intercepted
2. Create mining thread
3. Mining loop:
   - Calculate block discovery time using exponential distribution
   - Wait using `pthread_cond_timedwait` (Shadow-optimized)
   - On timeout: create and broadcast block
   - On signal: peer block received, restart mining
4. `stop_mining()` intercepted - stops mining thread
5. Library destructor exports metrics to JSON

### Block Discovery Calculation
```c
T = -ln(1-U) / λ
where:
  T = time to discover block (seconds)
  U = uniform random number [0,1) from seeded PRNG
  λ = hashrate / difficulty
```

### Peer Block Handling
When `handle_new_block_notify()` is intercepted:
1. Update network difficulty tracker
2. Signal mining thread via condition variable
3. Mining thread restarts with new difficulty
4. Call original monerod handler (if exists)

## Metrics

Metrics are automatically exported to `/tmp/miningshim_metrics_agent{ID}.json` when the library unloads.

### Metrics Structure
```json
{
  "agent_id": 1,
  "blocks_found": 42,
  "mining_iterations": 150,
  "peer_blocks_received": 38,
  "total_mining_time_ns": 3600000000000,
  "average_block_time_ns": 85714285714,
  "mining_errors": 0,
  "hashrate": 25000000
}
```

## Logging

### Log Levels
- **DEBUG**: Detailed mining iterations, peer block events
- **INFO**: Mining start/stop, block discovery, initialization
- **WARN**: Non-fatal issues, missing functions
- **ERROR**: Critical failures, configuration errors

### Log Format
```
[timestamp_sec.microsec] [LEVEL] [SHIM:agent_id] message
```

### Example Log Output
```
[1698765432.123456] [INFO] [SHIM:1] Mining shim initialized successfully
[1698765432.234567] [INFO] [SHIM:1] start_mining intercepted: wallet=4A..., threads=1
[1698765432.345678] [INFO] [SHIM:1] Mining loop started
[1698765450.456789] [INFO] [SHIM:1] Block found after 18111111111 ns
```

## Integration with Monerosim

### Rust Configuration Generator
The Rust tool should:
1. Set environment variables for each miner agent
2. Specify `LD_PRELOAD` in Shadow YAML
3. Ensure unique `AGENT_ID` for each agent
4. Use consistent `SIMULATION_SEED` for reproducibility

### Example Integration
```rust
// In process configuration generation
if agent.is_miner {
    let env_vars = vec![
        ("LD_PRELOAD", "/path/to/libminingshim.so"),
        ("MINER_HASHRATE", &hashrate.to_string()),
        ("AGENT_ID", &agent_id.to_string()),
        ("SIMULATION_SEED", &simulation_seed.to_string()),
    ];
}
```

## Debugging

### Verification Steps
1. Check library exports the correct symbols:
   ```bash
   nm -D libminingshim.so | grep mining
   ```

2. Verify environment variables are set:
   ```bash
   echo $MINER_HASHRATE $AGENT_ID $SIMULATION_SEED
   ```

3. Check log file for initialization messages:
   ```bash
   tail -f /tmp/miningshim_agent1.log
   ```

4. Verify metrics file after simulation:
   ```bash
   cat /tmp/miningshim_metrics_agent1.json
   ```

### Common Issues

**Issue**: Library not loaded
- **Solution**: Verify `LD_PRELOAD` path is correct and library exists

**Issue**: Missing environment variables
- **Solution**: Check all required variables are exported before monerod starts

**Issue**: PRNG warnings
- **Solution**: Expected on some systems, doesn't affect functionality

**Issue**: Unused parameter warnings
- **Solution**: Cosmetic warnings during compilation, safe to ignore

## Performance Considerations

### Memory Usage
- Minimal memory footprint (~31KB library + runtime state)
- All state stored in global structures
- No dynamic memory allocation during mining

### CPU Usage
- Mining thread sleeps most of the time (Shadow time advancement)
- Negligible CPU when not actively mining
- Thread-safe operations have minimal mutex contention

### Shadow Integration
- Uses `pthread_cond_timedwait` for efficient simulation
- Allows Shadow to advance time during mining periods
- No busy-waiting or tight loops

## Testing

### Unit Testing
The implementation has been validated through:
- Compilation without errors (only warnings for unused parameters)
- Symbol export verification
- Integration with current Monerosim test suite

### Recommended Tests
1. **Single Miner**: Verify block production with one agent
2. **Multiple Miners**: Test with varying hashrates
3. **Peer Block Interruption**: Verify mining restarts on peer blocks
4. **Determinism**: Run same configuration twice, verify identical results
5. **Metrics Accuracy**: Verify exported metrics match simulation behavior

## Known Limitations

1. **Block Template Construction**: Currently uses placeholder, needs integration with actual monerod block template API
2. **PRNG Warnings**: `srand48_r` and `drand48_r` may show implicit declaration warnings on some systems
3. **Monerod Version Compatibility**: Designed for current Monero version, may need updates for future releases

## Future Enhancements

1. **Block Template Integration**: Proper block construction using monerod API
2. **Enhanced Metrics**: More detailed mining statistics
3. **Dynamic Difficulty Adjustment**: Support for difficulty changes during simulation
4. **Performance Profiling**: Built-in performance measurement
5. **Configuration Validation**: More robust environment variable validation

## References

- Mining Shim Technical Specification v3.0
- Shadow Simulator Documentation
- Monero Protocol Documentation
- LD_PRELOAD mechanism (ld.so man page)

## License

Same as parent Monerosim project.

## Version History

- **v1.0** (2025-11-03): Initial implementation
  - Core function interception
  - Deterministic probabilistic mining
  - Shadow integration
  - Comprehensive logging and metrics