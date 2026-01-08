# Monerosim Configurator

## Problem

The current configuration experience is cumbersome. Users must manually create YAML stanzas for each agent in files like `config_32_agents.yaml`. For simulations with many agents, this means duplicating blocks repeatedly and manually managing details like hashrate distribution.

## Proposed Solution

A natural language configurator that allows users to describe simulations in plain English:

> "I want 100 stable mining nodes, then 30 nodes running a newer binary join after 1 hour to test upgrade compatibility"

The system generates a configuration file that can be used directly with monerosim.

## Architecture

```
┌─────────────────────────────────────────┐
│  Website (e.g., configurator.monerosim.org) │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  Natural language input         │    │
│  └─────────────┬───────────────────┘    │
│                ↓                         │
│  ┌─────────────────────────────────┐    │
│  │  LLM + RAG                      │    │
│  │  (DSL spec + examples in context)│   │
│  └─────────────┬───────────────────┘    │
│                ↓                         │
│  ┌─────────────────────────────────┐    │
│  │  configurator.yaml preview      │    │
│  │  [Download] [Copy] [Edit]       │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘

            User downloads
                 ↓
$ python expand_config.py configurator.yaml > monerosim.yaml
                 ↓
$ monerosim --config monerosim.yaml
```

### Why Web-Based?

- No LLM dependencies in monerosim itself
- Users don't need to install Ollama or similar
- Can use powerful hosted models (Claude API, etc.)
- Easy to update prompts/RAG context without monerosim releases
- Nice entry point for new users

### Why RAG Instead of Fine-Tuning?

- Config schema is well-defined and documentable
- Just inject DSL spec + examples into prompt context
- General LLM + good context = understands monerosim configs
- No training data collection needed
- Easier to maintain as DSL evolves

## Intermediate DSL (configurator.yaml)

A scenario-based, high-level configuration format that gets expanded into the full monerosim.yaml.

### Example

```yaml
simulation:
  duration: "2h"
  network: "1_gbit_switch"
  topology: "mesh"

binaries:
  current: "~/.monerosim/bin/monerod-v18"
  upgrade: "~/.monerosim/bin/monerod-v19"

scenarios:
  - name: "established_network"
    type: miner
    count: 100
    binary: current
    hashrate: even          # auto-distribute among this group
    behavior: autonomous

  - name: "regular_users"
    type: wallet
    count: 50
    daemon: auto            # connects to random available daemon
    transactions:
      interval: "30s"
      amount: "10-100"      # random range

  - name: "upgrade_nodes"
    type: miner
    count: 30
    binary: upgrade
    start_time: "1h"
    hashrate: "30% total"   # collectively 30% of network
    behavior: autonomous

# Optional: override specific agents in a scenario
overrides:
  - scenario: "established_network"
    index: 0
    attributes:
      special_flag: "true"
```

### DSL Features

- `count`: Number of agents in a scenario group
- `hashrate`: `even` (distribute among group), `X% each`, `X% total`
- `type`: `miner`, `wallet`, `daemon_only`, `script_only`
- `binary`: Reference to named binary (for fork/upgrade testing)
- `start_time`: Delayed join
- `daemon: auto`: Connect to random available daemon
- `transactions`: Wallet behavior config
- `overrides`: One-off tweaks for specific agents

## Expander Script

Python script that converts configurator.yaml → monerosim.yaml:
- Expands `count` into individual agent stanzas
- Distributes hashrates according to rules
- Validates constraints (hashrates sum correctly, scripts exist, etc.)
- Keeps monerosim binary clean

## Prerequisites

### Multi-Binary Support in Monerosim

Before the configurator can support fork/upgrade testing, monerosim needs to support multiple daemon binaries:

```yaml
# Needed in monerosim.yaml
binaries:
  stable: "/opt/monero/v18/monerod"
  experimental: "/opt/monero/v19-rc/monerod"

agents:
  user_agents:
    - daemon:
        binary: stable
    - daemon:
        binary: experimental
      start_time_offset: "1h"
```

This should be implemented first to inform the final DSL design.

## Open Questions

1. Should the web configurator have a conversational mode (back-and-forth refinement) or one-shot generation?
2. Exact hashrate distribution semantics when mixing `even`, `X% each`, and `X% total`
3. How to handle wallet-rpc versioning (must it match daemon version?)
4. Validation: what constraints should the expander enforce?

## Status

Parked. Implement multi-binary support in monerosim first.
