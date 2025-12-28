# Migrating to Autonomous Mining

This guide helps you migrate from the deprecated `block_controller` approach to the new autonomous mining system.

## Why Migrate?

The new autonomous mining system provides:
- **Better reproducibility** via `simulation_seed`
- **More realistic mining** with Poisson distribution
- **Simpler architecture** - no centralized coordinator
- **Better testing** - deterministic, predictable behavior

## Migration Steps

### 1. Automatic Migration

Use the migration utility:
```bash
python scripts/migrate_mining_config.py config.yaml
```

This will:
- Add `simulation_seed` to `general` section
- Add `mining_script: "agents.autonomous_miner"` to all miners
- Remove `block_controller` section
- Create a `.bak` backup of your original file

### 2. Manual Migration

If you prefer manual migration:

**Before**:
```yaml
general:
  stop_time: "1h"

agents:
  block_controller:
    script: "agents.block_controller"
  
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: true
        hashrate: "60"
```

**After**:
```yaml
general:
  simulation_seed: 12345  # ADD THIS
  stop_time: "1h"

# REMOVE block_controller section

agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      mining_script: "agents.autonomous_miner"  # ADD THIS
      attributes:
        is_miner: true
        hashrate: "60"
```

### 3. Verify Migration

After migration, verify:
```bash
# Check config is valid
./target/release/monerosim --config config.yaml --output shadow_output

# Run a short test simulation
shadow shadow_output/shadow_agents.yaml
```

## Key Differences

| Aspect | Block Controller | Autonomous Miner |
|--------|------------------|------------------|
| Coordination | Centralized | Decentralized |
| Reproducibility | Limited | Full (via seed) |
| Block timing | Fixed intervals | Poisson distribution |
| Configuration | Separate section | Per-agent |

## Example Configurations

See working examples:
- [`config_autonomous_mining.yaml`](../config_autonomous_mining.yaml) - Simple 2-miner example
- [`config_30_agents.yaml`](../config_30_agents.yaml) - Multi-miner network

## Troubleshooting

**Problem**: "Mining validation error"
- **Solution**: Ensure all miners have `mining_script` set and both daemon + wallet defined

**Problem**: "Different results each run"
- **Solution**: Set `simulation_seed` in `general` section for reproducibility

**Problem**: "Miners not generating blocks"
- **Solution**: Check that hashrate values sum to 100 across all miners

## Support

For issues or questions:
1. Check [`ind_mining_control_spec.md`](../ind_mining_control_spec.md) for technical details
2. Review test suite in [`tests/test_autonomous_mining.py`](../tests/test_autonomous_mining.py)
3. Open an issue on GitHub