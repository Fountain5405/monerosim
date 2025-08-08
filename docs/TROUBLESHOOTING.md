# MoneroSim Troubleshooting Guide

This document provides solutions to common issues encountered when using MoneroSim.

## Quick Diagnosis

### Check System Status

```bash
# Verify all components are installed
which shadow
which cargo
which cmake
which git

# Check MoneroSim binary
ls -la target/release/monerosim

# Check monero-shadow repository
ls -la ../monero-shadow/
```

### Check Logs

```bash
# Shadow simulator logs
cat shadow.data/shadow.log

# Individual node logs
ls shadow.data/hosts/*/monerod.*.stdout

# MoneroSim build logs
tail -f builds/*/monero/build.log

# Python script logs
ls shadow.data/hosts/*/simple_test.*.stdout
ls shadow.data/hosts/*/monitor.*.stdout

# Agent logs (for agent-based simulations)
ls shadow.data/hosts/*/regular_user*.stdout
```

## Common Issues and Solutions

### Agent Discovery Issues

#### Issue: Agent Discovery System fails to find agents

**Possible Causes**:
1. Shared state files not created
2. Agent registration failed
3. File permission issues with shared state directory

**Solutions**:
1. Verify shared state directory and files:
   ```bash
   # Check if directory exists
   ls -la /tmp/monerosim_shared/
   
   # Create if missing
   mkdir -p /tmp/monerosim_shared
   
   # Set proper permissions
   chmod 755 /tmp/monerosim_shared/
   ```

2. Check agent registration in logs:
   ```bash
   # Look for agent registration messages
   grep "agent.*register" shadow.data/hosts/*/bash.*.stdout
   
   # Check for errors in agent initialization
   grep "ERROR.*agent" shadow.data/hosts/*/bash.*.stdout
   ```

3. Test Agent Discovery manually:
   ```python
   # Manual test of Agent Discovery
   from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError
   
   try:
       ad = AgentDiscovery()
       stats = ad.get_registry_stats()
       print(f"Registry stats: {stats}")
       
       # Try to find specific agent types
       miners = ad.get_miner_agents()
       wallets = ad.get_wallet_agents()
       controllers = ad.get_block_controllers()
       
       print(f"Miners: {len(miners)}, Wallets: {len(wallets)}, Controllers: {len(controllers)}")
   except AgentDiscoveryError as e:
       print(f"Agent discovery failed: {e}")
   ```

### 1. Setup and Installation Issues

#### "Shadow not found" Error

**Symptoms**:
```
[ERROR] Shadow simulator is not installed
```

**Solutions**:
1. **Install Shadow**:
   ```bash
   # Follow official installation guide
   # https://shadow.github.io/docs/guide/install/
   
   # Verify installation
   shadow --version
   ```

2. **Check PATH**:
   ```bash
   echo $PATH
   which shadow
   
   # Add to PATH if needed
   export PATH=$PATH:/path/to/shadow/bin
   ```

#### "monerod not found" Error

**Symptoms**:
```
[ERROR] monerod binary not found
```

**Solutions**:
1. **Run setup script**:
   ```bash
   ./setup.sh
   ```

2. **Manual installation**:
   ```bash
   # Find built binary
   find builds/ -name monerod -type f
   
   # Install manually
   sudo cp builds/A/monero/bin/monerod /usr/local/bin/
   sudo chmod +x /usr/local/bin/monerod
   ```

3. **Verify installation**:
   ```bash
   /usr/local/bin/monerod --version
   ```

#### Rust/Cargo Issues

**Symptoms**:
```
[ERROR] Failed to build MoneroSim
```

**Solutions**:
1. **Update Rust**:
   ```bash
   rustup update
   rustc --version
   ```

2. **Clean and rebuild**:
   ```bash
   cargo clean
   cargo build --release
   ```

3. **Check dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install build-essential libssl-dev pkg-config

   # Fedora/RHEL
   sudo dnf install gcc gcc-c++ openssl-devel pkgconfig

   # Arch Linux
   sudo pacman -S base-devel openssl pkgconf
   ```

### 2. Configuration Issues

#### Invalid Configuration Format

**Symptoms**:
```
[ERROR] Failed to parse YAML configuration
```

**Solutions**:
1. **Validate YAML syntax**:
   ```bash
   # Use online YAML validator or
   python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"
   ```

2. **Check required fields**:
   ```yaml
   general:
     stop_time: "10m"  # Required
   
   monero:
     nodes:            # Required
       - count: 5      # Required
         name: "A"     # Required
   ```

3. **Use minimal config**:
   ```yaml
   general:
     stop_time: "5m"
   monero:
     nodes:
       - count: 2
         name: "test"
         base_commit: "shadow-complete"
   ```

#### Invalid Time Format

**Symptoms**:
```
[ERROR] Invalid stop_time format
```

**Solutions**:
```yaml
# Correct formats
general:
  stop_time: "30s"     # 30 seconds
  stop_time: "5m"      # 5 minutes
  stop_time: "1h"      # 1 hour
  stop_time: "2h30m"   # 2 hours 30 minutes

# Wrong formats
general:
  stop_time: "10 minutes"  # Wrong
  stop_time: "1.5h"        # Wrong
  stop_time: "3600"        # Wrong (missing unit)
```

### 3. Build Issues

#### Git Repository Issues

**Symptoms**:
```
[ERROR] Failed to clone monero-shadow repository
```

**Solutions**:
1. **Check repository exists**:
   ```bash
   ls -la ../monero-shadow/
   ```

2. **Clone manually**:
   ```bash
   cd ..
   git clone <your-monero-shadow-url> monero-shadow
   cd monero-shadow
   git checkout shadow-complete
   cd ../monerosim
   ```

3. **Update setup script URL**:
   ```bash
   # Edit setup.sh and update MONERO_SHADOW_REPO
   vim setup.sh
   ```

#### Branch Not Found

**Symptoms**:
```
[ERROR] Failed to checkout shadow-complete branch
```

**Solutions**:
1. **Check available branches**:
   ```bash
   cd ../monero-shadow
   git branch -a
   ```

2. **Create branch if missing**:
   ```bash
   git checkout -b shadow-complete
   git push origin shadow-complete
   ```

3. **Use alternative branch**:
   ```yaml
   # In config.yaml
   monero:
     nodes:
       - base_commit: "shadow-compatibility"  # Alternative branch
   ```

#### Patch Application Failures

**Symptoms**:
```
[ERROR] Failed to apply patch
```

**Solutions**:
1. **Check patch compatibility**:
   ```bash
   # Verify patch format
   git apply --check patches/testnet_from_scratch.patch
   ```

2. **Update patch for new Monero version**:
   ```bash
   # Create new patch
   git diff > patches/new_patch.patch
   ```

3. **Skip problematic patches**:
   ```yaml
   # Remove patches from config
   monero:
     nodes:
       - count: 5
         name: "A"
         base_commit: "shadow-complete"
         # patches: []  # No patches
   ```

#### CMake/Make Build Failures

**Symptoms**:
```
[ERROR] Failed to build Monero
```

**Solutions**:
1. **Install missing dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install libboost-all-dev libssl-dev libzmq3-dev

   # Fedora/RHEL
   sudo dnf install boost-devel openssl-devel zeromq-devel

   # Arch Linux
   sudo pacman -S boost openssl zeromq
   ```

2. **Increase system resources**:
   ```bash
   # Use fewer parallel jobs
   export MAKEFLAGS="-j2"
   ```

3. **Clean and rebuild**:
   ```bash
   rm -rf builds/
   cargo build --release
   ```

### 4. Simulation Issues

#### Nodes Not Starting

**Symptoms**:
```
[ERROR] No nodes started successfully
```

**Solutions**:
1. **Check node logs**:
   ```bash
   # Look for startup errors
   grep -i "error\|fail" shadow.data/hosts/*/monerod.*.stderr
   
   # Check RPC initialization
   grep "RPC server initialized" shadow.data/hosts/*/monerod.*.stdout
   ```

2. **Verify binary compatibility**:
   ```bash
   # Test binary directly
   /usr/local/bin/monerod --testnet --help
   ```

3. **Check configuration**:
   ```yaml
   # Ensure proper testnet configuration
   monero:
     nodes:
       - count: 2
         name: "test"
         base_commit: "shadow-complete"  # Includes testnet modifications
   ```

#### No P2P Connections

**Symptoms**:
```
[WARNING] No P2P connections detected
```

**Solutions**:
1. **Increase simulation time**:
   ```yaml
   general:
     stop_time: "30m"  # Longer simulation
   ```

2. **Check network topology**:
   ```bash
   # Verify Shadow configuration
   cat shadow_output/shadow.yaml
   
   # Check for network connectivity
   grep "network_node_id" shadow_output/shadow.yaml
   ```

3. **Verify seed node disabling**:
   ```bash
   # Check that --disable-seed-nodes is used
   grep "disable-seed-nodes" shadow_output/shadow.yaml
   ```

#### Simulation Hangs or Crashes

**Symptoms**:
```
[ERROR] Simulation failed
```

**Solutions**:
1. **Check system resources**:
   ```bash
   # Monitor during simulation
   htop
   df -h
   free -h
   ```

2. **Reduce simulation size**:
   ```yaml
   # Start with smaller simulation
   general:
     stop_time: "5m"
   monero:
     nodes:
       - count: 2  # Fewer nodes
         name: "test"
   ```

3. **Check for infinite loops**:
   ```bash
   # Look for repeated log messages
   tail -f shadow.data/shadow.log
   ```

### 5. Performance Issues

#### Slow Build Times

**Solutions**:
1. **Use parallel builds**:
   ```bash
   # Set number of CPU cores
   export MAKEFLAGS="-j$(nproc)"
   ```

2. **Use ccache**:
   ```bash
   # Install ccache
   sudo apt-get install ccache
   
   # Configure for faster rebuilds
   export CC="ccache gcc"
   export CXX="ccache g++"
   ```

3. **Skip unnecessary builds**:
   ```bash
   # Reuse existing builds
   # Don't delete builds/ directory between runs
   ```

#### High Memory Usage

**Solutions**:
1. **Reduce node count**:
   ```yaml
   monero:
     nodes:
       - count: 10  # Reduce from 50+
         name: "test"
   ```

2. **Optimize Shadow configuration**:
   ```bash
   # Edit shadow_output/shadow.yaml
   # Reduce host_bandwidth_* values
   # Increase model_unblocked_syscall_latency
   ```

3. **Use swap space**:
   ```bash
   # Add swap if needed
   sudo fallocate -l 4G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

#### Slow Simulation Execution

**Solutions**:
1. **Optimize Shadow settings**:
   ```yaml
   # In generated shadow.yaml
   general:
     model_unblocked_syscall_latency: true
     parallelism: 4  # Match CPU cores
   ```

2. **Reduce logging**:
   ```bash
   # Set lower log levels
   export RUST_LOG="warn"
   ```

3. **Use SSD storage**:
   ```bash
   # Move simulation to SSD
   ln -s /path/to/ssd/shadow.data shadow.data
   ```

### 6. Agent Discovery Issues

#### Agent Discovery System Not Working

**Symptoms**:
```
[ERROR] Failed to discover agents
[ERROR] AgentDiscoveryError: No agents found
```

**Solutions**:
1. **Check shared state files**:
   ```bash
   # Verify shared state directory exists
   ls -la /tmp/monerosim_shared/
   
   # Check for required files
   ls -la /tmp/monerosim_shared/{agent_registry,miners,wallets,block_controller}.json
   ```

2. **Verify agent registration**:
   ```bash
   # Check if agents are registering
   tail -f /tmp/monerosim_shared/agent_registry.json
   
   # Monitor agent activity
   watch -n 1 'ls -la /tmp/monerosim_shared/*.json'
   ```

3. **Test Agent Discovery manually**:
   ```python
   # Test Agent Discovery System
   from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError
   
   try:
       ad = AgentDiscovery()
       agents = ad.get_agent_registry()
       print(f"Found {len(agents)} agents")
       
       miners = ad.get_miner_agents()
       print(f"Found {len(miners)} miners")
       
       wallets = ad.get_wallet_agents()
       print(f"Found {len(wallets)} wallets")
   except AgentDiscoveryError as e:
       print(f"Agent discovery error: {e}")
   ```

#### Shared State File Corruption

**Symptoms**:
```
[ERROR] Failed to parse shared state file
[ERROR] JSON decode error
```

**Solutions**:
1. **Check file integrity**:
   ```bash
   # Validate JSON syntax
   python3 -c "import json; json.load(open('/tmp/monerosim_shared/agent_registry.json'))"
   
   # Check file permissions
   ls -la /tmp/monerosim_shared/
   ```

2. **Clear and regenerate**:
   ```bash
   # Clear shared state
   rm -rf /tmp/monerosim_shared/
   mkdir -p /tmp/monerosim_shared
   
   # Restart simulation
   shadow shadow_agents_output/shadow_agents.yaml
   ```

3. **Monitor file creation**:
   ```bash
   # Watch for file creation during simulation
   inotifywait -m /tmp/monerosim_shared/ -e create
   ```

#### Agent Discovery Performance Issues

**Symptoms**:
```
[WARNING] Agent discovery taking too long
[ERROR] Timeout during agent discovery
```

**Solutions**:
1. **Optimize shared state storage**:
   ```bash
   # Use tmpfs for better performance
   sudo mount -t tmpfs -o size=1G tmpfs /tmp/monerosim_shared
   
   # Or use SSD storage
   ln -s /path/to/ssd/monerosim_shared /tmp/monerosim_shared
   ```

2. **Check cache effectiveness**:
   ```python
   # Monitor Agent Discovery cache
   from scripts.agent_discovery import AgentDiscovery
   
   ad = AgentDiscovery()
   
   # First call (reads from disk)
   agents1 = ad.get_agent_registry()
   
   # Second call (uses cache)
   agents2 = ad.get_agent_registry()
   
   # Force cache refresh
   ad.refresh_cache()
   agents3 = ad.get_agent_registry()
   ```

3. **Reduce agent discovery frequency**:
   ```python
   # Cache agent information instead of repeated discovery
   class OptimizedAgent(BaseAgent):
       def __init__(self):
           super().__init__()
           self.agent_discovery = AgentDiscovery()
           self.cached_agents = None
           self.last_discovery = 0
       
       def get_agents(self):
           # Only rediscover every 30 seconds
           current_time = time.time()
           if self.cached_agents is None or current_time - self.last_discovery > 30:
               self.cached_agents = self.agent_discovery.get_agent_registry()
               self.last_discovery = current_time
           return self.cached_agents
   ```

### 7. Network and Connectivity Issues

#### IP Address Conflicts

**Symptoms**:
```
[ERROR] Network configuration error
```

**Solutions**:
1. **Check IP allocation**:
   ```bash
   # Verify IP addresses in Shadow config
   grep "ip" shadow_output/shadow.yaml
   ```

2. **Use different network range**:

#### Port Conflicts

**Symptoms**:
```
[ERROR] Port already in use
```

**Solutions**:
1. **Check port usage**:
   ```bash
   # Find processes using ports
   netstat -tulpn | grep :28080
   ```

2. **Use different port ranges**:

### 7. Analysis and Debugging

#### Understanding Logs

**Key log patterns**:
```bash
# Successful node startup
grep "RPC server initialized OK" shadow.data/hosts/*/monerod.*.stdout

# P2P connections
grep "Connected success" shadow.data/hosts/*/monerod.*.stdout

# Errors
grep -i "error\|fail\|exception" shadow.data/hosts/*/monerod.*.stderr

# Performance issues
grep "slow\|timeout\|delay" shadow.data/hosts/*/monerod.*.stdout
```

#### Debug Mode

**Enable debug logging**:
```bash
# Set debug environment variable
export MONEROSIM_DEBUG=1
export RUST_LOG=debug

# For Python scripts
export LOG_LEVEL=DEBUG

# Run with debug output
./target/release/monerosim --config config.yaml --output debug_output
```

#### Python Script Debugging

**Interactive debugging**:
```bash
# Use Python debugger
python -m pdb scripts/simple_test.py

# Common pdb commands:
# n - next line
# s - step into function
# c - continue
# l - list code
# p variable - print variable
```

**Add debug prints**:
```python
# In scripts, use logging instead of print
from error_handling import log_debug
log_debug(f"Variable value: {variable}")
```

#### Performance Profiling

**Monitor system resources**:
```bash
# CPU and memory usage
htop

# Disk I/O
iotop

# Network usage
iftop

# Process tree
pstree -p $(pgrep shadow)
```

## Getting Help

### 1. Self-Diagnosis

Before seeking help, try these steps:
1. **Read this troubleshooting guide**
2. **Check the logs** for specific error messages
3. **Try minimal configuration** to isolate the issue
4. **Search existing issues** on GitHub

### 2. Reporting Issues

When reporting issues, include:
1. **System information**:
   ```bash
   uname -a
   rustc --version
   shadow --version
   ```

2. **Configuration file** (sanitized):
   ```yaml
   general:
     stop_time: "5m"
   monero:
     nodes:
       - count: 2
         name: "test"
   ```

3. **Error logs**:
   ```bash
   # Relevant log excerpts
   tail -50 shadow.data/shadow.log
   ```

4. **Steps to reproduce**:
   - Exact commands run
   - Expected vs actual behavior
   - When the issue occurs

### 3. Community Resources

- **GitHub Issues**: Report bugs and request features
- **Documentation**: Check `docs/` directory for detailed guides
- **Examples**: Look at `config.yaml` for working configurations

## Prevention Tips

### 1. Regular Maintenance

```bash
# Keep dependencies updated
rustup update
cargo update

# Update Python packages
source venv/bin/activate
pip install --upgrade -r scripts/requirements.txt

# Clean old builds
cargo clean
rm -rf builds/

# Update monero-shadow
cd ../monero-shadow
git pull origin shadow-complete

# Clean agent shared state
rm -rf /tmp/monerosim_shared/
```

### 2. Testing Strategy

```bash
# Always test with small configurations first
# Use version control for configurations
# Keep backup of working configurations
# Document any workarounds or special settings

# Test Python scripts individually before full simulation
python3 scripts/simple_test.py
python3 scripts/sync_check.py

# Run unit tests before deployment
python -m pytest scripts/test_*.py -v
```

### 3. Monitoring

```bash
# Monitor system resources during simulations
# Keep logs for analysis
# Track performance metrics
# Document successful configurations

# Use monitoring script during simulations
python3 scripts/monitor.py --refresh 5

# Monitor agent activity
tail -f /tmp/monerosim_shared/*.json
```

## Common Python Script Commands

### Testing Scripts

```bash
# Basic functionality test
python3 scripts/simple_test.py

# Synchronization check
python3 scripts/sync_check.py --continuous --wait-time 30

# Transaction testing
python3 scripts/transaction_script.py

# P2P connectivity (must run in Shadow)
python3 scripts/test_p2p_connectivity.py

# Real-time monitoring
python3 scripts/monitor.py --refresh 10
```

### Agent Discovery Commands

```bash
# Test agent discovery system
python3 -c "
from scripts.agent_discovery import AgentDiscovery
ad = AgentDiscovery()
print(f'Total agents: {len(ad.get_agent_registry())}')
print(f'Miners: {len(ad.get_miner_agents())}')
print(f'Wallets: {len(ad.get_wallet_agents())}')
print(f'Block controllers: {len(ad.get_block_controllers())}')
"

# Monitor shared state files
watch -n 1 'ls -la /tmp/monerosim_shared/*.json'
tail -f /tmp/monerosim_shared/agent_registry.json

# Test agent discovery with error handling
python3 -c "
from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError
try:
    ad = AgentDiscovery()
    wallet_agents = ad.get_wallet_agents()
    print(f'Found {len(wallet_agents)} wallet agents')
    if len(wallet_agents) < 2:
        print('Script would exit with insufficient wallet agents (expected behavior)')
    else:
        print('Script would proceed with transaction')
except AgentDiscoveryError as e:
    print(f'AgentDiscoveryError: {e}')
except Exception as e:
    print(f'Unexpected error: {e}')
"
For more details on the Agent Discovery System, see [`scripts/README_agent_discovery.md`](scripts/README_agent_discovery.md).
```

### Agent Commands

```bash
# Run individual agents for testing
python3 agents/regular_user.py --name user001 --daemon-url http://11.0.0.1:18081

# Test agent with discovery integration
python3 -c "
from agents.regular_user import RegularUser
from scripts.agent_discovery import AgentDiscovery

# Create agent with automatic discovery
agent = RegularUser('test_user')
agent.setup()
agent.run()
agent.cleanup()
"
```
