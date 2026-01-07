# Shadow Simulation Execution

## Pre-Execution Checklist

**CRITICAL**:
```bash
# 1. Kill existing Shadow processes
pkill shadow

# 2. Clean previous data
rm -rf shadow.data shadow.log
```

## Running Simulation (Background Mode)

```bash
rm -rf shadow.data && nohup ~/.monerosim/bin/shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &
```

Or use the convenience script:
```bash
./run_sim.sh
```

## Monitoring

Check progress occasionally (NOT continuously):
```bash
tail shadow.log
```

**NEVER use `tail -f`** - wastes resources

## Normal Termination

Expect: "N managed processes in unexpected final state"
- Means: Simulation reached time limit, killed processes
- Status: **Normal behavior**, not an error

## Key Paths
- Shadow binary: `~/.monerosim/bin/shadow`
- Shadow libraries: `~/.monerosim/lib/`
- Output: `shadow.data/hosts/[hostname]/`
