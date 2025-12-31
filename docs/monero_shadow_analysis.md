# Plan: Transition Monerosim to Standard Monerod

## Goal

Analyze monero-shadow customizations and determine what's needed to run monerosim with unmodified monerod instead of the patched monero-shadow version.

---

## Current Monero-Shadow Modifications

### Summary of All Changes

| # | Modification | Files | Difficulty to Remove |
|---|--------------|-------|---------------------|
| 1 | `--simulation` flag | cryptonote_core.cpp/h | Medium - need alternative approach |
| 2 | Checkpoint validation bypass | blockchain.cpp/h | **HARD** - fundamental blocker |
| 3 | DNS checkpoint disable | cryptonote_core.cpp | **DONE** - DNS server approach |
| 4 | Startup message | cryptonote_core.cpp | Easy - cosmetic only |
| 5 | Block generation without sync | core_rpc_server.cpp | Medium - use `--regtest` |
| 6 | Block rate checking disable | cryptonote_core.cpp | Easy - use `--offline` |
| 7 | IP_TOS socket option handling | abstract_tcp_server2.inl | **HARD** - Shadow limitation |
| 8 | TCP_NODELAY socket option handling | abstract_tcp_server2.inl | **HARD** - Shadow limitation |
| 9 | Peer connection limits bypass | net_node.inl | **REMOVABLE** - diverse GML IPs solve this |
| 10 | Max connections per IP increase | net_node.cpp | Easy - CLI flag exists |
| 11 | Block generation RPC allowance | core_rpc_server.cpp | Medium - use `--regtest` |

---

## Detailed Analysis by Category

### Category A: Already Solved (DNS)
**Status: DONE**

- DNS checkpoint disable
- DNS seed node lookups

**Solution:** Our DNS server implementation handles this. Monerod uses `DNS_PUBLIC` env var to query our internal DNS server.

---

### Category B: Easy to Work Around

#### 1. Block Rate Checking
**Current:** Disabled via `m_simulation_mode`
**Standard monerod:** ~~Use `--offline` flag~~ **NOT VIABLE - see below**

---

## CRITICAL: Why `--offline` Cannot Be Used

The `--offline` flag does **much more** than just disable rate checking. It completely disables ALL networking:

```cpp
// From cryptonote_core.cpp line 119-121:
const command_line::arg_descriptor<bool> arg_offline = {
  "offline", "Do not listen for peers, nor connect to any"
};
```

**What `--offline` actually does:**
| Function | Effect |
|----------|--------|
| `get_dns_seed_nodes()` | Returns empty - no DNS lookups |
| `init()` in net_node | Returns early - **doesn't bind P2P port** |
| `connections_maker()` | Returns immediately - **no peer connections** |
| `make_expected_connections_count()` | Returns false - **no outgoing connections** |
| `check_incoming_connections()` | Skips check - **no incoming accepted** |
| Wallet RPC calls | Return "offline" error - **wallet broken** |

**This completely defeats the purpose of a network simulation!**

The `--simulation` flag was specifically created because `--offline` disables ALL P2P networking, but we need:
- ✅ P2P port binding
- ✅ Peer connections between nodes
- ✅ DNS discovery (or add-priority-node)
- ✅ Block/transaction propagation

`--offline` gives us NONE of these.

---

#### 2. Max Connections Per IP
**Current:** Hardcoded to 50 in monero-shadow
**Standard monerod:** Use `--max-connections-per-ip=50` CLI flag

#### 3. Startup Message
**Current:** Shows "simulation mode" message
**Standard monerod:** Will show normal message - cosmetic, no functional impact

---

### Category C: Medium Difficulty - Use Regtest Mode

#### 4. Block Generation Without Sync
**Current:** `m_simulation_mode` allows mining without sync
**Standard monerod:** `--regtest` mode allows this

#### 5. Block Generation RPC
**Current:** Allows `generateblocks` RPC in simulation
**Standard monerod:** `--regtest` mode enables this

**Trade-off:** Regtest mode uses FAKECHAIN nettype, which may have other implications for transaction validation, difficulty, etc.

---

### Category D: HARD - Fundamental Blockers

#### 6. Checkpoint Validation Bypass (CRITICAL)
**Problem:** Monero has hardcoded checkpoints - block hashes at specific heights that MUST match. Simulated blocks will have different hashes.

**Current monero-shadow solution:**
```cpp
if(m_checkpoints.is_in_checkpoint_zone(blockchain_height) && !m_simulation_mode) {
  // validate checkpoint
}
```

**Options for standard monerod:**
1. **Use `--regtest`**: Regtest mode skips checkpoint validation (needs verification)
2. **Start fresh chain from height 0**: No checkpoints at height 0-1
3. **Use testnet/stagenet**: Different checkpoint sets, but still have some

**Risk:** If regtest doesn't fully skip checkpoints, this is a blocker.

#### 7-8. Socket Option Errors (IP_TOS, TCP_NODELAY)
**Problem:** Shadow's virtual network doesn't support these Linux socket options. Standard monerod treats failures as fatal errors.

**Current monero-shadow solution:**
```cpp
if (ec.value()) {
  MWARNING("IP_TOS setsockopt failed: ...");
  // continue instead of fail
}
```

**Options for standard monerod:**
1. **Shadow patch**: Modify Shadow simulator to fake these syscalls (complex)
2. **LD_PRELOAD shim**: Intercept setsockopt() calls and ignore specific options
3. **Kernel module**: Not practical
4. **Accept the limitation**: These modifications MUST stay in monero-shadow

**Reality:** This likely requires keeping the socket patches in monero-shadow OR modifying Shadow itself.

#### 9. Peer Connection Limits Bypass - **NOW REMOVABLE**
**Original Problem:** Standard monerod limits connections per host/subnet to prevent DoS. In Shadow with simple IP allocation, all nodes appeared to be on the same subnet.

**Current monero-shadow solution:**
```cpp
bool is_host_limit(...) {
  return false; // always allow
}
```

**NEW FINDING (December 2024):** This bypass is **likely no longer needed** with GML-based network topology!

**Analysis:**
1. `is_same_host()` in `net_utils_base.h:83` does **EXACT IP matching**:
   ```cpp
   constexpr bool is_same_host(const ipv4_network_address& other) const noexcept
   { return ip() == other.ip(); }
   ```
2. `has_too_many_connections()` counts connections per EXACT IP, not per subnet
3. With GML topology, nodes get diverse IPs: `10.0.5.10`, `172.16.12.10`, `200.0.3.10`, etc.
4. Different nodes = different IPs = `is_same_host()` returns `false`
5. Per-host limit check passes naturally

**Original `is_host_limit()` function (before bypass):**
```cpp
bool is_host_limit(const epee::net_utils::network_address &address)
{
  const network_zone& zone = m_network_zones.at(address.get_zone());
  if (zone.m_current_number_of_in_peers >= zone.m_config.m_net_config.max_in_connection_count)
  {
    MWARNING("Exceeded max incoming connections, so dropping this one.");
    return true;
  }
  if(has_too_many_connections(address))
  {
    MWARNING("CONNECTION FROM " << address.host_str() << " REFUSED, too many connections from the same address");
    return true;
  }
  return false;
}
```

**Conclusion:** With diverse GML-based IP allocation, we can **restore the original function** and remove the bypass. The global incoming limit (check #1) is still configurable via CLI.

---

## Feasibility Assessment

### Can We Use Standard Monerod?

**Short answer: Partially, with significant limitations**

| Aspect | Standard Monerod Feasible? | Notes |
|--------|---------------------------|-------|
| DNS peer discovery | ✅ YES | DNS server solution works |
| Checkpoint bypass | ⚠️ MAYBE | Requires `--regtest` testing |
| Socket options | ❌ NO | Shadow limitation, needs patch |
| Peer limits | ✅ YES | Diverse GML IPs = exact IP matching works |
| Block generation | ✅ YES | Use `--regtest` |

### Minimum Required Patches

Even with best-case scenario, we likely need to keep these patches:

1. **Socket option error handling** (IP_TOS, TCP_NODELAY) - Shadow fundamental limitation
2. ~~**Possibly peer connection limits**~~ - **NO LONGER NEEDED** with diverse GML IPs

---

## Recommended Approach

### Phase 1: Test Regtest Mode (Low effort)
1. Try running monerosim with standard monerod using `--regtest` flag
2. Add CLI flags: `--max-connections-per-ip=50`, `--offline`
3. See what breaks

### Phase 2: Create Minimal Patch Set
1. If socket options fail, create MINIMAL monero patch (just socket handling)
2. Keep all other standard monerod behavior
3. Document exact changes needed

### Phase 3: Alternative - Shadow Modification
1. Investigate if Shadow can be modified to handle socket options
2. This would be more maintainable long-term
3. Shadow is the simulation layer - it should handle syscall virtualization

---

## Testing Plan

### Test 1: Regtest + Standard Monerod
```bash
monerod --regtest --offline --max-connections-per-ip=50 \
        --p2p-bind-ip=X --rpc-bind-ip=X
```

**Expected failures:**
- Socket option errors (if they occur)
- Peer connection issues (maybe)

### Test 2: Identify Exact Failure Points
- Run in Shadow
- Capture all error messages
- Identify which patches are truly required

---

## Files to Investigate Further

1. `/home/lever65/monerosim_dev/monero-shadow/src/cryptonote_core/cryptonote_core.cpp` - simulation mode implementation
2. `/home/lever65/monerosim_dev/monero-shadow/contrib/epee/include/net/abstract_tcp_server2.inl` - socket patches
3. `/home/lever65/monerosim_dev/monero-shadow/src/p2p/net_node.inl` - peer limit bypass

---

## Revised Conclusion

**Full standard monerod: NOT FEASIBLE** for multiple reasons:

### Must-Have Patches (Cannot be removed)

1. **Socket option handling** (IP_TOS, TCP_NODELAY)
   - Shadow's vnet doesn't support these
   - Standard monerod treats failures as fatal
   - **2 small patches in abstract_tcp_server2.inl**

2. **Checkpoint validation bypass**
   - Simulated blocks have different hashes than real network
   - `--regtest` MAY help but needs testing
   - **1 patch in blockchain.cpp**

3. **Block rate checking bypass** (cannot use `--offline`)
   - `--offline` disables ALL networking - unusable
   - Need simulation mode to allow fast block generation while keeping P2P
   - **1 condition in cryptonote_core.cpp**

### Can Be Removed (Already solved or cosmetic)

1. ✅ **DNS checkpoints** - DNS server solution
2. ✅ **DNS seed nodes** - DNS server solution
3. ✅ **Peer connection limits bypass** - diverse GML IPs solve this (uses exact IP matching)
4. 🔄 **Startup message** - cosmetic only
5. ⚠️ **Block generation without sync** - test with `--regtest`
6. ⚠️ **Block generation RPC** - test with `--regtest`

### Minimum Viable Patch Set

Even with our DNS server and optimal configuration, we need **at least 3-4 patches**:
- Socket error handling (2 locations)
- Checkpoint bypass (1 location)
- Block rate/generation (1-2 locations depending on `--regtest` testing)

**NOTE:** Peer limits bypass is NO LONGER NEEDED with GML-based diverse IP allocation.

### Recommendation

**Keep monero-shadow as a maintained fork** with minimal, well-documented patches. The `--simulation` flag approach is the right design because:

1. It's a single flag that enables all simulation-specific behaviors
2. It doesn't break normal monerod operation
3. It's easier to maintain than scattered CLI workarounds
4. `--offline` is NOT a substitute - it kills all networking

**Future improvement:** Consider upstreaming a `--simulation` or `--shadow` flag to official Monero, documented as "for network simulation environments".

---

## Action Plan: Test Peer Limits Bypass Removal

### Step 1: Restore Original `is_host_limit()` in monero-shadow
**File:** `/home/lever65/monerosim_dev/monero-shadow/src/p2p/net_node.inl:230`

Replace the bypass:
```cpp
bool is_host_limit(const epee::net_utils::network_address &address)
{
  (void)address;
  return false; // always allow
}
```

With the original:
```cpp
bool is_host_limit(const epee::net_utils::network_address &address)
{
  const network_zone& zone = m_network_zones.at(address.get_zone());
  if (zone.m_current_number_of_in_peers >= zone.m_config.m_net_config.max_in_connection_count)
  {
    MWARNING("Exceeded max incoming connections, so dropping this one.");
    return true;
  }
  if(has_too_many_connections(address))
  {
    MWARNING("CONNECTION FROM " << address.host_str() << " REFUSED, too many connections from the same address");
    return true;
  }
  return false;
}
```

### Step 2: Rebuild monero-shadow
```bash
cd /home/lever65/monerosim_dev/monero-shadow
make -j$(nproc)
```

### Step 3: Run simulation with GML topology
```bash
cd /home/lever65/monerosim_dev/monerosim
./run_sim.sh config_32_agents.yaml  # Uses GML topology with diverse IPs + DNS server
```

### Step 4: Verify success
- Check if all peer connections form properly
- Look for "too many connections from the same address" warnings in logs
- If no warnings and network forms correctly, the bypass can be permanently removed

### Expected Result
With diverse GML-based IPs (10.x, 172.16.x, 200.x, etc.), each node has a unique IP, so:
- `is_same_host()` returns `false` for different nodes
- `has_too_many_connections()` returns `false`
- Network should form normally without the bypass
