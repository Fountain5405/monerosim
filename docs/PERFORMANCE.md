# MoneroSim Performance Guide

This document provides comprehensive guidance for optimizing MoneroSim performance for different use cases and system configurations.

## Performance Overview

### Scalability Characteristics

MoneroSim performance scales with several factors:

- **Node Count**: Linear scaling up to system resource limits
- **Simulation Duration**: Near-linear scaling for most scenarios
- **Network Complexity**: Exponential scaling with connection density
- **System Resources**: CPU, memory, and storage are primary bottlenecks

### Performance Benchmarks

#### Small Networks (1-10 nodes)
- **Build Time**: 15-30 minutes (first time)
- **Simulation Speed**: 2-5x real-time
- **Memory Usage**: 100-500MB per node
- **Storage**: 1-5MB per node per hour

#### Medium Networks (10-50 nodes)
- **Build Time**: 30-60 minutes (first time)
- **Simulation Speed**: 1-3x real-time
- **Memory Usage**: 500MB-2GB per node
- **Storage**: 5-20MB per node per hour

#### Large Networks (50+ nodes)
- **Build Time**: 60+ minutes (first time)
- **Simulation Speed**: 0.5-1x real-time
- **Memory Usage**: 2GB+ per node
- **Storage**: 20MB+ per node per hour

## System Requirements

### Minimum Requirements

- **CPU**: 4 cores, 2.0 GHz
- **RAM**: 8GB
- **Storage**: 20GB free space
- **OS**: Linux (Ubuntu 20.04+, Fedora 32+, Arch Linux)

### Recommended Requirements

- **CPU**: 8+ cores, 3.0+ GHz
- **RAM**: 32GB+
- **Storage**: 100GB+ SSD
- **OS**: Linux with kernel 5.0+

### High-Performance Requirements

- **CPU**: 16+ cores, 3.5+ GHz
- **RAM**: 64GB+
- **Storage**: 500GB+ NVMe SSD
- **OS**: Linux with kernel 5.10+

## Optimization Strategies

### 1. Build Optimization

#### Parallel Compilation

```bash
# Use all available CPU cores
export MAKEFLAGS="-j$(nproc)"

# Or specify exact number
export MAKEFLAGS="-j8"
```

#### Caching

```bash
# Install ccache for faster rebuilds
sudo apt-get install ccache

# Configure ccache
export CC="ccache gcc"
export CXX="ccache g++"

# Set cache size (default 5GB)
ccache -M 10G
```

#### Selective Building

```bash
# Only build what you need
# Don't delete builds/ directory between runs
# Use specific node types instead of building all

# Example: Only build one node type
monero:
  nodes:
    - count: 10
      name: "main"
      base_commit: "shadow-complete"
    # Comment out unused node types
    # - count: 5
    #   name: "secondary"
```

### 2. Simulation Optimization

#### Shadow Configuration Tuning

The generated `shadow.yaml` can be optimized:

```yaml
general:
  # Enable syscall latency modeling for better performance
  model_unblocked_syscall_latency: true
  
  # Set parallelism to match CPU cores
  parallelism: 8
  
  # Optimize for your use case
  stop_time: "1h"

network:
  graph:
    type: gml
    inline: |
      graph [
        # Optimize bandwidth settings
        node [id 0 host_bandwidth_down="10 Gbit" host_bandwidth_up="10 Gbit"]
        # ... more nodes
      ]

hosts:
  # Optimize per-host settings
  a0:
    network_node_id: 0
    processes:
    - path: monerod
      args: [
        "--testnet",
        "--disable-seed-nodes",
        "--log-level=1",  # Reduce logging
        "--max-concurrency=4"  # Limit threads
      ]
      environment:
        RUST_LOG: "warn"  # Reduce log verbosity
        RUST_BACKTRACE: "0"  # Disable backtraces
```

#### Logging Optimization

```bash
# Reduce log verbosity
export RUST_LOG="warn"
export RUST_BACKTRACE="0"

# Or set in configuration
environment:
  RUST_LOG: "warn"
  RUST_BACKTRACE: "0"
```

#### Network Topology Optimization


### 3. System-Level Optimization

#### CPU Optimization

```bash
# Set CPU governor to performance
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Pin processes to specific cores
taskset -c 0-7 shadow shadow_output/shadow.yaml

# Use CPU affinity for better cache locality
```

#### Memory Optimization

```bash
# Increase available memory
# Close unnecessary applications
# Use swap if needed (but prefer RAM)

# Monitor memory usage
watch -n 1 'free -h && echo "---" && ps aux | grep monerod | head -5'
```

#### Storage Optimization

```bash
# Use SSD storage
# Ensure sufficient free space
# Optimize filesystem settings

# For ext4 filesystems
sudo tune2fs -O has_journal /dev/sdX
sudo mount -o noatime,nodiratime /dev/sdX /path/to/simulation
```

#### Network Optimization

```bash
# Optimize network settings for local simulation
sudo sysctl -w net.core.rmem_max=16777216
sudo sysctl -w net.core.wmem_max=16777216
sudo sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
sudo sysctl -w net.ipv4.tcp_wmem="4096 65536 16777216"
```

## Performance Monitoring

### Real-Time Monitoring

```bash
# CPU and memory usage
htop

# Process-specific monitoring
ps aux | grep monerod
ps aux | grep shadow

# System resource usage
iostat -x 1
vmstat 1
```

### Log Analysis

```bash
# Monitor simulation progress
tail -f shadow.data/shadow.log

# Check for performance issues
grep -i "slow\|timeout\|delay" shadow.data/hosts/*/monerod.*.stdout

# Analyze memory usage patterns
grep "memory\|alloc" shadow.data/hosts/*/monerod.*.stdout
```

### Performance Metrics

```bash
# Calculate simulation speed
start_time=$(date +%s)
shadow shadow_output/shadow.yaml
end_time=$(date +%s)
simulation_time=$((end_time - start_time))
echo "Simulation took ${simulation_time} seconds"

# Count successful operations
successful_nodes=$(grep "RPC server initialized OK" shadow.data/hosts/*/monerod.*.stdout | wc -l)
echo "Successfully started ${successful_nodes} nodes"

# Measure P2P connections
p2p_connections=$(grep "Connected success" shadow.data/hosts/*/monerod.*.stdout | wc -l)
echo "Established ${p2p_connections} P2P connections"
```

## Use Case Optimization

### 1. Development and Testing

**Goal**: Fast iteration cycles

```yaml
# Minimal configuration for quick testing
general:
  stop_time: "2m"

monero:
  nodes:
    - count: 2
      name: "dev"
      base_commit: "shadow-complete"
```

**Optimizations**:
- Short simulation times
- Few nodes
- Reduced logging
- Reuse builds

**Agent Testing Configuration**:
```yaml
# Minimal agent configuration
general:
  stop_time: "5m"

monero:
  nodes:
    - count: 3
      name: "A"

agents:
  regular_users:
    - count: 2
      transaction_interval: 60
  marketplaces:
    - count: 1
```

### 2. Research and Analysis

**Goal**: Accurate results with reasonable performance

```yaml
# Balanced configuration for research
general:
  stop_time: "30m"

monero:
  nodes:
    - count: 20
      name: "research"
      base_commit: "shadow-complete"
```

**Optimizations**:
- Moderate node count
- Longer simulation times
- Standard logging
- Optimized Shadow settings

### 3. Large-Scale Studies

**Goal**: Maximum scale with available resources

```yaml
# Large-scale configuration
general:
  stop_time: "2h"

monero:
  nodes:
    - count: 100
      name: "large_scale"
      base_commit: "shadow-complete"
```

**Optimizations**:
- High-performance hardware
- Optimized Shadow configuration
- Minimal logging
- Parallel processing

### 4. Performance Benchmarking

**Goal**: Measure system capabilities

```yaml
# Benchmark configuration
general:
  stop_time: "1h"

monero:
  nodes:
    - count: 50
      name: "benchmark"
      base_commit: "shadow-complete"
```

**Optimizations**:
- Consistent hardware settings
- Standardized configurations
- Detailed monitoring
- Performance metrics collection

### 5. Agent-Based Research

**Goal**: Study realistic network behavior

```yaml
# Agent research configuration
general:
  stop_time: "2h"

monero:
  nodes:
    - count: 30
      name: "A"

agents:
  regular_users:
    - count: 20
      transaction_interval: 180
  marketplaces:
    - count: 5
  mining_pools:
    - count: 2
      mining_threads: 2
```

**Optimizations**:
- Staggered agent startup
- Optimized transaction intervals
- Limited mining threads
- Efficient shared state updates

## Troubleshooting Performance Issues

### 1. Slow Build Times

**Symptoms**: Builds take hours instead of minutes

**Solutions**:
```bash
# Use parallel compilation
export MAKEFLAGS="-j$(nproc)"

# Use ccache
sudo apt-get install ccache
export CC="ccache gcc"
export CXX="ccache g++"

# Clean and rebuild if needed
cargo clean
rm -rf builds/
```

### 2. High Memory Usage

**Symptoms**: System becomes unresponsive, OOM errors

**Solutions**:
```bash
# Reduce node count
# Use swap space
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Monitor memory usage
watch -n 1 'free -h'
```

### 3. Slow Simulation Execution

**Symptoms**: Simulation runs slower than real-time

**Solutions**:
```yaml
# Optimize Shadow configuration
general:
  model_unblocked_syscall_latency: true
  parallelism: 8  # Match CPU cores

# Reduce logging
environment:
  RUST_LOG: "warn"
  RUST_BACKTRACE: "0"
```

### 4. Storage Space Issues

**Symptoms**: Disk full errors, slow I/O

**Solutions**:
```bash
# Clean old simulations
rm -rf shadow.data/
rm -rf old_shadow_outputs/

# Use SSD storage
# Monitor disk usage
df -h
du -sh shadow.data/
```

## Advanced Optimization

### 1. Custom Shadow Configuration

Create custom Shadow configurations for specific use cases:

```yaml
# Custom optimized configuration
general:
  model_unblocked_syscall_latency: true
  parallelism: 16
  stop_time: "1h"
  log_level: warn

network:
  graph:
    type: gml
    inline: |
      graph [
        # Optimized network topology
        node [id 0 host_bandwidth_down="20 Gbit" host_bandwidth_up="20 Gbit"]
        # ... more nodes with optimized settings
      ]

hosts:
  # Optimized host configurations
  a0:
    network_node_id: 0
    processes:
    - path: monerod
      args: [
        "--testnet",
        "--disable-seed-nodes",
        "--log-level=1",
        "--max-concurrency=8",
        "--db-sync-mode=fast"
      ]
      environment:
        RUST_LOG: "warn"
        RUST_BACKTRACE: "0"
        MONERO_DB_SYNC_MODE: "fast"
```

### 4. Agent-Specific Optimizations

#### Agent Discovery System Optimization

The new Agent Discovery System (`scripts/agent_discovery.py`) provides significant performance improvements over the legacy hardcoded configuration approach:

```python
# Use Agent Discovery for efficient agent lookup
from scripts.agent_discovery import AgentDiscovery

class OptimizedAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        # Initialize agent discovery with caching
        self.agent_discovery = AgentDiscovery()
    
    def find_wallet_agents(self):
        # Efficient discovery with caching (5-second TTL)
        wallet_agents = self.agent_discovery.get_wallet_agents()
        return wallet_agents
    
    def find_miner_agents(self):
        # Dynamic miner discovery
        miner_agents = self.agent_discovery.get_miner_agents()
        return miner_agents
```

Benefits of Agent Discovery System:
- **Dynamic Discovery**: Agents are discovered at runtime from shared state files
- **Caching**: 5-second TTL cache reduces file I/O operations
- **Error Handling**: Robust error handling for missing or corrupted files
- **Scalability**: Efficient lookup algorithms scale with agent count

#### Shared State Optimization

```bash
# Use tmpfs for shared state (RAM-based)
sudo mkdir -p /tmp/monerosim_shared
sudo mount -t tmpfs -o size=1G tmpfs /tmp/monerosim_shared

# Or use local SSD instead of network storage
ln -s /local/ssd/monerosim_shared /tmp/monerosim_shared
```

The Agent Discovery System reads from these shared state files:
- `agent_registry.json`: All registered agents
- `miners.json`: Mining agents with hashrate information
- `wallets.json`: Wallet agents with addresses
- `block_controller.json`: Block controller status

#### Agent Startup Optimization

```python
# In agent code, implement staggered startup
import time
import random
from scripts.agent_discovery import AgentDiscovery

class OptimizedAgent(BaseAgent):
    def __init__(self):
        # Add random delay to prevent thundering herd
        startup_delay = random.uniform(0, 30)
        time.sleep(startup_delay)
        super().__init__()
        
        # Initialize agent discovery after startup delay
        self.agent_discovery = AgentDiscovery()
```

#### Transaction Batching

```python
# Batch multiple transactions to reduce overhead
from scripts.agent_discovery import AgentDiscovery

class BatchedUser(RegularUser):
    def __init__(self):
        super().__init__()
        self.agent_discovery = AgentDiscovery()
    
    def send_transactions(self):
        # Discover wallet agents dynamically
        wallet_agents = self.agent_discovery.get_wallet_agents()
        
        transactions = []
        for _ in range(5):  # Batch 5 transactions
            tx = self.create_transaction()
            transactions.append(tx)
        
        # Send all at once
        self.wallet_rpc.send_batch(transactions)
```

#### Mining Pool Optimization

```yaml
# Optimize mining pool configuration using unified agent architecture
agents:
  user_agents:
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "25"  # Percentage of total hashrate
        mining_threads: 4  # Match CPU cores
        signal_check_interval: 10  # Reduce polling frequency
        block_generation_timeout: 300  # Longer timeout for stability
```

### 2. Hardware-Specific Optimizations

#### Multi-CPU Systems

```bash
# Use CPU affinity for better performance
taskset -c 0-15 shadow shadow_output/shadow.yaml

# Set NUMA policy for multi-socket systems
numactl --cpunodebind=0 --membind=0 shadow shadow_output/shadow.yaml
```

#### High-Memory Systems

```bash
# Optimize memory allocation
export MALLOC_ARENA_MAX=2

# Use huge pages if available
echo 1024 | sudo tee /proc/sys/vm/nr_hugepages
```

#### SSD Storage

```bash
# Optimize filesystem for SSD
sudo mount -o noatime,nodiratime,discard /dev/sdX /path/to/simulation

# Use fstrim for SSD maintenance
sudo fstrim -v /
```

### 3. Network Simulation Optimization

#### Bandwidth Optimization

```yaml
# Optimize bandwidth settings for your use case
network:
  graph:
    inline: |
      graph [
        # High bandwidth for performance testing
        node [id 0 host_bandwidth_down="100 Gbit" host_bandwidth_up="100 Gbit"]
        
        # Or realistic bandwidth for network analysis
        # node [id 0 host_bandwidth_down="100 Mbit" host_bandwidth_up="50 Mbit"]
      ]
```

#### Latency Optimization

```yaml
# Optimize latency settings
network:
  graph:
    inline: |
      graph [
        # Low latency for performance testing
        edge [source 0 target 1 latency="1 ms"]
        
        # Or realistic latency for network analysis
        # edge [source 0 target 1 latency="50 ms"]
      ]
```

## Performance Best Practices

### 1. Planning

- **Start small**: Begin with minimal configurations
- **Scale gradually**: Increase complexity step by step
- **Monitor resources**: Track system usage during development
- **Document performance**: Record successful configurations
- **Agent considerations**: Plan for agent overhead in resource allocation

### Agent-Specific Best Practices

1. **Agent Deployment**:
   - Start agents in waves, not all at once
   - Use smaller agent counts initially
   - Monitor shared state file sizes
   - Consider agent type distribution
   - Use the Agent Discovery System for dynamic agent registration

2. **Resource Planning**:
   - Add 100-300MB RAM per agent
   - Reserve IOPS for shared state access
   - Use local SSD for shared state directory
   - Plan for longer simulation times
   - Account for Agent Discovery System caching overhead

3. **Monitoring Agents**:
   ```bash
   # Monitor agent activity
   watch -n 1 'ls -la /tmp/monerosim_shared/*.json | tail -10'
   
   # Check specific shared state files used by Agent Discovery
   watch -n 1 'ls -la /tmp/monerosim_shared/{agent_registry,miners,wallets,block_controller}.json'
   
   # Check agent resource usage
   ps aux | grep -E "(regular_user|block_controller|wallet)" | awk '{sum+=$6} END {print "Total Agent RAM: " sum/1024 " MB"}'
   
   # Monitor shared state I/O
   iotop -o -p $(pgrep -f "regular_user|block_controller|wallet" | tr '\n' ',' | sed 's/,$//')
   ```

4. **Agent Discovery Optimization**:
   - Use the Agent Discovery System for dynamic agent configuration
   - Implement proper error handling for agent discovery operations
   - Cache agent information when possible to reduce file I/O
   - Monitor shared state file sizes for performance impact
   - For more details, see `scripts/README_agent_discovery.md`

5. **Troubleshooting Performance**:
   - If agents are slow, check shared state contention
   - Reduce transaction frequency for better performance
   - Use fewer mining agents to reduce coordination overhead
   - Monitor Python GIL contention with many agents
   - Check Agent Discovery System cache effectiveness

### 2. Execution

- **Use dedicated hardware**: Avoid running other intensive tasks
- **Optimize environment**: Set appropriate system parameters
- **Monitor progress**: Watch for performance degradation
- **Have fallbacks**: Keep backup configurations ready

### 3. Analysis

- **Collect metrics**: Gather performance data during runs
- **Analyze bottlenecks**: Identify limiting factors
- **Optimize iteratively**: Make incremental improvements
- **Document findings**: Share successful optimizations

### 4. Maintenance

- **Regular cleanup**: Remove old simulation data
- **Update dependencies**: Keep system and tools current
- **Monitor system health**: Check for hardware issues
- **Backup configurations**: Preserve working setups
- **Clean shared state**: Clear `/tmp/monerosim_shared/` between runs

## Agent Performance Tuning Guide

### Quick Reference

| Agent Count | RAM Overhead | Simulation Speed | Recommended Hardware |
|-------------|--------------|------------------|---------------------|
| 1-10        | 0.5-1 GB     | 1.5-3x real-time | 8GB RAM, 4 cores   |
| 10-50       | 1-10 GB      | 0.8-2x real-time | 16GB RAM, 8 cores  |
| 50-100      | 10-30 GB     | 0.3-1x real-time | 32GB RAM, 16 cores |
| 100+        | 30+ GB       | <0.5x real-time  | 64GB RAM, 32 cores |

### Optimization Checklist

- [ ] Use local SSD for shared state
- [ ] Implement agent startup delays
- [ ] Optimize transaction intervals
- [ ] Limit mining threads per agent
- [ ] Use appropriate log levels
- [ ] Monitor resource usage continuously
- [ ] Clean shared state between runs
- [ ] Use Python virtual environment
- [ ] Consider agent type balance
- [ ] Test scalability incrementally
- [ ] Use Agent Discovery System for dynamic agent configuration
- [ ] Monitor Agent Discovery System cache effectiveness
- [ ] Implement proper error handling for agent discovery operations
