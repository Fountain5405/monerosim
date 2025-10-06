# MoneroSim Quick Start Guide

**Get MoneroSim running in 5 minutes!**

## 🎉 P2P Connectivity Working!

MoneroSim now successfully establishes P2P connections between Monero nodes! The setup script will verify that nodes can connect and communicate with each other.

## Prerequisites

You need:
- Linux system (Ubuntu, Debian, CentOS, Arch, etc.)
- Internet connection
- Sudo access

## Installation

```bash
# 1. Clone the repository
git clone <repository_url>
cd monerosim

# 2. Run the automated setup script (takes 20-40 minutes)
./setup.sh
```

**Note**: The setup process includes building Monero from source with Shadow compatibility patches, which can take 20-40 minutes depending on your system.

The script will:
- ✅ Install all dependencies (Rust, Shadow, build tools)
- ✅ Clone and patch Monero source code for Shadow compatibility
- ✅ Build MoneroSim
- ✅ Build Monero binaries with Shadow patches
- ✅ Install Monero binaries to system PATH
- ✅ Prompt you about Shadow installation (if existing Shadow detected)
- ✅ Prompt you whether to run a test simulation (config_47_agents.yaml takes 6-7 hours)
- ✅ Show you the results if you choose to run the test

## What You'll See

The script will output colored progress messages:
- 🔵 **[INFO]** - General information
- 🟢 **[SUCCESS]** - Something worked correctly
- 🟡 **[WARNING]** - Non-critical issues
- 🔴 **[ERROR]** - Something failed

## After Setup

Once setup completes, you can:

**Note**: For analysis scripts and agent operations, activate the Python virtual environment:
```bash
source venv/bin/activate
```

### Run Custom Simulations

```bash
# Edit simulation parameters
vim config_47_agents.yaml

# Generate new configuration
./target/release/monerosim --config config_47_agents.yaml --output shadow_agents_output

# Run simulation
shadow shadow_agents_output/shadow_agents.yaml
```

### Analyze Results

First, process the logs for summarized analysis:

```bash
source venv/bin/activate
python scripts/log_processor.py
```

This creates `.processed_log` files with summarized information. Check these files first for a quick overview, or use grep commands for specific patterns:

```bash
# Check if nodes started
grep "RPC server initialized OK" shadow.data/hosts/*/monerod.*.stdout

# Check P2P connections (should show successful connections!)
grep "Connected success" shadow.data/hosts/*/monerod.*.stdout

# Look for TCP connection establishment
grep "handle_accept" shadow.data/hosts/*/monerod.*.stdout

# Check agent discovery files
ls -la /tmp/monerosim_shared/
cat /tmp/monerosim_shared/agent_registry.json
```

### Agent Discovery System

MoneroSim uses a dynamic agent discovery system that automatically finds and tracks agents during simulation:

- **Agent Registry**: `/tmp/monerosim_shared/agent_registry.json` contains all agent information
- **Dynamic Discovery**: Agents are discovered at runtime, not hardcoded
- **Type-Based Queries**: Find miners, wallets, and other agents by type

For more details, see [Agent Discovery System](agents/README_agent_discovery.md).

### Change Simulation Duration

Edit `config_47_agents.yaml`:
```yaml
general:
  stop_time: "30m"  # Run for 30 minutes instead of 10

agents:
  user_agents:
    # Add more users to increase simulation size
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      is_miner: true
      attributes:
        hashrate: "50"
    
    - daemon: "monerod"
      wallet: "monero-wallet-rpc"
      user_script: "agents.regular_user"
      attributes:
        transaction_interval: "60"
        min_transaction_amount: "0.5"
        max_transaction_amount: "2.0"
```

## Common Issues

**"Shadow not found"**: Install Shadow manually from https://shadow.github.io/docs/guide/install/

**Permission denied**: Make sure you can run `sudo` commands

**Script fails**: Check the error message - most issues are dependency-related

## Need Help?

- Check the full README.md for detailed documentation
- Look at Shadow logs: `shadow.data/shadow.log`
- Check node logs: `shadow.data/hosts/*/monerod.*.stdout`
- Review Agent Discovery documentation: [Agent Discovery System](agents/README_agent_discovery.md)

**Happy simulating!** 🚀