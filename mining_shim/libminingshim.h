#ifndef MINING_SHIM_H
#define MINING_SHIM_H

#include <stdint.h>
#include <stdbool.h>
#include <pthread.h>
#include <stdlib.h>

// Include stdlib for drand48_data
#include <stdlib.h>

// Define our own drand48_data structure to avoid incomplete type issues
typedef struct {
    unsigned short int __x[3];    /* Current state.  */
    unsigned short int __old_x[3]; /* Old state.  */
    unsigned short int __c;       /* Additive const. in congruential formula.  */
    unsigned short int __init;    /* Flag for initializing.  */
    unsigned long long int __a;   /* Factor in congruential formula.  */
} drand48_data_t;

// Log levels
typedef enum log_level {
    LOG_NONE = 0,
    LOG_ERROR = 1,
    LOG_WARN = 2,
    LOG_INFO = 3,
    LOG_DEBUG = 4
} log_level_t;

// Configuration structure
typedef struct shim_config {
    uint64_t miner_hashrate;        // MINER_HASHRATE
    uint32_t agent_id;              // AGENT_ID
    uint64_t simulation_seed;       // SIMULATION_SEED
    log_level_t log_level;          // MININGSHIM_LOG_LEVEL
    char log_file_path[256];        // MININGSHIM_LOG_FILE
} shim_config_t;

// PRNG state (thread-safe)
typedef struct prng_state {
    drand48_data_t buffer;
    uint64_t global_seed;
    uint32_t agent_id;
    uint64_t agent_seed;
    pthread_mutex_t prng_mutex;
} prng_state_t;

// Mining state
typedef struct mining_state {
    bool is_mining;
    pthread_t mining_thread;
    pthread_mutex_t state_mutex;
    pthread_cond_t state_cond;
    void* miner_context;
} mining_state_t;

// Difficulty tracker
typedef struct difficulty_tracker {
    uint64_t current_difficulty;
    uint64_t last_update_height;
    pthread_mutex_t difficulty_mutex;
} difficulty_tracker_t;

// Metrics structure
typedef struct shim_metrics {
    uint64_t blocks_found;
    uint64_t mining_iterations;
    uint64_t peer_blocks_received;
    uint64_t mining_start_time;
    uint64_t total_mining_time_ns;
    uint64_t last_block_time_ns;
    uint64_t mining_errors;
} shim_metrics_t;

// Block info structure (simplified for interception)
typedef struct block_info {
    uint64_t height;
    uint64_t difficulty;
    uint64_t timestamp;
} block_info_t;

// Function prototypes

// Configuration and initialization
void load_configuration(void);
void initialize_deterministic_prng(void);
void initialize_logging(void);
void initialize_metrics(void);
void initialize_mining_state(void);
bool is_running_under_shadow(void);
bool validate_shim_environment(void);

// PRNG functions
double get_deterministic_random(void);

// Mining calculations
uint64_t calculate_block_discovery_time(uint64_t hashrate, uint64_t difficulty);
uint32_t generate_deterministic_nonce(void);

// Difficulty tracking
void update_network_difficulty(const block_info_t* new_block);
uint64_t get_current_network_difficulty(void);
uint64_t get_agent_hashrate(void);

// Block creation
void create_and_broadcast_block(void* miner_context);

// Mining loop
void* mining_loop(void* context);

// Logging
void miningshim_log(log_level_t level, const char* format, ...);

// Metrics
void export_metrics_to_file(const char* filepath);

// Error handling
void handle_mining_error(const char* error_context);
void* get_monerod_function(const char* symbol_name);

// Hook function types (matching mining_hooks.h)
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

// Hook registration function types
typedef void (*register_mining_start_hook_t)(mining_start_hook_t hook);
typedef void (*register_mining_stop_hook_t)(mining_stop_hook_t hook);
typedef void (*register_find_nonce_hook_t)(find_nonce_hook_t hook);
typedef void (*register_block_found_hook_t)(block_found_hook_t hook);
typedef void (*register_difficulty_update_hook_t)(difficulty_update_hook_t hook);

// Hook implementations (called by monerod)
bool mining_shim_start_hook(
    void* miner_instance,
    const void* wallet_address,
    uint64_t threads_count,
    bool background_mining,
    bool ignore_battery
);

bool mining_shim_stop_hook(void* miner_instance);

bool mining_shim_find_nonce_hook(
    void* miner_instance,
    void* block_ptr,
    uint64_t difficulty,
    uint64_t height,
    const void* seed_hash,
    uint32_t* nonce_out
);

bool mining_shim_block_found_hook(
    void* miner_instance,
    void* block_ptr,
    uint64_t height
);

void mining_shim_difficulty_update_hook(
    void* miner_instance,
    uint64_t new_difficulty,
    uint64_t height
);

// Global state declarations (defined in .c file)
extern shim_config_t g_config;
extern prng_state_t g_prng_state;
extern mining_state_t g_mining_state;
extern difficulty_tracker_t g_difficulty_tracker;
extern shim_metrics_t g_metrics;

#endif // MINING_SHIM_H