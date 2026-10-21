# scripts/test_make_sop_scale_base.py
"""The scale-base generator: relay names, the linear start schedule, which relays
keep logs, and that the matrix runner still sees one attacker and all relays."""
from pathlib import Path

import pytest
import yaml

from scripts.make_sop_scale_base import BASE, build, relay_lines
from scripts.selfish_matrix import _agent_targets

TEXT = BASE.read_text()


def _agents(extra, **kw):
    return yaml.safe_load(build(TEXT, extra, **kw))["agents"]


def test_adds_exactly_the_requested_relays_and_keeps_the_base_hosts():
    base = yaml.safe_load(TEXT)["agents"]
    out = _agents(25)
    assert len(out) == len(base) + 25
    for name, stanza in base.items():
        assert out[name] == stanza


def test_start_times_are_linear_from_the_first_start():
    out = _agents(5, first_start_s=1200, interval_s=10)
    starts = [out[f"scale-000{i}"]["start_time"] for i in range(1, 6)]
    assert starts == ["1200s", "1210s", "1220s", "1230s", "1240s"]


def test_names_are_zero_padded_to_the_count():
    assert "scale-1000" in _agents(1000) and "scale-0001" in _agents(1000)


def test_every_kth_relay_keeps_monitor_logs_and_the_rest_are_quiet():
    out = _agents(100, keep_every=50)
    loud = [n for n, s in out.items() if n.startswith("scale-") and "daemon_options" not in s]
    assert loud == ["scale-0050", "scale-0100"]
    assert out["scale-0001"]["daemon_options"] == {"log-level": 0}


def test_keep_every_zero_silences_all():
    out = _agents(60, keep_every=0)
    assert all("daemon_options" in s for n, s in out.items() if n.startswith("scale-"))


def test_matrix_runner_sees_one_attacker_and_all_new_relays_as_relays():
    cfg = yaml.safe_load(build(TEXT, 40))
    t = _agent_targets(cfg)
    assert t["attacker"] == ["attacker-miner"]
    assert {f"scale-{i:04d}" for i in range(1, 41)} <= set(t["relays"])
    assert not set(t["honest"]) & set(t["relays"])


def test_relay_lines_are_one_line_each():
    assert len(relay_lines(7, 1200, 10, 50)) == 7


@pytest.mark.parametrize("kw", [dict(extra=0), dict(extra=3, interval_s=0), dict(extra=3, first_start_s=-1)])
def test_bad_arguments_raise(kw):
    with pytest.raises(ValueError):
        build(TEXT, **kw)


def test_base_without_the_anchor_raises():
    with pytest.raises(ValueError):
        build("agents:\n  a: {daemon: monerod}\n", 3)
