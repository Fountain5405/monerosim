# Monerosim Scaling Report - 32GB System

**Date:** 2026-01-06
**Hardware:** 31GB RAM, 24 CPUs, 4GB Swap
**Shadow Version:** 3.2.0
**Simulation Duration:** 4 hours simulated time

## Executive Summary

Testing determined that **75-100 agents** is the practical maximum for a 32GB system, depending on network topology size. The primary memory constraint is monerod processes, each consuming ~300MB RSS.

## Test Results

### Successful Tests

| Agents | GML Nodes | GML Edges | Wall Time | Shadow RSS | System RAM | Status |
|--------|-----------|-----------|-----------|------------|------------|--------|
| 50     | 50        | 244       | 21:06     | 315MB      | ~15GB      | SUCCESS |
| 100    | 50        | 244       | 40:48     | 312MB      | ~25GB      | SUCCESS |
| 75     | 150       | 672       | 30:54     | 324MB      | ~25GB      | SUCCESS |

### Failed Tests

| Agents | GML Nodes | Failure Mode | Notes |
|--------|-----------|--------------|-------|
| 125    | 50        | OOM Killed   | Exceeded available RAM |
| 100    | 150       | Swap Thrash  | 30GB used, 3.6GB swap, severely degraded |
| 150    | -         | Expected OOM | Not tested, would require ~45GB |
| 200    | -         | Expected OOM | Not tested, would require ~60GB |

## Memory Analysis

### Per-Agent Memory Footprint

Each Monero agent consists of:
- **monerod:** ~300MB RSS (dominant cost)
- **monero-wallet-rpc:** ~50MB RSS
- **Python scripts:** ~30MB RSS
- **Total per agent:** ~380MB

### Memory Scaling Formula

```
Estimated RAM = (Agents × 300MB) + 2GB overhead
```

| Agents | Estimated RAM | Fits in 32GB? |
|--------|---------------|---------------|
| 50     | 17GB          | Yes |
| 75     | 24.5GB        | Yes |
| 100    | 32GB          | Marginal |
| 125    | 39.5GB        | No |

### GML Topology Impact

Larger GML files add memory overhead for Shadow's network simulation:
- 50-node GML: Minimal overhead
- 150-node GML: ~1-2GB additional overhead
- 2000-node GML: Untested (file had missing self-loops)

## GML File Compatibility

Shadow requires self-loops on all nodes for shortest path computation.

| File | Nodes | Edges | Self-loops | Status |
|------|-------|-------|------------|--------|
| `caida_connected_sparse_with_loops_fixed.gml` | 50 | 244 | Yes | Working |
| `150_nodes_caida_with_loops.gml` | 150 | 672 | Yes | Working |
| `intermediate_global_caida.gml` | 2000 | 47,550 | No | Fails |
| `test_5000_nodes_caida_undirected_selfloops.gml` | 5000 | 65,815 | Yes | Untested |

**Note:** Use `gml_processing/create_caida_connected_with_loops.py` to generate GML files with self-loops:
```bash
python3 gml_processing/create_caida_connected_with_loops.py \
    gml_processing/cycle-aslinks.l7.t1.c008040.20200101.txt \
    output.gml \
    --max_nodes 150
```

## Configuration

### Test Configuration
- 5 fixed miners (hashrates: 25, 25, 30, 10, 10)
- Variable users starting at 1h mark (after block unlock)
- Users staggered 1 second apart
- Dynamic peer mode
- DNS server enabled

### Generate Custom Configs
```bash
# 75 agents with 150-node network
python3 scripts/generate_config.py \
    --agents 75 \
    --gml gml_processing/150_nodes_caida_with_loops.gml \
    -o config_75.yaml
```

## Recommendations

### For 32GB Systems
- **Safe maximum:** 75 agents with 150-node GML
- **Aggressive maximum:** 100 agents with 50-node GML (tight on memory)
- **Avoid:** 125+ agents (will OOM or swap thrash)

### For Larger Simulations
| Target Agents | Recommended RAM |
|---------------|-----------------|
| 100           | 40GB            |
| 150           | 50GB            |
| 200           | 64GB            |
| 500           | 160GB           |

### Performance Tips
1. Close other applications before running simulations
2. Monitor swap usage with `free -h` during runs
3. Use smaller GML files when possible (reduces overhead)
4. Kill stuck simulations early if swap exceeds 1GB

## Reproduction

```bash
# Run the full scaling test suite
./scripts/scaling_test.sh

# Or run individual tests manually
python3 scripts/generate_config.py --agents 75 --gml gml_processing/150_nodes_caida_with_loops.gml -o test.yaml
./target/release/monerosim --config test.yaml --output /tmp/shadow_out
shadow /tmp/shadow_out/shadow_agents.yaml
```

## Files Generated

- `scaling_results.txt` - Raw scaling test output
- `gml_processing/150_nodes_caida_with_loops.gml` - New 150-node topology
- `/tmp/shadow_*` - Temporary shadow configurations

---
*Report generated from monerosim scaling tests on 2026-01-06*
