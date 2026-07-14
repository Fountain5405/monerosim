"""Tests for scripts/scenario_parser.py (compact scenario -> expanded config).

Scope: the public expansion pipeline (parse_scenario -> expand_scenario) plus
the pure structural helpers it relies on (parse_range_pattern,
apply_type_defaults, parse_stagger_value, expand_stagger). These pin structural
invariants of the expansion output so the planned expand_scenario refactor keeps
the same public behavior. No engine / Shadow / daemon.

expand_scenario prints guardrail/calibration notes to stdout; tests capture and
ignore that (capsys) - the return value is the contract, not the chatter.
"""
import io
import contextlib

import pytest

from scripts.scenario_parser import (
    parse_scenario,
    expand_scenario,
    parse_range_pattern,
    apply_type_defaults,
    parse_stagger_value,
    expand_stagger,
    AGENT_TYPE_DEFAULTS,
)


# A deliberately small scenario mined from the shape of test_configs/*.scenario.yaml
# (topo300 / 20260511_200u_800r): 3 miners + 4 users + a script-only distributor.
# Kept tiny so expansion is fast and the arithmetic is checkable by hand.
SMALL_SCENARIO = """
general:
  stop_time: 2h
  simulation_seed: 12345
  bootstrap_end_time: auto
network:
  path: gml_processing/test.gml
  peer_mode: Dynamic
agents:
  miner-{001..003}:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    start_time: 0s
    start_time_stagger: 1s
    hashrate: [40, 30, 30]
  user-{001..004}:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.regular_user
    start_time: 600s
    transaction_interval: 300
    activity_start_time: auto
  miner-distributor:
    script: agents.miner_distributor
    wait_time: auto
"""


def _expand(text, seed=12345):
    """parse+expand, swallowing the guardrail prints."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        scenario = parse_scenario(text)
        config = expand_scenario(scenario, seed=seed)
    return config


def _plain(obj):
    """Recursively convert OrderedDicts to plain dicts for comparison."""
    if hasattr(obj, "items"):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_plain(i) for i in obj]
    return obj


# ---------------------------------------------------------------------------
# parse_range_pattern
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("pattern, expected", [
    ("miner-{001..005}", ("miner-", "{:03d}", 1, 5)),   # zero-padded width
    ("user-{1..100}", ("user-", "{}", 1, 100)),         # unpadded
    ("spy-{01..10}", ("spy-", "{:02d}", 1, 10)),
    ("relay-{001}", ("relay-", "{:03d}", 1, 1)),        # single-value brace
])
def test_parse_range_pattern(pattern, expected):
    assert parse_range_pattern(pattern) == expected


@pytest.mark.parametrize("pattern", ["miner-distributor", "simulation-monitor", "plain"])
def test_parse_range_pattern_non_range_returns_none(pattern):
    assert parse_range_pattern(pattern) is None


# ---------------------------------------------------------------------------
# apply_type_defaults
# ---------------------------------------------------------------------------
def test_apply_type_defaults_merges_and_strips_type_key():
    props = apply_type_defaults({"type": "miner", "hashrate": 50})
    assert "type" not in props
    assert props["daemon"] is True
    assert props["wallet"] is True
    assert props["script"] is True
    assert props["hashrate"] == 50  # explicit value preserved


def test_apply_type_defaults_explicit_wins_on_nested_merge():
    # daemon_options default {start-mining: True} deep-merges under explicit keys.
    props = apply_type_defaults({"type": "miner", "daemon_options": {"out-peers": 8}})
    assert props["daemon_options"]["out-peers"] == 8       # explicit
    assert props["daemon_options"]["start-mining"] is True  # from defaults


def test_apply_type_defaults_no_type_is_passthrough():
    original = {"daemon": "monerod", "hashrate": 10}
    assert apply_type_defaults(dict(original)) == original


def test_apply_type_defaults_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown agent type"):
        apply_type_defaults({"type": "wizard"})


def test_agent_type_defaults_table_has_expected_types():
    # Guard against an accidental key removal in the defaults table.
    assert {"miner", "user", "relay", "spy", "distributor", "monitor"} <= set(AGENT_TYPE_DEFAULTS)


# ---------------------------------------------------------------------------
# parse_stagger_value + expand_stagger (the stagger arithmetic primitives)
# ---------------------------------------------------------------------------
def test_parse_stagger_value_linear_from_duration_string():
    assert parse_stagger_value("5s", 3, 1) == ("linear", {"interval": 5})


def test_parse_stagger_value_random_range():
    stype, cfg = parse_stagger_value({"range": [10, 30]}, 4, 999)
    assert stype == "random"
    assert cfg == {"min": 10, "max": 30, "seed": 999}


def test_parse_stagger_value_list_length_mismatch_raises():
    with pytest.raises(ValueError, match="doesn't match agent count"):
        parse_stagger_value([1, 2, 3], 4, 1)


def test_expand_stagger_linear_arithmetic():
    # base 100s + i*5, three agents.
    assert expand_stagger(100, "linear", {"interval": 5}, 3, 0, 1) == [100, 105, 110]


def test_expand_stagger_random_is_seed_deterministic():
    stype, cfg = parse_stagger_value({"range": [10, 30]}, 4, 999)
    a = expand_stagger(0, stype, cfg, 4, 0, 999)
    b = expand_stagger(0, stype, cfg, 4, 0, 999)
    assert a == b
    assert len(a) == 4
    assert all(10 <= v <= 30 for v in a)


# ---------------------------------------------------------------------------
# expand_scenario: structural invariants on the small fixture.
# ---------------------------------------------------------------------------
def test_expand_scenario_agent_counts_and_ids():
    config = _expand(SMALL_SCENARIO)
    assert list(config.keys()) == ["general", "network", "agents"]
    agents = config["agents"]
    # 3 miners + 4 users + 1 distributor singleton = 8 entries.
    assert len(agents) == 8
    assert list(agents.keys()) == [
        "miner-001", "miner-002", "miner-003",
        "user-001", "user-002", "user-003", "user-004",
        "miner-distributor",
    ]


def test_expand_scenario_miner_start_time_stagger_arithmetic():
    agents = _expand(SMALL_SCENARIO)["agents"]
    # start_time stagger of 1s across the miner group: 0s, 1s, 2s.
    assert agents["miner-001"]["start_time"] == "0s"
    assert agents["miner-002"]["start_time"] == "1s"
    assert agents["miner-003"]["start_time"] == "2s"


def test_expand_scenario_hashrate_list_distributed_per_agent():
    agents = _expand(SMALL_SCENARIO)["agents"]
    assert agents["miner-001"]["hashrate"] == 40
    assert agents["miner-002"]["hashrate"] == 30
    assert agents["miner-003"]["hashrate"] == 30


def test_expand_scenario_u32_time_fields_are_plain_ints():
    # Rust parser wants these as u32 (plain int seconds), while start_time et al.
    # stay as "Ns" duration strings. Pin that type split ("u32 clamping").
    agents = _expand(SMALL_SCENARIO)["agents"]
    u = agents["user-001"]
    assert isinstance(u["transaction_interval"], int)
    assert isinstance(u["activity_start_time"], int)   # resolved from 'auto'
    assert u["activity_start_time"] != "auto"
    assert isinstance(u["start_time"], str) and u["start_time"].endswith("s")
    # singleton distributor: wait_time 'auto' -> int seconds.
    assert isinstance(agents["miner-distributor"]["wait_time"], int)


def test_expand_scenario_user_activity_times_are_staggered_and_ordered():
    agents = _expand(SMALL_SCENARIO)["agents"]
    times = [agents[f"user-{i:03d}"]["activity_start_time"] for i in range(1, 5)]
    # Non-decreasing stagger across the user group (first is the base).
    assert times == sorted(times)


def test_expand_scenario_is_deterministic_given_a_seed():
    a = _plain(_expand(SMALL_SCENARIO, seed=777))
    b = _plain(_expand(SMALL_SCENARIO, seed=777))
    assert a == b


def test_expand_scenario_passes_through_network_and_general():
    config = _expand(SMALL_SCENARIO)
    assert config["network"] == {"path": "gml_processing/test.gml", "peer_mode": "Dynamic"}
    # bootstrap_end_time: auto is resolved to a concrete duration string.
    assert config["general"]["bootstrap_end_time"] != "auto"
    assert config["general"]["simulation_seed"] == 12345


def test_expand_scenario_relay_group_daemon_only():
    # A daemon-only relay group (no wallet/script) still expands with staggered
    # start times and no wallet key.
    scenario = """
general:
  stop_time: 1h
  bootstrap_end_time: auto
network:
  path: g.gml
  peer_mode: Dynamic
agents:
  relay-{001..003}:
    daemon: monerod
    start_time: 0s
    start_time_stagger: 5s
"""
    agents = _expand(scenario)["agents"]
    assert len(agents) == 3
    assert agents["relay-001"]["start_time"] == "0s"
    assert agents["relay-002"]["start_time"] == "5s"
    assert agents["relay-003"]["start_time"] == "10s"
    assert "wallet" not in agents["relay-001"]
