"""Tests for analysis/mainnet/*.py. No network access.

Fixtures in analysis/mainnet/fixtures/ are one real get_info / get_connections
/ get_peer_list response captured from the live mainnet node given in the
task, with peer IPs anonymised to 10.x addresses.
"""
import gzip
import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agents import levin_lib as L  # noqa: E402

MAINNET_DIR = Path(__file__).resolve().parent
FIXTURES = MAINNET_DIR / "fixtures"

sys.path.insert(0, str(MAINNET_DIR))
import poll_node  # noqa: E402
import crawl  # noqa: E402
import enrich_asn  # noqa: E402
import summarize  # noqa: E402
import netscan_summarize  # noqa: E402


def load_fixture(name):
    with open(FIXTURES / name) as f:
        return json.load(f)


# ===== poll_node =============================================================
class TestPollNodeParsing:
    def test_parse_duration(self):
        assert poll_node.parse_duration("7d") == 7 * 86400
        assert poll_node.parse_duration("12h") == 12 * 3600
        assert poll_node.parse_duration("30m") == 30 * 60
        assert poll_node.parse_duration("90s") == 90
        assert poll_node.parse_duration("45") == 45.0

    def test_build_connections_tick_from_fixture(self):
        info = load_fixture("get_info.json")
        conns = load_fixture("get_connections.json")["connections"]
        tick = poll_node.build_connections_tick(1234.5, info, conns)
        assert tick["ts"] == 1234.5
        assert tick["error"] is None
        assert tick["get_info"]["height"] == info["height"]
        assert len(tick["connections"]) == len(conns)

    def test_connection_counts_from_fixture(self):
        conns = load_fixture("get_connections.json")["connections"]
        inc, out = poll_node.connection_counts(conns)
        assert inc + out == len(conns)
        assert inc == sum(1 for c in conns if c["incoming"])

    def test_median_live_time_from_fixture(self):
        conns = load_fixture("get_connections.json")["connections"]
        med = poll_node.median_live_time(conns)
        assert med is not None
        assert med >= 0

    def test_hourly_summary_line(self):
        conns = [{"incoming": True, "live_time": 10}, {"incoming": False, "live_time": 20}]
        line = poll_node.hourly_summary_line([None, conns])
        assert "last_in=1" in line
        assert "last_out=1" in line
        assert poll_node.hourly_summary_line([None, None]) is None

    def test_build_peerlist_tick_from_fixture(self):
        peers = load_fixture("get_peer_list.json")
        tick = poll_node.build_peerlist_tick(1.0, peers["white_list"], peers["gray_list"])
        assert len(tick["white_list"]) == len(peers["white_list"])
        assert len(tick["gray_list"]) == len(peers["gray_list"])
        assert tick["error"] is None

    def test_error_tick_has_null_payload(self):
        tick = poll_node.build_connections_tick(1.0, error="boom")
        assert tick["get_info"] is None
        assert tick["connections"] is None
        assert tick["error"] == "boom"


class TestPollNodeRollover:
    def test_gzip_and_remove_roundtrip(self, tmp_path):
        f = tmp_path / "connections-20260101.jsonl"
        f.write_text('{"a":1}\n{"a":2}\n')
        poll_node.gzip_and_remove(f)
        assert not f.exists()
        gz = tmp_path / "connections-20260101.jsonl.gz"
        assert gz.exists()
        with gzip.open(gz, "rt") as fh:
            assert fh.read() == '{"a":1}\n{"a":2}\n'

    def test_rollover_if_needed_only_on_date_change(self, tmp_path):
        f = tmp_path / "connections-20260101.jsonl"
        f.write_text("x\n")
        poll_node.rollover_if_needed(tmp_path, "connections", "20260101", "20260101")
        assert f.exists()  # same date: no-op
        poll_node.rollover_if_needed(tmp_path, "connections", "20260101", "20260102")
        assert not f.exists()
        assert (tmp_path / "connections-20260101.jsonl.gz").exists()

    def test_rollover_if_needed_missing_file_is_noop(self, tmp_path):
        # already-rolled-over or never-created file: must not raise
        poll_node.rollover_if_needed(tmp_path, "connections", "20260101", "20260102")


class TestPollerRunLoop:
    def test_run_writes_ticks_and_respects_duration(self, tmp_path, monkeypatch):
        clock = [1000.0]

        def now_fn():
            return clock[0]

        def sleep_fn(s):
            clock[0] += s

        monkeypatch.setattr(poll_node, "rpc_json",
                            lambda url, method, timeout=10:
                            {"height": 1} if method == "get_info" else {"connections": []})
        monkeypatch.setattr(poll_node, "rpc_plain",
                            lambda url, path, timeout=10: {"white_list": [], "gray_list": []})

        poller = poll_node.Poller("http://x", tmp_path, interval=10, peerlist_interval=20,
                                  duration=35, sleep_fn=sleep_fn, now_fn=now_fn)
        poller.run()

        conn_files = list(tmp_path.glob("connections-*.jsonl"))
        assert len(conn_files) == 1
        conn_lines = conn_files[0].read_text().strip().splitlines()
        assert len(conn_lines) == 4  # ticks at t=1000,1010,1020,1030

        peer_files = list(tmp_path.glob("peerlist-*.jsonl"))
        assert len(peer_files) == 1
        peer_lines = peer_files[0].read_text().strip().splitlines()
        assert len(peer_lines) == 2  # peerlist ticks at t=1000, t=1020

        assert (tmp_path / "poll_node.pid").exists()

    def test_run_tolerates_rpc_errors(self, tmp_path, monkeypatch):
        clock = [0.0]
        monkeypatch.setattr(poll_node, "rpc_json",
                            lambda url, method, timeout=10: (_ for _ in ()).throw(RuntimeError("down")))
        monkeypatch.setattr(poll_node, "rpc_plain",
                            lambda url, path, timeout=10: {"white_list": [], "gray_list": []})
        poller = poll_node.Poller("http://x", tmp_path, interval=5, peerlist_interval=100,
                                  duration=6, sleep_fn=lambda s: clock.__setitem__(0, clock[0] + s),
                                  now_fn=lambda: clock[0])
        poller.run()  # must not raise
        lines = (tmp_path / ("connections-%s.jsonl" % poll_node.utc_date_str(0))).read_text().strip().splitlines()
        assert len(lines) == 2
        rec = json.loads(lines[0])
        assert rec["error"] == "down"
        assert rec["get_info"] is None


# ===== crawl ==================================================================
class FakeSock:
    def close(self):
        pass


class TestCrawlProbing:
    def test_classify_exception(self):
        assert crawl.classify_exception(socket.timeout()) == "timeout"
        assert crawl.classify_exception(ConnectionRefusedError()) == "refused"
        assert crawl.classify_exception(OSError("no route")) == "unreachable"
        assert crawl.classify_exception(ValueError("garbage")) == "protocol"

    def test_probe_peer_success_records_mismatch_and_peerlist(self, monkeypatch):
        entry = L.peerlist_entry("5.6.7.8", 18080, peer_id=42, last_seen=100)
        # round-trip it through the real (de)serializer so the shape matches
        # what request_response would hand back after a genuine parse().
        parsed_entry = L.parse(L.serialize({"e": ("arr_obj", [entry])}))["e"][0]

        responses = iter([
            {
                "node_data": {"peer_id": 111, "my_port": 18080, "support_flags": 1},
                "payload_data": {"current_height": 12345, "top_id": b"\x00" * 32},
                "local_peerlist_new": [parsed_entry],
            },
            {"status": b"OK", "peer_id": 222},
        ])
        monkeypatch.setattr(crawl.L, "connect", lambda ip, port, timeout=8: FakeSock())
        monkeypatch.setattr(crawl.L, "request_response",
                            lambda sock, command, section: next(responses))

        rec = crawl.probe_peer("1.2.3.4", 18080, L.NETWORK_ID_MAINNET, 999,
                               100, 1, 0, b"\x00" * 32, timeout=1)

        assert rec["reachable"] is True
        assert rec["error_class"] is None
        assert rec["peer_id"] == "%016x" % 111
        assert rec["ping_peer_id"] == "%016x" % 222
        assert rec["peer_id_mismatch"] is True
        assert rec["support_flags"] == {"present": True, "value": 1}
        assert rec["top_height"] == 12345
        assert rec["peerlist_size"] == 1
        assert rec["peerlist"] == ["5.6.7.8:18080"]

    def test_probe_peer_connect_failure_sets_error_class(self, monkeypatch):
        def raise_refused(ip, port, timeout=8):
            raise ConnectionRefusedError()

        monkeypatch.setattr(crawl.L, "connect", raise_refused)
        rec = crawl.probe_peer("1.2.3.4", 18080, L.NETWORK_ID_MAINNET, 999,
                               100, 1, 0, b"\x00" * 32, timeout=1)
        assert rec["reachable"] is False
        assert rec["error_class"] == "refused"

    def test_probe_peer_absent_support_flags(self, monkeypatch):
        responses = iter([
            {"node_data": {"peer_id": 1}, "payload_data": {"current_height": 1},
            "local_peerlist_new": []},
            {"status": b"OK", "peer_id": 1},
        ])
        monkeypatch.setattr(crawl.L, "connect", lambda ip, port, timeout=8: FakeSock())
        monkeypatch.setattr(crawl.L, "request_response",
                            lambda sock, command, section: next(responses))
        rec = crawl.probe_peer("1.2.3.4", 18080, L.NETWORK_ID_MAINNET, 999,
                               100, 1, 0, b"\x00" * 32, timeout=1)
        assert rec["support_flags"] == {"present": False, "value": None}
        assert rec["peer_id_mismatch"] is False

    def test_normalize_ip_strips_ipv6_mapped_prefix(self):
        assert crawl.normalize_ip("::ffff:20.119.64.88") == "20.119.64.88"
        assert crawl.normalize_ip("20.119.64.88") == "20.119.64.88"

    def test_peerlist_targets_parses_ip_port(self):
        rec = {"peerlist": ["9.9.9.9:18080", "1.1.1.1:12345"]}
        assert list(crawl._peerlist_targets(rec)) == [("9.9.9.9", 18080), ("1.1.1.1", 12345)]


# ===== levin_lib additions ====================================================
class TestLevinLibHelpers:
    def test_ip_from_m_ip_roundtrip(self):
        m_ip = L.ipv4_m_ip("181.0.0.10")
        assert L.ip_from_m_ip(m_ip) == "181.0.0.10"

    def test_parse_network_address_ipv4(self):
        entry = L.network_address_ipv4("2.3.4.5", 18080)
        parsed = L.parse(L.serialize({"adr": entry}))["adr"]
        ip, port = L.parse_network_address(parsed)
        assert (ip, port) == ("2.3.4.5", 18080)

    def test_parse_peerlist(self):
        entries = [L.peerlist_entry("1.2.3.4", 18080, peer_id=7, last_seen=99),
                  L.peerlist_entry("5.6.7.8", 18081, peer_id=8, last_seen=100)]
        blob = L.serialize({"local_peerlist_new": ("arr_obj", entries)})
        parsed = L.parse(blob)["local_peerlist_new"]
        out = L.parse_peerlist(parsed)
        assert [(p["ip"], p["port"]) for p in out] == [("1.2.3.4", 18080), ("5.6.7.8", 18081)]
        assert out[0]["peer_id"] == 7

    def test_handshake_and_ping_request_round_trip(self):
        req = L.handshake_request(L.NETWORK_ID_MAINNET, 0, 555, 10, 20, b"\x01" * 32)
        blob = L.serialize(req)
        parsed = L.parse(blob)
        assert parsed["node_data"]["peer_id"] == 555
        assert parsed["payload_data"]["current_height"] == 10
        assert L.ping_request() == {}


# ===== enrich_asn ============================================================
class TestEnrichAsn:
    CYMRU_SAMPLE = (
        "AS      | IP               | BGP Prefix          | CC | Registry | Allocated  | AS Name\n"
        "15169   | 8.8.8.8          | 8.8.8.0/24          | US | arin     | 1992-12-01 | GOOGLE, US\n"
        "13335   | 1.1.1.1          | 1.1.1.0/24          | US | apnic    | 2011-08-11 | CLOUDFLARENET, US\n"
    )

    def test_parse_cymru_response(self):
        out = enrich_asn.parse_cymru_response(self.CYMRU_SAMPLE)
        assert out["8.8.8.8"] == {"ip": "8.8.8.8", "asn": "15169", "as_name": "GOOGLE, US",
                                  "cc": "US", "prefix": "8.8.8.0/24"}
        assert out["1.1.1.1"]["asn"] == "13335"
        assert "AS" not in out  # header row skipped

    def test_unique_ips_preserves_first_seen_order(self, tmp_path):
        p = tmp_path / "nodes.jsonl"
        p.write_text('{"ip":"1.1.1.1"}\n{"ip":"2.2.2.2"}\n{"ip":"1.1.1.1"}\n')
        assert enrich_asn.unique_ips(p) == ["1.1.1.1", "2.2.2.2"]

    def test_enrich_caches_and_skips_known_ips(self, tmp_path):
        nodes = tmp_path / "nodes.jsonl"
        nodes.write_text('{"ip":"8.8.8.8"}\n{"ip":"1.1.1.1"}\n')
        calls = []

        def fake_query(ips, timeout=15):
            calls.append(list(ips))
            return self.CYMRU_SAMPLE

        out = tmp_path / "asn.jsonl"
        total, missing = enrich_asn.enrich(nodes, out, timeout=1, query_fn=fake_query)
        assert (total, missing) == (2, 2)
        assert len(calls) == 1

        # second run: everything is cached, no query issued
        total2, missing2 = enrich_asn.enrich(nodes, out, timeout=1, query_fn=fake_query)
        assert (total2, missing2) == (2, 0)
        assert len(calls) == 1

        lines = [json.loads(l) for l in out.read_text().strip().splitlines()]
        assert lines[0]["asn"] == "15169"


# ===== summarize ==============================================================
class TestBanListMatching:
    def test_load_and_match(self):
        nets = summarize.load_ban_list(FIXTURES / "ban_list.txt")
        assert summarize.ip_in_networks("10.0.0.5", nets) is True   # bare IP
        assert summarize.ip_in_networks("10.0.1.50", nets) is True  # inside CIDR
        assert summarize.ip_in_networks("10.0.1.255", nets) is True
        assert summarize.ip_in_networks("10.0.2.10", nets) is True
        assert summarize.ip_in_networks("10.0.2.11", nets) is False
        assert summarize.ip_in_networks("10.9.9.9", nets) is False
        assert summarize.ip_in_networks("not-an-ip", nets) is False


class TestSpyLabelOverlap:
    NODES = [
        {"ip": "10.0.0.5", "reachable": True, "peer_id_mismatch": False,
         "support_flags": {"present": True}},
        {"ip": "10.0.1.50", "reachable": True, "peer_id_mismatch": True,
         "support_flags": {"present": True}},
        {"ip": "10.0.2.10", "reachable": True, "peer_id_mismatch": False,
         "support_flags": {"present": False}},
        {"ip": "10.0.9.9", "reachable": True, "peer_id_mismatch": False,
         "support_flags": {"present": True}},
        {"ip": "10.0.9.10", "reachable": False, "peer_id_mismatch": False,
         "support_flags": {"present": True}},
        {"ip": "10.0.9.11", "reachable": True, "peer_id_mismatch": True,
         "support_flags": {"present": False}},
    ]

    def test_labels_exclude_unreachable(self):
        nets = summarize.load_ban_list(FIXTURES / "ban_list.txt")
        labels = summarize.compute_spy_labels(self.NODES, nets)
        assert len(labels) == 5  # the unreachable node is dropped

    def test_summary_shares(self):
        nets = summarize.load_ban_list(FIXTURES / "ban_list.txt")
        labels = summarize.compute_spy_labels(self.NODES, nets)
        s = summarize.spy_label_summary(labels)
        assert s["total_reachable"] == 5
        assert s["ban_share"] == pytest.approx(0.6)
        assert s["mismatch_share"] == pytest.approx(0.4)
        assert s["flags_absent_share"] == pytest.approx(0.4)
        assert s["ban_and_mismatch_share"] == pytest.approx(0.2)
        assert s["ban_and_flags_absent_share"] == pytest.approx(0.2)
        assert s["mismatch_and_flags_absent_share"] == pytest.approx(0.2)
        assert s["all_three_share"] == pytest.approx(0.0)
        assert s["any_share"] == pytest.approx(0.8)


class TestConcentration:
    def test_spy_concentration(self):
        ips = ["10.0.0.5", "10.0.1.50", "10.0.2.10"]
        asn_map = {
            "10.0.0.5": {"ip": "10.0.0.5", "asn": "1234", "as_name": "X", "cc": "US"},
            "10.0.1.50": {"ip": "10.0.1.50", "asn": "1234", "as_name": "X", "cc": "US"},
            "10.0.2.10": {"ip": "10.0.2.10", "asn": "5678", "as_name": "Y", "cc": "DE"},
        }
        c = summarize.concentration(ips, asn_map)
        assert c["distinct_24s"] == 3
        by_asn = {a["asn"]: a for a in c["top_asns"]}
        assert by_asn["1234"]["count"] == 2
        assert by_asn["1234"]["share"] == pytest.approx(2 / 3)
        assert by_asn["5678"]["count"] == 1

    def test_top_prefix_share(self):
        ips = []
        for g in (0, 1):
            ips += ["10.0.%d.%d" % (g, i) for i in range(1, 6)]  # 5 each, dense
        for g in range(2, 10):
            ips.append("10.0.%d.1" % g)  # 1 each, sparse
        result = summarize.top_prefix_share(ips, top_fraction=0.12)
        assert result["distinct_24s"] == 10
        assert result["n_top_24s"] == 2
        assert result["top_share"] == pytest.approx(10 / 18)


class TestConnectionDuration:
    TICKS = [
        {"ts": 0, "connections": [
            {"connection_id": "A", "incoming": True, "live_time": 10},
            {"connection_id": "B", "incoming": False, "live_time": 5},
        ]},
        {"ts": 60, "connections": [
            {"connection_id": "A", "incoming": True, "live_time": 70},
            {"connection_id": "C", "incoming": False, "live_time": 1},
        ]},
        {"ts": 120, "connections": []},
        {"ts": 180, "connections": None},
    ]

    def test_derive_connection_durations(self):
        out_durs, in_durs = summarize.derive_connection_durations(self.TICKS)
        assert sorted(out_durs) == [1, 5]
        assert in_durs == [70]

    def test_duration_stats(self):
        stats = summarize.duration_stats([5, 1])
        assert stats["median"] == 3
        assert stats["over_6h_share"] == 0.0
        assert summarize.duration_stats([])["n"] == 0

    def test_live_time_snapshot_pools_all_ticks(self):
        in_stats, out_stats = summarize.live_time_snapshot(self.TICKS)
        assert in_stats["n"] == 2   # A appears twice (10, 70)
        assert out_stats["n"] == 2  # B once, C once
        assert in_stats["mean"] == pytest.approx(40)


class TestDegreeAndHubMetrics:
    # h1, h2 are hubs; a,b,c,d,e are leaves. See test docstring for hand-worked
    # expected degrees.
    EDGES = [
        ("h1", "a"), ("h1", "b"), ("h1", "c"), ("h1", "d"), ("h1", "h2"),
        ("h2", "a"), ("h2", "b"), ("h2", "e"),
        ("a", "h1"), ("b", "h1"), ("c", "h1"), ("d", "h1"),
        ("e", "h2"),
    ]

    def test_degree_distribution(self):
        degree = summarize.degree_distribution(self.EDGES)
        assert degree == {"h1": 9, "h2": 5, "a": 3, "b": 3, "c": 2, "d": 2, "e": 2}

    def test_top_share_of_edges(self):
        degree = summarize.degree_distribution(self.EDGES)
        result = summarize.top_share_of_edges(degree, top_fraction=0.132)
        assert result["n_nodes"] == 7
        assert result["n_top"] == 1
        assert result["top_share"] == pytest.approx(9 / 26)

    def test_hub_coverage(self):
        degree = summarize.degree_distribution(self.EDGES)
        result = summarize.hub_coverage(self.EDGES, degree, top_n=2)
        assert result["covered"] == 5
        assert result["total_nodes"] == 5
        assert result["coverage"] == pytest.approx(1.0)


class TestLoadersAndReport:
    def test_load_nodes_and_edges(self, tmp_path):
        (tmp_path / "nodes.jsonl").write_text('{"ip":"1.1.1.1","reachable":true}\n')
        with gzip.open(tmp_path / "edges.jsonl.gz", "wt") as f:
            f.write(json.dumps({"src": "1.1.1.1:18080", "dst": "2.2.2.2:18080"}) + "\n")
        nodes = summarize.load_nodes(tmp_path)
        edges = summarize.load_edges(tmp_path)
        assert nodes == [{"ip": "1.1.1.1", "reachable": True}]
        assert edges == [("1.1.1.1:18080", "2.2.2.2:18080")]

    def test_poll_loaders_read_plain_and_gz(self, tmp_path):
        (tmp_path / "connections-20260101.jsonl").write_text('{"ts":1,"connections":[]}\n')
        with gzip.open(tmp_path / "connections-20260102.jsonl.gz", "wt") as f:
            f.write(json.dumps({"ts": 2, "connections": []}) + "\n")
        ticks = summarize.load_poll_connections(tmp_path)
        assert [t["ts"] for t in ticks] == [1, 2]

    def test_build_report_end_to_end_smoke(self, tmp_path):
        (tmp_path / "nodes.jsonl").write_text(
            "\n".join(json.dumps(n) for n in TestSpyLabelOverlap.NODES) + "\n")
        with gzip.open(tmp_path / "edges.jsonl.gz", "wt") as f:
            for src, dst in TestDegreeAndHubMetrics.EDGES:
                f.write(json.dumps({"src": src, "dst": dst}) + "\n")
        nodes = summarize.load_nodes(tmp_path)
        edges = summarize.load_edges(tmp_path)
        nets = summarize.load_ban_list(FIXTURES / "ban_list.txt")
        report = summarize.build_report(nodes, edges, TestConnectionDuration.TICKS, [],
                                        nets, {})
        assert report["reachable_nodes"] == 5
        assert report["peerlist_adjacency_degree"]["stats"]["n"] == 7
        md = summarize.render_markdown(report)
        assert "# Mainnet observation report" in md
        assert "Spy share of reachable IPs" in md


class TestNetscanSummarize:
    """netscan_summarize.py against a hand-built xmrnetscan SQLite snapshot.

    Reachable set: a spy fleet of 2 IPs multiplexing ports (200.0.0.1 on 3
    ports, 200.0.0.2 on 2 ports = 5 ip:port) plus 2 honest IPs (1 port each);
    7 reachable ip:port on 4 IPs. 3 more attempted-but-unreachable ip:port.
    bad_peers.txt lists exactly the 5 spy ip:port. No network (asn_cache=None).
    """
    SPY = ["200.0.0.1:18080", "200.0.0.1:18081", "200.0.0.1:18082",
           "200.0.0.2:18080", "200.0.0.2:18081"]
    HONEST = ["10.0.0.1:18080", "10.1.0.1:18080"]   # two distinct /24s

    def _make_snapshot(self, tmp_path):
        import sqlite3
        snap = tmp_path / "2026-01-01"
        snap.mkdir()
        db = sqlite3.connect(snap / "crawler-netscan.db")
        db.execute("CREATE TABLE handshake_attempts (connected_node TEXT)")
        db.execute("CREATE TABLE handshake_data (connected_node TEXT, rpc_port INTEGER, "
                   "pruning_seed TEXT, peer_id BIGINT, support_flags TEXT, "
                   "core_sync_data TEXT, my_port INTEGER)")
        db.execute("CREATE TABLE peerlists (connected_node TEXT, peerlist TEXT)")
        reachable = self.SPY + self.HONEST
        for i, ipp in enumerate(reachable + ["9.9.9.9:18080", "9.9.9.10:18080", "9.9.9.11:18080"]):
            db.execute("INSERT INTO handshake_attempts VALUES (?)", (ipp,))
        csd = ("Mutex {{ data: CoreSyncData {{ cumulative_difficulty: 100, "
               "current_height: {h}, top_version: {v} }} }}")
        for i, ipp in enumerate(reachable):
            flags = "PeerSupportFlags(0)" if ipp == self.HONEST[-1] else "PeerSupportFlags(1)"
            pruning = "5" if ipp == self.HONEST[0] else "NotPruned"
            db.execute("INSERT INTO handshake_data VALUES (?,?,?,?,?,?,?)",
                       (ipp, 0, pruning, 1000 + i, flags,
                        csd.format(h=3000 + i, v=16), 18080))
        # one peerlist row so the graph is non-empty
        db.execute("INSERT INTO peerlists VALUES (?,?)",
                   ("KnownAddr(10.0.0.1:18080)", "[10.1.0.1:18080, 200.0.0.1:18080]"))
        db.commit()
        db.close()
        (snap / "bad_peers.txt").write_text(
            "".join("peer: %s, peer_ids: [1, 2, 2, 2],\n" % s for s in self.SPY))
        return snap

    def test_reachability_and_port_multiplexing(self, tmp_path):
        snap = self._make_snapshot(tmp_path)
        r = netscan_summarize.build_report(snap, None, None,
                                           netscan_summarize.SPRUCE_ASN, allow_network=False)
        rc = r["reachability"]
        assert rc["reachable_ipport"] == 7
        assert rc["reachable_ip"] == 4
        assert rc["probed_ipport"] == 10
        assert r["port_multiplexing"]["mean_ports_per_ip"] == pytest.approx(7 / 4)

    def test_dual_unit_spy_share_from_bad_peers(self, tmp_path):
        snap = self._make_snapshot(tmp_path)
        r = netscan_summarize.build_report(snap, None, None,
                                           netscan_summarize.SPRUCE_ASN, allow_network=False)
        mm = r["spy"]["mismatch"]
        assert mm["by_ipport"]["count"] == 5
        assert mm["by_ipport"]["share"] == pytest.approx(5 / 7)   # node-instances
        assert mm["by_ip"]["count"] == 2
        assert mm["by_ip"]["share"] == pytest.approx(2 / 4)       # distinct machines
        assert mm["by_ip"]["distinct_24s"] == 1                   # all 200.0.0.x
        assert mm["mean_ports_per_spy_ip"] == pytest.approx(5 / 2)

    def test_handshake_and_chain_fields(self, tmp_path):
        snap = self._make_snapshot(tmp_path)
        r = netscan_summarize.build_report(snap, None, None,
                                           netscan_summarize.SPRUCE_ASN, allow_network=False)
        hs = r["handshake"]
        assert hs["flags_absent_share"] == pytest.approx(1 / 7)   # one PeerSupportFlags(0)
        assert hs["pruned_share"] == pytest.approx(1 / 7)         # one pruning_seed != NotPruned
        assert r["chain"]["top_version_dist"] == {"16": 7}
        assert r["chain"]["height"]["n"] == 7
        # honest = reachable minus spies -> the 2 honest IPs, in 2 distinct /24s
        assert r["honest_concentration"]["prefix_share"]["distinct_24s"] == 2

    def test_render_markdown_smoke(self, tmp_path):
        snap = self._make_snapshot(tmp_path)
        r = netscan_summarize.build_report(snap, None, None,
                                           netscan_summarize.SPRUCE_ASN, allow_network=False)
        md = netscan_summarize.render_markdown(r)
        assert "xmrnetscan (S12) summary" in md
        assert "Port multiplexing" in md and "ports/IP" in md
