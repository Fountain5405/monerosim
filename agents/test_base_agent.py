"""Smoke tests for agents.base_agent helpers.

Covers the static/utility helpers that don't require live RPC: parse_bool,
retry_with_backoff, and write/read_shared_state round-trip.
"""
import pytest

from agents.base_agent import BaseAgent, retry_with_backoff


# ---------------------------------------------------------------------------
# parse_bool: pure data table test
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [
    # bool passthrough
    (True, True),
    (False, False),
    # numeric coercion
    (1, True),
    (0, False),
    (1.5, True),
    (0.0, False),
    # canonical truthy strings (case-insensitive)
    ("true", True),
    ("True", True),
    ("TRUE", True),
    ("1", True),
    ("yes", True),
    ("on", True),
    # canonical falsy strings
    ("false", False),
    ("False", False),
    ("0", False),
    ("no", False),
    ("off", False),
    # unrecognized -> default
    ("maybe", False),
    ("", False),
    (None, False),
    ([], False),
])
def test_parse_bool_table(value, expected):
    assert BaseAgent.parse_bool(value) is expected


def test_parse_bool_default_is_respected_for_unknown():
    # default=True should win when the string is unrecognized.
    assert BaseAgent.parse_bool("garbage", default=True) is True
    assert BaseAgent.parse_bool(None, default=True) is True


# ---------------------------------------------------------------------------
# retry_with_backoff: retries N times then re-raises the last exception
# ---------------------------------------------------------------------------

def test_retry_with_backoff_returns_on_success_first_try(mocker):
    sleep = mocker.patch("agents.base_agent.time.sleep")
    fn = mocker.Mock(return_value="ok")
    assert retry_with_backoff(fn, max_retries=3) == "ok"
    assert fn.call_count == 1
    sleep.assert_not_called()


def test_retry_with_backoff_retries_then_succeeds(mocker):
    sleep = mocker.patch("agents.base_agent.time.sleep")
    # Fail twice, succeed on third call.
    fn = mocker.Mock(side_effect=[RuntimeError("a"), RuntimeError("b"), "ok"])
    assert retry_with_backoff(fn, max_retries=3, initial_delay=1.0,
                              backoff_factor=2.0) == "ok"
    assert fn.call_count == 3
    # Two sleeps between three attempts: 1.0s then 2.0s (backoff).
    assert sleep.call_args_list == [mocker.call(1.0), mocker.call(2.0)]


def test_retry_with_backoff_reraises_after_max_retries(mocker):
    mocker.patch("agents.base_agent.time.sleep")
    fn = mocker.Mock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
        retry_with_backoff(fn, max_retries=3)
    # Wrapped function was tried exactly max_retries times.
    assert fn.call_count == 3


# ---------------------------------------------------------------------------
# write_shared_state / read_shared_state: round-trip via tmp_path
# ---------------------------------------------------------------------------

class _MinimalAgent(BaseAgent):
    """Bare-bones concrete subclass for exercising shared-state helpers
    without going through setup() (which would touch RPC and disk)."""

    def _setup_agent(self):  # pragma: no cover - never invoked here
        pass

    def run_iteration(self):  # pragma: no cover - never invoked here
        return 1.0


def test_shared_state_round_trip(shared_dir):
    agent = _MinimalAgent(agent_id="t1", shared_dir=shared_dir)
    payload = {"hello": "world", "count": 3, "items": [1, 2, 3]}

    agent.write_shared_state("test_state.json", payload)
    assert (shared_dir / "test_state.json").exists()

    loaded = agent.read_shared_state("test_state.json")
    assert loaded == payload


def test_shared_state_read_missing_returns_none(shared_dir):
    agent = _MinimalAgent(agent_id="t2", shared_dir=shared_dir)
    assert agent.read_shared_state("does_not_exist.json") is None
