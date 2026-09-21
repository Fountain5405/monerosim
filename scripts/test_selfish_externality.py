# scripts/test_selfish_externality.py
import math

from scripts.selfish_externality import (
    attacker_runs, canonical_times, detect_selfish_periods, found_time_s,
    hourly_series, msb_scores, reorg_contest_depths, spec,
)


def _found(miner, height, hash_, t):
    return {"miner": miner, "height": height, "hash": hash_,
            "time": f"2000-01-01 {t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}.000"}


def test_found_time_s_parses_sim_clock():
    assert found_time_s(_found("a", 1, "x", 3661)) == 3661.0


def test_canonical_times_matches_by_hash():
    found = [_found("a", 1, "h1", 100), _found("b", 2, "h2", 300)]
    chain = [{"height": 1, "hash": "h1"}, {"height": 2, "hash": "h2"}]
    assert canonical_times(chain, found) == {1: 100.0, 2: 300.0}


def test_canonical_times_fills_unjoined_from_calibrated_chain_timestamp():
    # Block 3 has no miner-log match (relay-found); the bridge dump's block
    # timestamp fills it, calibrated by the joined blocks' offset (here a
    # constant +9000, i.e. unix-scale minus sim-epoch).
    found = [_found("a", 1, "h1", 100), _found("b", 2, "h2", 300)]
    chain = [{"height": 1, "hash": "h1", "timestamp": 9100},
             {"height": 2, "hash": "h2", "timestamp": 9300},
             {"height": 3, "hash": "r3", "timestamp": 9500}]
    assert canonical_times(chain, found) == {1: 100.0, 2: 300.0, 3: 500.0}


def test_canonical_times_skips_fill_without_calibration_points():
    found = [_found("a", 1, "h1", 100)]
    chain = [{"height": 1, "hash": "h1"}, {"height": 2, "hash": "r2", "timestamp": 9999}]
    assert canonical_times(chain, found) == {1: 100.0}


def test_hourly_series_counts_finds_orphans_and_canonical():
    # hour boundaries at 3600s/7200s: c1 in h0; c2+o1 in h1; c3 in h2
    found = [
        _found("a", 1, "c1", 100), _found("a", 2, "c2", 3700),
        _found("b", 2, "o1", 3800),                      # orphaned tie loss
        _found("a", 3, "c3", 7300),
    ]
    canon = {"c1", "c2", "c3"}
    h = hourly_series(found, canon, hours=3)
    assert [x["finds"] for x in h] == [1, 2, 1]
    assert [x["orphans"] for x in h] == [0, 1, 0]
    assert [x["canonical"] for x in h] == [1, 1, 1]
    assert abs(h[0]["orphan_rate"] - 0.0) < 1e-9
    assert abs(h[1]["orphan_rate"] - 0.5) < 1e-9
    # the c1->c2 interval ENDS in h1 (at 3700): 3600s; c2->c3 ends in h2: 3600s
    assert h[0]["mean_interval"] is None
    assert h[1]["mean_interval"] == 3600.0
    assert h[2]["mean_interval"] == 3600.0


def test_detect_selfish_periods_merges_gaps_and_drops_short():
    hourly = [{"hour": i, "finds": 30, "orphans": o, "orphan_rate": 0, "canonical": 30, "mean_interval": 120}
              for i, o in enumerate([0, 3, 0, 4, 4, 2, 0, 0, 5, 5, 0])]
    periods = detect_selfish_periods(hourly)            # defaults tau=2, d=1, g=1
    assert periods == [(1, 1), (3, 5), (8, 9)]          # gap at hour 2 > g_max splits
    assert detect_selfish_periods(hourly, d_min_h=3) == [(3, 5)]


def test_attacker_runs_and_release_signature():
    # canonical: h a a a h h a a ; orphans at heights 2 and 6 (inside runs)
    chain = [{"height": i, "hash": c} for i, c in
             enumerate(["h1", "a1", "a2", "a3", "h2", "h3", "a4", "a5"], start=1)]
    h2m = {"h1": "h", "h2": "h", "h3": "h", "a1": "a", "a2": "a", "a3": "a", "a4": "a", "a5": "a"}
    found = ([{"miner": "h", "height": i, "hash": c, "time": "2000-01-01 00:00:00.000"}
              for i, c in zip(range(1, 9), ["h1", "a1", "a2", "a3", "h2", "h3", "a4", "a5"])]
             + [{"miner": "h", "height": 2, "hash": "x1", "time": "2000-01-01 00:00:00.000"},
                {"miner": "h", "height": 7, "hash": "x2", "time": "2000-01-01 00:00:00.000"}])
    canon = {c["hash"] for c in chain}
    runs = attacker_runs(chain, h2m, {"a"}, found, canon)
    assert [(r["length"], r["orphans"]) for r in runs] == [(3, 1), (2, 1)]
    # release signatures (as the analysis counts them): length>=2 only.
    # The (3,1) run sits on y=x-2 (lead-2 release); the (2,1) run on y=x-1.
    sig2 = sum(1 for r in runs if r["length"] >= 2 and r["orphans"] == r["length"] - 2)
    sig1 = sum(1 for r in runs if r["length"] >= 2 and r["orphans"] == r["length"] - 1)
    assert (sig1, sig2) == (1, 1)


def test_reorg_contest_depths_single_and_multi():
    # contested at h=1 (loser 'b' extends once more at h=2 -> depth 2), and at
    # h=4 a plain depth-1 contest
    found = [
        {"miner": "a", "height": 1, "hash": "a1", "time": "2000-01-01 00:00:00.000"},
        {"miner": "b", "height": 1, "hash": "b1", "time": "2000-01-01 00:00:00.000"},
        {"miner": "b", "height": 2, "hash": "b2", "time": "2000-01-01 00:00:00.000"},
        {"miner": "a", "height": 3, "hash": "a3", "time": "2000-01-01 00:00:00.000"},
        {"miner": "a", "height": 4, "hash": "a4", "time": "2000-01-01 00:00:00.000"},
        {"miner": "b", "height": 4, "hash": "b4", "time": "2000-01-01 00:00:00.000"},
    ]
    canon = {"a1", "a3", "a4"}
    h2m = {e["hash"]: e["miner"] for e in found}
    assert reorg_contest_depths(found, h2m, canon) == [2, 1]


def test_msb_flags_bursty_attacker_not_steady_miner():
    # 30 canonical blocks: attacker takes 12 in 4 bursts of 3 (withholding
    # release signature); honest miners alternate the rest. The attacker's
    # consecutive-win count should z >> 2; a steady miner's should not.
    winners = (["a", "a", "a", "h1", "h2"] * 2 + ["a", "a", "a", "h2", "h1"] * 2
               + ["a", "a", "a", "h1", "h1", "h2", "h2", "h1", "h2", "h1", "h2", "h1", "h2", "h1"])
    chain = [{"height": i, "hash": f"c{i}"} for i in range(len(winners))]
    h2m = {f"c{i}": w for i, w in enumerate(winners)}
    scores = msb_scores(chain, h2m)
    assert scores["a"]["z"] > 2.0
    assert scores["h1"]["z"] < 2.0 and scores["h2"]["z"] < 2.0


def test_spec_rewards_flat_and_punishes_dips():
    assert abs(spec([10, 10, 10, 10]) - 1.0) < 1e-9
    assert spec([10, 10, 10, 0]) < 0.5
    assert spec([]) == 0.0
