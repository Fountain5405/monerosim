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


def test_release2_config_is_micro_plus_release_lead():
    # The release-lead experiment must be selfish_micro.yaml with ONLY the
    # release_lead attribute (and header comments) different, so its result is
    # directly comparable to the archived phase-1 micro runs.
    cfg = _load(Path("test_configs/selfish_release2.yaml"))
    base = _load(Path("test_configs/selfish_micro.yaml"))
    att = next(v for v in cfg["agents"].values()
               if v.get("script") == "agents.selfish_miner")
    assert att["attributes"].get("release_lead") == "2", "release_lead: \"2\" set"
    assert att["attributes"].get("strategy") == "eyal_sirer"
    assert att.get("daemon_options", {}).get("offline") is True
    assert cfg["general"]["mining"]["mode"] == "native"

    def strip(path):
        d = _load(Path(path))
        for a in d["agents"].values():
            a.get("attributes", {}).pop("release_lead", None)
        return d
    assert strip("test_configs/selfish_release2.yaml") == strip("test_configs/selfish_micro.yaml"), \
        "release2 differs from micro by more than the release_lead attribute"


@pytest.mark.parametrize("path,expected_alpha", [
    (Path("test_configs/selfish_sweep_release2/alpha_0300.yaml"), 0.30),
    (Path("test_configs/selfish_sweep_release2/alpha_0400.yaml"), 0.40),
    (Path("test_configs/selfish_sweep_release2/alpha_0450.yaml"), 0.45),
], ids=["r2a030", "r2a040", "r2a045"])
def test_release2_sweep_alpha_and_knob(path, expected_alpha):
    # Each conservative-release sweep point is the matching ES sweep config
    # plus release_lead: 2 — same seed, same shape, alpha arithmetic intact.
    cfg = _load(path)
    agents = cfg["agents"]
    att = next(v for v in agents.values() if v.get("script") == "agents.selfish_miner")
    honest = sum(v["hashrate"] for v in agents.values()
                 if v.get("script") == "agents.autonomous_miner")
    assert abs(att["hashrate"] / (att["hashrate"] + honest) - expected_alpha) < 0.01
    assert att["attributes"].get("release_lead") == "2"
    assert att.get("daemon_options", {}).get("offline") is True
    assert cfg["general"]["mining"]["mode"] == "native"
    assert cfg["general"]["simulation_seed"] == 12345


def test_eclipse_config_pins_and_alpha_eff():
    from scripts.selfish_mining_analysis import _alpha_eff_from_config, _alpha_from_config
    cfg = _load(Path("test_configs/selfish_eclipse/gamma_eclipse.yaml"))
    agents = cfg["agents"]
    att = next(v for v in agents.values() if v.get("script") == "agents.selfish_miner")
    victim = agents["victim-001"]
    island = agents["attacker-island"]
    assert att["attributes"]["islands"] == "attacker-island"
    assert att.get("daemon_options", {}).get("offline") is True
    assert cfg["general"]["mining"]["mode"] == "native"
    assert victim["attributes"]["eclipsed"] == "true"
    assert victim["peers"]["exclusive"] == ["attacker-island"]
    assert victim["peers"]["in_peers"] == 0
    assert island["attributes"]["eclipsed"] == "true"
    # naive alpha far below the gamma=0 threshold; alpha_eff well inside the
    # profitable regime but below the majority line (ES curve defined).
    assert abs(_alpha_from_config(cfg) - 4 / 15) < 0.01
    assert abs(_alpha_eff_from_config(cfg) - 7 / 15) < 0.01
    assert cfg["general"]["simulation_seed"] == 12345
