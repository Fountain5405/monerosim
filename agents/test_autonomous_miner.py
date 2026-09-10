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


import re


class _FakeDaemonRPC:
    """Scripted daemon RPC: start_mining answers from a queue, mining_status
    from a list, get_info is static."""

    def __init__(self, start_answers, status_answers, height=10, difficulty=1200):
        self.start_answers = list(start_answers)
        self.status_answers = list(status_answers)
        self.calls = []
        self._info = {"height": height, "difficulty": difficulty}

    def start_mining(self, wallet_address, threads=1):
        self.calls.append(("start_mining", wallet_address, threads))
        answer = self.start_answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def stop_mining(self):
        self.calls.append(("stop_mining",))
        return {"status": "OK"}

    def mining_status(self):
        self.calls.append(("mining_status",))
        return self.status_answers.pop(0)

    def get_info(self):
        return dict(self._info)


def _native_agent(shared_dir, tmp_path, rpc):
    log = tmp_path / "bitmonero.log"
    log.write_text("")
    agent = AutonomousMinerAgent(
        agent_id="miner-001",
        shared_dir=shared_dir,
        attributes=[["hashrate", "20"], ["is_miner", "true"],
                    ["mining_mode", "native"], ["hash_interval_ms", "50"],
                    ["daemon_log_path", str(log)]],
    )
    agent.daemon_rpc = rpc
    agent.wallet_address = "4AE8E3bcVm2hfdErzPbA3cNRvymbAfGWYXZX5oFk2dgwEi4BPKSJEZw237bRPPBdH2C5cSiTThV389ESmN3q3DSJ9zAgkc8"
    agent.mining_active = True
    return agent, log


def test_native_mode_is_detected_from_attributes(shared_dir, tmp_path):
    agent, _ = _native_agent(shared_dir, tmp_path, _FakeDaemonRPC([], []))
    assert agent.native_mode is True
    assert agent.hash_interval_ms == 50


def test_native_start_retries_while_busy_then_starts(shared_dir, tmp_path):
    from agents.monero_rpc import RPCError
    rpc = _FakeDaemonRPC(
        start_answers=[{"status": "BUSY"}, RPCError("Core is busy"), {"status": "OK"}],
        status_answers=[{"active": True, "speed": 20}],
    )
    agent, _ = _native_agent(shared_dir, tmp_path, rpc)
    assert agent._native_run_iteration() == 5.0      # BUSY -> retry soon
    assert agent._native_run_iteration() == 5.0      # RPCError -> retry soon
    assert agent.native_started is False
    assert agent._native_run_iteration() == agent.native_poll_interval   # OK -> started
    assert agent.native_started is True
    assert [c[0] for c in rpc.calls].count("start_mining") == 3
    assert rpc.calls[0][2] == 1                       # threads=1


def test_native_restarts_when_status_reports_inactive(shared_dir, tmp_path):
    rpc = _FakeDaemonRPC(
        start_answers=[{"status": "OK"}, {"status": "OK"}],
        status_answers=[{"active": True}, {"active": False}, {"active": True}],
    )
    agent, _ = _native_agent(shared_dir, tmp_path, rpc)
    agent._native_run_iteration()                     # start
    agent._native_run_iteration()                     # status active
    agent._native_run_iteration()                     # status inactive -> start again
    assert [c[0] for c in rpc.calls].count("start_mining") == 2


def test_native_scans_found_blocks_incrementally(shared_dir, tmp_path):
    rpc = _FakeDaemonRPC(start_answers=[{"status": "OK"}], status_answers=[{"active": True}] * 3)
    agent, log = _native_agent(shared_dir, tmp_path, rpc)
    agent._native_run_iteration()
    log.write_text(
        "2000-01-01 00:10:00.000\tI Found block abc123 at height 5 for difficulty: 1200\n"
        "2000-01-01 00:10:01.000\tI something else\n"
    )
    assert agent._native_scan_found_blocks() == 1
    assert agent.blocks_generated == 1
    with open(log, "a") as f:
        f.write("2000-01-01 00:12:00.000\tI Found block def456 at height 6 for difficulty: 1250\n")
    assert agent._native_scan_found_blocks() == 1     # only the new line
    assert agent.blocks_generated == 2
    assert agent.last_block_height == 6


def test_native_cleanup_stops_mining(shared_dir, tmp_path):
    rpc = _FakeDaemonRPC(start_answers=[{"status": "OK"}], status_answers=[{"active": True}])
    agent, _ = _native_agent(shared_dir, tmp_path, rpc)
    agent._native_run_iteration()
    agent.mining_start_time = 1.0
    agent._cleanup_agent()
    assert ("stop_mining",) in rpc.calls


def test_generateblocks_mode_unchanged_by_default(shared_dir):
    agent = AutonomousMinerAgent(agent_id="miner-002", shared_dir=shared_dir,
                                 attributes=[["hashrate", "20"], ["is_miner", "true"]])
    assert agent.native_mode is False
