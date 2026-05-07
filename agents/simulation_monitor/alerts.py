"""
Alert evaluation and rendering for SimulationMonitorAgent.

Both helpers are pure functions of the inputs — they don't read or mutate
any agent state. They are factored out of agents/simulation_monitor.py so
the alert thresholds and the on-disk format live in one place.
"""

from typing import Any, Dict, List


def check_alerts(network_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check for alert conditions in the network metrics.

    Args:
        network_metrics: Dictionary containing network health metrics

    Returns:
        List of alert dictionaries
    """
    alerts = []

    # Check synchronization issues
    if network_metrics['sync_percentage'] < 90:
        alerts.append({
            "type": "sync_issue",
            "severity": "warning",
            "message": f"Low synchronization rate: {network_metrics['sync_percentage']:.1f}%"
        })

    # Check height variance
    if network_metrics['height_variance'] > 10:
        alerts.append({
            "type": "height_variance",
            "severity": "warning",
            "message": f"High height variance: {network_metrics['height_variance']:.2f}"
        })

    # Check for no miners - use registered_miners count
    registered_miners = network_metrics.get('registered_miners', 0)
    active_miners = network_metrics.get('active_miners', 0)
    if registered_miners == 0 and active_miners == 0:
        alerts.append({
            "type": "no_miners",
            "severity": "critical",
            "message": "No miners registered or detected"
        })

    # Check for large transaction pool
    if network_metrics['total_pool_size'] > 50:
        alerts.append({
            "type": "large_pool",
            "severity": "warning",
            "message": f"Large transaction pool: {network_metrics['total_pool_size']} transactions"
        })

    # Check for errors
    if network_metrics['errors']:
        alerts.append({
            "type": "node_errors",
            "severity": "warning",
            "message": f"{len(network_metrics['errors'])} nodes reporting errors"
        })

    return alerts


def write_alerts(f, alerts: List[Dict[str, Any]]):
    """Write alerts to the status file."""
    f.write("ALERTS:\n")
    for alert in alerts:
        severity_symbol = "⚠️" if alert["severity"] == "warning" else "🚨"
        f.write(f"{severity_symbol} {alert['message']}\n")
    f.write("\n")
