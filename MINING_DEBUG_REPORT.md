# Monerosim Agent-Based Mining Debug Report

## Issue Summary

The agent-based simulation was failing to generate blocks because the `block_controller` agent could not find the required `miners.json` file in `/tmp/monerosim_shared/`.

## Root Cause Analysis

### 1. Missing miners.json File

The `block_controller` agent requires a `miners.json` file that contains:
- List of potential miners (agent IDs)
- Their wallet addresses
- Their hash rates for weighted selection

### 2. Configuration System Design Gap

Investigation revealed a design gap in the configuration system:

1. **New Config Format (`config_v2.rs`)**: Does not include a `mining` field in either `TraditionalConfig` or `AgentConfig` structs.

2. **Compatibility Layer (`config_compat.rs`)**: When converting from new to old format, explicitly sets `mining: None`:
   ```rust
   // Line 18 for Traditional configs
   mining: None,
   
   // Line 33 for Agent configs  
   mining: None,
   ```

3. **Shadow Agents Generator (`shadow_agents.rs`)**: Checks for mining configuration:
   ```rust
   if let Some(mining_config) = &config.mining {
       // Generate miners.json
   }
   ```
   Since `config.mining` is always `None`, this code is never executed.

### 3. Impact

- The `mining` section in YAML configuration files is completely ignored
- `miners.json` is never generated
- Block controller fails with "file not found" error
- No blocks are generated in the simulation

## Workaround Solution

### Manual miners.json Creation

1. Create the shared directory:
   ```bash
   mkdir -p /tmp/monerosim_shared
   ```

2. Create `miners.json` with valid wallet addresses:
   ```json
   [
     {
       "agent_id": "user000",
       "wallet_address": "46ceMyuUTsqKMCZpykzzRAEZvimNpMYEYT47hZsJ5MUCSHNwcJommGpQLm67VpRtYyGCi2fwy2EqrcR7yqroxThyUgBYdk7",
       "hash_rate": 50
     },
     {
       "agent_id": "node000",
       "wallet_address": "4AYjQM9HoAFNUeC3cvSfgeAN8CftS49ekzgGyqvuPcKwFqPGcyEXCKyQH8KhQK9mJAxnwQcKBGWd7cHVBnJjZMzaRqp7vkZ",
       "hash_rate": 30
     },
     {
       "agent_id": "node001",
       "wallet_address": "44ovmrJHgyX3DzMxBAtAw8MqnKe47jaBZAQSzBKHgQVqbEcBWxQ5P5uCrrkJBh9ADb6Fh1zyRJZhUUvnWBVXbvV8K9C4Ede",
       "hash_rate": 20
     }
   ]
   ```

3. Run the simulation - blocks are now generated successfully!

## Verification

After applying the workaround, the block controller logs show:
- "Loaded 3 miners from registry"
- "Selected winning miner: [agent_id] with hash rate [rate]"
- "Successfully generated 1 blocks for [agent_id]"
- "New height: [increasing block height]"

## Permanent Fix Options

### Option 1: Update Configuration System (Recommended)

1. Add `mining` field to `AgentConfig` in `config_v2.rs`
2. Update `config_compat.rs` to properly convert mining configuration
3. Ensure YAML parser handles the mining section

### Option 2: Alternative Approach

1. Move mining configuration into the `block_generation` section of `AgentConfig`
2. Update `shadow_agents.rs` to read from this new location
3. Generate `miners.json` based on agent definitions with hash rate attributes

### Option 3: Dynamic Generation

1. Have agents register themselves as miners at runtime
2. Block controller discovers available miners dynamically
3. No pre-generated `miners.json` needed

## Lessons Learned

1. **Configuration Migration**: When updating configuration systems, ensure all fields are properly migrated
2. **Error Messages**: The block controller's error message was clear and helpful for debugging
3. **Workarounds**: Manual file creation can be an effective temporary solution
4. **Testing**: Need integration tests that verify all configuration sections are processed

## Next Steps

1. Apply the workaround for immediate functionality
2. Create a proper fix in the Rust codebase
3. Add tests to prevent regression
4. Update documentation to reflect the mining configuration requirements