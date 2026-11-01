import pytest



def _learned(ts, obs, action):
    return (f"2000-01-01 {ts},000 - attacker-miner - SelfishMinerAgent[attacker-miner] - DEBUG - "
            f"learned: obs={obs} key={obs} action={action} stored=True\n")


def test_sim_histograms_tally_a_sim_log_like_the_model():
    from scripts.sop_decision_hist import sim_histograms
    lines = [
        _learned("00:00:00", "(1, 20, 0, 0, 0, 0, 0)", "publish"),
        _learned("01:00:00", "(0, -9, 0, 12, 1, 9, 0)", "hold"),       # race start, pa 12
        _learned("01:00:00", "(0, -9, 0, 12, 1, 9, 0)", "hold"),       # the second handler's copy: not a new line
        _learned("01:00:05", "(0, -9, 0, 12, 1, 9, 0)", "hold"),       # a later poll of the same state
        _learned("01:05:00", "(2, 1, 32, 0, 3, 32, 0)", "reveal"),     # suppressed: no release line at this time
        _learned("01:10:00", "(2, 4, 32, 0, 3, 32, 0)", "reveal"),
        "2000-01-01 01:10:00,000 - attacker-miner - SelfishMinerAgent[attacker-miner] - INFO - "
        "param_stubborn: reveal fork=40 a=2 h=3 objects=40 weight=3000 honest_weight=2900\n",
        _learned("01:20:00", "(0, -40, 0, 0, 1, 0, 0)", "give_up"),    # race start and give-up at once
        _learned("02:00:00", "(2, -30, 20, 0, 2, 32, 0)", "give_up"),
        _learned("03:00:00", "(1, 18, 0, 0, 0, 0, 0)", "publish"),
    ]
    h = sim_histograms(lines, G=6, found=2000)
    assert h["hours"] == 3.0
    per = 72 / 3.0
    assert h["per72h"]["race_starts"] == 2 * per
    assert h["per72h"]["reveals"] == 1 * per
    assert h["per72h"]["publishes"] == 2 * per
    assert h["per72h"]["give_ups_no_block"] == 1 * per
    assert h["per72h"]["give_ups_with_blocks"] == 1 * per
    assert h["race_starts"]["pa"]["p50"] in (0, 12)
    assert h["reveal_ah"] == {"(2, 3)": 1}
    assert h["per72h"]["reveal_decisions"] == 2 * per        # the suppressed decision is not a reveal
    assert h["per_1000_found"]["reveals"] == 0.5             # 1 reveal in 2,000 found blocks
    assert h["per_1000_found"]["publishes"] == 1.0


def test_model_histograms_report_rates_per_found_block():
    from scripts.sop_decision_hist import histograms
    h = histograms(0.47, 5, 1, {"G": 6, "L": 1, "M": 1, "R": 1, "Z": 1})
    assert 3000 < h["found"] < 4200                           # ~720 found blocks a model day
    for k, v in h["per72h"].items():
        assert h["per_1000_found"][k] == pytest.approx(v * (5 / 3.0) / h["found"] * 1000)


def test_model_histograms_take_the_window_depth():
    from scripts.sop_decision_hist import histograms
    knobs = {"G": 4, "L": 1, "M": 1, "R": 1, "Z": 1}
    k3 = histograms(0.47, 10, 1, knobs, perish=True)
    k6 = histograms(0.47, 10, 1, knobs, perish=True, K=6, w=16)
    assert (k3["window_obs"], k6["window_obs"]) == (32, 80)
    assert k6["per_1000_found"]["reveals"] < 0.7 * k3["per_1000_found"]["reveals"]
