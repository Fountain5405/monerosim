# Refined Monerosim Architecture

## Executive Summary

This document proposes a refined architecture for Monerosim that addresses the current architectural issues and provides a scalable foundation for complex network simulations. The key improvements include:

1. **Agent-Based Architecture**: Replace direct binary execution with Python agents that manage node behavior
2. **Proper Separation of Concerns**: Clear boundaries between configuration, runtime behavior, and simulation orchestration
3. **Extensible Node Types**: Support for different node behaviors, wallet strategies, and network topologies
4. **Standardized Interfaces**: Clean APIs between components for maintainability and testing

## Current Architecture Issues

### 1. Direct Binary Execution
- Shadow YAML directly launches Monero binaries
- No intermediate layer for behavior control
- Difficult to implement complex node behaviors

### 2. Mixed Responsibilities
- Rust code generates static configurations
- Python scripts handle runtime behavior
- No clear separation between configuration and runtime

### 3. Limited Extensibility
- Hard-coded node types and behaviors
- Difficult to add new node types or wallet behaviors
- Network topology changes require code modifications

### 4. Inconsistent Patterns
- Some components use direct execution (monerod)
- Others use bash wrappers (wallets)
- Test scripts run as separate hosts

## Proposed Architecture

### Core Design Principles

1. **Agent-Based Simulation**: Each node/wallet is managed by a Python agent
2. **Configuration vs Runtime**: Clear separation between static config and dynamic behavior
3. **Plugin Architecture**: Extensible system for node types and behaviors
4. **Event-Driven Communication**: Agents communicate through events/messages
5. **Centralized Orchestration**: Single orchestrator manages simulation lifecycle

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Monerosim System                         │
├─────────────────────────────────────────────────────────────────┤
│                    Configuration Layer (Rust)                    │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐        │
│  │   CLI/API   │  │ Config Parser│  │ Shadow Builder │        │
│  └─────────────┘  └──────────────┘  └────────────────┘        │
├─────────────────────────────────────────────────────────────────┤
│                     Runtime Layer (Python)                       │
│  ┌─────────────────────────────────────────────────────┐       │
│  │                    Orchestrator                      │       │
│  │  ┌─────────┐  ┌──────────┐  ┌─────────────────┐   │       │
│  │  │Lifecycle │  │  Event   │  │    Monitoring   │   │       │
│  │  │ Manager │  │  Router  │  │    & Metrics    │   │       │
│  │  └─────────┘  └──────────┘  └─────────────────┘   │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐ │
│  │   Node Agent    │  │  Wallet Agent   │  │  Test Agent    │ │
│  │  ┌───────────┐  │  │  ┌───────────┐  │  │ ┌────────────┐ │ │
│  │  │  Daemon   │  │  │  │   Wallet  │  │  │ │Test Runner │ │ │
│  │  │ Manager   │  │  │  │  Manager  │  │  │ └────────────┘ │ │
│  │  ├───────────┤  │  │  ├───────────┤  │  └────────────────┘ │
│  │  │ Behavior  │  │  │  │ Strategy  │  │                     │
│  │  │  Plugin   │  │  │  │  Plugin   │  │                     │
│  │  └───────────┘  │  │  └───────────┘  │                     │
│  └─────────────────┘  └─────────────────┘                     │
├─────────────────────────────────────────────────────────────────┤
│                    Shadow Network Simulator                      │
└─────────────────────────────────────────────────────────────────┘
```

### Component Details

#### 1. Configuration Layer (Rust)

**Purpose**: Generate static Shadow configurations from high-level specifications

**Components**:
- **CLI/API**: Command-line interface and potential REST API
- **Config Parser**: Parse and validate simulation configurations
- **Shadow Builder**: Generate Shadow YAML with agent configurations

**Key Changes**:
- Generate configurations that launch Python agents, not raw binaries
- Support declarative behavior specifications
- Enable dynamic topology generation

#### 2. Orchestrator (Python)

**Purpose**: Central coordination of all simulation agents

**Components**:
- **Lifecycle Manager**: Start/stop agents, handle initialization
- **Event Router**: Route messages between agents
- **Monitoring & Metrics**: Collect and aggregate simulation metrics

**Responsibilities**:
- Initialize simulation environment
- Coordinate agent startup sequence
- Route inter-agent communication
- Collect and report metrics
- Handle simulation termination

#### 3. Node Agent (Python)

**Purpose**: Manage individual Monero daemon instances

**Components**:
- **Daemon Manager**: Start/stop/monitor monerod process
- **Behavior Plugin**: Implement node-specific behaviors

**Behavior Types**:
- **MiningNode**: Generates blocks at specified intervals
- **SyncNode**: Standard synchronizing node
- **AttackerNode**: Implements various attack strategies
- **ObserverNode**: Monitors network without participating

**Example Structure**:
```python
class NodeAgent:
    def __init__(self, config: NodeConfig):
        self.daemon = DaemonManager(config)
        self.behavior = BehaviorPlugin.create(config.behavior_type)
        
    async def run(self):
        await self.daemon.start()
        await self.behavior.execute(self.daemon)
```

#### 4. Wallet Agent (Python)

**Purpose**: Manage wallet instances with configurable strategies

**Components**:
- **Wallet Manager**: Handle wallet RPC process
- **Strategy Plugin**: Implement wallet behaviors

**Strategy Types**:
- **MiningWallet**: Receives mining rewards
- **TransactionBot**: Sends transactions at intervals
- **ExchangeWallet**: Simulates exchange behavior
- **UserWallet**: Simulates regular user patterns

#### 5. Test Agent (Python)

**Purpose**: Execute test scenarios and validations

**Components**:
- **Test Runner**: Execute test sequences
- **Assertion Engine**: Validate simulation state

**Test Types**:
- **Connectivity Tests**: Verify P2P connections
- **Consensus Tests**: Verify blockchain consistency
- **Performance Tests**: Measure throughput/latency
- **Attack Tests**: Verify security properties

### Configuration Schema

```yaml
# monerosim.yaml
simulation:
  duration: 4h
  network:
    topology: mesh  # or star, ring, custom
    bandwidth: 1Gbit
    latency: 10ms
    
nodes:
  - type: mining_node
    count: 2
    behavior:
      plugin: constant_mining
      block_interval: 120s
      
  - type: sync_node
    count: 10
    behavior:
      plugin: standard_sync
      
  - type: attacker_node
    count: 1
    behavior:
      plugin: eclipse_attack
      target: mining_node_0
      
wallets:
  - type: mining_wallet
    count: 2
    strategy:
      plugin: hold_rewards
      
  - type: user_wallet
    count: 5
    strategy:
      plugin: random_transactions
      interval: 300s
      amount_range: [0.1, 1.0]
      
tests:
  - name: verify_consensus
    start_time: 30m
    plugin: consensus_checker
    
  - name: measure_throughput
    start_time: 1h
    plugin: performance_monitor
```

### Shadow YAML Generation

Instead of directly launching binaries, generate configurations that launch agents:

```yaml
hosts:
  orchestrator:
    network_node_id: 0
    processes:
    - path: /usr/bin/python3
      args: -m monerosim.orchestrator --config /simulation/config.yaml
      start_time: 0s
      
  mining_node_0:
    network_node_id: 0
    ip_addr: 11.0.0.1
    processes:
    - path: /usr/bin/python3
      args: -m monerosim.node_agent --node-id mining_node_0 --orchestrator 11.0.0.100:8080
      environment:
        NODE_TYPE: mining_node
        BEHAVIOR_PLUGIN: constant_mining
      start_time: 10s
```

### Communication Architecture

#### Inter-Agent Communication

Agents communicate through a lightweight message bus:

```python
# Message types
class Message:
    source: str
    destination: str
    type: MessageType
    payload: dict

# Example messages
BlockGenerated(height=100, hash="...")
TransactionSent(from_wallet="w1", to_wallet="w2", amount=1.0)
NodeConnected(node_id="node_1", peer_id="node_2")
```

#### Orchestrator API

RESTful API for monitoring and control:

```
GET /api/status              # Simulation status
GET /api/nodes               # List all nodes
GET /api/nodes/{id}/info     # Node details
POST /api/nodes/{id}/action  # Trigger node action
GET /api/metrics             # Simulation metrics
```

### Extensibility Points

#### 1. Behavior Plugins

```python
class BehaviorPlugin(ABC):
    @abstractmethod
    async def execute(self, daemon: DaemonManager):
        pass

class ConstantMiningBehavior(BehaviorPlugin):
    def __init__(self, interval: int):
        self.interval = interval
        
    async def execute(self, daemon: DaemonManager):
        while True:
            await daemon.generate_blocks(1)
            await asyncio.sleep(self.interval)
```

#### 2. Network Topologies

```python
class TopologyGenerator(ABC):
    @abstractmethod
    def generate(self, nodes: List[NodeConfig]) -> NetworkTopology:
        pass

class MeshTopology(TopologyGenerator):
    def generate(self, nodes):
        # Generate full mesh connections
        pass
```

#### 3. Test Plugins

```python
class TestPlugin(ABC):
    @abstractmethod
    async def run(self, simulation: SimulationContext) -> TestResult:
        pass

class ConsensusTest(TestPlugin):
    async def run(self, simulation):
        # Verify all nodes have same blockchain
        pass
```

## Implementation Plan

### Phase 1: Core Infrastructure
1. Create Python agent framework
2. Implement orchestrator with basic lifecycle management
3. Create simple node and wallet agents
4. Update Rust code to generate agent-based configs

### Phase 2: Plugin System
1. Implement behavior plugin architecture
2. Create basic behavior plugins (mining, sync)
3. Implement wallet strategy plugins
4. Add test plugin framework

### Phase 3: Advanced Features
1. Implement complex network topologies
2. Add attack behavior plugins
3. Create performance monitoring
4. Build orchestrator API

### Phase 4: Optimization
1. Performance profiling and optimization
2. Scale testing with 100+ nodes
3. Resource usage optimization
4. Documentation and examples

## Migration Strategy

### Backward Compatibility
- Maintain support for current config format
- Provide migration tool for existing configs
- Keep existing Python scripts as legacy mode

### Gradual Migration
1. Implement agent framework alongside existing code
2. Migrate one component at a time
3. Maintain test coverage throughout
4. Deprecate old approach once stable

## Benefits of New Architecture

### 1. Scalability
- Clean separation allows horizontal scaling
- Plugin architecture enables easy extension
- Standardized communication reduces complexity

### 2. Maintainability
- Clear component boundaries
- Testable units
- Consistent patterns throughout

### 3. Flexibility
- Easy to add new node types
- Simple to implement new behaviors
- Network topologies as plugins

### 4. Research Enablement
- Attack simulations
- Performance studies
- Protocol modifications
- Economic modeling

## Technical Considerations

### Performance
- Python agents add overhead vs direct execution
- Mitigate with async/await patterns
- Use process pools for CPU-intensive tasks
- Profile and optimize critical paths

### Reliability
- Implement health checks for all agents
- Graceful degradation on agent failure
- Comprehensive logging and monitoring
- Automatic recovery mechanisms

### Security
- Agents run in isolated environments
- No real cryptocurrency operations
- Sanitize all configuration inputs
- Audit logging for all actions

## Conclusion

This refined architecture transforms Monerosim from a configuration generator into a comprehensive simulation platform. By introducing an agent-based architecture with clear separation of concerns, we enable:

1. Complex behavioral simulations
2. Easy extensibility for research
3. Standardized patterns for maintainability
4. Scalability to large networks

The phased implementation plan ensures we can migrate gradually while maintaining stability and backward compatibility.