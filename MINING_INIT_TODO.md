# Mining Initialization Implementation - Action Plan

## Overview
Implement decentralized per-miner initialization system to replace block controller, enabling immediate mining startup with wallet address retrieval.

## Implementation Tasks

### Phase 1: Create Miner Initialization Script
- [ ] Create `scripts/miner_init.sh` with wallet RPC query logic
- [ ] Implement retry mechanism (24 attempts, 5s intervals)
- [ ] Add wallet creation via RPC (create_wallet)
- [ ] Add address retrieval via RPC (getaddress)
- [ ] Add error handling and logging
- [ ] Make script executable and test standalone

### Phase 2: Implement Rust Daemon Process Module
- [ ] Implement `src/process/daemon.rs` with full daemon configuration
- [ ] Create `add_miner_daemon_process()` function for mining-enabled daemons
- [ ] Create `add_standard_daemon_process()` function for non-mining daemons
- [ ] Add mining shim environment variables (LD_PRELOAD, MINER_HASHRATE, AGENT_ID, SIMULATION_SEED)
- [ ] Add command-line flag support for --start-mining with wallet address
- [ ] Integrate with existing process generation flow

### Phase 3: Update Agent Processing Logic
- [ ] Modify `src/agent/user_agents.rs` to detect miner agents
- [ ] Schedule miner_init.sh script before daemon launch for miners
- [ ] Pass parameters to init script (agent_id, ip, wallet_port, daemon_port)
- [ ] Implement staggered startup timing (5s intervals between miners)
- [ ] Add conditional logic: miners use init script, non-miners use direct launch

### Phase 4: Environment Variable Configuration
- [ ] Update monero_environment in orchestrator to include mining shim vars
- [ ] Add simulation_seed propagation to all miner processes
- [ ] Ensure LD_PRELOAD path correctly resolves to mining shim library
- [ ] Add MININGSHIM_LOG_LEVEL configuration
- [ ] Validate all required environment variables are set

### Phase 5: Remove Block Controller Dependencies
- [ ] Mark `agents/block_controller.py` as deprecated
- [ ] Remove `process_block_controller()` call from orchestrator (optional - can keep for backward compat)
- [ ] Update example configurations to remove block_controller section
- [ ] Remove wallet address registration logic from block controller
- [ ] Clean up unused shared state files (block_controller.json, miner_info files)

### Phase 6: Testing & Validation
- [ ] Create test config with 2 miners (simple case)
- [ ] Generate Shadow configuration and verify miner_init.sh is scheduled
- [ ] Run short simulation (5 minutes) and verify mining starts
- [ ] Check mining shim logs for successful initialization
- [ ] Verify blocks are generated according to hashrate distribution
- [ ] Test with 5+ miners to validate scalability
- [ ] Test failure scenario (wallet unavailable) to verify graceful degradation

### Phase 7: Documentation & Examples
- [ ] Update MINING_SHIM_USAGE.md with new initialization flow
- [ ] Create example config without block controller
- [ ] Document migration path from block controller to mining shim
- [ ] Add troubleshooting section for common issues
- [ ] Update architecture documentation with new flow diagrams

## Implementation Order

1. **Start Simple**: Create and test miner_init.sh standalone
2. **Build Foundation**: Implement daemon.rs module 
3. **Integrate**: Connect init script to agent processing
4. **Test**: Validate with small simulations
5. **Scale**: Test with larger configurations
6. **Clean Up**: Remove block controller dependencies
7. **Document**: Update all documentation

## Success Criteria

✅ Miners start mining within 2 minutes of simulation start
✅ Wallet addresses successfully retrieved via RPC
✅ Mining shim correctly intercepts start_mining calls
✅ Blocks generated according to configured hashrate
✅ No block controller required for mining
✅ Graceful handling of wallet RPC failures
✅ Works with both initial and late-joining miners
✅ All tests pass with new architecture