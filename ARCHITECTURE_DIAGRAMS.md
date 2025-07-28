# Monerosim Architecture Diagrams

## System Overview

```mermaid
graph TB
    subgraph "User Interface"
        CLI[CLI Tool]
        API[REST API]
    end
    
    subgraph "Configuration Layer (Rust)"
        CP[Config Parser]
        SB[Shadow Builder]
        TG[Topology Generator]
    end
    
    subgraph "Runtime Layer (Python)"
        ORC[Orchestrator]
        NA[Node Agents]
        WA[Wallet Agents]
        TA[Test Agents]
    end
    
    subgraph "Simulation Layer"
        SHADOW[Shadow Simulator]
        MONERO[Monero Daemons]
        WALLETS[Wallet RPCs]
    end
    
    CLI --> CP
    API --> CP
    CP --> SB
    CP --> TG
    SB --> SHADOW
    TG --> SB
    
    SHADOW --> ORC
    ORC --> NA
    ORC --> WA
    ORC --> TA
    
    NA --> MONERO
    WA --> WALLETS
    TA --> ORC
```

## Agent Architecture

```mermaid
graph TD
    subgraph "Orchestrator"
        LM[Lifecycle Manager]
        ER[Event Router]
        MM[Metrics Manager]
        API_S[API Server]
    end
    
    subgraph "Node Agent"
        DM[Daemon Manager]
        BP[Behavior Plugin]
        NM[Network Monitor]
    end
    
    subgraph "Wallet Agent"
        WM[Wallet Manager]
        SP[Strategy Plugin]
        TM[Transaction Manager]
    end
    
    subgraph "Test Agent"
        TR[Test Runner]
        AE[Assertion Engine]
        RM[Report Manager]
    end
    
    LM --> DM
    LM --> WM
    LM --> TR
    
    ER <--> BP
    ER <--> SP
    ER <--> AE
    
    MM <-- NM
    MM <-- TM
    MM <-- RM
    
    API_S --> LM
    API_S --> ER
    API_S --> MM
```

## Communication Flow

```mermaid
sequenceDiagram
    participant Shadow
    participant Orchestrator
    participant NodeAgent
    participant WalletAgent
    participant TestAgent
    
    Shadow->>Orchestrator: Start orchestrator
    Orchestrator->>Orchestrator: Initialize
    
    Shadow->>NodeAgent: Start node agent
    NodeAgent->>Orchestrator: Register(node_id, capabilities)
    Orchestrator->>NodeAgent: Configure(behavior_plugin)
    NodeAgent->>NodeAgent: Start monerod
    NodeAgent->>Orchestrator: Ready(node_id)
    
    Shadow->>WalletAgent: Start wallet agent
    WalletAgent->>Orchestrator: Register(wallet_id, strategy)
    Orchestrator->>WalletAgent: Configure(strategy_plugin)
    WalletAgent->>WalletAgent: Start wallet-rpc
    WalletAgent->>Orchestrator: Ready(wallet_id)
    
    Orchestrator->>NodeAgent: StartMining()
    NodeAgent->>Orchestrator: BlockGenerated(height, hash)
    Orchestrator->>WalletAgent: NotifyBlock(height)
    
    WalletAgent->>Orchestrator: SendTransaction(tx_data)
    Orchestrator->>NodeAgent: BroadcastTx(tx_data)
    
    Shadow->>TestAgent: Start test agent
    TestAgent->>Orchestrator: GetSimulationState()
    Orchestrator->>TestAgent: SimulationState(nodes, wallets, metrics)
    TestAgent->>TestAgent: Run assertions
    TestAgent->>Orchestrator: TestResult(passed, details)
```

## Plugin Architecture

```mermaid
classDiagram
    class BehaviorPlugin {
        <<interface>>
        +execute(daemon: DaemonManager)
        +on_event(event: Event)
        +get_metrics() dict
    }
    
    class MiningBehavior {
        -interval: int
        -address: str
        +execute(daemon)
        +generate_blocks()
    }
    
    class AttackerBehavior {
        -attack_type: str
        -target: str
        +execute(daemon)
        +perform_attack()
    }
    
    class ObserverBehavior {
        -metrics: dict
        +execute(daemon)
        +collect_metrics()
    }
    
    BehaviorPlugin <|-- MiningBehavior
    BehaviorPlugin <|-- AttackerBehavior
    BehaviorPlugin <|-- ObserverBehavior
    
    class StrategyPlugin {
        <<interface>>
        +execute(wallet: WalletManager)
        +on_balance_change(balance: float)
        +get_metrics() dict
    }
    
    class TransactionBot {
        -interval: int
        -amount_range: tuple
        +execute(wallet)
        +send_random_tx()
    }
    
    class ExchangeWallet {
        -order_book: OrderBook
        +execute(wallet)
        +process_orders()
    }
    
    class HodlerWallet {
        -threshold: float
        +execute(wallet)
        +check_balance()
    }
    
    StrategyPlugin <|-- TransactionBot
    StrategyPlugin <|-- ExchangeWallet
    StrategyPlugin <|-- HodlerWallet
```

## Data Flow

```mermaid
graph LR
    subgraph "Configuration"
        YAML[monerosim.yaml]
        SCHEMA[Schema Validator]
        BUILDER[Config Builder]
    end
    
    subgraph "Generation"
        TOPO[Topology Generator]
        AGENT[Agent Configs]
        SHADOW_Y[shadow.yaml]
    end
    
    subgraph "Runtime"
        METRICS[Metrics Store]
        EVENTS[Event Bus]
        STATE[Simulation State]
    end
    
    subgraph "Output"
        LOGS[Log Files]
        REPORTS[Test Reports]
        DASH[Dashboard]
    end
    
    YAML --> SCHEMA
    SCHEMA --> BUILDER
    BUILDER --> TOPO
    BUILDER --> AGENT
    TOPO --> SHADOW_Y
    AGENT --> SHADOW_Y
    
    SHADOW_Y --> STATE
    STATE --> EVENTS
    EVENTS --> METRICS
    
    METRICS --> LOGS
    METRICS --> REPORTS
    METRICS --> DASH
```

## Network Topology Examples

```mermaid
graph TD
    subgraph "Star Topology"
        A0_S[A0 - Hub]
        A1_S[A1]
        A2_S[A2]
        A3_S[A3]
        A4_S[A4]
        
        A0_S --- A1_S
        A0_S --- A2_S
        A0_S --- A3_S
        A0_S --- A4_S
    end
    
    subgraph "Mesh Topology"
        A0_M[A0]
        A1_M[A1]
        A2_M[A2]
        A3_M[A3]
        
        A0_M --- A1_M
        A0_M --- A2_M
        A0_M --- A3_M
        A1_M --- A2_M
        A1_M --- A3_M
        A2_M --- A3_M
    end
    
    subgraph "Ring Topology"
        A0_R[A0]
        A1_R[A1]
        A2_R[A2]
        A3_R[A3]
        A4_R[A4]
        
        A0_R --- A1_R
        A1_R --- A2_R
        A2_R --- A3_R
        A3_R --- A4_R
        A4_R --- A0_R
    end
```

## State Machine - Node Agent

```mermaid
stateDiagram-v2
    [*] --> Initializing
    Initializing --> Starting: Config received
    Starting --> Running: Daemon started
    Running --> Mining: Start mining
    Mining --> Running: Stop mining
    Running --> Syncing: Behind chain
    Syncing --> Running: Caught up
    Running --> Attacking: Attack mode
    Attacking --> Running: Attack complete
    Running --> Stopping: Shutdown signal
    Stopping --> [*]
    
    Running --> Error: Daemon crash
    Error --> Restarting: Auto-recovery
    Restarting --> Running: Daemon restarted
```

## Deployment Architecture

```mermaid
graph TB
    subgraph "Development Environment"
        DEV_MS[Monerosim Dev]
        DEV_SHADOW[Shadow Dev]
        DEV_MONERO[Monero Fork]
    end
    
    subgraph "Build Pipeline"
        CI[CI/CD System]
        TESTS[Test Suite]
        BUILD[Build Artifacts]
    end
    
    subgraph "Simulation Environment"
        SIM_HOST[Simulation Host]
        SHADOW_RT[Shadow Runtime]
        AGENTS[Agent Processes]
        MONERO_NODES[Monero Nodes]
    end
    
    subgraph "Analysis Environment"
        JUPYTER[Jupyter Notebooks]
        GRAFANA[Grafana Dashboard]
        ELASTIC[ElasticSearch]
    end
    
    DEV_MS --> CI
    DEV_SHADOW --> CI
    DEV_MONERO --> CI
    
    CI --> TESTS
    TESTS --> BUILD
    BUILD --> SIM_HOST
    
    SIM_HOST --> SHADOW_RT
    SHADOW_RT --> AGENTS
    AGENTS --> MONERO_NODES
    
    AGENTS --> ELASTIC
    ELASTIC --> GRAFANA
    ELASTIC --> JUPYTER
```

## Message Flow Example

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Orchestrator
    participant MiningNode
    participant SyncNode
    participant Wallet1
    participant Wallet2
    participant TestAgent
    
    User->>CLI: Start simulation
    CLI->>Orchestrator: Initialize(config)
    
    Orchestrator->>MiningNode: Start(mining_behavior)
    Orchestrator->>SyncNode: Start(sync_behavior)
    Orchestrator->>Wallet1: Start(mining_wallet)
    Orchestrator->>Wallet2: Start(user_wallet)
    
    MiningNode->>Orchestrator: Ready
    SyncNode->>Orchestrator: Ready
    Wallet1->>Orchestrator: Ready
    Wallet2->>Orchestrator: Ready
    
    Orchestrator->>MiningNode: BeginMining
    
    loop Every 2 minutes
        MiningNode->>MiningNode: Generate block
        MiningNode->>Orchestrator: BlockGenerated(height)
        Orchestrator->>SyncNode: NewBlock(height)
        Orchestrator->>Wallet1: UpdateBalance
    end
    
    Wallet1->>Orchestrator: SendTransaction(to: Wallet2, amount: 1.0)
    Orchestrator->>MiningNode: BroadcastTx(tx_data)
    MiningNode->>SyncNode: RelayTx(tx_data)
    
    MiningNode->>Orchestrator: TxIncludedInBlock(tx_id, block)
    Orchestrator->>Wallet2: UpdateBalance
    
    Orchestrator->>TestAgent: RunTests
    TestAgent->>Orchestrator: QueryState
    Orchestrator->>TestAgent: CurrentState(nodes, wallets)
    TestAgent->>TestAgent: Verify consensus
    TestAgent->>Orchestrator: TestPassed
    
    Orchestrator->>User: SimulationComplete(results)
```

## Error Handling Flow

```mermaid
graph TD
    A[Agent Operation] --> B{Error?}
    B -->|No| C[Continue]
    B -->|Yes| D[Catch Exception]
    
    D --> E{Recoverable?}
    E -->|Yes| F[Log Warning]
    E -->|No| G[Log Error]
    
    F --> H[Retry Operation]
    H --> I{Max Retries?}
    I -->|No| A
    I -->|Yes| J[Escalate to Orchestrator]
    
    G --> J[Escalate to Orchestrator]
    J --> K{Critical?}
    K -->|Yes| L[Shutdown Agent]
    K -->|No| M[Mark Degraded]
    
    L --> N[Notify Orchestrator]
    M --> O[Continue Degraded]
    
    N --> P[Orchestrator Decision]
    P --> Q{Restart?}
    Q -->|Yes| R[Restart Agent]
    Q -->|No| S[Remove from Simulation]
```

These diagrams provide a comprehensive visual representation of the refined Monerosim architecture, showing:

1. **System Overview**: High-level component relationships
2. **Agent Architecture**: Internal structure of agents
3. **Communication Flow**: Sequence of interactions
4. **Plugin Architecture**: Class hierarchy for extensibility
5. **Data Flow**: Configuration to results pipeline
6. **Network Topologies**: Supported connection patterns
7. **State Machines**: Agent lifecycle management
8. **Deployment**: Infrastructure architecture
9. **Message Flow**: Example simulation scenario
10. **Error Handling**: Fault tolerance mechanisms