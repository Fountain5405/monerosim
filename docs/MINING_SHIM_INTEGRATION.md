# Mining Shim Integration Guide

## Overview

This guide provides technical details for developers integrating the Mining Shim into Monerosim. The mining shim is a C library that intercepts Monero daemon mining functions to provide deterministic, probabilistic mining simulation suitable for Shadow network simulations.

## Architecture Integration

### How the Mining Shim Works

The mining shim (`libminingshim.so`) uses Monero's built-in hook system to register mining callbacks. This replaces the previous LD_PRELOAD approach with a clean, official API.

**Hook Registration Process:**
1. Mining shim library loads and registers hook functions with monerod
2. Monerod calls registered hooks at key mining events
3. Shim implements probabilistic mining using exponential distribution
4. Deterministic results achieved through seeded PRNG

**Key Hook Points:**
```c
// Hook function types
typedef bool (*mining_start_hook_t)(
    void* miner_instance,
    const void* wallet_address,
    uint64_t threads_count,
    bool background_mining,
    bool ignore_battery
);

typedef bool (*mining_stop_hook_t)(void* miner_instance);

typedef bool (*find_nonce_hook_t)(
    void* miner_instance,
    void* block_ptr,
    uint64_t difficulty,
    uint64_t height,
    const void* seed_hash,
    uint32_t* nonce_out
);

typedef bool (*block_found_hook_t)(
    void* miner_instance,
    void* block_ptr,
    uint64_t height
);

typedef void (*difficulty_update_hook_t)(
    void* miner_instance,
    uint64_t new_difficulty,
    uint64_t height
);
```

### Integration Points in Monerosim

The mining shim integrates with Monerosim at these key points:

1. **Configuration Generation**: Rust code sets environment variables for each miner
2. **Shadow YAML Generation**: Adds mining shim library and environment variables to miner processes
3. **Runtime Execution**: Library loads, registers hooks with monerod, and handles mining events during simulation
4. **Hook Registration**: Mining shim registers callback functions with monerod's hook system

## Configuration Integration

### Required Configuration Fields

```rust
// In src/config_v2.rs - GeneralConfig
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GeneralConfig {
    // ... existing fields ...
    #[serde(skip_serializing_if = "Option::is_none")]
    pub simulation_seed: Option<u64>,        // Required for mining shim determinism
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mining_shim_path: Option<String>,    // Path to libminingshim.so
}
```

### Agent Configuration

Miners are identified by the `is_miner` attribute:

```rust
// In src/config_v2.rs - UserAgentConfig
pub fn is_miner_value(&self) -> bool {
    // Check top-level field or attributes
    if let Some(is_miner) = self.is_miner {
        return is_miner;
    }

    // Fall back to attributes
    if let Some(attrs) = &self.attributes {
        if let Some(is_miner_value) = attrs.get("is_miner") {
            return matches!(is_miner_value.to_lowercase().as_str(),
                          "true" | "1" | "yes" | "on");
        }
    }
    false
}
```

## Shadow Configuration Generation

### Environment Variable Setup

For each miner agent, the Rust orchestrator sets required environment variables:

```rust
// In src/agent/user_agents.rs or src/orchestrator.rs
fn configure_mining_shim_environment(
    agent: &UserAgentConfig,
    agent_id: usize,
    simulation_seed: u64,
    mining_shim_path: &str,
) -> HashMap<String, String> {
    let mut env = HashMap::new();

    // Inject mining shim library
    env.insert("LD_PRELOAD".to_string(), mining_shim_path.to_string());

    // Required mining shim configuration
    env.insert("MINER_HASHRATE".to_string(),
               agent.attributes.get("hashrate").unwrap_or("10000000").to_string());
    env.insert("AGENT_ID".to_string(), agent_id.to_string());
    env.insert("SIMULATION_SEED".to_string(), simulation_seed.to_string());

    // Optional configuration
    env.insert("MININGSHIM_LOG_LEVEL".to_string(), "INFO".to_string());
    env.insert("MININGSHIM_LOG_FILE".to_string(),
               format!("/tmp/miningshim_agent{}.log", agent_id));

    env
}
```

### Shadow Process Configuration

The generated Shadow YAML includes mining shim environment variables:

```yaml
hosts:
  miner001:
    network_node_id: 0
    ip_addr: "192.168.1.10"
    processes:
      - path: "/usr/local/bin/monerod"
        args: "--data-dir /tmp/miner001 --start-mining <wallet_address>"
        environment:
          # Mining shim library (hook-based approach)
          LD_PRELOAD: "./mining_shim/libminingshim.so"

          # Required shim configuration
          MINER_HASHRATE: "25000000"
          AGENT_ID: "1"
          SIMULATION_SEED: "42"

          # Enable mining hooks in monerod
          MONERO_MINING_HOOKS_ENABLED: "1"

          # Optional shim configuration
          MININGSHIM_LOG_LEVEL: "INFO"
          MININGSHIM_LOG_FILE: "/tmp/miner001_shim.log"
```

## Build System Integration

### Mining Shim Build Process

The mining shim should be built as part of the Monerosim setup:

```makefile
# In mining_shim/Makefile
CC = gcc
CFLAGS = -Wall -Wextra -fPIC -O2 -DNDEBUG -DMONERO_MINING_HOOKS_ENABLED
LDFLAGS = -shared
LIBS = -lpthread -lm -ldl

SOURCES = libminingshim.c
TARGET = libminingshim.so

all: $(TARGET)

$(TARGET): $(SOURCES)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^ $(LIBS)

install: $(TARGET)
	install -m 755 $(TARGET) /usr/local/lib/
	ldconfig

clean:
	rm -f $(TARGET)
```

**Key Build Flags:**
- `-DMONERO_MINING_HOOKS_ENABLED`: Enables hook-based compilation
- `-fPIC`: Required for shared library
- `-shared`: Creates shared object file

### Setup Script Integration

Update `setup.sh` to build and install the mining shim:

```bash
#!/bin/bash
# In setup.sh

echo "Building Mining Shim..."
cd mining_shim
make clean && make
sudo make install

echo "Mining Shim installed to ./mining_shim/libminingshim.so"
```

## Validation and Error Handling

### Configuration Validation

Add validation to ensure mining shim requirements are met:

```rust
// In src/config_v2.rs or validation module
pub fn validate_mining_shim_config(config: &Config) -> Result<(), String> {
    // Check if simulation seed is set (required for determinism)
    if config.general.simulation_seed.is_none() {
        return Err("SIMULATION_SEED must be set for mining shim determinism".to_string());
    }

    // Check if mining shim library exists
    if let Some(shim_path) = &config.general.mining_shim_path {
        if !Path::new(shim_path).exists() {
            return Err(format!("Mining shim library not found: {}", shim_path));
        }
    } else {
        // Check default location
        let default_path = "./mining_shim/libminingshim.so";
        if !Path::new(default_path).exists() {
            return Err(format!("Mining shim library not found at default location: {}", default_path));
        }
    }

    // Validate miner configurations
    let mut total_hashrate = 0u64;
    let mut miner_count = 0;

    if let Some(user_agents) = &config.agents.user_agents {
        for agent in user_agents {
            if agent.is_miner_value() {
                miner_count += 1;

                // Check hashrate is specified and valid
                if let Some(hashrate_str) = agent.attributes.get("hashrate") {
                    if let Ok(hashrate) = hashrate_str.parse::<u64>() {
                        if hashrate == 0 {
                            return Err(format!("Miner hashrate cannot be zero"));
                        }
                        total_hashrate += hashrate;
                    } else {
                        return Err(format!("Invalid hashrate value: {}", hashrate_str));
                    }
                } else {
                    return Err(format!("Miner agent missing hashrate attribute"));
                }
            }
        }
    }

    if miner_count == 0 {
        return Err("No miner agents found - mining shim requires at least one miner".to_string());
    }

    if total_hashrate == 0 {
        return Err("Total mining hashrate cannot be zero".to_string());
    }

    Ok(())
}
```

### Runtime Validation

The mining shim performs its own validation at startup:

```c
// In libminingshim.c
void __attribute__((constructor)) shim_initialize(void) {
    // Validate environment
    const char* hashrate_str = getenv("MINER_HASHRATE");
    const char* agent_id_str = getenv("AGENT_ID");
    const char* seed_str = getenv("SIMULATION_SEED");

    if (!hashrate_str || !agent_id_str || !seed_str) {
        fprintf(stderr, "[MININGSHIM ERROR] Missing required environment variables\n");
        exit(1);
    }

    // Validate monerod has mining hooks enabled
    const char* hooks_enabled = getenv("MONERO_MINING_HOOKS_ENABLED");
    if (!hooks_enabled || strcmp(hooks_enabled, "1") != 0) {
        fprintf(stderr, "[MININGSHIM ERROR] MONERO_MINING_HOOKS_ENABLED not set to 1\n");
        exit(1);
    }

    // Validate running under Shadow
    if (!is_running_under_shadow()) {
        fprintf(stderr, "[MININGSHIM WARNING] Not running under Shadow simulator\n");
    }

    // Initialize components
    load_configuration();
    initialize_deterministic_prng();
    initialize_logging();
    initialize_metrics();
    initialize_mining_state();

    // Register mining hooks with monerod
    register_mining_hooks();

    miningshim_log(LOG_INFO, "Mining shim initialized and hooks registered successfully");
}
```

## Testing Integration

### Unit Testing

The mining shim includes comprehensive unit tests:

```c
// In mining_shim/tests/test_determinism.c
void test_deterministic_prng(void) {
    // Test that same seed produces identical sequences
    setenv("SIMULATION_SEED", "12345", 1);
    setenv("AGENT_ID", "1", 1);

    initialize_deterministic_prng();

    double values1[100];
    for (int i = 0; i < 100; i++) {
        values1[i] = get_deterministic_random();
    }

    // Reinitialize with same parameters
    initialize_deterministic_prng();

    double values2[100];
    for (int i = 0; i < 100; i++) {
        values2[i] = get_deterministic_random();
    }

    // Verify identical sequences
    for (int i = 0; i < 100; i++) {
        assert(fabs(values1[i] - values2[i]) < 1e-10);
    }
}
```

### Integration Testing

End-to-end tests verify mining shim integration:

```python
# In mining_shim/tests/test_integration.py
def test_mining_shim_integration():
    """Test mining shim with Shadow simulation"""

    # Build mining shim
    subprocess.run(["make", "clean"], cwd="mining_shim", check=True)
    subprocess.run(["make"], cwd="mining_shim", check=True)

    # Generate Shadow configuration with mining shim
    config = {
        "general": {
            "stop_time": "2m",
            "simulation_seed": 42
        },
        "agents": {
            "user_agents": [{
                "daemon": "monerod",
                "wallet": "monero-wallet-rpc",
                "attributes": {
                    "is_miner": True,
                    "hashrate": "10000000"
                }
            }]
        }
    }

    # Run simulation
    result = subprocess.run(["shadow", "shadow_output/shadow_agents.yaml"],
                          capture_output=True, text=True)

    # Verify mining occurred
    assert "Block found" in result.stdout
    assert result.returncode == 0
```

### Determinism Testing

Critical test for reproducible research:

```bash
#!/bin/bash
# test_determinism.sh

SEED=99999
OUTPUT_DIR="/tmp/determinism_test"

# Run simulation twice with same seed
for run in 1 2; do
    rm -rf "$OUTPUT_DIR/run_$run"
    mkdir -p "$OUTPUT_DIR/run_$run"

    SIMULATION_SEED=$SEED \
    shadow shadow_config.yaml > "$OUTPUT_DIR/run_$run/output.log" 2>&1

    # Extract metrics
    cp /tmp/miningshim_metrics_agent1.json "$OUTPUT_DIR/run_$run/"
done

# Compare results
diff "$OUTPUT_DIR/run_1/miningshim_metrics_agent1.json" \
     "$OUTPUT_DIR/run_2/miningshim_metrics_agent1.json"

if [ $? -eq 0 ]; then
    echo "✓ Determinism test PASSED"
else
    echo "✗ Determinism test FAILED"
    exit 1
fi
```

## Performance Optimization

### Memory Management

The mining shim is designed for minimal memory footprint:

```c
// Static allocation for all global state
static prng_state_t g_prng_state = {0};
static mining_state_t g_mining_state = {0};
static shim_metrics_t g_metrics = {0};
static difficulty_tracker_t g_difficulty_tracker = {0};
```

### Thread Safety

All shared state uses proper synchronization:

```c
// Thread-safe random number generation
double get_deterministic_random(void) {
    double result;
    pthread_mutex_lock(&g_prng_state.prng_mutex);
    drand48_r(&g_prng_state.buffer, &result);
    pthread_mutex_unlock(&g_prng_state.prng_mutex);
    return result;
}
```

### Shadow Time Integration

Efficient time advancement using Shadow's discrete-event simulation:

```c
// This blocks in simulation time but doesn't consume real CPU
int wait_result = pthread_cond_timedwait(
    &g_mining_state.state_cond,
    &g_mining_state.state_mutex,
    &timeout  // Shadow advances time to this point instantly
);
```

## Error Handling and Diagnostics

### Comprehensive Logging

The mining shim provides detailed logging for debugging:

```c
typedef enum log_level {
    LOG_ERROR = 1,
    LOG_WARN = 2,
    LOG_INFO = 3,
    LOG_DEBUG = 4
} log_level_t;

// Configurable log levels and file output
void miningshim_log(log_level_t level, const char* format, ...) {
    // Thread-safe logging with timestamps
}
```

### Error Recovery

Graceful handling of various error conditions:

```c
void handle_mining_error(const char* context) {
    miningshim_log(LOG_ERROR, "Mining error: %s", context);

    // Attempt recovery or clean shutdown
    if (g_mining_state.is_mining) {
        stop_mining(NULL);
    }

    // Export error metrics for analysis
    export_metrics_to_file("/tmp/miningshim_error_metrics.json");
}
```

## Deployment Considerations

### Library Installation

The mining shim library should be installed system-wide:

```bash
# Install to standard library location
sudo cp libminingshim.so /usr/local/lib/
sudo ldconfig

# Verify installation
ldd ./mining_shim/libminingshim.so
nm -D ./mining_shim/libminingshim.so | grep start_mining
```

### Version Compatibility

The mining shim is designed to work with specific Monero versions:

```c
// Version detection and compatibility checking
bool check_monerod_compatibility(void) {
    // Verify required symbols exist
    void* start_mining_sym = dlsym(RTLD_NEXT, "start_mining");
    void* stop_mining_sym = dlsym(RTLD_NEXT, "stop_mining");
    void* handle_block_sym = dlsym(RTLD_NEXT, "handle_new_block_notify");

    if (!start_mining_sym || !stop_mining_sym || !handle_block_sym) {
        miningshim_log(LOG_ERROR, "Monero daemon missing required symbols");
        return false;
    }

    return true;
}
```

## Future Extensions

### Planned Enhancements

1. **Dynamic Difficulty**: Support for difficulty adjustments during simulation
2. **Mining Pools**: Coordination between multiple miners for pool mining
3. **Hardware Variance**: Different mining hardware characteristics
4. **Network Effects**: Propagation delays and network topology impact

### Extension Points

The mining shim provides hooks for future enhancements:

```c
// Mining event callbacks
typedef void (*mining_event_hook_t)(mining_event_t* event);

void register_mining_extension(mining_event_hook_t hook) {
    // Allow external modules to hook into mining events
    g_extension_hooks[g_num_extensions++] = hook;
}
```

## Troubleshooting Integration Issues

### Common Integration Problems

1. **Library Not Found**:
   ```bash
   # Check library location
   find /usr -name "libminingshim.so" 2>/dev/null

   # Verify LD_PRELOAD path
   grep "LD_PRELOAD" shadow_output/shadow_agents.yaml
   ```

2. **Missing Environment Variables**:
   ```bash
   # Check generated Shadow config
   grep -A 10 "environment:" shadow_output/shadow_agents.yaml
   ```

3. **Version Incompatibility**:
   ```bash
   # Check Monero symbols
   nm -D /usr/local/bin/monerod | grep mining
   ```

### Debug Build

Enable debug logging for integration debugging:

```bash
# Set debug environment
export MININGSHIM_LOG_LEVEL=DEBUG
export MININGSHIM_LOG_FILE=/tmp/shim_debug.log

# Run simulation
shadow shadow_config.yaml

# Check debug output
tail -f /tmp/shim_debug.log
```

## Summary

The mining shim integrates seamlessly with Monerosim through:

1. **Configuration**: `simulation_seed` and `mining_shim_path` in general config
2. **Agent Detection**: `is_miner` attribute identifies mining agents
3. **Environment Setup**: Automatic injection of required environment variables
4. **Validation**: Comprehensive checks for proper configuration
5. **Testing**: Determinism and integration tests ensure reliability

This integration provides deterministic, scalable mining simulation while maintaining full compatibility with existing Monerosim workflows.