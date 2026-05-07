"""Smoke tests for agents.autonomous_miner.

We don't drive the run loop (no daemon, no wallet, no Shadow). We exercise
the constructor and the pure helpers: hashrate parsing and the deterministic
seed derivation in shared_utils.make_deterministic_seed.
"""
import pytest

from agents.autonomous_miner import AutonomousMinerAgent
from agents.shared_utils import make_deterministic_seed


def test_constructor_with_valid_kwargs_does_not_raise(shared_dir):
    """Constructor sets up logging, attribute parsing and seed without RPC."""
    agent = AutonomousMinerAgent(
        agent_id="miner-001",
        shared_dir=shared_dir,
        attributes=[["hashrate", "20"], ["is_miner", "true"]],
    )
    # The constructor parses attributes_list -> dict and sets is_miner.
    assert agent.attributes["hashrate"] == "20"
    assert agent.is_miner is True
    # Per-agent seed is derived deterministically.
    assert isinstance(agent.agent_seed, int)


def test_parse_mining_config_accepts_valid_attributes(shared_dir):
    """_parse_mining_config converts the 'hashrate' attribute to a float."""
    agent = AutonomousMinerAgent(
        agent_id="miner-002",
        shared_dir=shared_dir,
        attributes=[["hashrate", "33.5"]],
    )
    agent._parse_mining_config()
    assert agent.hashrate_pct == pytest.approx(33.5)


def test_parse_mining_config_rejects_missing_hashrate(shared_dir):
    """Missing hashrate attribute raises ValueError per agent contract."""
    agent = AutonomousMinerAgent(
        agent_id="miner-003",
        shared_dir=shared_dir,
        attributes=[],  # no hashrate
    )
    with pytest.raises(ValueError, match="hashrate"):
        agent._parse_mining_config()


def test_parse_mining_config_rejects_non_numeric_hashrate(shared_dir):
    """Non-numeric hashrate string fails validation."""
    agent = AutonomousMinerAgent(
        agent_id="miner-004",
        shared_dir=shared_dir,
        attributes=[["hashrate", "not-a-number"]],
    )
    with pytest.raises(ValueError, match="Invalid hashrate"):
        agent._parse_mining_config()


def test_parse_mining_config_rejects_non_positive(shared_dir):
    """Hashrate <= 0 is rejected (would yield infinite/negative block times)."""
    agent = AutonomousMinerAgent(
        agent_id="miner-005",
        shared_dir=shared_dir,
        attributes=[["hashrate", "0"]],
    )
    with pytest.raises(ValueError, match="must be positive"):
        agent._parse_mining_config()


def test_make_deterministic_seed_is_deterministic_per_id(monkeypatch):
    """Same agent_id and SIMULATION_SEED -> same seed across invocations."""
    monkeypatch.setenv("SIMULATION_SEED", "42")
    a = make_deterministic_seed("miner-007")
    b = make_deterministic_seed("miner-007")
    assert a == b
    # Different agent_ids must yield different seeds.
    c = make_deterministic_seed("miner-008")
    assert c != a
