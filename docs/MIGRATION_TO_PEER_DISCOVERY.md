# Migration Guide: Peer Discovery Configuration

This guide helps existing Monerosim users migrate their configurations to use the new peer discovery modes and topology templates.

## Overview

The new peer discovery system introduces three modes (Dynamic, Hardcoded, Hybrid) and four topology templates (Star, Mesh, Ring, DAG) that enhance network realism and control.

## Migration Steps

### Step 1: Backup Your Configurations

Before making changes, backup your existing configuration files:

```bash
cp config.yaml config.yaml.backup
cp config_agents_small.yaml config_agents_small.yaml.backup
```

### Step 2: Add Peer Discovery Options

Add the new peer discovery options to your network configuration:

#### For Switch-Based Networks

```yaml
# Before
network:
  type: "1_gbit_switch"

# After
network:
  type: "1_gbit_switch"
  peer_mode: "Hardcoded"  # or "Dynamic" or "Hybrid"
  topology: "Dag"        # or "Star", "Mesh", "Ring"
  seed_nodes: []         # optional, for explicit seeds
```

#### For GML-Based Networks

```yaml
# Before
network:
  path: "topology.gml"

# After
network:
  path: "topology.gml"
  peer_mode: "Hybrid"    # recommended for GML networks
  topology: "Ring"       # optional, defaults to "Dag"
  seed_nodes: []         # optional
```

### Step 3: Choose Appropriate Settings

#### For Research and Realism
Use Dynamic mode for automatic optimization:

```yaml
network:
  type: "1_gbit_switch"
  peer_mode: "Dynamic"
  topology: "Mesh"
```

#### For Controlled Experiments
Use Hardcoded mode with specific topology:

```yaml
network:
  type: "1_gbit_switch"
  peer_mode: "Hardcoded"
  topology: "Star"
  seed_nodes:
    - "192.168.1.10:28080"
```

#### For Complex Networks
Use Hybrid mode with GML:

```yaml
network:
  path: "topology.gml"
  peer_mode: "Hybrid"
  topology: "Ring"
```

## Migration Examples

### Example 1: Basic Switch Network

**Before:**
```yaml
network:
  type: "1_gbit_switch"
```

**After:**
```yaml
network:
  type: "1_gbit_switch"
  peer_mode: "Hardcoded"
  topology: "Dag"
```

### Example 2: GML Network

**Before:**
```yaml
network:
  path: "topology.gml"
```

**After:**
```yaml
network:
  path: "topology.gml"
  peer_mode: "Hybrid"
  topology: "Dag"
```

### Example 3: Advanced Configuration

**Before:**
```yaml
network:
  type: "1_gbit_switch"
```

**After (with Dynamic mode):**
```yaml
network:
  type: "1_gbit_switch"
  peer_mode: "Dynamic"
  topology: "Mesh"
```

## Topology Selection Guide

### Choose Star Topology When:
- You have a central authoritative node
- You want simple, hierarchical connections
- Network size > 20 agents
- You need predictable performance

### Choose Mesh Topology When:
- You need maximum redundancy
- Network size ≤ 10 agents
- You want fully connected behavior
- Performance is less critical than connectivity

### Choose Ring Topology When:
- You need circular communication patterns
- Network size ≥ 3 agents
- You want structured but distributed connections

### Choose DAG Topology When:
- You want traditional blockchain behavior
- You have any number of agents
- You prefer default, proven patterns

## Peer Mode Selection Guide

### Dynamic Mode
- **Best for:** Research, optimization, realism
- **When to use:** When you want automatic seed selection
- **Pros:** Intelligent, adaptive, no manual configuration
- **Cons:** Less predictable, may vary between runs

### Hardcoded Mode
- **Best for:** Testing, validation, reproducibility
- **When to use:** When you need exact control over connections
- **Pros:** Predictable, reproducible, explicit
- **Cons:** Manual configuration required

### Hybrid Mode
- **Best for:** Production-like simulations
- **When to use:** When combining structure with discovery
- **Pros:** Robust, flexible, realistic
- **Cons:** More complex configuration

## Validation and Testing

After migration, validate your configuration:

```bash
# Test configuration parsing
./target/release/monerosim --config config.yaml --validate-only

# Run a short test simulation
./target/release/monerosim --config config.yaml --output test_output
shadow test_output/shadow_agents.yaml
```

## Troubleshooting

### Common Issues

1. **"Topology requires minimum agents"**
   - Star: Need ≥2 agents
   - Ring: Need ≥3 agents
   - Solution: Add more agents or change topology

2. **"Invalid peer mode"**
   - Check spelling: "Dynamic", "Hardcoded", "Hybrid"
   - Solution: Correct the peer_mode value

3. **"Seed nodes not allowed in Dynamic mode"**
   - Dynamic mode doesn't use explicit seed_nodes
   - Solution: Remove seed_nodes or change to Hardcoded/Hybrid mode

4. **Performance warnings**
   - Mesh with >50 agents shows warning
   - Solution: Consider Star topology for large networks

### Getting Help

- Check the [Configuration Guide](CONFIGURATION.md) for detailed options
- Review [Topology Features](TOPOLOGY_FEATURES.md) for advanced usage
- Test with small configurations first

## Backward Compatibility

The new peer discovery system is fully backward compatible:

- Existing configurations work unchanged
- New options are optional with sensible defaults
- No breaking changes to existing functionality
- Migration can be done incrementally

## Best Practices After Migration

1. **Start Small**: Test with small agent counts first
2. **Monitor Performance**: Use different topologies and measure impact
3. **Validate Results**: Ensure simulation behavior meets expectations
4. **Document Changes**: Keep track of configuration changes for reproducibility

## Advanced Migration

For complex migrations, consider:

1. **Gradual Rollout**: Migrate one configuration at a time
2. **A/B Testing**: Compare old vs new configurations
3. **Performance Benchmarking**: Measure impact of different settings
4. **Documentation Updates**: Update your research documentation

## Support

If you encounter issues during migration:

1. Check the logs for specific error messages
2. Review the configuration examples in this guide
3. Test with minimal configurations first
4. Refer to the main documentation for detailed explanations

---

**Note**: This migration guide assumes you have the latest version of Monerosim with peer discovery support. If you're using an older version, please update first.