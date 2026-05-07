"""
Path-resolution helpers for placing the monitor's status file alongside
Shadow's runtime data directory.

Factored out of agents/simulation_monitor.py: the candidate-list search
for shadow.data/hosts is purely a function of the optional output_dir
hint and the current working directory.
"""

from pathlib import Path
from typing import Optional


def find_shadow_data_hosts(output_dir: Optional[Path] = None) -> Optional[Path]:
    """Find the shadow.data/hosts directory.

    Shadow creates shadow.data/ in its working directory (the project
    root), not inside the output directory. Check both locations.

    Args:
        output_dir: Optional Shadow output directory hint. When supplied
            we also probe a few locations relative to it.

    Returns:
        Path to hosts directory, or None if not found.
    """
    # Shadow creates shadow.data in its cwd (project root)
    candidates = [
        Path("shadow.data") / "hosts",           # Relative to cwd (where Shadow runs)
        Path.cwd() / "shadow.data" / "hosts",    # Absolute cwd
    ]

    if output_dir:
        candidates += [
            output_dir / "shadow.data" / "hosts",
            output_dir / "hosts",
            output_dir.parent / "shadow.data" / "hosts",
        ]

    for hosts_dir in candidates:
        if hosts_dir.is_dir():
            return hosts_dir

    return None
