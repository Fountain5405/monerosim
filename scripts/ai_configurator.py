#!/usr/bin/env python3
"""
AI-powered configurator for monerosim scenarios.

Describe your simulation scenario in natural language, and this tool will
generate a valid monerosim YAML configuration file.

Supports multiple LLM backends:
  - Ollama (local): OLLAMA_HOST=http://localhost:11434
  - Claude API: ANTHROPIC_API_KEY=sk-ant-...
  - OpenAI-compatible: OPENAI_API_KEY=... OPENAI_BASE_URL=...

Usage:
    python scripts/ai_configurator.py "I want 50 nodes that reach steady
    state then upgrade to a new binary"

    python scripts/ai_configurator.py --provider ollama --model llama3.1:8b \
        "simulate a 51% attack with one miner controlling most hashrate"

    python scripts/ai_configurator.py --interactive
"""

import argparse
import json
import os
import sys
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import urllib.request
import urllib.error

# Schema context for the LLM - describes what monerosim can do
# Compact version (~2700 chars) for smaller models (7B-8B)
MONEROSIM_SCHEMA_COMPACT = """
# Monerosim YAML Config Schema (Monero network simulator)

## Structure:
```yaml
general:
  stop_time: "6h"           # Duration
  simulation_seed: 12345
  bootstrap_end_time: "4h"  # Sync period
  enable_dns_server: true
  daemon_defaults: {log-level: 1, db-sync-mode: fastest, no-zmq: true}
  wallet_defaults: {log-level: 1}

network:
  type: 1_gbit_switch
  peer_mode: Dynamic

agents:
  miner-001:                # Miners produce blocks
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    start_time: 0s
    hashrate: 20            # Sum to ~100 for easy %
    can_receive_distributions: true

  user-001:                 # Users send transactions
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.regular_user
    start_time: 3h
    transaction_interval: 60
    activity_start_time: 18000
    can_receive_distributions: true

  miner-distributor:        # Funds users
    script: agents.miner_distributor
    wait_time: 14400
    transaction_frequency: 30

  simulation-monitor:
    script: agents.simulation_monitor
    poll_interval: 300
```

## Agent naming: miner-001, user-001, spy-001, etc.

## Upgrade scenario (phase switching):
```yaml
user-001:
  wallet: monero-wallet-rpc
  script: agents.regular_user
  daemon_0: monerod-v1
  daemon_0_start: "3h"
  daemon_0_stop: "7h"
  daemon_1: monerod-v2
  daemon_1_start: "7h30s"   # 30s+ gap required
```

## Spy nodes (many connections):
```yaml
spy-001:
  daemon: monerod
  daemon_options: {out-peers: 500, in-peers: 500}
```

## Timing: bootstrap ~4h for sync, users start at 3h, activity at 5h (18000s)
"""

EXAMPLE_SCENARIOS_COMPACT = """
## Example: 30 nodes for 8 hours
```yaml
general:
  stop_time: 8h
  bootstrap_end_time: 4h
  enable_dns_server: true
  daemon_defaults: {log-level: 1, db-sync-mode: fastest, no-zmq: true}
network:
  type: 1_gbit_switch
  peer_mode: Dynamic
agents:
  miner-001: {daemon: monerod, wallet: monero-wallet-rpc, script: agents.autonomous_miner, start_time: 0s, hashrate: 20}
  miner-002: {daemon: monerod, wallet: monero-wallet-rpc, script: agents.autonomous_miner, start_time: 0s, hashrate: 20}
  # ... more miners (hashrates sum to 100)
  user-001: {daemon: monerod, wallet: monero-wallet-rpc, script: agents.regular_user, start_time: 3h, activity_start_time: 18000}
  # ... more users
  miner-distributor: {script: agents.miner_distributor, wait_time: 14400}
  simulation-monitor: {script: agents.simulation_monitor, poll_interval: 300}
```
"""

# Detailed version for larger models (14B+, Claude, GPT-4, etc.)
MONEROSIM_SCHEMA_DETAILED = """
# Monerosim Configuration Schema

Monerosim simulates Monero cryptocurrency networks using Shadow network simulator.
Configs are YAML files with these main sections:

## 1. general - Simulation settings
```yaml
general:
  stop_time: "8h"              # Simulation duration (e.g., "30m", "2h", "1d")
  simulation_seed: 12345       # Random seed for reproducibility
  parallelism: 0               # 0=auto, 1=deterministic single-thread
  bootstrap_end_time: "4h"     # High bandwidth period (for blockchain sync)
  progress: true               # Show progress bar
  enable_dns_server: true      # Enable peer discovery via DNS seeding
  shadow_log_level: info       # trace/debug/info/warning/error
  daemon_defaults:             # Default flags for all monerod instances
    log-level: 1
    db-sync-mode: fastest
    no-zmq: true
  wallet_defaults:
    log-level: 1
```

## 2. network - Topology configuration
```yaml
# Option A: Simple switch (all nodes same LAN, fast)
network:
  type: 1_gbit_switch
  peer_mode: Dynamic           # Dynamic/Hardcoded/Hybrid

# Option B: GML topology (realistic Internet simulation)
network:
  path: gml_processing/1200_nodes_caida_with_loops.gml
  peer_mode: Dynamic
```

## 3. agents - Network participants
Each agent needs a unique ID (e.g., miner-001, user-001, spy-001).

### Agent Types:

#### Miners (produce blocks)
```yaml
miner-001:
  daemon: monerod
  wallet: monero-wallet-rpc
  script: agents.autonomous_miner
  start_time: 0s
  hashrate: 25                 # Mining power (relative, sum to ~100)
  can_receive_distributions: true
```

#### Regular Users (send transactions)
```yaml
user-001:
  daemon: monerod
  wallet: monero-wallet-rpc
  script: agents.regular_user
  start_time: 3h               # Start after some bootstrap time
  transaction_interval: 60     # Seconds between transactions
  activity_start_time: 18000   # When to start sending (seconds from sim start)
  can_receive_distributions: true
```

#### Miner Distributor (funds users from mining rewards)
```yaml
miner-distributor:
  script: agents.miner_distributor
  wait_time: 14400             # Start distributing after this (seconds, ~4h)
  initial_fund_amount: "1.0"   # XMR per user
  transaction_frequency: 30    # Seconds between distributions
```

#### Simulation Monitor (logging/alerts)
```yaml
simulation-monitor:
  script: agents.simulation_monitor
  poll_interval: 300           # Check network status every N seconds
  enable_alerts: true
```

### Daemon Phase Switching (for upgrade scenarios)
Agents can switch daemon binaries during simulation:
```yaml
user-001:
  wallet: monero-wallet-rpc
  script: agents.regular_user
  start_time: 3h
  daemon_0: monerod-v1         # Phase 0 binary
  daemon_0_start: "3h"         # When phase 0 starts
  daemon_0_stop: "7h"          # When phase 0 stops (daemon shuts down)
  daemon_1: monerod-v2         # Phase 1 binary
  daemon_1_start: "7h30s"      # Must be 30s+ after phase 0 stop (restart gap)
```

### Custom Daemon Options (per-agent)
```yaml
spy-node:
  daemon: monerod
  daemon_options:
    out-peers: 500             # Many outbound connections (spy node)
    in-peers: 500              # Many inbound connections
    log-level: 2               # More verbose logging
```

## Key Timing Considerations:
- Bootstrap period (~4h): High bandwidth, no packet loss, nodes sync the blockchain
- Coinbase unlock: Mining rewards unlock after 60 blocks (~2h at 2min/block)
- Activity start: Users should wait for funding (typically bootstrap_end + 1h)
- Phase gaps: At least 30 seconds between daemon phases for graceful restart

## Common Scenarios:

1. **Basic Network**: 5 miners + N users, steady state transaction activity
2. **Upgrade Scenario**: Network upgrades binaries mid-simulation using daemon phases
3. **Spy Nodes**: Nodes with many connections monitoring the network
4. **51% Attack**: One miner with >50% hashrate
5. **Network Partition**: Using GML topology with regional weights
6. **Stress Test**: Many users with low transaction_interval
"""

EXAMPLE_SCENARIOS_DETAILED = """
## Example Scenario Descriptions → Configs

### Example 1: "30 nodes doing transactions for 8 hours"
```yaml
general:
  stop_time: 8h
  simulation_seed: 12345
  bootstrap_end_time: 4h
  enable_dns_server: true
  daemon_defaults:
    log-level: 1
    db-sync-mode: fastest
    no-zmq: true
  wallet_defaults:
    log-level: 1
network:
  type: 1_gbit_switch
  peer_mode: Dynamic
agents:
  miner-001:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    start_time: 0s
    hashrate: 20
    can_receive_distributions: true
  miner-002:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    start_time: 0s
    hashrate: 20
    can_receive_distributions: true
  # ... (5 miners total with hashrates summing to 100)
  user-001:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.regular_user
    start_time: 3h
    transaction_interval: 60
    activity_start_time: 18000
    can_receive_distributions: true
  # ... (25 users total)
  miner-distributor:
    script: agents.miner_distributor
    wait_time: 14400
    transaction_frequency: 30
  simulation-monitor:
    script: agents.simulation_monitor
    poll_interval: 300
```

### Example 2: "5 spy nodes with 500 connections each monitoring 50 regular nodes"
- Create 5 spy agents with high out-peers/in-peers daemon options
- Create 50 regular user agents
- Spy nodes can observe without wallets (daemon-only)
```yaml
agents:
  spy-001:
    daemon: monerod
    script: agents.regular_user  # or just daemon, no wallet
    start_time: 0s
    daemon_options:
      out-peers: 500
      in-peers: 500
      log-level: 2
  # ... 4 more spy nodes
```

### Example 3: "Upgrade scenario - switch from monerod-v1 to monerod-v2 after 4 hours"
- Use daemon_0/daemon_1 phase fields
- Stagger upgrade times across nodes (30s-1min apart)
- Ensure 30s+ gap between stop and start times
```yaml
agents:
  user-001:
    wallet: monero-wallet-rpc
    script: agents.regular_user
    start_time: 3h
    daemon_0: monerod-v1
    daemon_0_start: "3h"
    daemon_0_stop: "4h"
    daemon_1: monerod-v2
    daemon_1_start: "4h30s"
  user-002:
    # staggered: stops at 4h30s, starts at 5h
```

### Example 4: "51% attack simulation"
- One miner with 51+ hashrate, others with remaining
```yaml
agents:
  attacker:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    start_time: 0s
    hashrate: 55
  miner-001:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    start_time: 0s
    hashrate: 15
  # ... (other miners with remaining hashrate summing to 45)
```
"""


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> LLMResponse:
        """Send a chat completion request."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available/configured."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for display."""
        pass


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    def __init__(self, model: str = "llama3.1:8b", host: str = None):
        self.model = model
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    @property
    def name(self) -> str:
        return f"Ollama ({self.model})"

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.host}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except:
            return False

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> LLMResponse:
        data = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature}
        }).encode()

        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            return LLMResponse(
                content=result["message"]["content"],
                model=self.model,
                usage=result.get("eval_count")
            )


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str = None):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    @property
    def name(self) -> str:
        return f"Claude ({self.model})"

    def is_available(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> LLMResponse:
        # Extract system message if present
        system = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                chat_messages.append(msg)

        data = {
            "model": self.model,
            "max_tokens": 8192,
            "messages": chat_messages,
            "temperature": temperature
        }
        if system:
            data["system"] = system

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(data).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            return LLMResponse(
                content=result["content"][0]["text"],
                model=self.model,
                usage=result.get("usage")
            )


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible API provider (works with OpenAI, vLLM, LM Studio, etc.)."""

    def __init__(self, model: str = "gpt-4o-mini", api_key: str = None, base_url: str = None):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    @property
    def name(self) -> str:
        return f"OpenAI-compatible ({self.model})"

    def is_available(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> LLMResponse:
        data = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,  # Ensure enough tokens for full config generation
        }).encode()

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        )

        with urllib.request.urlopen(req, timeout=600) as resp:  # 10 min timeout for large responses
            result = json.loads(resp.read().decode())
            return LLMResponse(
                content=result["choices"][0]["message"]["content"],
                model=self.model,
                usage=result.get("usage")
            )


def get_provider(provider_name: str, model: str = None) -> LLMProvider:
    """Get an LLM provider by name."""
    if provider_name == "ollama":
        return OllamaProvider(model=model or "llama3.1:8b")
    elif provider_name == "claude":
        return AnthropicProvider(model=model or "claude-sonnet-4-20250514")
    elif provider_name == "openai":
        return OpenAICompatibleProvider(model=model or "gpt-4o-mini")
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


def auto_detect_provider() -> Optional[LLMProvider]:
    """Auto-detect an available LLM provider."""
    # Check Ollama first (local, free)
    ollama = OllamaProvider()
    if ollama.is_available():
        return ollama

    # Check Claude API
    claude = AnthropicProvider()
    if claude.is_available():
        return claude

    # Check OpenAI
    openai = OpenAICompatibleProvider()
    if openai.is_available():
        return openai

    return None


def build_system_prompt(detailed: bool = False) -> str:
    """Build the system prompt with schema context.

    Args:
        detailed: If True, use comprehensive schema (~6000 chars) for larger models.
                  If False, use compact schema (~2700 chars) for smaller models.
    """
    if detailed:
        schema = MONEROSIM_SCHEMA_DETAILED
        examples = EXAMPLE_SCENARIOS_DETAILED
        instructions = """## Your Task:
1. Understand the user's scenario description
2. Ask clarifying questions if critical details are missing
3. Generate a complete, valid YAML configuration

## Response Format:
- If you need clarification, ask specific questions
- When generating config, output ONLY the YAML inside ```yaml ... ``` code blocks
- Include helpful comments in the YAML explaining the configuration
- Ensure all timing values are consistent (bootstrap, activity start, phases, etc.)

## Important Rules:
- Always include miner-distributor if there are users (they need funding)
- Always include simulation-monitor for observability
- Use realistic timing: 4h bootstrap, 5h activity start for standard scenarios
- Hashrates should sum to ~100 for easy percentage reasoning
- Phase gaps must be at least 30 seconds
- Agent IDs must be unique (use patterns like miner-001, user-001, spy-001)
"""
    else:
        schema = MONEROSIM_SCHEMA_COMPACT
        examples = EXAMPLE_SCENARIOS_COMPACT
        instructions = "Rules: Include miner-distributor (funds users) and simulation-monitor. Hashrates sum to 100. Agent IDs: miner-001, user-001, etc."

    intro = "You generate monerosim YAML configs. Output ONLY valid YAML in ```yaml blocks." if not detailed else "You are a monerosim configuration generator. Your job is to convert natural language descriptions of Monero network simulation scenarios into valid YAML configuration files."

    return f"""{intro}

{schema}

{examples}

{instructions}
"""


def extract_yaml_from_response(response: str) -> Optional[str]:
    """Extract YAML content from LLM response."""
    # Look for ```yaml ... ``` blocks
    pattern = r"```yaml\s*(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)
    if matches:
        return matches[-1].strip()  # Return the last YAML block

    # Try ``` ... ``` without yaml tag
    pattern = r"```\s*(general:.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)
    if matches:
        return matches[-1].strip()

    return None


def validate_yaml(yaml_content: str) -> tuple[bool, str]:
    """Basic validation of generated YAML."""
    try:
        import yaml
        config = yaml.safe_load(yaml_content)

        errors = []

        # Check required sections
        if "general" not in config:
            errors.append("Missing 'general' section")
        if "agents" not in config:
            errors.append("Missing 'agents' section")

        # Check general has stop_time
        if "general" in config and "stop_time" not in config["general"]:
            errors.append("Missing 'stop_time' in general section")

        # Check agents have required fields
        if "agents" in config:
            for agent_id, agent in config["agents"].items():
                if not isinstance(agent, dict):
                    continue
                # Agents with scripts need at least a script
                # Agents with daemons need daemon or daemon_0
                has_daemon = "daemon" in agent or "daemon_0" in agent
                has_wallet = "wallet" in agent
                has_script = "script" in agent

                if not has_script and not has_daemon:
                    errors.append(f"Agent '{agent_id}' has no script or daemon")

        if errors:
            return False, "\n".join(errors)
        return True, "Valid"

    except Exception as e:
        return False, f"YAML parse error: {e}"


class Configurator:
    """AI-powered configurator for monerosim."""

    def __init__(self, provider: LLMProvider, detailed_prompt: bool = False):
        self.provider = provider
        self.detailed_prompt = detailed_prompt
        self.messages = [
            {"role": "system", "content": build_system_prompt(detailed=detailed_prompt)}
        ]

    def chat(self, user_message: str) -> str:
        """Send a message and get a response."""
        self.messages.append({"role": "user", "content": user_message})

        response = self.provider.chat(self.messages, temperature=0.3)
        assistant_message = response.content

        self.messages.append({"role": "assistant", "content": assistant_message})

        return assistant_message

    def generate_config(self, description: str, output_file: str = None) -> Optional[str]:
        """Generate a config from a description."""
        print(f"\nUsing {self.provider.name}")
        prompt_mode = "detailed" if self.detailed_prompt else "compact"
        print(f"Prompt mode: {prompt_mode}")
        print(f"Generating config for: {description[:100]}{'...' if len(description) > 100 else ''}")
        print()

        # Initial request
        response = self.chat(f"""Please generate a monerosim configuration for this scenario:

{description}

If you need any clarification about the scenario, ask me. Otherwise, generate the complete YAML configuration.""")

        # Check if it's a question or a config
        yaml_content = extract_yaml_from_response(response)

        if yaml_content:
            # Validate the YAML
            is_valid, validation_msg = validate_yaml(yaml_content)

            if is_valid:
                if output_file:
                    with open(output_file, 'w') as f:
                        f.write(f"# Generated by ai_configurator.py\n")
                        f.write(f"# Scenario: {description[:80]}{'...' if len(description) > 80 else ''}\n")
                        f.write(f"#\n\n")
                        f.write(yaml_content)
                        f.write("\n")
                    print(f"Configuration saved to: {output_file}")
                return yaml_content
            else:
                print(f"Validation issues: {validation_msg}")
                print("Asking LLM to fix...")

                fix_response = self.chat(f"The generated config has issues: {validation_msg}\n\nPlease fix these issues and regenerate the complete YAML.")
                yaml_content = extract_yaml_from_response(fix_response)

                if yaml_content and output_file:
                    with open(output_file, 'w') as f:
                        f.write(f"# Generated by ai_configurator.py\n")
                        f.write(f"# Scenario: {description[:80]}{'...' if len(description) > 80 else ''}\n\n")
                        f.write(yaml_content)
                        f.write("\n")
                    print(f"Configuration saved to: {output_file}")
                return yaml_content

        # LLM asked questions - print them for interactive mode
        print("The AI needs clarification:")
        print("-" * 40)
        print(response)
        print("-" * 40)
        return None


def interactive_mode(configurator: Configurator, output_file: str):
    """Interactive conversation mode."""
    print("\nInteractive mode - describe your scenario or answer questions.")
    print("Type 'quit' to exit, 'save' to save current config.\n")

    current_yaml = None

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if not user_input:
            continue

        if user_input.lower() == 'quit':
            break

        if user_input.lower() == 'save':
            if current_yaml:
                with open(output_file, 'w') as f:
                    f.write(current_yaml)
                print(f"Saved to {output_file}")
            else:
                print("No configuration to save yet.")
            continue

        response = configurator.chat(user_input)
        print(f"\nAssistant: {response}\n")

        # Check if response contains YAML
        yaml_content = extract_yaml_from_response(response)
        if yaml_content:
            current_yaml = yaml_content
            is_valid, msg = validate_yaml(yaml_content)
            if is_valid:
                print(f"[Config generated - type 'save' to save to {output_file}]")
            else:
                print(f"[Config has issues: {msg}]")


def main():
    parser = argparse.ArgumentParser(
        description="AI-powered monerosim configuration generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Auto-detect provider, describe scenario
    python scripts/ai_configurator.py "50 nodes with 5 miners, upgrade to new binary after 2h"

    # Use specific provider
    python scripts/ai_configurator.py --provider ollama --model llama3.1:8b "simple 30 node network"

    # Interactive mode
    python scripts/ai_configurator.py --interactive

Environment variables:
    OLLAMA_HOST         Ollama server URL (default: http://localhost:11434)
    ANTHROPIC_API_KEY   Claude API key
    OPENAI_API_KEY      OpenAI API key
    OPENAI_BASE_URL     OpenAI-compatible base URL
        """
    )

    parser.add_argument(
        "description",
        nargs="?",
        help="Natural language description of the simulation scenario"
    )

    parser.add_argument(
        "--provider", "-p",
        choices=["auto", "ollama", "claude", "openai"],
        default="auto",
        help="LLM provider to use (default: auto-detect)"
    )

    parser.add_argument(
        "--model", "-m",
        help="Model name (provider-specific, e.g., 'llama3.1:8b', 'claude-sonnet-4-20250514')"
    )

    parser.add_argument(
        "--output", "-o",
        default="generated_config.yaml",
        help="Output filename (default: generated_config.yaml)"
    )

    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Interactive conversation mode"
    )

    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List available providers and exit"
    )

    parser.add_argument(
        "--detailed-prompt", "-d",
        action="store_true",
        help="Use detailed prompt (~6000 chars) for larger models (14B+, Claude, GPT-4). "
             "Default uses compact prompt (~2700 chars) optimized for 7B models."
    )

    args = parser.parse_args()

    # List providers
    if args.list_providers:
        print("Checking available providers...\n")

        providers = [
            ("ollama", OllamaProvider()),
            ("claude", AnthropicProvider()),
            ("openai", OpenAICompatibleProvider()),
        ]

        for name, provider in providers:
            status = "available" if provider.is_available() else "not configured"
            print(f"  {name:10s} - {status}")

        print("\nTo configure providers:")
        print("  ollama: Install and run Ollama (https://ollama.com)")
        print("  claude: Set ANTHROPIC_API_KEY environment variable")
        print("  openai: Set OPENAI_API_KEY environment variable")
        return 0

    # Get provider
    if args.provider == "auto":
        provider = auto_detect_provider()
        if not provider:
            print("Error: No LLM provider available.")
            print("Run with --list-providers to see configuration options.")
            return 1
    else:
        try:
            provider = get_provider(args.provider, args.model)
            if not provider.is_available():
                print(f"Error: Provider '{args.provider}' is not available/configured.")
                return 1
        except ValueError as e:
            print(f"Error: {e}")
            return 1

    # Create configurator
    configurator = Configurator(provider, detailed_prompt=args.detailed_prompt)

    # Interactive or single-shot mode
    if args.interactive:
        interactive_mode(configurator, args.output)
    elif args.description:
        result = configurator.generate_config(args.description, args.output)
        if not result:
            print("\nThe AI needs more information. Run with --interactive for conversation mode.")
            return 1
    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
