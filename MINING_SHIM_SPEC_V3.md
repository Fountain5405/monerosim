# Mining Shim Technical Specification v3.0

**Version:** 3.0  
**Last Updated:** November 3, 2025  
**Focus:** Core Mining Shim Implementation

## 1.0 Overview

This specification defines a **deterministic probabilistic mining shim** (`libminingshim.so`) that intercepts and replaces Monero's computationally expensive Proof-of-Work calculations with a lightweight probabilistic model suitable for the Shadow discrete-event simulator.

### 1.1 Purpose

The mining shim enables realistic Monero network simulations by:

- **Intercepting** mining-related function calls in `monerod` processes
- **Replacing** CPU-intensive cryptographic hashing with probabilistic time-based simulation
- **Maintaining** deterministic behavior for reproducible research
- **Preserving** network protocol authenticity while eliminating computational overhead

### 1.2 Core Design Principles

1. **Transparent Interception**: Uses `LD_PRELOAD` to inject shim into `monerod` without source modifications
2. **Probabilistic Accuracy**: Models mining as exponential distribution matching real-world behavior
3. **Deterministic Execution**: Guarantees identical results across runs with same seed
4. **Shadow Integration**: Leverages Shadow's time manipulation for efficient simulation
5. **Minimal Footprint**: Simple, focused implementation without embedded strategy logic

### 1.3 System Context

```
┌──────────────────────────────────────────────────────────┐
│                  Shadow Simulator Environment            │
│                                                          │
│  ┌────────────────────────────────────────────────┐     │
│  │         monerod Process (unmodified)           │     │
│  │                                                │     │
│  │  ┌──────────────────────────────────────┐     │     │
│  │  │   libminingshim.so (LD_PRELOAD)      │     │     │
│  │  │                                      │     │     │
│  │  │  • Intercepts start_mining()         │     │     │
│  │  │  • Intercepts stop_mining()          │     │     │
│  │  │  • Intercepts new block handlers     │     │     │
│  │  │  • Probabilistic mining loop         │     │     │
│  │  │  • Deterministic PRNG                │     │     │
│  │  └──────────────────────────────────────┘     │     │
│  │                                                │     │
│  │  Native monerod functions (P2P, consensus)    │     │
│  └────────────────────────────────────────────────┘     │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## 2.0 Interception Architecture

### 2.1 LD_PRELOAD Mechanism

The shim is implemented as a Linux shared library loaded before the main `monerod` executable:

```bash
# Environment setup in Shadow configuration
LD_PRELOAD=./mining_shim/libminingshim.so monerod --start-mining ...
```

**Key Properties**:
- No source code modifications to Monero required
- Function symbols resolved to shim implementations first
- Original functions accessible via `dlsym(RTLD_NEXT, ...)`
- Clean separation between simulation and production code

### 2.2 Intercepted Functions

The shim intercepts these critical mining functions:

```c
// Core mining control
void start_mining(void* miner_context, const char* wallet_address, 
                 uint64_t threads_count, bool background_mining);
void stop_mining(void* miner_context);

// Block event handling
void handle_new_block_notify(void* blockchain_context, 
                             const block_info_t* new_block);

// Mining state queries
bool get_mining_status(void* miner_context, mining_status_t* status);
uint64_t get_current_difficulty(void* blockchain_context);
```

### 2.3 Function Signature Discovery

**Challenge**: Monero's internal APIs may not be stable across versions.

**Solution**: Use symbol inspection and dynamic discovery:

```bash
# Discover function signatures
nm -D /usr/local/bin/monerod | grep mining
objdump -T /usr/local/bin/monerod | grep start_mining
```

**Compatibility Strategy**:
- Target specific Monero version for initial implementation
- Document required symbol names and signatures
- Implement version detection and compatibility checking
- Provide clear error messages for unsupported versions

## 3.0 Probabilistic Mining Model

### 3.1 Mathematical Foundation

Mining is modeled as a **Poisson process** with exponential distribution for block discovery times:

**Given**:
- `H` = Agent hashrate (hashes/second)
- `D` = Network difficulty (hashes required)
- `λ = H / D` = Success rate (blocks/second)

**Time to find block** follows exponential distribution:
```
T = -ln(1 - U) / λ
```
Where `U ~ Uniform(0,1)` is a random number from deterministic PRNG.

### 3.2 Implementation Details

```c
// Calculate time to find next block
uint64_t calculate_block_discovery_time(uint64_t hashrate, uint64_t difficulty) {
    double lambda = (double)hashrate / (double)difficulty;
    
    // Get deterministic random number [0,1)
    double u;
    drand48_r(&g_prng_state.buffer, &u);
    
    // Exponential distribution: T = -ln(1-U) / λ
    double time_seconds = -log(1.0 - u) / lambda;
    
    // Convert to nanoseconds for Shadow
    return (uint64_t)(time_seconds * 1e9);
}
```

### 3.3 Network Difficulty Tracking

The shim must track current network difficulty to calculate accurate mining times:

```c
typedef struct difficulty_tracker {
    uint64_t current_difficulty;
    uint64_t last_update_height;
    pthread_mutex_t difficulty_mutex;
} difficulty_tracker_t;

// Update difficulty when new block received
void update_network_difficulty(const block_info_t* new_block) {
    pthread_mutex_lock(&g_difficulty_tracker.difficulty_mutex);
    
    g_difficulty_tracker.current_difficulty = new_block->difficulty;
    g_difficulty_tracker.last_update_height = new_block->height;
    
    pthread_mutex_unlock(&g_difficulty_tracker.difficulty_mutex);
}
```

## 4.0 Deterministic PRNG System

### 4.1 Seeding Strategy

Determinism requires carefully designed seed management:

```c
// Global seed configuration
typedef struct seed_config {
    uint64_t global_seed;      // From SIMULATION_SEED env var
    uint32_t agent_id;          // From AGENT_ID env var
    uint64_t agent_seed;        // Derived: global_seed + agent_id
} seed_config_t;

// PRNG state (thread-safe)
typedef struct prng_state {
    struct drand48_data buffer;
    seed_config_t seed_config;
    pthread_mutex_t prng_mutex;
} prng_state_t;
```

### 4.2 Initialization

```c
void initialize_deterministic_prng(void) {
    // Read configuration from environment
    const char* global_seed_str = getenv("SIMULATION_SEED");
    const char* agent_id_str = getenv("AGENT_ID");
    
    if (!global_seed_str || !agent_id_str) {
        miningshim_log(LOG_ERROR, "Missing required env vars: SIMULATION_SEED, AGENT_ID");
        exit(1);
    }
    
    g_prng_state.seed_config.global_seed = strtoull(global_seed_str, NULL, 10);
    g_prng_state.seed_config.agent_id = strtoul(agent_id_str, NULL, 10);
    g_prng_state.seed_config.agent_seed = 
        g_prng_state.seed_config.global_seed + g_prng_state.seed_config.agent_id;
    
    // Initialize reentrant PRNG
    srand48_r(g_prng_state.seed_config.agent_seed, &g_prng_state.buffer);
    
    pthread_mutex_init(&g_prng_state.prng_mutex, NULL);
    
    miningshim_log(LOG_INFO, "PRNG initialized: global_seed=%lu, agent_id=%u, agent_seed=%lu",
                   g_prng_state.seed_config.global_seed,
                   g_prng_state.seed_config.agent_id,
                   g_prng_state.seed_config.agent_seed);
}
```

### 4.3 Thread-Safe Random Number Generation

```c
double get_deterministic_random(void) {
    double result;
    pthread_mutex_lock(&g_prng_state.prng_mutex);
    drand48_r(&g_prng_state.buffer, &result);
    pthread_mutex_unlock(&g_prng_state.prng_mutex);
    return result;
}
```

## 5.0 Mining Loop Implementation

### 5.1 Core Mining Thread

```c
void* mining_loop(void* context) {
    miningshim_log(LOG_INFO, "Mining loop started");
    
    pthread_mutex_lock(&g_mining_state.state_mutex);
    while (g_mining_state.is_mining) {
        pthread_mutex_unlock(&g_mining_state.state_mutex);
        
        // Get current network difficulty
        uint64_t difficulty = get_current_network_difficulty();
        uint64_t hashrate = get_agent_hashrate();
        
        // Calculate time to find next block
        uint64_t time_to_block_ns = calculate_block_discovery_time(hashrate, difficulty);
        
        miningshim_log(LOG_DEBUG, "Mining iteration: difficulty=%lu, hashrate=%lu, time_to_block=%lu ns",
                       difficulty, hashrate, time_to_block_ns);
        
        // Convert to timespec for sleeping
        struct timespec sleep_duration = {
            .tv_sec = time_to_block_ns / 1000000000ULL,
            .tv_nsec = time_to_block_ns % 1000000000ULL
        };
        
        // Acquire lock before waiting
        pthread_mutex_lock(&g_mining_state.state_mutex);
        if (!g_mining_state.is_mining) {
            pthread_mutex_unlock(&g_mining_state.state_mutex);
            break;
        }
        
        // Calculate absolute timeout
        struct timespec timeout;
        clock_gettime(CLOCK_REALTIME, &timeout);
        timeout.tv_sec += sleep_duration.tv_sec;
        timeout.tv_nsec += sleep_duration.tv_nsec;
        if (timeout.tv_nsec >= 1000000000) {
            timeout.tv_sec++;
            timeout.tv_nsec -= 1000000000;
        }
        
        // Wait for timeout (block found) or signal (new peer block)
        int wait_result = pthread_cond_timedwait(
            &g_mining_state.state_cond,
            &g_mining_state.state_mutex,
            &timeout
        );
        
        if (wait_result == ETIMEDOUT) {
            // Timeout occurred - we found a block!
            pthread_mutex_unlock(&g_mining_state.state_mutex);
            
            miningshim_log(LOG_INFO, "Block found after %lu ns", time_to_block_ns);
            
            // Create and broadcast block via monerod APIs
            create_and_broadcast_block(context);
            
            pthread_mutex_lock(&g_mining_state.state_mutex);
        } else if (wait_result == 0) {
            // Signaled - new block from peer, restart mining
            miningshim_log(LOG_DEBUG, "Mining interrupted by peer block");
            // Loop continues with new difficulty
        } else {
            miningshim_log(LOG_ERROR, "pthread_cond_timedwait error: %d", wait_result);
        }
    }
    pthread_mutex_unlock(&g_mining_state.state_mutex);
    
    miningshim_log(LOG_INFO, "Mining loop stopped");
    return NULL;
}
```

### 5.2 Block Creation Interface

```c
// Call into monerod's actual block creation logic
void create_and_broadcast_block(void* miner_context) {
    // Get original block creation function from monerod
    typedef bool (*create_block_func_t)(void* context, block_template_t* block_template);
    create_block_func_t create_block = (create_block_func_t)dlsym(RTLD_NEXT, "create_block");
    
    if (!create_block) {
        miningshim_log(LOG_ERROR, "Failed to find create_block function in monerod");
        return;
    }
    
    // Create block template
    block_template_t block_template;
    memset(&block_template, 0, sizeof(block_template));
    
    // Set nonce to deterministic value (simulation doesn't need real PoW)
    block_template.nonce = generate_deterministic_nonce();
    
    // Call monerod's block creation
    bool success = create_block(miner_context, &block_template);
    
    if (success) {
        miningshim_log(LOG_INFO, "Block created and broadcasted successfully");
        g_metrics.blocks_found++;
    } else {
        miningshim_log(LOG_WARN, "Block creation failed");
    }
}

uint32_t generate_deterministic_nonce(void) {
    // Generate nonce from PRNG for determinism
    return (uint32_t)(get_deterministic_random() * UINT32_MAX);
}
```

## 6.0 Function Interception Implementation

### 6.1 Start Mining Interception

```c
// Global mining state
typedef struct mining_state {
    bool is_mining;
    pthread_t mining_thread;
    pthread_mutex_t state_mutex;
    pthread_cond_t state_cond;
    void* miner_context;
} mining_state_t;

static mining_state_t g_mining_state = {0};

// Intercepted start_mining function
void start_mining(void* miner_context, const char* wallet_address, 
                 uint64_t threads_count, bool background_mining) {
    miningshim_log(LOG_INFO, "start_mining intercepted: wallet=%s, threads=%lu",
                   wallet_address, threads_count);
    
    pthread_mutex_lock(&g_mining_state.state_mutex);
    
    if (g_mining_state.is_mining) {
        miningshim_log(LOG_WARN, "Mining already active, ignoring start request");
        pthread_mutex_unlock(&g_mining_state.state_mutex);
        return;
    }
    
    g_mining_state.is_mining = true;
    g_mining_state.miner_context = miner_context;
    
    // Start mining thread
    int result = pthread_create(&g_mining_state.mining_thread, NULL, 
                                mining_loop, miner_context);
    
    if (result != 0) {
        miningshim_log(LOG_ERROR, "Failed to create mining thread: %d", result);
        g_mining_state.is_mining = false;
        pthread_mutex_unlock(&g_mining_state.state_mutex);
        return;
    }
    
    pthread_mutex_unlock(&g_mining_state.state_mutex);
    
    miningshim_log(LOG_INFO, "Mining started successfully");
    g_metrics.mining_start_time = get_current_time_ns();
}
```

### 6.2 Stop Mining Interception

```c
void stop_mining(void* miner_context) {
    miningshim_log(LOG_INFO, "stop_mining intercepted");
    
    pthread_mutex_lock(&g_mining_state.state_mutex);
    
    if (!g_mining_state.is_mining) {
        miningshim_log(LOG_WARN, "Mining not active, ignoring stop request");
        pthread_mutex_unlock(&g_mining_state.state_mutex);
        return;
    }
    
    // Signal mining thread to stop
    g_mining_state.is_mining = false;
    pthread_cond_signal(&g_mining_state.state_cond);
    pthread_mutex_unlock(&g_mining_state.state_mutex);
    
    // Wait for mining thread to finish
    pthread_join(g_mining_state.mining_thread, NULL);
    
    miningshim_log(LOG_INFO, "Mining stopped successfully");
    
    // Update metrics
    g_metrics.total_mining_time_ns = get_current_time_ns() - g_metrics.mining_start_time;
}
```

### 6.3 New Block Notification Interception

```c
void handle_new_block_notify(void* blockchain_context, const block_info_t* new_block) {
    miningshim_log(LOG_DEBUG, "New peer block received: height=%lu, difficulty=%lu",
                   new_block->height, new_block->difficulty);
    
    // Update difficulty tracker
    update_network_difficulty(new_block);
    
    // Interrupt current mining to restart with new chain state
    pthread_mutex_lock(&g_mining_state.state_mutex);
    if (g_mining_state.is_mining) {
        pthread_cond_signal(&g_mining_state.state_cond);
        miningshim_log(LOG_DEBUG, "Mining interrupted for peer block");
    }
    pthread_mutex_unlock(&g_mining_state.state_mutex);
    
    // Call original handler to process block normally
    typedef void (*handle_block_func_t)(void*, const block_info_t*);
    handle_block_func_t original_handler = 
        (handle_block_func_t)dlsym(RTLD_NEXT, "handle_new_block_notify");
    
    if (original_handler) {
        original_handler(blockchain_context, new_block);
    } else {
        miningshim_log(LOG_WARN, "Original handle_new_block_notify not found");
    }
}
```

## 7.0 Configuration System

### 7.1 Environment Variables

```c
typedef struct shim_config {
    uint64_t miner_hashrate;        // MINER_HASHRATE
    uint32_t agent_id;              // AGENT_ID
    uint64_t simulation_seed;       // SIMULATION_SEED
    log_level_t log_level;          // MININGSHIM_LOG_LEVEL
    char log_file_path[256];        // MININGSHIM_LOG_FILE
} shim_config_t;

static shim_config_t g_config = {0};
```

### 7.2 Configuration Loading

```c
void load_configuration(void) {
    // Required configuration
    const char* hashrate_str = getenv("MINER_HASHRATE");
    const char* agent_id_str = getenv("AGENT_ID");
    const char* seed_str = getenv("SIMULATION_SEED");
    
    if (!hashrate_str || !agent_id_str || !seed_str) {
        fprintf(stderr, "[MININGSHIM ERROR] Missing required environment variables:\n");
        fprintf(stderr, "  MINER_HASHRATE: %s\n", hashrate_str ? "set" : "MISSING");
        fprintf(stderr, "  AGENT_ID: %s\n", agent_id_str ? "set" : "MISSING");
        fprintf(stderr, "  SIMULATION_SEED: %s\n", seed_str ? "set" : "MISSING");
        exit(1);
    }
    
    g_config.miner_hashrate = strtoull(hashrate_str, NULL, 10);
    g_config.agent_id = strtoul(agent_id_str, NULL, 10);
    g_config.simulation_seed = strtoull(seed_str, NULL, 10);
    
    // Optional configuration
    const char* log_level_str = getenv("MININGSHIM_LOG_LEVEL");
    if (log_level_str) {
        if (strcmp(log_level_str, "DEBUG") == 0) g_config.log_level = LOG_DEBUG;
        else if (strcmp(log_level_str, "INFO") == 0) g_config.log_level = LOG_INFO;
        else if (strcmp(log_level_str, "WARN") == 0) g_config.log_level = LOG_WARN;
        else if (strcmp(log_level_str, "ERROR") == 0) g_config.log_level = LOG_ERROR;
        else g_config.log_level = LOG_INFO;
    } else {
        g_config.log_level = LOG_INFO;
    }
    
    const char* log_file_str = getenv("MININGSHIM_LOG_FILE");
    if (log_file_str) {
        strncpy(g_config.log_file_path, log_file_str, sizeof(g_config.log_file_path) - 1);
    } else {
        snprintf(g_config.log_file_path, sizeof(g_config.log_file_path),
                "/tmp/miningshim_agent%u.log", g_config.agent_id);
    }
}
```

### 7.3 Shadow YAML Configuration

```yaml
hosts:
  miner001:
    network_node_id: 0
    ip_addr: "192.168.1.10"
    processes:
      - path: "/usr/local/bin/monerod"
        args: "--data-dir /tmp/miner001 --start-mining <wallet_address>"
        environment:
          # Shim injection
          LD_PRELOAD: "./mining_shim/libminingshim.so"
          
          # Required shim configuration
          MINER_HASHRATE: "1000000"        # 1 MH/s
          AGENT_ID: "1"
          SIMULATION_SEED: "12345"
          
          # Optional shim configuration
          MININGSHIM_LOG_LEVEL: "INFO"
          MININGSHIM_LOG_FILE: "/tmp/miner001_shim.log"
        start_time: "0s"
```

## 8.0 Shadow Integration

### 8.1 Time Manipulation

Shadow intercepts time-related system calls. The shim leverages this for efficient simulation:

```c
// This nanosleep is intercepted by Shadow and advances simulation time
// without consuming real CPU time
nanosleep(&sleep_duration, NULL);

// Similarly for condition variable timeouts
pthread_cond_timedwait(&cond, &mutex, &timeout);
```

**Key Insight**: Shadow's discrete-event simulation means the `pthread_cond_timedwait` in the mining loop advances simulation time instantly to the timeout value if no signal occurs.

### 8.2 Shadow-Specific Considerations

```c
// Detect if running under Shadow
bool is_running_under_shadow(void) {
    // Shadow sets LD_PRELOAD to include libshadow-interpose.so
    const char* ld_preload = getenv("LD_PRELOAD");
    return ld_preload && strstr(ld_preload, "libshadow");
}

// Initialize shim with Shadow awareness
void __attribute__((constructor)) shim_initialize(void) {
    if (!is_running_under_shadow()) {
        fprintf(stderr, "[MININGSHIM] WARNING: Not running under Shadow simulator\n");
        fprintf(stderr, "[MININGSHIM] Shim is designed for Shadow environment only\n");
    }
    
    load_configuration();
    initialize_deterministic_prng();
    initialize_logging();
    initialize_metrics();
    initialize_mining_state();
    
    miningshim_log(LOG_INFO, "Mining shim initialized successfully");
}
```

## 9.0 Monitoring and Metrics

### 9.1 Metrics Structure

```c
typedef struct shim_metrics {
    uint64_t blocks_found;
    uint64_t mining_iterations;
    uint64_t peer_blocks_received;
    uint64_t mining_start_time;
    uint64_t total_mining_time_ns;
    uint64_t last_block_time_ns;
} shim_metrics_t;

static shim_metrics_t g_metrics = {0};
```

### 9.2 Metrics Export

```c
// Export metrics to JSON file for post-simulation analysis
void export_metrics_to_file(const char* filepath) {
    FILE* fp = fopen(filepath, "w");
    if (!fp) {
        miningshim_log(LOG_ERROR, "Failed to open metrics file: %s", filepath);
        return;
    }
    
    fprintf(fp, "{\n");
    fprintf(fp, "  \"agent_id\": %u,\n", g_config.agent_id);
    fprintf(fp, "  \"blocks_found\": %lu,\n", g_metrics.blocks_found);
    fprintf(fp, "  \"mining_iterations\": %lu,\n", g_metrics.mining_iterations);
    fprintf(fp, "  \"peer_blocks_received\": %lu,\n", g_metrics.peer_blocks_received);
    fprintf(fp, "  \"total_mining_time_ns\": %lu,\n", g_metrics.total_mining_time_ns);
    
    if (g_metrics.blocks_found > 0) {
        uint64_t avg_block_time = g_metrics.total_mining_time_ns / g_metrics.blocks_found;
        fprintf(fp, "  \"average_block_time_ns\": %lu,\n", avg_block_time);
    }
    
    fprintf(fp, "  \"hashrate\": %lu\n", g_config.miner_hashrate);
    fprintf(fp, "}\n");
    
    fclose(fp);
    miningshim_log(LOG_INFO, "Metrics exported to %s", filepath);
}

// Called on shim cleanup
void __attribute__((destructor)) shim_cleanup(void) {
    char metrics_path[512];
    snprintf(metrics_path, sizeof(metrics_path), 
             "/tmp/miningshim_metrics_agent%u.json", g_config.agent_id);
    
    export_metrics_to_file(metrics_path);
    
    miningshim_log(LOG_INFO, "Mining shim cleanup complete");
}
```

## 10.0 Logging System

### 10.1 Log Levels

```c
typedef enum log_level {
    LOG_NONE = 0,
    LOG_ERROR = 1,
    LOG_WARN = 2,
    LOG_INFO = 3,
    LOG_DEBUG = 4
} log_level_t;

static FILE* g_log_file = NULL;
static log_level_t g_current_log_level = LOG_INFO;
```

### 10.2 Logging Implementation

```c
void miningshim_log(log_level_t level, const char* format, ...) {
    if (level > g_current_log_level) return;
    
    const char* level_str[] = {"NONE", "ERROR", "WARN", "INFO", "DEBUG"};
    
    // Format timestamp
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    
    // Write to log file
    if (g_log_file) {
        fprintf(g_log_file, "[%lu.%09lu] [%s] [SHIM:%u] ",
                ts.tv_sec, ts.tv_nsec, level_str[level], g_config.agent_id);
        
        va_list args;
        va_start(args, format);
        vfprintf(g_log_file, format, args);
        va_end(args);
        
        fprintf(g_log_file, "\n");
        fflush(g_log_file);
    }
    
    // Also write errors/warnings to stderr
    if (level <= LOG_WARN) {
        fprintf(stderr, "[MININGSHIM:%u] [%s] ", g_config.agent_id, level_str[level]);
        va_list args;
        va_start(args, format);
        vfprintf(stderr, format, args);
        va_end(args);
        fprintf(stderr, "\n");
    }
}

void initialize_logging(void) {
    g_log_file = fopen(g_config.log_file_path, "w");
    if (!g_log_file) {
        fprintf(stderr, "[MININGSHIM] Failed to open log file: %s\n", 
                g_config.log_file_path);
        g_log_file = stderr;
    }
    g_current_log_level = g_config.log_level;
}
```

## 11.0 Build System

### 11.1 Compilation

```makefile
# Makefile for libminingshim.so

CC = gcc
CFLAGS = -Wall -Wextra -fPIC -O2 -DNDEBUG
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

.PHONY: all install clean
```

### 11.2 Build Commands

```bash
# Development build with debug symbols
gcc -shared -fPIC -g -O0 -o libminingshim.so libminingshim.c \
    -lpthread -lm -ldl -DDEBUG

# Production build
gcc -shared -fPIC -O2 -DNDEBUG -o libminingshim.so libminingshim.c \
    -lpthread -lm -ldl

# Install system-wide
sudo cp libminingshim.so /usr/local/lib/
sudo ldconfig
```

## 12.0 Testing Strategy

### 12.1 Unit Testing

```c
// Test deterministic behavior
void test_deterministic_prng(void) {
    // Initialize with same seed
    setenv("SIMULATION_SEED", "12345", 1);
    setenv("AGENT_ID", "1", 1);
    initialize_deterministic_prng();
    
    double values1[100];
    for (int i = 0; i < 100; i++) {
        values1[i] = get_deterministic_random();
    }
    
    // Reinitialize with same seed
    initialize_deterministic_prng();
    
    double values2[100];
    for (int i = 0; i < 100; i++) {
        values2[i] = get_deterministic_random();
    }
    
    // Verify identical sequences
    for (int i = 0; i < 100; i++) {
        assert(values1[i] == values2[i]);
    }
}

// Test exponential distribution properties
void test_exponential_distribution(void) {
    const int num_samples = 10000;
    const uint64_t hashrate = 1000000;  // 1 MH/s
    const uint64_t difficulty = 1000000;
    const double expected_lambda = (double)hashrate / difficulty;
    
    uint64_t times[num_samples];
    for (int i = 0; i < num_samples; i++) {
        times[i] = calculate_block_discovery_time(hashrate, difficulty);
    }
    
    // Calculate mean
    double mean = 0;
    for (int i = 0; i < num_samples; i++) {
        mean += times[i] / 1e9;  // Convert to seconds
    }
    mean /= num_samples;
    
    double expected_mean = 1.0 / expected_lambda;
    
    // Mean should be within 5% of expected for large sample
    assert(fabs(mean - expected_mean) < expected_mean * 0.05);
}
```

### 12.2 Integration Testing

```bash
#!/bin/bash
# Test shim with monerod in Shadow

# Build shim
make clean && make

# Create test Shadow configuration
cat > test_shadow.yaml <<EOF
general:
  stop_time: 300s
  
network:
  graph:
    type: gml
    inline: |
      graph [
        node [ id 0 bandwidth_down "1 Gbit" bandwidth_up "1 Gbit" ]
      ]

hosts:
  miner001:
    network_node_id: 0
    processes:
      - path: /usr/local/bin/monerod
        args: "--data-dir /tmp/test_miner --start-mining <test_wallet>"
        environment:
          LD_PRELOAD: ./libminingshim.so
          MINER_HASHRATE: "1000000"
          AGENT_ID: "1"
          SIMULATION_SEED: "12345"
          MININGSHIM_LOG_LEVEL: "DEBUG"
EOF

# Run simulation
shadow test_shadow.yaml

# Verify outputs
test -f /tmp/miningshim_metrics_agent1.json || exit 1
test -f /tmp/miningshim_agent1.log || exit 1

echo "Integration test passed"
```

### 12.3 Reproducibility Testing

```bash
#!/bin/bash
# Verify deterministic behavior across runs

SEED=99999

# Run simulation twice with same seed
for run in 1 2; do
    rm -rf /tmp/test_run_$run
    mkdir -p /tmp/test_run_$run
    
    SIMULATION_SEED=$SEED \
    AGENT_ID=1 \
    MINER_HASHRATE=1000000 \
    MININGSHIM_LOG_FILE=/tmp/test_run_$run/shim.log \
    shadow test_config.yaml
    
    cp /tmp/miningshim_metrics_agent1.json /tmp/test_run_$run/metrics.json
done

# Compare results
diff /tmp/test_run_1/metrics.json /tmp/test_run_2/metrics.json
if [ $? -eq 0 ]; then
    echo "Reproducibility test PASSED: identical results"
else
    echo "Reproducibility test FAILED: different results"
    exit 1
fi
```

## 13.0 Deployment Integration

### 13.1 Monerosim Configuration Generation

The Rust configuration tool generates Shadow YAML with shim integration:

```rust
// In src/process/daemon.rs or similar
pub fn generate_miner_process(agent: &UserAgent, config: &Config) -> ShadowProcess {
    let mut environment = HashMap::new();
    
    // Inject mining shim via LD_PRELOAD
    environment.insert(
        "LD_PRELOAD".to_string(),
        "./mining_shim/libminingshim.so".to_string()
    );
    
    // Configure shim parameters
    if let Some(hashrate) = agent.attributes.get("hashrate") {
        environment.insert("MINER_HASHRATE".to_string(), hashrate.clone());
    }
    
    environment.insert("AGENT_ID".to_string(), agent.id.to_string());
    environment.insert("SIMULATION_SEED".to_string(), config.general.simulation_seed.to_string());
    environment.insert("MININGSHIM_LOG_LEVEL".to_string(), "INFO".to_string());
    
    ShadowProcess {
        path: "/usr/local/bin/monerod".to_string(),
        args: format!("--data-dir /tmp/miner{} --start-mining {}", 
                     agent.id, agent.wallet_address),
        environment,
        start_time: "0s".to_string(),
    }
}
```

### 13.2 Validation

```rust
pub fn validate_mining_shim_config(config: &Config) -> Result<(), String> {
    // Check if shim library exists
    if !Path::new("./mining_shim/libminingshim.so").exists() {
        return Err("Mining shim library not found: ./mining_shim/libminingshim.so".to_string());
    }
    
    // Validate simulation seed is set
    if config.general.simulation_seed == 0 {
        return Err("SIMULATION_SEED must be non-zero for deterministic mining".to_string());
    }
    
    // Validate all miners have hashrate configured
    for agent in &config.agents.user_agents {
        if agent.attributes.get("is_miner") == Some(&"true".to_string()) {
            if agent.attributes.get("hashrate").is_none() {
                return Err(format!("Miner agent {} missing hashrate attribute", agent.id));
            }
        }
    }
    
    Ok(())
}
```

## 14.0 Error Handling

### 14.1 Graceful Degradation

```c
// Handle missing function symbols gracefully
void* get_monerod_function(const char* symbol_name) {
    void* func = dlsym(RTLD_NEXT, symbol_name);
    if (!func) {
        miningshim_log(LOG_WARN, "Function not found in monerod: %s", symbol_name);
        miningshim_log(LOG_WARN, "This may indicate version incompatibility");
    }
    return func;
}

// Validate shim can operate in current environment
bool validate_shim_environment(void) {
    bool valid = true;
    
    // Check required monerod functions exist
    const char* required_functions[] = {
        "start_mining",
        "stop_mining",
        "handle_new_block_notify",
        NULL
    };
    
    for (int i = 0; required_functions[i] != NULL; i++) {
        if (!get_monerod_function(required_functions[i])) {
            miningshim_log(LOG_ERROR, "Required function missing: %s", 
                          required_functions[i]);
            valid = false;
        }
    }
    
    return valid;
}
```

### 14.2 Runtime Error Recovery

```c
// Attempt recovery from mining errors
void handle_mining_error(const char* error_context) {
    miningshim_log(LOG_ERROR, "Mining error: %s", error_context);
    g_metrics.mining_errors++;
    
    // Stop mining gracefully
    pthread_mutex_lock(&g_mining_state.state_mutex);
    if (g_mining_state.is_mining) {
        g_mining_state.is_mining = false;
        pthread_cond_signal(&g_mining_state.state_cond);
    }
    pthread_mutex_unlock(&g_mining_state.state_mutex);
    
    // Export error metrics
    export_metrics_to_file("/tmp/miningshim_error_metrics.json");
}
```

## 15.0 Future Enhancements

### 15.1 Planned Extensions

While this specification focuses on core mining simulation, the architecture supports future enhancements:

1. **Variable Difficulty**: Support dynamic difficulty adjustments during simulation
2. **Pool Mining**: Simulate mining pool mechanics with reward distribution
3. **Hardware Variance**: Model different mining hardware characteristics
4. **Network Latency Effects**: Account for propagation delays in mining competition

### 15.2 Extensibility Points

The shim provides clean extension points:

```c
// Hook for custom mining behavior
typedef void (*mining_extension_hook_t)(mining_event_t* event);

void register_mining_extension(mining_extension_hook_t hook) {
    // Allow external modules to hook into mining events
    g_extension_hooks[g_num_extensions++] = hook;
}
```

## 16.0 Summary

This specification defines a **focused, production-ready mining shim** that:

✅ **Intercepts** `monerod` mining functions via `LD_PRELOAD`  
✅ **Simulates** mining using exponential distribution probabilistic model  
✅ **Guarantees** deterministic behavior through careful PRNG seeding  
✅ **Integrates** seamlessly with Shadow discrete-event simulator  
✅ **Provides** comprehensive logging and metrics for analysis  
✅ **Handles** errors gracefully with clear diagnostics  

The shim replaces computationally expensive Proof-of-Work calculations while maintaining protocol authenticity, enabling large-scale Monero network simulations suitable for research and protocol development.

**Implementation Priority**: This specification provides sufficient detail for immediate development of the core mining shim, with extension points for future enhancements as needed.