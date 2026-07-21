# Running Simulations

This guide covers the end-to-end workflow for running Monerosim simulations.

## Prerequisites

- Monerosim built (`cargo build --release`)
- shadowformonero and Monero binaries installed to `~/.monerosim/bin/`
- Python virtual environment set up (`source venv/bin/activate`)

If you haven't set up the environment yet, run `./setup.sh` first. It will install shadowformonero (a Shadow fork with Monero socket compatibility), build official Monero from source, and set up all dependencies.

## Step 1: Generate Shadow Configuration

```bash
./target/release/monerosim --config test_configs/quickstart.yaml --output shadow_output
```

This parses your YAML configuration and generates:
- `shadow_output/shadow_agents.yaml` - the Shadow configuration
- `<shared-dir>/agent_registry.json` - agent metadata
- `<shared-dir>/miners.json` - miner hashrate distribution

`<shared-dir>` defaults to `/tmp/monerosim_shared/` when the generator is run standalone, as above. When invoked through `run_sim.sh` (the recommended workflow, see Step 2), each run instead gets its own namespaced directory, `/tmp/monerosim-<runid>/shared/`, so concurrent runs on one box don't collide. The resolved paths for a given run are breadcrumbed to `shadow_output/run_env.sh` — `source` it to get `$MONEROSIM_DAEMON_DATA_DIR` and `$MONEROSIM_SHARED_DIR`. See [docs/20260721_per_run_tmp_namespacing.md](20260721_per_run_tmp_namespacing.md) for details.

The `--output` flag defaults to `shadow_output` if omitted.

### CLI Options

| Flag | Description |
|------|-------------|
| `--config <path>` | Path to YAML configuration file (required) |
| `--output <path>` | Output directory (default: `shadow_output`) |

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

A simulation with a typical configuration (8h simulation time, 25 agents) takes several hours of wall-clock time depending on your hardware.

**Normal termination message**: When Shadow finishes, you will see a message like "N managed processes in unexpected final state". This is expected behavior - Shadow terminates all processes when the simulation time limit is reached.

## Step 4: Analyze Results

### Quick verification

```bash
# Load this run's paths (breadcrumbed by run_sim.sh)
source shadow_output/run_env.sh

# Check if daemons started
grep "RPC server initialized OK" "$MONEROSIM_DAEMON_DATA_DIR"/monero-*/bitmonero.log

# Check P2P connections
grep "Connected success" "$MONEROSIM_DAEMON_DATA_DIR"/monero-*/bitmonero.log

# Check agent discovery
cat "$MONEROSIM_SHARED_DIR"/agent_registry.json
```

### Analysis tools (LLM-generated, unverified)

There is an LLM-generated analysis tool (`tx-analyzer`, the Rust binary at `target/release/tx-analyzer`) in the repository for examining transaction routing and network behavior. Its results have **not been human-verified** and should not be trusted without independent validation. See [ANALYSIS_TOOLS.md](ANALYSIS_TOOLS.md) for details.

## Log File Locations

| Log | Path |
|-----|------|
| Shadow main log | `shadow.log` |
| Daemon logs | `$MONEROSIM_DAEMON_DATA_DIR/monero-[agent]/bitmonero.log` |
| Agent logs (Python) | `shadow.data/hosts/[hostname]/bash.*.stdout` |
| Shared state | `$MONEROSIM_SHARED_DIR/*.json` |

`$MONEROSIM_DAEMON_DATA_DIR` and `$MONEROSIM_SHARED_DIR` are per-run paths under `/tmp/monerosim-<runid>/`; run `source shadow_output/run_env.sh` to load them (see Step 1). The legacy global defaults (`/tmp/monero-[agent]/`, `/tmp/monerosim_shared/`) only apply when the generator is run standalone, outside `run_sim.sh`.

## Interpreting Logs

Shadow emits warnings during normal operation that look alarming but are expected for Monero workloads on every distro. Distinguish noise from real failures using the lists below.

### Expected warnings (safe to ignore)

| Pattern (in `shadow.log`) | What it is |
|---|---|
| `[WARN] ... ioctl.c ... ioctl request 21519` | `TIOCGWINSZ` — monerod queries terminal size on stderr at startup. Shadow doesn't fully emulate ttys; the call fails harmlessly. |
| `[WARN] ... regular_file.c ... /proc/sys/crypto/fips_enabled` | monerod's crypto init reads Linux's FIPS-mode flag. Shadow's regular_file shim falls through to the host's value (always `0` on a normal box), which is what monerod expects. |
| `[WARN] ... Detected unsupported syscall umask` | Shadow doesn't emulate `umask`. Processes use the default file-creation mask, which is irrelevant to the simulation. |
| `N managed processes in unexpected final state` | Shadow terminates all processes when `stop_time` is reached. Normal end-of-simulation message. |

These appear on every Monerosim run. They are not portability issues, not configuration-specific, and not a sign that anything is wrong.

### Real failure signals (investigate)

If any of the following appear, the simulation likely has a real problem:

- **Non-zero exit code from `run_sim.sh`** — Shadow itself crashed.
- **`[ERROR]` lines (not `[WARN]`) in `shadow.log`** — Shadow recorded an error condition. Read surrounding context.
- **`Killed` or signal-related shutdowns of monerod processes mid-sim** — typically OOM, or a crash. Check `$MONEROSIM_DAEMON_DATA_DIR/monero-[agent]/bitmonero.log` for the cause.
- **`shadow.data/hosts/*/monerod.*.stdout` empty or missing for many agents** at end of sim — many daemons failed to start or were killed.
- **`./scripts/check_sim.sh` reporting 0 P2P connections** after the bootstrap window — peer discovery failed; check `peer_mode` and seed nodes.
- **Non-zero exit from `./scripts/smoke_test.sh`** — Tier 2 baselines (block-height floor, transaction floors, disallowed log patterns from `tests/baselines/`) failed. Indicates a real regression.

For real errors, start with the relevant per-agent log at `$MONEROSIM_DAEMON_DATA_DIR/monero-[agent]/bitmonero.log` — that has the actual failure context, while `shadow.log` aggregates Shadow-level events.

## Testing Approaches

### Post-simulation analysis (recommended)

1. Wait for the simulation to complete
2. Use grep on raw logs (e.g., `"$MONEROSIM_DAEMON_DATA_DIR"/monero-*/bitmonero.log`, after `source shadow_output/run_env.sh`) for detailed investigation
3. Run `./target/release/tx-analyzer` for transaction-flow analysis (see [ANALYSIS_TOOLS.md](ANALYSIS_TOOLS.md))

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

Using a typical configuration:

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
