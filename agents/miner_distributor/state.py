"""
Persisted state schema for MinerDistributorAgent.

The actual JSON read/write goes through BaseAgent.read_shared_state /
write_shared_state, so the file-format helpers live as methods on the
agent class. This module documents the shape and the file name so the
schema is in one place.
"""

from typing import Any, Dict


# File name in the shared dir used to persist initial-funding progress
# across MD restarts. Schema:
#   - funded_recipients (list[str]): IDs of agents successfully funded
#   - failed_recipients (list[str]): IDs of agents that failed transiently
#   - permanently_failed (list[str]): IDs of agents marked as permanently
#     broken after exceeding _PERMANENT_FAILURE_THRESHOLD address-lookup
#     failures
#   - completed (bool): whether the initial-funding phase is finished
#   - last_updated (float | None): unix time of the most recent update
FUNDING_STATUS_FILE = "initial_funding_status.json"


def empty_funding_status() -> Dict[str, Any]:
    """Return the default funding-status dict used when no file exists."""
    return {
        "funded_recipients": [],
        "failed_recipients": [],
        "permanently_failed": [],
        "completed": False,
        "last_updated": None,
    }
