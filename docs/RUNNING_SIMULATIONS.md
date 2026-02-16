# Running Simulations

This guide covers the end-to-end workflow for running Monerosim simulations.

## Prerequisites

- Monerosim built (`cargo build --release`)
- shadowformonero and Monero binaries installed to `~/.monerosim/bin/`
- Python virtual environment set up (`source venv/bin/activate`)

If you haven't set up the environment yet, run `./setup.sh` first. It will install shadowformonero (a Shadow fork with Monero socket compatibility), build official Monero from source, and set up all dependencies.

## Step 1: Generate Shadow Configuration

```bash
./target/release/monerosim --config monerosim.expanded.yaml --output shadow_output
```

This parses your YAML configuration and generates:
- `shadow_output/shadow_agents.yaml` - the Shadow configuration
- `/tmp/monerosim_shared/agent_registry.json` - agent metadata
- `/tmp/monerosim_shared/miners.json` - miner hashrate distribution

The `--output` flag defaults to `shadow_output` if omitted.

### CLI Options

| Flag | Description |
|------|-------------|
| `--config <path>` | Path to YAML configuration file (required) |
| `--output <path>` | Output directory (default: `shadow_output`) |
| `--migrate` | Migrate old config format to new |
| `--migrate-output <path>` | Output path for migrated config |

## Step 2: Run the Simulation

### Using the convenience script

```bash
./run_sim.sh
```

### Manual execution

```bash
# Kill any existing Shadow processes
pkill shadow

# Clean previous simulation data
rm -rf shadow.data shadow.log

# Run Shadow in the background
nohup ~/.monerosim/bin/shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &
```

### Monitoring progress

Check simulation progress periodically:
```bash
tail shadow.log
```

Do **not** use `tail -f` as it consumes unnecessary resources.

## Step 3: Wait for Completion

A simulation with the default `monerosim.expanded.yaml` configuration (8h simulation time, 25 agents) takes several hours of wall-clock time depending on your hardware.

**Normal termination message**: When Shadow finishes, you will see a message like "N managed processes in unexpected final state". This is expected behavior - Shadow terminates all processes when the simulation time limit is reached.

## Step 4: Analyze Results

### Process logs first

```bash
source venv/bin/activate
python scripts/log_processor.py
```

This creates `.processed_log` files with summarized information. Always check these before reading raw logs.

### Quick verification

```bash
# Check if daemons started
grep "RPC server initialized OK" shadow.data/hosts/*/monerod.*.stdout

# Check P2P connections
grep "Connected success" shadow.data/hosts/*/monerod.*.stdout

# Check agent discovery
cat /tmp/monerosim_shared/agent_registry.json
```

### Analysis tools (LLM-generated, unverified)

There are also LLM-generated analysis tools (`tx-analyzer`, `scripts/tx_analyzer.py`) in the repository for examining transaction routing and network behavior. These have **not been human-verified** and their results should not be trusted without independent validation. See [ANALYSIS_TOOLS.md](ANALYSIS_TOOLS.md) for details.

## Log File Locations

| Log | Path |
|-----|------|
| Shadow main log | `shadow.log` |
| Daemon logs | `shadow.data/hosts/[hostname]/monerod.*.stdout` |
| Wallet logs | `shadow.data/hosts/[hostname]/wallet.*.stdout` |
| Agent logs | `shadow.data/hosts/[hostname]/bash.*.stdout` |
| Shared state | `/tmp/monerosim_shared/*.json` |

## Testing Approaches

### Post-simulation analysis (recommended)

1. Wait for the simulation to complete
2. Process logs with `log_processor.py`
3. Analyze processed logs (`.processed_log` files)
4. Use grep on raw logs for detailed investigation

### In-simulation monitoring

Add a `simulation_monitor` agent to your configuration:

```yaml
agents:
  simulation-monitor:
    script: agents.simulation_monitor
    poll_interval: 300
    enable_alerts: true
```

The monitor writes status information internally during the simulation. Review its logs post-simulation.

**Important**: The simulation environment is isolated. External scripts cannot access the virtual network during runtime. All monitoring must happen through agents defined in the configuration.

## Typical Simulation Timeline

Using the default `monerosim.expanded.yaml` configuration:

| Time | Event |
|------|-------|
| t=0 | Miners start, begin generating blocks |
| t=3h | User agents spawn and connect |
| t=4h | Bootstrap period ends, miner distributor starts funding users |
| t=5h | Users begin sending transactions |
| t=8h | Simulation ends |

## Troubleshooting

**Shadow not found**: Ensure `~/.monerosim/bin/` is in your PATH. Run `source ~/.bashrc` or add it manually.

**Permission errors on shadow.data**: Monero wallet-rpc sometimes creates directories with restrictive permissions. The Monerosim CLI handles this automatically when cleaning up, but if you need to manually delete: `chmod -R 755 shadow.data && rm -rf shadow.data`.

**Processes not connecting**: Check that `peer_mode` is set correctly and that seed nodes are reachable for Hardcoded/Hybrid modes.

**High memory usage**: Large simulations (100+ agents) require 16GB+ RAM. Consider reducing agent count or using a shorter `stop_time` for initial testing.
