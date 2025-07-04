# MoneroSim Configuration Reference

This document provides a complete reference for all configuration options available in MoneroSim.

## Configuration File Format

MoneroSim uses YAML configuration files to define simulation parameters. The default configuration file is `config.yaml` in the project root.

## Basic Example

```yaml
# Basic MoneroSim configuration
general:
  stop_time: "10m"

monero:
  nodes:
    - count: 5
      name: "A"
      base_commit: "shadow-complete"
```

## Configuration Schema

### Top-Level Structure

```yaml
general:
  # General simulation parameters
  stop_time: string

monero:
  # Monero-specific configuration
  nodes: [NodeType]
```

## General Configuration

### `general.stop_time`

**Type**: `string`  
**Required**: Yes  
**Description**: Specifies how long the simulation should run.

**Format**: Human-readable time duration string

**Examples**:
```yaml
general:
  stop_time: "30s"     # 30 seconds
  stop_time: "5m"      # 5 minutes
  stop_time: "1h"      # 1 hour
  stop_time: "2h30m"   # 2 hours and 30 minutes
  stop_time: "3600s"   # 3600 seconds (1 hour)
```

**Valid Units**:
- `s` - seconds
- `m` - minutes
- `h` - hours
- `d` - days

**Recommendations**:
- **Testing**: `30s` to `2m` for quick validation
- **Development**: `5m` to `10m` for feature testing
- **Research**: `30m` to `2h` for meaningful network analysis
- **Long-term studies**: `4h+` for network evolution analysis

## Monero Configuration

### `monero.nodes`

**Type**: `array[NodeType]`  
**Required**: Yes  
**Description**: List of node type definitions that specify different Monero node configurations.

### NodeType Object

Each node type represents a group of identical Monero nodes with specific configurations.

```yaml
- count: number
  name: string
  base_commit: string (optional)
  patches: [string] (optional)
  prs: [number] (optional)
```

#### `count`

**Type**: `number`  
**Required**: Yes  
**Range**: 1-1000 (limited by system resources)  
**Description**: Number of nodes to create of this type.

**Performance Considerations**:
- **1-10 nodes**: Minimal resource usage, good for development
- **10-50 nodes**: Moderate resource usage, suitable for most research
- **50+ nodes**: High resource usage, requires powerful hardware

#### `name`

**Type**: `string`  
**Required**: Yes  
**Pattern**: `^[a-zA-Z][a-zA-Z0-9_]*$`  
**Description**: Unique identifier for the node type. Used for build directories and node naming.

**Node Naming Convention**:
- Individual nodes are named: `{name}{index}` (e.g., `A0`, `A1`, `bootstrap0`)
- Build directories: `builds/{name}/`
- Log files: `shadow.data/hosts/{name}{index}/`

#### `base_commit`

**Type**: `string`  
**Required**: No  
**Default**: Current branch of `../monero-shadow`  
**Description**: Git commit, branch, or tag to checkout for this node type.

**Examples**:
```yaml
nodes:
  # Use the consolidated shadow-complete branch (recommended)
  - base_commit: "shadow-complete"
  
  # Use a specific Monero version tag
  - base_commit: "v0.18.4.0"
  
  # Use a specific commit hash
  - base_commit: "8a490dfbc2e4c1c8b4d2e3f1a5b6c7d8e9f0a1b2"
  
  # Use a specific branch
  - base_commit: "shadow-fork/feature-branch"
```

**Common Values**:
- `"shadow-complete"`: Recommended for most simulations (includes all Shadow modifications)
- `"shadow-compatibility"`: Legacy branch with basic Shadow support
- `"shadow-disable-seeds"`: Branch with seed node disabling functionality
- `"v0.18.4.0"`: Official Monero release (requires additional patches)

#### `patches`

**Type**: `array[string]`  
**Required**: No  
**Description**: List of patch files to apply after checking out the base commit.

**Examples**:
```yaml
nodes:
  # Apply a single patch
  - patches:
      - "patches/custom_modification.patch"
  
  # Apply multiple patches in order
  - patches:
      - "patches/performance_optimization.patch"
      - "patches/debug_logging.patch"
      - "patches/custom_feature.patch"
  
  # No patches (use base commit as-is)
  - patches: []
```

**Patch File Requirements**:
- Must be valid git patch files
- Applied in the order specified
- Path is relative to MoneroSim project root
- Must be compatible with the specified `base_commit`

#### `prs`

**Type**: `array[number]`  
**Required**: No  
**Description**: List of GitHub pull request numbers to merge after checking out the base commit.

**Examples**:
```yaml
nodes:
  # Merge a single PR
  - prs: [1234]
  
  # Merge multiple PRs
  - prs: [1234, 5678, 9012]
  
  # No PRs
  - prs: []
```

**Important Notes**:
- PRs are fetched from the official Monero repository
- PRs are merged in the order specified
- Conflicts must be resolved manually if they occur
- Only works with open or merged PRs that are accessible

## Complete Configuration Examples

### Simple Configuration

```yaml
# Minimal configuration for quick testing
general:
  stop_time: "5m"

monero:
  nodes:
    - count: 3
      name: "A"
      base_commit: "shadow-complete"
```

### Multi-Node Type Configuration

```yaml
# Configuration with different node types
general:
  stop_time: "30m"

monero:
  nodes:
    # Bootstrap node with latest features
    - count: 1
      name: "bootstrap"
      base_commit: "shadow-complete"
    
    # Standard nodes
    - count: 10
      name: "standard"
      base_commit: "shadow-complete"
    
    # Legacy nodes for compatibility testing
    - count: 5
      name: "legacy"
      base_commit: "v0.18.3.0"
      patches:
        - "patches/shadow_compatibility.patch"
```

### Research Configuration

```yaml
# Advanced configuration for research scenarios
general:
  stop_time: "2h"

monero:
  nodes:
    # Control group - standard nodes
    - count: 20
      name: "control"
      base_commit: "shadow-complete"
    
    # Experimental group - with modifications
    - count: 20
      name: "experimental"
      base_commit: "shadow-complete"
      patches:
        - "patches/experimental_feature.patch"
    
    # Adversarial nodes for attack simulation
    - count: 5
      name: "adversarial"
      base_commit: "shadow-complete"
      patches:
        - "patches/modified_behavior.patch"
```

## Configuration Best Practices

### 1. Start Small

Begin with small simulations and scale up:

```yaml
# Development
general:
  stop_time: "2m"
monero:
  nodes:
    - count: 2
      name: "dev"

# Testing
general:
  stop_time: "10m"
monero:
  nodes:
    - count: 5
      name: "test"

# Production
general:
  stop_time: "1h"
monero:
  nodes:
    - count: 50
      name: "prod"
```

### 2. Use Meaningful Names

Choose descriptive node type names:

```yaml
# Good
nodes:
  - name: "bootstrap"
  - name: "miners"
  - name: "regular_users"
  - name: "v18_4_nodes"

# Avoid
nodes:
  - name: "A"
  - name: "1"
  - name: "test123"
```

### 3. Document Your Configuration

Add comments to explain your simulation setup:

```yaml
# Network split simulation - testing consensus behavior
general:
  stop_time: "1h"  # Long enough for network to stabilize

monero:
  nodes:
    # Group A - isolated network partition
    - count: 25
      name: "partition_a"
      base_commit: "shadow-complete"
    
    # Group B - main network
    - count: 50
      name: "partition_b"
      base_commit: "shadow-complete"
```

## Troubleshooting Configuration Issues

### Common Problems

1. **Invalid time format**:
   ```yaml
   # Wrong
   stop_time: "10 minutes"
   
   # Correct
   stop_time: "10m"
   ```

2. **Missing base_commit for patches**:
   ```yaml
   # Specify base_commit when using patches
   - base_commit: "shadow-complete"
     patches: ["patches/custom.patch"]
   ```

3. **Node name conflicts**:
   ```yaml
   # Each node type must have a unique name
   nodes:
     - name: "A"
     - name: "B"  # Not "A" again
   ```

### Debugging Tips

1. **Validate early**: Always test with small configurations first
2. **Check logs**: Look for validation errors in MoneroSim output
3. **Verify paths**: Ensure patch files and repositories exist
4. **Test incremental**: Add complexity gradually

## Configuration File Templates

### Template: Basic Network

```yaml
# Basic network simulation template
general:
  stop_time: "10m"

monero:
  nodes:
    - count: 5
      name: "nodes"
      base_commit: "shadow-complete"
```

### Template: Multi-Version Testing

```yaml
# Multi-version compatibility testing
general:
  stop_time: "30m"

monero:
  nodes:
    - count: 5
      name: "v18_3"
      base_commit: "v0.18.3.0"
      patches: ["patches/shadow_compatibility.patch"]
    
    - count: 5
      name: "v18_4"
      base_commit: "v0.18.4.0"
      patches: ["patches/shadow_compatibility.patch"]
    
    - count: 5
      name: "latest"
      base_commit: "shadow-complete"
```

### Template: Large Scale Simulation

```yaml
# Large scale network simulation
general:
  stop_time: "2h"

monero:
  nodes:
    - count: 1
      name: "bootstrap"
      base_commit: "shadow-complete"
    
    - count: 100
      name: "network"
      base_commit: "shadow-complete"
```
