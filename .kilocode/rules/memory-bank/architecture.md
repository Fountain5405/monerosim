# Monerosim Architecture

## System Overview
Rust tool generating Shadow simulator configs for Monero network simulations with Python agent framework for autonomous behaviors.

## Core Components

### 1. Rust Configuration Engine (`src/`)
**Purpose**: Parse YAML → Generate Shadow configuration

**Key Modules**:
- `main.rs:112` - CLI entry point (clap argument parser)
- `config_v2.rs:292` - Type-safe config structures (serde YAML/JSON)
- `config_loader.rs:87` - Config file loading and migration
- `shadow_agents.rs:2525` - Shadow YAML generation + network topology
- `gml_parser.rs:1004` - GML graph parser for complex topologies

**Key Functions**:
- IP allocation with geographic distribution (6 continents)
- Peer connection configuration (Dynamic/Hardcoded/Hybrid)
- Validation and error handling
- Registry generation (agents, miners)

### 2. Python Agent Framework (`agents/`)
**Purpose**: Autonomous network participants

**Agent Types**:
- `base_agent.py` - Abstract base class with lifecycle management
- `regular_user.py` - Transaction-generating users
- `block_controller.py` - Mining orchestration
- `miner_distributor.py` - Mining reward distribution
- `simulation_monitor.py` - Real-time simulation monitoring
- `agent_discovery.py` - Dynamic agent discovery (5-sec TTL cache)
- `monero_rpc.py` - RPC client library

**Communication**: Shared state via `/tmp/monerosim_shared/` JSON files

### 3. Shadow Network Simulator Integration
Monerosim generates configs that Shadow executes:
- Network topology (switch or GML-based)
- Host definitions with IP addresses
- Process configurations (monerod, monero-wallet-rpc, agents)
- Peer connections
- Start time scheduling

### 4. Testing Infrastructure
- **Python**: `tests/` (pytest, 95%+ coverage)
  - `test_ip_allocation.py` - IP assignment validation
  - `test_reproducibility.py` - Determinism checks
  - `test_sparse_placement.py` - Large topology agent placement
  - `test_backward_compatibility.py` - Config migration

- **Scripts**: `scripts/` (external analysis)
  - `sync_check.py`, `log_processor.py`, `analyze_*.py`

### 5. Topology Generation (`gml_processing/`)
- CAIDA AS-links based topologies
- Geographic IP distribution
- Scalable 50-5000 node generation
- `create_large_scale_caida_gml.py`, `create_global_caida_internet.py`

## Network Architecture

### Two Topology Modes

**Switch-Based** (Simple):
```yaml
network:
  type: "1_gbit_switch"
```
- High performance, uniform connectivity
- Best for development/testing

**GML-Based** (Realistic):
```yaml
network:
  path: "topology.gml"
```
- AS-aware agent distribution
- Variable bandwidth/latency/packet-loss per link
- Multi-hop routing, complex topologies

### Peer Discovery System

**Three Modes**:
1. **Dynamic**: Intelligent seed selection (miners prioritized)
2. **Hardcoded**: Explicit topology templates (Star/Mesh/Ring/DAG)
3. **Hybrid**: GML topology + discovery elements

**Topologies**: Star (hub-spoke), Mesh (fully connected), Ring (circular), DAG (blockchain default)

### IP Allocation Strategy
Geographic distribution across 6 continents:
```rust
// Example from shadow_agents.rs
region = agent_number % 6
match region {
  0 => (10, subnet, "North America"),
  1 => (172, 16+subnet, "Europe"),
  2 => (203, subnet, "Asia"),
  3 => (200, subnet, "South America"),
  4 => (197, subnet, "Africa"),
  5 => (202, subnet, "Oceania"),
}
```

## Data Flow

1. User creates `config.yaml` (network type, agents, peer mode, topology)
2. Rust parses YAML → validates → loads GML if specified
3. Agent distribution (AS-aware for GML, round-robin for switch)
4. Generate Shadow YAML + registries (`agent_registry.json`, `miners.json`)
5. Shadow executes simulation
6. Agents coordinate via shared state files
7. Post-simulation analysis via scripts

## Agent Communication
Decentralized coordination via shared state:
```
/tmp/monerosim_shared/
├── agent_registry.json      # All agents + attributes
├── miners.json               # Hashrate weights
├── block_controller.json     # Mining status
├── transactions.json         # Transaction log
└── [agent]_stats.json        # Per-agent stats
```

## GML Format Support
```gml
graph [
  node [ id 0 AS "65001" bandwidth "1Gbit" ]
  edge [ source 0 target 1 latency "10ms" bandwidth "100Mbit" ]
]
```
**Features**: AS grouping, bandwidth/latency/packet-loss modeling, connectivity validation

## Key Design Decisions

1. **Rust Core**: Memory safety, performance, strong typing for config
2. **Python Agents**: Rapid development, RPC libraries, research accessibility
3. **Custom GML Parser**: Lightweight, Shadow-optimized, full control
4. **Dual Topology Support**: Performance (switch) vs realism (GML) trade-off
5. **AS-Aware Distribution**: Realistic internet structure modeling
6. **Shadow Integration**: Run actual Monero code (high fidelity) vs simplified models

## File Paths

**Source**:
- `/src/main.rs`, `config_v2.rs`, `gml_parser.rs`, `shadow_agents.rs`

**Agents**:
- `/agents/base_agent.py`, `block_controller.py`, `regular_user.py`, `monero_rpc.py`, `agent_discovery.py`

**Scripts**:
- `/scripts/sync_check.py`, `log_processor.py`, `analyze_*.py`

**Config**:
- `/config_*.yaml` (examples), `/testnet.gml` (example topology)

**Generated**:
- `/shadow_output/shadow_agents.yaml`
- `/tmp/monerosim_shared/*.json`

## Performance Scaling
- Small (2-10 agents): Near real-time
- Medium (10-50 agents): 2-5x slowdown
- Large (50-100+ agents): Significant slowdown, high resources

**Optimizations**: Staggered startup, shared state batching, connection pooling, configurable logging
