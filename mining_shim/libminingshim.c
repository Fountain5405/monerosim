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

// Constructor - called when library is loaded
void __attribute__((constructor)) shim_initialize(void) {
    // Skip initialization in test environment
    if (getenv("MININGSHIM_TEST_MODE")) {
        return;
    }

    if (!is_running_under_shadow()) {
        fprintf(stderr, "[MININGSHIM] WARNING: Not running under Shadow simulator\n");
        fprintf(stderr, "[MININGSHIM] Shim is designed for Shadow environment only\n");
    }

    load_configuration();
    initialize_deterministic_prng();
    initialize_logging();
    initialize_metrics();
    initialize_mining_state();

    if (!validate_shim_environment()) {
        miningshim_log(LOG_ERROR, "Shim environment validation failed");
        exit(1);
    }

    miningshim_log(LOG_INFO, "Mining shim initialized successfully");
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

// Shadow detection
bool is_running_under_shadow(void) {
    const char* ld_preload = getenv("LD_PRELOAD");
    return ld_preload && strstr(ld_preload, "libshadow");
}

// Environment validation
bool validate_shim_environment(void) {
    bool valid = true;

    const char* required_functions[] = {
        "start_mining_rpc",
        "stop_mining_rpc",
        "handle_block_notification",
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

// Block creation interface
void create_and_broadcast_block(void* miner_context) {
    typedef bool (*create_block_func_t)(void* context, void* block_template);
    create_block_func_t create_block = (create_block_func_t)dlsym(RTLD_NEXT, "create_block");

    if (!create_block) {
        miningshim_log(LOG_ERROR, "Failed to find create_block function in monerod");
        return;
    }

    // For now, use a simple placeholder - in real implementation this would
    // construct a proper block template
    void* block_template = NULL;  // This needs proper implementation

    bool success = create_block(miner_context, block_template);

    if (success) {
        miningshim_log(LOG_INFO, "Block created and broadcasted successfully");
        g_metrics.blocks_found++;
        g_metrics.last_block_time_ns = get_current_time_ns();
    } else {
        miningshim_log(LOG_WARN, "Block creation failed");
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

// Intercepted functions

void start_mining_rpc(void* miner_context, const char* wallet_address,
                      uint64_t threads_count, bool background_mining) {
    miningshim_log(LOG_INFO, "start_mining_rpc intercepted: wallet=%s, threads=%lu",
                   wallet_address, threads_count);

    pthread_mutex_lock(&g_mining_state.state_mutex);

    if (g_mining_state.is_mining) {
        miningshim_log(LOG_WARN, "Mining already active, ignoring start request");
        pthread_mutex_unlock(&g_mining_state.state_mutex);
        return;
    }

    g_mining_state.is_mining = true;
    g_mining_state.miner_context = miner_context;

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

void stop_mining_rpc(void* miner_context) {
    miningshim_log(LOG_INFO, "stop_mining_rpc intercepted");

    pthread_mutex_lock(&g_mining_state.state_mutex);

    if (!g_mining_state.is_mining) {
        miningshim_log(LOG_WARN, "Mining not active, ignoring stop request");
        pthread_mutex_unlock(&g_mining_state.state_mutex);
        return;
    }

    g_mining_state.is_mining = false;
    pthread_cond_signal(&g_mining_state.state_cond);
    pthread_mutex_unlock(&g_mining_state.state_mutex);

    pthread_join(g_mining_state.mining_thread, NULL);

    miningshim_log(LOG_INFO, "Mining stopped successfully");

    g_metrics.total_mining_time_ns = get_current_time_ns() - g_metrics.mining_start_time;
}

void handle_block_notification(void* blockchain_context, const block_info_t* new_block) {
    miningshim_log(LOG_DEBUG, "New peer block received: height=%lu, difficulty=%lu",
                   new_block->height, new_block->difficulty);

    update_network_difficulty(new_block);

    pthread_mutex_lock(&g_mining_state.state_mutex);
    if (g_mining_state.is_mining) {
        pthread_cond_signal(&g_mining_state.state_cond);
        miningshim_log(LOG_DEBUG, "Mining interrupted for peer block");
    }
    pthread_mutex_unlock(&g_mining_state.state_mutex);

    typedef void (*handle_block_func_t)(void*, const block_info_t*);
    handle_block_func_t original_handler =
        (handle_block_func_t)dlsym(RTLD_NEXT, "handle_new_block_notify");

    if (original_handler) {
        original_handler(blockchain_context, new_block);
    } else {
        miningshim_log(LOG_WARN, "Original handle_new_block_notify not found");
    }
}