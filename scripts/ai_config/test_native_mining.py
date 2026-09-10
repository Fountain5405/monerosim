"""Tests for the AI config generator's native-mining support.

Scope: pure-Python pieces only — the validator's mirror guards for
`general.mining` (docs/NATIVE_MINING.md), the generator's request-detection
regex and its `_check_against_request` expectation checks, and the
`LLMProvider` request-body construction (local-vs-remote Ollama fields,
`AI_CONFIG_REQUEST_EXTRAS`). No live model, no network I/O.
"""

import pytest

from scripts.ai_config.validator import ConfigValidator, ValidationReport
from scripts.ai_config.generator import (
    ConfigGenerator,
    LLMProvider,
    parse_user_request,
    _load_request_extras,
)


def _base_general(mining=None):
    general = {"stop_time": "1h"}
    if mining is not None:
        general["mining"] = mining
    return general


def _miner(hashrate=20, daemon="monerod", extra=None):
    cfg = {
        "daemon": daemon,
        "wallet": "monero-wallet-rpc",
        "script": "agents.autonomous_miner",
        "hashrate": hashrate,
        "start_time": "0s",
    }
    if extra:
        cfg.update(extra)
    return cfg


def _config(general, agents, network=None):
    return {
        "general": general,
        "network": network or {"path": "x.gml", "peer_mode": "Dynamic"},
        "agents": agents,
    }


# --- Validator: valid native config -----------------------------------------

def test_validator_accepts_valid_native_config():
    config = _config(
        _base_general({"mode": "native"}),
        {
            "miner-001": _miner(hashrate=20),
            "miner-002": _miner(hashrate=20),
        },
    )
    report = ConfigValidator().validate(config)
    assert report.has_native_mining is True
    assert report.is_valid, report.errors
    assert report.errors == []


# --- Validator: hashrate range in native mode -------------------------------

@pytest.mark.parametrize("bad_hashrate", [0, 1001])
def test_validator_rejects_out_of_range_hashrate_in_native_mode(bad_hashrate):
    config = _config(
        _base_general({"mode": "native"}),
        {"miner-001": _miner(hashrate=bad_hashrate)},
    )
    report = ConfigValidator().validate(config)
    assert not report.is_valid
    assert any("1..=1000" in e or "1000" in e for e in report.errors), report.errors


def test_validator_accepts_boundary_hashrates_in_native_mode():
    config = _config(
        _base_general({"mode": "native"}),
        {"miner-001": _miner(hashrate=1), "miner-002": _miner(hashrate=1000)},
    )
    report = ConfigValidator().validate(config)
    assert report.is_valid, report.errors


# --- Validator: zero miners in native mode ----------------------------------

def test_validator_rejects_native_mode_with_zero_miners():
    config = _config(_base_general({"mode": "native"}), {})
    report = ConfigValidator().validate(config)
    assert not report.is_valid
    assert any("no miners" in e for e in report.errors), report.errors


# --- Validator: hand-set sim knobs, either mode -----------------------------

def test_validator_rejects_hand_set_knob_in_daemon_defaults_native_mode():
    general = _base_general({"mode": "native"})
    general["daemon_defaults"] = {"sim-hash-interval-ms": 5}
    config = _config(general, {"miner-001": _miner()})
    report = ConfigValidator().validate(config)
    assert not report.is_valid
    assert any("sim-hash-interval-ms" in e for e in report.errors), report.errors


def test_validator_rejects_hand_set_knob_in_daemon_defaults_generateblocks_mode():
    general = _base_general()  # no mining key at all -> generateblocks
    general["daemon_defaults"] = {"sim-rx-full-dataset": True}
    config = _config(general, {"miner-001": _miner()})
    report = ConfigValidator().validate(config)
    assert not report.is_valid
    assert any("sim-rx-full-dataset" in e for e in report.errors), report.errors


def test_validator_rejects_hand_set_knob_in_agent_daemon_options():
    config = _config(
        _base_general({"mode": "native"}),
        {"miner-001": _miner(extra={"daemon_options": {"sim-hash-interval-ms": 10}})},
    )
    report = ConfigValidator().validate(config)
    assert not report.is_valid
    assert any("miner-001" in e and "sim-hash-interval-ms" in e for e in report.errors)


def test_validator_rejects_hand_set_knob_in_daemon_args():
    config = _config(
        _base_general(),  # generateblocks mode too
        {"miner-001": _miner(extra={"daemon_args": ["--sim-rx-full-dataset"]})},
    )
    report = ConfigValidator().validate(config)
    assert not report.is_valid
    assert any("miner-001" in e and "sim-rx-full-dataset" in e for e in report.errors)


# --- Validator: daemon_N phases on native miners ----------------------------

@pytest.mark.parametrize("extra", [
    {"daemon_0": "monerod", "daemon_1": "monerod"},
    # A lone suffix key (no bare daemon_0) still creates a phase entry in
    # the orchestrator (src/config/agent_config.rs parse_typed_phases /
    # has_daemon_phases) — the validator must catch this too.
    {"daemon_0_start": "0s"},
])
def test_validator_rejects_daemon_phases_on_native_miner(extra):
    config = _config(
        _base_general({"mode": "native"}),
        {"miner-001": _miner(extra=extra)},
    )
    report = ConfigValidator().validate(config)
    assert not report.is_valid
    assert any("miner-001" in e and "phase" in e for e in report.errors), report.errors


def test_validator_allows_daemon_phases_on_non_miner_in_native_mode():
    """Phase-key rejection is miner-specific; a phased user is unrelated."""
    config = _config(
        _base_general({"mode": "native"}),
        {
            "miner-001": _miner(),
            "user-001": {
                "daemon_0": "monerod",
                "daemon_1": "monerod",
                "wallet": "monero-wallet-rpc",
                "script": "agents.regular_user",
                "start_time": "0s",
            },
        },
    )
    report = ConfigValidator().validate(config)
    assert report.is_valid, report.errors


# --- Validator: bad mode value -----------------------------------------------

def test_validator_rejects_bad_mining_mode_value():
    config = _config(
        _base_general({"mode": "turbo"}),
        {"miner-001": _miner()},
    )
    report = ConfigValidator().validate(config)
    assert not report.is_valid
    assert any("general.mining.mode" in e for e in report.errors), report.errors
    assert report.has_native_mining is False


# --- Validator: sum-to-100 warning suppression ------------------------------

def test_validator_suppresses_sum_to_100_warning_in_native_mode():
    config = _config(
        _base_general({"mode": "native"}),
        {"miner-001": _miner(hashrate=20), "miner-002": _miner(hashrate=25)},
    )
    report = ConfigValidator().validate(config)
    assert not any("not 100" in w for w in report.warnings), report.warnings


def test_validator_keeps_sum_to_100_warning_in_generateblocks_mode():
    config = _config(
        _base_general(),  # no general.mining -> generateblocks (default)
        {"miner-001": _miner(hashrate=20), "miner-002": _miner(hashrate=25)},
    )
    report = ConfigValidator().validate(config)
    assert any("not 100" in w for w in report.warnings), report.warnings


# --- Generator: is_native_mining detection ----------------------------------

@pytest.mark.parametrize("request_text", [
    "native mining study: 5 miners at 20 hashes per second each, 10 users, 6 hours",
    "I want real PoW mining for this run",
    "let monerod mine all the blocks itself",
    "run a difficulty algorithm study over 8 hours",
    "study mining behaviour for research purposes",
    "study mining behavior for research purposes",
    "a pow study of 10 miners",
])
def test_parse_user_request_detects_native_mining_positive(request_text):
    parsed = parse_user_request(request_text)
    assert parsed.is_native_mining is True


@pytest.mark.parametrize("request_text", [
    "5 miners, 10 users, 2 hours",
    "hard fork scenario with 5 miners and mining as usual",
    "50 miners and 200 users for 8 hours",
])
def test_parse_user_request_detects_native_mining_negative(request_text):
    parsed = parse_user_request(request_text)
    assert parsed.is_native_mining is False


# --- Generator: _check_against_request both directions ---------------------

def test_check_against_request_flags_missing_native_mining():
    generator = ConfigGenerator(provider=LLMProvider(model="x", api_key="x", base_url="http://x"), verbose=False)
    report = ValidationReport()
    report.has_native_mining = False
    issues = generator._check_against_request(
        "native mining study of difficulty algorithm", report
    )
    assert issues is not None
    assert "native mining" in issues
    assert "general.mining.mode is not 'native'" in issues


def test_check_against_request_flags_unrequested_native_mining():
    generator = ConfigGenerator(provider=LLMProvider(model="x", api_key="x", base_url="http://x"), verbose=False)
    report = ValidationReport()
    report.has_native_mining = True
    issues = generator._check_against_request("5 miners and 10 users for 6 hours", report)
    assert issues is not None
    assert "did not ask for native mining" in issues


def test_check_against_request_silent_when_both_agree():
    generator = ConfigGenerator(provider=LLMProvider(model="x", api_key="x", base_url="http://x"), verbose=False)
    report = ValidationReport()
    report.has_native_mining = True
    issues = generator._check_against_request(
        "native mining study of difficulty algorithm", report
    )
    assert issues is None or "native mining" not in issues.lower().replace(
        "asks for native mining", ""
    )


# --- LLMProvider: local vs remote request body ------------------------------

def test_llm_provider_omits_ollama_fields_for_remote_url():
    provider = LLMProvider(
        model="glm-4.5-flash",
        api_key="x",
        base_url="https://api.z.ai/api/paas/v4",
        request_extras={},
    )
    body = provider._build_body([{"role": "user", "content": "hi"}])
    assert "num_ctx" not in body
    assert "keep_alive" not in body


@pytest.mark.parametrize("base_url", [
    "http://localhost:11434/v1",
    "http://127.0.0.1:11434/v1",
    "http://some-host:11434/v1",
])
def test_llm_provider_includes_ollama_fields_for_local_url(base_url):
    provider = LLMProvider(model="qwen3:8b-16k", api_key="x", base_url=base_url, request_extras={})
    body = provider._build_body([{"role": "user", "content": "hi"}])
    assert body["num_ctx"] == 16384
    assert body["keep_alive"] == "30m"


# --- LLMProvider: AI_CONFIG_REQUEST_EXTRAS merge ----------------------------

def test_request_extras_merge_from_env(monkeypatch):
    monkeypatch.setenv("AI_CONFIG_REQUEST_EXTRAS", '{"thinking": {"type": "disabled"}}')
    provider = LLMProvider(model="glm-4.5-flash", api_key="x", base_url="https://api.z.ai/api/paas/v4")
    body = provider._build_body([{"role": "user", "content": "hi"}])
    assert body["thinking"] == {"type": "disabled"}


def test_request_extras_win_over_ollama_defaults():
    provider = LLMProvider(
        model="qwen3:8b-16k",
        api_key="x",
        base_url="http://localhost:11434/v1",
        request_extras={"num_ctx": 999},
    )
    body = provider._build_body([{"role": "user", "content": "hi"}])
    assert body["num_ctx"] == 999


def test_request_extras_invalid_json_raises_clear_error(monkeypatch):
    monkeypatch.setenv("AI_CONFIG_REQUEST_EXTRAS", "{not valid json")
    with pytest.raises(ValueError, match="AI_CONFIG_REQUEST_EXTRAS"):
        LLMProvider(model="x", api_key="x", base_url="http://x")


def test_load_request_extras_helper_empty_and_none():
    assert _load_request_extras(None) == {}
    assert _load_request_extras("") == {}
    assert _load_request_extras('{"a": 1}') == {"a": 1}


def test_load_request_extras_helper_rejects_non_object():
    with pytest.raises(ValueError):
        _load_request_extras("[1, 2, 3]")


# --- CLI: malformed AI_CONFIG_REQUEST_EXTRAS surfaces as a clean error -----

def test_cli_main_reports_clear_error_for_invalid_request_extras(monkeypatch, capsys):
    """main() must not let get_llm_config()'s ValueError escape as a raw
    traceback; it should print 'Error: ...' and return 1, with no network
    call (the malformed env var is resolved before any LLMProvider/
    ConfigGenerator is constructed)."""
    import sys
    from scripts.ai_config import __main__ as ai_config_main

    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://x")
    monkeypatch.setenv("AI_CONFIG_REQUEST_EXTRAS", "{not valid json")
    monkeypatch.setattr(sys, "argv", ["ai_config", "5 miners, 10 users, 2 hours"])

    exit_code = ai_config_main.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error:" in captured.err
    assert "Traceback" not in captured.err
