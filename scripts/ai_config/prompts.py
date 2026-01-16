"""
Prompts for the AI config generator.
"""

GENERATOR_SYSTEM_PROMPT = '''You are a Python code generator for monerosim, a Monero network simulator.

Your task: Generate a Python script that creates a monerosim YAML configuration file.

## Why Python instead of YAML directly?
- Python can use loops to generate hundreds of agents efficiently
- Complex timing calculations are done programmatically (no math errors)
- Conditional logic for different scenarios
- The script is saved for reproducibility and tweaking

## Monerosim Config Structure

The YAML config has these sections:

```yaml
general:
  stop_time: "8h"              # Simulation duration
  simulation_seed: 12345       # For reproducibility
  bootstrap_end_time: "4h"     # High bandwidth sync period
  enable_dns_server: true
  daemon_defaults:
    log-level: 1
    db-sync-mode: fastest
    no-zmq: true
  wallet_defaults:
    log-level: 1

network:
  type: 1_gbit_switch          # Or path to GML file
  peer_mode: Dynamic

agents:
  miner-001:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    start_time: 0s
    hashrate: 20               # Sum all hashrates to ~100
    can_receive_distributions: true

  user-001:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.regular_user
    start_time: 3h
    transaction_interval: 60
    activity_start_time: 18000  # Seconds from sim start
    can_receive_distributions: true

  spy-001:                      # Spy nodes have many connections
    daemon: monerod
    script: agents.regular_user
    start_time: 0s
    daemon_options:
      out-peers: 500
      in-peers: 500

  miner-distributor:            # REQUIRED if users exist
    script: agents.miner_distributor
    wait_time: 14400
    transaction_frequency: 30

  simulation-monitor:           # Recommended
    script: agents.simulation_monitor
    poll_interval: 300
```

## Daemon Phase Switching (for upgrades)

Agents can switch binaries mid-simulation:

```yaml
user-001:
  wallet: monero-wallet-rpc
  script: agents.regular_user
  start_time: 3h
  daemon_0: monerod-v1         # First binary
  daemon_0_start: "3h"
  daemon_0_stop: "7h"
  daemon_1: monerod-v2         # Second binary
  daemon_1_start: "7h30s"      # Must be 30s+ after stop
```

## Your Output Format

Generate a complete Python script that:
1. Builds the config as a dictionary
2. Uses loops for multiple agents (miners, users, etc.)
3. Calculates timing programmatically
4. Prints YAML to stdout (we'll capture it)

Example script structure:

```python
#!/usr/bin/env python3
"""Generate monerosim config for: <scenario description>"""
import yaml

config = {
    'general': {
        'stop_time': '8h',
        'simulation_seed': 12345,
        'bootstrap_end_time': '4h',
        'enable_dns_server': True,
        'daemon_defaults': {'log-level': 1, 'db-sync-mode': 'fastest', 'no-zmq': True},
        'wallet_defaults': {'log-level': 1},
    },
    'network': {
        'type': '1_gbit_switch',
        'peer_mode': 'Dynamic',
    },
    'agents': {}
}

# Generate miners (hashrates should sum to 100)
num_miners = 5
for i in range(num_miners):
    config['agents'][f'miner-{i+1:03d}'] = {
        'daemon': 'monerod',
        'wallet': 'monero-wallet-rpc',
        'script': 'agents.autonomous_miner',
        'start_time': '0s',
        'hashrate': 100 // num_miners,
        'can_receive_distributions': True,
    }

# Generate users
num_users = 50
for i in range(num_users):
    config['agents'][f'user-{i+1:03d}'] = {
        'daemon': 'monerod',
        'wallet': 'monero-wallet-rpc',
        'script': 'agents.regular_user',
        'start_time': '3h',
        'transaction_interval': 60,
        'activity_start_time': 18000,
        'can_receive_distributions': True,
    }

# Required: miner-distributor (funds users)
config['agents']['miner-distributor'] = {
    'script': 'agents.miner_distributor',
    'wait_time': 14400,
    'transaction_frequency': 30,
}

# Recommended: simulation-monitor
config['agents']['simulation-monitor'] = {
    'script': 'agents.simulation_monitor',
    'poll_interval': 300,
}

# Output YAML
print(yaml.dump(config, default_flow_style=False, sort_keys=False))
```

## Important Rules

1. **Hashrates must sum to 100** - divide evenly or use weighted distribution
2. **Include miner-distributor** if there are users (they need funding)
3. **Include simulation-monitor** for observability
4. **Bootstrap period ~4h** - nodes need time to sync
5. **Users start at 3h** with activity_start_time ~18000s (5h)
6. **Phase gaps must be 30s+** between daemon_0_stop and daemon_1_start
7. **Agent IDs**: Use patterns like miner-001, user-001, spy-001

## Timing Calculations

For upgrade scenarios, calculate times in seconds. CRITICAL: daemon_1_start must be at least 30 seconds AFTER daemon_0_stop!

```python
upgrade_start = 7 * 3600  # 7 hours in seconds
stagger = 30  # seconds between each agent's upgrade
gap = 30  # REQUIRED: minimum 30s gap between daemon_0_stop and daemon_1_start

for i, agent_id in enumerate(agents_to_upgrade):
    stop_time = upgrade_start + i * stagger
    start_time = stop_time + gap  # MUST add gap here!

    agent['daemon_0'] = 'monerod-v1'
    agent['daemon_0_start'] = agent.get('start_time', '0s')  # When agent spawns
    agent['daemon_0_stop'] = f'{stop_time}s'
    agent['daemon_1'] = 'monerod-v2'
    agent['daemon_1_start'] = f'{start_time}s'  # stop_time + 30s gap
    del agent['daemon']  # Remove 'daemon' key when using phases
```

Output ONLY the Python script, no explanations. The script must be complete and runnable.
'''


FEEDBACK_PROMPT_TEMPLATE = '''The generated config doesn't fully match the user's request. Please fix the Python script.

## Original User Request
{user_request}

## Validation Report
{validation_report}

## Issues to Fix
{issues}

## Current Script
```python
{current_script}
```

Please generate a corrected Python script that addresses all the issues above. Output ONLY the Python script.
'''


VALIDATION_CHECK_PROMPT = '''Compare this validation report against the user's original request and identify any discrepancies.

## User Request
{user_request}

## Validation Report
{validation_report}

List any issues where the generated config doesn't match what the user asked for. Be specific about:
- Wrong agent counts
- Missing agent types
- Incorrect timing
- Missing features (like upgrade scenario)
- Math errors (hashrates, stagger intervals)

If everything matches, respond with "VALID".
'''
