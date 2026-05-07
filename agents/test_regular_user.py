"""Smoke tests for agents.regular_user.

Exercises the constructor and the transaction-parameter parser without
touching wallet/daemon RPC. The activity_start_time helper does
SHADOW_EPOCH arithmetic; we cover the past-epoch and future-epoch branches
plus the zero-disabled branch.
"""
import time

import pytest

from agents.base_agent import SHADOW_EPOCH
from agents.regular_user import RegularUserAgent


def test_constructor_does_not_raise(shared_dir):
    """A regular user constructs cleanly with empty attributes."""
    agent = RegularUserAgent(
        agent_id="user-01",
        shared_dir=shared_dir,
        tx_frequency=60,
        attributes=[],
    )
    assert agent.agent_id == "user-01"
    assert agent.is_miner is False
    # Deterministic seeding wired up.
    assert isinstance(agent.agent_seed, int)


def test_setup_transaction_parameters_reads_attributes(shared_dir):
    """_setup_transaction_parameters pulls min/max amounts and interval
    from agent attributes and exposes them as instance fields."""
    attrs = [
        ["min_transaction_amount", "0.5"],
        ["max_transaction_amount", "2.5"],
        ["transaction_interval", "120"],
        ["tx_send_probability", "0.5"],
    ]
    agent = RegularUserAgent(
        agent_id="user-02",
        shared_dir=shared_dir,
        attributes=attrs,
    )
    agent._setup_transaction_parameters()

    assert agent.min_tx_amount == pytest.approx(0.5)
    assert agent.max_tx_amount == pytest.approx(2.5)
    assert agent.tx_interval == 120
    assert agent.tx_send_probability == pytest.approx(0.5)
    # No activity_start_time means the agent is ready to transact.
    assert agent.waiting_for_activity_start is False
    assert agent.activity_start_time == 0


def test_setup_transaction_parameters_uses_defaults(shared_dir):
    """When attributes are missing the parser falls back to documented
    defaults (0.1 / 1.0 XMR, 60s interval, 0.75 send probability)."""
    agent = RegularUserAgent(
        agent_id="user-03",
        shared_dir=shared_dir,
        attributes=[],
    )
    agent._setup_transaction_parameters()
    assert agent.min_tx_amount == pytest.approx(0.1)
    assert agent.max_tx_amount == pytest.approx(1.0)
    assert agent.tx_interval == 60
    assert agent.tx_send_probability == pytest.approx(0.75)


def test_activity_start_time_in_future_sets_waiting_flag(shared_dir, mocker):
    """A future activity_start_time (sim seconds) sets waiting_for_activity_start."""
    # Pin time.time() to just-after SHADOW_EPOCH so a 3600s start is in the future.
    mocker.patch(
        "agents.regular_user.time.time",
        return_value=SHADOW_EPOCH + 100.0,
    )
    agent = RegularUserAgent(
        agent_id="user-04",
        shared_dir=shared_dir,
        attributes=[["activity_start_time", "3600"]],
    )
    agent._setup_transaction_parameters()
    # activity_start_time is recorded as the unix timestamp (SHADOW_EPOCH + 3600).
    assert agent.activity_start_time == SHADOW_EPOCH + 3600
    assert agent.waiting_for_activity_start is True


def test_activity_start_time_in_past_does_not_wait(shared_dir, mocker):
    """If sim time has already passed the activity_start_time, no wait."""
    # Pin time.time() well past the configured 60s start.
    mocker.patch(
        "agents.regular_user.time.time",
        return_value=SHADOW_EPOCH + 7200.0,
    )
    agent = RegularUserAgent(
        agent_id="user-05",
        shared_dir=shared_dir,
        attributes=[["activity_start_time", "60"]],
    )
    agent._setup_transaction_parameters()
    assert agent.waiting_for_activity_start is False
