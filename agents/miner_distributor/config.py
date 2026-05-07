"""
Configuration parsing helpers for MinerDistributorAgent.

These are factored out of agents/miner_distributor.py so the parsing logic
lives separately from the agent's runtime state. The agent class still owns
configuration via thin wrapper methods that delegate here.
"""

from typing import Optional


def parse_time_duration(value) -> Optional[int]:
    """Parse time duration string (e.g., '1h', '30m', '3600s')"""
    if isinstance(value, (int, float)):
        return int(value)
    elif isinstance(value, str):
        try:
            if value.endswith('h'):
                return int(float(value[:-1]) * 3600)
            elif value.endswith('m'):
                return int(float(value[:-1]) * 60)
            elif value.endswith('s'):
                return int(float(value[:-1]))
            else:
                return int(float(value))
        except ValueError:
            return None
    return None
