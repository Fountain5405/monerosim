#include "libminingshim.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <time.h>
#include <math.h>
#include <dlfcn.h>
#include <unistd.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <sys/time.h>

// Forward declarations
static uint64_t get_current_time_ns(void);

// Global state
shim_config_t g_config = {0};
prng_state_t g_prng_state = {0};
mining_state_t g_mining_state = {0};
difficulty_tracker_t g_difficulty_tracker = {0};
shim_metrics_t g_metrics = {0};
static FILE* g_log_file = NULL;
static log_level_t g_current_log_level = LOG_INFO;

// Global initialization flag
static bool g_initialized = false;

// Lazy initialization function - called when hooks are first invoked
static void ensure_initialized(void) {
    if (g_initialized) {
        return;
    }

    // Skip initialization in test environment
    if (getenv("MININGSHIM_TEST_MODE")) {
        g_initialized = true;
        return;
    }

    // Check if we're running under Shadow
    bool under_shadow = is_running_under_shadow();
    if (!under_shadow) {
        fprintf(stderr, "[MININGSHIM] WARNING: Not running under Shadow simulator\n");
        fprintf(stderr, "[MININGSHIM] Shim is designed for Shadow environment only\n");
        // Don't exit - allow library to load but skip mining functionality
        g_initialized = true;
        return;
    }

    // Only initialize if we're actually running under Shadow
    load_configuration();
    initialize_deterministic_prng();
    initialize_logging();
    initialize_metrics();
    initialize_mining_state();

    if (!validate_shim_environment()) {
        miningshim_log(LOG_ERROR, "Shim environment validation failed");
        exit(1);
    }

    // Register hooks with monerod using the new hook system
    register_mining_start_hook_t reg_start =
        (register_mining_start_hook_t)dlsym(RTLD_NEXT, "monero_register_mining_start_hook");
    register_mining_stop_hook_t reg_stop =
        (register_mining_stop_hook_t)dlsym(RTLD_NEXT, "monero_register_mining_stop_hook");
    register_find_nonce_hook_t reg_find_nonce =
        (register_find_nonce_hook_t)dlsym(RTLD_NEXT, "monero_register_find_nonce_hook");
    register_block_found_hook_t reg_block_found =
        (register_block_found_hook_t)dlsym(RTLD_NEXT, "monero_register_block_found_hook");
    register_difficulty_update_hook_t reg_difficulty_update =
        (register_difficulty_update_hook_t)dlsym(RTLD_NEXT, "monero_register_difficulty_update_hook");

    if (reg_start && reg_stop && reg_find_nonce && reg_block_found && reg_difficulty_update) {
        reg_start(mining_shim_start_hook);
        reg_stop(mining_shim_stop_hook);
        reg_find_nonce(mining_shim_find_nonce_hook);
        reg_block_found(mining_shim_block_found_hook);
        reg_difficulty_update(mining_shim_difficulty_update_hook);

        miningshim_log(LOG_INFO, "Mining hooks registered successfully with monerod");
    } else {
        miningshim_log(LOG_ERROR, "Failed to find hook registration functions in monerod");
        miningshim_log(LOG_ERROR, "Available functions: start=%p, stop=%p, find_nonce=%p, block_found=%p, difficulty=%p",
                      reg_start, reg_stop, reg_find_nonce, reg_block_found, reg_difficulty_update);
        exit(1);
    }

    miningshim_log(LOG_INFO, "Mining shim initialized successfully");
    g_initialized = true;
}

// Constructor - called when library is loaded (minimal setup only)
void __attribute__((constructor)) shim_initialize(void) {
    // Just mark that we're loaded - actual initialization happens lazily
    miningshim_log(LOG_DEBUG, "Mining shim library loaded");
}

// Destructor - called when library is unloaded
void __attribute__((destructor)) shim_cleanup(void) {
    char metrics_path[512];
    snprintf(metrics_path, sizeof(metrics_path),
             "/tmp/miningshim_metrics_agent%u.json", g_config.agent_id);

    export_metrics_to_file(metrics_path);

    if (g_log_file && g_log_file != stderr) {
        fclose(g_log_file);
    }

    miningshim_log(LOG_INFO, "Mining shim cleanup complete");
}

// Configuration loading
void load_configuration(void) {
    // Required configuration
    const char* hashrate_str = getenv("MINER_HASHRATE");
    const char* agent_id_str = getenv("AGENT_ID");
    const char* seed_str = getenv("SIMULATION_SEED");

    // Log what we found for debugging
    fprintf(stderr, "[MININGSHIM] Loading configuration:\n");
    fprintf(stderr, "  MINER_HASHRATE: %s\n", hashrate_str ? hashrate_str : "MISSING");
    fprintf(stderr, "  AGENT_ID: %s\n", agent_id_str ? agent_id_str : "MISSING");
    fprintf(stderr, "  SIMULATION_SEED: %s\n", seed_str ? seed_str : "MISSING");

    if (!hashrate_str || !agent_id_str || !seed_str) {
        fprintf(stderr, "[MININGSHIM ERROR] Missing required environment variables:\n");
        fprintf(stderr, "  MINER_HASHRATE: %s\n", hashrate_str ? "set" : "MISSING");
        fprintf(stderr, "  AGENT_ID: %s\n", agent_id_str ? "set" : "MISSING");
        fprintf(stderr, "  SIMULATION_SEED: %s\n", seed_str ? "set" : "MISSING");
        // Don't exit - allow library to load but skip mining functionality
        return;
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

// Shadow detection
bool is_running_under_shadow(void) {
    const char* ld_preload = getenv("LD_PRELOAD");
    return ld_preload && (strstr(ld_preload, "libshadow") || strstr(ld_preload, "libminingshim"));
}

// Environment validation
bool validate_shim_environment(void) {
    bool valid = true;

    // Check for actual Monero hash functions (C++ mangled names)
    const char* required_functions[] = {
        "_ZN10cryptonote18get_block_longhashEPKNS_10BlockchainERKNS_5blockERN6crypto4hashEmPKS7_i",  // cryptonote::get_block_longhash
        "_ZN10cryptonote18get_block_longhashEPKNS_10BlockchainERKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEERN6crypto4hashEmiPKSC_i",  // cryptonote::get_block_longhash (blob version)
        NULL
    };

    for (int i = 0; required_functions[i] != NULL; i++) {
        if (!get_monerod_function(required_functions[i])) {
            miningshim_log(LOG_ERROR, "Required function missing: %s",
                          required_functions[i]);
            valid = false;
        }
    }

    // If functions are missing, don't exit - just log and continue
    // This allows the simulation to run even if mining shim can't intercept functions
    if (!valid) {
        miningshim_log(LOG_WARN, "Some mining functions not found - mining shim will be disabled");
        valid = true; // Override to allow continuation
    }

    return valid;
}

// PRNG initialization
void initialize_deterministic_prng(void) {
    g_prng_state.global_seed = g_config.simulation_seed;
    g_prng_state.agent_id = g_config.agent_id;
    g_prng_state.agent_seed = g_prng_state.global_seed + g_prng_state.agent_id;

    srand48_r(g_prng_state.agent_seed, &g_prng_state.buffer);
    pthread_mutex_init(&g_prng_state.prng_mutex, NULL);

    miningshim_log(LOG_INFO, "PRNG initialized: global_seed=%lu, agent_id=%u, agent_seed=%lu",
                   g_prng_state.global_seed,
                   g_prng_state.agent_id,
                   g_prng_state.agent_seed);
}

// Thread-safe random number generation
double get_deterministic_random(void) {
    double result;
    pthread_mutex_lock(&g_prng_state.prng_mutex);
    drand48_r(&g_prng_state.buffer, &result);
    pthread_mutex_unlock(&g_prng_state.prng_mutex);
    return result;
}

// Mining calculations
uint64_t calculate_block_discovery_time(uint64_t hashrate, uint64_t difficulty) {
    double lambda = (double)hashrate / (double)difficulty;

    double u = get_deterministic_random();

    double time_seconds = -log(1.0 - u) / lambda;

    return (uint64_t)(time_seconds * 1e9);  // Convert to nanoseconds
}

uint32_t generate_deterministic_nonce(void) {
    return (uint32_t)(get_deterministic_random() * UINT32_MAX);
}

// Difficulty tracking
void update_network_difficulty(const block_info_t* new_block) {
    pthread_mutex_lock(&g_difficulty_tracker.difficulty_mutex);

    g_difficulty_tracker.current_difficulty = new_block->difficulty;
    g_difficulty_tracker.last_update_height = new_block->height;

    pthread_mutex_unlock(&g_difficulty_tracker.difficulty_mutex);

    g_metrics.peer_blocks_received++;
}

uint64_t get_current_network_difficulty(void) {
    uint64_t difficulty;
    pthread_mutex_lock(&g_difficulty_tracker.difficulty_mutex);
    difficulty = g_difficulty_tracker.current_difficulty;
    pthread_mutex_unlock(&g_difficulty_tracker.difficulty_mutex);
    return difficulty;
}

uint64_t get_agent_hashrate(void) {
    return g_config.miner_hashrate;
}

// Mining status structure
typedef struct mining_status {
    bool is_mining;
    uint64_t current_hashrate;
    uint64_t blocks_found;
    uint64_t mining_start_time;
} mining_status_t;

// Block template structure (simplified for simulation)
typedef struct block_template {
    uint32_t nonce;
    uint64_t timestamp;
    uint32_t version;
    char prev_block_hash[64];  // Hex string
    char merkle_root[64];      // Hex string
    uint64_t difficulty;
    uint32_t height;
} block_template_t;

// Block creation interface
void create_and_broadcast_block(void* miner_context) {
    typedef bool (*create_block_func_t)(void* context, void* block_template);
    create_block_func_t create_block = (create_block_func_t)dlsym(RTLD_NEXT, "create_block");

    if (!create_block) {
        miningshim_log(LOG_ERROR, "Failed to find create_block function in monerod");
        return;
    }

    // Create proper block template structure
    block_template_t block_template;
    memset(&block_template, 0, sizeof(block_template));

    // Set deterministic nonce (simulation doesn't need real PoW)
    block_template.nonce = generate_deterministic_nonce();

    // Set current timestamp
    block_template.timestamp = (uint32_t)(get_current_time_ns() / 1000000000ULL);

    // Set version (typical Monero version)
    block_template.version = 12;

    // Set difficulty from current network state
    block_template.difficulty = get_current_network_difficulty();

    // Height will be set by monerod based on current chain state
    block_template.height = 0;  // Let monerod determine this

    miningshim_log(LOG_DEBUG, "Created block template: nonce=%u, timestamp=%u, difficulty=%lu",
                   block_template.nonce, block_template.timestamp, block_template.difficulty);

    bool success = create_block(miner_context, &block_template);

    if (success) {
        miningshim_log(LOG_INFO, "Block created and broadcasted successfully");
        g_metrics.blocks_found++;
        g_metrics.last_block_time_ns = get_current_time_ns();
    } else {
        miningshim_log(LOG_WARN, "Block creation failed");
        g_metrics.mining_errors++;
    }
}

// Get current time in nanoseconds
uint64_t get_current_time_ns(void) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (uint64_t)tv.tv_sec * 1000000000ULL + tv.tv_usec * 1000ULL;
}

// Mining loop
void* mining_loop(void* context) {
    miningshim_log(LOG_INFO, "Mining loop started");

    pthread_mutex_lock(&g_mining_state.state_mutex);
    while (g_mining_state.is_mining) {
        pthread_mutex_unlock(&g_mining_state.state_mutex);

        uint64_t difficulty = get_current_network_difficulty();
        uint64_t hashrate = get_agent_hashrate();

        uint64_t time_to_block_ns = calculate_block_discovery_time(hashrate, difficulty);

        miningshim_log(LOG_DEBUG, "Mining iteration: difficulty=%lu, hashrate=%lu, time_to_block=%lu ns",
                       difficulty, hashrate, time_to_block_ns);

        struct timespec sleep_duration = {
            .tv_sec = time_to_block_ns / 1000000000ULL,
            .tv_nsec = time_to_block_ns % 1000000000ULL
        };

        pthread_mutex_lock(&g_mining_state.state_mutex);
        if (!g_mining_state.is_mining) {
            pthread_mutex_unlock(&g_mining_state.state_mutex);
            break;
        }

        struct timespec timeout;
        struct timeval tv;
        gettimeofday(&tv, NULL);
        timeout.tv_sec = tv.tv_sec + sleep_duration.tv_sec;
        timeout.tv_nsec = tv.tv_usec * 1000 + sleep_duration.tv_nsec;
        if (timeout.tv_nsec >= 1000000000) {
            timeout.tv_sec++;
            timeout.tv_nsec -= 1000000000;
        }

        int wait_result = pthread_cond_timedwait(
            &g_mining_state.state_cond,
            &g_mining_state.state_mutex,
            &timeout
        );

        if (wait_result == ETIMEDOUT) {
            pthread_mutex_unlock(&g_mining_state.state_mutex);

            miningshim_log(LOG_INFO, "Block found after %lu ns", time_to_block_ns);

            create_and_broadcast_block(context);

            pthread_mutex_lock(&g_mining_state.state_mutex);
        } else if (wait_result == 0) {
            miningshim_log(LOG_DEBUG, "Mining interrupted by peer block");
        } else {
            miningshim_log(LOG_ERROR, "pthread_cond_timedwait error: %d", wait_result);
        }
    }
    pthread_mutex_unlock(&g_mining_state.state_mutex);

    miningshim_log(LOG_INFO, "Mining loop stopped");
    return NULL;
}

// Initialize mining state
void initialize_mining_state(void) {
    memset(&g_mining_state, 0, sizeof(g_mining_state));
    pthread_mutex_init(&g_mining_state.state_mutex, NULL);
    pthread_cond_init(&g_mining_state.state_cond, NULL);

    memset(&g_difficulty_tracker, 0, sizeof(g_difficulty_tracker));
    g_difficulty_tracker.current_difficulty = 1;  // Default difficulty
    pthread_mutex_init(&g_difficulty_tracker.difficulty_mutex, NULL);
}

// Initialize metrics
void initialize_metrics(void) {
    memset(&g_metrics, 0, sizeof(g_metrics));
}

// Initialize logging
void initialize_logging(void) {
    g_log_file = fopen(g_config.log_file_path, "w");
    if (!g_log_file) {
        fprintf(stderr, "[MININGSHIM] Failed to open log file: %s\n",
                g_config.log_file_path);
        g_log_file = stderr;
    }
    g_current_log_level = g_config.log_level;
}

// Logging function
void miningshim_log(log_level_t level, const char* format, ...) {
    if (level > g_current_log_level) return;

    const char* level_str[] = {"NONE", "ERROR", "WARN", "INFO", "DEBUG"};

    struct timeval tv;
    gettimeofday(&tv, NULL);

    if (g_log_file) {
        fprintf(g_log_file, "[%lu.%06lu] [%s] [SHIM:%u] ",
                tv.tv_sec, tv.tv_usec, level_str[level], g_config.agent_id);

        va_list args;
        va_start(args, format);
        vfprintf(g_log_file, format, args);
        va_end(args);

        fprintf(g_log_file, "\n");
        fflush(g_log_file);
    }

    if (level <= LOG_WARN) {
        fprintf(stderr, "[MININGSHIM:%u] [%s] ", g_config.agent_id, level_str[level]);
        va_list args;
        va_start(args, format);
        vfprintf(stderr, format, args);
        va_end(args);
        fprintf(stderr, "\n");
    }
}

// Export metrics
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

    fprintf(fp, "  \"mining_errors\": %lu,\n", g_metrics.mining_errors);
    fprintf(fp, "  \"hashrate\": %lu\n", g_config.miner_hashrate);
    fprintf(fp, "}\n");

    fclose(fp);
    miningshim_log(LOG_INFO, "Metrics exported to %s", filepath);
}

// Error handling
void handle_mining_error(const char* error_context) {
    miningshim_log(LOG_ERROR, "Mining error: %s", error_context);
    g_metrics.mining_errors++;

    pthread_mutex_lock(&g_mining_state.state_mutex);
    if (g_mining_state.is_mining) {
        g_mining_state.is_mining = false;
        pthread_cond_signal(&g_mining_state.state_cond);
    }
    pthread_mutex_unlock(&g_mining_state.state_mutex);

    export_metrics_to_file("/tmp/miningshim_error_metrics.json");
}

void* get_monerod_function(const char* symbol_name) {
    void* func = dlsym(RTLD_NEXT, symbol_name);
    if (!func) {
        miningshim_log(LOG_WARN, "Function not found in monerod: %s", symbol_name);
        miningshim_log(LOG_WARN, "This may indicate version incompatibility");
    }
    return func;
}

// Hook implementations

// Mining start hook - called when monerod starts mining
bool mining_shim_start_hook(
    void* miner_instance,
    const void* wallet_address,
    uint64_t threads_count,
    bool background_mining,
    bool ignore_battery
) {
    ensure_initialized();

    miningshim_log(LOG_INFO, "Mining start hook called: threads=%lu, background=%d",
                   threads_count, background_mining);

    pthread_mutex_lock(&g_mining_state.state_mutex);

    if (g_mining_state.is_mining) {
        miningshim_log(LOG_WARN, "Mining already active, ignoring start request");
        pthread_mutex_unlock(&g_mining_state.state_mutex);
        return true; // Tell monerod we handled it
    }

    g_mining_state.is_mining = true;
    g_mining_state.miner_context = miner_instance;

    // Start mining thread
    int result = pthread_create(&g_mining_state.mining_thread, NULL,
                               mining_loop, miner_instance);

    if (result != 0) {
        miningshim_log(LOG_ERROR, "Failed to create mining thread: %d", result);
        g_mining_state.is_mining = false;
        pthread_mutex_unlock(&g_mining_state.state_mutex);
        return false; // Let monerod handle it
    }

    pthread_mutex_unlock(&g_mining_state.state_mutex);

    g_metrics.mining_start_time = get_current_time_ns();
    miningshim_log(LOG_INFO, "Mining started successfully via hook");

    return true; // Tell monerod we handled it
}

// Mining stop hook - called when monerod stops mining
bool mining_shim_stop_hook(void* miner_instance) {
    miningshim_log(LOG_INFO, "Mining stop hook called");

    pthread_mutex_lock(&g_mining_state.state_mutex);

    if (!g_mining_state.is_mining) {
        miningshim_log(LOG_WARN, "Mining not active, ignoring stop request");
        pthread_mutex_unlock(&g_mining_state.state_mutex);
        return true; // Tell monerod we handled it
    }

    // Signal mining thread to stop
    g_mining_state.is_mining = false;
    pthread_cond_signal(&g_mining_state.state_cond);
    pthread_mutex_unlock(&g_mining_state.state_mutex);

    // Wait for mining thread to finish
    pthread_join(g_mining_state.mining_thread, NULL);

    g_metrics.total_mining_time_ns = get_current_time_ns() - g_metrics.mining_start_time;
    miningshim_log(LOG_INFO, "Mining stopped successfully via hook");

    return true; // Tell monerod we handled it
}

// Find nonce hook - called when monerod needs to find a nonce
bool mining_shim_find_nonce_hook(
    void* miner_instance,
    void* block_ptr,
    uint64_t difficulty,
    uint64_t height,
    const void* seed_hash,
    uint32_t* nonce_out
) {
    miningshim_log(LOG_DEBUG, "Find nonce hook called: height=%lu, difficulty=%lu",
                   height, difficulty);

    // Generate deterministic nonce for simulation
    *nonce_out = generate_deterministic_nonce();

    miningshim_log(LOG_DEBUG, "Generated nonce: %u", *nonce_out);

    return true; // Tell monerod we found a nonce
}

// Block found hook - called when monerod finds a block
bool mining_shim_block_found_hook(
    void* miner_instance,
    void* block_ptr,
    uint64_t height
) {
    miningshim_log(LOG_INFO, "Block found hook called: height=%lu", height);

    g_metrics.blocks_found++;
    g_metrics.last_block_time_ns = get_current_time_ns();

    // The mining loop will handle the actual block creation and broadcasting
    // This hook is just for notification

    return true; // Tell monerod we handled the notification
}

// Difficulty update hook - called when network difficulty changes
void mining_shim_difficulty_update_hook(
    void* miner_instance,
    uint64_t new_difficulty,
    uint64_t height
) {
    miningshim_log(LOG_DEBUG, "Difficulty update hook called: height=%lu, difficulty=%lu",
                   height, new_difficulty);

    update_network_difficulty(&(block_info_t){height, new_difficulty, 0});

    // Interrupt current mining to restart with new difficulty
    pthread_mutex_lock(&g_mining_state.state_mutex);
    if (g_mining_state.is_mining) {
        pthread_cond_signal(&g_mining_state.state_cond);
        miningshim_log(LOG_DEBUG, "Mining interrupted for difficulty update");
    }
    pthread_mutex_unlock(&g_mining_state.state_mutex);
}

// Legacy functions for backward compatibility (may be called by monerod directly)
// These are now handled through the hook system, but we keep them for compatibility

bool get_mining_status(void* miner_context, mining_status_t* status) {
    if (!status) {
        miningshim_log(LOG_ERROR, "get_mining_status: NULL status parameter");
        return false;
    }

    memset(status, 0, sizeof(mining_status_t));

    pthread_mutex_lock(&g_mining_state.state_mutex);
    status->is_mining = g_mining_state.is_mining;
    status->current_hashrate = g_config.miner_hashrate;
    status->blocks_found = g_metrics.blocks_found;
    status->mining_start_time = g_metrics.mining_start_time;
    pthread_mutex_unlock(&g_mining_state.state_mutex);

    miningshim_log(LOG_DEBUG, "get_mining_status: is_mining=%d, hashrate=%lu, blocks_found=%lu",
                   status->is_mining, status->current_hashrate, status->blocks_found);

    return true;
}

uint64_t get_current_difficulty(void* blockchain_context) {
    uint64_t difficulty = get_current_network_difficulty();
    miningshim_log(LOG_DEBUG, "get_current_difficulty: %lu", difficulty);
    return difficulty;
}

// This function is now handled through the difficulty_update_hook
// But we keep it for direct calls from monerod
void handle_new_block_notify(void* blockchain_context, const block_info_t* new_block) {
    miningshim_log(LOG_DEBUG, "New peer block received: height=%lu, difficulty=%lu",
                   new_block->height, new_block->difficulty);

    update_network_difficulty(new_block);

    pthread_mutex_lock(&g_mining_state.state_mutex);
    if (g_mining_state.is_mining) {
        pthread_cond_signal(&g_mining_state.state_cond);
        miningshim_log(LOG_DEBUG, "Mining interrupted for peer block");
    }
    pthread_mutex_unlock(&g_mining_state.state_mutex);

    // Note: In the new hook system, this notification should come through the hook
    // But we keep this for backward compatibility
}