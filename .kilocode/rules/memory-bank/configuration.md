# Monerosim Configuration Guide

## Configuration Structure

All configurations use YAML format with unified agent-based model:

```yaml
general:
  stop_time: "3h"           # Simulation duration
  fresh_blockchain: true     # Start from genesis
  log_level: info           # trace/debug/info/warn/error

network:
  # Option 1: Simple switch network
  type: "1_gbit_switch"

  # Option 2: Complex GML topology
  path: "topology.gml"

  # Peer discovery mode
  peer_mode: "Dynamic"      # Dynamic/Hardcoded/Hybrid

  # Network topology
  topology: "Mesh"          # Star/Mesh/Ring/DAG

  # Optional: explicit seeds (Hardcoded/Hybrid only)
  seed_nodes:
    - "192.168.1.10:28080"

agents:
  user_agents:
    # Miner example
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"  # Required for miners
      attributes:
        is_miner: true              # Boolean
        hashrate: "25"              # % of total hashrate
        can_receive_distributions: true

    # Regular user example
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "60"
        min_transaction_amount: "0.5"
        max_transaction_amount: "2.0"

  block_controller:
    script: "agents.block_controller"

  pure_script_agents:
    - script: "scripts.monitor"
```

## Peer Discovery Modes

**Dynamic** - Auto seed selection, miners prioritized
- Best for: Research, optimization
- Pros: Intelligent, no manual config
- Cons: Less predictable

**Hardcoded** - Explicit topology templates
- Best for: Testing, validation
- Pros: Predictable, reproducible
- Cons: Manual configuration

**Hybrid** - GML topology + discovery
- Best for: Production-like sims
- Pros: Robust, flexible
- Cons: Complex config

## Network Topologies

**Star**: All connect to hub (first agent). Min: 2 agents
**Mesh**: Fully connected. Min: 2 agents, slow >50
**Ring**: Circular connections. Min: 3 agents
**DAG**: Blockchain default. Min: 2 agents

## Important Rules

1. **Miners need wallet**: Both daemon + wallet required
2. **No `nodes` section**: Legacy format deprecated
3. **Hashrate sum**: Should equal 100 across all miners
4. **Distribution eligibility**: `can_receive_distributions` boolean
5. **IP auto-assigned**: System handles geographic distribution
6. **Boolean formats**: true/false, "true"/"false", 1/0, "yes"/"no", "on"/"off"

## Example Configurations

The working configuation, scale (30 agents): `config_30_agents.yaml`
