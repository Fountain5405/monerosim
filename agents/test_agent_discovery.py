"""Smoke tests for agents.agent_discovery.

Covers the constructor, registry-file loading semantics (missing/malformed
JSON), TTL caching behavior on get_agent_registry, and a known-good
find_agents_by_type filter pass.
"""
import json

import pytest

from agents.agent_discovery import AgentDiscovery, AgentDiscoveryError


def _write_registry(shared_dir, name, payload):
    """Write *payload* as JSON into shared_dir/<name>.json."""
    path = shared_dir / f"{name}.json"
    path.write_text(json.dumps(payload))
    return path


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

def test_constructor_does_not_raise(shared_dir):
    """Constructor stores shared_state_dir and primes the cache slots."""
    discovery = AgentDiscovery(shared_state_dir=str(shared_dir))
    assert discovery.shared_state_dir == shared_dir
    # All 4 documented cache slots present and unpopulated.
    assert set(discovery._caches.keys()) == {
        "registry", "distribution_recipients", "miner_agents", "public_nodes",
    }
    for entry in discovery._caches.values():
        assert entry["data"] is None
        assert entry["time"] == 0


def test_setup_logger_is_idempotent(shared_dir):
    """Re-constructing AgentDiscovery does not double up log handlers
    (the ``if not logger.handlers:`` guard in _setup_logger holds)."""
    d1 = AgentDiscovery(shared_state_dir=str(shared_dir))
    handlers_after_first = len(d1.logger.handlers)
    AgentDiscovery(shared_state_dir=str(shared_dir))
    # Second instance shares the same module-level logger ("AgentDiscovery").
    assert len(d1.logger.handlers) == handlers_after_first


# ---------------------------------------------------------------------------
# Missing / malformed registry files
# ---------------------------------------------------------------------------

def test_get_agent_registry_with_no_files_returns_empty_skeleton(shared_dir):
    """An empty shared dir yields a registry skeleton with no agents."""
    discovery = AgentDiscovery(shared_state_dir=str(shared_dir))
    registry = discovery.get_agent_registry()
    assert registry["agents"] == {}
    assert registry["miners"] == {}
    assert registry["wallets"] == {}
    assert registry["block_controllers"] == {}


def test_get_agent_registry_skips_malformed_json(shared_dir):
    """A registry file with invalid JSON is logged-and-skipped, not raised."""
    # Garbage in a non-special filename; categorization branch will short-
    # circuit on the AgentDiscoveryError raised by _load_registry_file.
    (shared_dir / "broken.json").write_text("{not valid json")
    discovery = AgentDiscovery(shared_state_dir=str(shared_dir))
    # Must not raise; broken file is caught and skipped.
    registry = discovery.get_agent_registry()
    assert "broken" not in registry  # the bad file didn't end up in the registry


# ---------------------------------------------------------------------------
# TTL caching for get_agent_registry
# ---------------------------------------------------------------------------

def test_registry_cache_returns_stale_within_ttl(shared_dir, mocker):
    """Within the TTL, modifying the underlying file does NOT re-read."""
    _write_registry(shared_dir, "agent_registry",
                    {"agents": [{"id": "a1", "type": "miner"}]})
    # Pin time.time() at t=1000 for the first read; the cache TTL for
    # 'registry' is 5 seconds.
    mocker.patch("agents.agent_discovery.time.time", return_value=1000.0)

    discovery = AgentDiscovery(shared_state_dir=str(shared_dir))
    first = discovery.get_agent_registry()
    assert len(first["agents"]) == 1

    # Mutate the file on disk and read again at t=1003 (still within TTL=5s).
    _write_registry(shared_dir, "agent_registry",
                    {"agents": [{"id": "a1"}, {"id": "a2"}]})
    mocker.patch("agents.agent_discovery.time.time", return_value=1003.0)

    second = discovery.get_agent_registry()
    # Cached value is unchanged.
    assert second is first
    assert len(second["agents"]) == 1


def test_registry_cache_refreshes_after_ttl(shared_dir, mocker):
    """Bumping time past the TTL forces a re-read from disk."""
    _write_registry(shared_dir, "agent_registry",
                    {"agents": [{"id": "a1", "type": "miner"}]})
    mock_time = mocker.patch("agents.agent_discovery.time.time",
                             return_value=2000.0)

    discovery = AgentDiscovery(shared_state_dir=str(shared_dir))
    discovery.get_agent_registry()  # populate cache

    # Mutate the file and jump past the 5s TTL.
    _write_registry(shared_dir, "agent_registry",
                    {"agents": [{"id": "a1"}, {"id": "a2"}, {"id": "a3"}]})
    mock_time.return_value = 2010.0

    refreshed = discovery.get_agent_registry()
    assert len(refreshed["agents"]) == 3


def test_force_refresh_bypasses_cache(shared_dir):
    """force_refresh=True bypasses the cache check entirely."""
    _write_registry(shared_dir, "agent_registry", {"agents": [{"id": "a1"}]})
    discovery = AgentDiscovery(shared_state_dir=str(shared_dir))
    discovery.get_agent_registry()

    _write_registry(shared_dir, "agent_registry",
                    {"agents": [{"id": "a1"}, {"id": "a2"}]})
    refreshed = discovery.get_agent_registry(force_refresh=True)
    assert len(refreshed["agents"]) == 2


# ---------------------------------------------------------------------------
# Filtered queries
# ---------------------------------------------------------------------------

def test_find_agents_by_type_returns_matches_only(shared_dir):
    """find_agents_by_type returns only agents whose ``type`` matches."""
    _write_registry(shared_dir, "agent_registry", {"agents": [
        {"id": "m1", "type": "miner"},
        {"id": "u1", "type": "user"},
        {"id": "m2", "type": "miner"},
    ]})
    discovery = AgentDiscovery(shared_state_dir=str(shared_dir))
    miners = discovery.find_agents_by_type("miner")
    assert {a["id"] for a in miners} == {"m1", "m2"}
    users = discovery.find_agents_by_type("user")
    assert [a["id"] for a in users] == ["u1"]


# ---------------------------------------------------------------------------
# get_public_nodes file-shape contract
# ---------------------------------------------------------------------------

def test_get_public_nodes_missing_file_returns_empty(shared_dir):
    """When public_nodes.json is absent, get_public_nodes returns []."""
    discovery = AgentDiscovery(shared_state_dir=str(shared_dir))
    assert discovery.get_public_nodes() == []


def test_get_public_nodes_filters_by_status(shared_dir):
    """status_filter (default 'available') excludes offline nodes."""
    (shared_dir / "public_nodes.json").write_text(json.dumps({
        "nodes": [
            {"agent_id": "n1", "ip_addr": "10.0.0.1", "rpc_port": 18081,
             "status": "available"},
            {"agent_id": "n2", "ip_addr": "10.0.0.2", "rpc_port": 18081,
             "status": "offline"},
        ],
    }))
    discovery = AgentDiscovery(shared_state_dir=str(shared_dir))
    available = discovery.get_public_nodes()  # default = "available"
    assert [n["agent_id"] for n in available] == ["n1"]
    # status_filter=None returns all nodes regardless of status.
    all_nodes = discovery.get_public_nodes(status_filter=None)
    assert {n["agent_id"] for n in all_nodes} == {"n1", "n2"}
