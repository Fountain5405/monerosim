"""End-to-end CLI tests for scripts/generate_config.py.

Scope: invoke generate_config.py as a subprocess (the same way run_sim.sh does)
and assert on the YAML it writes - top-level structure, agent-count contracts,
and determinism. This is the outer contract the planned main() refactor must
preserve. Uses the interpreter running the tests (the venv python) and runs
from the repo root so the module's dual-import resolves.

No Shadow, no monerod - generate_config only emits a YAML file. Subprocess
spawns are shared across assertions via module-scoped fixtures to stay fast.
"""
import subprocess
import sys
from pathlib import Path

import yaml
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATE = REPO_ROOT / "scripts" / "generate_config.py"

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


def _run(*args):
    """Run generate_config.py from the repo root; return CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(GENERATE), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture(scope="module")
def from_outputs(tmp_path_factory):
    """Run --from twice into distinct files (shared across the --from tests)."""
    d = tmp_path_factory.mktemp("gen_from")
    scenario = d / "small.scenario.yaml"
    scenario.write_text(SMALL_SCENARIO)
    out_a = d / "a.expanded.yaml"
    out_b = d / "b.expanded.yaml"
    r_a = _run("--from", str(scenario), "-o", str(out_a))
    r_b = _run("--from", str(scenario), "-o", str(out_b))
    assert r_a.returncode == 0, r_a.stderr
    assert r_b.returncode == 0, r_b.stderr
    return out_a, out_b


@pytest.fixture(scope="module")
def direct_output(tmp_path_factory):
    """One direct-flag (--agents) invocation, shared across the direct tests."""
    d = tmp_path_factory.mktemp("gen_direct")
    out = d / "direct.expanded.yaml"
    r = _run("--agents", "4", "--duration", "2h", "-o", str(out))
    assert r.returncode == 0, r.stderr
    return out


# ---------------------------------------------------------------------------
# --from scenario mode
# ---------------------------------------------------------------------------
def test_from_output_parses_and_has_expected_top_keys(from_outputs):
    out_a, _ = from_outputs
    doc = yaml.safe_load(out_a.read_text())
    assert set(doc.keys()) == {"general", "network", "agents"}


def test_from_output_agent_count(from_outputs):
    out_a, _ = from_outputs
    doc = yaml.safe_load(out_a.read_text())
    # 3 miners + 4 users + miner-distributor = 8.
    assert len(doc["agents"]) == 8
    assert "miner-distributor" in doc["agents"]


def test_from_output_is_deterministic_across_two_runs(from_outputs):
    out_a, out_b = from_outputs
    assert out_a.read_text() == out_b.read_text()


def test_from_output_preserves_network_path(from_outputs):
    out_a, _ = from_outputs
    doc = yaml.safe_load(out_a.read_text())
    assert doc["network"]["path"] == "gml_processing/test.gml"


def test_from_output_roundtrips_semantically_to_expanded_structure(from_outputs):
    """The --from path now uses the shared config_to_yaml emitter instead of
    yaml.dump, so the text formatting changed. But safe_load of the emitted
    file must still equal the structure expand_scenario produces (which is
    exactly what the pre-refactor yaml.dump path serialized). Semantic, not
    byte: only the serialization changed, not the content."""
    import io
    import contextlib

    from scripts.scenario_parser import parse_scenario, expand_scenario

    out_a, _ = from_outputs
    doc = yaml.safe_load(out_a.read_text())

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        scenario = parse_scenario(SMALL_SCENARIO)
        # Mirror main()'s --from call: seed from scenario, safe-tx-interval on.
        expected = expand_scenario(scenario, seed=12345,
                                   respect_safe_tx_interval=True)

    def _plain(o):
        if hasattr(o, "items"):
            return {k: _plain(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_plain(i) for i in o]
        return o

    assert doc == _plain(expected)


# ---------------------------------------------------------------------------
# direct-flag mode (--agents N): the miners-on-top contract.
# ---------------------------------------------------------------------------
def test_direct_output_parses(direct_output):
    doc = yaml.safe_load(direct_output.read_text())
    assert "agents" in doc
    assert "general" in doc


def test_direct_miner_and_user_count_contract(direct_output):
    # --agents N means N users; 5 fixed miners are added on top (docstring).
    doc = yaml.safe_load(direct_output.read_text())
    agents = doc["agents"]
    miners = [a for a in agents if a.startswith("miner-0")]
    users = [a for a in agents if a.startswith("user-")]
    assert len(users) == 4
    assert len(miners) == 5


def test_direct_missing_agents_is_an_error(tmp_path):
    # Neither --from nor --agents -> non-zero exit with a helpful message.
    out = tmp_path / "x.yaml"
    r = _run("-o", str(out))
    assert r.returncode != 0
    assert "--agents is required" in r.stderr
