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

*   **Maintain Miner Registry**: Manages a registry of all potential Designated Miners, mapping each miner's IP address to a specific integer "weight" and its unique wallet address.
*   **Weighted Random Selection**: In each block generation cycle, it performs a weighted random selection to choose a single winning miner for the current block.
*   **Block Generation RPC**: Initiates an RPC request to the selected miner's blockchain daemon, instructing it to generate a new block.

**Operational Loop**:

The Block Controller's operational loop executes every `N` minutes, where `N` is the target block time. In each cycle, the Controller performs the following actions:

1.  It references the registry of active Designated Miners and their corresponding weights.
2.  It conducts a weighted random selection to choose a single winning miner for the current block.
3.  It initiates an RPC request to the selected miner's blockchain daemon, instructing it to generate a new block.

### 2.2. Designated Miners

Each Designated Miner is a standard Monero daemon instance with the following properties:

*   **Unique Network IP Address**: A unique IP address within the simulation network.
*   **Unique Wallet Address**: A unique wallet address for receiving block rewards.
*   **"Mining-Enabled" Status**: A flag indicating whether the node is actively participating in the mining simulation.

When a node's mining status is active, it registers its IP address with the Block Controller.

## 3. Configuration Schema

The following changes will be made to the configuration schema to support the new mining architecture:

The configuration will be updated to allow for dynamic assignment of mining roles and hashrate distribution. Instead of pre-assigning IPs, the user will specify the number of miners and their relative weights. The `monerosim` tool will then randomly select nodes to fulfill these roles during the generation of the `shadow.yaml` file.

*   A new `mining` section will be added to `config_agents_*.yaml`.
*   This section will define the target `block_time`, the total `number_of_mining_nodes`, and a `mining_distribution` list of integer weights.

**Note:** The length of the `mining_distribution` array must match `number_of_mining_nodes`. The weights are relative and do not need to sum to 100; the selection probability is calculated as `miner_weight / sum_of_all_weights`.

```yaml
mining:
  block_time: 120 # Target block time in seconds
  number_of_mining_nodes: 7
  mining_distribution: [25, 25, 10, 10, 10, 5, 5]
  solo_miner_threshold: 2 # Percentage of hashrate below which a miner is considered a "solo miner"
```

### 3.1. Future Hashrate Distribution Models

While the initial implementation will use a simple array for the `mining_distribution`, the system should be designed to accommodate more complex, function-based distributions in the future. This will allow for more sophisticated hashrate distribution models, such as exponential or stair-step functions, without requiring a complete redesign of the configuration system. This is a key principle for the implementation and should be considered during development.

### 3.2. Solo Miner Behavior

A "solo miner" is defined as a mining node with a hashrate below the `solo_miner_threshold`. In addition to their mining activities, solo miners should also behave as regular users, making transactions and participating in the network in a manner consistent with a standard user agent. This dual role should be reflected in the agent's implementation.

## 4. Architectural Diagram

```mermaid
graph TD
    subgraph "Configuration Generation (monerosim)"
        A[config_agents_small.yaml] --> B{monerosim binary};
        B -- "1. Randomly select N designated miners" --> C((All Nodes));
        B -- "2. Assign weights" --> D[Miner Registry<br/>(IP, Weight, Wallet)];
        D -- "3. Write to shared state" --> E((/tmp/monerosim_shared/miners.json));
    end

    subgraph "Simulation Execution (shadow)"
        F[Block Controller] -- "4. Read Miner Registry" --> E;
        F -- "5. Weighted Random Selection" --> G{Select Winner};
        subgraph "Simulated Monero Network"
            M1[Designated Miner 1];
            M2[Designated Miner 2];
            MN[... Designated Miner N];
        end
        G -- "6. RPC: Generate Block" --> M2;
    end
```

## 5. Implementation Plan

The implementation will be carried out in the following phases:

1.  **Configuration Schema Update**:
    *   Update the `config.rs` module to support the `number_of_mining_nodes` and `mining_distribution` fields.
    *   Implement validation to ensure the length of the `mining_distribution` array matches `number_of_mining_nodes`.

2.  **Agent Configuration Logic**:
    *   In `shadow_agents.rs`, implement a mechanism to collect all potential mining nodes (e.g., all `user` and `additional` nodes).
    *   Implement logic to randomly select `number_of_mining_nodes` from the collected pool.
    *   Assign the weights from `mining_distribution` to the selected miners.
    *   Write the resulting miner registry (containing IP, weight, wallet address, and a boolean `is_solo_miner` flag) to a shared JSON file (e.g., `/tmp/monerosim_shared/miners.json`). The `is_solo_miner` flag should be set based on the `solo_miner_threshold`.

3.  **Block Controller Refactoring**:
    *   Refactor the `BlockController` agent to read the miner registry from the shared JSON file on startup.
    *   Implement the weighted random selection algorithm based on the weights in the registry.
    *   Remove the old round-robin logic.

4.  **RPC and Daemon Integration**:
    *   Implement the necessary RPC calls to instruct a `monerod` instance to generate a block with a specific coinbase transaction.
    *   Ensure that the `monerod` instances are configured to accept these RPC calls.

5.  **Testing and Validation**:
    *   Develop a comprehensive test suite to validate the new mining architecture.
    *   Run simulations with various hashrate distributions to ensure that the block generation is correctly distributed.
    *   Verify that block rewards are correctly assigned to the winning miners' wallet addresses.