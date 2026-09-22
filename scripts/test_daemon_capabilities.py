"""The capability gate must follow the config, not a fixed install path.

run_sim.sh used to demand ~/.monerosim/bin/monerod-sim whenever a config asked
for a patched option. That blocked a legitimate and important case: a
researcher pointing `daemon:` at their own monerod -- an eclipse countermeasure
build, for instance -- whose binary carried the needed patch all along. The
only escape was MONEROSIM_SKIP_SIM_BINARY_CHECK=1, which disables every
capability check at once, so the workaround was strictly worse than the
problem it solved.

daemon_capabilities() decides which binaries to probe and which flags each
needs. It has to mirror the orchestrator, including two subtleties that are
easy to get wrong and were wrong first time round: pure script agents run no
daemon, and native mining substitutes monerod-sim for miners.
"""
import os

import pytest
import yaml

from scripts.run_sim_helpers import daemon_capabilities

BIN = os.path.join(os.path.expanduser("~"), ".monerosim", "bin")


def write(tmp_path, cfg):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return str(p)


def test_shorthand_resolves_under_install_dir(tmp_path):
    cfg = {"agents": {"relay-1": {
        "daemon": "monerod-hf",
        "daemon_options": {"peerlist-dump-file": "peerlist_dump.jsonl"}}}}
    (e,) = daemon_capabilities(write(tmp_path, cfg))
    assert e["path"] == os.path.join(BIN, "monerod-hf")
    assert e["explicit"] is False
    assert e["flags"] == ["peerlist-dump-file"]


def test_explicit_path_is_honoured(tmp_path):
    """The colleague's shape: own patched build, named by absolute path."""
    own = "/home/someone/monero/build/release/bin/monerod"
    cfg = {"agents": {"relay-1": {
        "daemon": own,
        "daemon_options": {"peerlist-dump-file": "peerlist_dump.jsonl"}}}}
    (e,) = daemon_capabilities(write(tmp_path, cfg))
    assert e["path"] == own
    assert e["explicit"] is True, "explicit paths drive the advisory pin check"
    assert e["flags"] == ["peerlist-dump-file"]


def test_daemon_defaults_reach_node_agents(tmp_path):
    cfg = {"general": {"daemon_defaults": {"fakechain-hard-forks": "1:0,14:1"}},
           "agents": {"relay-1": {"daemon": "monerod-hf"}}}
    (e,) = daemon_capabilities(write(tmp_path, cfg))
    assert e["flags"] == ["fakechain-hard-forks"]


def test_pop_countermeasure_flags_are_gated(tmp_path):
    """A PoP run must fail preflight against a binary without the patch:
    without this gate the run would silently measure stock fork choice and
    report it as the countermeasure's effect."""
    cfg = {"agents": {"honest-001": {
        "daemon": "monerod-sim",
        "daemon_options": {"sim-publish-or-perish": True,
                           "sim-pop-k": 3}}}}
    (e,) = daemon_capabilities(write(tmp_path, cfg))
    assert e["flags"] == ["sim-pop-k", "sim-publish-or-perish"]


def test_pop_uncles_flag_is_gated(tmp_path):
    cfg = {"agents": {"honest-001": {
        "daemon": "monerod-sim",
        "daemon_options": {"sim-publish-or-perish": True,
                           "sim-pop-uncles": True}}}}
    (e,) = daemon_capabilities(write(tmp_path, cfg))
    assert e["flags"] == ["sim-pop-uncles", "sim-publish-or-perish"]  # sorted


def test_pop_uncles_header_flag_is_gated(tmp_path):
    cfg = {"agents": {"honest-001": {
        "daemon": "monerod-sim",
        "daemon_options": {"sim-publish-or-perish": True,
                           "sim-pop-uncles-header": True}}}}
    (e,) = daemon_capabilities(write(tmp_path, cfg))
    assert e["flags"] == ["sim-pop-uncles-header", "sim-publish-or-perish"]


def test_pure_script_agent_needs_no_daemon(tmp_path):
    """Regression: a monitor agent inherited daemon_defaults and demanded a
    patched binary it never runs (src/agent/pure_scripts.rs)."""
    cfg = {"general": {"daemon_defaults": {"fakechain-hard-forks": "1:0,14:1"}},
           "agents": {"simulation-monitor": {"script": "agents.simulation_monitor"}}}
    assert daemon_capabilities(write(tmp_path, cfg)) == []


def test_agent_with_script_and_daemon_is_a_node(tmp_path):
    """eclipse_probe agents carry both; they do run a daemon."""
    cfg = {"agents": {"relay-4000": {
        "daemon": "monerod-hf", "script": "agents.eclipse_probe",
        "daemon_options": {"peerlist-dump-file": "d.jsonl"}}}}
    (e,) = daemon_capabilities(write(tmp_path, cfg))
    assert e["agents"] == ["relay-4000"]


def test_native_mining_substitutes_monerod_sim_for_miners(tmp_path):
    """Regression: miners declare `daemon: monerod` but the orchestrator swaps
    in monerod-sim (src/agent/user_agents.rs), so probe that instead."""
    cfg = {"general": {"mining": {"mode": "native"}},
           "agents": {"miner-001": {"daemon": "monerod", "hashrate": 50}}}
    (e,) = daemon_capabilities(write(tmp_path, cfg))
    assert e["path"] == os.path.join(BIN, "monerod-sim")
    assert e["flags"] == ["sim-hash-interval-ms"]


def test_native_mining_leaves_non_miners_alone(tmp_path):
    cfg = {"general": {"mining": {"mode": "native"}},
           "agents": {"miner-001": {"hashrate": 50},
                      "relay-1": {"daemon": "monerod"}}}
    paths = [e["path"] for e in daemon_capabilities(write(tmp_path, cfg))]
    assert paths == [os.path.join(BIN, "monerod-sim")]


def test_plain_config_is_ungated(tmp_path):
    """An ordinary run must not be blocked by this gate at all."""
    cfg = {"agents": {"relay-1": {"daemon": "monerod"},
                      "miner-001": {"daemon": "monerod", "hashrate": 10}}}
    assert daemon_capabilities(write(tmp_path, cfg)) == []


def test_cuprated_is_left_to_its_own_gate(tmp_path):
    cfg = {"general": {"daemon_defaults": {"peerlist-dump-file": "d.jsonl"}},
           "agents": {"relay-1": {"daemon": "cuprated"}}}
    assert daemon_capabilities(write(tmp_path, cfg)) == []


def test_distinct_binaries_reported_separately(tmp_path):
    own = "/opt/custom/monerod"
    cfg = {"agents": {
        "relay-1": {"daemon": "monerod-hf",
                    "daemon_options": {"peerlist-dump-file": "d.jsonl"}},
        "relay-2": {"daemon": own,
                    "daemon_options": {"sim-relay-alt-blocks": True}}}}
    got = {e["path"]: e for e in daemon_capabilities(write(tmp_path, cfg))}
    assert set(got) == {os.path.join(BIN, "monerod-hf"), own}
    assert got[own]["flags"] == ["sim-relay-alt-blocks"]
    assert got[own]["explicit"] is True


def test_per_agent_options_override_defaults(tmp_path):
    cfg = {"general": {"daemon_defaults": {"log-level": 1}},
           "agents": {"relay-1": {
               "daemon": "monerod-hf",
               "daemon_options": {"sim-relay-alt-blocks": True}}}}
    (e,) = daemon_capabilities(write(tmp_path, cfg))
    assert e["flags"] == ["sim-relay-alt-blocks"]


def test_named_patched_binary_is_checked_even_without_flags(tmp_path):
    """Naming monerod-hf means the build must exist, flags or not."""
    cfg = {"agents": {"relay-1": {"daemon": "monerod-hf"}}}
    (e,) = daemon_capabilities(write(tmp_path, cfg))
    assert e["flags"] == []
    assert e["path"] == os.path.join(BIN, "monerod-hf")
