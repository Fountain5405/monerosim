"""
Miner Distributor agent package.

This package replaces the previous single-file `agents/miner_distributor.py`
module with a directory of submodules grouped by concern:

  - agent.py     : MinerDistributorAgent class (the orchestrator)
  - config.py    : configuration parsing helpers
  - discovery.py : miner-wallet discovery helpers
  - funding.py   : funding-cycle helpers (batch sizing)
  - selection.py : miner-selection strategy helpers
  - state.py     : persisted funding-status schema

The agent class itself stays as a single class in agent.py; only genuinely
free-standing helpers were extracted into the other submodules.

Backwards-compat: the import path `agents.miner_distributor` still resolves
to a module exposing `MinerDistributorAgent` (and `main`), so callers and
the orchestrator-generated wrapper scripts continue to work unchanged.
"""

from .agent import MinerDistributorAgent, main

__all__ = ['MinerDistributorAgent', 'main']
