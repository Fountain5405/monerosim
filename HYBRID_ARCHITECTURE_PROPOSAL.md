# Hybrid Architecture Proposal for Monerosim

## Executive Summary

Based on Shadow's constraints, I propose a **hybrid architecture** that achieves your vision while working within Shadow's limitations. Each network participant will be represented by multiple coordinated processes: Shadow directly manages the Monero binaries, while Python agents control the behavior.

## Core Concept

Instead of:
```
Python Agent → launches → monerod + wallet
```

We use:
```
Shadow → launches → monerod + wallet + Python Agent (in parallel)
         Python Agent → controls → monerod + wallet (via RPC)
```

## Architecture Overview

### 1. Regular User Participant

Each regular user consists of three Shadow processes:

```yaml
hosts:
  user_001:
    processes:
    # Process 1: Monero daemon
    - path: /monero/monerod
      args: --data-dir /data/user_001/node --rpc-bind-port 29001 ...
      start_time: 0s
      
    # Process 2: Wallet RPC
    - path: /monero/monero-wallet-rpc
      args: --daemon-address 127.0.0.1:29001 --rpc-bind-port 29002 ...
      start_time: 30s
      
    # Process 3: Behavior agent
    - path: /usr/bin/python3
      args: /agents/regular_user.py --id user_001 --node-rpc 29001 --wallet-rpc 29002
      start_time: 60s
```

### 2. Python Agent Structure

```python
# agents/regular_user.py
class RegularUserAgent:
    def __init__(self, agent_id, node_rpc_port, wallet_rpc_port):
        self.agent_id = agent_id
        # Connect to pre-launched services
        self.node_rpc = MoneroRPC(f"127.0.0.1:{node_rpc_port}")
        self.wallet_rpc = WalletRPC(f"127.0.0.1:{wallet_rpc_port}")
        
    def run(self):
        # Wait for services to be ready
        self.wait_for_services()
        
        # Initialize wallet
        self.setup_wallet()
        
        # Main behavior loop
        while True:
            if self.should_send_transaction():
                self.send_transaction()
            time.sleep(60)
            
    def wait_for_services(self):
        # Poll RPC endpoints until ready
        while not self.node_rpc.is_ready():
            time.sleep(1)
        while not self.wallet_rpc.is_ready():
            time.sleep(1)
```

### 3. Marketplace Participant

```yaml
hosts:
  marketplace_001:
    processes:
    # Just needs wallet for receiving payments
    - path: /monero/monero-wallet-rpc
      args: --daemon-address user_001:29001 --rpc-bind-port 29102 ...
      start_time: 30s
      
    # Marketplace behavior
    - path: /usr/bin/python3
      args: /agents/marketplace.py --id marketplace_001 --wallet-rpc 29102
      start_time: 60s
```

### 4. Mining Pool Participant

```yaml
hosts:
  pool_alpha:
    processes:
    # Mining-enabled daemon
    - path: /monero/monerod
      args: --data-dir /data/pool_alpha --fixed-difficulty 1000 ...
      start_time: 0s
      
    # Mining pool agent
    - path: /usr/bin/python3
      args: /agents/mining_pool.py --id pool_alpha --node-rpc 29201
      start_time: 30s
```

### 5. Block Controller

The block controller remains a standalone Python process:

```yaml
hosts:
  block_controller:
    processes:
    - path: /usr/bin/python3
      args: /agents/block_controller.py
      start_time: 90s
```

## Communication Patterns

### 1. Agent-to-Service Communication
- Agents communicate with their local services via RPC
- No process launching required
- Standard HTTP/JSON-RPC that Shadow handles well

### 2. Agent-to-Agent Communication
- Through shared files in Shadow's filesystem
- Marketplace addresses: `/shared/marketplace_addresses.json`
- Mining signals: `/shared/mining_signals/`
- No direct network communication between agents

### 3. Service-to-Service Communication
- Monero P2P protocol between daemons
- Wallet-to-daemon RPC connections
- All handled by Shadow's network virtualization

## Configuration Generation

The Rust generator would create:

```rust
// For each regular user
for i in 0..config.regular_users.count {
    let user_id = format!("user_{:03}", i);
    let node_rpc_port = 29000 + (i * 10) + 1;
    let wallet_rpc_port = 29000 + (i * 10) + 2;
    
    // Add monerod process
    hosts.insert(user_id.clone(), ShadowHost {
        processes: vec![
            // Monero daemon
            ShadowProcess {
                path: "/monero/monerod".to_string(),
                args: format!("--data-dir /data/{}/node --rpc-bind-port {} ...", 
                    user_id, node_rpc_port),
                start_time: "0s".to_string(),
            },
            // Wallet RPC
            ShadowProcess {
                path: "/monero/monero-wallet-rpc".to_string(),
                args: format!("--daemon-address 127.0.0.1:{} --rpc-bind-port {} ...",
                    node_rpc_port, wallet_rpc_port),
                start_time: "30s".to_string(),
            },
            // Behavior agent
            ShadowProcess {
                path: "/usr/bin/python3".to_string(),
                args: format!("/agents/regular_user.py --id {} --node-rpc {} --wallet-rpc {}",
                    user_id, node_rpc_port, wallet_rpc_port),
                start_time: "60s".to_string(),
            },
        ],
    });
}
```

## Benefits of This Approach

### 1. **Shadow Compatibility** ✓
- Uses proven patterns from current implementation
- No risky subprocess launching
- Proper process lifecycle management

### 2. **Your Vision Achieved** ✓
- Each participant is still represented by a Python script
- Python scripts control behavior
- Can simulate hundreds of different participant types

### 3. **Flexibility** ✓
- Easy to add new participant types
- Behavior logic separated from infrastructure
- Can modify behaviors without touching binaries

### 4. **Reliability** ✓
- Shadow manages critical processes
- Clean shutdown and resource cleanup
- Better debugging and monitoring

## Example: 400 Regular Users

Your example of 400 regular users would generate:
- 400 monerod processes (managed by Shadow)
- 400 wallet-rpc processes (managed by Shadow)  
- 400 Python agent processes (controlling behavior)
- 1200 total processes, all properly coordinated

## Migration Strategy

### Phase 1: Proof of Concept
1. Implement one regular_user agent with pre-launched services
2. Verify RPC communication works
3. Test shared file communication

### Phase 2: Core Implementation
1. Update Rust generator for hybrid approach
2. Implement base agent framework
3. Create regular_user, marketplace, and mining_pool agents

### Phase 3: Testing
1. Test with small numbers (10 users)
2. Scale up gradually
3. Verify Shadow performance with many processes

## Conclusion

This hybrid architecture gives you exactly what you want:
- Python scripts representing network participants
- Flexible behavioral modeling
- Scalable to hundreds of participants

While working within Shadow's constraints:
- Reliable process management
- Proven communication patterns
- No risky subprocess launching

The key insight is that **the Python agent IS the network participant** from a behavioral perspective, even though Shadow manages the underlying Monero processes. This achieves your vision while ensuring reliability.