"""Tests for sop_v4_probes (R3 flips, R4 count, pool-counted decisions)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sop_v4_probes as P  # noqa: E402

ALT, MAIN = "aa" * 32, "bb" * 32


def rec(**kw):
    r = {"v": 4, "h0": 0, "hf": 11, "top": 12, "w": 16, "k": 2, "d_ms": 1000,
         "online": False, "major": 16, "mode": "x", "alt_tip": ALT,
         "main_tip": MAIN, "alt_tips": 1,
         "alt": [{"h": 11, "diff": "160"}, {"h": 12, "diff": "100"}],
         "main": [{"h": 11, "diff": "160"}, {"h": 12, "diff": "160"}],
         "pool_alt": [], "pool_main": [], "pool_diff_alt": "160",
         "pool_diff_main": "160"}
    r.update(kw)
    return r


def dec_line(ts, r):
    return f"{ts}\t[P2P1]\tINFO\tblockchain\tx.cpp:1\tSIM-SoP-DEC {json.dumps(r)}\n"


def share_line(ts, prev, slot, tip=0):
    return (f"{ts}\t[P2P9]\tINFO\tblockchain\tx.cpp:2\tSIM-SoP: pooled remote "
            f"share <{'cc' * 32}> at height 13 prev {prev} slot {slot} tip {tip}\n")


def run_dir(tmp_path, lines):
    d = tmp_path / "run" / "daemon_logs" / "n1"
    d.mkdir(parents=True)
    (d / "bitmonero.log").write_text("".join(lines))
    return tmp_path / "run"


def test_r3_flip(tmp_path):
    rd = run_dir(tmp_path, [dec_line("2000-01-01 00:20:13.000", rec()),
                            share_line("2000-01-01 00:20:14.000", ALT, 16)])
    s = P.probe_run(rd)["n1"]
    assert s["v4"] == 1 and s["flips"] == 1


def test_r4_and_pool_counted(tmp_path):
    rd = run_dir(tmp_path, [dec_line("2000-01-01 00:20:13.000", rec(alt_tips=2))])
    s = P.probe_run(rd)["n1"]
    assert s["r4"] == 1 and s["flips"] == 0 and s["pool_counted"] == 0


def test_v3_only(tmp_path):
    rd = run_dir(tmp_path, [dec_line("2000-01-01 00:20:13.000", {"v": 3}),
                            "garbage line\n"])
    s = P.probe_run(rd)["n1"]
    assert s == {"v4": 0, "pool_counted": 0, "r4": 0, "flips": 0}
