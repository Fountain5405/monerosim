"""Smoke tests for agents.miner_distributor.

Covers the constructor, _parse_configuration's type dispatch (int_min,
int_range, float_min, choice, time_duration), and the _parse_time_duration
helper. We don't drive the run loop or touch any RPC.
"""
import pytest

from agents.miner_distributor import MinerDistributorAgent


def test_constructor_does_not_raise(shared_dir):
    """Constructor sets sensible defaults without parsing user attributes."""
    agent = MinerDistributorAgent(
        agent_id="miner-distributor",
        shared_dir=shared_dir,
        attributes=[],
    )
    # Documented defaults from miner_distributor.py
    assert agent.min_transaction_amount == pytest.approx(0.1)
    assert agent.max_transaction_amount == pytest.approx(1.0)
    assert agent.miner_selection_strategy == "weighted"
    assert agent.transaction_priority == 1
    assert agent.max_retries == 5
    assert agent.recipient_selection == "random"
    assert agent.md_n_recipients == 8
    assert agent.md_out_per_tx == 2
    assert agent.md_output_amount == pytest.approx(5.0)


def test_parse_configuration_handles_all_types(shared_dir):
    """_parse_configuration correctly applies the int_min/int_range/float_min/
    choice/time_duration mappers from its config_mappings table."""
    attrs = [
        ["min_transaction_amount", "0.05"],          # float
        ["max_transaction_amount", "10.0"],          # float
        ["miner_selection_strategy", "balance"],     # choice
        ["transaction_priority", "2"],               # int_range (0..3)
        ["max_retries", "7"],                        # int_min (>=1)
        ["recipient_selection", "round_robin"],      # choice
        ["balance_check_interval", "15"],            # int_min
        ["max_wait_time", "1h"],                     # time_duration
        ["md_n_recipients", "4"],                    # int_min
        ["md_out_per_tx", "3"],                      # int_min
        ["md_output_amount", "2.5"],                 # float_min
        ["md_funding_cycle_interval", "30m"],        # time_duration
    ]
    agent = MinerDistributorAgent(
        agent_id="miner-distributor",
        shared_dir=shared_dir,
        attributes=attrs,
    )
    agent._parse_configuration()

    assert agent.min_transaction_amount == pytest.approx(0.05)
    assert agent.max_transaction_amount == pytest.approx(10.0)
    assert agent.miner_selection_strategy == "balance"
    assert agent.transaction_priority == 2
    assert agent.max_retries == 7
    assert agent.recipient_selection == "round_robin"
    assert agent.balance_check_interval == 15
    assert agent.max_wait_time == 3600  # 1h in seconds
    assert agent.md_n_recipients == 4
    assert agent.md_out_per_tx == 3
    assert agent.md_output_amount == pytest.approx(2.5)
    assert agent.md_funding_cycle_interval == 1800  # 30m


def test_parse_configuration_invalid_choice_keeps_default(shared_dir):
    """An out-of-list choice value warns and leaves the default in place."""
    agent = MinerDistributorAgent(
        agent_id="miner-distributor",
        shared_dir=shared_dir,
        attributes=[["miner_selection_strategy", "garbage"]],
    )
    agent._parse_configuration()
    assert agent.miner_selection_strategy == "weighted"  # default


def test_parse_time_duration_supported_units(shared_dir):
    """_parse_time_duration handles 'h', 'm', 's' suffixes and bare numbers."""
    agent = MinerDistributorAgent(
        agent_id="miner-distributor",
        shared_dir=shared_dir,
        attributes=[],
    )
    assert agent._parse_time_duration("1h") == 3600
    assert agent._parse_time_duration("30m") == 1800
    assert agent._parse_time_duration("3600s") == 3600
    assert agent._parse_time_duration("250") == 250  # bare number string
    assert agent._parse_time_duration(125) == 125    # already an int
    assert agent._parse_time_duration(1.5) == 1      # float -> int(1.5) == 1


def test_parse_time_duration_invalid_returns_none(shared_dir):
    """Garbage strings return None instead of raising (caller falls back)."""
    agent = MinerDistributorAgent(
        agent_id="miner-distributor",
        shared_dir=shared_dir,
        attributes=[],
    )
    assert agent._parse_time_duration("abc") is None
    assert agent._parse_time_duration("12x") is None
