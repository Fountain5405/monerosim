# scripts/test_selfish_matrix.py
"""Unit tests for the matrix runner: config generation, cell planning, the
run/analyze pipeline (with the sim launch and analyzer mocked), and table
rendering. No simulation is ever started."""
from pathlib import Path

import pytest
import yaml

from scripts.selfish_matrix import (
    apply_overlay, build_config, plan_cells, render_table, run_cell,
    _sanitize,
)

BASE = {
    "general": {"stop_time": "6h", "simulation_seed": 12345,
                "mining": {"mode": "native"}},
    "agents": {
        "honest-001": {"daemon": "monerod", "script": "agents.autonomous_miner",
                       "hashrate": 3},
        "honest-002": {"daemon": "monerod", "script": "agents.autonomous_miner",
                       "hashrate": 3},
        "attacker-miner": {"daemon": "monerod", "script": "agents.selfish_miner",
                           "hashrate": 4,
                           "attributes": {"strategy": "honest",
                                          "bridge_agent": "attacker-bridge"}},
        "attacker-bridge": {"daemon": "monerod", "script": "agents.selfish_bridge"},
    },
}


def _spec(tmp_path, axes, **kw):
    base = tmp_path / "base.yaml"
    base.write_text(yaml.safe_dump(BASE))
    spec = {"name": "t", "base": str(base), "axes": axes}
    spec.update(kw)
    return spec


def test_build_config_merges_overlays(tmp_path):
    spec = _spec(tmp_path, {}, stop_time="2h", seed=99)
    cfg = build_config(spec, {"s": {
        "attacker": {"attributes": {"strategy": "eyal_sirer", "release_lead": "2"}},
        "honest": {"daemon_options": {"sim-publish-or-perish": True}},
    }})
    att = cfg["agents"]["attacker-miner"]
    # attributes MERGE: bridge_agent survives, strategy overridden, new key added
    assert att["attributes"] == {"strategy": "eyal_sirer", "release_lead": "2",
                                 "bridge_agent": "attacker-bridge"}
    for hid in ("honest-001", "honest-002"):
        assert cfg["agents"][hid]["daemon_options"] == {"sim-publish-or-perish": True}
    assert cfg["general"]["stop_time"] == "2h"
    assert cfg["general"]["simulation_seed"] == 99


def test_hashrate_split_scalar_and_list(tmp_path):
    spec = _spec(tmp_path, {})
    cfg = build_config(spec, {"a": {"attacker": {"hashrate": 5},
                                    "honest": {"hashrate": [4, 3]}}})
    assert cfg["agents"]["attacker-miner"]["hashrate"] == 5
    assert cfg["agents"]["honest-001"]["hashrate"] == 4
    assert cfg["agents"]["honest-002"]["hashrate"] == 3
    with pytest.raises(SystemExit, match="hashrate list of 1"):
        build_config(spec, {"a": {"honest": {"hashrate": [4]}}})


def test_overlay_targets_and_eclipsed_victims(tmp_path):
    base = yaml.safe_load(yaml.safe_dump(BASE))
    base["agents"]["victim-001"] = {
        "daemon": "monerod", "script": "agents.autonomous_miner", "hashrate": 2,
        "attributes": {"eclipsed": "true"}}
    p = tmp_path / "base2.yaml"
    p.write_text(yaml.safe_dump(base))
    cfg = yaml.safe_load(yaml.safe_dump(base))
    apply_overlay(cfg, {"honest": {"daemon_options": {"x": True}},
                        "bridges": {"daemon_options": {"y": True}},
                        "all": {"daemon_options": {"z": True}}}, "t")
    assert cfg["agents"]["victim-001"]["daemon_options"] == {"z": True}  # not x
    assert cfg["agents"]["honest-001"]["daemon_options"] == {"x": True, "z": True}
    assert cfg["agents"]["attacker-bridge"]["daemon_options"] == {"y": True, "z": True}
    with pytest.raises(SystemExit, match="unknown overlay target"):
        apply_overlay(cfg, {"islands": {}}, "t")


def test_relays_target_reaches_only_forwarding_nodes():
    """SoP-style gossip specs must flip relays to monerod-sim (a vanilla
    monerod relay drops the workshare levin message) without touching the
    attacker, its bridge, or any miner."""
    from scripts.selfish_matrix import apply_overlay
    base = yaml.safe_load(yaml.safe_dump(BASE))
    base["agents"]["relay-001"] = {"daemon": "monerod", "start_time": "30s"}
    cfg = yaml.safe_load(yaml.safe_dump(base))
    apply_overlay(cfg, {"relays": {"daemon": "monerod-sim",
                                   "daemon_options": {"sim-share-or-perish": True}}}, "t")
    r = cfg["agents"]["relay-001"]
    assert r["daemon"] == "monerod-sim"
    assert r["daemon_options"] == {"sim-share-or-perish": True}
    # nobody else moved: attacker stock, bridge stock, honest miner untouched
    assert "daemon_options" not in cfg["agents"]["attacker-miner"]
    assert "daemon_options" not in cfg["agents"]["attacker-bridge"]
    assert "daemon_options" not in cfg["agents"]["honest-001"]


def test_plan_cells_product_and_exclude(tmp_path):
    axes = {
        "strategy": {"es": {}, "honest": {}},
        "cm": {"none": {}, "pop": {"honest": {"daemon_options": {"p": True}}}},
    }
    cells = plan_cells(_spec(tmp_path, axes))
    assert len(cells) == 4
    assert {c[0] for c in cells} == {"es_none", "es_pop", "honest_none", "honest_pop"}
    cells = plan_cells(_spec(tmp_path, axes, exclude=[{"strategy": "honest", "cm": "pop"}]))
    assert "honest_pop" not in {c[0] for c in cells}
    assert _sanitize("lead 2/ω=0.3") == "lead_2___0.3"   # per-char, like run_sim.sh


def _fake_analyze(run_dir, chain_path=None):
    return {"alpha": 0.4, "alpha_eff": 0.4, "release_lead": 1, "eclipse": False,
            "share": 0.47, "controlled": None, "gamma": 0.0, "n_ties": 3,
            "attacker_orphan_rate": 0.2, "network_orphan_rate": 0.25,
            "canonical_blocks": 180, "msb_max_z": 4.2,
            "theory": {"es_gamma0": 0.484}, "verdicts": [{"name": "v", "pass": True}]}


def test_run_cell_pipeline_and_resume(tmp_path, monkeypatch):
    spec = _spec(tmp_path, {"strategy": {"es": {}}})
    archive = tmp_path / "archive"
    archive.mkdir()
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        run_name = cmd[cmd.index("--name") + 1]
        (archive / f"20260922_000000_{run_name}").mkdir()

        class P:
            returncode = 0
            stdout = ""
            stderr = ""
        return P()

    monkeypatch.setattr("scripts.selfish_matrix.subprocess.run", fake_run)
    monkeypatch.setattr("scripts.selfish_mining_analysis.analyze_run", _fake_analyze)

    row = run_cell(spec, "es", {"strategy": "es"}, {"strategy": {}},
                   tmp_path / "work", archive)
    assert row["share"] == 0.47 and row["all_verdicts_pass"] is True
    assert row["run_dir"].endswith("t__es")
    assert (tmp_path / "work" / "cells" / "es.json").exists()
    assert (tmp_path / "work" / "configs" / "es.yaml").exists()

    row2 = run_cell(spec, "es", {"strategy": "es"}, {"strategy": {}},
                    tmp_path / "work", archive)
    assert len(calls) == 1          # marker present -> no second launch


def test_run_cell_records_failure(tmp_path, monkeypatch):
    spec = _spec(tmp_path, {"strategy": {"es": {}}})

    def fake_run(cmd, **kw):
        class P:
            returncode = 1
            stdout = ""
            stderr = "preflight failed"
        return P()

    monkeypatch.setattr("scripts.selfish_matrix.subprocess.run", fake_run)
    row = run_cell(spec, "es", {"strategy": "es"}, {"strategy": {}},
                   tmp_path / "work", tmp_path)
    assert "error" in row and "preflight failed" in row["error"]


def test_render_table(tmp_path):
    spec = _spec(tmp_path, {"strategy": {"es": {}, "honest": {}}})
    rows = [
        {"cell": "es", "values": {}, "alpha": 0.4, "share": 0.47,
         "controlled": None, "gamma": 0.0, "attacker_orphan_rate": 0.2,
         "network_orphan_rate": 0.25, "msb_max_z": 4.2, "canonical_blocks": 180,
         "verdicts": [("v", True)], "all_verdicts_pass": True,
         "run_dir": "/x/archived_runs/20260922_000000_t__es"},
        {"cell": "honest", "values": {}, "error": "boom"},
    ]
    table = render_table(spec, rows)
    assert "PASS" in table and "0.470" in table and "t__es" in table
    assert "Failed cells" in table and "boom" in table


def test_render_table_two_axes_columns_align(tmp_path):
    """Review 2026-09-25 F6: with two axes the old renderer emitted one `cell`
    column under two axis headers, shifting every value one column left
    (gamma read as attacker orphan, ...). Each axis now gets its column."""
    spec = _spec(tmp_path, {"strategy": {"es": {}}, "countermeasure": {"sop2": {}, "stock": {}}})
    rows = [{"cell": "es_sop2", "values": {"strategy": "es", "countermeasure": "sop2"},
             "alpha": 0.4, "share": 0.0, "controlled": None, "gamma": 0.0,
             "attacker_orphan_rate": 1.0, "network_orphan_rate": 0.353,
             "msb_max_z": 1.417, "canonical_blocks": 66, "verdicts": [("v", False)],
             "all_verdicts_pass": False, "health": {"summary": "REORG 0/9; EXC 9"},
             "run_dir": "/x/archived_runs/20260925_000000_t__es_sop2"}]
    table = render_table(spec, rows)
    header, sep, row = [l for l in table.splitlines() if l.startswith("|")][:3]
    cols = [c.strip() for c in header.strip("|").split("|")]
    cells = [c.strip() for c in row.strip("|").split("|")]
    assert len(cols) == len(cells)
    got = dict(zip(cols, cells))
    assert got["strategy"] == "es" and got["countermeasure"] == "sop2"
    assert got["gamma"] == "0.000" and got["att_orph"] == "1.000"
    assert got["net_orph"] == "0.353" and got["msb_z"] == "1.417"
    assert got["health"] == "REORG 0/9; EXC 9"


def test_main_dry_run_generates_overlaid_configs(tmp_path, monkeypatch, capsys):
    spec = {
        "name": "t", "base": str(tmp_path / "base.yaml"), "stop_time": "1h",
        "axes": {
            "strategy": {"es": {"attacker": {"attributes": {"strategy": "eyal_sirer"}}},
                         "honest": {}},
            "cm": {"none": {},
                   "relay": {"honest": {"daemon_options": {"sim-relay-alt-blocks": True}}}},
        },
    }
    (tmp_path / "base.yaml").write_text(yaml.safe_dump(BASE))
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(spec, sort_keys=False))   # axis order = cell-name order
    monkeypatch.setenv("MONEROSIM_MATRIX_WORKROOT", str(tmp_path / "mw"))
    monkeypatch.setattr("sys.argv", ["selfish_matrix.py", str(spec_path), "--dry-run"])
    import scripts.selfish_matrix as sm
    assert sm.main() == 0
    out = capsys.readouterr().out
    assert "4 cell(s) planned" in out
    cfg = yaml.safe_load((tmp_path / "mw" / "t" / "configs" / "es_relay.yaml").read_text())
    assert cfg["agents"]["attacker-miner"]["attributes"]["strategy"] == "eyal_sirer"
    assert cfg["agents"]["honest-001"]["daemon_options"] == {"sim-relay-alt-blocks": True}
    assert cfg["general"]["stop_time"] == "1h"
