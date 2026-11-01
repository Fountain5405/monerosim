import json

import pytest

from scripts import sop_param_readout as rd


def test_fit_crossing_recovers_the_zero_of_a_line():
    pts = [(0.45, -0.02), (0.46, -0.01), (0.47, 0.0), (0.48, 0.01)]
    c, b = rd.fit_crossing(pts)
    assert c == pytest.approx(0.47)
    assert b == pytest.approx(1.0)


def test_model_rows_keep_only_the_cells_knobs_and_the_default_window(tmp_path):
    p = tmp_path / "m.jsonl"
    rows = [
        dict(alpha=0.47, knobs=dict(G=6, L=1, M=1, R=1, Z=1), K=3, w=16, share=0.47, reveals=100, days=2000),
        dict(alpha=0.47, knobs=dict(G=8, L=1, M=1, R=1, Z=1), K=3, w=16, share=0.99, reveals=1, days=2000),
        dict(alpha=0.47, knobs=dict(G=6, L=1, M=1, R=1, Z=1), K=3, w=8, share=0.99, reveals=1, days=2000),
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows))
    m = rd.model_rows(str(p))
    assert [r["share"] for r in m[0.47]] == [0.47]


def test_sim_cells_group_seeds_by_the_alpha_in_the_file_name(tmp_path):
    for name, share in (("a047_s1", 0.45), ("a047_s2", 0.51), ("a050_s1", 0.72)):
        (tmp_path / f"share_sop2_param_{name}.json").write_text(json.dumps({"share": share}))
    cells = rd.sim_cells(str(tmp_path))
    assert sorted(cells) == [0.47, 0.5]
    assert [(s, d["share"]) for s, d in cells[0.47]] == [("s1", 0.45), ("s2", 0.51)]


def test_reveals_are_compared_per_found_block(tmp_path):
    # the model's 72 h is 2,160 found blocks, a sim's holds 1.4-1.6x that (2026-10-27)
    row = dict(reveals=60, att_final=400, att_orphaned=100, hon_final=400, hon_orphaned=300)
    assert rd.model_reveals_per_1000_found(row) == 50.0
    run = "20261026_100300_sop_v4_param_72h__share_sop2_param_a047_s1"
    d = tmp_path / "moonpie" / "campaign9" / run
    d.mkdir(parents=True)
    (d / "summary.txt").write_text(f"CHECK {run} oracle=0mm/12nodes a3=542 reveals=150 a3_undelivered=2 -> PASS\n")
    cell = {"run_dir": f"/home/x/monerosim/archived_runs/{run}", "canonical_blocks": 1950, "network_orphan_rate": 0.35}
    assert rd.sim_reveals_per_1000_found(cell, str(tmp_path)) == pytest.approx(50.0)
    assert rd.sim_reveals_per_1000_found(cell, str(tmp_path / "nothing")) is None
