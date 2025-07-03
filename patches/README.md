# Monero Shadow Compatibility Patches

This directory contains patches to make Monero compatible with the Shadow network simulator.

## shadow_compatibility.patch

**Purpose**: Enables Monero to run in Shadow network simulator by resolving threading compatibility issues.

**What it does**:
- Adds `SHADOW_BUILD` CMake configuration option
- Patches `tests/performance_tests/performance_utils.h` to skip pthread scheduling operations
- Avoids `pthread_setaffinity_np` and `pthread_setschedprio` calls that cause "Operation not permitted" errors in Shadow

**How to apply**:

1. **To a fresh Monero repository**:
   ```bash
   cd /path/to/monero
   git apply /path/to/monerosim/patches/shadow_compatibility.patch
   ```

2. **Build with Shadow compatibility**:
   ```bash
   cmake -DSHADOW_BUILD=ON -DCMAKE_BUILD_TYPE=Release .
   make -j$(nproc)
   ```

3. **Use with MoneroSim**:
   The MoneroSim build system automatically applies this patch and enables the SHADOW_BUILD flag when building Monero nodes for Shadow simulation.

**Compatibility**: 
- Tested with Monero v0.18.4.0
- Should work with most Monero versions that include the performance test framework
- Safe for normal builds (patch only activates with SHADOW_BUILD=ON)

**Background**: 
Shadow network simulator intercepts system calls and provides its own process emulation. While basic pthread operations (create, join, mutex) work fine, thread affinity and priority modifications are not supported and cause crashes. This patch conditionally disables these operations while maintaining full functionality for native builds.

**Results**: 
With this patch, 5-node Monero networks can run continuously for extended periods in Shadow (tested 10+ minutes) with full blockchain and P2P operations. 