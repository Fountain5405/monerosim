# Miner Distributor Agent Documentation

## Overview

The Miner Distributor Agent is a specialized agent for Monerosim that distributes Monero from miner wallets to other participants in the network. It extends the BaseAgent class and provides functionality to discover miners, select appropriate wallets, and send transactions to other agents.

## Purpose

The Miner Distributor Agent serves several important purposes in the Monerosim ecosystem:

1. **Realistic Network Simulation**: Simulates realistic transaction patterns in a cryptocurrency network
2. **Wallet Testing**: Tests wallet functionality under various conditions
3. **Network Load Testing**: Generates transaction load to test network performance
4. **Miner Wallet Utilization**: Demonstrates how miner wallets can be used for transactions

## Features

### 1. Wallet Discovery
- Automatically discovers available miners from agent and miner registries
- Verifies wallet availability and connectivity
- Filters miners based on wallet status

### 2. Miner Selection Strategies
- **Weighted Selection**: Selects miners based on hashrate weights
- **Balance-based Selection**: Prefers miners with higher balances
- **Random Selection**: Fallback random selection mechanism

### 3. Transaction Management
- Configurable transaction frequency and amounts
- Automatic retry mechanism for failed transactions
- Transaction recording in shared state
- Support for different transaction priorities

### 4. Error Handling
- Graceful handling of unavailable miners
- Exponential backoff for retry attempts
- Comprehensive logging for debugging

## Configuration

### Required Configuration
The Miner Distributor Agent must be configured with the following basic parameters:

```yaml
- daemon: "monerod"
  wallet: "monero-wallet-rpc"
  user_script: "agents.miner_distributor"
```

### Optional Configuration Attributes
The agent supports the following optional attributes to customize behavior:

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `transaction_frequency` | Integer | 60 | Seconds between transactions |
| `min_transaction_amount` | Float | 0.1 | Minimum XMR per transaction |
| `max_transaction_amount` | Float | 1.0 | Maximum XMR per transaction |
| `miner_selection_strategy` | String | "weighted" | Strategy for selecting miners ("weighted", "balance", "random") |
| `transaction_priority` | Integer | 1 | Transaction priority (0-3) |
| `max_retries` | Integer | 3 | Maximum retry attempts for failed transactions |
| `recipient_selection` | String | "random" | Method for selecting recipients ("random", "round_robin") |

### Example Configuration

```yaml
- daemon: "monerod"
  wallet: "monero-wallet-rpc"
  user_script: "agents.miner_distributor"
  attributes:
    transaction_frequency: "30"
    min_transaction_amount: "0.1"
    max_transaction_amount: "0.5"
    miner_selection_strategy: "weighted"
    transaction_priority: "1"
    max_retries: "3"
    recipient_selection: "random"
```

## Usage

### 1. Adding to Configuration
To use the Miner Distributor Agent, add it to the `user_agents` section of your configuration file:

```yaml
agents:
  user_agents:
    # Add miners first
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: 'true'
        hashrate: "50"
    
    # Then add the miner distributor agent
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.miner_distributor"
      attributes:
        transaction_frequency: "60"
        min_transaction_amount: "0.1"
        max_transaction_amount: "1.0"
```

### 2. Generating Shadow Configuration
Use the Monerosim tool to generate the Shadow configuration:

```bash
./target/release/monerosim --config your_config.yaml --output shadow_output
```

### 3. Running the Simulation
Execute the simulation using Shadow:

```bash
shadow shadow_output/shadow_agents.yaml
```

## Behavior

### Initialization Phase
1. Agent starts and parses configuration attributes
2. Discovers available miners from agent and miner registries
3. Registers itself as a transaction agent in the shared state
4. Sets up RPC connections to its own wallet

### Runtime Phase
1. Waits for the configured transaction interval
2. Selects a miner wallet based on the configured strategy
3. Checks the miner's wallet balance
4. Selects a recipient from other agents in the network
5. Generates a random transaction amount within configured limits
6. Sends the transaction with retry logic
7. Records the transaction in shared state
8. Repeats the process

### Shutdown Phase
1. Stops sending new transactions
2. Closes all RPC connections
3. Writes final statistics to shared state
4. Exits gracefully

## Shared State Files

The Miner Distributor Agent creates and updates several shared state files:

### transactions.json
Records all transactions sent by the agent:
```json
[
  {
    "tx_hash": "abc123...",
    "sender_id": "user000",
    "recipient_id": "user001",
    "amount": 0.5,
    "timestamp": 1625097600.0
  }
]
```

### miner_distributor_stats.json
Contains runtime statistics:
```json
{
  "agent_id": "user002",
  "total_transactions": 10,
  "successful_transactions": 9,
  "failed_transactions": 1,
  "total_amount_sent": 4.5,
  "runtime_seconds": 600,
  "timestamp": 1625098200.0
}
```

## Monitoring and Debugging

### Log Messages
The agent produces detailed log messages at various levels:

- **INFO**: Normal operation (miner discovery, transaction sending)
- **WARNING**: Recoverable errors (retry attempts, insufficient balance)
- **ERROR**: Serious errors (RPC failures, agent discovery issues)

### Key Log Patterns
Look for these patterns in the logs:

```
# Successful miner discovery
INFO - Discovered 2 miners

# Transaction sending
INFO - Selected miner user000 with weight 50
INFO - Sent transaction: abc123... from user000 to user001 for 0.5 XMR

# Error conditions
WARNING - Insufficient balance: 0.05 XMR < 0.1 XMR
WARNING - Transaction attempt 1 failed: RPC Error
ERROR - Failed to send transaction after 3 attempts
```

### Shared State Analysis
Monitor the shared state files to track agent performance:

```bash
# View transaction history
cat /tmp/monerosim_shared/transactions.json

# View agent statistics
cat /tmp/monerosim_shared/transaction_agent_stats.json
```

## Troubleshooting

### Common Issues

#### 1. No Miners Discovered
**Symptoms**: Log shows "Discovered 0 miners"
**Causes**:
- No miners configured in the YAML file
- Agent or miner registries not created
- Miners don't have wallet addresses

**Solutions**:
- Verify miners are configured with `is_miner: 'true'`
- Check that miners have wallets configured
- Ensure block controller is running to populate miner addresses

#### 2. Insufficient Balance
**Symptoms**: Log shows "Insufficient balance" messages
**Causes**:
- Miners haven't received any block rewards yet
- Transaction amounts are too high
- Mining is not working properly

**Solutions**:
- Reduce `min_transaction_amount` and `max_transaction_amount`
- Verify mining is working (check block controller logs)
- Increase simulation time to allow for block rewards

#### 3. Transaction Failures
**Symptoms**: Log shows repeated transaction failures
**Causes**:
- Network connectivity issues
- RPC server problems
- Invalid recipient addresses

**Solutions**:
- Check network connectivity between agents
- Verify RPC servers are running
- Increase `max_retries` for better fault tolerance

#### 4. No Recipients Available
**Symptoms**: Log shows "No suitable recipient found"
**Causes**:
- No other agents with wallets in the configuration
- Recipient agents don't have wallet addresses

**Solutions**:
- Add more agents with wallets to the configuration
- Verify recipient agents have proper wallet setup

### Debug Mode
Enable debug logging for more detailed information:

```yaml
attributes:
  transaction_frequency: "30"
  # ... other attributes ...
  log_level: "DEBUG"
```

## Performance Considerations

### Transaction Frequency
- Higher frequencies generate more network load
- Lower frequencies may not provide sufficient testing
- Balance based on simulation goals

### Retry Logic
- Exponential backoff prevents overwhelming the network
- Too many retries can delay other transactions
- Too few retries can reduce success rate

### Miner Selection
- Weighted selection provides realistic distribution
- Balance selection ensures transactions are sent
- Random selection provides fallback mechanism

## Integration with Other Components

### Block Controller
The Miner Distributor Agent works closely with the Block Controller:
- Block controller generates blocks and rewards miners
- Miner distributor agent uses miner wallets to send transactions
- Both share the same miner registry information

### Regular User Agent
The Miner Distributor Agent can send transactions to Regular User Agents:
- Regular User Agents provide recipient addresses
- They can also send their own transactions
- Combined, they create realistic network activity

### Monitoring Scripts
The agent integrates with monitoring scripts:
- Transaction history is recorded in shared state
- Statistics are available for analysis
- Performance metrics are logged for debugging

## Future Enhancements

### Planned Features
1. **Dynamic Transaction Amounts**: Adjust amounts based on network conditions
2. **Transaction Pool Monitoring**: Monitor mempool and adjust fees
3. **Multi-signature Transactions**: Support for complex transaction types
4. **Scheduled Transactions**: Time-delayed or recurring transactions

### Extension Points
The agent is designed to be extensible:
- Add new miner selection strategies
- Implement custom transaction logic
- Integrate with external analysis tools
- Support additional cryptocurrency features

## Conclusion

The Miner Distributor Agent is a powerful tool for simulating realistic transaction patterns in Monerosim. By leveraging miner wallets and configurable behavior, it provides valuable testing capabilities for cryptocurrency network simulations. With proper configuration and monitoring, it can help researchers and developers understand network behavior under various transaction loads.