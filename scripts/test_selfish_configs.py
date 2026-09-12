# scripts/test_selfish_configs.py
from pathlib import Path
import yaml
import pytest

CONFIGS = [
    Path("test_configs/selfish_micro.yaml"),
    Path("test_configs/selfish_sweep/alpha_0300.yaml"),
    Path("test_configs/selfish_sweep/alpha_0400.yaml"),
    Path("test_configs/selfish_sweep/alpha_0450.yaml"),
]


def _load(p):
    with open(p) as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.name)
def test_config_has_offline_attacker_and_bridge(path):
    cfg = _load(path)
    agents = cfg["agents"]
    attackers = {k: v for k, v in agents.items()
                 if v.get("script") == "agents.selfish_miner"}
    bridges = {k: v for k, v in agents.items()
               if v.get("script") == "agents.selfish_bridge"}
    assert len(attackers) == 1, f"{path}: exactly one attacker miner"
    assert len(bridges) == 1, f"{path}: exactly one bridge"

    (att_name, att), = attackers.items()
    (bridge_name, _), = bridges.items()
    assert att.get("daemon_options", {}).get("offline") is True, "attacker miner is --offline"
    assert att.get("hashrate", 0) >= 1, "attacker has a native hashrate"
    assert att["attributes"]["bridge_agent"] == bridge_name, "attacker points at the bridge"
    assert att["attributes"]["strategy"] in ("honest", "eyal_sirer")
    assert cfg["general"]["mining"]["mode"] == "native", "native mining mode"


@pytest.mark.parametrize("path,expected_alpha", [
    (Path("test_configs/selfish_sweep/alpha_0300.yaml"), 0.30),
    (Path("test_configs/selfish_sweep/alpha_0400.yaml"), 0.40),
    (Path("test_configs/selfish_sweep/alpha_0450.yaml"), 0.45),
], ids=["a030", "a040", "a045"])
def test_sweep_alpha_matches_hashrate_split(path, expected_alpha):
    cfg = _load(path)
    agents = cfg["agents"]
    att = next(v["hashrate"] for v in agents.values()
               if v.get("script") == "agents.selfish_miner")
    honest = sum(v["hashrate"] for v in agents.values()
                 if v.get("script") == "agents.autonomous_miner")
    alpha = att / (att + honest)
    assert abs(alpha - expected_alpha) < 0.01, f"{path}: alpha {alpha:.3f} != {expected_alpha}"
