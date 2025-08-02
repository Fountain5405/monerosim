# Migration Guide: From Traditional to Agent-Based Simulations

This guide helps you understand the agent-based simulation framework in Monerosim. The agent framework enables realistic cryptocurrency network behavior modeling with autonomous participants.

## Overview of Agent-Based Simulations

Agent-based simulations represent a paradigm shift from simple node-to-node testing to complex, realistic network behavior modeling. Instead of manually scripting interactions between two nodes, agents autonomously make decisions and interact based on configurable behaviors.

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

## Configuration Differences


### Agent-Based Configuration (`config_agents_small.yaml`)

```yaml
general:
  simulation_duration: 10800
  
# Regular Monero nodes
nodes:
  - name: node001
    ip: 11.0.1.1
    port: 18080
    mining: false
    
  - name: node002
    ip: 11.0.1.2
    port: 18080
    mining: false
    
# Agent definitions
agents:
  regular_users:
    - name: user001
      wallet_port: 28081
      connected_node: node001
      transaction_frequency: 60  # seconds
      
    - name: user002
      wallet_port: 28082
      connected_node: node002
      transaction_frequency: 120
      
  marketplaces:
    - name: marketplace001
      wallet_port: 28090
      connected_node: node001
      
  mining_pools:
    - name: poolalpha
      connected_node: node001
      mining_threads: 1
      
  block_controller:
    name: controller
    target_block_time: 120  # seconds
```

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

# View active users
cat /tmp/monerosim_shared/users.json

# Check marketplace payments
cat /tmp/monerosim_shared/marketplace_payments.json

# Monitor mining coordination
cat /tmp/monerosim_shared/mining_signals/poolalpha.json
```

## Example: Small Scale Simulation

### 1. Review Configuration

```bash
cat config_agents_small.yaml
```

This shows:
- 10 Monero nodes
- 10 regular users (each with own wallet)
- 2 marketplaces
- 2 mining pools
- 1 block controller

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
  simulation_duration: 7200  # 2 hours
  
nodes:
  # Define Monero nodes (non-mining)
  - name: node001
    ip: 11.0.1.1
    port: 18080
    mining: false
    
agents:
  # Define different agent types
  regular_users:
    - name: alice
      wallet_port: 28081
      connected_node: node001
      transaction_frequency: 300  # Every 5 minutes
      transaction_amount: 0.1
      
  marketplaces:
    - name: shop001
      wallet_port: 28090
      connected_node: node001
      
  mining_pools:
    - name: pool001
      connected_node: node001
      mining_threads: 2
```

### Advanced Configuration

```yaml
agents:
  regular_users:
    - name: power_user
      wallet_port: 28081
      connected_node: node001
      transaction_frequency: 30  # Very active
      transaction_amount: 1.0
      preferred_marketplaces: ["premium_shop"]
      
    - name: casual_user
      wallet_port: 28082
      connected_node: node002
      transaction_frequency: 3600  # Once per hour
      transaction_amount: 0.01
      
  marketplaces:
    - name: premium_shop
      wallet_port: 28090
      connected_node: node001
      fee_percentage: 2.5
      
    - name: budget_shop
      wallet_port: 28091
      connected_node: node002
      fee_percentage: 1.0
```

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
   
   # View specific agent state
   cat /tmp/monerosim_shared/user001_stats.json
   ```

2. **Agent Logs**:
   ```bash
   # View all agent logs
   find shadow.data/hosts -name "*.stdout" -exec tail -f {} +
   
   # Filter for errors
   grep -r "ERROR" shadow.data/hosts/
   ```

3. **Network Analysis**:
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

## Example Use Cases

### 1. Transaction Pattern Analysis

```yaml
# Simulate different user types
agents:
  regular_users:
    # Day trader - frequent small transactions
    - name: trader001
      transaction_frequency: 60
      transaction_amount: 0.01
      
    # Investor - infrequent large transactions  
    - name: investor001
      transaction_frequency: 3600
      transaction_amount: 10.0
```

### 2. Marketplace Competition

```yaml
# Multiple marketplaces with different characteristics
agents:
  marketplaces:
    - name: fast_shop
      confirmation_requirement: 1
      
    - name: secure_shop
      confirmation_requirement: 10
```

### 3. Mining Pool Dynamics

```yaml
# Competing mining pools
agents:
  mining_pools:
    - name: big_pool
      mining_threads: 4
      fee_percentage: 1.0
      
    - name: small_pool
      mining_threads: 1
      fee_percentage: 0.5
```

## Conclusion

Agent-based simulations represent a significant advancement in cryptocurrency network testing. They provide invaluable insights into network behavior, scalability, and emergent properties. Start with small-scale simulations to familiarize yourself with the framework, then gradually scale up as needed for your research or testing requirements.

The agent framework is actively being developed, and feedback is welcome. For the latest updates and known issues, check the `docs/AGENT_FRAMEWORK.md` documentation.