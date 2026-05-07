"""
Simulation Monitor agent package.

This package replaces the previous single-file `agents/simulation_monitor.py`
module with a directory of submodules grouped by concern:

  - agent.py        : SimulationMonitorAgent class (the orchestrator)
  - alerts.py       : alert evaluation + rendering helpers (pure)
  - log_parser.py   : monerod log mining-event detection (pure)
  - metadata.py     : git-commit / config-metadata discovery helpers
  - status_paths.py : shadow.data/hosts path resolution helper

The agent class itself stays as a single class in agent.py; only genuinely
free-standing helpers were extracted into the other submodules. Methods
that touch many ``self.*`` attributes remained methods (matching the
heuristic from the miner_distributor decomposition).

Backwards-compat: the import path `agents.simulation_monitor` still
resolves to a module exposing `SimulationMonitorAgent` (and `main`), so
callers and the orchestrator-generated wrapper scripts continue to work
unchanged.
"""

from .agent import SimulationMonitorAgent, main

# Re-export AgentDiscovery at the package level so existing patch targets
# (e.g. tests using ``mocker.patch("agents.simulation_monitor.AgentDiscovery.__init__", ...)``)
# continue to resolve after the single-file -> package conversion.
from ..agent_discovery import AgentDiscovery  # noqa: F401

__all__ = ['SimulationMonitorAgent', 'main']
