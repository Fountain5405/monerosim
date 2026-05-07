"""
Metadata-discovery helpers for SimulationMonitorAgent.

These read environment-level information (git commit, monerosim config
file) without touching any agent state. Factored out of
agents/simulation_monitor.py.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


def get_git_commit_hash() -> str:
    """Get the current git commit hash of the monerosim codebase."""
    try:
        # Try to get git commit from the monerosim directory
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def get_config_metadata(shared_dir: Path,
                        logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """Read metadata from the monerosim config file.

    Searches a fixed set of candidate locations relative to cwd and to
    the agent's shared_dir. Returns the parsed metadata block (or the
    full JSON contents of config_metadata.json) on first match, otherwise
    an empty dict.
    """
    import yaml

    # Try common config file locations
    config_candidates = [
        Path("monerosim.expanded.yaml"),
        Path("monerosim.yaml"),
        Path("config.yaml"),
        shared_dir / "config_metadata.json",
    ]

    # Also check parent directories
    cwd = Path.cwd()
    for parent in [cwd, cwd.parent, cwd.parent.parent]:
        config_candidates.append(parent / "monerosim.expanded.yaml")
        config_candidates.append(parent / "monerosim.yaml")
        config_candidates.append(parent / "config.yaml")

    for config_path in config_candidates:
        try:
            if config_path.exists():
                if config_path.suffix == '.json':
                    with open(config_path, 'r') as f:
                        return json.load(f)
                else:
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                        if config and 'metadata' in config:
                            return config['metadata']
        except Exception as e:
            if logger is not None:
                logger.debug(f"Could not read config from {config_path}: {e}")
            continue

    return {}
