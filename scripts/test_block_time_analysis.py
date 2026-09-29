"""scripts/block_time_analysis.py: warm-up split, expected exponential counts,
verdict and rendering of the post-run block-time summary."""
import math

from scripts.block_time_analysis import (
    TARGET_S, expected_counts, render_summary, steady_state_start, verdict)


def _events(diffs, gaps):
    """(sim_offset_s, height, difficulty) with the given per-block gaps."""
    t, out = 0.0, [(0.0, 0, diffs[0])]
    for h, (d, g) in enumerate(zip(diffs[1:], gaps), start=1):
        t += g
        out.append((t, h, d))
    return out


def test_steady_state_starts_once_difficulty_reaches_its_late_run_level():
    # Genesis ramp: difficulty climbs from 1, then sits near 3000.
    diffs = [1, 1, 2, 5, 40, 300, 1500, 2400, 2900] + [3000] * 20
    ev = _events(diffs, [60] * (len(diffs) - 1))
    assert steady_state_start(ev) == 7          # first height within 25 % of 3000


def test_snapshot_start_has_no_warm_up():
    diffs = [1080, 1083, 1065, 1067] + [1100] * 20
    ev = _events(diffs, [100] * (len(diffs) - 1))
    assert steady_state_start(ev) == 0


def test_expected_counts_follow_the_exponential_with_the_target_mean():
    edges = [0, 30, 60, math.inf]
    exp = expected_counts(100, edges)
    assert abs(exp[0] - 100 * (1 - math.exp(-30 / TARGET_S))) < 1e-9
    assert abs(sum(exp) - 100) < 1e-9


def test_verdict_passes_inside_the_statistical_band_and_says_which_way_otherwise():
    ok, text = verdict(mean_s=108.0, n=200)     # band 2.5 * 120 / sqrt(200) = 21 s
    assert ok and "consistent" in text
    ok, text = verdict(mean_s=60.0, n=200)
    assert not ok and "faster" in text
    ok, text = verdict(mean_s=200.0, n=200)
    assert not ok and "slower" in text


def test_render_reports_warm_up_separately_and_shows_expected_column():
    diffs = [1, 1, 2, 5, 40, 300, 1500, 2400, 2900] + [3000] * 40
    gaps = [5] * 8 + [120] * 40
    out = render_summary(_events(diffs, gaps), source="monero-miner-001")
    assert "Warm-up" in out and "difficulty ramp" in out
    assert "expected" in out
    assert "Steady state" in out and "consistent with the 2-minute target" in out
    assert "exponential" in out                  # explains why short gaps dominate


def test_find_miner_log_falls_back_to_any_daemon_log(tmp_path):
    # Selfish-mining configs name their miners honest-001 / attacker-*, not
    # miner-*; the summary must still find a log to read.
    from scripts.block_time_analysis import find_miner_log
    d = tmp_path / "daemon_logs" / "monero-honest-001"
    d.mkdir(parents=True)
    (d / "bitmonero.log").write_text("x\n")
    assert find_miner_log(tmp_path) == d / "bitmonero.log"
    m = tmp_path / "daemon_logs" / "monero-miner-001"
    m.mkdir()
    (m / "bitmonero.log").write_text("x\n")
    assert find_miner_log(tmp_path) == m / "bitmonero.log"     # miner-* still preferred
