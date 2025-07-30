# Monerosim Configuration Architecture Design

## Executive Summary

This document proposes a comprehensive redesign of the Monerosim configuration system to properly support both traditional node-based simulations and agent-based simulations. The current system has fundamental design issues where agent parameters are split between CLI arguments and YAML files, with the YAML parser expecting traditional node configurations even in agent mode.

## Current State Analysis

### Problems with Current Implementation

1. **Rigid Configuration Structure**: The `Config` struct requires both `general` and `nodes` sections, making it incompatible with agent-based configurations
2. **Split Configuration Sources**: Agent parameters come from CLI args while other settings come from YAML
3. **Misleading Configuration Files**: Medium/large agent configs use an aspirational format that isn't implemented
4. **Poor User Experience**: Users must understand the workaround of adding dummy nodes for agent configs
5. **Limited Extensibility**: Adding new agent types or parameters requires modifying CLI argument parsing

### Current Architecture

```rust
// Current inflexible structure
pub struct Config {
    pub general: General,
    pub nodes: Vec<NodeConfig>,  // Required, causing issues
}
```

## Proposed Architecture

### Design Principles

1. **Unified Configuration**: All settings should be configurable via YAML files
2. **Mode Separation**: Clear distinction between traditional and agent modes
3. **Backward Compatibility**: Existing traditional configs must continue to work
4. **Extensibility**: Easy to add new agent types and parameters
5. **CLI Override**: CLI arguments can override YAML settings for flexibility
6. **Validation**: Strong validation with helpful error messages

### Configuration Schema Design

#### 1. Unified Configuration Structure

```rust
// New flexible configuration structure
#[derive(Debug, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Config {
    Traditional(TraditionalConfig),
    Agent(AgentConfig),
}

// Traditional mode configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct TraditionalConfig {
    pub general: GeneralConfig,
    pub nodes: Vec<NodeConfig>,
}

// Agent mode configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct AgentConfig {
    pub general: GeneralConfig,
    pub network: Option<NetworkConfig>,
    pub agents: AgentDefinitions,
    pub block_generation: Option<BlockGenerationConfig>,
}

// Shared general configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct GeneralConfig {
    pub stop_time: String,
    pub fresh_blockchain: Option<bool>,
    pub python_venv: Option<String>,
    pub log_level: Option<String>,
}

// Agent definitions
#[derive(Debug, Serialize, Deserialize)]
pub struct AgentDefinitions {
    pub regular_users: RegularUserConfig,
    pub marketplaces: MarketplaceConfig,
    pub mining_pools: MiningPoolConfig,
    pub custom_agents: Option<Vec<CustomAgentConfig>>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct RegularUserConfig {
    pub count: u32,
    pub transaction_interval: Option<u32>,
    pub min_transaction_amount: Option<f64>,
    pub max_transaction_amount: Option<f64>,
    pub wallet_settings: Option<WalletSettings>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct MarketplaceConfig {
    pub count: u32,
    pub payment_processing_delay: Option<u32>,
    pub wallet_settings: Option<WalletSettings>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct MiningPoolConfig {
    pub count: u32,
    pub mining_threads: Option<u32>,
    pub pool_fee: Option<f64>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct BlockGenerationConfig {
    pub interval: u32,
    pub pools_per_round: u32,
    pub difficulty_adjustment: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct NetworkConfig {
    #[serde(rename = "type")]
    pub network_type: String,
    pub bandwidth: Option<String>,
    pub latency: Option<String>,
}
```

#### 2. Configuration File Formats

**Traditional Configuration (config.yaml)**:
```yaml
# Traditional node-based simulation
general:
  stop_time: "3h"
  fresh_blockchain: true
  python_venv: /path/to/venv

nodes:
  - name: "A0"
    ip: "11.0.0.1"
    port: 28080
    mining: true
    fixed_difficulty: 1
  - name: "A1"
    ip: "11.0.0.2"
    port: 28080
```

**Agent Configuration (config_agents_medium.yaml)**:
```yaml
# Agent-based simulation
general:
  stop_time: "30m"
  fresh_blockchain: true
  log_level: info

network:
  type: simple
  bandwidth: "1Gbps"
  latency: "10ms"

agents:
  regular_users:
    count: 10
    transaction_interval: 60
    min_transaction_amount: 0.1
    max_transaction_amount: 5.0
    wallet_settings:
      initial_balance: 100.0
      
  marketplaces:
    count: 3
    payment_processing_delay: 5
    
  mining_pools:
    count: 2
    mining_threads: 1
    
block_generation:
  interval: 60
  pools_per_round: 1
  difficulty_adjustment: "fixed"
```

### CLI and YAML Interaction Rules

1. **Mode Detection**:
   - If config contains `nodes` section → Traditional mode
   - If config contains `agents` section → Agent mode
   - CLI `--agents` flag forces agent mode (for backward compatibility)

2. **Parameter Priority** (highest to lowest):
   - CLI arguments (explicit overrides)
   - YAML configuration values
   - Default values in code

3. **CLI Override Behavior**:
   ```bash
   # YAML defines 10 users, CLI overrides to 50
   monerosim --config config_agents_medium.yaml --users 50
   
   # Use YAML for all settings
   monerosim --config config_agents_large.yaml
   
   # Force agent mode with traditional config (uses defaults)
   monerosim --config config.yaml --agents
   ```

### Implementation Strategy

#### Phase 1: Parser Enhancement
1. Create new configuration structures
2. Implement untagged enum deserialization
3. Add configuration validation
4. Maintain backward compatibility

#### Phase 2: Mode Detection
1. Implement automatic mode detection
2. Add validation for mode-specific requirements
3. Provide clear error messages for invalid configs

#### Phase 3: CLI Integration
1. Update CLI argument handling
2. Implement override logic
3. Add configuration merging

#### Phase 4: Migration Support
1. Create migration tool for old configs
2. Update documentation
3. Add deprecation warnings

### Migration Path

1. **Immediate Compatibility**:
   - Existing traditional configs continue to work unchanged
   - Small agent config with dummy nodes continues to work
   
2. **Transition Period**:
   - Support both old and new formats
   - Log deprecation warnings for dummy node workaround
   - Provide migration guide

3. **Future State**:
   - Remove support for dummy node workaround
   - All configs use appropriate format for their mode

### Error Handling and Validation

```rust
impl Config {
    pub fn validate(&self) -> Result<(), ValidationError> {
        match self {
            Config::Traditional(cfg) => {
                // Validate nodes have unique IPs
                // Validate port ranges
                // Check mining node exists
            }
            Config::Agent(cfg) => {
                // Validate agent counts > 0
                // Validate transaction amounts
                // Check block generation settings
            }
        }
    }
}
```

Example error messages:
```
Error: Invalid agent configuration
  - regular_users.count must be greater than 0
  - block_generation.interval must be at least 30 seconds
  - marketplaces.count (3) cannot exceed regular_users.count (2)
```

### Extensibility Features

1. **Custom Agent Types**:
   ```yaml
   agents:
     regular_users:
       count: 10
     custom_agents:
       - type: "exchange"
         count: 2
         script: "agents/exchange.py"
         parameters:
           trading_pairs: ["XMR/USD", "XMR/BTC"]
   ```

2. **Agent Templates**:
   ```yaml
   templates:
     power_user:
       base: regular_user
       transaction_interval: 30
       min_transaction_amount: 10.0
       
   agents:
     regular_users:
       count: 8
     power_users:
       template: power_user
       count: 2
   ```

3. **Environment-Specific Overrides**:
   ```yaml
   general:
     stop_time: "1h"
     
   environments:
     development:
       general:
         stop_time: "5m"
       agents:
         regular_users:
           count: 2
   ```

## Benefits of Proposed Architecture

1. **Unified Configuration**: All settings in one place, no more split between CLI and YAML
2. **Clear Separation**: Distinct configuration formats for different simulation modes
3. **Better UX**: No more dummy nodes workaround, intuitive configuration
4. **Extensible**: Easy to add new agent types and parameters
5. **Backward Compatible**: Existing configs continue to work
6. **Type Safety**: Strong typing prevents configuration errors
7. **Flexible**: CLI overrides for quick testing without editing files

## Implementation Recommendations

1. **Start with Parser**: Implement new configuration structures first
2. **Add Tests**: Comprehensive tests for all configuration scenarios
3. **Gradual Migration**: Support both formats during transition
4. **Documentation First**: Update docs before releasing changes
5. **User Feedback**: Beta test with key users before full release

## Example Usage After Implementation

```bash
# Traditional simulation (unchanged)
monerosim --config config.yaml

# Agent simulation with YAML config
monerosim --config config_agents_medium.yaml

# Agent simulation with CLI overrides
monerosim --config config_agents_small.yaml --users 20 --marketplaces 5

# Quick test with minimal config
echo "general: {stop_time: 5m}" | monerosim --config - --agents --users 2
```

## Conclusion

This architecture provides a clean, extensible solution that addresses all current issues while maintaining backward compatibility. It creates a foundation for future enhancements and provides a better user experience for both traditional and agent-based simulations.