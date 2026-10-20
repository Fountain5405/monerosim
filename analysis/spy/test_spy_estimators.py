"""Tests for analysis/spy/spy_estimators.py on hand-built observations.

Run: python3 -m pytest analysis/spy/test_spy_estimators.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spy_estimators as se  # noqa: E402

SPIES = {"spy-001", "spy-002"}
UNREACHABLE = {"user-001": True, "user-002": False, "relay-001": False}


def test_estimate_skips_spy_senders_and_applies_reachability():
    # spy-002 stemmed it to spy-001 first; the first honest stem is user-001.
    obs = [(1, "spy-002", False), (2, "user-001", False), (3, "relay-001", True)]
    g = se.estimate(obs, SPIES, UNREACHABLE)
    assert g == {"sp": "user-001", "sp_r": "user-001", "fs": "relay-001", "combined": "user-001"}


def test_estimate_reachable_predecessor_dropped_by_sp_r():
    g = se.estimate([(1, "user-002", False)], SPIES, UNREACHABLE)
    assert g["sp"] == "user-002" and g["sp_r"] is None and g["fs"] is None


def test_estimate_fluff_only_falls_back_to_first_spy():
    g = se.estimate([(5, "relay-001", True), (6, "user-002", True)], SPIES, UNREACHABLE)
    assert g == {"sp": None, "sp_r": None, "fs": "relay-001", "combined": "relay-001"}


def test_score_groups_recall_by_sender_and_precision_by_guess():
    cls = {"user-001": "unreachable", "user-002": "reachable", "relay-001": "reachable"}.get
    none = {e: None for e in se.ESTIMATORS}
    rows = [
        ("user-001", dict(none, sp="user-001")),   # correct
        ("user-001", dict(none, sp="relay-001")),  # wrong, guess is reachable
        ("user-002", dict(none, sp="user-002")),   # correct
        ("user-002", none),                        # abstain
    ]
    s = se.score(rows, cls)["sp"]
    assert s["unreachable"] == {"n": 2, "guesses": 1, "correct": 1, "recall": 0.5, "precision": 1.0}
    assert s["reachable"]["recall"] == 0.5 and s["reachable"]["precision"] == 0.5


def test_exposure_buckets_by_tx_count():
    cls = lambda a: "reachable"  # noqa: E731
    none = {e: None for e in se.ESTIMATORS}
    rows = [("a", dict(none, combined="a"))] + [("b", none)] * 3 + [("c", none)] * 5
    e = se.exposure(rows, cls, "combined")["reachable"]
    assert e == {"1": [1, 1], "2-4": [1, 0], "5-9": [1, 0]}


def test_bootstrap_interval_contains_point_estimate():
    cls = lambda a: "reachable"  # noqa: E731
    none = {e: None for e in se.ESTIMATORS}
    rows = [(f"u{i}", dict(none, sp=f"u{i}" if i % 2 else None)) for i in range(40)]
    lo, hi = se.bootstrap(rows, cls, 200)[("sp", "reachable", "recall")]
    assert lo <= 0.5 <= hi and hi - lo < 0.5


def test_first_hop_spy_counts_origin_stems_to_spies():
    ip_map = {"10.0.0.9": "spy-001", "10.0.0.2": "relay-001"}
    stems = {"aa": {"user-001": (1, "10.0.0.9:18080")},
             "bb": {"user-001": (2, "10.0.0.2:18080")},
             "cc": {"relay-001": (3, "10.0.0.9:18080")}}  # not the origin's hop
    rows = [("aa", "user-001"), ("bb", "user-001"), ("cc", "user-001")]
    r = se.first_hop_spy(stems, rows, SPIES, ip_map, lambda a: "unreachable")
    assert r["unreachable"] == {"txs": 2, "to_spy": 1, "share": 0.5}


def test_p_stem_series_window_carries_epoch_in_force():
    ip_map = {"10.0.0.9": "spy-001", "10.0.0.2": "relay-001"}
    t = lambda s: (s + se.topology_metrics.SIM_EPOCH_UNIX) * 1e6  # noqa: E731
    spy, honest = {"addr": "10.0.0.9:18080"}, {"addr": "10.0.0.2:18080"}
    logs = {"user-001": [
        {"t": t(10), "ev": "epoch", "stems": [honest]},
        {"t": t(50), "ev": "epoch", "stems": [spy, honest]},   # in force at 100
        {"t": t(150), "ev": "epoch", "stems": [spy]},
        {"t": t(300), "ev": "epoch", "stems": [honest]},       # after the window
    ]}
    s = se.p_stem_series(logs, SPIES, ip_map, t_from=100, t_to=200)
    assert s == {"user-001": [(100, 0.5), (150.0, 1.0)]}
