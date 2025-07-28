# Shadow Constraints Analysis: Can Python Agents Launch Monero Binaries?

## The Critical Question

Can Python scripts running inside Shadow successfully launch and manage monerod/wallet processes? This is a fundamental question that affects the entire architecture.

## Current Reality

### What's Working Now
1. **Direct Binary Launch**: Shadow successfully launches monerod and monero-wallet-rpc directly
2. **Python Scripts**: Shadow runs Python scripts via bash that make RPC calls to running processes
3. **Bash Wrappers**: Wallet processes are launched through bash with directory setup

### Shadow's Constraints
1. **System Call Interception**: Shadow intercepts and virtualizes system calls
2. **Process Management**: Child processes must be properly managed within Shadow's framework
3. **Network Virtualization**: All network operations go through Shadow's virtual network
4. **Time Virtualization**: Processes must respect Shadow's virtual time

## The Problem with Python Launching Binaries

### Potential Issues
1. **Fork/Exec Complexity**: Python's subprocess.Popen uses fork/exec which Shadow must intercept
2. **Process Hierarchy**: Shadow may not properly track processes launched by Python scripts
3. **Resource Management**: Child processes might not inherit proper Shadow context
4. **Signal Handling**: Process termination and cleanup could be problematic

### Evidence from Current Implementation
The current implementation is careful to:
- Launch binaries directly from Shadow config
- Use bash only for simple setup tasks (mkdir, rm)
- Keep Python scripts focused on RPC communication

## Recommended Architecture Adjustment

Given these constraints, I recommend a **hybrid approach**:

### Option 1: Direct Launch with Python Coordination (RECOMMENDED)

```yaml
# Shadow launches both the binary AND the agent
hosts:
  user_1:
    processes:
    # Launch monerod directly (Shadow manages it properly)
    - path: /monero/monerod
      args: --data-dir /data/user_1 --p2p-port 28080 ...
      start_time: 0s
      
    # Launch Python agent that coordinates behavior
    - path: /usr/bin/python3
      args: /agents/regular_user.py --id user_1 --daemon-rpc 127.0.0.1:28090
      start_time: 5s  # After daemon starts
```

The Python agent would:
- Connect to its pre-launched monerod via RPC
- Manage wallet operations
- Implement behavioral logic
- NOT try to launch binaries

### Option 2: Bash Wrapper Approach (FALLBACK)

If we absolutely need agents to control process lifecycle:

```python
# Use bash as an intermediary (proven to work)
class MoneroProcess:
    def start(self):
        # Instead of subprocess.Popen(["monerod", ...])
        # Use bash which Shadow handles well
        cmd = f"/bin/bash -c '{self.binary_path} {self.args} &'"
        subprocess.run(cmd, shell=True)
```

### Option 3: Test and Validate (RISKY)

Before committing to the full agent architecture:
1. Create a minimal test where Python launches monerod
2. Run it in Shadow to see if it works
3. Check process management, signals, cleanup

## Revised Architecture Recommendation

### 1. **Configuration Phase**
- Rust generator creates Shadow config with BOTH binaries and agents
- Each "participant" gets multiple processes in Shadow

### 2. **Runtime Architecture**
```
Shadow Host "user_1":
  ├── monerod (launched directly by Shadow)
  ├── monero-wallet-rpc (launched directly by Shadow)
  └── regular_user.py (coordinates the above via RPC)
```

### 3. **Agent Responsibilities**
- Behavioral logic (when to send transactions)
- Coordination (reading marketplace addresses)
- Monitoring (checking balances, confirmations)
- NOT process management

### 4. **Example Configuration**

```yaml
# User config
agents:
  regular_users:
    count: 100
    behavior:
      transaction_frequency: 0.1
      
# Generated Shadow config
hosts:
  user_1:
    processes:
    - path: /monero/monerod
      args: --data-dir /data/user_1/node ...
      environment: { ... }
      start_time: 0s
      
    - path: /monero/monero-wallet-rpc
      args: --wallet-dir /data/user_1/wallet ...
      environment: { ... }
      start_time: 30s
      
    - path: /usr/bin/python3
      args: /agents/regular_user.py --id user_1
      environment: { ... }
      start_time: 60s
```

## Benefits of This Approach

1. **Shadow Compatibility**: Uses proven patterns that work
2. **Process Reliability**: Shadow directly manages critical processes
3. **Behavioral Flexibility**: Python agents still control behavior
4. **Debugging**: Easier to debug when processes are Shadow-managed
5. **Performance**: Better performance without subprocess overhead

## Migration Path

1. **Phase 1**: Implement agents that work with pre-launched processes
2. **Phase 2**: Test Python subprocess launching in Shadow
3. **Phase 3**: Only if Phase 2 succeeds, consider full agent control

## Conclusion

While the original vision of Python agents launching their own processes is elegant, Shadow's constraints make this risky. The hybrid approach maintains the benefits of agent-based behavioral modeling while respecting Shadow's process management requirements.

The key insight: **Agents should control behavior, not process lifecycle**. This gives us the flexibility we want while working within Shadow's constraints.