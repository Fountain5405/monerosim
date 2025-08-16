# Monerosim Mining Architecture Design

## 1. System Overview

This document specifies a simulation framework for a proof-of-work blockchain network that models hashrate distribution without performing actual cryptographic computations. The system will rely on a central orchestrator, the **Block Controller**, to deterministically assign block creation rights to a distributed set of miners based on a weighted probability model.

The system comprises two primary components:

1.  **Block Controller**: A central agent responsible for orchestrating the block generation process.
2.  **Designated Miners**: Standard Monero daemon instances that participate in the simulation and generate blocks when instructed by the Block Controller.

This architecture replaces a deterministic, single-generator model with a computationally trivial, probabilistic selection managed by the Block Controller. This allows for a more realistic simulation of the block discovery process in a proof-of-work network.

## 2. Component Design

### 2.1. Block Controller

The Block Controller is the central component of the mining simulation. It maintains a persistent, centralized configuration registry of all potential Mining Nodes and orchestrates the block generation process.

**Responsibilities**:

*   **Maintain Miner Registry**: Manages a registry of all potential Designated Miners, mapping each miner's agent ID to a specific integer "weight" and its unique wallet address.
*   **Weighted Random Selection**: In each block generation cycle, it performs a weighted random selection to choose a single winning miner for the current block.
*   **Block Generation RPC**: Initiates an RPC request to the selected miner's blockchain daemon, instructing it to generate a new block.
*   **Agent Discovery Integration**: Uses the Agent Discovery System to dynamically discover and interact with miners without hardcoded configurations.

**Operational Loop**:

The Block Controller's operational loop executes every `N` minutes, where `N` is the target block time. In each cycle, the Controller performs the following actions:

1.  It uses the Agent Discovery System to get the latest registry of active Designated Miners and their corresponding weights.
2.  It conducts a weighted random selection to choose a single winning miner for the current block.
3.  It initiates an RPC request to the selected miner's blockchain daemon, instructing it to generate a new block.
4.  It updates the shared state with information about the newly generated block.

### 2.2. Designated Miners

Each Designated Miner is a standard Monero daemon instance with the following properties:

*   **Unique Agent ID**: A unique identifier within the simulation network.
*   **Unique Wallet Address**: A unique wallet address for receiving block rewards.
*   **"Mining-Enabled" Status**: A flag indicating whether the node is actively participating in the mining simulation.

When a node's mining status is active, the Agent Discovery System automatically registers it with the Block Controller through shared state files.

## 3. Configuration Schema

The following changes will be made to the configuration schema to support the new mining architecture:

The configuration will be updated to allow for dynamic assignment of mining roles and hashrate distribution. Instead of pre-assigning IPs, the user will specify miners as user agents with `is_miner: true` and their relative hashrate. The `monerosim` tool will then automatically register these miners with the Agent Discovery System.

*   Miners are defined as user agents with `is_miner: true` in the `user_agents` section.
*   Each miner specifies its hashrate as a percentage in the `attributes` section.
*   The Block Controller uses the Agent Discovery System to find all miners and their hashrates.

**Note:** The hashrate values are percentages and should sum to 100 across all miners. The Agent Discovery System automatically calculates the selection probability as `miner_hashrate / sum_of_all_hashrates`.

```yaml
agents:
  user_agents:
    # Mining agents
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "25"  # 25% of network hashrate
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "25"  # 25% of network hashrate
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "10"  # 10% of network hashrate
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "10"  # 10% of network hashrate
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "10"  # 10% of network hashrate
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "5"   # 5% of network hashrate
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "5"   # 5% of network hashrate
    
    # Regular user agents
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "60"
        min_transaction_amount: "0.5"
        max_transaction_amount: "2.0"

  block_controller:
    script: "agents.block_controller"
    arguments:
      - "--interval 120"  # Target block time in seconds
      - "--solo-miner-threshold 2"  # Percentage threshold for solo miners
```

### 3.1. Agent Discovery Integration

The Agent Discovery System provides a clean API for the Block Controller to discover and interact with miners:

```python
from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError

class BlockController:
    def __init__(self):
        self.ad = AgentDiscovery()
        
    def select_miner_for_block(self):
        try:
            # Get all miner agents
            miners = self.ad.get_miner_agents()
            if not miners:
                raise AgentDiscoveryError("No miners found")
                
            # Calculate total hashrate
            total_hashrate = sum(float(miner['hashrate']) for miner in miners)
            
            # Perform weighted random selection
            import random
            rand_val = random.uniform(0, total_hashrate)
            cumulative = 0
            
            for miner in miners:
                cumulative += float(miner['hashrate'])
                if rand_val <= cumulative:
                    return miner
                    
            # Fallback to last miner
            return miners[-1]
            
        except AgentDiscoveryError as e:
            print(f"Error selecting miner: {e}")
            return None
```

This approach eliminates the need for hardcoded miner configurations and allows for dynamic discovery of miners as they join or leave the simulation. For more details on the Agent Discovery System, see [`scripts/README_agent_discovery.md`](scripts/README_agent_discovery.md).

### 3.2. Solo Miner Behavior

A "solo miner" is defined as a mining node with a hashrate below the `solo_miner_threshold`. In addition to their mining activities, solo miners should also behave as regular users, making transactions and participating in the network in a manner consistent with a standard user agent. This dual role should be reflected in the agent's implementation.

The Agent Discovery System automatically identifies solo miners based on their hashrate percentage:


## 4. Architectural Diagram

```mermaid
graph TD
    subgraph "Configuration Generation (monerosim)"
        A[config_agents_small.yaml] --> B{monerosim binary};
        B -- "1. Process user agents with is_miner: true" --> C((Miner Agents));
        B -- "2. Create agent registry" --> D[Agent Discovery System<br/>(agent_registry.json)];
        B -- "3. Create miner registry" --> E[Miner Registry<br/>(miners.json)];
    end

    subgraph "Simulation Execution (shadow)"
        F[Block Controller] -- "4. Use Agent Discovery System" --> D;
        F -- "5. Get miner agents" --> E;
        F -- "6. Weighted Random Selection" --> G{Select Winner};
        subgraph "Simulated Monero Network"
            M1[Miner Agent 1<br/>hashrate: 25%];
            M2[Miner Agent 2<br/>hashrate: 25%];
            MN[... Miner Agent N<br/>hashrate: ...%];
        end
        G -- "7. RPC: Generate Block" --> M2;
        M2 -- "8. Update shared state" --> H[(Shared State Files<br/>miners.json, blocks_found.json)];
    end
```

## 5. Implementation Plan

The implementation will be carried out in the following phases:

1.  **Configuration Schema Update**:
    *   Update the configuration schema to support miners as user agents with `is_miner: true`.
    *   Implement validation to ensure the hashrate values are properly specified.

2.  **Agent Discovery System Implementation**:
    *   Implement the `scripts/agent_discovery.py` module to provide a clean API for discovering agents.
    *   Implement methods for discovering miner agents, wallet agents, and block controllers.
    *   Implement caching and error handling for agent discovery operations.

3.  **Agent Configuration Logic**:
    *   In `shadow_agents.rs`, implement a mechanism to collect all user agents with `is_miner: true`.
    *   Write the resulting miner registry (containing agent ID, hashrate, and wallet address) to a shared JSON file (e.g., `/tmp/monerosim_shared/miners.json`).
    *   Write the agent registry to `/tmp/monerosim_shared/agent_registry.json`.

4.  **Block Controller Refactoring**:
    *   Refactor the `BlockController` agent to use the Agent Discovery System for discovering miners.
    *   Implement the weighted random selection algorithm based on the hashrates in the registry.
    *   Remove the old round-robin logic and hardcoded miner configurations.

5.  **RPC and Daemon Integration**:
    *   Implement the necessary RPC calls to instruct a `monerod` instance to generate a block with a specific coinbase transaction.
    *   Ensure that the `monerod` instances are configured to accept these RPC calls.

6.  **Testing and Validation**:
    *   Develop a comprehensive test suite to validate the new mining architecture.
    *   Run simulations with various hashrate distributions to ensure that the block generation is correctly distributed.
    *   Verify that block rewards are correctly assigned to the winning miners' wallet addresses.
    *   Test the Agent Discovery System to ensure it correctly discovers and categorizes agents.