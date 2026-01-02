# Monerosim Determinism Investigation - Findings and Remediation Plan

## Executive Summary

Deep investigation of the monerosim codebase has identified **14 distinct sources of non-determinism** that could cause simulations to produce different outputs across runs. These issues range from critical (unseeded RNG in Python agents) to architectural (Monero's internal PRNG not being seedable).

---

## Critical Non-Determinism Sources

### 1. Unseeded Random Number Generation in Python Agents (CRITICAL)

**Files affected:**
- `agents/block_controller.py` - Lines 309, 314-328
- `agents/miner_distributor.py` - Lines 534-535, 554, 570, 627-628, 780
- `agents/regular_user.py` - Lines 252-286

**Issue:** These agents use Python's `random` module without seeding from `SIMULATION_SEED`:
```python
# block_controller.py - No seeding
random.choice()  # Line 309, 325
random.uniform() # Line 314

# miner_distributor.py - No seeding
random.choice()  # Lines 534-535, 554, 570
random.uniform() # Lines 627-628, 780

# regular_user.py - No seeding
random.random()  # Line 266
random.choice()  # Line 278
random.uniform() # Line 286
```

**Working reference:** `agents/autonomous_miner.py` correctly implements seeding:
```python
self.global_seed = int(os.getenv('SIMULATION_SEED', '12345'))
self.agent_seed = self.global_seed + hash(agent_id)
random.seed(self.agent_seed)
```

**Additional issue:** `block_controller.py:314` also uses `np.random.choice()` - numpy's RNG is separate from Python's `random` module and requires its own seeding via `np.random.seed()`.

**Fix:** Add identical seeding pattern to all agents that use random, plus add `np.random.seed(self.agent_seed)` where numpy is used.

---

### 2. Process ID in Temporary File Path (CRITICAL)

**File:** `src/orchestrator.rs:33`
```rust
let temp_gml_path = format!("/tmp/monerosim_gml_{}.gml", std::process::id());
```

**Issue:** `std::process::id()` varies between runs, creating different temp file paths.

**Fix:** Use a deterministic identifier based on `simulation_seed` or timestamp from config.

---

### 3. Python `hash()` Function Non-determinism (HIGH)

**File:** `agents/autonomous_miner.py:57`
```python
self.agent_seed = self.global_seed + hash(agent_id)
```

**Issue:** Python's `hash()` is randomized by default (PYTHONHASHSEED). Different systems or runs produce different hashes.

**Current state:** PYTHONHASHSEED is NOT set anywhere in the codebase (confirmed via grep).

**Fix:** Set `PYTHONHASHSEED=0` in environment variables passed to all processes in `src/orchestrator.rs`.

---

### 4. HashMap Iteration Order (MEDIUM-HIGH)

**Files:**
- `src/orchestrator.rs` - Multiple HashMaps
- `src/topology/distribution.rs` - Agent distribution logic

**Issue:** Rust's HashMap has non-deterministic iteration order. While host output is sorted (line 747-748), internal logic may depend on iteration order.

**Partial mitigation exists:**
```rust
let mut sorted_hosts: Vec<(String, ShadowHost)> = hosts.into_iter().collect();
sorted_hosts.sort_by(|(a, _), (b, _)| a.cmp(b));
```

**Fix:** Replace HashMap with BTreeMap for deterministic iteration, or ensure all HashMap iterations are followed by sorting.

---

### 5. `time.time()` Usage Throughout Python Agents (MEDIUM)

**Files affected:**
- `agents/agent_discovery.py` - Lines 108, 173, 234, 508, 844, 906
- `agents/simulation_monitor.py` - Lines 389, 413, 437, 513, 523, 999, 1034, etc.
- `agents/block_controller.py` - Lines 53, 65, 105, 108, 130, 400, 404, etc.
- `agents/miner_distributor.py` - Lines 58, 264, 278, 445, 461, 890
- `agents/dns_server.py` - Lines 73, 74
- `agents/base_agent.py` - Lines 216, 219, 223, 226, 452, 475, 476, etc.
- `agents/regular_user.py` - Lines 118, 149, 351

**Issue:** `time.time()` returns wall-clock time, not simulated time. If decision logic depends on actual time elapsed, results vary.

**Fix:** Audit each usage - logging timestamps are OK, but decision logic based on wall-clock time should use Shadow's simulated time or deterministic counters.

---

### 6. File System Race Conditions (MEDIUM)

**Directory:** `/tmp/monerosim_shared/`

**Files written concurrently:**
- `agent_registry.json`
- `miners.json`
- `{agent_id}_miner_info.json`
- `public_nodes.json`

**Issue:** Multiple agents write to shared files without locking. File read/write timing can vary.

**Fix:** Implement file locking or atomic write operations. Python's `fcntl.flock()` or write-to-temp-then-rename pattern.

---

### 7. Environment-Dependent Current Directory (LOW)

**File:** `src/process/wallet.rs:31`
```rust
let _launcher_path = std::env::current_dir()
```

**Issue:** Current working directory depends on where binary is executed from.

**Fix:** Use absolute paths from configuration instead of relying on current directory.

---

## Architectural Non-Determinism (External Dependencies)

### 8. Monero's Internal PRNG (ARCHITECTURAL)

**Issue:** Monerod uses its own internal random number generator for:
- Block candidate generation
- Transaction ordering in blocks
- Peer selection (when dynamic)

**Impact:** Block hashes will differ between runs even with identical network behavior.

**Potential fixes:**
- Patch monerod to accept a seed from environment variable
- Or accept that block content/hashes will vary but network behavior is deterministic

---

### 9. DNS Server Timing (MEDIUM - if enabled)

**File:** `agents/dns_server.py`

**Issue:** Python DNS server response timing is unpredictable. Monerod's DNS query retry logic may not be synchronized with Shadow's virtual clock.

**Fix:** Disable DNS server for deterministic runs (use hardcoded seed nodes) or investigate Shadow's DNS handling.

---

### 10. RPC Retry Jitter (LOW-MEDIUM)

**File:** `agents/monero_rpc.py:131-135`

**Issue:** Exponential backoff for RPC readiness checking uses wall-clock time with capped delays.

**Fix:** Use fixed retry intervals or coordinate with Shadow's simulated time.

---

## Summary Table

| # | Issue | Severity | Category | File(s) | Fix Complexity |
|---|-------|----------|----------|---------|----------------|
| 1 | Unseeded RNG (block_controller) | CRITICAL | Python RNG | block_controller.py | Easy ✅ |
| 2 | Unseeded RNG (miner_distributor) | CRITICAL | Python RNG | miner_distributor.py | Easy ✅ |
| 3 | Unseeded RNG (regular_user) | CRITICAL | Python RNG | regular_user.py | Easy ✅ |
| 4 | Process ID in temp path | CRITICAL | Rust runtime | orchestrator.rs:33 | Easy ✅ |
| 5 | Python hash() randomization | HIGH | Environment | All Python agents | Easy ✅ |
| 6 | HashMap iteration order | MEDIUM-HIGH | Rust collections | orchestrator.rs, distribution.rs | Medium ✅ |
| 7 | time.time() usage | MEDIUM | Python timing | Multiple agents | N/A (Shadow intercepts) |
| 8 | File system race conditions | MEDIUM | Concurrency | /tmp/monerosim_shared | Medium ✅ |
| 9 | Monero internal PRNG | PARTIAL | Shadow | shadowformonero/injector.c | RNG seeded ✅, threading causes ~4% variance |
| 10 | DNS server file access | MEDIUM | External | dns_server.py | Easy ✅ |
| 11 | RPC retry jitter | LOW-MEDIUM | Timing | monero_rpc.py | N/A (Shadow intercepts) |
| 12 | Current directory dependency | LOW | Environment | wallet.rs | Easy (low priority) |
| 13 | Shadow seed not set | CRITICAL | Shadow config | orchestrator.rs, types.rs | Easy ✅ |

---

## Recommended Implementation Order

### Phase 1: Quick Wins (High Impact, Low Effort) - COMPLETED
1. ✅ Add `PYTHONHASHSEED=0` to environment variables in orchestrator.rs
2. ✅ Add RNG seeding to block_controller.py, miner_distributor.py, regular_user.py
3. ✅ Replace `std::process::id()` with deterministic value in orchestrator.rs

### Phase 2: Collection Ordering - COMPLETED
4. ✅ Audit HashMap usage and either replace with BTreeMap or add sorting before iteration

### Phase 3: Timing and File I/O - COMPLETED
5. ✅ Audit time.time() usage - Shadow intercepts time calls making them deterministic
6. ✅ Implement file locking for shared state files (write_shared_state, append_shared_list)

### Phase 4: DNS Server Determinism - COMPLETED
7. ✅ Add file locking to dns_server.py for agent_registry.json and dns_checkpoints.json reads
8. ✅ Add file locking to block_controller.py for agent_registry.json access
9. ✅ Add file locking to autonomous_miner.py for agent_registry.json access

### Phase 5: Shadow RNG Seeding - COMPLETED
10. ✅ Pass simulation_seed to Shadow's `general.seed` config (CRITICAL)
    - Shadow intercepts OpenSSL RNG via `use_preload_openssl_rng` (enabled by default)
    - This controls randomness for Dandelion++, peer selection, and other Monero behaviors
    - Previously Shadow was using default seed (1) instead of configured simulation_seed

### Phase 6: Shadow Constructor Priority Fix - COMPLETED
11. ✅ Fix Shadow's injector constructor priority to run before monerod's RNG initialization
    - **Root cause identified:** Shadow's `libshadow_injector.so` constructor had no priority
    - Monerod's `init_random()` uses priority 101, running before Shadow's default-priority constructor
    - This caused `/dev/urandom` reads during monerod startup to use real randomness, not Shadow's seeded PRNG
    - **Fix applied:** Changed `shadowformonero/src/lib/preload-injector/injector.c` to use `__attribute__((constructor(101)))`
    - **Important:** GCC reserves priorities 0-100, so priority 101 is the lowest valid user-settable priority
    - When two constructors have the same priority (101), LD_PRELOAD order determines execution order
    - Since Shadow's injector.so is first in LD_PRELOAD, it runs BEFORE monerod's init_random()
    - Verified via: `readelf -r ~/.local/lib/libshadow_injector.so` shows _injector_load at offset 0x3e00 in .init_array
    - Rebuild Shadow with: `cd shadowformonero/build && make -j4 shadow_injector && make install`

### Phase 7: Architectural Decisions - PENDING
12. Determine if DNS server should be disabled by default for determinism
13. Verify full determinism with run comparisons after Phase 6 fix

---

## Files to Modify

**Shadow files (shadowformonero):**
- `src/lib/preload-injector/injector.c` - Set constructor priority to 101 for early RNG interception

**Rust files:**
- `src/orchestrator.rs` - Add PYTHONHASHSEED, fix temp file path, audit HashMaps
- `src/topology/distribution.rs` - Audit HashMap iteration
- `src/process/wallet.rs` - Remove current_dir dependency

**Python files:**
- `agents/block_controller.py` - Add RNG seeding, file locking for agent_registry.json
- `agents/miner_distributor.py` - Add RNG seeding
- `agents/regular_user.py` - Add RNG seeding
- `agents/base_agent.py` - Add file locking utilities
- `agents/monero_rpc.py` - Fixed retry intervals
- `agents/dns_server.py` - Add file locking for agent_registry.json and dns_checkpoints.json
- `agents/autonomous_miner.py` - Add file locking for agent_registry.json

---

## Verification Strategy

After fixes are applied:
1. Run simulation twice with identical config and `simulation_seed`
2. Compare Shadow log outputs
3. Compare final blockchain state (block heights, transaction counts)
4. If Monero PRNG is not patched, compare network-level events only (connection patterns, message timing)
