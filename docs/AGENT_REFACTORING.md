# Agent Architecture Refactoring

This document describes the refactoring of the Monerosim codebase to fully implement the unified agent architecture and remove the concept of "nodes" from the codebase.

## Overview

The Monerosim project has been transitioning from a node-based architecture to an agent-based architecture. This refactoring completes that transition by ensuring consistent terminology throughout the codebase.

## Changes Made

### 1. Consistent Naming Convention

- Renamed all variables, parameters, and file names from "node" to "agent"
- Updated comments and log messages to use agent terminology
- Ensured consistent naming across Rust and Python code

### 2. Updated Host Generation

- Refactored functions in `shadow_agents.rs` to use agent terminology
- Updated host generation logic with consistent naming
- Added helper function to find agents by role

### 3. Registry File Renaming

- Renamed `node_registry.json` to `agent_registry.json`
- Updated all code references to the registry file
- Added backward compatibility to support legacy code

### 4. Dynamic Agent References

- Replaced hardcoded references with dynamic lookups where possible
- Added backward compatibility for both registry formats

### 5. Block Controller Updates

- Updated all references to node registry in the block controller
- Updated functions to use agent terminology consistently

## Files Modified

1. `src/shadow_agents.rs` - Primary file with most node references
2. `agents/base_agent.py` - References to node registry
3. `agents/block_controller.py` - References to node registry and node terminology
4. `scripts/network_config.py` - Updated registry access functions
5. `scripts/test_agent_registration.py` - Updated test file
6. `scripts/monitor.py` - Updated monitoring script

## Backward Compatibility

To ensure backward compatibility, the following measures were implemented:

1. **Dual Registry Files**: The system now writes both `agent_registry.json` and `node_registry.json` (for backward compatibility)
2. **Legacy Function Support**: Added wrapper functions like `get_node_registry()` that call the new `get_agent_registry()` function
3. **Flexible Field Access**: Code now checks for both old and new field names (e.g., `agent.get("agent_rpc_port") or agent.get("node_rpc_port")`)
4. **Command-line Argument Support**: Scripts that accepted `--nodes` now also accept `--agents` with a deprecation warning

## Testing

To test the refactored code, follow these steps:

1. **Basic Functionality Test**:
   ```bash
   rm -rf shadow.data && shadow shadow_agents_output/shadow_agents.yaml
   ```

2. **Verify Registry Files**:
   - Check that both `agent_registry.json` and `node_registry.json` are created
   - Verify that they contain the same information

3. **Test Python Scripts**:
   ```bash
   python scripts/monitor.py --once
   ```

4. **Test Block Controller**:
   - Verify that the block controller can read the agent registry
   - Verify that mining works correctly

## Known Issues

- Some hardcoded references may still exist in less frequently used code paths
- The transition is not complete in all documentation files
- Some test files may still use node terminology

## Future Work

1. **Complete Documentation Update**: Update all documentation to use agent terminology
2. **Remove Legacy Support**: In a future version, remove backward compatibility for node terminology
3. **Standardize Registry Format**: Ensure consistent field names in the registry