# MoneroSim Configuration Reference

This document provides a complete reference for all configuration options available in MoneroSim.

## Configuration File Format

MoneroSim uses YAML configuration files to define simulation parameters.

## Configuration Schema

### Top-Level Structure

```yaml
general:
  # General simulation parameters
  stop_time: string
  fresh_blockchain: bool (optional)
  log_level: string (optional)

network:
  # Network topology parameters
  type: string (optional)

agents:
  # Agent definitions
  user_agents: [UserAgent] (optional)
  block_controller: BlockController (optional)
  pure_script_agents: [PureScriptAgent] (optional)
```

## General Configuration

### `general.stop_time`

**Type**: `string`  
**Required**: Yes  
**Description**: Specifies how long the simulation should run.
**Format**: Human-readable time duration string (e.g., "30s", "5m", "1h").

### `general.fresh_blockchain`

**Type**: `bool`  
**Required**: No  
**Default**: `true`  
**Description**: If `true`, clears existing blockchain data before starting the simulation.

### `general.log_level`

**Type**: `string`  
**Required**: No  
**Default**: `info`  
**Description**: Sets the log level for the simulation. Options are `trace`, `debug`, `info`, `warn`, `error`.

## Network Configuration

MoneroSim supports two network topology types: switch-based networks for simple configurations and GML-based networks for complex, realistic topologies.

### Switch-Based Networks

#### `network.type`

**Type**: `string`
**Required**: No
**Default**: `"1_gbit_switch"`
**Description**: Defines the network topology for switch-based networks.
**Options**:
- `"1_gbit_switch"`: All nodes connected to a 1 Gbit switch
- Other Shadow-supported network types

**Example**:
```yaml
network:
  type: "1_gbit_switch"
```

### GML-Based Networks

#### `network.path`

**Type**: `string`
**Required**: Yes (when using GML topology)
**Description**: Path to the GML topology file that defines the network structure.

**Example**:
```yaml
network:
  path: "topology.gml"
```

## Peer Discovery Configuration

Monerosim supports advanced peer discovery modes that control how Monero nodes connect to each other in the network.

### `network.peer_mode`

**Type**: `string`
**Required**: No
**Default**: `"Hardcoded"`
**Description**: Controls how peers are discovered and connected.
**Options**:
- `"Dynamic"`: Automatic intelligent seed selection based on agent characteristics
- `"Hardcoded"`: Explicit seed nodes with topology-based connection patterns
- `"Hybrid"`: Combines topology connections with peer discovery

### `network.topology`

**Type**: `string`
**Required**: No
**Default**: `"Dag"`
**Description**: Defines the network topology pattern for peer connections.
**Options**:
- `"Star"`: All nodes connect to a central hub
- `"Mesh"`: Fully connected network (all nodes connect to all others)
- `"Ring"`: Circular connections between nodes
- `"Dag"`: Hierarchical connections (traditional blockchain pattern)

### `network.seed_nodes`

**Type**: `array[string]`
**Required**: No
**Default**: `[]`
**Description**: List of explicit seed node IP addresses for peer discovery.

## Peer Discovery Modes

### Dynamic Mode Configuration

```yaml
network:
  type: "1_gbit_switch"
  peer_mode: "Dynamic"  # Automatic seed selection
  topology: "Mesh"      # Topology still applies to connection patterns
```

**Features**:
- Intelligent seed selection based on mining capability, network centrality, and geographic distribution
- No manual seed configuration required
- Automatic optimization for realistic network behavior

### Hardcoded Mode Configuration

```yaml
network:
  type: "1_gbit_switch"
  peer_mode: "Hardcoded"
  topology: "Star"
  seed_nodes:
    - "192.168.1.10:28080"
    - "192.168.1.11:28080"
```

**Features**:
- Explicit control over seed nodes
- Structured topology patterns
- Predictable and reproducible connections

### Hybrid Mode Configuration

```yaml
network:
  path: "topology.gml"
  peer_mode: "Hybrid"
  topology: "Ring"
  seed_nodes:
    - "10.0.0.10:28080"
```

**Features**:
- Combines structured topology with dynamic discovery
- DNS discovery support for maximum connectivity
- Robust peer connections with controlled structure

## Topology Templates

Monerosim provides pre-built topology templates that define structured patterns for peer connections:

### Star Topology
- **Description**: All nodes connect to a central hub (first agent)
- **Requirements**: Minimum 2 agents
- **Use Case**: Centralized networks, hub-and-spoke architectures
- **Performance**: Excellent for large networks (low connection overhead)

### Mesh Topology
- **Description**: Every node connects to every other node
- **Requirements**: Any number of agents (warns for >50 agents)
- **Use Case**: Fully connected networks, maximum redundancy
- **Performance**: High overhead, best for small networks (≤10 agents)

### Ring Topology
- **Description**: Nodes connect in a circular pattern
- **Requirements**: Minimum 3 agents
- **Use Case**: Circular communication patterns, token ring networks
- **Performance**: Moderate overhead, good for structured communication

### DAG Topology (Default)
- **Description**: Hierarchical connections based on agent index
- **Requirements**: Any number of agents
- **Use Case**: Traditional blockchain networks, default behavior
- **Performance**: Good performance, traditional patterns

### Topology Validation

The system validates topology requirements at configuration time:

```yaml
# Valid Star topology (≥2 agents)
network:
  peer_mode: "Hardcoded"
  topology: "Star"

# Valid Ring topology (≥3 agents)
network:
  peer_mode: "Hardcoded"
  topology: "Ring"

# Warning for Mesh with many agents
network:
  peer_mode: "Hardcoded"
  topology: "Mesh"  # Warning if >50 agents
```

#### GML File Format

GML (Graph Modeling Language) files define complex network topologies with nodes, edges, and attributes:

```gml
graph [
  # Graph-level attributes (optional)
  directed 1

  # Network nodes with attributes
  node [ id 0 AS "65001" label "US-West" bandwidth "1000Mbit" ip "192.168.1.1" ]
  node [ id 1 AS "65001" label "US-East" bandwidth "500Mbit" ]
  node [ id 2 AS "65002" label "EU-Central" bandwidth "200Mbit" ]

  # Network connections with attributes
  edge [ source 0 target 1 latency "10ms" bandwidth "1Gbit" ]
  edge [ source 1 target 2 latency "50ms" bandwidth "100Mbit" packet_loss "0.1%" ]
  edge [ source 2 target 0 latency "75ms" bandwidth "10Mbit" ]
]
```

#### Supported GML Attributes

##### Node Attributes
- **`id`** (required): Unique numeric identifier
- **`AS`** or **`as`** (optional): Autonomous System number for grouping
- **`label`** (optional): Human-readable name
- **`ip`**, **`ip_addr`**, **`address`**, **`ip_address`** (optional): Pre-assigned IP address
- **`bandwidth`**, **`bandwidth_up`**, **`bandwidth_down`** (optional): Node bandwidth limits
- **`packet_loss`** (optional): Node-level packet loss percentage

##### Edge Attributes
- **`source`** (required): Source node ID
- **`target`** (required): Target node ID
- **`latency`** (optional): Link latency (default: "10ms")
- **`bandwidth`** (optional): Link bandwidth (default: "1000Mbit")
- **`packet_loss`** (optional): Link packet loss percentage

#### AS-Aware IP Assignment

When using GML topologies, MoneroSim automatically assigns IP addresses based on Autonomous System (AS) numbers:

| AS Number | Subnet Range | Starting IP |
|-----------|--------------|-------------|
| 65001 | 10.0.0.0/24 | 10.0.0.10 |
| 65002 | 192.168.0.0/24 | 192.168.0.10 |
| 65003 | 172.16.0.0/24 | 172.16.0.10 |

**IP Assignment Priority**:
1. **Pre-assigned IPs**: If a node has an IP attribute in the GML file, it's used directly
2. **AS-aware assignment**: IPs are assigned based on the node's AS number
3. **Sequential fallback**: For nodes without AS attributes

#### Agent Distribution in GML Networks

Agents are distributed across GML network nodes intelligently:

- **Multi-AS Distribution**: Agents are distributed proportionally across AS groups
- **Load Balancing**: Ensures even distribution within AS groups
- **Fallback Strategy**: Uses round-robin distribution when no AS information is available

**Example Distribution**:
```rust
AS 65001: [Node 0, Node 1] -> Agents [0, 2, 4]
AS 65002: [Node 2, Node 3] -> Agents [1, 3, 5]
```

## Agent Configuration

MoneroSim's configuration system works in conjunction with the [`agent_discovery.py`](scripts/agent_discovery.md) module to provide dynamic agent discovery during simulation. The YAML configuration defines the initial agent setup, while the agent discovery system enables agents to dynamically find and interact with each other during runtime.

### `agents.user_agents`

**Type**: `array[UserAgent]`
**Required**: No
**Description**: A list of user agents to simulate. These agents will be automatically registered with the agent discovery system at runtime.

#### UserAgent Object

```yaml
- daemon: "monerod"
  wallet: "monero-wallet-rpc" (optional)
  user_script: "agents.regular_user" (optional)
  attributes:
    is_miner: "true" | "false" | "1" | "0" | "yes" | "no" | "on" | "off" (optional, boolean indicator for miners)
    hashrate: "50" (optional, for miners, percentage of total network hashrate)
    can_receive_distributions: "true" | "false" | "1" | "0" | "yes" | "no" | "on" | "off" (optional, boolean indicator for receiving mining distributions)
    transaction_interval: "60" (optional, for users, seconds between transactions)
    min_transaction_amount: "0.1" (optional, for users, minimum XMR for transactions)
    max_transaction_amount: "1.0" (optional, for users, maximum XMR for transactions)
```

#### `attributes.can_receive_distributions`

**Type**: `string` (boolean)
**Required**: No
**Default**: `false`
**Description**: Determines whether an agent can receive mining distributions from the Miner Distributor Agent. When set to true, the agent will be eligible to receive distributed mining rewards.

**Supported Formats**: The attribute supports multiple boolean formats (case-insensitive):
- `"true"` or `"false"`
- `"1"` or `"0"`
- `"yes"` or `"no"`
- `"on"` or `"off"`

**Behavior**:
- When `can_receive_distributions` is set to a true value, the agent will be included in the recipient pool for mining distributions
- When `can_receive_distributions` is set to a false value or not specified, the agent will not receive mining distributions
- If no agents have `can_receive_distributions` set to true, the Miner Distributor Agent will fall back to distributing to all agents

**Examples**:
```yaml
# Agent that can receive distributions
- daemon: "monerod"
  wallet: "monero-wallet-rpc"
  user_script: "agents.regular_user"
  attributes:
    can_receive_distributions: "true"
    transaction_interval: "60"

# Agent that cannot receive distributions
- daemon: "monerod"
  wallet: "monero-wallet-rpc"
  user_script: "agents.regular_user"
  attributes:
    can_receive_distributions: "false"
    transaction_interval: "60"

# Agent using different boolean format
- daemon: "monerod"
  wallet: "monero-wallet-rpc"
  user_script: "agents.regular_user"
  attributes:
    can_receive_distributions: "yes"
    transaction_interval: "60"

# Agent without the attribute (defaults to false)
- daemon: "monerod"
  wallet: "monero-wallet-rpc"
  user_script: "agents.regular_user"
  attributes:
    transaction_interval: "60"
```

### `agents.block_controller`

**Type**: `BlockController`
**Required**: No
**Description**: Configures the block controller agent. The block controller is automatically discoverable by other agents through the agent discovery system.

#### BlockController Object

```yaml
script: "agents.block_controller"
arguments: (optional)
  - "--interval 120"
  - "--blocks 1"
```

### `agents.pure_script_agents`

**Type**: `array[PureScriptAgent]`
**Required**: No
**Description**: Agents that run a simple script without a daemon or wallet. These agents can also be discovered by other agents through the agent discovery system.

#### PureScriptAgent Object

```yaml
- script: "scripts.monitor"
  arguments: [] (optional)
```

## Agent Discovery Integration

The configuration system integrates with the [`agent_discovery.py`](scripts/agent_discovery.md) module to provide dynamic agent discovery during simulation:

- **Automatic Registration**: All agents defined in the configuration are automatically registered in the shared state files (`/tmp/monerosim_shared/agent_registry.json`)
- **Dynamic Discovery**: Agents can discover each other at runtime using the `AgentDiscovery` class
- **Agent Classification**: Agents are automatically classified by type (miners, users, wallets, block controllers)
- **Shared State**: Agent information is stored in shared JSON files for coordination between agents

For more details on using the agent discovery system, see [`scripts/README_agent_discovery.md`](scripts/README_agent_discovery.md).

## Complete Examples

### Dynamic Mode Example

```yaml
general:
  stop_time: "30m"
  fresh_blockchain: true
  log_level: info

network:
  type: "1_gbit_switch"
  peer_mode: "Dynamic"  # Intelligent automatic seed selection
  topology: "Mesh"      # Topology pattern for connections

agents:
  user_agents:
    # High-priority seed (miner with high hashrate)
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "60"

    # Medium-priority seed (miner with medium hashrate)
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "30"

    # Regular user (lower priority)
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        can_receive_distributions: "true"
        transaction_interval: "60"

  block_controller:
    script: "agents.block_controller"

  pure_script_agents:
    - script: "scripts.monitor"
    - script: "scripts.sync_check"
```

### Hardcoded Mode with Star Topology Example

```yaml
general:
  stop_time: "30m"
  fresh_blockchain: true
  log_level: info

network:
  type: "1_gbit_switch"
  peer_mode: "Hardcoded"
  topology: "Star"
  seed_nodes:
    - "192.168.1.10:28080"  # Central hub seed

agents:
  user_agents:
    # Central hub (first agent becomes the center)
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "50"

    # Spoke nodes (connect only to central hub)
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "25"

    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "25"

    # Regular users
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        can_receive_distributions: "true"
        transaction_interval: "60"

  block_controller:
    script: "agents.block_controller"

  pure_script_agents:
    - script: "scripts.monitor"
    - script: "scripts.sync_check"
```

### Hybrid Mode with GML Network Example

```yaml
general:
  stop_time: "45m"
  fresh_blockchain: true
  log_level: info

network:
  path: "topology.gml"
  peer_mode: "Hybrid"
  topology: "Ring"
  seed_nodes:
    - "10.0.0.10:28080"
    - "192.168.0.10:28080"

agents:
  user_agents:
    # Agents distributed across GML network nodes
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "40"

    - daemon: "monerod"
      wallet: "monerod"
      attributes:
        is_miner: "true"
        hashrate: "30"

    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        can_receive_distributions: "true"
        transaction_interval: "60"

    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        can_receive_distributions: "true"
        transaction_interval: "90"

  block_controller:
    script: "agents.block_controller"

  pure_script_agents:
    - script: "scripts.monitor"
    - script: "scripts.sync_check"
```

### Switch-Based Network Example

```yaml
general:
  stop_time: "30m"
  fresh_blockchain: true
  log_level: info

network:
  type: "1_gbit_switch"

agents:
  user_agents:
    # Miner 1
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "50"
    
    # Miner 2
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "50"

    # Regular User that can receive distributions
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        can_receive_distributions: "true"
        transaction_interval: "60"
        min_transaction_amount: "0.1"
        max_transaction_amount: "1.0"
    
    # Regular User that cannot receive distributions
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        can_receive_distributions: "false"
        transaction_interval: "90"
        min_transaction_amount: "0.05"
        max_transaction_amount: "0.5"
    
    # Miner Distributor Agent
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.miner_distributor"
      attributes:
        transaction_frequency: "60"
        min_transaction_amount: "0.1"
        max_transaction_amount: "1.0"
        miner_selection_strategy: "weighted"
        transaction_priority: "1"
        max_retries: "3"
        recipient_selection: "random"

  block_controller:
    script: "agents.block_controller"
    
  pure_script_agents:
    - script: "scripts.monitor"
    - script: "scripts.sync_check"
```

### GML-Based Network Example

```yaml
general:
  stop_time: "30m"
  fresh_blockchain: true
  log_level: info

network:
  path: "topology.gml"

agents:
  user_agents:
    # Miner 1 (will be assigned to AS 65001 node)
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "50"

    # Miner 2 (will be assigned to AS 65002 node)
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: "true"
        hashrate: "50"

    # Regular User in AS 65001
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        can_receive_distributions: "true"
        transaction_interval: "60"
        min_transaction_amount: "0.1"
        max_transaction_amount: "1.0"

    # Regular User in AS 65002
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        can_receive_distributions: "true"
        transaction_interval: "90"
        min_transaction_amount: "0.05"
        max_transaction_amount: "0.5"

  block_controller:
    script: "agents.block_controller"

  pure_script_agents:
    - script: "scripts.monitor"
    - script: "scripts.sync_check"
```

### Corresponding GML Topology File (`topology.gml`)

```gml
graph [
  # Multi-AS topology with realistic network characteristics
  directed 1

  # AS 65001 nodes (US region)
  node [ id 0 AS "65001" label "US-West" bandwidth "1000Mbit" ]
  node [ id 1 AS "65001" label "US-East" bandwidth "500Mbit" ip "10.0.0.100" ]

  # AS 65002 nodes (EU region)
  node [ id 2 AS "65002" label "EU-Central" bandwidth "200Mbit" ]
  node [ id 3 AS "65002" label "EU-North" bandwidth "100Mbit" ]

  # Inter-AS connections (higher latency)
  edge [ source 0 target 2 latency "100ms" bandwidth "100Mbit" ]
  edge [ source 1 target 3 latency "80ms" bandwidth "200Mbit" ]

  # Intra-AS connections (lower latency)
  edge [ source 0 target 1 latency "20ms" bandwidth "1Gbit" ]
  edge [ source 2 target 3 latency "10ms" bandwidth "500Mbit" ]
]
```

### GML with Pre-assigned IPs Example

```gml
graph [
  # Topology with some pre-assigned IP addresses
  node [ id 0 AS "65001" ip "192.168.1.10" label "Miner-Node" ]
  node [ id 1 AS "65001" label "User-Node-1" ]  # Will get 10.0.0.10
  node [ id 2 AS "65002" ip_addr "172.16.1.100" label "User-Node-2" ]
  node [ id 3 AS "65002" label "User-Node-3" ]  # Will get 192.168.0.10

  # Network connections
  edge [ source 0 target 1 latency "10ms" bandwidth "1Gbit" ]
  edge [ source 1 target 2 latency "50ms" bandwidth "100Mbit" ]
  edge [ source 2 target 3 latency "25ms" bandwidth "500Mbit" ]
  edge [ source 3 target 0 latency "75ms" bandwidth "50Mbit" ]
]
```

**Note**: In the GML example above:
- Node 0: Uses pre-assigned IP `192.168.1.10`
- Node 1: Gets AS-aware IP `10.0.0.10` (first available in AS 65001)
- Node 2: Uses pre-assigned IP `172.16.1.100`
- Node 3: Gets AS-aware IP `192.168.0.10` (first available in AS 65002)