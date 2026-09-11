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
    hashes_in,
    active_hashrate,
    monerod_window,
    theory_difficulty_at_time,
    expected_blocks,
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
# monerod difficulty-window theory: hashes_in / active_hashrate /
# monerod_window / theory_difficulty_at_time / expected_blocks
# ---------------------------------------------------------------------------
def test_hashes_in():
    miners = {"a": {"hashrate": 100.0, "start_s": 0.0}, "b": {"hashrate": 200.0, "start_s": 14400.0}}
    assert hashes_in(miners, 0, 36000) == pytest.approx(100 * 36000 + 200 * 21600)
    assert hashes_in(miners, 0, 10000) == pytest.approx(100 * 10000)
    assert hashes_in(miners, 20000, 10000) == 0.0


def test_active_hashrate():
    miners = {"a": {"hashrate": 100.0, "start_s": 0.0}, "b": {"hashrate": 200.0, "start_s": 14400.0}}
    assert active_hashrate(miners, 0) == pytest.approx(100.0)
    assert active_hashrate(miners, 14399) == pytest.approx(100.0)
    assert active_hashrate(miners, 14400) == pytest.approx(300.0)


def _height_list(n, spacing=120.0):
    """N synthetic blocks at heights 1..N, spaced `spacing` seconds apart
    (only "height" and "sim_time_s" matter to monerod_window)."""
    return [{"height": i + 1, "sim_time_s": (i + 1) * spacing} for i in range(n)]


@pytest.mark.parametrize("n,h,expected", [
    (50, 51, (0, 50)),
    (700, 701, (50, 650)),
    (800, 801, (125, 725)),
])
def test_monerod_window(n, h, expected):
    accepted = _height_list(n)
    assert monerod_window(accepted, h) == expected


def _step_scenario_chain():
    """Reference late-joiner scenario: miner 'a' at 100 h/s from t=0, miner
    'b' joins at t=14400 (4h) with 200 h/s. Blocks every 120s pre-join and
    every 60s post-join (both consistent with 120 * active hashrate at
    equilibrium) so the block count stays under 600 for the whole 10h run.
    """
    accepted = []
    h, t = 1, 120.0
    while t <= 14400.0 + 1e-9:
        accepted.append({"height": h, "sim_time_s": t, "miner": "a",
                          "difficulty": 12000, "interval_s": 120.0, "regime": "pre"})
        h += 1
        t += 120.0
    t = 14460.0
    while t <= 36000.0 + 1e-9:
        accepted.append({"height": h, "sim_time_s": t, "miner": "b",
                          "difficulty": 20000, "interval_s": 60.0, "regime": "post"})
        h += 1
        t += 60.0
    miners = {"a": {"hashrate": 100.0, "start_s": 0.0}, "b": {"hashrate": 200.0, "start_s": 14400.0}}
    return accepted, miners


def test_theory_difficulty_at_time_constant_hashrate():
    accepted = _height_list(300)  # 300 * 120s = 36000s
    miners = {"a": {"hashrate": 100.0, "start_s": 0.0}}
    assert theory_difficulty_at_time(accepted, miners, 36000.0) == pytest.approx(12000.0, rel=0.01)


def test_theory_difficulty_at_time_step_scenario():
    accepted, miners = _step_scenario_chain()
    assert theory_difficulty_at_time(accepted, miners, 18000.0) == pytest.approx(16800.0, rel=0.01)
    assert theory_difficulty_at_time(accepted, miners, 36000.0) == pytest.approx(26400.0, rel=0.01)


def test_expected_blocks_constant_hashrate():
    accepted = _height_list(300)  # 300 * 120s = 36000s
    miners = {"a": {"hashrate": 100.0, "start_s": 0.0}}
    assert expected_blocks(accepted, miners, 28800.0, 36000.0) == pytest.approx(60.0, rel=0.02)


# ---------------------------------------------------------------------------
# end-difficulty verdict: +/-25% tolerance, not a hard 1.0x ceiling
# ---------------------------------------------------------------------------
def _find_verdict(verdicts, name_substr):
    for name, status, detail in verdicts:
        if name_substr in name:
            return status, detail
    raise AssertionError(f"no verdict matched {name_substr!r}")


def test_end_difficulty_verdict_uses_theory_centre_not_old_band():
    # The verdict's tolerance band is still +/-25%, but its centre is now
    # monerod's own difficulty-window theory (theory_end, computed below
    # from the step scenario), not the fixed post-join equilibrium D_post_eq
    # used previously. 40000 sits inside the *old* band ([0.75, 1.25] x
    # d_post_eq=36000 -> [27000, 45000]) but outside the new theory band,
    # so it now FAILs; that is the point of the model change.
    accepted, miners = _step_scenario_chain()
    theory_end = theory_difficulty_at_time(accepted, miners, accepted[-1]["sim_time_s"])
    assert theory_end == pytest.approx(26400.0, rel=0.01)
    diffcp = {"checkpoints": {"at_end_theory": theory_end}, "d_pre_eq": 12000.0, "d_post_eq": 36000.0}
    windows = {"pre_h1_4": [], "first20": None, "last2h": [], "run_end": accepted[-1]["sim_time_s"]}

    accepted_pass = accepted[:-1] + [dict(accepted[-1], difficulty=26400)]
    status, detail = _find_verdict(
        make_verdicts(accepted_pass, miners, None, diffcp, windows, {}, 0),
        "end difficulty",
    )
    assert status == "PASS", detail

    # 40000 > 1.25 x 26400, even though it is inside the old [27000, 45000] band.
    accepted_fail = accepted[:-1] + [dict(accepted[-1], difficulty=40000)]
    status, detail = _find_verdict(
        make_verdicts(accepted_fail, miners, None, diffcp, windows, {}, 0),
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
