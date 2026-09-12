# scripts/test_selfish_phase2_configs.py
from pathlib import Path
import yaml
import pytest

CONFIG_DIR = Path("test_configs/selfish_phase2")

# (filename, expected bridge count, expected strategy)
CONFIGS = [
    ("fanout_1.yaml", 1, "eyal_sirer"),
    ("fanout_3.yaml", 3, "eyal_sirer"),
    ("fanout_6.yaml", 6, "eyal_sirer"),
    ("stub_trail.yaml", 6, "trail_stubborn"),
    ("stub_equalfork.yaml", 6, "equal_fork_stubborn"),
    ("stub_lead.yaml", 6, "lead_stubborn"),
]


def _load(name):
    with open(CONFIG_DIR / name) as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("name,n_bridges,strategy", CONFIGS,
                          ids=[c[0] for c in CONFIGS])
def test_phase2_config_invariants(name, n_bridges, strategy):
    cfg = _load(name)
    agents = cfg["agents"]

    attackers = {k: v for k, v in agents.items()
                 if v.get("script") == "agents.selfish_miner"}
    bridges = {k: v for k, v in agents.items()
               if v.get("script") == "agents.selfish_bridge"}

    assert len(attackers) == 1, f"{name}: exactly one attacker miner"
    assert len(bridges) == n_bridges, f"{name}: expected {n_bridges} bridges"

    (att_name, att), = attackers.items()
    bridge_ids = set(bridges.keys())
    attr_bridges = {b.strip() for b in att["attributes"]["bridges"].split(",") if b.strip()}
    assert attr_bridges == bridge_ids, (
        f"{name}: attacker bridges attr must list exactly the bridge ids "
        f"({attr_bridges} != {bridge_ids})")

    assert att.get("daemon_options", {}).get("offline") is True, f"{name}: attacker is --offline"
    assert cfg["general"]["mining"]["mode"] == "native", f"{name}: native mining mode"
    assert att["attributes"]["strategy"] == strategy, (
        f"{name}: strategy {att['attributes']['strategy']!r} != expected {strategy!r}")

    honest_total = sum(v["hashrate"] for v in agents.values()
                        if v.get("script") == "agents.autonomous_miner")
    alpha = att["hashrate"] / (att["hashrate"] + honest_total)
    assert abs(alpha - 0.4) < 0.01, f"{name}: alpha {alpha:.3f} != 0.4"
