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


# --- review 2026-09-26: overlay mutation / aliasing; plumbing-failure flag ----

def test_build_config_does_not_mutate_spec_overlays(tmp_path):
    """_apply_hashrates popped `hashrate` out of the spec's shared overlay
    dict, so a hashrate axis value applied only to the FIRST cell using it
    (later cells silently ran at the base alpha)."""
    spec = _spec(tmp_path, {"s": {"es": {}}})
    overlay = {"honest": {"hashrate": [4, 3]}, "attacker": {"hashrate": 5}}
    cfg1 = build_config(spec, {"a": overlay})
    cfg2 = build_config(spec, {"a": overlay})
    for cfg in (cfg1, cfg2):
        assert cfg["agents"]["honest-001"]["hashrate"] == 4
        assert cfg["agents"]["honest-002"]["hashrate"] == 3
        assert cfg["agents"]["attacker-miner"]["hashrate"] == 5
    assert overlay == {"honest": {"hashrate": [4, 3]}, "attacker": {"hashrate": 5}}


def test_overlay_does_not_leak_through_yaml_aliases(tmp_path):
    """_merge_stanza updated the agent's sub-dict in place; with a YAML anchor
    shared between agents, an overlay aimed at `honest` rewrote every agent
    sharing the alias (a network-wide flag flip measured as 'honest only')."""
    base = tmp_path / "base.yaml"
    base.write_text(
        "general: {stop_time: 6h, mining: {mode: native}}\n"
        "agents:\n"
        "  honest-001: {daemon: monerod, script: agents.autonomous_miner, hashrate: 3,\n"
        "               daemon_options: &common {log-level: 1}}\n"
        "  relay-001: {daemon: monerod, daemon_options: *common}\n"
        "  attacker-miner: {daemon: monerod, script: agents.selfish_miner, hashrate: 4,\n"
        "                   daemon_options: *common,\n"
        "                   attributes: {strategy: honest, bridge_agent: attacker-bridge}}\n"
        "  attacker-bridge: {daemon: monerod, script: agents.selfish_bridge}\n")
    spec = {"name": "t", "base": str(base), "axes": {"c": {"x": {}}}}
    cfg = build_config(spec, {"c": {"honest": {"daemon_options": {"sim-publish-or-perish": True}}}})
    assert cfg["agents"]["honest-001"]["daemon_options"] == {"log-level": 1, "sim-publish-or-perish": True}
    assert cfg["agents"]["relay-001"]["daemon_options"] == {"log-level": 1}
    assert cfg["agents"]["attacker-miner"]["daemon_options"] == {"log-level": 1}
    from scripts.selfish_matrix import dump_config
    dump_config(cfg, tmp_path / "out" / "x.yaml")
    dumped = (tmp_path / "out" / "x.yaml").read_text()
    assert "&id" not in dumped and "*id" not in dumped      # no aliases in generated configs
    assert yaml.safe_load(dumped)["agents"]["relay-001"]["daemon_options"] == {"log-level": 1}


def test_run_cell_flags_cell_with_no_attacker_blocks(tmp_path, monkeypatch):
    """An attacker at 4 h/s that found ZERO blocks in 6 h did not run (bridge
    never connected, daemon never mined): the cell proves nothing and must not
    read as a clean share of 0.000."""
    spec = _spec(tmp_path, {"strategy": {"es": {}}})
    archive = tmp_path / "archive"
    archive.mkdir()

    def fake_run(cmd, **kw):
        run_name = cmd[cmd.index("--name") + 1]
        (archive / f"20260922_000000_{run_name}").mkdir()

        class P:
            returncode = 0
            stdout = ""
            stderr = ""
        return P()

    def fake_analyze(run_dir, chain_path=None):
        r = dict(_fake_analyze(run_dir))
        r["share"] = 0.0
        r["orphan_stats"] = {"attacker_found": 0, "attacker_canonical": 0}
        r["preload_blocks"] = 336
        return r

    monkeypatch.setattr("scripts.selfish_matrix.subprocess.run", fake_run)
    monkeypatch.setattr("scripts.selfish_mining_analysis.analyze_run", fake_analyze)
    row = run_cell(spec, "es", {"strategy": "es"}, {"strategy": {}}, tmp_path / "work", archive)
    assert row["attacker_found"] == 0
    assert row["preload_blocks"] == 336
    assert row["health"]["ok"] is False
    assert "no-attacker-blocks" in row["health"]["summary"]


def test_reanalyze_rewrites_markers_without_launching(tmp_path, monkeypatch, capsys):
    """--reanalyze recomputes health + analysis from the archived run dirs
    (analysis fixes must never require re-running simulations)."""
    import json
    import sys
    from scripts.selfish_matrix import main
    spec_path = tmp_path / "spec.yaml"
    base = tmp_path / "base.yaml"
    base.write_text(yaml.safe_dump(BASE))
    spec_path.write_text(yaml.safe_dump({"name": "t", "base": str(base), "axes": {"strategy": {"es": {}}}}))
    work = tmp_path / "work" / "t"
    run_dir = tmp_path / "archive" / "20260926_000000_t__es"
    run_dir.mkdir(parents=True)
    (work / "cells").mkdir(parents=True)
    (work / "cells" / "es.json").write_text(json.dumps(
        {"cell": "es", "values": {"strategy": "es"}, "run_dir": str(run_dir), "returncode": 0, "share": 0.9}))

    def no_launch(cmd, *a, **k):
        if any("run_sim.sh" in str(c) for c in cmd):
            raise AssertionError("reanalyze must not launch run_sim.sh")

        class P:          # the commit stamp (`git rev-parse`) is fine
            returncode = 0
            stdout = "abc1234"
            stderr = ""
        return P()
    monkeypatch.setattr("scripts.selfish_matrix.subprocess.run", no_launch)

    def fake_analyze(rd, chain_path=None):
        r = dict(_fake_analyze(rd))
        r["share"] = 0.11
        r["share_honest_ref"] = 0.10
        r["orphan_stats"] = {"attacker_found": 40}
        return r
    monkeypatch.setattr("scripts.selfish_mining_analysis.analyze_run", fake_analyze)
    monkeypatch.setenv("MONEROSIM_MATRIX_WORKROOT", str(tmp_path / "work"))
    monkeypatch.setattr(sys, "argv", ["selfish_matrix.py", str(spec_path), "--reanalyze"])
    rc = main()
    row = json.loads((work / "cells" / "es.json").read_text())
    assert row["share"] == 0.11 and row["share_honest_ref"] == 0.10 and row["attacker_found"] == 40
    table = (work / "table.md").read_text()
    assert "share_h" in table and "0.110" in table and "0.100" in table
    assert rc in (0, 1)


def test_reanalyze_recovers_run_dir_from_run_name(tmp_path, monkeypatch):
    """A cell whose run_sim.sh exited non-zero AFTER archiving (2026-09-26:
    the script file was rewritten under 12 running instances) has a complete
    archive but a row with no run_dir; --reanalyze finds it by run name."""
    import json
    import sys
    from scripts.selfish_matrix import main
    spec_path = tmp_path / "spec.yaml"
    base = tmp_path / "base.yaml"
    base.write_text(yaml.safe_dump(BASE))
    spec_path.write_text(yaml.safe_dump({"name": "t", "base": str(base), "axes": {"strategy": {"es": {}}}}))
    work = tmp_path / "work" / "t"
    archive = tmp_path / "archive"
    run_dir = archive / "20260926_140803_t__es"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.txt").write_text("Exit code: 0\n")
    (work / "cells").mkdir(parents=True)
    (work / "cells" / "es.json").write_text(json.dumps(
        {"cell": "es", "values": {"strategy": "es"}, "run_name": "t__es", "returncode": 126,
         "error": "./run_sim.sh: line 2158: ...: Is a directory"}))

    def no_launch(cmd, *a, **k):
        assert not any("run_sim.sh" in str(c) for c in cmd)

        class P:
            returncode = 0
            stdout = "abc1234"
            stderr = ""
        return P()
    monkeypatch.setattr("scripts.selfish_matrix.subprocess.run", no_launch)
    monkeypatch.setattr("scripts.selfish_mining_analysis.analyze_run", _fake_analyze)
    monkeypatch.setenv("MONEROSIM_MATRIX_WORKROOT", str(tmp_path / "work"))
    monkeypatch.setenv("MONEROSIM_ARCHIVE_BASE", str(archive))
    monkeypatch.setattr(sys, "argv", ["selfish_matrix.py", str(spec_path), "--reanalyze"])
    main()
    row = json.loads((work / "cells" / "es.json").read_text())
    assert row["run_dir"] == str(run_dir) and row["recovered_run_dir"] is True
    assert row["share"] == 0.47 and "error" not in row


REPO = Path(__file__).resolve().parent.parent


def _plan_and_build(spec_name):
    from scripts.selfish_matrix import load_spec
    spec = load_spec(REPO / "test_configs" / "matrix" / f"{spec_name}.yaml")
    return spec, {cell: build_config(spec, overlays) for cell, _values, overlays in plan_cells(spec)}


def test_sop2_ctl_specs_unoffline_and_flag_the_attacker():
    """The upgrade-transition controls (2026-09-26) turn the attacker into a
    connected honest miner: `offline: false` (rendered as no flag by the
    orchestrator) and, for the upgraded cell only, the SoP flags; the sop2
    countermeasure stays as in pop_sop2_h10. The _rep draw has its own seed."""
    for name, seed in (("sop2_h10_ctl", 12345), ("sop2_h10_ctl_rep", 54321)):
        spec, cfgs = _plan_and_build(name)
        assert sorted(cfgs) == ["connected_sop2", "upgraded_sop2"]
        for cell, cfg in cfgs.items():
            assert cfg["general"]["simulation_seed"] == seed
            assert cfg["general"]["mining"]["chain_snapshot"] == "h10"
            att = cfg["agents"]["attacker-miner"]
            assert att["attributes"]["strategy"] == "honest"
            assert att["daemon_options"]["offline"] is False
            assert cfg["agents"]["honest-001"]["daemon_options"] == {"sim-share-or-perish": True, "sim-sop-w": 16}
            assert cfg["agents"]["relay-001"]["daemon"] == "monerod-sim"
            assert cfg["agents"]["attacker-bridge"]["daemon"] == "monerod-sim"
        assert cfgs["upgraded_sop2"]["agents"]["attacker-miner"]["daemon_options"]["sim-share-or-perish"] is True
        assert cfgs["upgraded_sop2"]["agents"]["attacker-miner"]["daemon_options"]["sim-sop-w"] == 16
        assert "sim-share-or-perish" not in cfgs["connected_sop2"]["agents"]["attacker-miner"]["daemon_options"]


def test_exact_specs_flag_honest_miners_only():
    """MRL #144 exact cells (2026-09-26): flags on the honest miners only, the
    attacker/bridge/relays stock; micro pairs with pop_sop2_h10's stock rows
    (same base and seeds), mid carries its own stock pairs."""
    flags = {"sim-publish-or-perish": True, "sim-pop-uncles-header": True, "sim-pop-det-tie": True}
    for name, seed, base in (("pop_exact_h10", 12345, "selfish_micro_sop.yaml"),
                             ("pop_exact_h10_rep", 54321, "selfish_micro_sop.yaml")):
        spec, cfgs = _plan_and_build(name)
        assert spec["base"].endswith(base)
        assert sorted(cfgs) == ["es_exact", "es_r2_exact", "honest_exact"]
        for cfg in cfgs.values():
            assert cfg["general"]["simulation_seed"] == seed
            assert cfg["agents"]["honest-001"]["daemon_options"] == flags
            assert cfg["agents"]["honest-002"]["daemon_options"] == flags
            assert cfg["agents"]["attacker-miner"]["daemon_options"] == {"offline": True}
            assert "daemon_options" not in cfg["agents"]["relay-001"]
        assert cfgs["es_r2_exact"]["agents"]["attacker-miner"]["attributes"]["release_lead"] == "2"
    for name, seed in (("pop_exact_mid", 12345), ("pop_exact_mid_rep", 54321)):
        spec, cfgs = _plan_and_build(name)
        assert sorted(cfgs) == ["es_exact", "es_none", "es_r2_exact", "es_r2_none", "honest_exact", "honest_none"]
        assert cfgs["es_exact"]["agents"]["honest-006"]["daemon_options"] == flags
        assert "daemon_options" not in cfgs["es_none"]["agents"]["honest-006"]
        assert cfgs["es_none"]["general"]["simulation_seed"] == seed


def test_dettie_mid_control_differs_from_exact_only_by_the_uncle_flag():
    """pop_dettie_mid{,_rep} (2026-09-27) isolate the uncle term: same base,
    seeds and strategies as pop_exact_mid, honest flags minus
    sim-pop-uncles-header."""
    for name, exact_name, seed in (("pop_dettie_mid", "pop_exact_mid", 12345),
                                   ("pop_dettie_mid_rep", "pop_exact_mid_rep", 54321)):
        spec, cfgs = _plan_and_build(name)
        _, exact = _plan_and_build(exact_name)
        assert sorted(cfgs) == ["es_dettie", "es_r2_dettie"]
        for strat in ("es", "es_r2"):
            d, e = cfgs[f"{strat}_dettie"], exact[f"{strat}_exact"]
            assert d["general"]["simulation_seed"] == seed == e["general"]["simulation_seed"]
            assert d["agents"]["attacker-miner"] == e["agents"]["attacker-miner"]
            eo = dict(e["agents"]["honest-001"]["daemon_options"])
            assert eo.pop("sim-pop-uncles-header") is True
            assert d["agents"]["honest-001"]["daemon_options"] == eo


def test_exact_relay_specs_put_the_relay_flag_on_the_bridge_in_every_cell():
    """pop_exact_relay{,_rep} (2026-09-27): the attacker bridge runs
    monerod-sim with sim-relay-alt-blocks in all six cells; the honest flags
    are the only other variable; nothing else relays alternatives."""
    for name, seed in (("pop_exact_relay", 12345), ("pop_exact_relay_rep", 54321)):
        spec, cfgs = _plan_and_build(name)
        assert sorted(cfgs) == sorted(f"{s}_{c}_relay" for s in ("es", "es_r2")
                                      for c in ("stock", "dettie", "exact"))
        for cell, cfg in cfgs.items():
            assert cfg["general"]["simulation_seed"] == seed
            assert cfg["general"]["mining"]["chain_snapshot"] == "h10"
            br = cfg["agents"]["attacker-bridge"]
            assert br["daemon"] == "monerod-sim" and br["daemon_options"] == {"sim-relay-alt-blocks": True}
            relaying = [a for a, v in cfg["agents"].items()
                        if (v.get("daemon_options") or {}).get("sim-relay-alt-blocks")]
            assert relaying == ["attacker-bridge"]
            assert cfg["agents"]["attacker-miner"]["daemon_options"] == {"offline": True}
        assert "daemon_options" not in cfgs["es_stock_relay"]["agents"]["honest-001"]
        assert "sim-pop-uncles-header" not in cfgs["es_dettie_relay"]["agents"]["honest-001"]["daemon_options"]
        assert cfgs["es_exact_relay"]["agents"]["honest-001"]["daemon_options"]["sim-pop-uncles-header"] is True


def test_fbridge_specs_differ_from_their_originals_only_in_the_bridge():
    """Stranding re-run (2026-09-27): each *_fbridge cell equals the same-named
    cell of its original matrix except that the attacker bridge runs the
    countermeasure rule (SoP: the relays' flag; PoP: the honest miners'
    flags). Seeds pair draw-for-draw."""
    pairs = [("pop_sop2_h10_fbridge", "pop_sop2_h10", {"sim-share-or-perish": True}),
             ("pop_exact_h10_fbridge", "pop_exact_h10", None),
             ("pop_exact_mid_fbridge", "pop_exact_mid", None)]
    for new, orig, bridge_opts in pairs:
        for suffix in ("", "_rep"):
            _, fb = _plan_and_build(new + suffix)
            _, og = _plan_and_build(orig + suffix)
            assert sorted(fb) and set(fb) <= set(og)
            for cell, cfg in fb.items():
                o = og[cell]
                want = bridge_opts or o["agents"]["honest-001"]["daemon_options"]
                br = cfg["agents"]["attacker-bridge"]
                assert br["daemon"] == "monerod-sim" and br["daemon_options"] == want
                assert cfg["general"] == o["general"]
                for aid in cfg["agents"]:
                    if aid != "attacker-bridge":
                        assert cfg["agents"][aid] == o["agents"][aid], (new + suffix, cell, aid)


def test_reject_specs_differ_from_their_predecessors_only_in_reject_aware():
    """Stranding-free re-run (2026-09-29): each *_reject cell equals the
    same-named cell of the flagged-bridge matrix (countermeasure cells) or of
    the original matrix (stock cells, micro only; the old ones ran on the
    pre-2026-09-29 h10 preset), except that the attacker is reject_aware.
    Seeds pair draw-for-draw."""
    pairs = [("pop_sop2_h10_reject", ["pop_sop2_h10_fbridge", "pop_sop2_h10"]),
             ("pop_exact_h10_reject", ["pop_exact_h10_fbridge"]),
             ("pop_exact_mid_reject", ["pop_exact_mid_fbridge"])]
    for new, preds in pairs:
        for suffix in ("", "_rep"):
            _, rj = _plan_and_build(new + suffix)
            cells = {}
            for p in preds:
                _, built = _plan_and_build(p + suffix)
                for c, cfg in built.items():
                    cells.setdefault(c, cfg)
            assert rj and all(c.startswith(("es_", "es_r2_")) for c in rj), sorted(rj)
            for cell, cfg in rj.items():
                o = cells[cell]
                att = dict(cfg["agents"]["attacker-miner"])
                att["attributes"] = dict(att["attributes"])
                assert att["attributes"].pop("reject_aware") == "true"
                assert att == o["agents"]["attacker-miner"], (new + suffix, cell)
                assert cfg["general"] == o["general"]
                for aid in cfg["agents"]:
                    if aid != "attacker-miner":
                        assert cfg["agents"][aid] == o["agents"][aid], (new + suffix, cell, aid)
    _, sop = _plan_and_build("pop_sop2_h10_reject")
    assert sorted(sop) == ["es_r2_sop2", "es_r2_stock", "es_sop2", "es_stock"]


def test_stubborn_specs_pin_arms_alphas_and_the_depth_sweep():
    """Stubborn-attacker campaign, corrected-binary run (2026-09-30): 12 cells
    (5 share_sop2, 2 block_sop2, 5 block_stock -- share is excluded against
    stock; block_sop2 is excluded at a030 and at d1/d3). Every cell keeps the
    10 h/s total so it grafts h10. The share arm flags the attacker's offline
    daemon and reads its own embedded share counts; the block arm does
    neither. weigh is `sop` on both arms except the stock countermeasure,
    which forces `weigh: difficulty, window_objects: "0"` (stock has no SoP
    concept of a window). The SoP overlay equals campaign 6's."""
    _, c6 = _plan_and_build("pop_sop2_h10_reject")
    c6_sop, c6_stock = c6["es_sop2"], c6["es_stock"]
    alphas = {"a030": (3, [3.5, 3.5]), "a040": (4, [3, 3]), "a045": (4.5, [2.75, 2.75])}
    for name, seed in (("stubborn_h10", 12345), ("stubborn_h10_rep", 54321)):
        _, cfgs = _plan_and_build(name)
        expected = ({f"share_sop2_{al}_d2" for al in alphas}
                    | {f"share_sop2_a040_{d}" for d in ("d1", "d3")}
                    | {f"block_sop2_{al}_d2" for al in ("a040", "a045")}
                    | {f"block_stock_{al}_d2" for al in alphas}
                    | {f"block_stock_a040_{d}" for d in ("d1", "d3")})
        assert len(expected) == 12
        assert set(cfgs) == expected, sorted(cfgs)
        for cell, cfg in cfgs.items():
            arm, cm, al, d = cell.split("_")
            assert cfg["general"]["simulation_seed"] == seed
            assert cfg["general"]["mining"]["chain_snapshot"] == "h10"
            att = cfg["agents"]["attacker-miner"]
            honest = [cfg["agents"][h]["hashrate"] for h in ("honest-001", "honest-002")]
            assert (att["hashrate"], honest) == alphas[al]
            assert att["hashrate"] + sum(honest) == 10
            assert cfg["agents"]["honest-001"]["hashrate"] == cfg["agents"]["honest-002"]["hashrate"]
            at = att["attributes"]
            assert at["strategy"] == "window_stubborn" and at["reject_aware"] == "true"
            assert at["give_up_depth"] == d[1:]
            if cell.startswith("share_sop2"):
                assert at["embedded_shares"] == "true"
                assert at["weigh"] == "sop" and at["window_objects"] == "48"
                assert att["daemon_options"] == {"offline": True, "sim-share-or-perish": True, "sim-sop-w": 16}
            elif cell.startswith("block_sop2"):
                assert "embedded_shares" not in at
                assert at["weigh"] == "sop" and at["window_objects"] == "48"
                assert att["daemon_options"] == {"offline": True}
            else:
                assert cell.startswith("block_stock")
                assert "embedded_shares" not in at
                assert at["weigh"] == "difficulty" and at["window_objects"] == "0"
                assert att["daemon_options"] == {"offline": True}
            ref = c6_sop if cm == "sop2" else c6_stock
            for aid in ("relay-001", "relay-002", "attacker-bridge"):
                assert cfg["agents"][aid] == ref["agents"][aid], (name, cell, aid)
            assert cfg["agents"]["honest-001"].get("daemon_options") == ref["agents"]["honest-001"].get("daemon_options")
            assert cfg["general"]["stop_time"] == ref["general"]["stop_time"]


def test_stubborn_rejudge_specs_add_one_flag_to_the_share_sop2_cells():
    """stubborn_h10_rejudge{,_rep} (2026-09-30): isolate monerod's native
    one-block-at-a-time re-judging of displaced blocks. Every cell equals
    stubborn_h10(_rep)'s share_sop2 cell at the same alpha and d2, once
    sim-sop-rejudge-displaced is popped from every non-attacker daemon's
    daemon_options -- and that flag is present on exactly those daemons."""
    for name, base_name in (("stubborn_h10_rejudge", "stubborn_h10"),
                            ("stubborn_h10_rejudge_rep", "stubborn_h10_rep")):
        _, cfgs = _plan_and_build(name)
        _, base = _plan_and_build(base_name)
        assert sorted(cfgs) == ["share_sop2_rejudge_a040_d2", "share_sop2_rejudge_a045_d2"]
        for cell, cfg in cfgs.items():
            ref = base[cell.replace("sop2_rejudge", "sop2")]
            must_have = ("honest-001", "honest-002", "relay-001", "relay-002", "attacker-bridge")
            assert cfg["agents"]["attacker-miner"] == ref["agents"]["attacker-miner"]
            for aid in cfg["agents"]:
                if aid == "attacker-miner":
                    continue
                do = dict(cfg["agents"][aid].get("daemon_options") or {})
                popped = do.pop("sim-sop-rejudge-displaced", None)
                if aid in must_have:
                    assert popped is True, (name, cell, aid)
                assert do == (ref["agents"][aid].get("daemon_options") or {}), (name, cell, aid)


def test_stubborn_long_specs_pin_alpha033_and_240h_otherwise_match_a040_d2():
    """stubborn_h10_long{,_rep} (2026-09-30): the MRL #146 alpha = 0.33 claim
    check ("about once per 10 days", "on average a 3-block reorg") at 240 h.
    Each cell equals stubborn_h10(_rep)'s same-arm, same-countermeasure
    a040_d2 cell once hashrate and stop_time are set aside."""
    for name, base_name in (("stubborn_h10_long", "stubborn_h10"),
                            ("stubborn_h10_long_rep", "stubborn_h10_rep")):
        _, cfgs = _plan_and_build(name)
        _, base = _plan_and_build(base_name)
        assert sorted(cfgs) == ["block_stock_a033_d2", "share_sop2_a033_d2"]
        for cell, cfg in cfgs.items():
            assert cfg["general"]["stop_time"] == "240h"
            assert cfg["agents"]["attacker-miner"]["hashrate"] == 3.3
            assert [cfg["agents"][h]["hashrate"] for h in ("honest-001", "honest-002")] == [3.35, 3.35]
            ref_cell = {"share_sop2_a033_d2": "share_sop2_a040_d2",
                        "block_stock_a033_d2": "block_stock_a040_d2"}[cell]
            ref = base[ref_cell]
            a = dict(cfg["agents"]["attacker-miner"]); a.pop("hashrate")
            r = dict(ref["agents"]["attacker-miner"]); r.pop("hashrate")
            assert a == r
            for aid in cfg["agents"]:
                if aid not in ("attacker-miner",):
                    c, b = dict(cfg["agents"][aid]), dict(ref["agents"][aid])
                    c.pop("hashrate", None)
                    b.pop("hashrate", None)
                    assert c == b, (name, cell, aid)


def test_pop_sop2_fixed_specs_match_reject_specs_cell_for_cell():
    """pop_sop2_h10_fixed{,_rep} (2026-09-30): campaign 6's SoP cells re-run on
    the corrected binary; configs identical to pop_sop2_h10_reject{,_rep},
    only the binary differs. Seeds already agree (pop_sop2_h10_reject has no
    explicit seed, so it takes the base config's 12345, same as this spec's
    explicit seed; the _rep pair both pin 54321)."""
    for name, ref_name in (("pop_sop2_h10_fixed", "pop_sop2_h10_reject"),
                           ("pop_sop2_h10_fixed_rep", "pop_sop2_h10_reject_rep")):
        _, cfgs = _plan_and_build(name)
        _, ref = _plan_and_build(ref_name)
        assert sorted(cfgs) == ["es_r2_sop2", "es_sop2"]
        for cell, cfg in cfgs.items():
            assert cfg == ref[cell], (name, cell)


def test_sop2_honest_specs_pin_cells_and_match_ctl_sop2_cells():
    """sop2_h10_honest{,_rep} (2026-09-30): honest controls on the corrected
    binary. upgraded_sop2 and connected_sop2 equal sop2_h10_ctl{,_rep}'s same
    cells; connected_stock carries no SoP flag anywhere."""
    for name, ctl_name in (("sop2_h10_honest", "sop2_h10_ctl"),
                           ("sop2_h10_honest_rep", "sop2_h10_ctl_rep")):
        _, cfgs = _plan_and_build(name)
        _, ctl = _plan_and_build(ctl_name)
        assert sorted(cfgs) == ["connected_sop2", "connected_stock", "upgraded_sop2"]
        assert cfgs["upgraded_sop2"] == ctl["upgraded_sop2"]
        assert cfgs["connected_sop2"] == ctl["connected_sop2"]
        cs = cfgs["connected_stock"]
        for aid, agent in cs["agents"].items():
            do = agent.get("daemon_options") or {}
            assert not any("sop" in str(k).lower() for k in do), (name, aid, do)


def test_stubborn_smoke_matches_stubborn_h10_cells_except_stop_time():
    """stubborn_h10_smoke (2026-09-30): its two cells (share_sop2_a045_d2,
    block_stock_a045_d2) equal stubborn_h10's same cells except stop_time."""
    _, cfgs = _plan_and_build("stubborn_h10_smoke")
    _, base = _plan_and_build("stubborn_h10")
    assert sorted(cfgs) == ["block_stock_a045_d2", "share_sop2_a045_d2"]
    for cell, cfg in cfgs.items():
        assert cfg["general"]["stop_time"] == "2h"
        ref = base[cell]
        c, b = dict(cfg["general"]), dict(ref["general"])
        c.pop("stop_time"); b.pop("stop_time")
        assert c == b
        assert cfg["agents"] == ref["agents"], cell


def test_every_matrix_cell_builds_its_attackers_strategy():
    """Every selfish-miner agent in every matrix cell gets a strategy that
    SelfishStrategy accepts, through the agent's own attribute parsing. The
    agent builds its strategy on its first tick. A rejected value
    (window_objects "0" in the stubborn smoke's stock cell, 2026-09-30) raised
    on every tick of the run, and the attacker never published."""
    from agents.selfish_miner import SelfishMinerAgent
    from agents.selfish_strategy import SelfishStrategy
    specs = sorted((REPO / "test_configs" / "matrix").glob("*.yaml"))
    built, bad = 0, []
    for path in specs:
        _, cfgs = _plan_and_build(path.stem)
        for cell, cfg in cfgs.items():
            for aid, agent in cfg["agents"].items():
                if not str(agent.get("script", "")).endswith("selfish_miner"):
                    continue
                at = agent.get("attributes") or {}
                try:
                    SelfishStrategy(at.get("strategy", "honest"), 0,
                                    **SelfishMinerAgent.strategy_kwargs(at))
                    built += 1
                except ValueError as e:
                    bad.append(f"{path.stem}/{cell}/{aid}: {e}")
    assert not bad, bad
    assert built > 0
