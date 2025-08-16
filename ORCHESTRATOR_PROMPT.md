# Monerosim Attributes-Only Migration Implementation

## Task Overview

Implement a complete transition from boolean-based to attributes-only `is_miner` configuration in Monerosim. This is a direct migration with no backward compatibility - all existing configurations must be converted to use the attributes-only approach.

## First Step: Read the Analysis Report

Before beginning implementation, you MUST read the comprehensive analysis report at `ATTRIBUTE_ANALYSIS_REPORT.md`. This document contains:

1. **Current State Analysis**: Detailed explanation of why the attributes-only approach currently fails
2. **Root Cause Analysis**: Specific code locations and issues that need to be addressed
3. **Complete 4-Phase Transition Plan**: Step-by-step approach with clear deliverables
4. **Implementation Strategy**: Specific file changes and code modifications needed
5. **Risk Mitigation**: Strategies to ensure smooth transition
6. **Testing Approach**: Comprehensive testing strategy

## Implementation Requirements

### Phase 1: Create Migration Script
1. Create a Python script to convert existing configurations from boolean-based to attributes-only
2. The script should:
   - Read YAML configuration files
   - Move `is_miner: true/false` from the top level to `attributes: { is_miner: "true"/"false" }`
   - Create the attributes section if it doesn't exist
   - Preserve all other configuration options
   - Test the script with both `config_that_works.yaml` and `config_in_desired_attributes_style_but_doesnt_work.yaml`

### Phase 2: Update Configuration Schema
1. Modify `src/config_v2.rs`:
   - Remove the boolean `is_miner` field from `UserAgentConfig` struct
   - Add `is_miner_value()` helper function that checks attributes for `is_miner`
   - Update any validation logic

### Phase 3: Update Configuration Generation Logic
1. Modify `src/shadow_agents.rs`:
   - Replace all instances of `user_agent_config.is_miner.unwrap_or(false)` with `user_agent_config.is_miner_value()`
   - Update agent registry population logic
   - Remove attribute filtering that prevents `is_miner` from being passed to agents
   - Ensure all 9 references to boolean `is_miner` are properly updated

### Phase 4: Update Agent Framework
1. Modify `agents/base_agent.py`:
   - Extract `is_miner` from attributes during initialization
   - Add `is_miner` property to agent class

2. Modify `agents/regular_user.py`:
   - Use `is_miner` attribute for behavior determination
   - Update setup logic to handle miner vs. regular user configuration

### Testing Requirements
1. Create comprehensive tests to verify:
   - Migration script correctly converts configurations
   - Configuration parsing works with attributes-only approach
   - Agent framework properly handles `is_miner` from attributes
   - End-to-end simulation works with converted configurations

2. Test with both small and large configuration files

## Order of Operations
1. First, read and understand the `ATTRIBUTE_ANALYSIS_REPORT.md`
2. Create and test the migration script
3. Update configuration schema in `src/config_v2.rs`
4. Update configuration generation logic in `src/shadow_agents.rs`
5. Update agent framework in `agents/`
6. Run comprehensive tests
7. Verify end-to-end functionality

## Important Notes
- This is a complete transition with NO backward compatibility
- All existing configurations MUST be converted before code changes
- The migration script should be tested thoroughly before implementing code changes
- Follow the specific code changes outlined in the analysis report

## Deliverables
1. Working migration script
2. Updated configuration schema (no boolean `is_miner`)
3. Updated configuration generation logic
4. Updated agent framework
5. Comprehensive tests
6. Verification that attributes-only configuration works end-to-end

Begin by reading the `ATTRIBUTE_ANALYSIS_REPORT.md` file to understand the full scope of this migration.