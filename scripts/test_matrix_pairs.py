# scripts/test_matrix_pairs.py
from scripts.matrix_pairs import pair, render


def _row(cell, share, share_h, ok=True, summary="ok", err=None):
    r = {"cell": cell, "values": {"strategy": cell.split("_")[0], "countermeasure": cell.split("_")[-1]},
         "alpha": 0.4, "share": share, "share_honest_ref": share_h, "canonical_blocks": 180,
         "preload_blocks": 336, "attacker_found": 70, "run_dir": f"archived_runs/x_{cell}",
         "health": {"ok": ok, "summary": summary, "forks_seen": 40, "share_weighted": 12}}
    if err:
        r["error"] = err
    return r


def test_pair_means_spread_and_ok_requires_every_draw():
    paired = pair({"a": [_row("es_sop2", 0.30, 0.28), _row("es_stock", 0.45, 0.45)],
                   "b": [_row("es_sop2", 0.34, 0.30), _row("es_stock", 0.47, 0.47, ok=False, summary="no-forks")]})
    by = {p["cell"]: p for p in paired}
    assert abs(by["es_sop2"]["mean_share"] - 0.32) < 1e-9 and abs(by["es_sop2"]["spread_share"] - 0.04) < 1e-9
    assert abs(by["es_sop2"]["mean_share_h"] - 0.29) < 1e-9
    assert by["es_sop2"]["ok"] is True and by["es_stock"]["ok"] is False
    assert by["es_stock"]["per_draw"]["b"]["health"] == "no-forks"


def test_pair_handles_missing_draw_and_errors():
    paired = pair({"a": [_row("honest_sop2", 0.39, None)], "b": [_row("honest_sop2", None, None, err="analysis: empty")]})
    p = paired[0]
    assert p["n"] == 1 and p["spread_share"] is None and p["mean_share_h"] is None
    assert p["ok"] is False


def test_render_has_one_row_per_cell_and_flags_not_ok():
    paired = pair({"a": [_row("es_sop2", 0.3, 0.3)], "b": [_row("es_sop2", 0.3, 0.3, ok=False, summary="share-term-inert")]})
    t = render(paired, ["a", "b"])
    lines = [l for l in t.splitlines() if l.startswith("| es_sop2")]
    assert len(lines) == 1 and "| NO |" in lines[0] and "share-term-inert" in lines[0]
