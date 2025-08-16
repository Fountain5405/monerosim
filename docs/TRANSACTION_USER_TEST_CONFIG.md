# Test Configuration for Miner Distributor Agent

This document contains the YAML configuration for testing the Miner Distributor Agent.

## Configuration File

```yaml
# Test configuration for Miner Distributor Agent
# This configuration includes miners and a miner distributor agent

general:
  stop_time: "1h"
  fresh_blockchain: true
  log_level: info

network:
  type: "1_gbit_switch"

agents:
  user_agents:
    # Miner 1 - 40% hashrate
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: 'true'
        hashrate: "40"
    
    # Miner 2 - 60% hashrate
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      attributes:
        is_miner: 'true'
        hashrate: "60"
    
    # Regular user to receive transactions
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "120"
    
    # Miner Distributor Agent
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

  block_controller:
    script: "agents.block_controller"
    
  pure_script_agents:
    - script: "scripts.monitor"
    - script: "scripts.sync_check"
```

## Configuration Explanation

### Miners
- Two miners with hashrate distribution of 40% and 60%
- Both miners have wallets to receive mining rewards
- The block controller will select miners based on their hashrate weights

### Regular User
- A standard user agent that can receive transactions
- Configured with a transaction interval of 120 seconds

### Miner Distributor Agent
- Specialized agent that distributes Monero from miner wallets to other agents
- Configuration attributes:
  - `transaction_frequency: "30"` - Send a transaction every 30 seconds
  - `min_transaction_amount: "0.1"` - Minimum transaction amount is 0.1 XMR
  - `max_transaction_amount: "0.5"` - Maximum transaction amount is 0.5 XMR
  - `miner_selection_strategy: "weighted"` - Select miners based on hashrate
  - `transaction_priority: "1"` - Use medium transaction priority
  - `max_retries: "3"` - Retry failed transactions up to 3 times
  - `recipient_selection: "random"` - Select recipients randomly

### Monitoring
- Monitor script to track simulation progress
- Sync check script to verify network synchronization

## Expected Behavior

1. **Initialization Phase**:
   - All agents start up and initialize their wallets
   - Block controller discovers miners and their hashrates
   - Miner distributor agent discovers available miners

2. **Mining Phase**:
   - Block controller selects miners based on hashrate weights
   - Selected miners generate blocks and receive rewards
   - Miner wallets accumulate balance over time

3. **Transaction Phase**:
   - Miner distributor agent waits for configured interval (30 seconds)
   - Selects a miner based on weighted hashrate (40%/60% distribution)
   - Checks miner's wallet balance
   - Selects a recipient (regular user in this case)
   - Sends transaction with random amount between 0.1 and 0.5 XMR
   - Records transaction in shared state

4. **Monitoring Phase**:
   - Monitor script tracks overall simulation progress
   - Sync check script verifies all nodes are synchronized
   - Transaction history is recorded in shared state files

## Testing Scenarios

### Scenario 1: Basic Transaction Flow
- Verify that transactions are sent at the configured interval
- Check that transactions are recorded in shared state
- Confirm that miner balances decrease after sending transactions

### Scenario 2: Miner Selection
- Verify that miners are selected according to their hashrate weights
- Check that the 60% hashrate miner is selected approximately 60% of the time
- Test fallback to random selection if weighted selection fails

### Scenario 3: Balance Management
- Verify that transactions are only sent when miners have sufficient balance
- Test behavior when miner balance is insufficient
- Check that transaction amounts stay within configured limits

### Scenario 4: Error Handling
- Test retry mechanism when transactions fail
- Verify graceful handling of unavailable miners
- Check behavior when recipient selection fails

## Success Criteria

The Miner Distributor Agent is considered working correctly when:

1. **Discovery**: Successfully discovers all available miners from the registries
2. **Selection**: Selects miners according to the configured strategy
3. **Transaction Sending**: Successfully sends transactions with proper error handling
4. **Recording**: Accurately records all transactions in shared state
5. **Configuration**: Respects all configuration parameters (frequency, amounts, etc.)

## Next Steps

1. Implement the Miner Distributor Agent based on this design
2. Generate Shadow configuration using this YAML file
3. Run simulation and verify expected behavior
4. Analyze transaction logs and shared state files
5. Adjust configuration parameters as needed