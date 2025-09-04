# Monerosim Agent Framework Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Agent Types](#agent-types)
4. [Communication Architecture](#communication-architecture)
5. [Configuration](#configuration)
6. [Agent Attributes](#agent-attributes)
7. [Running Simulations](#running-simulations)
8. [Shared State Structure](#shared-state-structure)
9. [Agent Behaviors](#agent-behaviors)
10. [Scalability](#scalability)
11. [Troubleshooting](#troubleshooting)
12. [Examples](#examples)
13. [Future Enhancements](#future-enhancements)

## Overview

The Monerosim Agent Framework is a sophisticated simulation capability that enables realistic cryptocurrency network behavior modeling. The agent framework introduces autonomous participants that make independent decisions, creating emergent network behaviors that closely mirror real-world cryptocurrency ecosystems. The framework now includes an Agent Discovery System that dynamically discovers agents and their configurations, replacing the legacy hardcoded network configuration approach.

### Why the Agent Framework?

Traditional network simulations often fail to capture the complex interactions between different types of network participants. The agent framework was created to:

- **Model Realistic Behavior**: Simulate how real users and designated miners interact
- **Enable Emergent Properties**: Allow complex behaviors to emerge from simple agent rules
- **Support Research**: Provide a platform for studying cryptocurrency economics and network dynamics
- **Test at Scale**: Simulate networks from small (2-10 participants) to large (100+ participants)
- **Facilitate Attack Research**: Enable testing of various attack scenarios and defenses

### Key Features

- **Autonomous Agents**: Each agent makes independent decisions based on its role and configuration
- **Scalable Architecture**: Supports simulations from 2 to 100+ participants
- **Realistic Transaction Patterns**: Users send transactions based on configurable patterns
- **Coordinated Mining**: Block generation is orchestrated for consistent blockchain progress
- **Shared State Communication**: Agents coordinate through a decentralized state mechanism
- **Production-Ready**: Fully integrated with Shadow network simulator

## Architecture

The agent framework is built on a modular architecture that separates concerns and enables easy extension. The architecture has been simplified to use a unified agent model where every node is a user_agent with appropriate attributes.

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Framework                          │
├─────────────────────────────────────────────────────────────┤
│  Base Agent Layer (base_agent.py)                          │
│  ├── Lifecycle Management                                   │
│  ├── RPC Connection Handling                                │
│  ├── Shared State Management                                │
│  └── Signal Handling                                        │
├─────────────────────────────────────────────────────────────┤
│  Specialized Agents                                         │
│  ├── Regular User Agent (regular_user.py)                  │
│  └── Block Controller Agent (block_controller.py)          │
├─────────────────────────────────────────────────────────────┤
│  Agent Discovery System (agent_discovery.py)               │
│  ├── Dynamic Agent Discovery                                │
│  ├── Agent Registry Management                             │
│  ├── Shared State File Reading                              │
│  └── Caching and Performance Optimization                   │
├─────────────────────────────────────────────────────────────┤
│  RPC Communication Layer (monero_rpc.py)                   │
│  ├── Daemon RPC Client                                     │
│  ├── Wallet RPC Client                                     │
│  └── Retry Logic & Error Handling                          │
├─────────────────────────────────────────────────────────────┤
│  Shadow Integration (shadow_agents.rs)                     │
│  ├── Configuration Generation                              │
│  ├── Process Orchestration                                 │
│  ├── Network Topology Setup                                │
│  └── Agent Registry Management                             │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Modularity**: Each agent type is self-contained and can be extended independently
2. **Fault Tolerance**: Agents handle failures gracefully and continue operation
3. **Observability**: All agent actions are logged and traceable
4. **Decentralization**: No central control point; agents coordinate through shared state
5. **Realism**: Agent behaviors are modeled after real-world participants

## Agent Types

### Base Agent (base_agent.py)

The abstract base class that provides common functionality for all agents:

**Key Features:**
- Lifecycle management (setup, run, cleanup)
- RPC connection handling for both daemon and wallet
- Shared state read/write operations
- Signal handling for graceful shutdown
- Logging infrastructure
- Common utility methods

**Methods:**
- `setup()`: Initialize RPC connections and agent-specific setup
- `run()`: Main agent loop
- `run_iteration()`: Single iteration of agent behavior (abstract)
- `cleanup()`: Clean up resources before shutdown
- `write_shared_state()`: Write data to shared state files
- `read_shared_state()`: Read data from shared state files
- `wait_for_height()`: Wait for blockchain to reach target height
- `wait_for_wallet_sync()`: Wait for wallet to sync with daemon

### Regular User Agent (regular_user.py)

Represents typical Monero users who maintain wallets and send transactions.

**Characteristics:**
- Maintains a personal wallet
- Sends transactions at configurable intervals
- Monitors transaction confirmations
- Adjusts behavior based on wallet balance

**Configuration Parameters:**
- `transaction_frequency`: Probability of sending transaction per iteration (0.0-1.0)
- `min_amount`: Minimum transaction amount in XMR
- `max_amount`: Maximum transaction amount in XMR
- `can_receive_distributions`: Boolean indicating if agent can receive mining distributions (default: true)

**Behavior Pattern:**
1. Initialize wallet and get address
2. Register address in shared state
3. Periodically check balance
4. Decide whether to send transaction based on frequency parameter
5. Send transaction with random amount within configured range
6. Track pending transactions until confirmed


### Block Controller Agent (block_controller.py)

Orchestrates block generation across the network using a proven approach.

**Implementation Note**: Due to mining RPC limitations, this agent uses the `generateblocks` RPC method directly on the daemon, which is the same approach used in the working `scripts/block_controller.py`.

**Characteristics:**
- Creates its own wallet to get a mining address
- Generates blocks at regular intervals using daemon's `generateblocks` method
- Tracks blockchain progress
- Ensures consistent block generation for the simulation

**Configuration Parameters:**
- `target_block_interval`: Seconds between block generations
- `blocks_per_generation`: Number of blocks to generate each time
- `can_receive_distributions`: Boolean indicating if agent can receive mining distributions (default: true)

**Behavior Pattern:**
1. Create wallet and get mining address
2. Wait for configured interval
3. Generate blocks using daemon RPC
4. Update statistics
5. Repeat until simulation ends

## Communication Architecture

Agents communicate through a shared state mechanism using JSON files in a common directory:

```
/tmp/monerosim_shared/
├── agent_registry.json          # Registry of all agents with attributes
├── miners.json                  # List of all mining agents
├── wallets.json                 # List of all wallet agents
├── users.json                    # List of all user agents
├── block_controller.json        # Block controller status
├── transactions.json            # Transaction log
├── blocks_found.json           # Block discovery log
└── [agent]_stats.json          # Per-agent statistics
```

### Shared State Design

The shared state mechanism enables:

1. **Service Discovery**: Agents can find other agents
2. **Coordination**: Block controller can coordinate block generation
3. **Monitoring**: External tools can observe simulation progress
4. **Analysis**: Researchers can analyze agent interactions

### File Formats

**users.json** - Array of user registrations:
```json
[
  {
    "agent_id": "user001",
    "address": "4A5X...",
    "type": "regular_user",
    "timestamp": 1234567890.123
  }
]
```

**transactions.json** - Array of transaction records:
```json
[
  {
    "sender": "user001",
    "recipient": "user002",
    "amount": 1.5,
    "tx_hash": "abc123...",
    "timestamp": 1234567891.789
  }
]
```

## Configuration

### Agent Configuration Files

Monerosim provides pre-configured agent simulation scales. The configuration has been simplified to use a unified agent architecture where every node is a user_agent with appropriate attributes.

#### Small Scale (config_agents_small.yaml)
```yaml
general:
  stop_time: "60m"
  fresh_blockchain: true
  log_level: debug  # More verbose for debugging

network:
  type: "1_gbit_switch"

agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "30"
        min_transaction_amount: "0.5"
        max_transaction_amount: "2.0"
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "30"
        min_transaction_amount: "0.5"
        max_transaction_amount: "2.0"
    - daemon: "monerod"
      is_miner: true
    
  block_controller:
    script: "agents.block_controller"
    
  pure_script_agents:
    - script: "scripts.monitor"
    - script: "scripts.sync_check"
```

In this configuration:
- Regular user agents have a daemon, wallet, and user script
- Mining nodes are also user agents with the `is_miner` attribute set to true
- All nodes are treated consistently as user_agents with different attributes

### Agent Discovery Integration

The agent discovery system integrates seamlessly with the YAML configuration:

1. **Configuration Parsing**: The `shadow_agents.rs` module parses the YAML configuration and generates the necessary shared state files
2. **Agent Registry**: Creates `agent_registry.json` with all agent information
3. **Specialized Registries**: Creates specialized files like `miners.json` and `wallets.json` for efficient access
4. **Dynamic Discovery**: Agents use the `AgentDiscovery` class to find other agents at runtime

This approach eliminates the need for hardcoded network configurations and allows agents to dynamically discover and interact with each other.

## Agent Attributes

Agent attributes are configuration parameters that define the behavior and capabilities of each agent. These attributes are specified in the YAML configuration files and are used by the agent framework to customize agent behavior.

### Common Attributes

#### can_receive_distributions

The `can_receive_distributions` attribute is a boolean flag that indicates whether an agent can receive mining distributions from the Miner Distributor Agent. This attribute is used by the agent discovery system to filter agents when distributing mining rewards.

**Purpose:**
- Control which agents receive mining distributions
- Enable selective distribution of mining rewards
- Support different economic models in simulations

**Supported Values:**
- `true` or `"true"`: Agent can receive distributions
- `false` or `"false"`: Agent cannot receive distributions
- `"1"` or `"yes"` or `"on"`: Agent can receive distributions (alternative true values)
- `"0"` or `"no"` or `"off"`: Agent cannot receive distributions (alternative false values)

**Default Behavior:**
- If not specified, agents default to `true` (can receive distributions)

**Examples:**
```yaml
# Agent that can receive distributions
- daemon: "monerod"
  wallet: "monero-wallet-rpc"
  user_script: "agents.regular_user"
  attributes:
    transaction_interval: "60"
    min_transaction_amount: "0.5"
    max_transaction_amount: "2.0"
    can_receive_distributions: true

# Agent that cannot receive distributions
- daemon: "monerod"
  wallet: "monero-wallet-rpc"
  user_script: "agents.regular_user"
  attributes:
    transaction_interval: "90"
    min_transaction_amount: "0.1"
    max_transaction_amount: "1.0"
    can_receive_distributions: false

# Using alternative boolean formats
- daemon: "monerod"
  wallet: "monero-wallet-rpc"
  is_miner: true
  attributes:
    hashrate: "25"
    can_receive_distributions: "yes"

- daemon: "monerod"
  wallet: "monero-wallet-rpc"
  is_miner: true
  attributes:
    hashrate: "20"
    can_receive_distributions: "0"
```

**Integration with Miner Distributor Agent:**
The Miner Distributor Agent uses the `can_receive_distributions` attribute to filter agents when distributing mining rewards. Only agents with this attribute set to a truthy value will be included in the distribution list.

**Network Dynamics Impact:**
- Agents that cannot receive distributions will not get mining rewards
- This can create different economic models within the simulation
- Useful for studying scenarios with restricted reward distribution

### Shadow Integration

The `shadow_agents.rs` module generates Shadow configuration that:

1. Creates Monero daemon processes for each user
2. Creates wallet RPC processes for users
3. Launches agent processes with appropriate parameters
4. Sets up network topology with proper IP addressing
5. Configures process start times to ensure proper initialization order

## Running Simulations

### Prerequisites

1. Build Monerosim and Monero binaries:
```bash
./setup.sh
cargo build --release
```

2. Ensure Python environment is set up:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r scripts/requirements.txt
```

### Running Agent-Based Simulations

#### Small Scale Test
```bash
# Generate configuration
./target/release/monerosim --config config_agents_small.yaml --output shadow_agents_output --mode agents

# Run simulation
shadow shadow_agents_output/shadow_agents.yaml
```

#### Medium Scale Test
```bash
./target/release/monerosim --config config_agents_medium.yaml --output shadow_agents_output --mode agents
shadow shadow_agents_output/shadow_agents.yaml
```

#### Large Scale Test
```bash
./target/release/monerosim --config config_agents_large.yaml --output shadow_agents_output --mode agents
shadow shadow_agents_output/shadow_agents.yaml
```

### Monitoring Simulations

While the simulation runs, you can monitor agent activity:

```bash
# Watch shared state files
watch -n 1 'ls -la /tmp/monerosim_shared/'

# Monitor transactions
tail -f /tmp/monerosim_shared/transactions.json

# Check agent statistics
cat /tmp/monerosim_shared/user001_stats.json
```

## Shared State Structure

### Directory Layout

All shared state files are stored in `/tmp/monerosim_shared/`:

```
/tmp/monerosim_shared/
├── Registration Files
│   ├── users.json                 # All registered users
│   ├── agent_registry.json        # Registry of all agents with attributes
│   ├── miners.json                # List of all mining agents
│   └── wallets.json               # List of all wallet agents
│
├── Activity Logs
│   ├── transactions.json         # All transactions sent
│   └── blocks_found.json        # All blocks discovered
│
├── Control Files
│   └── block_controller.json    # Block controller configuration
│
└── Statistics Files
    ├── user_[id]_stats.json     # Per-user statistics
    └── block_controller_stats.json # Block generation statistics
```

The `agent_registry.json` file documents all attributes for every agent (note: `node_registry.json` was renamed to `agent_registry.json`):

```json
{
  "agents": [
    {
      "id": "user001",
      "ip_addr": "11.0.0.10",
      "daemon": true,
      "wallet": true,
      "user_script": "agents.regular_user",
      "is_miner": false,
      "attributes": {
        "transaction_interval": "30",
        "min_transaction_amount": "0.5",
        "max_transaction_amount": "2.0",
        "can_receive_distributions": true
      }
    },
    {
      "id": "node001",
      "ip_addr": "11.0.0.12",
      "daemon": true,
      "wallet": false,
      "user_script": null,
      "is_miner": true,
      "attributes": {}
    }
  ]
}
```

### File Update Patterns

1. **Registration Files**: Append-only during agent initialization
2. **Activity Logs**: Append-only throughout simulation
3. **Control Files**: Updated by block controller
4. **Statistics Files**: Periodically updated by each agent

## Agent Behaviors

### Regular User Behavior

1. **Initialization Phase**:
   - Create or open wallet
   - Get wallet address
   - Register in shared state
   - Wait for initial sync

2. **Transaction Decision Process**:
   ```python
   if balance >= min_amount and random() < transaction_frequency:
       amount = random(min_amount, max_amount)
       send_transaction(amount)
   ```

3. **Transaction Lifecycle**:
   - Create transaction
   - Submit to network
   - Track in pending list
   - Monitor for confirmations
   - Remove from pending when confirmed

### Block Controller Behavior

1. **Setup**:
   - Create wallet for mining address
   - Connect to daemon RPC
   - Register in shared state

2. **Block Generation Loop**:
   ```python
   while running:
       if time_since_last_block >= target_interval:
           generate_blocks(blocks_per_generation)
           update_statistics()
       sleep(1)
   ```

## Scalability

The agent framework is designed to scale from small development tests to large production simulations:

### Performance Characteristics

#### Small Scale (2-10 agents)
- **Resource Usage**: Minimal (< 1GB RAM)
- **Simulation Speed**: Near real-time
- **Use Cases**: Development, testing, debugging
- **Typical Duration**: 10-30 minutes

#### Medium Scale (10-50 agents)
- **Resource Usage**: Moderate (2-4GB RAM)
- **Simulation Speed**: 2-5x slower than real-time
- **Use Cases**: Realistic testing, research
- **Typical Duration**: 1-4 hours

#### Large Scale (50-100+ agents)
- **Resource Usage**: High (8-16GB RAM)
- **Simulation Speed**: 5-10x slower than real-time
- **Use Cases**: Stress testing, large-scale research
- **Typical Duration**: 1-2 hours

### Optimization Strategies

1. **Staggered Startup**: Agents start at different times to prevent resource contention
   ```python
   start_time: format!("{}s", 60 + i * 2)  # 2-second intervals
   ```

2. **Efficient RPC Usage**: Connection pooling and retry logic minimize overhead

3. **Batch State Updates**: Agents can batch multiple state updates

4. **Configurable Logging**: Adjust log levels based on scale:
   - Small: `debug` for detailed analysis
   - Medium: `info` for normal operation
   - Large: `warning` to reduce overhead

## Troubleshooting

### Common Issues and Solutions

#### 1. Mining RPC Methods Not Found

**Issue**: The `start_mining`, `stop_mining`, and `mining_status` RPC methods return "Method not found" errors.

**Cause**: The Monero daemon may not have these RPC methods enabled or they may require different parameters.

**Solution**: The Block Controller Agent uses the `generateblocks` RPC method instead, which is proven to work:
```python
result = self.daemon_rpc._make_request("generateblocks", {
    "amount_of_blocks": self.blocks_per_generation,
    "wallet_address": self.wallet_address
})
```

#### 2. Agents Can't Connect to RPC

**Issue**: Agents fail to connect to daemon or wallet RPC services.

**Cause**: Incorrect IP addresses or ports in configuration.

**Solution**: Ensure the Shadow configuration properly assigns IPs:
```python
# Each agent must use its assigned IP
--rpc-host {} # Use the host's IP, not localhost
```

#### 3. No Transactions Being Sent

**Issue**: Users don't send any transactions.

**Cause**: No balance available (requires mining to generate funds).

**Solution**: 
- Ensure block generation is working
- Wait for blocks to mature (typically 60 blocks)
- Check user wallet balances in logs

#### 4. Shared State Access Errors

**Issue**: Agents can't read/write shared state files.

**Cause**: Permission issues or missing directory.

**Solution**: The framework automatically creates `/tmp/monerosim_shared/` with proper permissions.

### Debugging Tips

1. **Enable Debug Logging**:
   ```yaml
   log_level: debug
   ```

2. **Monitor Agent Logs**:
   ```bash
   grep "user001" shadow.data/hosts/user001/stdout-user001.log
   ```

3. **Check RPC Connectivity**:
   ```bash
   curl -X POST http://11.0.0.10:28090/json_rpc \
     -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}'
   ```

4. **Verify Shared State**:
   ```bash
   cat /tmp/monerosim_shared/users.json | jq .
   ```

## Examples

### Example 1: Basic Transaction Flow

```python
# User agent decides to send transaction
def _send_transaction(self):
    # Generate random amount
    amount = random.uniform(self.min_amount, self.max_amount)
    
    # Send transaction to a random user using agent discovery
    from scripts.agent_discovery import AgentDiscovery
    ad = AgentDiscovery()
    recipients = ad.get_wallet_agents()
    recipient = random.choice(recipients)
    
    # Send transaction
    result = self.wallet_rpc.transfer([{
        "address": recipient["address"],
        "amount": int(amount * 1e12)
    }])
    
    # Log to shared state
    self.append_shared_list("transactions.json", {
        "sender": self.agent_id,
        "recipient": recipient["agent_id"],
        "amount": amount,
        "tx_hash": result["tx_hash"],
        "timestamp": time.time()
    })
```

### Example 2: Custom Agent Configuration

```yaml
# config_custom.yaml
agents:
  user_agents:
    # Regular users
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "45"
        min_transaction_amount: "0.01"
        max_transaction_amount: "0.5"
        can_receive_distributions: true
    # Repeat for 20 users...
    
    # Mining nodes
    - daemon: "monerod"
      is_miner: true
      attributes:
        hashrate: "30"
        can_receive_distributions: true
    - daemon: "monerod"
      is_miner: true
      attributes:
        hashrate: "25"
        can_receive_distributions: false
    - daemon: "monerod"
      is_miner: true
      attributes:
        hashrate: "20"
        can_receive_distributions: "yes"
    - daemon: "monerod"
      is_miner: true
      attributes:
        hashrate: "15"
        can_receive_distributions: "0"
    - daemon: "monerod"
      is_miner: true
      attributes:
        hashrate: "10"
        can_receive_distributions: "on"
    
  block_controller:
    script: "agents.block_controller"
    arguments: ["--block-time", "60"]
```

### Example 3: Analyzing Simulation Results

```python
import json
import pandas as pd

# Load transaction data
with open('/tmp/monerosim_shared/transactions.json', 'r') as f:
    transactions = json.load(f)

# Convert to DataFrame
df = pd.DataFrame(transactions)

# Analyze transaction patterns
print(f"Total transactions: {len(df)}")
print(f"Average amount: {df['amount'].mean():.4f} XMR")
print(f"Transactions per user: {df.groupby('sender').size().mean():.2f}")
```

## Future Enhancements

### Planned Improvements

1. **Additional Agent Types**:
   - **Exchange Agents**: Simulate cryptocurrency exchanges
   - **Miner Agents**: Individual miners (not mining pools)
   - **Merchant Agents**: E-commerce participants
   - **Attacker Agents**: Various attack scenarios

2. **Enhanced Behaviors**:
   - Dynamic transaction patterns based on market conditions
   - Price discovery mechanisms
   - Reputation systems for designated miners
   - Mining difficulty adjustments

3. **Network Effects**:
   - Transaction fee markets
   - Network congestion simulation
   - Mempool dynamics
   - Chain reorganization scenarios

4. **Analysis Tools**:
   - Real-time visualization dashboard
   - Automated report generation
   - Performance metrics collection
   - Network health indicators

5. **Integration Enhancements**:
   - Direct integration with Monero's mining subsystem
   - Support for multiple blockchain networks
   - Cross-chain transaction simulation
   - Lightning/payment channel networks

### Research Applications

The agent framework enables research in:

1. **Economic Analysis**:
   - Transaction fee dynamics
   - Mining economics
   - Market microstructure

2. **Security Research**:
   - 51% attack scenarios
   - Double-spend attempts
   - Network partition attacks
   - Privacy analysis

3. **Protocol Development**:
   - Testing protocol changes
   - Evaluating new features
   - Performance optimization

4. **Network Science**:
   - Emergent behaviors
   - Network topology effects
   - Information propagation

## Agent Discovery System

The Agent Discovery System provides a dynamic way for agents to discover and interact with each other, replacing the legacy hardcoded network configuration approach. This system is implemented in `scripts/agent_discovery.py` and provides a clean API for agent discovery.

### Key Components

1. **AgentDiscovery Class**: Main class that provides methods for discovering agents
2. **Shared State Files**: JSON files that store agent information in `/tmp/monerosim_shared/`
3. **Caching Mechanism**: Improves performance by caching agent information
4. **Error Handling**: Robust error handling for missing files or invalid data

### Benefits

1. **Dynamic Discovery**: Agents can discover other agents at runtime without hardcoded configurations
2. **Scalability**: Easily scales to support large numbers of agents
3. **Flexibility**: Supports different types of agents (miners, users, wallets, etc.)
4. **Maintainability**: Eliminates the need to update hardcoded configurations when the network changes

### API Examples

```python
from scripts.agent_discovery import AgentDiscovery

# Initialize agent discovery
ad = AgentDiscovery()

# Get all agents
all_agents = ad.get_agent_registry()

# Find agents by type
miners = ad.get_miner_agents()
wallets = ad.get_wallet_agents()

# Get a specific agent by ID
agent = ad.get_agent_by_id("user001")

# Refresh cache if needed
ad.refresh_cache()
```

For more detailed information about the Agent Discovery System, see [`scripts/README_agent_discovery.md`](../scripts/README_agent_discovery.md).

## Migration from Legacy Network Configuration

The Agent Framework has transitioned from a hardcoded network configuration approach to a dynamic agent discovery system:

### Legacy Approach

```python
# Legacy approach using hardcoded network configuration
# Note: This approach has been removed and replaced with Agent Discovery
```

### New Agent Discovery Approach

```python
# New approach using agent discovery
from scripts.agent_discovery import AgentDiscovery

# Initialize agent discovery
ad = AgentDiscovery()

# Get agent information dynamically
agent = ad.get_agent_by_id("user001")
ip_address = agent["ip_addr"]
daemon_port = agent["daemon_port"]
wallet_port = agent["wallet_port"]
```

### Benefits of Migration

1. **No Hardcoded Configurations**: Eliminates the need to update hardcoded IP addresses and ports
2. **Dynamic Network Support**: Agents can join and leave the network dynamically
3. **Improved Scalability**: Easily scales to support large numbers of agents
4. **Better Maintainability**: Reduces the risk of configuration errors and inconsistencies

## Conclusion

The Monerosim Agent Framework represents a significant advancement in cryptocurrency network simulation. By introducing autonomous agents that model real-world participants, it enables researchers and developers to study complex network behaviors that emerge from simple individual actions.

The framework is production-ready and has been successfully tested at various scales. The new Agent Discovery System replaces the legacy hardcoded network configuration approach, providing a more flexible, scalable, and maintainable solution for agent interaction.

For questions, bug reports, or contributions, please refer to the main Monerosim repository.