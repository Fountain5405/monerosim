import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import check_run as cr
import status as st
import chain

ORACLE = "\n".join(f"monero-n-{i:03d}  decisions=411 skipped=145 ties=1 mismatches={'2' if i == 3 else '0'}" for i in range(12))


def test_parse_oracle():
    n, mm, tb = cr.parse_oracle(ORACLE + "\ntotal: whatever")
    assert (n, mm, tb) == (12, 2, False)
    assert cr.parse_oracle("Traceback (most recent call last)")[2]


def test_gate():
    assert cr.gate(9, 0, False, False, 0)
    assert cr.gate(12, 1, False, False, 0)
    assert cr.gate(12, 0, True, False, 0)
    assert cr.gate(12, 0, False, True, 0)
    assert not cr.gate(12, 0, False, False, 0)
    assert not cr.gate(12, 0, False, True, 3)
    assert cr.gate(12, 0, False, True, 0, reveals=2)
    assert not cr.gate(12, 0, False, True, 0, reveals=0)
    assert not cr.gate(12, 0, False, True, 2, reveals=2)
    assert cr.verdict(cr.gate(12, 0, False, True, 0, 2), False) == "FAIL"
    assert cr.verdict(cr.gate(12, 0, False, True, 0, 0), True) == "WARN"
    assert cr.verdict(cr.gate(12, 0, False, True, 2, 2), False) == "PASS"
    assert cr.verdict(False, True) == "WARN" and cr.verdict(True, True) == "FAIL" and cr.verdict(False, False) == "PASS"


def test_tip_shares():
    assert cr.tip_shares_enabled("      tip_shares: 'true'\n")
    assert not cr.tip_shares_enabled("tip_shares: 'false'")
    assert not cr.tip_shares_enabled("other: 1")


def test_grep_count(tmp_path):
    f = tmp_path / "l"
    f.write_bytes(b"a pooled remote share x tip 0\npooled remote share y tip 1\npooled remote share z tip 0\n")
    assert cr.grep_count([f], b"pooled remote share", b" tip 0") == 2


LOG = ("x\rProgress: 38% — simulated: 02:16:57.543/06:00:00, realtime: 00:11:00, processes failed: 0\r"
       "Progress: 50% — simulated: 03:00:00.000/06:00:00, realtime: 00:15:00, processes failed: 0\r")


def test_progress():
    p = st.parse_progress(LOG)
    assert p["pct"] == 50 and p["sim"] == 10800 and p["total"] == 21600 and p["real"] == 900
    assert p["eta"] == 900
    assert st.parse_progress("nothing") is None


def test_alert():
    assert st.alert_is_bad("WARN: RAM 100% used, swap 1.0 GB")
    assert st.alert_is_bad("WARN: RAM 95% used")
    assert st.alert_is_bad("WARN: RAM 55% used, swap 350.0 GB in use")
    assert not st.alert_is_bad("WARN: RAM 55% used, swap 35.0 GB in use")


def S(runs=None, queue=(), chain=(), go="", halt="", alerts=None):
    return {"runs": dict(runs or {}), "queue": list(queue), "chain": list(chain), "go": go, "halt": halt,
            "alerts": dict(alerts or {})}


def test_diff():
    assert st.diff_state(S(), S()) == []
    assert st.diff_state(S(), S({"a": 3}))[0].startswith("RUN appeared")
    assert st.diff_state(S({"a": 3}), S())[0].startswith("RUN gone")
    assert st.diff_state(S({"a": 38}), S({"a": 42})) == ["PROGRESS a: 42%"]
    assert st.diff_state(S({"a": 41}), S({"a": 49})) == []
    assert st.diff_state(S({"a": 38}), S({"a": 52})) == ["PROGRESS a: 52%"]
    assert st.diff_state(S(queue=["x"]), S(queue=["x", "y"])) == ["queue.log: y"]
    assert st.diff_state(S(chain=[]), S(chain=["c"])) == ["chain.log: c"]
    assert "GO changed" in st.diff_state(S(go="0"), S(go="2"))[0]
    assert "HALT changed" in st.diff_state(S(), S(halt="why"))[0]
    ev = st.diff_state(S(alerts={"a": ["RAM 55%"]}), S(alerts={"a": ["RAM 55%", "RAM 99% used", "RAM 50% swap 10 GB"]}))
    assert ev == ["ALERT a: RAM 99% used"]


def test_chain_decide():
    assert chain.decide(1, 3, False) == "halt"
    assert chain.decide(0, 3, True) == "halt"
    assert chain.decide(0, 1, False) == "launch"
    assert chain.decide(2, 0, False) == "wait"


def test_read_go(tmp_path):
    p = tmp_path / "GO"
    assert chain.read_go(p) == 0
    p.write_text("3\n")
    assert chain.read_go(p) == 3
    p.write_text("junk")
    assert chain.read_go(p) == 0


def test_dedupe_counts(tmp_path):
    L = ["2026-01-01 00:00:01.000 - {p}SelfishMinerAgent[a] - INFO - tip shares: published 3 on x",
         "2026-01-01 00:00:02.000 - {p}SelfishMinerAgent[a] - INFO - tip shares: bridge never reached",
         "2026-01-01 00:00:03.000 - {p}SelfishMinerAgent[a] - INFO - reveal rejected by the bridge",
         "2026-01-01 00:00:04.000 - {p}SelfishMinerAgent[a] - INFO - tip shares: published 2 on y"]
    f = tmp_path / "bash.1.stdout"
    f.write_text("\n".join(l.format(p=p) for l in L for p in ("a - ", "")) + "\n")
    assert len(cr.distinct_lines([f], cr.A3_STR)) == 2
    assert len(cr.distinct_lines([f], cr.UNDELIV_STR)) == 1
    assert len(cr.distinct_lines([f], cr.REJECT_STR)) == 1
    assert cr.count_shares([f]) == 5


def _daemon_log(root, host, last_ts):
    d = root / "shadow.data" / "hosts" / host
    d.mkdir(parents=True)
    (d / "monerod-sim.1000.stdout").write_text(
        "2000-01-01 00:00:01.000\tI starting\n"
        f"{last_ts}\tI HEIGHT 997, difficulty:\t1224\n"
        "\tI continuation line without a timestamp\n")


def test_dead_daemons_flags_a_daemon_whose_log_stops_early(tmp_path):
    # 2026-10-26: OOM-killed honest daemons ran on unnoticed (share 0.858, SPLIT 1813);
    # a daemon whose log ends > 2 h before the run's latest daemon line is dead.
    _daemon_log(tmp_path, "honest-001", "2000-01-01 00:04:50.004")
    _daemon_log(tmp_path, "honest-002", "2000-01-03 23:58:10.000")
    _daemon_log(tmp_path, "relay-001", "2000-01-03 23:59:47.454")
    _daemon_log(tmp_path, "monero-seed-001", "2000-01-03 22:10:00.000")
    assert cr.dead_daemons(tmp_path) == ["honest-001"]


def test_dead_daemons_is_empty_for_a_healthy_run_and_a_run_with_no_daemon_logs(tmp_path):
    _daemon_log(tmp_path, "honest-001", "2000-01-03 23:58:10.000")
    _daemon_log(tmp_path, "attacker-miner", "2000-01-03 23:59:00.000")
    assert cr.dead_daemons(tmp_path) == []
    assert cr.dead_daemons(tmp_path / "nothing") == []


def test_gate_fails_a_run_with_a_dead_daemon():
    assert cr.gate(12, 0, False, True, 5, reveals=5, dead=["honest-001"]) is True
    assert cr.gate(12, 0, False, True, 5, reveals=5, dead=[]) is False
