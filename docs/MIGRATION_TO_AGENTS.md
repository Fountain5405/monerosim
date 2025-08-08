# Migration Guide: From Traditional to Agent-Based Simulations

This guide helps you understand the agent-based simulation framework in Monerosim. The agent framework enables realistic cryptocurrency network behavior modeling with autonomous participants.

## Overview of Agent-Based Simulations

Agent-based simulations represent a paradigm shift from simple node-to-node testing to complex, realistic network behavior modeling. Instead of manually scripting interactions between two nodes, agents autonomously make decisions and interact based on configurable behaviors.

A key component of this approach is the **Agent Discovery System** (`scripts/agent_discovery.py`), which provides a dynamic mechanism for agents to discover and interact with each other without relying on hardcoded network configurations. This system reads agent information from shared state files in `/tmp/monerosim_shared/` and provides a clean API for agents to find and communicate with each other.

## Key Differences


### Agent-Based Simulations

```
┌─────────────────────────────────────────┐
│          Block Controller               │
│    (Orchestrates Mining Pools)          │
└─────────────────────────────────────────┘
                    │
    ┌───────────────┴───────────────┐
    │                               │
┌───────────┐                ┌───────────┐
│  Mining   │                │  Mining   │
│  Pool A   │                │  Pool B   │
└───────────┘                └───────────┘
    │                               │
    └───────────┬───────────────────┘
                │
    ┌───────────┴───────────────┐
    │                           │
┌─────────┐  ┌─────────┐  ┌─────────┐
│ User001 │  │ User002 │  │ UserN   │
└─────────┘  └─────────┘  └─────────┘
    │            │              │
    └────────────┴──────────────┘
                 │
    ┌────────────┴──────────────┐
    │                           │
┌─────────────┐          ┌─────────────┐
│Marketplace1 │          │Marketplace2 │
└─────────────┘          └─────────────┘
```

- **Dynamic topology**: Scalable from 2 to 100+ participants
- **Autonomous behavior**: Agents make independent decisions
- **Realistic patterns**: Emergent network behavior
- **Configurable scale**: Small, medium, or large simulations

## Benefits of Agent-Based Simulations

1. **Realistic Network Behavior**: Models actual cryptocurrency usage patterns
2. **Scalability Testing**: Test network performance under various loads
3. **Emergent Properties**: Discover unexpected network behaviors
4. **Attack Simulation**: Model various attack scenarios
5. **Economic Modeling**: Study transaction patterns and fee markets
6. **Research Platform**: Ideal for academic and protocol research
7. **Dynamic Agent Discovery**: Agents can discover and interact with each other without hardcoded configurations, enabling more flexible and realistic simulations

## Configuration Differences


### Agent-Based Configuration (`config_agents_small.yaml`)

```yaml
general:
  stop_time: "3h"
  fresh_blockchain: true
  log_level: info

network:
  type: "1_gbit_switch"  # Network topology

agents:
  user_agents:
    # Miner example
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"  # Required for miners
      is_miner: true
      attributes:
        hashrate: "25"  # Percentage of total hashrate
    
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
    - script: "scripts.sync_check"
```

This configuration uses the unified agent architecture where all network participants are defined as agents. The Agent Discovery System automatically registers these agents and makes them discoverable to each other through shared state files.

## Migration Steps

### Step 1: Choose Your Scale

Monerosim provides three pre-configured agent simulation scales:

1. **Small** (`config_agents_small.yaml`):
   - 2 regular users
   - 1 marketplace
   - 1 mining pool
   - Good for development and testing

2. **Medium** (`config_agents_medium.yaml`):
   - 10 regular users
   - 3 marketplaces
   - 2 mining pools
   - Realistic small network simulation

3. **Large** (`config_agents_large.yaml`):
   - 100 regular users
   - 10 marketplaces
   - 5 mining pools
   - Stress testing and research

### Step 2: Generate Agent Configuration

**Agent-based approach:**
```bash
# For small scale
./target/release/monerosim --config config_agents_small.yaml --output shadow_agents_output

# For medium scale
./target/release/monerosim --config config_agents_medium.yaml --output shadow_agents_output

# For large scale
./target/release/monerosim --config config_agents_large.yaml --output shadow_agents_output
```

### Step 3: Run the Simulation

**Agent-based:**
```bash
shadow shadow_agents_output/shadow_agents.yaml
```

### Step 4: Monitor Agent Behavior

Agent simulations create shared state files for monitoring:

```bash
# Monitor agent status
ls /tmp/monerosim_shared/

# View all registered agents
cat /tmp/monerosim_shared/agent_registry.json

# View miner information
cat /tmp/monerosim_shared/miners.json

# Check wallet information
cat /tmp/monerosim_shared/wallets.json

# Monitor block controller status
cat /tmp/monerosim_shared/block_controller.json

# View transaction logs
cat /tmp/monerosim_shared/transactions.json
```

The Agent Discovery System uses these shared state files to provide agents with up-to-date information about other agents in the simulation.

## Example: Small Scale Simulation

### 1. Review Configuration

```bash
cat config_agents_small.yaml
```

This shows:
- Multiple user agents (some with mining capabilities)
- A block controller for coordinating mining
- Monitoring and sync check scripts
- Network topology configuration

The Agent Discovery System will automatically discover all these components and make them available to each other through the shared state files.

### 2. Generate Shadow Configuration

```bash
./target/release/monerosim --config config_agents_small.yaml --output test_output_small
```

### 3. Run Simulation

```bash
shadow test_output_small/shadow_agents.yaml
```

### 4. Observe Agent Interactions

```bash
# Watch users sending transactions
tail -f shadow.data/hosts/user001/user001.stdout

# Monitor marketplace receipts
tail -f shadow.data/hosts/marketplace001/marketplace001.stdout

# Check mining pool activity
tail -f shadow.data/hosts/poolalpha/poolalpha.stdout
```

## Creating Custom Agent Configurations

### Basic Structure

```yaml
general:
  stop_time: "2h"
  fresh_blockchain: true
  log_level: info

network:
  type: "1_gbit_switch"

agents:
  user_agents:
    # Regular user
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "300"
        min_transaction_amount: "0.1"
        max_transaction_amount: "0.1"
    
    # Miner
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "100"  # 100% of hashrate

  block_controller:
    script: "agents.block_controller"
    
  pure_script_agents:
    - script: "scripts.monitor"
```

This configuration uses the Agent Discovery System to automatically discover and connect agents. No hardcoded IP addresses or ports are needed.

### Advanced Configuration

```yaml
agents:
  user_agents:
    # Power user with high transaction frequency
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "30"  # Very active
        min_transaction_amount: "1.0"
        max_transaction_amount: "1.0"
        
    # Casual user with low transaction frequency
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "3600"  # Once per hour
        min_transaction_amount: "0.01"
        max_transaction_amount: "0.01"
    
    # Large mining pool
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "60"  # 60% of network hashrate
        
    # Small mining pool
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "40"  # 40% of network hashrate

  block_controller:
    script: "agents.block_controller"
    
  pure_script_agents:
    - script: "scripts.monitor"
    - script: "scripts.sync_check"
```

The Agent Discovery System automatically manages the discovery and interaction between all these agents, making it easy to create complex simulations with many different types of participants.

## Troubleshooting Agent Simulations

### Common Issues

1. **Mining RPC Methods Not Found**
   ```
   Error: Method 'start_mining' not found
   ```
   **Solution**: This is a known issue. The current Monero build may not have mining RPC enabled. Workarounds:
   - Use pre-funded wallets for testing
   - Modify Monero build configuration
   - Use command-line mining flags instead

2. **Agents Not Starting**
   ```
   Error: Failed to connect to wallet RPC
   ```
   **Solution**: Ensure wallet RPC services start before agents:
   - Check start_time in Shadow configuration
   - Verify wallet ports are not conflicting
   - Increase agent start delay

3. **No Transactions Occurring**
   ```
   Warning: No balance available for transactions
   ```
   **Solution**: Without mining, wallets have no balance:
   - Wait for mining pools to generate blocks
   - Use testnet with pre-funded addresses
   - Manually mine blocks before starting agents

4. **Performance Issues with Large Simulations**
   ```
   Warning: Simulation running slower than real-time
   ```
   **Solution**: Large simulations require optimization:
   - Increase system resources
   - Reduce logging verbosity
   - Use staggered agent start times
   - Optimize agent update frequencies

### Debugging Techniques

1. **Check Shared State**:
    ```bash
    # Monitor all shared state files
    watch -n 1 'ls -la /tmp/monerosim_shared/'
    
    # View agent registry
    cat /tmp/monerosim_shared/agent_registry.json
    
    # View miner information
    cat /tmp/monerosim_shared/miners.json
    
    # View wallet information
    cat /tmp/monerosim_shared/wallets.json
    
    # View block controller status
    cat /tmp/monerosim_shared/block_controller.json
    
    # View transaction logs
    cat /tmp/monerosim_shared/transactions.json
    ```

2. **Agent Discovery Debugging**:
    ```bash
    # Test agent discovery from Python
    python3 -c "
    from scripts.agent_discovery import AgentDiscovery
    ad = AgentDiscovery()
    print('Agent Registry:', ad.get_agent_registry())
    print('Miners:', ad.get_miner_agents())
    print('Wallets:', ad.get_wallet_agents())
    "
    ```

3. **Agent Logs**:
    ```bash
    # View all agent logs
    find shadow.data/hosts -name "*.stdout" -exec tail -f {} +
    
    # Filter for errors
    grep -r "ERROR" shadow.data/hosts/
    ```

4. **Network Analysis**:
    ```bash
    # Check P2P connections
    grep "Incoming connection" shadow.data/hosts/*/monerod*.stdout
    
    # Monitor transaction flow
    grep "transaction received" shadow.data/hosts/*/monerod*.stdout
    ```

## Performance Considerations

### Resource Requirements

| Scale | Nodes | Agents | RAM | CPU | Disk | Sim Speed |
|-------|-------|--------|-----|-----|------|-----------|
| Small | 10 | 14 | 4GB | 2 cores | 5GB | ~1x |
| Medium | 20 | 35 | 8GB | 4 cores | 10GB | ~0.5x |
| Large | 50 | 115 | 16GB+ | 8 cores | 20GB | ~0.1x |

### Optimization Tips

1. **Stagger Agent Start Times**:
   ```yaml
   regular_users:
     - name: user001
       start_delay: 30  # Start 30s after simulation begins
     - name: user002
       start_delay: 35  # Start 35s after simulation begins
   ```

2. **Adjust Update Frequencies**:
   ```yaml
   block_controller:
     update_interval: 10  # Check every 10s instead of 5s
   ```

3. **Limit Logging**:
   ```yaml
   general:
     log_level: info  # Instead of debug or trace
   ```

## Best Practices

1. **Start Small**: Begin with small-scale simulations to understand agent behavior
2. **Monitor Resources**: Use system monitoring tools during simulations
3. **Incremental Scaling**: Gradually increase scale to find optimal performance
4. **Document Behaviors**: Record observed agent interactions for analysis
5. **Version Control**: Track agent configuration changes in git
6. **Use Agent Discovery**: Leverage the Agent Discovery System for dynamic agent interactions instead of hardcoded configurations
7. **Monitor Shared State**: Regularly check shared state files to understand agent interactions and system status

## Example Use Cases

### 1. Transaction Pattern Analysis

```yaml
# Simulate different user types
agents:
  user_agents:
    # Day trader - frequent small transactions
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "60"
        min_transaction_amount: "0.01"
        max_transaction_amount: "0.01"
      
    # Investor - infrequent large transactions
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "3600"
        min_transaction_amount: "10.0"
        max_transaction_amount: "10.0"
    
    # Miner to support transactions
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "100"
```

### 2. Mining Pool Dynamics

```yaml
# Competing mining pools
agents:
  user_agents:
    # Large mining pool
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "70"  # 70% of network hashrate
      
    # Small mining pool
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "30"  # 30% of network hashrate
    
    # Regular users to create transactions
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "120"
        min_transaction_amount: "0.1"
        max_transaction_amount: "1.0"

  block_controller:
    script: "agents.block_controller"
```

### 3. Using Agent Discovery in Custom Scripts

```python
# Example of using Agent Discovery in a custom script
from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError

def custom_transaction_script():
    try:
        # Initialize agent discovery
        ad = AgentDiscovery()
        
        # Discover wallet agents
        wallet_agents = ad.get_wallet_agents()
        if len(wallet_agents) < 2:
            print("Need at least 2 wallet agents for transactions")
            return
        
        # Discover miner agents
        miner_agents = ad.get_miner_agents()
        if not miner_agents:
            print("No miners found - transactions may not be confirmed")
        
        # Use discovered agents for transactions
        sender = wallet_agents[0]
        receiver = wallet_agents[1]
        
        print(f"Sending transaction from {sender['agent_id']} to {receiver['agent_id']}")
        # Transaction logic here...
        
    except AgentDiscoveryError as e:
        print(f"Agent discovery error: {e}")
```

## Conclusion

Agent-based simulations represent a significant advancement in cryptocurrency network testing. They provide invaluable insights into network behavior, scalability, and emergent properties. The Agent Discovery System further enhances this approach by providing a dynamic, flexible mechanism for agents to discover and interact with each other without relying on hardcoded configurations.

Start with small-scale simulations to familiarize yourself with the framework, then gradually scale up as needed for your research or testing requirements. The Agent Discovery System makes it easy to create complex, realistic simulations with many different types of participants.

The agent framework is actively being developed, and feedback is welcome. For the latest updates and known issues, check the `docs/AGENT_FRAMEWORK.md` documentation. For detailed information about the Agent Discovery System, see `scripts/README_agent_discovery.md`.