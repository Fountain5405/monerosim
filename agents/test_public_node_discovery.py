"""Smoke tests for agents.public_node_discovery.

Covers the constructor, missing/present registry handling, daemon-selection
strategies (random/first/round_robin), and the parse_selection_strategy
helper. We exercise `select_daemon` directly.
"""
import json

import pytest

from agents.public_node_discovery import (
    DaemonSelectionStrategy,
    PublicNodeDiscovery,
    parse_selection_strategy,
)


def _write_public_nodes(shared_dir, nodes):
    """Write a public_nodes.json registry with *nodes* as the nodes list."""
    (shared_dir / "public_nodes.json").write_text(
        json.dumps({"nodes": nodes, "version": 1})
    )


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

def test_constructor_does_not_raise(shared_dir):
    """Constructor stores shared_dir and primes the round-robin counter."""
    discovery = PublicNodeDiscovery(shared_dir=shared_dir)
    assert discovery.shared_dir == shared_dir
    assert discovery._round_robin_index == 0
    assert discovery._cache is None


# ---------------------------------------------------------------------------
# get_public_nodes file-shape contract
# ---------------------------------------------------------------------------

def test_get_public_nodes_missing_file_returns_empty(shared_dir):
    """Missing public_nodes.json returns [] (not None) per the docstring."""
    discovery = PublicNodeDiscovery(shared_dir=shared_dir)
    assert discovery.get_public_nodes() == []


def test_get_public_nodes_filters_to_available(shared_dir):
    """get_public_nodes filters out nodes whose status != 'available'."""
    _write_public_nodes(shared_dir, [
        {"agent_id": "n1", "ip_addr": "10.0.0.1", "rpc_port": 18081,
         "status": "available"},
        {"agent_id": "n2", "ip_addr": "10.0.0.2", "rpc_port": 18081,
         "status": "offline"},
        {"agent_id": "n3", "ip_addr": "10.0.0.3", "rpc_port": 18081,
         "status": "available"},
    ])
    discovery = PublicNodeDiscovery(shared_dir=shared_dir)
    available = discovery.get_public_nodes()
    assert {n["agent_id"] for n in available} == {"n1", "n3"}


def test_get_public_nodes_returns_empty_on_malformed_json(shared_dir):
    """Malformed JSON: log error, return [] (no exception bubbles up)."""
    (shared_dir / "public_nodes.json").write_text("{garbage")
    discovery = PublicNodeDiscovery(shared_dir=shared_dir)
    assert discovery.get_public_nodes() == []


# ---------------------------------------------------------------------------
# TTL cache
# ---------------------------------------------------------------------------

def test_get_public_nodes_caches_within_ttl(shared_dir, mocker):
    """A second call within TTL returns the cached list, not a re-read."""
    _write_public_nodes(shared_dir, [
        {"agent_id": "n1", "ip_addr": "10.0.0.1", "rpc_port": 18081,
         "status": "available"},
    ])
    mock_time = mocker.patch("agents.public_node_discovery.time.time",
                             return_value=500.0)
    discovery = PublicNodeDiscovery(shared_dir=shared_dir)
    first = discovery.get_public_nodes()
    assert len(first) == 1

    # Mutate the file; advance time only by 2s (TTL is 5s).
    _write_public_nodes(shared_dir, [
        {"agent_id": "n1", "ip_addr": "10.0.0.1", "rpc_port": 18081,
         "status": "available"},
        {"agent_id": "n2", "ip_addr": "10.0.0.2", "rpc_port": 18081,
         "status": "available"},
    ])
    mock_time.return_value = 502.0

    second = discovery.get_public_nodes()
    # Cached list returned unchanged.
    assert second is first
    assert len(second) == 1


def test_invalidate_cache_forces_refresh(shared_dir):
    """invalidate_cache() makes the next call re-read disk."""
    _write_public_nodes(shared_dir, [
        {"agent_id": "n1", "ip_addr": "10.0.0.1", "rpc_port": 18081,
         "status": "available"},
    ])
    discovery = PublicNodeDiscovery(shared_dir=shared_dir)
    discovery.get_public_nodes()  # populate cache

    _write_public_nodes(shared_dir, [
        {"agent_id": "n1", "ip_addr": "10.0.0.1", "rpc_port": 18081,
         "status": "available"},
        {"agent_id": "n2", "ip_addr": "10.0.0.2", "rpc_port": 18081,
         "status": "available"},
    ])
    discovery.invalidate_cache()
    refreshed = discovery.get_public_nodes()
    assert len(refreshed) == 2


# ---------------------------------------------------------------------------
# Selection strategies
# ---------------------------------------------------------------------------

def test_select_daemon_first_strategy(shared_dir):
    """FIRST strategy always returns the first node in the list."""
    _write_public_nodes(shared_dir, [
        {"agent_id": "n1", "ip_addr": "10.0.0.1", "rpc_port": 18081,
         "status": "available"},
        {"agent_id": "n2", "ip_addr": "10.0.0.2", "rpc_port": 18082,
         "status": "available"},
    ])
    discovery = PublicNodeDiscovery(shared_dir=shared_dir)
    addr = discovery.select_daemon(DaemonSelectionStrategy.FIRST)
    assert addr == "10.0.0.1:18081"
    # Repeated calls keep returning the first node.
    assert discovery.select_daemon(DaemonSelectionStrategy.FIRST) == "10.0.0.1:18081"


def test_select_daemon_round_robin_rotates(shared_dir):
    """ROUND_ROBIN cycles through nodes deterministically."""
    _write_public_nodes(shared_dir, [
        {"agent_id": "n1", "ip_addr": "10.0.0.1", "rpc_port": 18081,
         "status": "available"},
        {"agent_id": "n2", "ip_addr": "10.0.0.2", "rpc_port": 18081,
         "status": "available"},
        {"agent_id": "n3", "ip_addr": "10.0.0.3", "rpc_port": 18081,
         "status": "available"},
    ])
    discovery = PublicNodeDiscovery(shared_dir=shared_dir)
    picks = [discovery.select_daemon(DaemonSelectionStrategy.ROUND_ROBIN)
             for _ in range(7)]
    # 7 picks across 3 nodes wrap exactly: idx 0,1,2,0,1,2,0.
    assert picks == [
        "10.0.0.1:18081", "10.0.0.2:18081", "10.0.0.3:18081",
        "10.0.0.1:18081", "10.0.0.2:18081", "10.0.0.3:18081",
        "10.0.0.1:18081",
    ]


def test_select_daemon_returns_none_when_no_nodes(shared_dir):
    """No available nodes: select_daemon returns None, not a raise."""
    discovery = PublicNodeDiscovery(shared_dir=shared_dir)
    assert discovery.select_daemon(DaemonSelectionStrategy.FIRST) is None


def test_select_daemon_excludes_caller(shared_dir):
    """exclude_ids removes the caller's own node from the candidate pool."""
    _write_public_nodes(shared_dir, [
        {"agent_id": "n1", "ip_addr": "10.0.0.1", "rpc_port": 18081,
         "status": "available"},
        {"agent_id": "n2", "ip_addr": "10.0.0.2", "rpc_port": 18081,
         "status": "available"},
    ])
    discovery = PublicNodeDiscovery(shared_dir=shared_dir)
    addr = discovery.select_daemon(
        DaemonSelectionStrategy.FIRST, exclude_ids=["n1"])
    assert addr == "10.0.0.2:18081"


# ---------------------------------------------------------------------------
# parse_selection_strategy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("input_str, expected", [
    ("random", DaemonSelectionStrategy.RANDOM),
    ("RANDOM", DaemonSelectionStrategy.RANDOM),
    ("first", DaemonSelectionStrategy.FIRST),
    ("round_robin", DaemonSelectionStrategy.ROUND_ROBIN),
])
def test_parse_selection_strategy_known_values(input_str, expected):
    assert parse_selection_strategy(input_str) is expected


def test_parse_selection_strategy_none_defaults_to_random():
    """None / "" / unknown all default to RANDOM."""
    assert parse_selection_strategy(None) is DaemonSelectionStrategy.RANDOM
    assert parse_selection_strategy("") is DaemonSelectionStrategy.RANDOM
    assert parse_selection_strategy("balance") is DaemonSelectionStrategy.RANDOM
