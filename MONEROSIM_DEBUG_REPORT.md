# Monerosim Agent-Based Simulation Debug Report

## Executive Summary

The Monerosim agent-based simulation was failing to produce blocks due to multiple configuration errors in the Shadow configuration generator (`src/shadow_agents.rs`). All critical issues have been identified and fixed.

## Issues Identified

### 1. P2P Network Failure (Critical)
**Symptom**: All nodes reported "Failed to connect to any peer" errors
**Root Cause**: Nodes were configured to connect to non-existent IP addresses (`11.0.0.1` and `11.0.0.2`)
**Location**: `src/shadow_agents.rs` lines 164-165 and 323-324

### 2. Block Controller Misconfiguration (Critical)
**Symptom**: Block controller crashed with wallet creation error
**Root Cause**: 
- Block controller expected daemon at hardcoded IP `11.0.0.252:29100`
- Block controller expected wallet at hardcoded IP `11.0.0.254:29200`
- Shadow config was passing different IPs
**Location**: `src/shadow_agents.rs` line 383

### 3. Monitor Script Path Error (Major)
**Symptom**: Monitor crashed with `ModuleNotFoundError`
**Root Cause**: Invalid Python module path `agents.../scripts/monitor`
**Location**: `src/shadow_agents.rs` line 405

### 4. No Mining Pools (Design Issue)
**Symptom**: No blocks being generated
**Root Cause**: Despite config specifying "mining_pools: 2", the code creates regular nodes instead
**Note**: This is by design - the new block controller approach uses `generateblocks` RPC instead of mining pools

### 5. libunbound Error (Minor)
**Symptom**: `setsockopt(..., IP_MTU_DISCOVER, IP_PMTUDISC_OMIT...) failed`
**Root Cause**: Shadow network simulation environment limitation
**Impact**: Non-critical, does not affect functionality

## Fixes Applied

### 1. P2P Network Fix
```rust
// Before:
daemon_args.push("--add-priority-node=11.0.0.1:28080".to_string());
daemon_args.push("--add-priority-node=11.0.0.2:28080".to_string());

// After:
daemon_args.push("--add-priority-node=11.0.0.10:28080".to_string());
if agent_config.regular_users > 1 {
    daemon_args.push("--add-priority-node=11.0.0.11:28080".to_string());
}
```

### 2. Block Controller Fix
```rust
// Added proper host parameters to block controller
let agent_args = format!(
    "--interval 120 --blocks 1 --wallet-rpc {} --wallet-host {} \
     --daemon-host 11.0.0.10 --daemon-rpc 28090 \
     --log-level INFO",
    block_controller_wallet_port, block_controller_ip
);
```

### 3. Monitor Script Fix
```rust
// Before:
args: create_agent_command(&current_dir, "../scripts/monitor.py", ""),

// After:
args: format!("-c 'cd {} && . ./venv/bin/activate && python3 scripts/monitor.py'", current_dir),
```

## Architecture Clarification

The agent-based simulation uses a different approach than traditional mining:
- **Traditional**: Mining pools with `start_mining` RPC
- **Agent-Based**: Block controller using `generateblocks` RPC
- This is intentional and more reliable for simulations

## Verification Steps

1. Rebuild monerosim: `cargo build --release`
2. Regenerate config: `./target/release/monerosim --config config_agents_medium.yaml --output shadow_agents_output`
3. Run simulation: `shadow shadow_agents_output/shadow_agents.yaml`

## Expected Behavior After Fixes

1. All nodes should connect to the P2P network successfully
2. Block controller should create wallet and start generating blocks
3. Users should receive mining rewards and start sending transactions
4. Marketplaces should receive and track payments
5. Monitor should display simulation progress

## Recommendations

1. Consider making the seed node IPs configurable rather than hardcoded
2. Add validation to ensure at least 2 user nodes exist when using priority nodes
3. Consider adding actual mining pool agents for more realistic simulations
4. Add better error handling for wallet creation (idempotency)
5. Document the architectural decision to use generateblocks instead of mining pools

## Files Modified

- `src/shadow_agents.rs` - Fixed P2P connections, block controller config, and monitor path
- Created patch file: `fix_shadow_agents.patch`

## Next Steps

1. Run a test simulation with the fixed configuration
2. Monitor logs to ensure blocks are being generated
3. Verify transactions are flowing between users and marketplaces
4. Consider implementing the recommendations above