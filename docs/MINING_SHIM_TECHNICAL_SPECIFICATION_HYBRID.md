# Technical Specification: Deterministic Probabilistic Mining Shim for Monerosim

**Version:** 1.0
**Last Updated:** October 27, 2025

## 1.0 Overview and Design Philosophy

This specification defines a deterministic, probabilistic mining shim (`libminingshim.so`) that provides core mining functionality while delegating strategic decisions to external agents. The shim replaces computationally expensive Proof-of-Work (PoW) calculations with a deterministic, probabilistic model suitable for the Shadow discrete-event simulator.

**IMPORTANT**: This shim implementation **REPLACES** the existing block controller approach entirely. The old centralized block controller system will be deprecated and removed to avoid having two competing mining approaches in the codebase. All mining functionality will be handled through this decentralized shim-based system.

### 1.1 Core Design Principles

1. **Probabilistic Mining**: Models mining as a probabilistic search process using exponential distribution
2. **Deterministic Behavior**: Ensures identical results across runs with same configuration and seed
3. **Simple Mining Focus**: Handles only core mining functionality without embedded strategy logic
4. **External Strategy Delegation**: Provides hooks for external strategy agents to make behavioral decisions
5. **Shadow Compatibility**: Designed specifically for Shadow simulator constraints and architecture
6. **Extensible PoW Framework**: Designed to handle multiple PoW use cases beyond just mining (e.g., DDoS prevention mechanisms)

### 1.2 System Context

```
┌─────────────────────────────────────────────────────────────────┐
│                    Monerosim Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│  External Strategy Agents (Python)                         │
│  ├── Honest Mining Strategy                                 │
│  ├── Selfish Mining Strategy                                │
│  └── Custom Strategy Implementations                        │
├─────────────────────────────────────────────────────────────────┤
│  Deterministic Probabilistic Mining Shim (libminingshim.so)  │
│  ├── Probabilistic Mining Engine                            │
│  ├── Deterministic PRNG                                     │
│  ├── Strategy Hook Interface                                │
│  └── Event Notification System                              │
├─────────────────────────────────────────────────────────────────┤
│  Monero Daemon (monerod)                                  │
│  ├── Mining Function Hooks                                   │
│  ├── Block Creation Interface                               │
│  └── P2P Network Layer                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 2.0 Core Architecture

The shim is implemented as a Linux shared library (`.so` file) loaded into each `monerod` process using the `LD_PRELOAD` mechanism. It intercepts specific PoW-related function calls and replaces the CPU-intensive PoW loop with a deterministic, probabilistic model.

### 2.1 Extensible PoW Framework

The shim is designed as an **extensible PoW framework** that can handle multiple Proof-of-Work use cases beyond just block mining:

- **Block Mining**: Traditional cryptocurrency block mining
- **DDoS Prevention**: PoW-based challenge-response mechanisms for connection throttling
- **Transaction Prioritization**: PoW requirements for transaction processing
- **Network Security**: PoW-based authentication and anti-spam measures

This extensibility ensures that as Monero develops new PoW-based mechanisms, they can be seamlessly integrated into the simulation without requiring architectural changes.

### 2.3 Extensibility Implementation

The shim achieves extensibility through:

1. **Generic PoW Interface**: Unified interface for all PoW computations
2. **Type-Based Routing**: Different handling based on PoW type enumeration
3. **Configurable Parameters**: Environment variables for each PoW type
4. **Modular Design**: Separate handling for each PoW use case
5. **Future-Proof Enumeration**: Extensible PoW type system with custom values

#### Example: Adding DDoS Prevention PoW

When Monero adds a new DDoS prevention mechanism requiring PoW:

```c
// Add new PoW type to enumeration
typedef enum pow_type {
    POW_TYPE_MINING = 0,
    POW_TYPE_DDOS_CHALLENGE = 1,    // New DDoS challenge type
    POW_TYPE_TX_PRIORITY = 2,
    POW_TYPE_NETWORK_AUTH = 3,
    POW_TYPE_CUSTOM = 255
} pow_type_t;

// Add environment variable configuration
// In monerod: setenv("DDOS_POW_DIFFICULTY", "10000", 1);
// In shim: const char* ddos_difficulty = getenv("DDOS_POW_DIFFICULTY");

// Add interception point
void ddos_challenge_generate(void* context, ...) {
    pow_context_t pow_context = {
        .challenge_data = extract_challenge_data(context),
        .challenge_size = challenge_data_size,
        .difficulty_target = get_ddos_difficulty(),
        .pow_type = POW_TYPE_DDOS_CHALLENGE,
        .caller_context = context
    };
    
    pow_result_t result;
    miningshim_compute_pow(&pow_context, &result);
    
    // Use result for DDoS prevention
    apply_ddos_challenge_result(&result);
}
```

This extensibility model allows the shim to evolve with Monero's security and protocol enhancements without requiring complete redesign.

### 2.2 Function Interception

The shim intercepts these key functions within `monerod`:

- **`start_mining(...)`**: Initiates the probabilistic mining process
- **`stop_mining(...)`**: Halts the mining process and cleans up resources
- **`handle_new_block_notify(...)`**: Handles notifications of new blocks from peers
- **`pow_verify(...)`**: Generic PoW verification function for non-mining use cases
- **`pow_challenge_generate(...)`**: PoW challenge generation for DDoS prevention
- **`pow_challenge_verify(...)`**: PoW challenge verification for connection validation

### 2.3 Probabilistic Mining Model

The core mining model uses standard academic blockchain simulation approach:

1. **Success Rate (λ)**: `λ = agent_hashrate / network_difficulty`
2. **Time to Find Block (T)**: `T = -ln(1-U) / λ` where U is uniform random number
3. **Event Scheduling**: Uses Shadow's `nanosleep` to advance simulated time

## 3.0 Extensible PoW Implementation

### 3.1 Generic PoW Interface

The shim provides a generic interface that can be used for various PoW applications:

```c
// Generic PoW computation interface
typedef struct pow_context {
    char* challenge_data;
    size_t challenge_size;
    uint64_t difficulty_target;
    uint32_t pow_type;  // MINING, DDOS_CHALLENGE, TX_PRIORITY, etc.
    void* caller_context;
} pow_context_t;

// Generic PoW computation function
typedef struct pow_result {
    bool success;
    uint64_t computation_time_ns;
    char* solution_data;
    size_t solution_size;
    uint32_t nonce;
} pow_result_t;

// Extensible PoW computation interface
int miningshim_compute_pow(const pow_context_t* context, pow_result_t* result);
```

### 3.2 PoW Type Handling

The shim supports different PoW types with appropriate parameters:

```c
typedef enum pow_type {
    POW_TYPE_MINING = 0,           // Block mining PoW
    POW_TYPE_DDOS_CHALLENGE = 1,    // DDoS prevention challenge
    POW_TYPE_TX_PRIORITY = 2,        // Transaction priority PoW
    POW_TYPE_NETWORK_AUTH = 3,       // Network authentication PoW
    POW_TYPE_CUSTOM = 255            // Extensible for future use
} pow_type_t;
```

### 3.3 Integration Points

For each PoW type, the shim provides:

1. **Intercept Points**: Function interception for specific PoW calls
2. **Configuration**: Environment variables for PoW-specific parameters
3. **Strategy Hooks**: Optional strategy agent involvement for complex decisions
4. **Metrics**: Separate metrics collection for each PoW type

## 4.0 Determinism Requirements

### 4.1 Seeding Strategy

Determinism is achieved through carefully designed seeding:

1. **Global Seed**: Read from `SIMULATION_SEED` environment variable
2. **Agent-Specific Seed**: `agent_prng_seed = SIMULATION_SEED + AGENT_ID`
3. **Thread-Safe PRNG**: Uses `drand48_r` for reentrant random number generation

### 4.2 Reproducibility Guarantees

Given identical configuration and global seed, the shim guarantees:
- Identical block discovery times across runs
- Same sequence of mining events
- Reproducible agent behavior for testing

## 5.0 External Strategy Interface

### 5.1 Strategy Hook Architecture

The shim provides a simple interface for external strategy agents:

```c
// Strategy decision callback types
typedef enum {
    STRATEGY_DECISION_BROADCAST_BLOCK = 0,
    STRATEGY_DECISION_WITHHOLD_BLOCK = 1,
    STRATEGY_DECISION_SWITCH_CHAIN = 2
} strategy_decision_t;

// Strategy event notification
typedef struct strategy_event {
    uint32_t event_type;
    uint64_t timestamp;
    void* event_data;
    size_t data_size;
} strategy_event_t;

// Strategy decision callback
typedef strategy_decision_t (*strategy_callback_t)(const strategy_event_t* event);

// Register strategy agent with shim
int miningshim_register_strategy(strategy_callback_t callback);
```

### 5.2 Event Notifications

The shim notifies strategy agents of key mining events:

- **BLOCK_FOUND**: Agent has found a new block
- **PEER_BLOCK_RECEIVED**: New block received from network
- **MINING_STARTED**: Mining process has started
- **MINING_STOPPED**: Mining process has stopped

### 5.3 Strategy Decision Points

External agents can influence behavior at these decision points:

- **Block Broadcasting**: Whether to immediately broadcast found blocks
- **Chain Switching**: Whether to switch to a competing chain
- **Mining Continuation**: Whether to continue or stop mining

## 6.0 Configuration

### 6.1 Environment Variables

The shim is configured via environment variables:

```bash
# Required Configuration
MINER_HASHRATE=1000000          # Agent hashrate in H/s
AGENT_ID=1                       # Unique agent identifier
SIMULATION_SEED=12345           # Global simulation seed

# Optional Configuration
MINER_STRATEGY_SOCKET=/tmp/agent1_strategy.sock  # Strategy agent socket
MININGSHIM_LOG_LEVEL=INFO                    # Logging level
MININGSHIM_LOG_FILE=/tmp/miner1_shim.log     # Log file path
```

### 6.2 Configuration Validation

The shim validates all required environment variables on initialization and fails gracefully with descriptive error messages if any are missing or invalid.

## 7.0 Implementation Details

### 7.1 Core Data Structures

```c
// Mining state management
typedef struct mining_state {
    bool is_mining;
    uint64_t current_difficulty;
    uint64_t last_block_height;
    pthread_t mining_thread;
    pthread_mutex_t state_mutex;
    pthread_cond_t state_cond;
} mining_state_t;

// PRNG state for determinism
typedef struct deterministic_prng {
    struct drand48_data buffer;
    unsigned int seed;
} deterministic_prng_t;

// Strategy agent interface
typedef struct strategy_interface {
    int socket_fd;
    strategy_callback_t callback;
    bool is_connected;
} strategy_interface_t;
```

### 7.2 Mining Loop Implementation

```c
void* mining_loop(void* context) {
    // Initialize deterministic PRNG
    deterministic_prng_t prng;
    init_deterministic_prng(&prng);
    
    pthread_mutex_lock(&g_mining_state.state_mutex);
    while (g_mining_state.is_mining) {
        pthread_mutex_unlock(&g_mining_state.state_mutex);
        
        // Get current network difficulty
        uint64_t difficulty = get_current_network_difficulty(context);
        
        // Calculate time to find block using exponential distribution
        double lambda = (double)get_miner_hashrate() / difficulty;
        double u;
        drand48_r(&prng.buffer, &u);
        uint64_t time_to_block_ns = (uint64_t)(-log(1.0 - u) / lambda * 1e9);
        
        // Sleep for calculated time (Shadow will advance simulation time)
        struct timespec sleep_time = {
            .tv_sec = time_to_block_ns / 1000000000,
            .tv_nsec = time_to_block_ns % 1000000000
        };
        
        // Check if we should continue mining
        pthread_mutex_lock(&g_mining_state.state_mutex);
        if (!g_mining_state.is_mining) {
            pthread_mutex_unlock(&g_mining_state.state_mutex);
            break;
        }
        
        // Cancellable sleep with timeout
        struct timespec timeout;
        clock_gettime(CLOCK_REALTIME, &timeout);
        timeout.tv_sec += sleep_time.tv_sec;
        timeout.tv_nsec += sleep_time.tv_nsec;
        if (timeout.tv_nsec >= 1000000000) {
            timeout.tv_sec++;
            timeout.tv_nsec -= 1000000000;
        }
        
        int wait_result = pthread_cond_timedwait(&g_mining_state.state_cond, 
                                             &g_mining_state.state_mutex, 
                                             &timeout);
        
        if (wait_result == 0) {
            // Woken up by new block notification, restart mining
            pthread_mutex_unlock(&g_mining_state.state_mutex);
            continue;
        }
        
        // Timeout occurred - we found a block!
        pthread_mutex_unlock(&g_mining_state.state_mutex);
        
        // Notify strategy agent and get decision
        strategy_decision_t decision = notify_strategy_agent_block_found();
        
        if (decision == STRATEGY_DECISION_BROADCAST_BLOCK) {
            // Create and broadcast block
            create_and_broadcast_block(context);
        } else if (decision == STRATEGY_DECISION_WITHHOLD_BLOCK) {
            // Add to private chain (for selfish mining)
            add_to_private_chain(context);
        }
        
        pthread_mutex_lock(&g_mining_state.state_mutex);
    }
    pthread_mutex_unlock(&g_mining_state.state_mutex);
    
    return NULL;
}
```

### 7.3 Function Interception

```c
// Intercepted start_mining function
void start_mining(void* context, ...) {
    pthread_mutex_lock(&g_mining_state.state_mutex);
    if (g_mining_state.is_mining) {
        pthread_mutex_unlock(&g_mining_state.state_mutex);
        return;
    }
    
    g_mining_state.is_mining = true;
    
    // Start mining thread
    pthread_create(&g_mining_state.mining_thread, NULL, mining_loop, context);
    pthread_mutex_unlock(&g_mining_state.state_mutex);
    
    // Notify strategy agent
    notify_strategy_agent_mining_started();
}

// Intercepted stop_mining function
void stop_mining(void* context, ...) {
    pthread_mutex_lock(&g_mining_state.state_mutex);
    if (!g_mining_state.is_mining) {
        pthread_mutex_unlock(&g_mining_state.state_mutex);
        return;
    }
    
    g_mining_state.is_mining = false;
    pthread_cond_signal(&g_mining_state.state_cond);
    pthread_mutex_unlock(&g_mining_state.state_mutex);
    
    // Wait for mining thread to finish
    pthread_join(g_mining_state.mining_thread, NULL);
    
    // Notify strategy agent
    notify_strategy_agent_mining_stopped();
    
    // Call original function if needed
    stop_mining_func_t original_stop_mining = (stop_mining_func_t)dlsym(RTLD_NEXT, "stop_mining");
    if (original_stop_mining) {
        original_stop_mining(context, ...);
    }
}

// Intercepted new block handler
void handle_new_block_notify(void* context, ...) {
    // Signal mining thread to restart
    pthread_mutex_lock(&g_mining_state.state_mutex);
    if (g_mining_state.is_mining) {
        pthread_cond_signal(&g_mining_state.state_cond);
    }
    pthread_mutex_unlock(&g_mining_state.state_mutex);
    
    // Notify strategy agent
    notify_strategy_agent_peer_block_received();
    
    // Call original handler
    handle_new_block_func_t original_handler = (handle_new_block_func_t)dlsym(RTLD_NEXT, "handle_new_block_notify");
    if (original_handler) {
        original_handler(context, ...);
    }
}
```

## 8.0 Integration with Shadow

### 8.1 Shadow Configuration

```yaml
# shadow_agents.yaml - Shim integration example
hosts:
  miner001:
    network_node_id: 0
    ip_addr: "192.168.1.10"
    processes:
      - path: "/usr/local/bin/monerod-simulation"
        args: "--data-dir=/tmp/monero-miner001 --rpc-bind-port=28081"
        environment:
          LD_PRELOAD: "/usr/local/lib/libminingshim.so"
          MINER_HASHRATE: "1000000"
          AGENT_ID: "1"
          SIMULATION_SEED: "12345"
          MINER_STRATEGY_SOCKET: "/tmp/miner001_strategy.sock"
          MININGSHIM_LOG_LEVEL: "INFO"
        start_time: "0s"
      - path: "python3"
        args: "-m agents.mining_strategy_agent --id miner001 --strategy honest"
        environment:
          PYTHONPATH: "/opt/monerosim/agents"
          MINING_AGENT_STRATEGY: "honest"
          MINING_AGENT_SOCKET: "/tmp/miner001_strategy.sock"
        start_time: "5s"
```

### 8.2 Strategy Agent Example

```python
# Python strategy agent example
class MiningStrategyAgent(BaseAgent):
    def __init__(self, strategy="honest", **kwargs):
        super().__init__(**kwargs)
        self.strategy = strategy
        self.shim_socket = kwargs.get('shim_socket', '/tmp/miningshim.sock')
        
    def _setup_agent(self):
        # Connect to shim communication socket
        self.shim_connection = connect_to_shim_socket(self.shim_socket)
        
        # Register strategy callbacks with shim
        self.register_strategy_callbacks()
        
    def handle_block_found_event(self, event):
        """Called when shim finds a block"""
        if self.strategy == "honest":
            return self.handle_honest_block_found(event)
        elif self.strategy == "selfish":
            return self.handle_selfish_block_found(event)
        else:
            return self.handle_custom_block_found(event)
            
    def handle_honest_block_found(self, event):
        """Honest strategy: always broadcast immediately"""
        return STRATEGY_DECISION_BROADCAST_BLOCK
        
    def handle_selfish_block_found(self, event):
        """Selfish strategy: implement selfish mining logic"""
        # Complex selfish mining state machine logic here
        return self.evaluate_selfish_decision(event)
```

## 9.0 Testing Requirements

### 9.1 Determinism Testing

```c
// Test that identical seeds produce identical results
void test_deterministic_behavior() {
    const char* test_config = "MINER_HASHRATE=1000000,AGENT_ID=1,SIMULATION_SEED=12345";
    
    // Run simulation twice with identical config
    simulation_result_t result1 = run_simulation_with_config(test_config);
    simulation_result_t result2 = run_simulation_with_config(test_config);
    
    // Verify identical results
    assert(result1.block_discovery_times_count == result2.block_discovery_times_count);
    for (int i = 0; i < result1.block_discovery_times_count; i++) {
        assert(result1.block_discovery_times[i] == result2.block_discovery_times[i]);
    }
}
```

### 9.2 Probabilistic Model Testing

```c
// Test exponential distribution properties
void test_probabilistic_model() {
    const int num_samples = 10000;
    const double hashrate = 1000000.0; // 1 MH/s
    const uint64_t difficulty = 1000000;
    const double expected_lambda = hashrate / difficulty;
    
    // Generate many block discovery times
    double discovery_times[num_samples];
    for (int i = 0; i < num_samples; i++) {
        discovery_times[i] = simulate_block_discovery_time(hashrate, difficulty);
    }
    
    // Verify exponential distribution properties
    double mean_time = calculate_mean(discovery_times, num_samples);
    double expected_mean = 1.0 / expected_lambda;
    
    // Mean should be close to expected (within 5% for large sample)
    assert(fabs(mean_time - expected_mean) < expected_mean * 0.05);
}
```

### 9.3 Strategy Interface Testing

```python
# Test strategy agent integration
def test_strategy_agent_integration():
    strategies = ["honest", "selfish", "custom"]
    
    for strategy in strategies:
        # Start strategy agent
        strategy_agent = start_strategy_agent(strategy)
        
        # Configure shim with strategy agent
        shim_config = create_shim_config_with_strategy(strategy_agent.socket_path)
        shim = MiningShim(shim_config)
        
        # Test strategy decision flow
        test_events = generate_mining_events()
        for event in test_events:
            decision = shim.notify_strategy_agent(event)
            strategy_decision = strategy_agent.handle_event(event)
            
            assert decision == strategy_decision
        
        # Cleanup
        strategy_agent.stop()
        shim.cleanup()
```

## 10.0 Build and Deployment

### 10.1 Build Requirements

```bash
# Build the shim library
gcc -shared -fPIC -o libminingshim.so \
    libminingshim.c \
    -ldl -lpthread -lm \
    -O2 -DNDEBUG

# Install to system location
sudo cp libminingshim.so /usr/local/lib/
sudo ldconfig
```

### 10.2 Dependencies

- **Build Environment**: Standard C/C++ compiler (GCC/Clang)
- **Libraries**: `pthread` for threading, `dlfcn.h` for dynamic linking, `math.h` for logarithm
- **Target Application**: Dynamically linked `monerod` binary
- **Execution Environment**: Shadow discrete-event simulator

## 11.0 Monitoring and Observability

### 11.1 Logging Interface

```c
typedef enum log_level {
    LOG_NONE = 0,
    LOG_ERROR = 1,
    LOG_WARN = 2,
    LOG_INFO = 3,
    LOG_DEBUG = 4
} log_level_t;

// Logging interface
void miningshim_log(log_level_t level, const char* format, ...);
void miningshim_set_log_level(log_level_t level);
```

### 11.2 Metrics Collection

```c
typedef struct shim_metrics {
    uint64_t blocks_found;
    uint64_t total_mining_time_ns;
    uint64_t average_block_time_ns;
    uint32_t strategy_decisions_made;
    uint64_t uptime_seconds;
} shim_metrics_t;

// Metrics interface
int miningshim_get_metrics(shim_metrics_t* metrics);
void miningshim_reset_metrics(void);
```

## 12.0 Security Considerations

### 12.1 Input Validation

- Validate all environment variables for type and range
- Implement bounds checking for array operations
- Protect against buffer overflows in string handling

### 12.2 Resource Protection

- Implement resource usage limits to prevent DoS
- Use bounded queues and memory pools
- Proper cleanup on error conditions

### 12.3 Communication Security

- Validate socket connections and permissions
- Implement proper authentication for strategy agents
- Log all access attempts and failures

## 13.0 Migration and Deprecation

### 13.1 Migration from Block Controller

This shim-based approach **REPLACES** the existing block controller system. The migration plan includes:

1. **Phase 1**: Implement shim alongside existing block controller for testing
2. **Phase 2**: Migrate all mining configurations to use shim-based approach
3. **Phase 3**: Remove deprecated block controller code and related scripts
4. **Phase 4**: Update documentation and examples to use shim exclusively

### 13.2 Code Cleanup Requirements

The following components will be deprecated and removed:

- `agents/block_controller.py` - Centralized block controller agent
- `agents/miner_distributor.py` - Mining reward distribution logic
- Related configuration options in `config_v2.rs`
- Legacy mining-related scripts in `scripts/` directory

### 13.3 Backward Compatibility

During transition period:

- Configuration files will be validated for either approach
- Clear error messages will guide users to shim-based configuration
- Migration utilities will help convert old configurations to new format

## 14.0 Conclusion

This specification defines a deterministic, probabilistic mining shim that provides core mining functionality while delegating strategic decisions to external agents. The design balances several key requirements:

- **Probabilistic Accuracy**: Uses mathematically sound exponential distribution model
- **Deterministic Behavior**: Ensures reproducible simulation results
- **Simple Focus**: Handles only core mining without embedded strategy logic
- **Extensibility**: Provides clean interface for external strategy implementations
- **Shadow Compatibility**: Designed specifically for Shadow simulator architecture

The specification provides sufficient detail for immediate implementation while maintaining flexibility for future enhancements and strategy implementations.