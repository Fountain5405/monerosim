# Monerosim Refined Architecture V2

## Executive Summary

Based on the analysis of ethshadow and your specific requirements, this document presents a refined agent-based architecture for Monerosim. Unlike ethshadow which launches binaries directly, Monerosim will use Python agents that represent network participants and manage Monero processes.

## Core Architecture Principles

### 1. **Agent-Centric Design**
- Each Shadow process is a Python agent representing a network participant
- Agents manage their own Monero node and/or wallet instances
- Agents implement realistic behaviors (transactions, mining, trading)

### 2. **Behavioral Modeling**
- Agents are not just process managers but behavioral simulators
- Each agent type models specific network participant behaviors
- Behaviors are configurable and extensible

### 3. **Coordinated Simulation**
- Agents can communicate through shared files or network calls
- A coordination layer manages complex interactions (e.g., mining schedules)
- Time-based and event-based behaviors are supported

## Architecture Components

### 1. Configuration Generator (Rust)

The existing Rust tool remains largely unchanged but generates different Shadow configurations:

```yaml
# Generated shadow.yaml
hosts:
  user1:
    processes:
    - path: /usr/bin/python3
      args: /simulation/agents/regular_user.py --id user1 --config user1.json
      start_time: 0s
  
  marketplace1:
    processes:
    - path: /usr/bin/python3
      args: /simulation/agents/marketplace.py --id marketplace1
      start_time: 0s
  
  miner1:
    processes:
    - path: /usr/bin/python3
      args: /simulation/agents/mining_pool.py --id pool1 --hashrate 1000
      start_time: 0s
```

### 2. Agent Framework

#### Base Agent Class
```python
# agents/base_agent.py
class BaseAgent:
    def __init__(self, agent_id, config):
        self.agent_id = agent_id
        self.config = config
        self.logger = self.setup_logging()
        
    def setup_logging(self):
        # Agent-specific logging
        pass
        
    def run(self):
        """Main agent loop - must be implemented by subclasses"""
        raise NotImplementedError
        
    def cleanup(self):
        """Cleanup resources on shutdown"""
        pass
```

#### Process Management
```python
# agents/process_manager.py
class MoneroProcess:
    def __init__(self, binary_path, data_dir, config):
        self.binary_path = binary_path
        self.data_dir = data_dir
        self.config = config
        self.process = None
        
    def start(self):
        cmd = [self.binary_path] + self.build_args()
        self.process = subprocess.Popen(cmd)
        
    def stop(self):
        if self.process:
            self.process.terminate()
            
class MoneroNode(MoneroProcess):
    def build_args(self):
        return [
            '--data-dir', self.data_dir,
            '--no-igd',
            '--hide-my-port',
            '--p2p-bind-port', str(self.config['p2p_port']),
            '--rpc-bind-port', str(self.config['rpc_port']),
            '--fixed-difficulty', str(self.config.get('difficulty', 1000)),
            '--disable-dns-checkpoints',
            '--check-updates', 'disabled',
        ]
        
class MoneroWallet(MoneroProcess):
    def build_args(self):
        return [
            '--wallet-dir', self.data_dir,
            '--daemon-address', self.config['daemon_address'],
            '--rpc-bind-port', str(self.config['rpc_port']),
            '--disable-rpc-login',
        ]
```

### 3. Agent Types

#### Regular User Agent
```python
# agents/regular_user.py
class RegularUserAgent(BaseAgent):
    def __init__(self, agent_id, config):
        super().__init__(agent_id, config)
        self.node = MoneroNode(
            binary_path='/monero/monerod',
            data_dir=f'/data/{agent_id}/node',
            config=config['node']
        )
        self.wallet = MoneroWallet(
            binary_path='/monero/monero-wallet-rpc',
            data_dir=f'/data/{agent_id}/wallet',
            config=config['wallet']
        )
        self.transaction_frequency = config.get('transaction_frequency', 0.1)
        
    def run(self):
        # Start node and wallet
        self.node.start()
        time.sleep(10)  # Wait for node to initialize
        self.wallet.start()
        time.sleep(5)   # Wait for wallet to initialize
        
        # Main behavior loop
        while True:
            try:
                if random.random() < self.transaction_frequency:
                    self.send_transaction()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                break
                
    def send_transaction(self):
        # Get a marketplace address
        marketplace_addresses = self.get_marketplace_addresses()
        if marketplace_addresses:
            recipient = random.choice(marketplace_addresses)
            amount = random.uniform(0.1, 2.0)
            
            # Send transaction via wallet RPC
            self.wallet_rpc.transfer(recipient, amount)
            self.logger.info(f"Sent {amount} XMR to {recipient}")
            
    def get_marketplace_addresses(self):
        try:
            with open('/shared/marketplace_addresses.json', 'r') as f:
                return json.load(f)
        except:
            return []
```

#### Marketplace Agent
```python
# agents/marketplace.py
class MarketplaceAgent(BaseAgent):
    def __init__(self, agent_id, config):
        super().__init__(agent_id, config)
        self.addresses = []
        self.wallet_count = config.get('wallet_count', 10)
        
    def run(self):
        # Generate marketplace addresses
        self.generate_addresses()
        
        # Publish addresses for other agents
        self.publish_addresses()
        
        # Monitor incoming transactions
        while True:
            self.check_transactions()
            time.sleep(30)
            
    def generate_addresses(self):
        # Create multiple wallet addresses to simulate different vendors
        for i in range(self.wallet_count):
            wallet = self.create_wallet(f"vendor_{i}")
            address = wallet.get_address()
            self.addresses.append({
                'vendor_id': f"vendor_{i}",
                'address': address,
                'items': self.generate_items()
            })
            
    def publish_addresses(self):
        with open('/shared/marketplace_addresses.json', 'w') as f:
            addresses = [a['address'] for a in self.addresses]
            json.dump(addresses, f)
```

#### Mining Pool Agent
```python
# agents/mining_pool.py
class MiningPoolAgent(BaseAgent):
    def __init__(self, agent_id, config):
        super().__init__(agent_id, config)
        self.pool_id = config['pool_id']
        self.hashrate_share = config.get('hashrate_share', 0.1)
        self.node = MoneroNode(
            binary_path='/monero/monerod',
            data_dir=f'/data/{agent_id}/node',
            config={**config['node'], 'mining': True}
        )
        
    def run(self):
        self.node.start()
        
        # Register with block controller
        self.register_with_controller()
        
        # Mining loop
        while True:
            if self.should_mine():
                self.mine_block()
            time.sleep(1)
            
    def register_with_controller(self):
        registration = {
            'pool_id': self.pool_id,
            'hashrate_share': self.hashrate_share,
            'rpc_port': self.node.config['rpc_port']
        }
        with open(f'/shared/mining_pools/{self.pool_id}.json', 'w') as f:
            json.dump(registration, f)
            
    def should_mine(self):
        try:
            with open(f'/shared/mining_signals/{self.pool_id}.signal', 'r') as f:
                signal = f.read().strip()
                return signal == 'mine'
        except:
            return False
            
    def mine_block(self):
        # Call node RPC to mine one block
        self.node_rpc.generateblocks(1)
        # Clear the signal
        os.remove(f'/shared/mining_signals/{self.pool_id}.signal')
```

### 4. Coordination Layer

#### Block Controller
```python
# agents/block_controller.py
class BlockController(BaseAgent):
    def __init__(self, agent_id, config):
        super().__init__(agent_id, config)
        self.block_time = config.get('block_time', 120)  # 2 minutes
        self.mining_pools = {}
        
    def run(self):
        # Wait for mining pools to register
        time.sleep(30)
        self.discover_mining_pools()
        
        # Main control loop
        while True:
            self.select_miner()
            time.sleep(self.block_time)
            
    def discover_mining_pools(self):
        pool_files = glob.glob('/shared/mining_pools/*.json')
        for pool_file in pool_files:
            with open(pool_file, 'r') as f:
                pool_data = json.load(f)
                self.mining_pools[pool_data['pool_id']] = pool_data
                
    def select_miner(self):
        # Weighted random selection based on hashrate
        total_hashrate = sum(p['hashrate_share'] for p in self.mining_pools.values())
        rand = random.uniform(0, total_hashrate)
        
        cumulative = 0
        for pool_id, pool_data in self.mining_pools.items():
            cumulative += pool_data['hashrate_share']
            if rand <= cumulative:
                self.signal_pool_to_mine(pool_id)
                break
                
    def signal_pool_to_mine(self, pool_id):
        os.makedirs('/shared/mining_signals', exist_ok=True)
        with open(f'/shared/mining_signals/{pool_id}.signal', 'w') as f:
            f.write('mine')
        self.logger.info(f"Signaled pool {pool_id} to mine next block")
```

## Configuration Schema

### User Configuration (config.yaml)
```yaml
simulation:
  duration: 3600  # 1 hour
  
network:
  # Define agent types and counts
  agents:
    regular_users:
      count: 100
      config:
        transaction_frequency: 0.1  # 10% chance per minute
        wallet_initial_balance: 10.0
        
    marketplaces:
      count: 5
      config:
        wallet_count: 20  # vendors per marketplace
        
    mining_pools:
      - id: pool_alpha
        hashrate_share: 0.4
      - id: pool_beta
        hashrate_share: 0.3
      - id: pool_gamma
        hashrate_share: 0.3
        
  # Block generation settings
  consensus:
    block_time: 120  # seconds
    difficulty: 1000  # fixed for simulation
```

### Generated Shadow Configuration
```yaml
hosts:
  # Regular users
  user_0:
    network_node_id: 0
    processes:
    - path: /usr/bin/python3
      args: /simulation/agents/regular_user.py --id user_0 --config /configs/user_0.json
      
  # Marketplaces  
  marketplace_0:
    network_node_id: 0
    processes:
    - path: /usr/bin/python3
      args: /simulation/agents/marketplace.py --id marketplace_0 --config /configs/marketplace_0.json
      
  # Mining pools
  pool_alpha:
    network_node_id: 0
    processes:
    - path: /usr/bin/python3
      args: /simulation/agents/mining_pool.py --id pool_alpha --config /configs/pool_alpha.json
      
  # Block controller
  block_controller:
    network_node_id: 0
    processes:
    - path: /usr/bin/python3
      args: /simulation/agents/block_controller.py --config /configs/block_controller.json
```

## Key Advantages

### 1. **Flexibility**
- Easy to add new agent types
- Behaviors can be modified without changing core infrastructure
- Configuration-driven agent parameters

### 2. **Realism**
- Agents model actual network participant behaviors
- Probabilistic actions create realistic network patterns
- Time-based and event-based behaviors

### 3. **Scalability**
- Can simulate hundreds of agents
- Efficient process management
- Shared state through filesystem (Shadow-compatible)

### 4. **Extensibility**
- New behaviors can be added as plugins
- Agents can be composed from reusable components
- Clear interfaces for integration

## Migration Path

### Phase 1: Foundation (Weeks 1-2)
- Implement base agent framework
- Create process management utilities
- Set up shared state mechanisms

### Phase 2: Core Agents (Weeks 3-4)
- Implement RegularUserAgent
- Implement MiningPoolAgent
- Implement BlockController

### Phase 3: Extended Agents (Weeks 5-6)
- Implement MarketplaceAgent
- Add transaction verification
- Implement metrics collection

### Phase 4: Integration (Weeks 7-8)
- Update Rust configuration generator
- Create agent configuration templates
- Full system testing

## Conclusion

This architecture provides exactly what you envisioned:
- Python scripts as network participants
- Each script manages its own Monero processes
- Realistic behavioral modeling
- Coordinated network activities

The design is fundamentally different from ethshadow's direct binary launching approach, instead providing a flexible agent-based simulation framework that can model complex Monero network behaviors.