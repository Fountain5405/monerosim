"""Tests for scripts/native_daa_analysis.py (native-mining DAA analysis).

Scope: the pure-function pieces (duration/timestamp parsing, interval and
regime computation, share/sigma math, stale-find exclusion) pinned with
tiny synthetic fixtures, plus one integration test that runs the CLI
end-to-end against a real archived native-mining run if present. No Shadow,
no daemon, no run execution.
"""
import math
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.native_daa_analysis import (
    parse_duration,
    parse_sim_ts,
    build_accepted,
    attach_intervals,
    derive_join_time,
    assign_regimes,
    per_regime_miner_table,
    make_verdicts,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "native_daa_analysis.py"


# ---------------------------------------------------------------------------
# parse_duration
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("value,expected", [
    ("0s", 0.0),
    ("4s", 4.0),
    ("14400s", 14400.0),
    ("4h", 14400.0),
    ("10m", 600.0),
    (30, 30.0),
    (12.5, 12.5),
    (None, 0.0),
])
def test_parse_duration(value, expected):
    assert parse_duration(value) == expected


def test_parse_duration_rejects_garbage():
    with pytest.raises(ValueError):
        parse_duration("not-a-duration")


# ---------------------------------------------------------------------------
# parse_sim_ts (including day rollover)
# ---------------------------------------------------------------------------
def test_parse_sim_ts_basic():
    assert parse_sim_ts("2000-01-01 00:00:18.104") == pytest.approx(18.104)


def test_parse_sim_ts_day_rollover():
    # A run past 24h wall-clock rolls the date to 2000-01-02.
    t_end_of_day1 = parse_sim_ts("2000-01-01 23:59:59.500")
    t_start_of_day2 = parse_sim_ts("2000-01-02 00:00:05.000")
    assert t_end_of_day1 == pytest.approx(86399.5)
    assert t_start_of_day2 == pytest.approx(86405.0)
    assert t_start_of_day2 > t_end_of_day1


# ---------------------------------------------------------------------------
# interval / regime computation on a tiny synthetic block list
# ---------------------------------------------------------------------------
def _entry(miner, height, t, diff, stale=False):
    return {"miner": miner, "height": height, "sim_time_s": t, "difficulty": diff, "stale": stale}


def test_attach_intervals_and_regimes():
    accepted = [
        {"height": 1, "sim_time_s": 0.0, "miner": "m1", "difficulty": 1},
        {"height": 2, "sim_time_s": 120.0, "miner": "m1", "difficulty": 100},
        {"height": 3, "sim_time_s": 250.0, "miner": "m2", "difficulty": 110},
    ]
    attach_intervals(accepted)
    assert accepted[0]["interval_s"] is None
    assert accepted[1]["interval_s"] == pytest.approx(120.0)
    assert accepted[2]["interval_s"] == pytest.approx(130.0)

    assign_regimes(accepted, join_time=200.0)
    assert [r["regime"] for r in accepted] == ["pre", "pre", "post"]

    assign_regimes(accepted, join_time=None)
    assert [r["regime"] for r in accepted] == ["n/a", "n/a", "n/a"]


def test_derive_join_time():
    miners = {
        "m1": {"hashrate": 20, "start_s": 0.0},
        "m2": {"hashrate": 20, "start_s": 30.0},
        "m3": {"hashrate": 10, "start_s": 14400.0},
    }
    assert derive_join_time(miners) == pytest.approx(14400.0)

    # No miner starts after 60s -> no split.
    miners_no_late = {
        "m1": {"hashrate": 20, "start_s": 0.0},
        "m2": {"hashrate": 5, "start_s": 60.0},
    }
    assert derive_join_time(miners_no_late) is None


# ---------------------------------------------------------------------------
# stale-find exclusion
# ---------------------------------------------------------------------------
def test_build_accepted_excludes_stale_and_dedupes_races():
    raw = [
        _entry("m1", 1, 0.0, 1),
        _entry("m2", 1, 0.1, 1),          # race at height 1: earliest wins
        _entry("m1", 2, 1.0, 40),
        _entry("m2", 2, 1.05, 40, stale=True),  # explicitly flagged stale
    ]
    accepted = build_accepted(raw)
    heights = [r["height"] for r in accepted]
    assert heights == [1, 2]
    # height 1: m1 (0.0) wins over m2 (0.1) by earliest-timestamp tie-break.
    assert accepted[0]["miner"] == "m1"
    # height 2: m2 was excluded (stale), so only m1's find remains.
    assert accepted[1]["miner"] == "m1"


def test_build_accepted_empty_input():
    assert build_accepted([]) == []


# ---------------------------------------------------------------------------
# share / sigma math
# ---------------------------------------------------------------------------
def test_per_regime_miner_table_share_math():
    miners = {
        "m1": {"hashrate": 80, "start_s": 0.0},
        "m2": {"hashrate": 20, "start_s": 0.0},
    }
    # 100 blocks, exactly matching the 80/20 hashrate split.
    accepted = []
    for h in range(1, 101):
        miner = "m1" if h <= 80 else "m2"
        accepted.append({"height": h, "sim_time_s": float(h), "miner": miner,
                          "difficulty": 1000, "interval_s": 1.0, "regime": "n/a"})
    table = per_regime_miner_table(accepted, miners, join_time=None)
    rows = {r["miner"]: r for r in table["n/a"]}
    assert rows["m1"]["share"] == pytest.approx(80.0)
    assert rows["m1"]["expected"] == pytest.approx(80.0)
    assert rows["m1"]["verdict"] == "PASS"
    # sigma = 100*sqrt(p*(1-p)/n), p=0.8, n=100
    expected_sigma = 100.0 * math.sqrt(0.8 * 0.2 / 100)
    assert rows["m1"]["sigma"] == pytest.approx(expected_sigma, rel=1e-6)
    assert rows["m2"]["verdict"] == "PASS"


def test_per_regime_miner_table_skewed_share_fails():
    miners = {
        "m1": {"hashrate": 50, "start_s": 0.0},
        "m2": {"hashrate": 50, "start_s": 0.0},
    }
    # m1 finds every single block despite an even hashrate split -> way
    # outside 2.5 sigma.
    accepted = [
        {"height": h, "sim_time_s": float(h), "miner": "m1",
         "difficulty": 1000, "interval_s": 1.0, "regime": "n/a"}
        for h in range(1, 51)
    ]
    table = per_regime_miner_table(accepted, miners, join_time=None)
    rows = {r["miner"]: r for r in table["n/a"]}
    assert rows["m1"]["share"] == pytest.approx(100.0)
    assert rows["m2"]["share"] == pytest.approx(0.0)
    assert rows["m1"]["verdict"] == "FAIL"
    assert rows["m2"]["verdict"] == "FAIL"


# ---------------------------------------------------------------------------
# end-difficulty verdict: +/-25% tolerance, not a hard 1.0x ceiling
# ---------------------------------------------------------------------------
def _find_verdict(verdicts, name_substr):
    for name, status, detail in verdicts:
        if name_substr in name:
            return status, detail
    raise AssertionError(f"no verdict matched {name_substr!r}")


def test_end_difficulty_verdict_allows_a_few_percent_overshoot():
    d_eq = 12000.0
    diffcp = {"checkpoints": {"at_end": None}, "d_pre_eq": d_eq, "d_post_eq": d_eq}
    windows = {"pre_h1_4": [], "first20": None, "last2h": []}
    miners = {"m1": {"hashrate": 100, "start_s": 0.0}}

    # D_end = 1.01 x D_eq: a real LWMA overshoot within +/-25%, must PASS
    # (the old hard 1.0x ceiling would have failed this).
    accepted_high = [{"height": 1, "sim_time_s": 0.0, "miner": "m1",
                       "difficulty": d_eq * 1.01, "interval_s": None, "regime": "n/a"}]
    status, detail = _find_verdict(
        make_verdicts(accepted_high, miners, None, diffcp, windows, {}, 0),
        "end difficulty",
    )
    assert status == "PASS", detail

    # D_end = 0.70 x D_eq: outside +/-25%, must FAIL.
    accepted_low = [{"height": 1, "sim_time_s": 0.0, "miner": "m1",
                      "difficulty": d_eq * 0.70, "interval_s": None, "regime": "n/a"}]
    status, detail = _find_verdict(
        make_verdicts(accepted_low, miners, None, diffcp, windows, {}, 0),
        "end difficulty",
    )
    assert status == "FAIL", detail


# ---------------------------------------------------------------------------
# Integration: real archived run, end to end via the CLI subprocess.
# ---------------------------------------------------------------------------
SPLIT_RUN = REPO_ROOT / "archived_runs" / "20260910_125449_gate_native_split"


@pytest.mark.skipif(not SPLIT_RUN.is_dir(), reason="archived gate_native_split run not present")
def test_cli_end_to_end_on_split_archive(tmp_path):
    out_dir = tmp_path / "native_daa_out"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(SPLIT_RUN), "--out", str(out_dir)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode in (0, 1), result.stderr

    blocks_csv = out_dir / "blocks.csv"
    report_md = out_dir / "report.md"
    assert blocks_csv.is_file()
    assert report_md.is_file()

    lines = blocks_csv.read_text().splitlines()
    assert len(lines) > 100  # header + >100 accepted blocks

    assert "Verdicts" in report_md.read_text()
