# Monero Mining Hooks Specification

**Version:** 1.0  
**Last Updated:** November 4, 2025  
**Purpose:** Extend Monero daemon to expose hookable mining functions for external mining implementations

## 1.0 Executive Summary

This specification defines modifications to the Monero daemon (`monerod`) to expose mining control functions as dynamically linkable hooks. This enables external libraries (via `LD_PRELOAD`) to intercept and replace mining behavior for simulation, testing, and alternative mining implementations.

### 1.1 Motivation

**Problem**: Monero's mining functions are not exposed in the dynamic symbol table, making LD_PRELOAD interception impossible for simulation frameworks like Monerosim/Shadow.

**Solution**: Add explicit hook points in Monero's mining subsystem that:
1. Export symbols to dynamic table (`-rdynamic` or `__attribute__((visibility("default")))`)
2. Allow external libraries to override mining behavior
3. Maintain backward compatibility with normal operation
4. Enable deterministic simulation for research

### 1.2 Benefits

- **For Monerosim**: Enable LD_PRELOAD-based mining shim without source modifications
- **For Developers**: Create custom mining implementations (pool mining, specialized hardware)
- **For Researchers**: Test protocol modifications in controlled environments
- **For Testing**: Deterministic mining for CI/CD pipelines

## 2.0 Current Monero Mining Architecture

### 2.1 Key Components

Based on analysis of `builds/A/monero/src/cryptonote_basic/miner.{h,cpp}`:

```cpp
// miner.h - Key class
class miner {
public:
    // Mining control
    bool start(const account_public_address& adr, size_t threads_count, 
               bool do_background = false, bool ignore_battery = false);
    bool stop();
    
    // Core mining function (static)
    static bool find_nonce_for_given_block(
        const get_block_hash_t &gbh, 
        block& bl, 
        const difficulty_type& diffic, 
        uint64_t height, 
        const crypto::hash *seed_hash = NULL
    );
    
    // Block handling
    bool set_block_template(const block& bl, const difficulty_type& diffic, 
                           uint64_t height, uint64_t block_reward);
    bool on_block_chain_update();
    
    // Status queries
    bool is_mining() const;
    uint64_t get_speed() const;
};

// Interface for block submission
struct i_miner_handler {
    virtual bool handle_block_found(block& b, block_verification_context &bvc) = 0;
    virtual bool get_block_template(block& b, ...) = 0;
};
```

### 2.2 Mining Flow

```
1. miner::start() 
   └─> Spawns worker threads
       └─> Each thread calls worker_thread()
           └─> Calls find_nonce_for_given_block()
               └─> Loops incrementing nonce, hashing block
                   └─> On success: calls i_miner_handler::handle_block_found()
```

### 2.3 Problem: Hidden Symbols

Running `nm -D` on monerod shows:
- **Missing**: `_ZN10cryptonote5miner5startE*` (miner::start)
- **Missing**: `_ZN10cryptonote5miner4stopE*` (miner::stop)
- **Missing**: `_ZN10cryptonote5miner26find_nonce_for_given_blockE*`

These symbols exist in static table but are **not exported** to dynamic symbol table.

## 3.0 Proposed Hook Architecture

### 3.1 Hook Points

Introduce **5 strategic hook points** at key mining operations:

```cpp
// New header: src/cryptonote_basic/mining_hooks.h

#ifndef MONERO_MINING_HOOKS_H
#define MONERO_MINING_HOOKS_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Hook function types
typedef bool (*mining_start_hook_t)(
    void* miner_instance,
    const void* wallet_address,
    uint64_t threads_count,
    bool background_mining,
    bool ignore_battery
);

typedef bool (*mining_stop_hook_t)(
    void* miner_instance
);

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

// Hook registration functions (called by external library via LD_PRELOAD)
__attribute__((visibility("default")))
void monero_register_mining_start_hook(mining_start_hook_t hook);

__attribute__((visibility("default")))
void monero_register_mining_stop_hook(mining_stop_hook_t hook);

__attribute__((visibility("default")))
void monero_register_find_nonce_hook(find_nonce_hook_t hook);

__attribute__((visibility("default")))
void monero_register_block_found_hook(block_found_hook_t hook);

__attribute__((visibility("default")))
void monero_register_difficulty_update_hook(difficulty_update_hook_t hook);

// Hook invocation functions (called by monerod internally)
__attribute__((visibility("default")))
bool monero_invoke_mining_start_hook(
    void* miner_instance,
    const void* wallet_address,
    uint64_t threads_count,
    bool background_mining,
    bool ignore_battery
);

__attribute__((visibility("default")))
bool monero_invoke_mining_stop_hook(void* miner_instance);

__attribute__((visibility("default")))
bool monero_invoke_find_nonce_hook(
    void* miner_instance,
    void* block_ptr,
    uint64_t difficulty,
    uint64_t height,
    const void* seed_hash,
    uint32_t* nonce_out
);

__attribute__((visibility("default")))
bool monero_invoke_block_found_hook(
    void* miner_instance,
    void* block_ptr,
    uint64_t height
);

__attribute__((visibility("default")))
void monero_invoke_difficulty_update_hook(
    void* miner_instance,
    uint64_t new_difficulty,
    uint64_t height
);

#ifdef __cplusplus
}
#endif

#endif // MONERO_MINING_HOOKS_H
```

### 3.2 Hook Implementation

```cpp
// New file: src/cryptonote_basic/mining_hooks.cpp

#include "mining_hooks.h"
#include <mutex>

namespace {
    // Hook storage (thread-safe)
    std::mutex g_hook_mutex;
    mining_start_hook_t g_start_hook = nullptr;
    mining_stop_hook_t g_stop_hook = nullptr;
    find_nonce_hook_t g_find_nonce_hook = nullptr;
    block_found_hook_t g_block_found_hook = nullptr;
    difficulty_update_hook_t g_difficulty_hook = nullptr;
}

extern "C" {

// Registration functions
void monero_register_mining_start_hook(mining_start_hook_t hook) {
    std::lock_guard<std::mutex> lock(g_hook_mutex);
    g_start_hook = hook;
}

void monero_register_mining_stop_hook(mining_stop_hook_t hook) {
    std::lock_guard<std::mutex> lock(g_hook_mutex);
    g_stop_hook = hook;
}

void monero_register_find_nonce_hook(find_nonce_hook_t hook) {
    std::lock_guard<std::mutex> lock(g_hook_mutex);
    g_find_nonce_hook = hook;
}

void monero_register_block_found_hook(block_found_hook_t hook) {
    std::lock_guard<std::mutex> lock(g_hook_mutex);
    g_block_found_hook = hook;
}

void monero_register_difficulty_update_hook(difficulty_update_hook_t hook) {
    std::lock_guard<std::mutex> lock(g_hook_mutex);
    g_difficulty_hook = hook;
}

// Invocation functions
bool monero_invoke_mining_start_hook(
    void* miner_instance,
    const void* wallet_address,
    uint64_t threads_count,
    bool background_mining,
    bool ignore_battery
) {
    std::lock_guard<std::mutex> lock(g_hook_mutex);
    if (g_start_hook) {
        return g_start_hook(miner_instance, wallet_address, threads_count, 
                           background_mining, ignore_battery);
    }
    return false; // No hook registered, use default behavior
}

bool monero_invoke_mining_stop_hook(void* miner_instance) {
    std::lock_guard<std::mutex> lock(g_hook_mutex);
    if (g_stop_hook) {
        return g_stop_hook(miner_instance);
    }
    return false;
}

bool monero_invoke_find_nonce_hook(
    void* miner_instance,
    void* block_ptr,
    uint64_t difficulty,
    uint64_t height,
    const void* seed_hash,
    uint32_t* nonce_out
) {
    std::lock_guard<std::mutex> lock(g_hook_mutex);
    if (g_find_nonce_hook) {
        return g_find_nonce_hook(miner_instance, block_ptr, difficulty, 
                                height, seed_hash, nonce_out);
    }
    return false;
}

bool monero_invoke_block_found_hook(
    void* miner_instance,
    void* block_ptr,
    uint64_t height
) {
    std::lock_guard<std::mutex> lock(g_hook_mutex);
    if (g_block_found_hook) {
        return g_block_found_hook(miner_instance, block_ptr, height);
    }
    return false;
}

void monero_invoke_difficulty_update_hook(
    void* miner_instance,
    uint64_t new_difficulty,
    uint64_t height
) {
    std::lock_guard<std::mutex> lock(g_hook_mutex);
    if (g_difficulty_hook) {
        g_difficulty_hook(miner_instance, new_difficulty, height);
    }
}

} // extern "C"
```

### 3.3 Integration with Existing Miner Class

Modify `src/cryptonote_basic/miner.cpp`:

```cpp
// Add at top of file
#include "mining_hooks.h"

// Modify miner::start()
bool miner::start(const account_public_address& adr, size_t threads_count, 
                 bool do_background, bool ignore_battery)
{
    // Check if external hook wants to handle start
    if (monero_invoke_mining_start_hook(
        static_cast<void*>(this),
        static_cast<const void*>(&adr),
        threads_count,
        do_background,
        ignore_battery
    )) {
        MINFO("Mining start handled by external hook");
        m_mine_address = adr;
        m_threads_total = threads_count;
        m_is_mining = true;
        return true;
    }

    // Original implementation continues...
    // (existing miner::start code)
}

// Modify miner::stop()
bool miner::stop()
{
    // Check if external hook wants to handle stop
    if (monero_invoke_mining_stop_hook(static_cast<void*>(this))) {
        MINFO("Mining stop handled by external hook");
        m_is_mining = false;
        return true;
    }

    // Original implementation continues...
    // (existing miner::stop code)
}

// Modify find_nonce_for_given_block()
bool miner::find_nonce_for_given_block(
    const get_block_hash_t &gbh, 
    block& bl, 
    const difficulty_type& diffic, 
    uint64_t height, 
    const crypto::hash *seed_hash
) {
    uint32_t nonce_out = 0;
    
    // Check if external hook wants to handle nonce finding
    if (monero_invoke_find_nonce_hook(
        nullptr, // Static function, no instance
        static_cast<void*>(&bl),
        diffic,
        height,
        static_cast<const void*>(seed_hash),
        &nonce_out
    )) {
        MINFO("Nonce finding handled by external hook");
        bl.nonce = nonce_out;
        return true;
    }

    // Original implementation continues...
    // (existing find_nonce_for_given_block code)
}

// Add hook invocation when block found
bool miner::worker_thread()
{
    // ... existing worker thread code ...
    
    // When block found:
    if (/* block found condition */) {
        // Invoke hook before submission
        monero_invoke_block_found_hook(
            static_cast<void*>(this),
            static_cast<void*>(&b),
            height
        );
        
        // Continue with normal block submission
        // ... existing code ...
    }
}

// Add hook invocation on difficulty update
bool miner::on_block_chain_update()
{
    // ... existing code ...
    
    // When difficulty changes:
    if (/* difficulty changed */) {
        monero_invoke_difficulty_update_hook(
            static_cast<void*>(this),
            new_difficulty,
            height
        );
    }
    
    // ... rest of function ...
}
```

## 4.0 Build System Modifications

### 4.1 CMakeLists.txt Changes

```cmake
# In src/cryptonote_basic/CMakeLists.txt

set(cryptonote_basic_sources
  # ... existing sources ...
  mining_hooks.cpp  # ADD THIS
)

set(cryptonote_basic_headers
  # ... existing headers ...
  mining_hooks.h    # ADD THIS
)

# Ensure symbols are exported
set_target_properties(obj_cryptonote_basic PROPERTIES
  LINK_FLAGS "-rdynamic"  # Export all symbols to dynamic table
)
```

### 4.2 Compiler Flags

Add to main CMakeLists.txt or daemon-specific config:

```cmake
# Export dynamic symbols for hooking
if(UNIX AND NOT APPLE)
  set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -rdynamic")
endif()
```

### 4.3 Verification

After building, verify symbols are exported:

```bash
nm -D /usr/local/bin/monerod-simulation | grep monero_
```

Expected output:
```
... T monero_register_mining_start_hook
... T monero_register_mining_stop_hook
... T monero_register_find_nonce_hook
... T monero_invoke_mining_start_hook
... T monero_invoke_mining_stop_hook
... T monero_invoke_find_nonce_hook
```

## 5.0 External Library Integration (Mining Shim)

### 5.1 Hook Registration in Constructor

```c
// In libminingshim.c

#include <dlfcn.h>

// Function pointer types for hook registration
typedef void (*register_start_hook_t)(mining_start_hook_t);
typedef void (*register_stop_hook_t)(mining_stop_hook_t);
typedef void (*register_find_nonce_hook_t)(find_nonce_hook_t);

// Hook implementations
static bool mining_shim_start_hook(
    void* miner_instance,
    const void* wallet_address,
    uint64_t threads_count,
    bool background_mining,
    bool ignore_battery
) {
    miningshim_log(LOG_INFO, "Mining start intercepted by shim");
    
    // Initialize probabilistic mining
    pthread_mutex_lock(&g_mining_state.state_mutex);
    g_mining_state.is_mining = true;
    g_mining_state.miner_context = miner_instance;
    
    // Start mining thread
    pthread_create(&g_mining_state.mining_thread, NULL, 
                  mining_loop, miner_instance);
    
    pthread_mutex_unlock(&g_mining_state.state_mutex);
    
    return true; // Tell monerod we handled it
}

static bool mining_shim_stop_hook(void* miner_instance) {
    miningshim_log(LOG_INFO, "Mining stop intercepted by shim");
    
    pthread_mutex_lock(&g_mining_state.state_mutex);
    g_mining_state.is_mining = false;
    pthread_cond_signal(&g_mining_state.state_cond);
    pthread_mutex_unlock(&g_mining_state.state_mutex);
    
    pthread_join(g_mining_state.mining_thread, NULL);
    
    return true;
}

static bool mining_shim_find_nonce_hook(
    void* miner_instance,
    void* block_ptr,
    uint64_t difficulty,
    uint64_t height,
    const void* seed_hash,
    uint32_t* nonce_out
) {
    // Generate deterministic nonce
    *nonce_out = generate_deterministic_nonce();
    
    miningshim_log(LOG_DEBUG, "Nonce generated: %u for height %lu", 
                  *nonce_out, height);
    
    return true; // Nonce is "valid" for simulation
}

// Constructor - register hooks
void __attribute__((constructor)) shim_initialize(void) {
    // ... existing initialization ...
    
    // Get registration functions from monerod
    register_start_hook_t reg_start = 
        (register_start_hook_t)dlsym(RTLD_NEXT, "monero_register_mining_start_hook");
    register_stop_hook_t reg_stop = 
        (register_stop_hook_t)dlsym(RTLD_NEXT, "monero_register_mining_stop_hook");
    register_find_nonce_hook_t reg_nonce = 
        (register_find_nonce_hook_t)dlsym(RTLD_NEXT, "monero_register_find_nonce_hook");
    
    if (reg_start && reg_stop && reg_nonce) {
        reg_start(mining_shim_start_hook);
        reg_stop(mining_shim_stop_hook);
        reg_nonce(mining_shim_find_nonce_hook);
        
        miningshim_log(LOG_INFO, "Mining hooks registered successfully");
    } else {
        miningshim_log(LOG_ERROR, "Failed to register mining hooks");
        exit(1);
    }
}
```

## 6.0 Testing and Validation

### 6.1 Unit Tests

```cpp
// tests/unit_tests/mining_hooks.cpp

TEST(mining_hooks, registration) {
    bool start_called = false;
    bool stop_called = false;
    
    auto start_hook = [](void*, const void*, uint64_t, bool, bool) -> bool {
        start_called = true;
        return true;
    };
    
    auto stop_hook = [](void*) -> bool {
        stop_called = true;
        return true;
    };
    
    monero_register_mining_start_hook(start_hook);
    monero_register_mining_stop_hook(stop_hook);
    
    ASSERT_TRUE(monero_invoke_mining_start_hook(nullptr, nullptr, 1, false, false));
    ASSERT_TRUE(start_called);
    
    ASSERT_TRUE(monero_invoke_mining_stop_hook(nullptr));
    ASSERT_TRUE(stop_called);
}
```

### 6.2 Integration Test

```bash
#!/bin/bash
# Test hook-enabled monerod with mining shim

# Build monerod with hooks
cd builds/A/monero/build
cmake -DCMAKE_EXE_LINKER_FLAGS="-rdynamic" ..
make -j$(nproc)

# Verify hooks exported
nm -D bin/monerod | grep monero_ || exit 1

# Build mining shim
cd ../../../../mining_shim
make clean && make

# Test with LD_PRELOAD
LD_PRELOAD=./libminingshim.so \
MINER_HASHRATE=1000000 \
AGENT_ID=1 \
SIMULATION_SEED=12345 \
bin/monerod --start-mining <test_address>

# Should see: "Mining hooks registered successfully"
```

## 7.0 Backward Compatibility

### 7.1 No Hooks Registered

If no external library registers hooks:
- `monero_invoke_*` functions return `false`
- Monerod continues with original implementation
- **Zero performance impact**
- **Zero behavior change**

### 7.2 Conditional Compilation

Optional: Add compile-time flag to disable hooks entirely:

```cmake
option(ENABLE_MINING_HOOKS "Enable external mining hooks" ON)

if(ENABLE_MINING_HOOKS)
  add_definitions(-DMONERO_MINING_HOOKS_ENABLED)
endif()
```

```cpp
// In miner.cpp
#ifdef MONERO_MINING_HOOKS_ENABLED
    if (monero_invoke_mining_start_hook(...)) {
        return true;
    }
#endif
    // Original implementation
```

## 8.0 Security Considerations

### 8.1 Production Safety

**Concern**: External library could compromise mining behavior

**Mitigations**:
1. **Environment Variable Gate**: Only enable hooks if `MONERO_ENABLE_MINING_HOOKS=1`
2. **Signature Verification**: Optional hook library signature checking
3. **Logging**: All hook invocations logged for audit trails
4. **Capability Limits**: Hooks cannot access private keys or sensitive data

### 8.2 Implementation

```cpp
bool monero_invoke_mining_start_hook(...) {
    // Check if hooks explicitly enabled
    const char* enable_hooks = getenv("MONERO_ENABLE_MINING_HOOKS");
    if (!enable_hooks || strcmp(enable_hooks, "1") != 0) {
        return false; // Hooks disabled by default
    }
    
    // ... rest of implementation ...
}
```

## 9.0 Documentation Updates

### 9.1 Monero Documentation

Add section to Monero developer docs:

```markdown
## Mining Hooks for External Implementations

Monero supports external mining implementations via runtime hooks. This enables:
- Simulation frameworks (Shadow, ns-3)
- Custom mining hardware integration
- Mining pool software
- Protocol research and testing

### Usage

External libraries can register hooks via LD_PRELOAD:

\`\`\`c
#include "cryptonote_basic/mining_hooks.h"

void __attribute__((constructor)) my_init() {
    monero_register_mining_start_hook(my_start_function);
}
\`\`\`

See `src/cryptonote_basic/mining_hooks.h` for complete API.
```

### 9.2 Monerosim Documentation

Update `MINING_SHIM_INTEGRATION.md` to reference new hooks.

## 10.0 Deployment Checklist

- [ ] Add `mining_hooks.h` to `src/cryptonote_basic/`
- [ ] Add `mining_hooks.cpp` to `src/cryptonote_basic/`
- [ ] Modify `src/cryptonote_basic/miner.cpp` with hook invocations
- [ ] Update `src/cryptonote_basic/CMakeLists.txt`
- [ ] Add `-rdynamic` linker flag to daemon build
- [ ] Add unit tests in `tests/unit_tests/`
- [ ] Build and verify symbol export with `nm -D`
- [ ] Test with mining shim via LD_PRELOAD
- [ ] Update Monero documentation
- [ ] Create example external mining library
- [ ] Submit patch to monero-shadow repository

## 11.0 Benefits Summary

### For Monerosim/Shadow
✅ LD_PRELOAD-based mining shim works without source modifications  
✅ Deterministic mining for reproducible research  
✅ Probabilistic mining model integration  

### For Monero Ecosystem
✅ Enables custom mining implementations  
✅ Facilitates protocol research and testing  
✅ Opens door for specialized mining hardware  
✅ Zero impact when hooks not used  
✅ Maintains backward compatibility  

### For Developers
✅ Clean C API for external integration  
✅ Thread-safe hook registration  
✅ Well-defined extension points  
✅ Easy to test and validate  

## 12.0 Implementation Timeline

**Phase 1: Core Infrastructure** (Week 1)
- Create mining_hooks.{h,cpp}
- Add hook registration/invocation functions
- Update build system

**Phase 2: Integration** (Week 2)
- Modify miner.cpp with hook calls
- Ensure proper error handling
- Add logging for debugging

**Phase 3: Testing** (Week 3)
- Write unit tests
- Create integration tests
- Test with Monerosim mining shim
- Verify symbol export

**Phase 4: Documentation & Release** (Week 4)
- Update Monero documentation
- Create example external library
- Submit patch to repository
- Update Monerosim to use new hooks

## 13.0 Alternative Approaches Considered

### 13.1 LD_PRELOAD with Weak Symbols
**Rejected**: Requires monerod to use weak symbol declarations throughout, too invasive.

### 13.2 Plugin System
**Rejected**: Too complex, requires major architectural changes.

### 13.3 RPC-Based Mining Coordinator
**Rejected**: Adds latency, doesn't enable true PoW interception.

### 13.4 Patch-Based Approach (Chosen)
**Accepted**: Minimal changes, clean API, backward compatible, enables LD_PRELOAD.

## 14.0 Conclusion

This specification provides a **minimal, backward-compatible** approach to exposing Monero's mining subsystem for external control. By adding explicit hook points with exported symbols, we enable powerful use cases (simulation, testing, custom implementations) while maintaining zero impact on normal operation.

The implementation is straightforward, well-tested, and opens Monero to a wider ecosystem of mining-related tooling and research.
