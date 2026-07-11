"""Smoke tests for agents.simulation_monitor.

The constructor instantiates AgentDiscovery (touches disk via mkdir) and
records initial transaction-tracking state. We patch AgentDiscovery to a
no-op for hermetic isolation, then exercise the constructor's expected
shape and the status-file initializer.
"""
import os

import pytest

from agents.simulation_monitor import SimulationMonitorAgent


@pytest.fixture(autouse=True)
def _stub_agent_discovery(mocker):
    """Replace AgentDiscovery's __init__ with a no-op so it doesn't touch
    disk. The monitor stores the discovery instance as ``self.discovery``
    and only uses it during run_iteration (which we don't call here)."""
    mocker.patch(
        "agents.simulation_monitor.AgentDiscovery.__init__",
        return_value=None,
    )


def test_constructor_does_not_raise(shared_dir):
    """Monitor agent constructs cleanly with the typical kwargs."""
    agent = SimulationMonitorAgent(
        agent_id="simulation-monitor",
        shared_dir=shared_dir,
        poll_interval=60,
        attributes=[],
    )
    assert agent.agent_id == "simulation-monitor"
    assert agent.poll_interval == 60
    assert agent.cycle_count == 0
    assert agent.max_historical_entries == 1000


def test_transaction_stats_initial_shape(shared_dir):
    """The per-iteration tracking dict has all the expected keys at startup."""
    agent = SimulationMonitorAgent(
        agent_id="simulation-monitor",
        shared_dir=shared_dir,
        attributes=[],
    )
    stats = agent.transaction_stats
    # Counters
    assert stats["total_created"] == 0
    assert stats["total_in_blocks"] == 0
    assert stats["total_broadcast"] == 0
    assert stats["blocks_mined"] == 0
    assert stats["last_block_height"] == 0
    assert stats["last_processed_height"] == 0
    # Containers
    assert isinstance(stats["unique_tx_hashes"], set)
    assert isinstance(stats["pending_txs"], set)
    assert isinstance(stats["included_txs"], set)
    assert isinstance(stats["nodes_with_balance"], dict)
    assert isinstance(stats["tx_created_by_node"], dict)
    assert isinstance(stats["tx_to_block_mapping"], dict)


def test_initialize_status_file_writes_header(shared_dir):
    """_initialize_status_file creates the file and writes the expected header."""
    status_path = shared_dir / "monitor.log"
    agent = SimulationMonitorAgent(
        agent_id="simulation-monitor",
        shared_dir=shared_dir,
        poll_interval=60,
        status_file=str(status_path),
        attributes=[],
    )
    agent._initialize_status_file()

    assert status_path.exists()
    contents = status_path.read_text()
    assert "MoneroSim Simulation Monitor" in contents
    assert "Poll Interval: 60 seconds" in contents


def test_constructor_records_status_file_path(shared_dir):
    """The constructor stores the status_file path verbatim for later use."""
    agent = SimulationMonitorAgent(
        agent_id="simulation-monitor",
        shared_dir=shared_dir,
        status_file="/tmp/custom-monitor.log",
        attributes=[],
    )
    assert agent.status_file == "/tmp/custom-monitor.log"


def test_transaction_status_pool_delta_reads_nested_key(shared_dir):
    """Pin the bug-A key path: the pool delta must read total_pool_size from
    each historical entry's nested ``network_metrics`` block, not the entry
    top level (which never carries it, so curr_pool was always 0)."""
    from io import StringIO

    agent = SimulationMonitorAgent(
        agent_id="simulation-monitor",
        shared_dir=shared_dir,
        attributes=[],
    )
    # Two prior cycles: pool drained from 10 -> 3, i.e. 7 processed. The value
    # lives under "network_metrics" exactly as _store_historical_data writes it.
    agent.historical_data = [
        {"network_metrics": {"total_pool_size": 10}},
        {"network_metrics": {"total_pool_size": 3}},
    ]
    network_metrics = {
        "total_pool_size": 3,
        "total_balance": 0,
        "total_unlocked_balance": 0,
    }
    buf = StringIO()
    agent._write_transaction_status(buf, network_metrics)
    out = buf.getvalue()
    # With the bug (top-level lookup -> curr_pool=0) this line read "10".
    assert "Transactions Processed: 7" in out
