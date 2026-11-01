"""Tests for studies/antiproxy/analysis/mainnet/monitor_series.py. No network access.

Moved out of analysis/mainnet/test_mainnet_tools.py by the 2026-11-01
reorganization: monitor_series.py belongs to the antiproxy study, while
analysis/mainnet/poll_node.py, whose tick builders the test uses, stays in core.
"""
import gzip
import json
import sys
from pathlib import Path

MAINNET_DIR = Path(__file__).resolve().parent  # holds monitor_series.py
CORE_MAINNET_DIR = Path(__file__).resolve().parents[4] / "analysis" / "mainnet"

sys.path.insert(0, str(CORE_MAINNET_DIR))
sys.path.insert(0, str(MAINNET_DIR))
import poll_node  # noqa: E402


class TestMonitorSeries:
    def test_series(self, tmp_path):
        import monitor_series as ms
        mon = tmp_path / "mon"
        mon.mkdir()
        (tmp_path / "spy.txt").write_text("# spy\n192.0.2.0/24\n\n")

        def pe(host, age, t):
            return {"host": host, "ip": 0, "port": 18080, "last_seen": t - age}
        t1, t2, t3 = 10000.0, 10600.0, 11200.0
        w1 = [pe("192.0.2.1", 100, t1), pe("192.0.2.2", 200, t1),
              pe("198.51.100.1", 1000, t1), pe("198.51.100.2", 3000, t1)]
        w3 = [pe("192.0.2.5", 10, t3), pe("198.51.100.9", 20, t3),
              pe("203.0.113.1", 30, t3)]
        ticks = [poll_node.build_peerlist_tick(t1, w1, [{"host": "192.0.2.3"}]),
                 {"ts": t2, "unchanged": True, "hash": "h"},
                 poll_node.build_peerlist_tick(t3, w3, [])]
        with gzip.open(mon / "peerlist-19700101.jsonl.gz", "wt") as f:
            for t in ticks:
                f.write(json.dumps(t) + "\n")
        conns = [
            poll_node.build_connections_tick(10100.0, {}, [
                {"host": "192.0.2.1", "incoming": True},
                {"host": "198.51.100.1", "incoming": False}]),
            poll_node.build_connections_tick(11100.0, {}, [
                {"host": "192.0.2.1", "incoming": True},
                {"host": "192.0.2.2", "incoming": True}]),
        ]
        (mon / "connections-19700101.jsonl").write_text(
            "".join(json.dumps(c) + "\n" for c in conns))
        dials = [(10000.0, "192.0.2.1"), (10100.0, "192.0.2.4"), (11000.0, "198.51.100.3")]
        (mon / "dials-19700101.jsonl").write_text(
            "".join(json.dumps({"ts": t, "ip": ip, "line": "l"}) + "\n" for t, ip in dials))

        csvp, jsp = tmp_path / "s.csv", tmp_path / "s.json"
        import subprocess
        subprocess.run([sys.executable, str(MAINNET_DIR / "monitor_series.py"), str(mon),
                        "--spy-cidrs", str(tmp_path / "spy.txt"),
                        "--csv", str(csvp), "--json", str(jsp)], check=True)
        import csv as _csv
        rows = list(_csv.DictReader(open(csvp)))
        assert len(rows) == 3
        assert [r["spy_white"] for r in rows] == ["2", "2", "1"]
        assert [r["newest20_spy"] for r in rows] == ["1", "1", "1"]
        assert [r["spy_gray"] for r in rows] == ["1", "1", "0"]
        assert rows[0]["n_in"] == "" and rows[1]["n_in"] == "1" and rows[2]["spy_in"] == "2"
        summ = json.loads(jsp.read_text())
        assert summ["ticks"] == 3
        assert summ["white_size_med"] == 4
        assert summ["spy_white_share_med"] == 0.5
        assert summ["spy_age_med_s_med"] == 150
        assert summ["n_in_med"] == 1.5
        assert summ["dials_per_hour"] == {"total_med": 1.5, "spy_med": 1.0, "hours": 2}
        blob = csvp.read_text() + jsp.read_text()
        for needle in ("192.0.2", "198.51.100", "203.0.113"):
            assert needle not in blob
        assert ms.ts_to_unix(5) == 5.0
