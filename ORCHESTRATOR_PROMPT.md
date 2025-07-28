# Orchestrator Mode Prompt for Monerosim Agent Architecture Implementation

## Project Context

Monerosim is a Monero network simulator that uses Shadow. We need to implement a hybrid agent-based architecture where Python agents represent network participants (regular users, marketplaces, mining pools) and control pre-launched Monero processes via RPC.

## Architecture Overview

The architecture uses a hybrid approach due to Shadow constraints:
- Shadow launches Monero binaries (monerod, monero-wallet-rpc) directly
- Shadow also launches Python agents that control these binaries via RPC
- Agents implement participant behaviors (sending transactions, mining coordination, etc.)

Key architectural documents:
- `HYBRID_ARCHITECTURE_PROPOSAL.md` - The approved architecture design
- `SHADOW_CONSTRAINTS_ANALYSIS.md` - Why we need the hybrid approach
- Current working implementation in `src/shadow.rs` and `scripts/`

## Development Goals

Implement the agent-based architecture in phases:

### Phase 1: Foundation (Week 1-2)
1. Create base agent framework (`agents/base_agent.py`)
2. Implement RPC client wrappers for monerod and wallet
3. Set up shared state mechanisms (file-based communication)
4. Create minimal proof-of-concept with one agent type

### Phase 2: Core Agents (Week 3-4)
1. Implement `regular_user.py` agent
2. Implement `mining_pool.py` agent
3. Implement `block_controller.py` for mining coordination
4. Test with small-scale simulation (10 users)

### Phase 3: Extended Features (Week 5-6)
1. Implement `marketplace.py` agent
2. Add transaction verification and monitoring
3. Implement metrics collection
4. Scale testing (100+ users)

### Phase 4: Integration (Week 7-8)
1. Update Rust configuration generator to create hybrid configs
2. Create configuration templates for different scenarios
3. Full system testing and documentation
4. Performance optimization

## Technical Requirements

1. **Python 3.8+** with virtual environment at `/home/lever65/monerosim_dev/monerosim/venv`
2. **Monero binaries** already customized for Shadow compatibility
3. **Shadow 2.0+** for network simulation
4. **File-based IPC** for agent communication (Shadow-compatible)

## Key Implementation Tasks

### Task 1: Agent Framework
- Create `agents/` directory structure
- Implement `base_agent.py` with lifecycle management
- Create `monero_rpc.py` wrapper for daemon/wallet RPC
- Set up logging and error handling

### Task 2: Regular User Agent
- Implement wallet initialization
- Add transaction sending logic
- Integrate marketplace address discovery
- Add configurable behavior parameters

### Task 3: Mining Coordination
- Implement mining pool registration
- Create block controller logic
- Add mining signal system
- Test coordinated block generation

### Task 4: Rust Integration
- Modify `src/shadow.rs` to generate agent processes
- Update configuration schema
- Create agent configuration templates
- Test end-to-end flow

## Success Criteria

1. Can simulate 100+ regular users sending transactions
2. Mining pools coordinate block generation
3. Marketplaces receive and track payments
4. All within Shadow's constraints
5. Clean logs and metrics for analysis

## Starting Point

Begin with Task 1: Create the agent framework. The existing Python scripts in `scripts/` provide good examples of RPC communication patterns that can be reused.

## Important Notes

- Do NOT attempt to have Python agents launch Monero processes (Shadow constraint)
- Use file-based communication between agents (proven to work in Shadow)
- Reuse existing RPC patterns from current scripts
- Test incrementally within Shadow environment