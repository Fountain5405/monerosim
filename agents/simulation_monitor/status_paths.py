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
    """Find the shadow.data/hosts directory for this run (output-dir-relative first, cwd last).

    Shadow creates shadow.data/ in its working directory (the project
    root), not inside the output directory. Check both locations.

    Args:
        output_dir: Optional Shadow output directory hint. When supplied
            we also probe a few locations relative to it.

    Returns:
        Path to hosts directory, or None if not found.
    """
    # Since 2026-09 run_sim.sh points Shadow's -d at <run_dir>/shadow.data,
    # next to the generator's <run_dir>/shadow_output (our output_dir), so
    # the output-relative candidates come first. The cwd-relative ones are
    # a last resort for hand-run Shadow invocations: with several runs per
    # checkout a stale <checkout>/shadow.data must never win.
    candidates = []
    if output_dir:
        candidates += [
            output_dir / "shadow.data" / "hosts",
            output_dir / "hosts",
            output_dir.parent / "shadow.data" / "hosts",
        ]
    candidates += [
        Path("shadow.data") / "hosts",           # Relative to cwd (where Shadow runs)
        Path.cwd() / "shadow.data" / "hosts",    # Absolute cwd
    ]

    for hosts_dir in candidates:
        if hosts_dir.is_dir():
            return hosts_dir

    return None
