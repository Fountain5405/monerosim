# Monerosim Architecture Diagrams V2

## System Overview

```mermaid
graph TB
    subgraph "Configuration Phase"
        UC[User Config YAML] --> RG[Rust Generator]
        RG --> SC[Shadow Config YAML]
        RG --> AC[Agent Configs JSON]
    end
    
    subgraph "Shadow Simulation"
        SC --> S[Shadow Simulator]
        S --> A1[Regular User Agent 1]
        S --> A2[Regular User Agent 2]
        S --> AN[Regular User Agent N]
        S --> M1[Marketplace Agent 1]
        S --> MP1[Mining Pool Agent 1]
        S --> MP2[Mining Pool Agent 2]
        S --> BC[Block Controller Agent]
    end
    
    subgraph "Agent Layer"
        A1 --> MD1[monerod]
        A1 --> MW1[monero-wallet-rpc]
        MP1 --> MD2[monerod mining]
        M1 --> MW2[monero-wallet-rpc]
    end
    
    subgraph "Coordination"
        BC -.-> MP1
        BC -.-> MP2
        M1 -.-> SF[Shared Files]
        A1 -.-> SF
        A2 -.-> SF
    end
```

## Agent Architecture

```mermaid
classDiagram
    class BaseAgent {
        +agent_id: str
        +config: dict
        +logger: Logger
        +run()
        +cleanup()
        +setup_logging()
    }
    
    class MoneroProcess {
        +binary_path: str
        +data_dir: str
        +config: dict
        +process: Process
        +start()
        +stop()
        +build_args()
    }
    
    class MoneroNode {
        +build_args()
        +get_rpc_client()
    }
    
    class MoneroWallet {
        +build_args()
        +get_rpc_client()
    }
    
    class RegularUserAgent {
        +node: MoneroNode
        +wallet: MoneroWallet
        +transaction_frequency: float
        +send_transaction()
        +get_marketplace_addresses()
    }
    
    class MarketplaceAgent {
        +addresses: list
        +wallet_count: int
        +generate_addresses()
        +publish_addresses()
        +check_transactions()
    }
    
    class MiningPoolAgent {
        +pool_id: str
        +hashrate_share: float
        +node: MoneroNode
        +register_with_controller()
        +should_mine()
        +mine_block()
    }
    
    class BlockController {
        +block_time: int
        +mining_pools: dict
        +discover_mining_pools()
        +select_miner()
        +signal_pool_to_mine()
    }
    
    BaseAgent <|-- RegularUserAgent
    BaseAgent <|-- MarketplaceAgent
    BaseAgent <|-- MiningPoolAgent
    BaseAgent <|-- BlockController
    
    MoneroProcess <|-- MoneroNode
    MoneroProcess <|-- MoneroWallet
    
    RegularUserAgent --> MoneroNode
    RegularUserAgent --> MoneroWallet
    MiningPoolAgent --> MoneroNode
    MarketplaceAgent --> MoneroWallet
```

## Agent Communication Flow

```mermaid
sequenceDiagram
    participant BC as Block Controller
    participant MP1 as Mining Pool 1
    participant MP2 as Mining Pool 2
    participant RU as Regular User
    participant M as Marketplace
    participant SF as Shared Files
    
    Note over MP1,MP2: Mining pools register
    MP1->>SF: Write pool registration
    MP2->>SF: Write pool registration
    
    BC->>SF: Read pool registrations
    BC->>BC: Calculate hashrate shares
    
    Note over M: Marketplace publishes addresses
    M->>SF: Write marketplace addresses
    
    Note over RU: User sends transaction
    RU->>SF: Read marketplace addresses
    RU->>RU: Select random address
    RU->>M: Send XMR transaction
    
    Note over BC: Block generation cycle
    loop Every block_time seconds
        BC->>BC: Select miner by hashrate
        BC->>SF: Write mining signal
        MP1->>SF: Check for signal
        alt Has mining signal
            MP1->>MP1: Mine block
            MP1->>SF: Clear signal
        end
    end
```

## Agent State Machine

```mermaid
stateDiagram-v2
    [*] --> Initializing
    
    state RegularUserAgent {
        Initializing --> StartingNode
        StartingNode --> StartingWallet
        StartingWallet --> Active
        
        state Active {
            Idle --> CheckingTransaction
            CheckingTransaction --> SendingTransaction
            SendingTransaction --> Idle
        }
    }
    
    state MiningPoolAgent {
        Initializing --> StartingNode
        StartingNode --> Registering
        Registering --> WaitingForSignal
        
        state WaitingForSignal {
            Checking --> Mining
            Mining --> Checking
        }
    }
    
    state BlockController {
        Initializing --> DiscoveringPools
        DiscoveringPools --> Scheduling
        
        state Scheduling {
            Waiting --> SelectingMiner
            SelectingMiner --> SignalingMiner
            SignalingMiner --> Waiting
        }
    }
```

## Data Flow Architecture

```mermaid
graph LR
    subgraph "Agent Processes"
        RU1[Regular User 1]
        RU2[Regular User 2]
        MP[Marketplace]
        M1[Miner Pool 1]
        M2[Miner Pool 2]
        BC[Block Controller]
    end
    
    subgraph "Shared State"
        MA[marketplace_addresses.json]
        PR[Pool Registrations]
        MS[Mining Signals]
    end
    
    subgraph "Monero Processes"
        D1[monerod 1]
        D2[monerod 2]
        W1[wallet-rpc 1]
        W2[wallet-rpc 2]
    end
    
    MP -->|writes| MA
    RU1 -->|reads| MA
    RU2 -->|reads| MA
    
    M1 -->|writes| PR
    M2 -->|writes| PR
    BC -->|reads| PR
    
    BC -->|writes| MS
    M1 -->|reads| MS
    M2 -->|reads| MS
    
    RU1 -->|controls| D1
    RU1 -->|controls| W1
    M1 -->|controls| D2
    
    D1 <-->|P2P| D2
    W1 -->|RPC| D1
    W2 -->|RPC| D2
```

## Configuration Generation Flow

```mermaid
flowchart TD
    UC[User Config] --> Parse[Parse Config]
    Parse --> GenAgents[Generate Agent Configs]
    Parse --> GenShadow[Generate Shadow Config]
    
    GenAgents --> AC1[regular_user_1.json]
    GenAgents --> AC2[regular_user_2.json]
    GenAgents --> ACN[...]
    GenAgents --> MPC1[mining_pool_1.json]
    GenAgents --> MC1[marketplace_1.json]
    GenAgents --> BCC[block_controller.json]
    
    GenShadow --> Hosts[Generate Hosts]
    Hosts --> H1[Host: user_1<br/>Process: python regular_user.py]
    Hosts --> H2[Host: pool_1<br/>Process: python mining_pool.py]
    Hosts --> H3[Host: marketplace_1<br/>Process: python marketplace.py]
    Hosts --> H4[Host: controller<br/>Process: python block_controller.py]
    
    H1 --> SC[shadow.yaml]
    H2 --> SC
    H3 --> SC
    H4 --> SC
```

## Mining Coordination

```mermaid
graph TB
    subgraph "Block Controller Logic"
        Timer[Block Timer] --> Select[Select Miner]
        Select --> Weight[Weight by Hashrate]
        Weight --> Signal[Write Signal File]
    end
    
    subgraph "Mining Pool Agents"
        Check1[Pool 1: Check Signal] --> Mine1{Signal Present?}
        Mine1 -->|Yes| GenBlock1[Generate Block]
        Mine1 -->|No| Wait1[Wait]
        GenBlock1 --> Clear1[Clear Signal]
        
        Check2[Pool 2: Check Signal] --> Mine2{Signal Present?}
        Mine2 -->|Yes| GenBlock2[Generate Block]
        Mine2 -->|No| Wait2[Wait]
        GenBlock2 --> Clear2[Clear Signal]
    end
    
    Signal -.-> Check1
    Signal -.-> Check2
    
    Clear1 --> Timer
    Clear2 --> Timer
```

## Transaction Flow

```mermaid
sequenceDiagram
    participant User as Regular User Agent
    participant UW as User Wallet
    participant UD as User Daemon
    participant Network as P2P Network
    participant MD as Miner Daemon
    participant Market as Marketplace
    
    User->>Market: Request addresses
    Market-->>User: Return address list
    
    User->>User: Select random address
    User->>UW: Create transaction
    UW->>UD: Submit to mempool
    UD->>Network: Broadcast transaction
    Network->>MD: Receive transaction
    
    Note over MD: Mining process
    MD->>MD: Include in block
    MD->>Network: Broadcast block
    Network->>UD: Receive block
    UD->>UW: Update balance
    
    Market->>Market: Monitor incoming transactions
```

## Deployment Structure

```mermaid
graph TB
    subgraph "Shadow Simulation Environment"
        subgraph "Host: user_1"
            PY1[Python Process]
            PY1 --> D1[monerod]
            PY1 --> W1[wallet-rpc]
        end
        
        subgraph "Host: pool_1"
            PY2[Python Process]
            PY2 --> D2[monerod --mining]
        end
        
        subgraph "Host: marketplace_1"
            PY3[Python Process]
            PY3 --> W3[wallet-rpc]
        end
        
        subgraph "Host: controller"
            PY4[Python Process]
        end
        
        subgraph "Shared Volume"
            SF[/shared/]
            SF --> MA[marketplace_addresses.json]
            SF --> MS[mining_signals/]
            SF --> PR[mining_pools/]
        end
    end
    
    D1 <-.->|P2P| D2
    PY1 -.->|Read| MA
    PY3 -.->|Write| MA
    PY2 -.->|Read| MS
    PY4 -.->|Write| MS
```

## Key Design Decisions

1. **Agent-Based Architecture**: Each Shadow host runs a Python agent that represents a network participant
2. **Process Management**: Agents manage their own Monero processes (node/wallet)
3. **Shared State**: Agents communicate through shared files (Shadow-compatible)
4. **Behavioral Modeling**: Agents implement realistic participant behaviors
5. **Coordinated Mining**: Block Controller ensures realistic block generation patterns
6. **Extensibility**: New agent types can be easily added without core changes