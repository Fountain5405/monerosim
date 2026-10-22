"""Tests for analysis/spy/run_register.py: add a run, rebuild the register, annotate without overwriting."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_register as rr  # noqa: E402

CAL = [{"run": "x", "cell": "24/none",
        "slots": {"light": {"out": 0.07, "in": 0.0, "nodes": 3},
                  **{f"light:q{i}": {"out": 0.07 + i / 1000, "in": 0.0, "nodes": 3} for i in range(1, 5)}},
        "model": {"spies": 12, "spy_24s": 6, "honest_reachable": 71, "honest_reachable_24s": 69, "24": 0.0825},
        "stems": {"txs": 100, "fluff_per_hop": 0.2, "stem_hops_implied": 5.0, "embargo_rate": 0.0}}]


def fake_run(tmp_path, name="20261022_000000_x0_24_none_s1"):
    run = tmp_path / "archive" / name
    run.mkdir(parents=True)
    (run / "input_config.yaml").write_text("general: {}\n")
    (run / "binary_provenance.txt").write_text(
        "archived_at: 2026-10-22T00:00:00Z\nmonerod-sim: sha256=" + "ab" * 32 + " mtime=x\n")
    (run / "summary.txt").write_text("Wall time:      1h 55m\nExit code:      0\n  Created:          10\n  In blocks:        9\n")
    (run / "x0_calibration.json").write_text(json.dumps(CAL))
    (run / "memory_samples.csv").write_text("time,avail_mb\n00:00,5000\n00:01,4000\n00:02,6000\n")
    return run


def setup(tmp_path, monkeypatch):
    journal = tmp_path / "J.md"
    journal.write_text("head\n" + rr.START + "\nold\n" + rr.END + "\ntail\n")
    monkeypatch.setattr(rr, "JOURNAL", journal)
    monkeypatch.setattr(rr, "RUNS", tmp_path / "runs")
    return journal


def test_add_records_what_defines_and_scores_the_run(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    dest = rr.add(fake_run(tmp_path), "phantom", "n", [])
    meta = json.loads((dest / "meta.json").read_text())
    assert meta["light_out"] == 0.07 and meta["model_out"] == 0.0825
    assert meta["min_avail_mb"] == 4000 and meta["wall"] == "1h 55m" and meta["exit_code"] == 0
    assert meta["monerod_sim_sha"] == "ab" * 6 and meta["cell"] == "x0_24_none_s1"
    assert (dest / "input_config.yaml").exists() and (dest / "summary_head.txt").exists()


def test_table_replaces_only_the_register_block(tmp_path, monkeypatch):
    journal = setup(tmp_path, monkeypatch)
    rr.add(fake_run(tmp_path), "phantom", "a note", [])
    assert rr.table() == 1
    text = journal.read_text()
    assert text.startswith("head\n") and text.endswith("\ntail\n") and "old" not in text
    assert "`20261022_000000_x0_24_none_s1` | phantom | 12 / 6 | 71 / 69 | 0.0700 (0.0825)" in text
    assert "a note" in text


def test_annotate_appends_and_keeps_the_old_note(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    dest = rr.add(fake_run(tmp_path), "phantom", "first", [])
    rr.main(["annotate", dest.name, "second"])
    note = json.loads((dest / "meta.json").read_text())["note"]
    assert note.startswith("first [") and note.endswith("] second")
