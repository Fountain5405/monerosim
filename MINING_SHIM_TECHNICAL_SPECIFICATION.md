# Technical Specification: Neutral Passthrough Mining Shim for Monerosim

## 1.0 Architecture Overview

### 1.1 Design Philosophy

This specification defines a neutral passthrough shim layer that operates as a transparent interface mechanism without any embedded logic for distinguishing or handling behavioral classifications. The shim serves as a pure conduit between Monero daemon operations and external strategy agents, delegating all behavioral decisions to higher-level components.

### 1.2 System Context

```
┌─────────────────────────────────────────────────────────────────┐
│                    Monerosim Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│  Strategy Agents (Python)                                  │
│  ├── Honest Mining Strategy                                 │
│  ├── Selfish Mining Strategy                                │
│  └── Custom Strategy Implementations                        │
├─────────────────────────────────────────────────────────────────┤
│  Neutral Passthrough Shim (libminingshim.so)               │
│  ├── Request Interception Layer                             │
│  ├── Transparent Forwarding Engine                          │
│  └── Response Passthrough Interface                          │
├─────────────────────────────────────────────────────────────────┤
│  Monero Daemon (monerod)                                  │
│  ├── Mining Function Hooks                                   │
│  ├── Block Creation Interface                               │
│  └── P2P Network Layer                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Core Principles

1. **Neutrality**: The shim contains no behavioral logic or classification mechanisms
2. **Transparency**: All requests and responses pass through without modification
3. **Statelessness**: The shim maintains no persistent state between operations
4. **Extensibility**: Interface supports future strategy implementations without shim modifications

## 2.0 Core Functionality

### 2.1 Transparent Interface Layer

The shim provides a transparent interface that:

- Accepts incoming requests without inspecting or classifying their intent
- Forwards all requests to the appropriate destination without modification
- Returns responses without applying any behavioral filtering or transformation
- Maintains consistent performance characteristics regardless of request type

### 2.2 Request Processing Pipeline

```
Incoming Request → Validation → Forwarding → Response → Passthrough
     ↓                ↓           ↓          ↓
  Neutral          Neutral     Neutral    Neutral
Interception      Forwarding   Return      Delivery
```

### 2.3 Operation Modes

The shim supports two operational modes:

1. **Passthrough Mode**: Default mode where all operations are transparently forwarded
2. **Monitoring Mode**: Optional mode for logging and metrics collection without behavioral interference

## 3.0 Interface Requirements

### 3.1 Standardized Request Objects

```c
typedef struct mining_request {
    uint32_t request_id;
    char* request_type;
    void* request_data;
    size_t data_size;
    uint64_t timestamp;
} mining_request_t;
```

### 3.2 Standardized Response Objects

```c
typedef struct mining_response {
    uint32_t request_id;
    int status_code;
    char* status_message;
    void* response_data;
    size_t response_size;
    uint64_t timestamp;
} mining_response_t;
```

### 3.3 Core Interface Functions

```c
// Initialize shim with configuration
int miningshim_init(const shim_config_t* config);

// Process incoming request neutrally
int miningshim_process_request(const mining_request_t* request, 
                           mining_response_t* response);

// Cleanup shim resources
void miningshim_cleanup(void);

// Get shim status and metrics
int miningshim_get_status(shim_status_t* status);
```

### 3.4 Asynchronous Operation Support

```c
typedef struct async_request_context {
    mining_request_t request;
    void (*completion_callback)(const mining_response_t* response);
    void* user_data;
    uint32_t timeout_ms;
} async_request_context_t;

// Submit asynchronous request
int miningshim_submit_async(const async_request_context_t* context);
```

### 3.5 Error Handling and Timeout Mechanisms

```c
typedef enum shim_error_code {
    SHIM_SUCCESS = 0,
    SHIM_ERROR_INVALID_REQUEST = 1,
    SHIM_ERROR_TIMEOUT = 2,
    SHIM_ERROR_RESOURCE_UNAVAILABLE = 3,
    SHIM_ERROR_FORWARDING_FAILED = 4
} shim_error_code_t;

// Error handling with retry policy
typedef struct retry_policy {
    uint32_t max_retries;
    uint32_t base_delay_ms;
    uint32_t max_delay_ms;
    float backoff_multiplier;
} retry_policy_t;
```

## 4.0 Implementation Constraints

### 4.1 Behavioral Neutrality Requirements

The shim implementation must:

- Contain no conditional logic based on behavioral characteristics or intent classification
- Avoid any hardcoded assumptions about request types or patterns
- Implement logging and monitoring hooks without behavioral interpretation
- Maintain stateless operation where possible to ensure scalability

### 4.2 Dependency Injection Requirements

```c
typedef struct shim_dependencies {
    void* (*request_forwarder)(const mining_request_t* request);
    int (*response_handler)(const mining_response_t* response);
    void* (*logger)(const char* message, int level);
    void* (*metrics_collector)(const char* metric_name, double value);
} shim_dependencies_t;

// Initialize with injected dependencies
int miningshim_init_with_deps(const shim_config_t* config,
                             const shim_dependencies_t* deps);
```

### 4.3 Memory Management Constraints

- All memory allocations must be tracked and properly freed
- No memory leaks permitted in long-running simulations
- Implement bounded memory usage with configurable limits
- Use memory pools for frequent allocations

### 4.4 Thread Safety Requirements

- All public interfaces must be thread-safe
- Use lock-free data structures where possible
- Implement proper synchronization for shared resources
- Minimize lock contention for high-throughput scenarios

## 5.0 Configuration

### 5.1 Externalized Configuration Structure

```c
typedef struct shim_config {
    // Routing destinations
    char* monerod_library_path;
    char* strategy_agent_socket_path;
    
    // Timeout values and retry policies
    uint32_t default_timeout_ms;
    uint32_t max_concurrent_requests;
    retry_policy_t retry_policy;
    
    // Logging levels and output formats
    enum log_level {
        LOG_NONE = 0,
        LOG_ERROR = 1,
        LOG_WARN = 2,
        LOG_INFO = 3,
        LOG_DEBUG = 4
    } log_level;
    
    char* log_file_path;
    bool log_to_stdout;
    
    // Resource limits and throttling parameters
    uint32_t max_memory_mb;
    uint32_t max_requests_per_second;
    uint32_t queue_depth;
    
    // Performance tuning parameters
    bool enable_monitoring_mode;
    uint32_t metrics_collection_interval_ms;
    bool enable_performance_profiling;
} shim_config_t;
```

### 5.2 Configuration File Format

```yaml
# miningshim.yaml
routing:
  monerod_library_path: "/usr/local/lib/libmonerod.so"
  strategy_agent_socket_path: "/tmp/miningshim_strategy.sock"

timeouts:
  default_timeout_ms: 5000
  max_concurrent_requests: 100
  retry_policy:
    max_retries: 3
    base_delay_ms: 100
    max_delay_ms: 5000
    backoff_multiplier: 2.0

logging:
  level: "INFO"
  file_path: "/var/log/miningshim.log"
  log_to_stdout: true

resources:
  max_memory_mb: 512
  max_requests_per_second: 1000
  queue_depth: 10000

performance:
  enable_monitoring_mode: false
  metrics_collection_interval_ms: 1000
  enable_performance_profiling: false
```

## 6.0 Testing Requirements

### 6.1 Unit Testing Specifications

#### 6.1.1 Neutral Passthrough Behavior Tests

```c
// Test that all requests pass through unchanged
void test_neutral_passthrough_behavior() {
    // Setup mock dependencies
    mock_dependencies_t mocks = setup_mock_dependencies();
    
    // Test various request types
    mining_request_t requests[] = {
        create_mining_request(),
        create_block_request(),
        create_transaction_request(),
        create_network_request()
    };
    
    for (int i = 0; i < sizeof(requests)/sizeof(requests[0]); i++) {
        mining_response_t response;
        
        // Process request through shim
        int result = miningshim_process_request(&requests[i], &response);
        
        // Verify neutral behavior
        assert(result == SHIM_SUCCESS);
        assert(response.request_id == requests[i].request_id);
        assert(response.status_code == MOCK_SUCCESS_CODE);
        assert(memcmp(response.response_data, requests[i].request_data, 
                   requests[i].data_size) == 0);
    }
    
    cleanup_mock_dependencies(&mocks);
}
```

#### 6.1.2 Performance Characterization Tests

```c
// Test consistent performance regardless of request type
void test_performance_characteristics() {
    const char* request_types[] = {"mining", "block", "transaction", "network"};
    const int num_types = sizeof(request_types)/sizeof(request_types[0]);
    
    uint64_t latencies[num_types];
    uint64_t throughputs[num_types];
    
    for (int i = 0; i < num_types; i++) {
        // Measure latency and throughput for each request type
        measure_performance(request_types[i], &latencies[i], &throughputs[i]);
    }
    
    // Verify performance consistency (within 10% variance)
    uint64_t avg_latency = calculate_average(latencies, num_types);
    uint64_t avg_throughput = calculate_average(throughputs, num_types);
    
    for (int i = 0; i < num_types; i++) {
        assert(abs(latencies[i] - avg_latency) < avg_latency * 0.1);
        assert(abs(throughputs[i] - avg_throughput) < avg_throughput * 0.1);
    }
}
```

### 6.2 Integration Testing Requirements

#### 6.2.1 Shadow Integration Tests

```python
# Integration test with Shadow simulator
def test_shadow_integration():
    # Configure shim for Shadow environment
    shim_config = create_shadow_shim_config()
    
    # Start Shadow simulation with shim
    shadow_process = start_shadow_with_shim(shim_config)
    
    # Verify neutral behavior in simulation
    for agent_type in ["miner", "user", "controller"]:
        agent = create_test_agent(agent_type)
        response = agent.send_request_through_shim(test_request)
        
        assert response.is_neutral_passthrough()
        assert response.preserves_original_intent()
    
    # Cleanup
    shadow_process.terminate()
```

#### 6.2.2 Strategy Agent Integration Tests

```python
# Test integration with various strategy agents
def test_strategy_agent_integration():
    strategies = ["honest", "selfish", "custom"]
    
    for strategy in strategies:
        # Start strategy agent
        strategy_agent = start_strategy_agent(strategy)
        
        # Configure shim with strategy agent socket
        shim_config = create_shim_config_with_strategy(strategy_agent.socket_path)
        shim = MiningShim(shim_config)
        
        # Test that shim correctly forwards to strategy agent
        test_requests = generate_various_requests()
        for request in test_requests:
            response = shim.process_request(request)
            strategy_response = strategy_agent.get_last_response()
            
            assert response.matches_strategy_response(strategy_response)
        
        # Cleanup
        strategy_agent.stop()
        shim.cleanup()
```

### 6.3 Performance Testing Requirements

#### 6.3.1 Latency and Throughput Benchmarks

```c
// Performance benchmark suite
typedef struct performance_metrics {
    uint64_t avg_latency_ns;
    uint64_t p95_latency_ns;
    uint64_t p99_latency_ns;
    uint64_t requests_per_second;
    uint64_t memory_usage_mb;
    double cpu_usage_percent;
} performance_metrics_t;

void run_performance_benchmark(performance_metrics_t* metrics) {
    const int test_duration_seconds = 60;
    const int target_rps = 1000;
    
    // Setup performance monitoring
    performance_monitor_t monitor = setup_performance_monitor();
    
    // Run benchmark
    benchmark_result_t result = run_load_test(target_rps, test_duration_seconds);
    
    // Collect metrics
    metrics->avg_latency_ns = result.avg_latency_ns;
    metrics->p95_latency_ns = result.p95_latency_ns;
    metrics->p99_latency_ns = result.p99_latency_ns;
    metrics->requests_per_second = result.actual_rps;
    metrics->memory_usage_mb = monitor.peak_memory_mb;
    metrics->cpu_usage_percent = monitor.avg_cpu_percent;
    
    cleanup_performance_monitor(&monitor);
}
```

#### 6.3.2 Scalability Testing

```c
// Test scalability under increasing load
void test_scalability() {
    const int load_levels[] = {100, 500, 1000, 5000, 10000};
    const int num_levels = sizeof(load_levels)/sizeof(load_levels[0]);
    
    for (int i = 0; i < num_levels; i++) {
        printf("Testing load level: %d RPS\n", load_levels[i]);
        
        performance_metrics_t metrics;
        run_scalability_test(load_levels[i], &metrics);
        
        // Verify linear scalability characteristics
        assert(metrics.avg_latency_ns < 1000000); // < 1ms average
        assert(metrics.memory_usage_mb < 1024); // < 1GB memory
        assert(metrics.cpu_usage_percent < 80.0); // < 80% CPU
        
        printf("  Latency: %lu ns, Memory: %lu MB, CPU: %.1f%%\n",
               metrics.avg_latency_ns, metrics.memory_usage_mb, metrics.cpu_usage_percent);
    }
}
```

### 6.4 Error Handling Tests

#### 6.4.1 Failure Scenario Testing

```c
// Test various failure scenarios
void test_error_handling() {
    error_scenario_t scenarios[] = {
        {"timeout", create_timeout_scenario()},
        {"resource_exhaustion", create_resource_exhaustion_scenario()},
        {"network_failure", create_network_failure_scenario()},
        {"invalid_request", create_invalid_request_scenario()},
        {"dependency_failure", create_dependency_failure_scenario()}
    };
    
    for (int i = 0; i < sizeof(scenarios)/sizeof(scenarios[0]); i++) {
        printf("Testing error scenario: %s\n", scenarios[i].name);
        
        // Setup error injection
        setup_error_scenario(&scenarios[i]);
        
        // Test shim behavior under error conditions
        mining_request_t request = create_standard_request();
        mining_response_t response;
        
        int result = miningshim_process_request(&request, &response);
        
        // Verify proper error handling
        assert(result == SHIM_ERROR_TIMEOUT || 
               result == SHIM_ERROR_RESOURCE_UNAVAILABLE ||
               result == SHIM_ERROR_FORWARDING_FAILED);
        
        // Verify error information is preserved
        assert(response.status_code != SHIM_SUCCESS);
        assert(response.status_message != NULL);
        
        // Cleanup error scenario
        cleanup_error_scenario(&scenarios[i]);
    }
}
```

## 7.0 Example Implementation

### 7.1 Basic Shim Structure

```c
// libminingshim.c - Neutral passthrough implementation
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <errno.h>

// Configuration and state
static shim_config_t g_config = {0};
static shim_dependencies_t g_deps = {0};
static pthread_mutex_t g_config_mutex = PTHREAD_MUTEX_INITIALIZER;

// Original function pointers
static int (*original_start_mining)(const char* address, int threads) = NULL;
static int (*original_stop_mining)(void) = NULL;
static int (*original_handle_block)(const void* block_data) = NULL;

// Initialize shim
__attribute__((constructor))
void libminingshim_init() {
    // Load configuration from environment or file
    load_shim_config(&g_config);
    
    // Resolve original functions
    original_start_mining = dlsym(RTLD_NEXT, "start_mining");
    original_stop_mining = dlsym(RTLD_NEXT, "stop_mining");
    original_handle_block = dlsym(RTLD_NEXT, "handle_block");
    
    // Initialize monitoring if enabled
    if (g_config.enable_monitoring_mode) {
        init_monitoring(&g_config);
    }
}

// Neutral request forwarding function
static int forward_request_neutrally(const mining_request_t* request,
                                  mining_response_t* response) {
    // No behavioral classification - transparent forwarding
    if (g_deps.request_forwarder) {
        return g_deps.request_forwarder(request);
    }
    
    // Default forwarding behavior
    return forward_to_monerod(request, response);
}

// Intercepted start_mining function
int start_mining(const char* address, int threads) {
    // Create neutral request
    mining_request_t request = {
        .request_id = generate_request_id(),
        .request_type = "start_mining",
        .request_data = (void*)address,
        .data_size = strlen(address) + 1,
        .timestamp = get_current_timestamp_ns()
    };
    
    mining_response_t response;
    
    // Forward neutrally without behavioral interpretation
    int result = forward_request_neutrally(&request, &response);
    
    if (result == SHIM_SUCCESS && response.status_code == SHIM_SUCCESS) {
        // Call original function if forwarding succeeded
        if (original_start_mining) {
            return original_start_mining(address, threads);
        }
    }
    
    return -1; // Forwarding failed
}

// Intercepted stop_mining function
int stop_mining(void) {
    // Create neutral request
    mining_request_t request = {
        .request_id = generate_request_id(),
        .request_type = "stop_mining",
        .request_data = NULL,
        .data_size = 0,
        .timestamp = get_current_timestamp_ns()
    };
    
    mining_response_t response;
    
    // Forward neutrally without behavioral interpretation
    int result = forward_request_neutrally(&request, &response);
    
    if (result == SHIM_SUCCESS && response.status_code == SHIM_SUCCESS) {
        // Call original function if forwarding succeeded
        if (original_stop_mining) {
            return original_stop_mining();
        }
    }
    
    return -1; // Forwarding failed
}

// Public API functions
int miningshim_init(const shim_config_t* config) {
    pthread_mutex_lock(&g_config_mutex);
    
    // Validate configuration
    if (validate_config(config) != SHIM_SUCCESS) {
        pthread_mutex_unlock(&g_config_mutex);
        return SHIM_ERROR_INVALID_CONFIG;
    }
    
    // Copy configuration
    memcpy(&g_config, config, sizeof(shim_config_t));
    
    pthread_mutex_unlock(&g_config_mutex);
    return SHIM_SUCCESS;
}

int miningshim_process_request(const mining_request_t* request,
                           mining_response_t* response) {
    // Validate inputs
    if (!request || !response) {
        return SHIM_ERROR_INVALID_REQUEST;
    }
    
    // Log request if monitoring enabled
    if (g_config.enable_monitoring_mode) {
        log_request(request);
    }
    
    // Forward request neutrally
    return forward_request_neutrally(request, response);
}

void miningshim_cleanup(void) {
    pthread_mutex_lock(&g_config_mutex);
    
    // Cleanup monitoring
    if (g_config.enable_monitoring_mode) {
        cleanup_monitoring();
    }
    
    // Reset configuration
    memset(&g_config, 0, sizeof(shim_config_t));
    
    pthread_mutex_unlock(&g_config_mutex);
}
```

### 7.2 Integration with Shadow Configuration

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
          MININGSHIM_CONFIG: "/etc/miningshim.yaml"
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

## 8.0 Deployment and Usage

### 8.1 Build Requirements

```bash
# Build the shim library
gcc -shared -fPIC -o libminingshim.so \
    libminingshim.c \
    -ldl -lpthread \
    -O2 -DNDEBUG

# Install to system location
sudo cp libminingshim.so /usr/local/lib/
sudo ldconfig
```

### 8.2 Configuration Deployment

```bash
# Install configuration file
sudo cp miningshim.yaml /etc/miningshim.yaml

# Set appropriate permissions
sudo chmod 644 /etc/miningshim.yaml
sudo chmod 755 /usr/local/lib/libminingshim.so
```

### 8.3 Integration with Monerosim

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
        
        # Register strategy with shim
        self.register_strategy_with_shim()
        
    def run_iteration(self):
        # Receive mining events from shim
        mining_event = self.shim_connection.receive_event()
        
        # Apply strategy logic
        if self.strategy == "honest":
            return self.handle_honest_mining(mining_event)
        elif self.strategy == "selfish":
            return self.handle_selfish_mining(mining_event)
        else:
            return self.handle_custom_mining(mining_event)
```

## 9.0 Monitoring and Observability

### 9.1 Metrics Collection

```c
typedef struct shim_metrics {
    uint64_t total_requests_processed;
    uint64_t total_forwarding_errors;
    uint64_t average_latency_ns;
    uint64_t peak_memory_usage_bytes;
    uint32_t active_connections;
    uint64_t uptime_seconds;
} shim_metrics_t;

// Metrics collection interface
int miningshim_get_metrics(shim_metrics_t* metrics);
void miningshim_reset_metrics(void);
```

### 9.2 Logging Interface

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

### 9.3 Performance Profiling

```c
// Performance profiling hooks
typedef struct profile_entry {
    char function_name[64];
    uint64_t execution_count;
    uint64_t total_time_ns;
    uint64_t min_time_ns;
    uint64_t max_time_ns;
} profile_entry_t;

// Profiling interface
void miningshim_start_profiling(void);
void miningshim_stop_profiling(void);
int miningshim_get_profile_data(profile_entry_t* entries, int max_entries);
```

## 10.0 Security Considerations

### 10.1 Input Validation

- All input parameters must be validated for type and range
- Buffer overflow protection for all string inputs
- Memory bounds checking for array operations
- Validation of configuration file permissions and integrity

### 10.2 Resource Protection

- Implement resource usage limits to prevent DoS
- Use bounded queues and memory pools
- Implement proper cleanup on error conditions
- Protect against privilege escalation attacks

### 10.3 Communication Security

- Validate socket connections and permissions
- Implement proper authentication for strategy agents
- Use secure IPC mechanisms for inter-process communication
- Log all access attempts and failures

## 11.0 Conclusion

This technical specification defines a neutral passthrough mining shim that provides a transparent interface layer for Monerosim mining operations. The shim maintains complete behavioral neutrality while enabling sophisticated strategy implementations through external agents.

Key design principles:
- **Neutrality**: No embedded behavioral logic or classification
- **Transparency**: All operations pass through unchanged
- **Extensibility**: Support for arbitrary strategy implementations
- **Performance**: Minimal overhead and consistent characteristics
- **Reliability**: Robust error handling and resource management

The specification provides comprehensive implementation guidance including detailed function signatures, data structures, testing requirements, and deployment procedures suitable for immediate development by automated systems.