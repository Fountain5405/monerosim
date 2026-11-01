from scripts import sop_reveal_audit as ra

H = "2000-01-01 01:00:00,000 - attacker-miner - SelfishMinerAgent[attacker-miner] - INFO - param_stubborn: "


def test_reveal_lines_are_grouped_by_fork_and_deduplicated():
    lines = [
        H + "reveal fork=10 a=2 h=1 objects=30 weight=900 honest_weight=600\n",
        H + "reveal fork=10 a=2 h=1 objects=30 weight=900 honest_weight=600\n",   # second handler copy
        H.replace("01:00:00", "01:02:00") + "reveal fork=10 a=3 h=2 objects=40 weight=990 honest_weight=900\n",
        H.replace("01:00:00", "01:05:00") + "reveal fork=12 a=1 h=1 objects=20 weight=700 honest_weight=650\n",
        H.replace("01:00:00", "01:06:00") + "publish fork=12 a=1 h=0 objects=20 weight=700 honest_weight=0\n",
        "2000-01-01 01:07:00,000 - SelfishMinerAgent[attacker-miner] - INFO - param_stubborn: reveal fork=99 a=1 h=1 objects=1 weight=1 honest_weight=0\n",
    ]
    s = ra.summarize(ra.parse(lines))
    assert s["reveal_lines"] == 3
    assert s["distinct_forks"] == 2
    assert s["per_fork"] == {1: 1, 2: 1}
    assert dict(s["first_ah"]) == {(2, 1): 1, (1, 1): 1}
    assert dict(s["repeat_ah"]) == {(3, 2): 1}
    assert s["forks_also_published"] == 1 and s["publish_lines"] == 1
