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

That's it! The script will:
- ✅ Install all dependencies (Rust, Shadow, build tools)
- ✅ Clone and patch Monero source code for Shadow compatibility
- ✅ Build MoneroSim
- ✅ Build Monero binaries with Shadow patches
- ✅ Install Monero binaries to system PATH
- ✅ Run a test simulation
- ✅ Show you the results

## What You'll See

The script will output colored progress messages:
- 🔵 **[INFO]** - General information
- 🟢 **[SUCCESS]** - Something worked correctly
- 🟡 **[WARNING]** - Non-critical issues
- 🔴 **[ERROR]** - Something failed

## After Setup

Once setup completes, you can:

### Run Custom Simulations

```bash
# Edit simulation parameters
vim config.yaml

# Generate new configuration
./target/release/monerosim --config config.yaml --output shadow_output

# Run simulation
shadow shadow_output/shadow.yaml
```

### Analyze Results

```bash
# Check if nodes started
grep "RPC server initialized OK" shadow.data/hosts/*/monerod.*.stdout

# Check P2P connections (should show successful connections!)
grep "Connected success" shadow.data/hosts/*/monerod.*.stdout

# Look for TCP connection establishment
grep "handle_accept" shadow.data/hosts/*/monerod.*.stdout
```

### Change Simulation Duration

Edit `config.yaml`:
```yaml
general:
  stop_time: "30m"  # Run for 30 minutes instead of 10

monero:
  nodes: 8          # Simulate 8 nodes instead of 5
```

## Common Issues

**"Shadow not found"**: Install Shadow manually from https://shadow.github.io/docs/guide/install/

**Permission denied**: Make sure you can run `sudo` commands

**Script fails**: Check the error message - most issues are dependency-related

## Need Help?

- Check the full README.md for detailed documentation
- Look at Shadow logs: `shadow.data/shadow.log`
- Check node logs: `shadow.data/hosts/*/monerod.*.stdout`

**Happy simulating!** 🚀 