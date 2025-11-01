-----

## Specification: `libminingshim.so` — A Deterministic, Probabilistic Mining Shim for `monerod` in Shadow

**Version:** 1.0
**Last Updated:** October 27, 2025

### 1.0 Overview and Rationale

This document specifies the design and implementation of `libminingshim.so`, a shared library shim designed to enable decentralized, agent-based Proof-of-Work (PoW) mining of `monerod` within the Shadow discrete-event simulator.

The primary goal is to replace a centralized block creation model with a system where each simulated `monerod` node acts as an independent, competitive mining agent. This architecture is essential for accurately simulating emergent, consensus-level behaviors like selfish mining, which are impossible to model with a central controller.

Instead of performing the computationally expensive RandomX PoW algorithm, which would deadlock the simulator, each agent will use this shim to model the mining process as a probabilistic search.[1] The shim will deterministically calculate the time required for its agent to find a block and will use the simulator's event scheduling capabilities to model this outcome, ensuring reproducible experiments.

### 2.0 Core Architecture

The shim will be implemented as a standard Linux shared library (`.so` file). It will be loaded into each `monerod` process at runtime using the `LD_PRELOAD` mechanism, which is a standard feature of the Shadow simulator.[2]

The shim operates by intercepting specific, high-level function calls within the `monerod` daemon related to the start and stop of mining, as well as the handling of new blocks from peers. By replacing the native CPU-bound mining loop with a deterministic, probabilistic, and event-driven model, the shim allows each `monerod` instance to participate in a competitive mining race without consuming prohibitive host CPU resources or violating Shadow's architectural constraints.

### 3.0 Functional Requirements

#### 3.1 Interception Mechanism

The shim MUST intercept the following key functions within the `monerod` application. The exact function names, signatures, and calling conventions must be identified by inspecting the `monerod` source code or its dynamic symbol table (e.g., using `nm -D`).

  * **`start_mining(...)` (or equivalent):** The function that initiates the PoW hashing loop. The shim will override this to start its probabilistic search timer instead of the real hashing loop.
  * **`stop_mining(...)` (or equivalent):** The function that halts the PoW hashing loop. The shim will override this to cancel its pending search timer.
  * **`handle_new_block_notify(...)` (or equivalent):** The function or callback that is triggered when a new valid block is received from the network and accepted by the daemon's core logic. The shim will hook into this to cancel its current mining search and start a new one based on the new chain tip.

#### 3.2 Agent Configuration

Each mining agent's behavior MUST be configured via environment variables. These will be passed to each virtual host by Shadow's main configuration file (`shadow.yaml`).

  * `MINER_HASHRATE`: (Required) A floating-point number representing the hashrate of this agent in hashes per second (H/s).
  * `AGENT_ID`: (Required) A unique integer identifying the agent (e.g., the last octet of its IP address). This is crucial for deterministic seed generation.
  * `SIMULATION_SEED`: (Required) An integer used as the global seed for the entire simulation to ensure deterministic outcomes.[3]
  * `MINER_STRATEGY`: (Optional) A string specifying the agent's mining strategy. Defaults to `HONEST`. The design must be extensible to support other strategies like `SELFISH`.

#### 3.3 Probabilistic Mining Logic

The core of the shim is the probabilistic model of the PoW search, which is standard in academic blockchain simulators.[1]

1.  **Success Rate ($\lambda$):** The rate at which an agent is expected to find a block is calculated as:
    $\lambda = \frac{\text{agent\_hashrate}}{\text{network\_difficulty}}$
2.  **Time to Find Block (T):** The time `T` until the agent finds a block is a random variable that follows an exponential distribution with rate $\lambda$. The shim will compute `T` by transforming a uniform random number `U` (from its seeded PRNG) using the inverse transform sampling method:
    $T = \frac{-\ln(1 - U)}{\lambda}$
3.  **Unit Conversion:** The calculated time `T` will be in seconds. It must be converted to nanoseconds for use with the `nanosleep` syscall, which Shadow intercepts to advance simulated time.

### 4.0 Determinism and Reproducibility

#### 4.1 Requirement

The simulation MUST be deterministic. Given an identical configuration file and global seed, every run of the simulation must produce an identical sequence of events, including the exact order of blocks found and the miners who found them.

#### 4.2 Mechanism

Determinism will be achieved by using a seeded pseudo-random number generator (PRNG) within each mining agent's shim. The generation of "random" numbers for the probabilistic mining calculation must not use unseeded or system-time-based random sources (e.g., C's `rand()` without a call to `srand()`).

#### 4.3 Seeding Strategy

1.  **Global Seed Input:** The shim will read a global simulation seed from the environment variable `SIMULATION_SEED`.
2.  **Agent-Specific Seed Generation:** Each agent will create its own unique seed for its PRNG instance by combining the global seed with its unique `AGENT_ID`.
    `agent_prng_seed = SIMULATION_SEED + AGENT_ID;`
3.  **PRNG Initialization:** The `mining_loop` thread within the shim must initialize its PRNG with this `agent_prng_seed` before any random numbers are drawn. This ensures that each agent has its own unique, but perfectly repeatable, stream of random numbers.

### 5.0 Implementation Details & API

The shim will be written in C or C++ and will use `dlsym` with `RTLD_NEXT` to find and call the original `monerod` functions.

#### 5.1 Shim Entry Points (Illustrative C/C++ Code)

```c
#define _GNU_SOURCE
#include <dlfcn.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <math.h>
#include <unistd.h>

// Typedefs for original monerod functions (signatures are placeholders)
typedef void (*start_mining_func_t)(void* context,...);
typedef void (*stop_mining_func_t)(void* context,...);
typedef void (*handle_new_block_func_t)(void* context,...);

// Global state for the shim, must be thread-safe
static pthread_t g_miner_thread;
static volatile bool g_is_mining = false;
static pthread_mutex_t g_state_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_state_cond = PTHREAD_COND_INITIALIZER;

// Intercepted start_mining function
void start_mining(void* context,...) {
    pthread_mutex_lock(&g_state_mutex);
    if (g_is_mining) {
        pthread_mutex_unlock(&g_state_mutex);
        return; // Already mining
    }
    g_is_mining = true;

    // Spawn a new thread to manage the probabilistic search loop.
    // This is critical to prevent blocking the main monerod thread.
    pthread_create(&g_miner_thread, NULL, mining_loop, context);
    pthread_mutex_unlock(&g_state_mutex);
}

// Intercepted stop_mining function
void stop_mining(void* context,...) {
    pthread_mutex_lock(&g_state_mutex);
    if (!g_is_mining) {
        pthread_mutex_unlock(&g_state_mutex);
        return;
    }
    g_is_mining = false;
    pthread_cond_signal(&g_state_cond); // Signal the mining thread to wake up and exit
    pthread_mutex_unlock(&g_state_mutex);

    // Wait for the thread to terminate
    pthread_join(g_miner_thread, NULL);

    // Call the original function if necessary for cleanup
    stop_mining_func_t original_stop_mining = (stop_mining_func_t)dlsym(RTLD_NEXT, "stop_mining");
    if (original_stop_mining) {
        original_stop_mining(context,...);
    }
}

// Intercepted new block handler
void handle_new_block_notify(void* context,...) {
    pthread_mutex_lock(&g_state_mutex);
    if (g_is_mining) {
        // A peer won the race. Signal the mining thread to restart its search.
        pthread_cond_signal(&g_state_cond);
    }
    pthread_mutex_unlock(&g_state_mutex);

    // Call the original handler to process the block
    handle_new_block_func_t original_handler = (handle_new_block_func_t)dlsym(RTLD_NEXT, "handle_new_block_notify");
    if (original_handler) {
        original_handler(context,...);
    }
}
```

#### 5.2 The Mining Loop Thread

This thread contains the core logic for the agent-based model. It uses `pthread_cond_timedwait` as a cancellable sleep, which is more robust than relying on flags with `nanosleep`.

```c
void* mining_loop(void* context) {
    // 1. Initialization
    const char* hashrate_str = getenv("MINER_HASHRATE");
    const char* agent_id_str = getenv("AGENT_ID");
    const char* seed_str = getenv("SIMULATION_SEED");
    
    double hashrate = atof(hashrate_str);
    unsigned int seed = atoi(seed_str) + atoi(agent_id_str);
    
    // Use a re-entrant PRNG for thread safety
    struct drand48_data prng_buffer;
    srand48_r(seed, &prng_buffer);

    pthread_mutex_lock(&g_state_mutex);
    while (g_is_mining) {
        pthread_mutex_unlock(&g_state_mutex);

        // 2. Get current network difficulty from monerod internals
        // This function must be implemented to safely read from monerod's state.
        uint64_t difficulty = get_current_network_difficulty(context);

        // 3. Calculate time T to find a block
        double u;
        drand48_r(&prng_buffer, &u); // Draw from.

*   **State:** Requires additional state to manage a private chain (e.g., `private_chain_length`, `public_chain_length`).
*   **On "Block Found" (timer expires):**
    *   Does **not** broadcast the block.
    *   Increments its `private_chain_length`.
    *   Immediately starts a new search on top of its own private block.
*   **On Peer Block Received:**
    *   Increments `public_chain_length`.
    *   Executes the selfish mining state machine logic based on the lead `delta = private_chain_length - public_chain_length`.
        *   If `delta` becomes 0 (a tie), broadcast the private block to create a race.
        *   If `delta` becomes -1 (honest chain pulls ahead), abandon the private chain and mine on the public chain.
        *   If `delta` becomes 1 and an honest block is found, broadcast the entire private chain to win the fork.
    *   This logic requires careful state management and the ability to broadcast specific, withheld blocks on demand.

### 7.0 Dependencies and Environment

*   **Build Environment:** Standard C/C++ compiler (GCC/Clang).
*   **Libraries:** `pthread` for the mining loop thread, `dlfcn.h` for `dlsym`, `math.h` for `log()`.
*   **Target Application:** A dynamically linked build of `monerod`. The shim will not work with a statically linked binary.
*   **Execution Environment:** The Shadow discrete-event simulator. The shim is intended to be loaded via `LD_PRELOAD`.
```
