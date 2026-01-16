"""
Validator for monerosim YAML configurations.

Analyzes a config and produces a structured report describing what the
simulation will do. This report is used for:
1. Validating the config matches user intent
2. Providing feedback to the LLM for corrections
"""

import yaml
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path


def parse_time_to_seconds(time_str: str) -> int:
    """Parse time string like '3h', '30m', '3h30s', '18000s', '18000' to seconds."""
    if isinstance(time_str, (int, float)):
        return int(time_str)

    time_str = str(time_str).strip()

    # Pure number (assume seconds)
    if time_str.isdigit():
        return int(time_str)

    total = 0
    # Match patterns like 3h, 30m, 45s
    patterns = [
        (r'(\d+)h', 3600),
        (r'(\d+)m', 60),
        (r'(\d+)s', 1),
    ]

    for pattern, multiplier in patterns:
        match = re.search(pattern, time_str)
        if match:
            total += int(match.group(1)) * multiplier

    return total if total > 0 else int(re.sub(r'[^\d]', '', time_str) or 0)


def seconds_to_human(seconds: int) -> str:
    """Convert seconds to human readable format like '3h 30m 45s'."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


@dataclass
class AgentInfo:
    """Information about a single agent."""
    agent_id: str
    agent_type: str  # miner, user, spy, distributor, monitor, unknown
    daemon: Optional[str] = None
    wallet: Optional[str] = None
    script: Optional[str] = None
    start_time_s: int = 0
    hashrate: Optional[int] = None
    transaction_interval: Optional[int] = None
    activity_start_time_s: Optional[int] = None

    # Daemon phase info
    has_phases: bool = False
    daemon_0: Optional[str] = None
    daemon_0_start_s: Optional[int] = None
    daemon_0_stop_s: Optional[int] = None
    daemon_1: Optional[str] = None
    daemon_1_start_s: Optional[int] = None
    phase_gap_s: Optional[int] = None

    # Spy node info
    out_peers: Optional[int] = None
    in_peers: Optional[int] = None


@dataclass
class UpgradeInfo:
    """Information about upgrade scenario."""
    enabled: bool = False
    agents_with_phases: int = 0
    total_agents: int = 0
    v1_binary: Optional[str] = None
    v2_binary: Optional[str] = None
    upgrade_start_s: Optional[int] = None
    upgrade_end_s: Optional[int] = None
    min_stagger_s: Optional[int] = None
    max_stagger_s: Optional[int] = None
    avg_stagger_s: Optional[float] = None
    min_gap_s: Optional[int] = None
    agents_with_invalid_gap: List[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    """Complete validation report for a monerosim config."""

    # Basic validity
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # General settings
    stop_time_s: int = 0
    bootstrap_end_time_s: int = 0
    simulation_seed: Optional[int] = None

    # Network
    network_type: Optional[str] = None
    peer_mode: Optional[str] = None

    # Agent counts
    total_agents: int = 0
    miner_count: int = 0
    user_count: int = 0
    spy_count: int = 0
    has_distributor: bool = False
    has_monitor: bool = False

    # Miner stats
    total_hashrate: int = 0
    hashrate_distribution: Dict[str, int] = field(default_factory=dict)

    # User stats
    user_start_time_range: Tuple[int, int] = (0, 0)
    activity_start_time_range: Tuple[int, int] = (0, 0)

    # Spy node stats
    spy_connections: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # agent_id -> (out, in)

    # Upgrade info
    upgrade: UpgradeInfo = field(default_factory=UpgradeInfo)

    # All agents
    agents: List[AgentInfo] = field(default_factory=list)

    def to_summary(self) -> str:
        """Generate a natural language summary of the config."""
        lines = []

        lines.append("## Configuration Summary\n")

        # Duration
        lines.append(f"**Duration:** {seconds_to_human(self.stop_time_s)}")
        lines.append(f"**Bootstrap period:** {seconds_to_human(self.bootstrap_end_time_s)}")
        if self.simulation_seed:
            lines.append(f"**Seed:** {self.simulation_seed}")
        lines.append("")

        # Network
        lines.append(f"**Network:** {self.network_type or 'default'}, {self.peer_mode or 'Dynamic'} peer mode")
        lines.append("")

        # Agents
        lines.append(f"**Total agents:** {self.total_agents}")
        lines.append(f"  - Miners: {self.miner_count} (total hashrate: {self.total_hashrate})")
        lines.append(f"  - Users: {self.user_count}")
        if self.spy_count:
            lines.append(f"  - Spy nodes: {self.spy_count}")
        lines.append(f"  - Distributor: {'Yes' if self.has_distributor else 'NO (missing!)'}")
        lines.append(f"  - Monitor: {'Yes' if self.has_monitor else 'No'}")
        lines.append("")

        # Hashrate distribution
        if self.hashrate_distribution:
            lines.append("**Hashrate distribution:**")
            for agent_id, hr in sorted(self.hashrate_distribution.items()):
                lines.append(f"  - {agent_id}: {hr}")
            lines.append("")

        # User timing
        if self.user_count > 0:
            start_min, start_max = self.user_start_time_range
            act_min, act_max = self.activity_start_time_range
            lines.append(f"**User timing:**")
            lines.append(f"  - Start time: {seconds_to_human(start_min)} to {seconds_to_human(start_max)}")
            lines.append(f"  - Activity start: {seconds_to_human(act_min)} to {seconds_to_human(act_max)}")
            lines.append("")

        # Spy nodes
        if self.spy_connections:
            lines.append("**Spy nodes:**")
            for agent_id, (out_p, in_p) in self.spy_connections.items():
                lines.append(f"  - {agent_id}: {out_p} out-peers, {in_p} in-peers")
            lines.append("")

        # Upgrade scenario
        if self.upgrade.enabled:
            lines.append("**Upgrade scenario:**")
            lines.append(f"  - Agents with phases: {self.upgrade.agents_with_phases}/{self.upgrade.total_agents}")
            lines.append(f"  - Binary v1: {self.upgrade.v1_binary}")
            lines.append(f"  - Binary v2: {self.upgrade.v2_binary}")
            if self.upgrade.upgrade_start_s is not None:
                lines.append(f"  - Upgrade window: {seconds_to_human(self.upgrade.upgrade_start_s)} to {seconds_to_human(self.upgrade.upgrade_end_s or 0)}")
            if self.upgrade.avg_stagger_s is not None:
                lines.append(f"  - Stagger: {self.upgrade.avg_stagger_s:.1f}s avg (min: {self.upgrade.min_stagger_s}s, max: {self.upgrade.max_stagger_s}s)")
            if self.upgrade.min_gap_s is not None:
                lines.append(f"  - Phase gap: {self.upgrade.min_gap_s}s minimum")
            if self.upgrade.agents_with_invalid_gap:
                lines.append(f"  - WARNING: {len(self.upgrade.agents_with_invalid_gap)} agents have gap < 30s")
            lines.append("")

        # Errors and warnings
        if self.errors:
            lines.append("**ERRORS:**")
            for err in self.errors:
                lines.append(f"  - {err}")
            lines.append("")

        if self.warnings:
            lines.append("**Warnings:**")
            for warn in self.warnings:
                lines.append(f"  - {warn}")
            lines.append("")

        return "\n".join(lines)

    def to_checklist(self, user_request: str) -> str:
        """Generate a checklist comparing config to user request."""
        lines = []
        lines.append("## Validation Checklist\n")
        lines.append(f"**User request:** {user_request}\n")
        lines.append("**Generated config:**")
        lines.append(f"  - {self.miner_count} miners")
        lines.append(f"  - {self.user_count} users")
        lines.append(f"  - {self.spy_count} spy nodes")
        lines.append(f"  - Duration: {seconds_to_human(self.stop_time_s)}")
        lines.append(f"  - Total hashrate: {self.total_hashrate}")
        lines.append(f"  - Has distributor: {self.has_distributor}")
        lines.append(f"  - Has monitor: {self.has_monitor}")
        if self.upgrade.enabled:
            lines.append(f"  - Upgrade: {self.upgrade.v1_binary} -> {self.upgrade.v2_binary}")
            lines.append(f"  - Upgrade stagger: {self.upgrade.avg_stagger_s:.1f}s avg")
        lines.append("")

        if self.errors:
            lines.append("**Issues to fix:**")
            for err in self.errors:
                lines.append(f"  - {err}")

        return "\n".join(lines)


class ConfigValidator:
    """Validates monerosim YAML configurations."""

    def validate_file(self, path: str) -> ValidationReport:
        """Validate a YAML config file."""
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
        return self.validate(config)

    def validate_yaml(self, yaml_content: str) -> ValidationReport:
        """Validate YAML content string."""
        config = yaml.safe_load(yaml_content)
        return self.validate(config)

    def validate(self, config: Dict[str, Any]) -> ValidationReport:
        """Validate a config dictionary."""
        report = ValidationReport()

        # Check required sections
        if not config:
            report.is_valid = False
            report.errors.append("Config is empty")
            return report

        if 'general' not in config:
            report.is_valid = False
            report.errors.append("Missing 'general' section")

        if 'agents' not in config:
            report.is_valid = False
            report.errors.append("Missing 'agents' section")
            return report

        # Parse general section
        general = config.get('general', {})
        if 'stop_time' in general:
            report.stop_time_s = parse_time_to_seconds(general['stop_time'])
        else:
            report.errors.append("Missing 'stop_time' in general section")

        report.bootstrap_end_time_s = parse_time_to_seconds(general.get('bootstrap_end_time', '4h'))
        report.simulation_seed = general.get('simulation_seed')

        # Parse network section
        network = config.get('network', {})
        report.network_type = network.get('type') or network.get('path', 'default')
        report.peer_mode = network.get('peer_mode', 'Dynamic')

        # Parse agents
        agents = config.get('agents', {})
        report.total_agents = len(agents)

        miners = []
        users = []
        spies = []
        phase_agents = []

        for agent_id, agent_config in agents.items():
            if not isinstance(agent_config, dict):
                continue

            info = self._parse_agent(agent_id, agent_config)
            report.agents.append(info)

            if info.agent_type == 'miner':
                miners.append(info)
                report.miner_count += 1
                if info.hashrate:
                    report.total_hashrate += info.hashrate
                    report.hashrate_distribution[agent_id] = info.hashrate
            elif info.agent_type == 'user':
                users.append(info)
                report.user_count += 1
            elif info.agent_type == 'spy':
                spies.append(info)
                report.spy_count += 1
                if info.out_peers or info.in_peers:
                    report.spy_connections[agent_id] = (info.out_peers or 0, info.in_peers or 0)
            elif info.agent_type == 'distributor':
                report.has_distributor = True
            elif info.agent_type == 'monitor':
                report.has_monitor = True

            if info.has_phases:
                phase_agents.append(info)

        # User timing ranges
        if users:
            start_times = [u.start_time_s for u in users]
            report.user_start_time_range = (min(start_times), max(start_times))

            activity_times = [u.activity_start_time_s for u in users if u.activity_start_time_s]
            if activity_times:
                report.activity_start_time_range = (min(activity_times), max(activity_times))

        # Analyze upgrade scenario
        if phase_agents:
            report.upgrade = self._analyze_upgrade(phase_agents, report.total_agents)

        # Validation checks
        if report.user_count > 0 and not report.has_distributor:
            report.warnings.append("Users exist but no miner-distributor to fund them")

        if report.total_hashrate != 100 and report.miner_count > 0:
            report.warnings.append(f"Total hashrate is {report.total_hashrate}, not 100")

        return report

    def _parse_agent(self, agent_id: str, config: Dict[str, Any]) -> AgentInfo:
        """Parse a single agent configuration."""
        info = AgentInfo(agent_id=agent_id, agent_type='unknown')

        # Determine agent type
        script = config.get('script', '')
        if 'miner_distributor' in script:
            info.agent_type = 'distributor'
        elif 'simulation_monitor' in script:
            info.agent_type = 'monitor'
        elif 'autonomous_miner' in script:
            info.agent_type = 'miner'
        elif 'regular_user' in script:
            # Check if it's a spy node (high peer counts)
            daemon_opts = config.get('daemon_options', {})
            out_peers = daemon_opts.get('out-peers', 0)
            in_peers = daemon_opts.get('in-peers', 0)
            if out_peers >= 100 or in_peers >= 100:
                info.agent_type = 'spy'
                info.out_peers = out_peers
                info.in_peers = in_peers
            else:
                info.agent_type = 'user'
        elif 'spy' in agent_id.lower():
            info.agent_type = 'spy'
            daemon_opts = config.get('daemon_options', {})
            info.out_peers = daemon_opts.get('out-peers', 0)
            info.in_peers = daemon_opts.get('in-peers', 0)
        elif 'miner' in agent_id.lower() and 'distributor' not in agent_id.lower():
            info.agent_type = 'miner'
        elif 'user' in agent_id.lower():
            info.agent_type = 'user'

        # Basic fields
        info.daemon = config.get('daemon')
        info.wallet = config.get('wallet')
        info.script = script
        info.start_time_s = parse_time_to_seconds(config.get('start_time', '0s'))
        info.hashrate = config.get('hashrate')
        info.transaction_interval = config.get('transaction_interval')

        if 'activity_start_time' in config:
            info.activity_start_time_s = parse_time_to_seconds(config['activity_start_time'])

        # Phase switching
        if 'daemon_0' in config:
            info.has_phases = True
            info.daemon_0 = config.get('daemon_0')
            info.daemon_1 = config.get('daemon_1')

            if 'daemon_0_start' in config:
                info.daemon_0_start_s = parse_time_to_seconds(config['daemon_0_start'])
            if 'daemon_0_stop' in config:
                info.daemon_0_stop_s = parse_time_to_seconds(config['daemon_0_stop'])
            if 'daemon_1_start' in config:
                info.daemon_1_start_s = parse_time_to_seconds(config['daemon_1_start'])

            if info.daemon_0_stop_s is not None and info.daemon_1_start_s is not None:
                info.phase_gap_s = info.daemon_1_start_s - info.daemon_0_stop_s

        return info

    def _analyze_upgrade(self, phase_agents: List[AgentInfo], total_agents: int) -> UpgradeInfo:
        """Analyze upgrade scenario from agents with phases."""
        upgrade = UpgradeInfo()
        upgrade.enabled = True
        upgrade.agents_with_phases = len(phase_agents)
        upgrade.total_agents = total_agents

        # Get binary names
        for agent in phase_agents:
            if agent.daemon_0:
                upgrade.v1_binary = agent.daemon_0
            if agent.daemon_1:
                upgrade.v2_binary = agent.daemon_1
            if upgrade.v1_binary and upgrade.v2_binary:
                break

        # Analyze timing
        stop_times = [a.daemon_0_stop_s for a in phase_agents if a.daemon_0_stop_s is not None]
        start_times = [a.daemon_1_start_s for a in phase_agents if a.daemon_1_start_s is not None]
        gaps = [a.phase_gap_s for a in phase_agents if a.phase_gap_s is not None]

        if stop_times:
            upgrade.upgrade_start_s = min(stop_times)
        if start_times:
            upgrade.upgrade_end_s = max(start_times)

        # Calculate stagger (time between consecutive upgrades)
        if len(stop_times) > 1:
            sorted_stops = sorted(stop_times)
            staggers = [sorted_stops[i+1] - sorted_stops[i] for i in range(len(sorted_stops)-1)]
            staggers = [s for s in staggers if s > 0]  # Filter zero staggers
            if staggers:
                upgrade.min_stagger_s = min(staggers)
                upgrade.max_stagger_s = max(staggers)
                upgrade.avg_stagger_s = sum(staggers) / len(staggers)

        # Check gaps
        if gaps:
            upgrade.min_gap_s = min(gaps)
            for agent in phase_agents:
                if agent.phase_gap_s is not None and agent.phase_gap_s < 30:
                    upgrade.agents_with_invalid_gap.append(agent.agent_id)

        return upgrade


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python validator.py <config.yaml>")
        sys.exit(1)

    validator = ConfigValidator()
    report = validator.validate_file(sys.argv[1])
    print(report.to_summary())
