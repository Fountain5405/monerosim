# Monerosim Configuration Architecture Analysis: Complete Transition to Attributes-Only

## Executive Summary

This document provides a comprehensive analysis of the current Monerosim configuration system, specifically focusing on the transition from the boolean `is_miner` field to an attributes-only approach. The analysis reveals why the attributes-only approach currently fails and provides a detailed transition plan to migrate the entire codebase to use attributes exclusively, with no backward compatibility.

## Current State Analysis

### 1. Configuration Parsing Architecture

#### Current Configuration Schema (`src/config_v2.rs`)

The current configuration schema in `src/config_v2.rs` defines the `UserAgentConfig` struct with both a boolean `is_miner` field and an `attributes` section:

```rust
#[derive(Debug, Serialize, Deserialize)]
pub struct UserAgentConfig {
    pub daemon: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_script: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_miner: Option<bool>,         // Boolean field (current approach)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attributes: Option<HashMap<String, String>>,  // Attributes section
}
```

#### Working Configuration Style

The working configuration uses a boolean `is_miner` field plus an `attributes` section:

```yaml
# Miner 3
- daemon: "monerod"
  wallet: "monero-wallet-rpc"
  is_miner: true                          # Boolean field
  attributes:
    hashrate: "20"                        # Additional attributes
```

#### Desired Configuration Style (Currently Not Working)

The desired attributes-only approach moves `is_miner` into the attributes section:

```yaml
# Miner 5 - 10% hashrate
- daemon: "monerod"
  wallet: "monero-wallet-rpc"
  attributes:
    is_miner: "true"                      # String in attributes
    hashrate: "10"                        # Additional attributes
```

### 2. Configuration Generation Logic

#### Key Components in `src/shadow_agents.rs`

The configuration generation logic in `src/shadow_agents.rs` has several critical dependencies on the boolean `is_miner` field:

1. **Miner Detection** (Line 325):
   ```rust
   let is_miner = user_agent_config.is_miner.unwrap_or(false);
   ```

2. **Seed Node Selection** (Line 341):
   ```rust
   if i < 2 || is_miner {
       seed_agents.push(format!("{}:{}", agent_ip, agent_port));
   }
   ```

3. **User Script Assignment** (Line 376):
   ```rust
   let user_script = user_agent_config.user_script.clone().unwrap_or_else(|| {
       if is_miner {
           "agents.regular_user".to_string()
       } else {
           "agents.regular_user".to_string()
       }
   });
   ```

4. **Agent Registry Population** (Lines 609-618):
   ```rust
   let is_miner = user_agent_config.is_miner.unwrap_or(false);
   // ...
   let mut attributes = user_agent_config.attributes.clone().unwrap_or_default();
   if is_miner {
       attributes.insert("is_miner".to_string(), "true".to_string());
   }
   ```

5. **Miner Registry Population** (Line 648):
   ```rust
   if user_agent_config.is_miner.unwrap_or(false) {
       // Add to miner registry
   }
   ```

#### Critical Issue: Attribute Filtering

The configuration generation logic explicitly filters out `is_miner` and `hashrate` from attributes when creating agent arguments (Line 283):

```rust
} else if key != "is_miner" && key != "hashrate" {
    // Pass other attributes directly, but filter out is_miner and hashrate
    agent_args.push(format!("--{} {}", key, value));
}
```

This filtering prevents the `is_miner` attribute from being passed to agents when using the attributes-only approach.

### 3. Agent Framework Integration

#### Base Agent Implementation (`agents/base_agent.py`)

The agent framework in `agents/base_agent.py` does not directly reference `is_miner`. Instead, it:

1. Accepts attributes as a list of key-value pairs
2. Converts them to a dictionary
3. Passes them to the agent implementation

#### Block Controller Agent (`agents/block_controller.py`)

The block controller agent:
1. Does not directly use `is_miner`
2. Relies on the miner registry created by the Rust code
3. Uses the `weight` field from the miner registry for weighted selection

#### Regular User Agent (`agents/regular_user.py`)

The regular user agent:
1. Accepts both `tx_frequency` and `hash_rate` parameters
2. Does not directly reference `is_miner`
3. Can function as both a miner and a regular user depending on parameters

### 4. Root Cause Analysis: Why Attributes-Only Approach Fails

#### Primary Issue: Missing Boolean Field Processing

The attributes-only approach fails because the configuration generation logic in `src/shadow_agents.rs` only checks the boolean `is_miner` field and does not check for `is_miner` in the attributes section.

Specifically:

1. **Miner Detection** (Line 325):
   ```rust
   let is_miner = user_agent_config.is_miner.unwrap_or(false);
   ```
   This line only checks the boolean field, not the attributes.

2. **Agent Registry Population** (Lines 609-618):
   ```rust
   let is_miner = user_agent_config.is_miner.unwrap_or(false);
   // ...
   if is_miner {
       attributes.insert("is_miner".to_string(), "true".to_string());
   }
   ```
   This code only adds `is_miner` to attributes if the boolean field is true, creating a circular dependency.

3. **Miner Registry Population** (Line 648):
   ```rust
   if user_agent_config.is_miner.unwrap_or(false) {
   ```
   This only checks the boolean field, not the attributes.

#### Secondary Issue: Type Mismatch

In the working configuration, `is_miner` is a boolean (`true`/`false`), while in the attributes-only approach, it's a string (`"true"`/`"false"`). The current code does not handle this type conversion.

#### Tertiary Issue: Attribute Filtering

The explicit filtering of `is_miner` from attributes (Line 283) prevents the attribute from being passed to agents, even if it were properly detected.

## Transition Plan

### Phase 1: Remove Boolean Field from Configuration Schema

#### 1.1 Update Configuration Schema

Modify `src/config_v2.rs` to remove the boolean `is_miner` field entirely:

```rust
#[derive(Debug, Serialize, Deserialize)]
pub struct UserAgentConfig {
    pub daemon: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wallet: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_script: Option<String>,
    // is_miner boolean field removed - now only in attributes
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attributes: Option<HashMap<String, String>>,
}
```

#### 1.2 Add Helper Function

Add a helper function to check for `is_miner` in attributes:

```rust
impl UserAgentConfig {
    pub fn is_miner_value(&self) -> bool {
        // Check attributes for is_miner
        if let Some(attrs) = &self.attributes {
            if let Some(miner_str) = attrs.get("is_miner") {
                return miner_str == "true" || miner_str == "1";
            }
        }
        
        false
    }
}
```

### Phase 2: Update Configuration Generation Logic

#### 2.1 Replace Boolean Checks

Replace all direct `is_miner` boolean checks with the new helper function:

```rust
// Before
let is_miner = user_agent_config.is_miner.unwrap_or(false);

// After
let is_miner = user_agent_config.is_miner_value();
```

#### 2.2 Update Agent Registry Population

Modify the agent registry population to handle attributes-only approach:

```rust
let is_miner = user_agent_config.is_miner_value();
let mut attributes = user_agent_config.attributes.clone().unwrap_or_default();

// is_miner should already be in attributes from configuration
```

#### 2.3 Remove Attribute Filtering

Remove the filtering logic that prevents `is_miner` from being passed to agents:

```rust
// Before
} else if key != "is_miner" && key != "hashrate" {

// After
} else if key != "hashrate" {  // Allow is_miner to pass through
```

### Phase 3: Update Agent Framework

#### 3.1 Update Base Agent

Modify `agents/base_agent.py` to handle `is_miner` attribute:

```python
def __init__(self, ..., **kwargs):
    # ... existing code ...
    
    # Extract is_miner from attributes
    self.is_miner = self.attributes.get("is_miner", "false").lower() == "true"
    
    # ... rest of initialization ...
```

#### 3.2 Update Regular User Agent

Modify `agents/regular_user.py` to use `is_miner` attribute:

```python
def _setup_agent(self):
    """Agent-specific setup logic"""
    self.logger.info("RegularUserAgent initialized")
    
    if self.is_miner:
        self.logger.info("Agent configured as miner")
    else:
        self.logger.info("Agent configured as regular user")
```

### Phase 4: Migration and Testing

#### 4.1 Create Migration Script

Create a script to convert existing configurations:

```python
#!/usr/bin/env python3
"""
Migration script to convert boolean is_miner to attributes-based is_miner
"""

import yaml
import sys
from pathlib import Path

def migrate_config(input_path: Path, output_path: Path):
    """Migrate configuration from boolean to attributes-only is_miner"""
    
    with open(input_path, 'r') as f:
        config = yaml.safe_load(f)
    
    if 'agents' in config and 'user_agents' in config['agents']:
        for agent in config['agents']['user_agents']:
            # Create attributes section if it doesn't exist
            if 'attributes' not in agent:
                agent['attributes'] = {}
            
            # Move is_miner from boolean to attributes
            if 'is_miner' in agent:
                is_miner_value = agent.pop('is_miner')
                agent['attributes']['is_miner'] = str(is_miner_value).lower()
    
    with open(output_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python migrate_config.py <input> <output>")
        sys.exit(1)
    
    migrate_config(Path(sys.argv[1]), Path(sys.argv[2]))
```

#### 4.2 Test Strategy

1. **Unit Tests**: Test the new helper function and configuration parsing
2. **Integration Tests**: Test attributes-only configuration with expected behavior
3. **End-to-End Tests**: Run full simulations with attributes-only configuration
4. **Performance Tests**: Ensure no performance degradation
5. **Migration Tests**: Verify migration script correctly converts all configurations

## Implementation Strategy

### File Changes Required

1. **`src/config_v2.rs`**:
   - Add `is_miner_value()` helper function
   - Update validation logic

2. **`src/shadow_agents.rs`**:
   - Replace all `is_miner.unwrap_or(false)` with `is_miner_value()`
   - Update agent registry population logic
   - Remove or modify attribute filtering

3. **`agents/base_agent.py`**:
   - Extract `is_miner` from attributes
   - Add `is_miner` property to agent

4. **`agents/regular_user.py`**:
   - Use `is_miner` attribute for behavior determination

5. **New migration script**:
   - Convert existing configurations to attributes-only format

### Order of Operations

1. Update `src/config_v2.rs` with backward compatibility
2. Update `src/shadow_agents.rs` to use new helper function
3. Update agent framework to handle attributes-based `is_miner`
4. Create and test migration script
5. Add comprehensive tests
6. Add deprecation warnings
7. Document the transition

### Risk Mitigation

1. **Backward Compatibility**: Maintain support for boolean `is_miner` during transition
2. **Testing**: Comprehensive test suite to ensure both approaches work
3. **Documentation**: Clear migration guide for users
4. **Performance**: Benchmark to ensure no performance impact
5. **Rollback**: Keep version control to allow rollback if issues arise

## Conclusion

The transition from boolean-based to attributes-only `is_miner` configuration is feasible but requires careful implementation to maintain backward compatibility. The primary issue is that the current configuration generation logic only checks the boolean field and does not properly handle `is_miner` in the attributes section.

By implementing a phased approach with backward compatibility, comprehensive testing, and clear documentation, the transition can be completed successfully with minimal disruption to existing users.