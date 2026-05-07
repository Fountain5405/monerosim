"""Shared pytest fixtures for the monerosim test suite.

This conftest.py is collected from the project root (see pyproject.toml's
testpaths) so the fixtures defined here are visible to tests in agents/,
scripts/, and tests/.
"""
import pytest


@pytest.fixture
def shared_dir(tmp_path):
    """Per-test shared dir; replaces /tmp/monerosim_shared for BaseAgent."""
    d = tmp_path / "shared"
    d.mkdir()
    return d


@pytest.fixture
def stub_rpc(mocker):
    """Patch BaseRPC._make_request with a configurable mock.

    Returning the mock so individual tests can configure return_value /
    side_effect as needed.
    """
    return mocker.patch("agents.monero_rpc.BaseRPC._make_request")


@pytest.fixture(autouse=True)
def _no_signal_install(mocker):
    """BaseAgent installs SIGTERM/SIGINT handlers in __init__; neutralize
    them in tests so they don't pollute the test process.
    """
    mocker.patch("signal.signal")
