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
    assert victim["daemon_options"]["offline"] is True   # v8: no P2P at all
    assert victim["attributes"]["mine_after_height"] == "3"
    assert island["attributes"]["eclipsed"] == "true"
    assert island["daemon_options"]["offline"] is True
    # naive alpha far below the gamma=0 threshold; alpha_eff well inside the
    # profitable regime but below the majority line (ES curve defined).
    assert abs(_alpha_from_config(cfg) - 4 / 15) < 0.01
    assert abs(_alpha_eff_from_config(cfg) - 7 / 15) < 0.01
    assert cfg["general"]["simulation_seed"] == 12345


def test_eclipse_majority_config():
    from scripts.selfish_mining_analysis import _alpha_eff_from_config
    cfg = _load(Path("test_configs/selfish_eclipse/gamma_eclipse_majority.yaml"))
    agents = cfg["agents"]
    assert agents["victim-001"]["hashrate"] == 6
    assert agents["victim-001"]["start_time"] == "15m"
    honest = sum(v["hashrate"] for k, v in agents.items()
                 if v.get("script") == "agents.autonomous_miner" and k != "victim-001")
    assert honest == 5
    assert abs(_alpha_eff_from_config(cfg) - 10 / 15) < 0.01   # majority regime


def test_pop_pilot_matrix_spec():
    # The PoP pilot flags HONEST miners only (honest-network deployment; the
    # attacker's covert bridge keeps stock rules). docs/20260922_pop_
    # countermeasure_design.md pre-registers the predictions.
    with open("test_configs/matrix/pop_pilot.yaml") as f:
        spec = yaml.safe_load(f)
    pop = spec["axes"]["countermeasure"]["pop"]
    assert set(pop) == {"honest"}, "PoP must not reach the attacker or its bridge"
    assert pop["honest"]["daemon_options"]["sim-publish-or-perish"] is True
    assert spec["axes"]["strategy"]["es"]["attacker"]["attributes"]["strategy"] == "eyal_sirer"
    base = _load(Path(spec["base"]))
    honest = [k for k, v in base["agents"].items()
              if v.get("script") == "agents.autonomous_miner"]
    assert len(honest) >= 2, "overlay target population exists in the base"


@pytest.mark.parametrize("rep,orig", [
    ("pop_exact_rep", "pop_exact"),
    ("pop_scale_rep", "pop_scale"),
    ("pop_scale_r2_rep", "pop_scale_r2"),
], ids=["exact", "scale", "scale_r2"])
def test_replication_specs_mirror_their_originals(rep, orig):
    # A replication run must be the SAME experiment under a NEW matrix
    # name: the runner resumes per matrix name (a reused name would skip
    # every cell and "replicate" nothing), and a drifted overlay would
    # silently measure a different point while wearing the old label.
    with open(f"test_configs/matrix/{rep}.yaml") as f:
        r = yaml.safe_load(f)
    with open(f"test_configs/matrix/{orig}.yaml") as f:
        o = yaml.safe_load(f)
    assert r["name"] == rep != o["name"]
    assert r["base"] == o["base"]
    assert r["axes"] == o["axes"], "replication must not drift from the original cells"
    assert r.get("exclude") == o.get("exclude")


@pytest.mark.parametrize("path,n_miners,hps,relays", [
    (Path("test_configs/selfish_scaled.yaml"), 12, 2, 32),      # senior
    (Path("test_configs/selfish_scaled_mid.yaml"), 6, 3, 16),   # local pilot
], ids=["scaled", "scaled_mid"])
def test_scaled_selfish_configs(path, n_miners, hps, relays):
    from scripts.selfish_mining_analysis import _alpha_from_config
    cfg = _load(path)
    agents = cfg["agents"]
    att = next(v for v in agents.values() if v.get("script") == "agents.selfish_miner")
    honest = [v for v in agents.values() if v.get("script") == "agents.autonomous_miner"]
    n_relay = sum(1 for k in agents if k.startswith("relay-"))
    assert len(honest) == n_miners and all(v["hashrate"] == hps for v in honest)
    assert n_relay == relays
    assert att["daemon_options"]["offline"] is True
    assert att["attributes"]["bridges"] == "attacker-bridge"
    assert abs(_alpha_from_config(cfg) - 0.40) < 0.01   # attacker/(attacker+honest)
    assert cfg["general"]["simulation_seed"] == 12345


@pytest.mark.parametrize("path,omega,expected_alpha_eff", [
    (Path("test_configs/selfish_eclipse_sweep/omega_0000.yaml"), 0, 4 / 15),
    (Path("test_configs/selfish_eclipse_sweep/omega_0200.yaml"), 2, 6 / 15),
    (Path("test_configs/selfish_eclipse_sweep/omega_0300_3v.yaml"), 3, 7 / 15),
], ids=["w000", "w020", "w030_3v"])
def test_omega_sweep_points(path, omega, expected_alpha_eff):
    # The omega sweep holds TOTAL hashrate at 15 h/s (so equilibrium
    # difficulty is identical at every point) and the attacker at 4 h/s,
    # varying only how much honest hashrate is eclipsed (recruited).
    from scripts.selfish_mining_analysis import _alpha_eff_from_config
    cfg = _load(path)
    agents = cfg["agents"]
    att = next(v for v in agents.values() if v.get("script") == "agents.selfish_miner")
    victims = {k: v for k, v in agents.items()
               if v.get("attributes", {}).get("eclipsed") == "true"
               and v.get("script") == "agents.autonomous_miner"}
    islands = {k: v for k, v in agents.items()
               if v.get("script") == "agents.selfish_bridge"
               and v.get("attributes", {}).get("victims")}
    total = sum(v["hashrate"] for v in agents.values() if v.get("hashrate"))
    assert total == 15, f"{path}: sweep points hold total hashrate at 15 h/s"
    assert att["hashrate"] == 4
    assert sum(v["hashrate"] for v in victims.values()) == omega
    assert cfg["general"]["simulation_seed"] == 12345
    if omega == 0:
        assert not victims and not islands
        assert "islands" not in att["attributes"]   # plain-selfish anchor
    else:
        for vid, v in victims.items():              # v8+ victim semantics
            assert v["daemon_options"]["offline"] is True
            assert v["attributes"]["mine_after_height"] == "3"
        assert len(islands) == 1                    # exactly one island
        island = next(iter(islands.values()))
        assert set(island["attributes"]["victims"].split(",")) == set(victims)
        assert att["attributes"]["islands"] in islands
    assert abs(_alpha_eff_from_config(cfg) - expected_alpha_eff) < 0.01
