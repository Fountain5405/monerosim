"""Tests for analysis/topology_metrics.py.

The main fixture (`fixture_graph`) is a hand-built 49-node graph (3 hubs, 40
peripheral nodes, 6 spies) fed straight into `compute_snapshot_metrics` --
the same function `analyze()` calls per window -- so every metric is
exercised through its real code path without touching log parsing. Expected
values are derived by hand in the comments; degree_assortativity is also
cross-checked against a from-scratch Pearson computation, and
modularity_greedy against a direct networkx call on the same edge set (its
absolute value depends on networkx's greedy algorithm, so a hand derivation
isn't practical; the cross-check confirms our wiring, not the algorithm).

A separate smoke test exercises `parse_timestamped_peers` /
`load_node_events` / `snapshot_peer_sets` against a tiny synthetic monitor-log
fixture using the exact line format real archived logs use (see the
docstring in that test for the source line copied as a template).
"""
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import topology_metrics as tm  # noqa: E402


# ---------------------------------------------------------------------------
# classify() / parse_duration() / make_windows()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("spy-a-001", "spy"),
    ("monero-seed-003", "monero-seed"),
    ("miner-001", "miner"),
    ("medium-a-012", "medium"),
    ("observer-002", "observer"),
    ("relay-042", "relay"),
    ("user-07", "user"),
    ("bridge-1", "other"),
])
def test_classify(name, expected):
    assert tm.classify(name) == expected


@pytest.mark.parametrize("value,expected", [
    ("10m", 600),
    ("1h", 3600),
    ("300s", 300),
    (120, 120),
    ("auto", 0),
    (None, 0),
    ("garbage", 0),
])
def test_parse_duration(value, expected):
    assert tm.parse_duration(value, default=0) == expected


def test_make_windows_tiles_the_range():
    windows = tm.make_windows(0, 1000, 300)
    assert windows == [(0, 300), (300, 600), (600, 900), (900, 1000)]


def test_make_windows_degenerate_range_returns_one_window():
    windows = tm.make_windows(100, 100, 300)
    assert windows == [(100, 400)]


# ---------------------------------------------------------------------------
# compute_snapshot_metrics: the hand-built 49-node fixture
# ---------------------------------------------------------------------------

def _add(d, name, peer):
    d.setdefault(name, set()).add(peer)


@pytest.fixture
def fixture_graph():
    """3 hubs (H1, H2 miner; H3 monero-seed) dial OUT to 40 peripherals
    (relay class); 6 spies attach to a few peripherals; P31..P40 (firewalled,
    no hub link) pair up among themselves. See module docstring / builder's
    report for the full hand derivation.
    """
    nodes = ["H1", "H2", "H3"]
    nodes += ["P%02d" % i for i in range(1, 41)]
    nodes += ["S%d" % i for i in range(1, 7)]

    node_class = {"H1": "miner", "H2": "miner", "H3": "monero-seed"}
    node_class.update({"P%02d" % i: "relay" for i in range(1, 41)})
    node_class.update({"S%d" % i: "spy" for i in range(1, 7)})

    firewalled = {name: False for name in nodes}
    for i in range(31, 41):
        firewalled["P%02d" % i] = True

    out_peers, in_peers = {}, {}

    for i in range(1, 21):
        _add(out_peers, "H1", "P%02d" % i)
        _add(in_peers, "P%02d" % i, "H1")
    for i in range(11, 31):
        _add(out_peers, "H2", "P%02d" % i)
        _add(in_peers, "P%02d" % i, "H2")
    for i in range(1, 11):
        _add(out_peers, "H3", "P%02d" % i)
        _add(in_peers, "P%02d" % i, "H3")

    _add(out_peers, "S1", "P01"); _add(in_peers, "P01", "S1")
    _add(out_peers, "S2", "P02"); _add(in_peers, "P02", "S2")
    _add(out_peers, "P03", "S3"); _add(in_peers, "S3", "P03")
    _add(out_peers, "S4", "P21"); _add(in_peers, "P21", "S4")
    _add(out_peers, "S5", "P22"); _add(in_peers, "P22", "S5")
    _add(out_peers, "P23", "S6"); _add(in_peers, "S6", "P23")

    for a, b in [(31, 32), (33, 34), (35, 36), (37, 38), (39, 40)]:
        _add(out_peers, "P%02d" % a, "P%02d" % b)
        _add(in_peers, "P%02d" % b, "P%02d" % a)

    return nodes, out_peers, in_peers, node_class, firewalled


def test_degree_class_shares_absolute_and_scaled(fixture_graph):
    nodes, out_peers, in_peers, node_class, firewalled = fixture_graph
    m = tm.compute_snapshot_metrics(nodes, out_peers, in_peers, node_class, firewalled)

    # Only H1 (out-degree 20) and H2 (out-degree 20) exceed the absolute
    # light cap of 12; both stay <=250, so they land in "medium": 2/49.
    abs_shares = m["degree_class_shares_absolute"]
    assert abs_shares["light_pct"] == pytest.approx(47 / 49 * 100)
    assert abs_shares["medium_pct"] == pytest.approx(2 / 49 * 100)
    assert abs_shares["heavy_pct"] == pytest.approx(0.0)

    # Scaled heavy threshold = 0.25*49 = 12.25: H1/H2 (20 > 12.25) now count
    # as heavy instead of medium; nothing else changes.
    scaled_shares = m["degree_class_shares_scaled"]
    assert scaled_shares["light_pct"] == pytest.approx(47 / 49 * 100)
    assert scaled_shares["medium_pct"] == pytest.approx(0.0)
    assert scaled_shares["heavy_pct"] == pytest.approx(2 / 49 * 100)


def test_top_k_connection_share(fixture_graph):
    nodes, out_peers, in_peers, node_class, firewalled = fixture_graph
    m = tm.compute_snapshot_metrics(nodes, out_peers, in_peers, node_class, firewalled)

    # round(0.132 * 49) = 6: {H1(20), H2(20), H3(10), P01(3), P02(3), P03(3)}
    # unambiguously the top 6 by total degree (next tier is degree 2).
    assert m["top_k_count"] == 6
    # sum(top6)=59, sum(all)=122 (hand-derived; also equals 2*edge_count=122).
    assert m["top_k_connection_share_pct"] == pytest.approx(59 / 122 * 100)
    assert m["edge_count"] == 61


def test_hub_coverage_and_overlap_default_hubs(fixture_graph):
    nodes, out_peers, in_peers, node_class, firewalled = fixture_graph
    m = tm.compute_snapshot_metrics(nodes, out_peers, in_peers, node_class, firewalled)

    assert m["hub_set"] == ["H1", "H2", "H3"]
    # Non-hub population = 46; P01..P30 (30 nodes) touch a hub, P31..P40 and
    # S1..S6 (16 nodes) do not.
    assert m["hub_coverage_pct"] == pytest.approx(30 / 46 * 100)
    # H1 neighbours (P01-20) are a subset of H2|H3's neighbours -> 100%;
    # H3 neighbours (P01-10) are a subset of H1|H2's -> 100%; H2's overlap
    # with H1|H3 is P11-20 only, 10/20 = 50%. Median of [100, 50, 100] = 100.
    assert m["hub_neighbour_overlap_pct"] == pytest.approx(100.0)


def test_hub_coverage_with_explicit_hubs(fixture_graph):
    nodes, out_peers, in_peers, node_class, firewalled = fixture_graph
    m = tm.compute_snapshot_metrics(nodes, out_peers, in_peers, node_class, firewalled,
                                     hubs=["H1"])
    assert m["hub_set"] == ["H1"]
    # Non-hub population = 48; only P01-P20 touch H1.
    assert m["hub_coverage_pct"] == pytest.approx(20 / 48 * 100)


def test_hub_coverage_with_top_k(fixture_graph):
    nodes, out_peers, in_peers, node_class, firewalled = fixture_graph
    m = tm.compute_snapshot_metrics(nodes, out_peers, in_peers, node_class, firewalled,
                                     top_k=3)
    assert set(m["hub_set"]) == {"H1", "H2", "H3"}


def test_degree_assortativity(fixture_graph):
    nodes, out_peers, in_peers, node_class, firewalled = fixture_graph
    m = tm.compute_snapshot_metrics(nodes, out_peers, in_peers, node_class, firewalled)
    # Hand-derived (see builder's report): symmetrized Pearson correlation
    # over the 61-edge graph's endpoint total-degrees.
    assert m["degree_assortativity"] == pytest.approx(-0.6017556547926544)


def test_modularity_matches_direct_networkx_call(fixture_graph):
    nx = pytest.importorskip("networkx")
    nodes, out_peers, in_peers, node_class, firewalled = fixture_graph
    m = tm.compute_snapshot_metrics(nodes, out_peers, in_peers, node_class, firewalled)

    neighbors = {n: out_peers.get(n, set()) | in_peers.get(n, set()) for n in nodes}
    edges = {frozenset((n, p)) for n in nodes for p in neighbors[n]}
    g = nx.Graph()
    g.add_nodes_from(nodes)
    g.add_edges_from(tuple(e) for e in edges)
    communities = nx.algorithms.community.greedy_modularity_communities(g)
    expected = nx.algorithms.community.modularity(g, communities)

    assert m["modularity_greedy"] == pytest.approx(expected)
    assert m["modularity_note"] is None


def test_inbound_per_reachable_honest_node(fixture_graph):
    nodes, out_peers, in_peers, node_class, firewalled = fixture_graph
    m = tm.compute_snapshot_metrics(nodes, out_peers, in_peers, node_class, firewalled)
    # 33 reachable honest nodes (P31-40 firewalled, S1-6 are spies);
    # sorted in-degrees: 3 zeros, 8 ones, 20 twos, 2 threes -> median = 2.
    assert m["reachable_honest_count"] == 33
    assert m["inbound_per_reachable_honest"] == 2


def test_spy_share_of_honest_slots(fixture_graph):
    nodes, out_peers, in_peers, node_class, firewalled = fixture_graph
    m = tm.compute_snapshot_metrics(nodes, out_peers, in_peers, node_class, firewalled)
    # total honest in-degree = 59, of which 4 (P01,P02,P21,P22) are spy-dialed.
    assert m["spy_share_inbound_pct"] == pytest.approx(4 / 59 * 100)
    # total honest out-degree = 57, of which 2 (P03->S3, P23->S6) are spy-dialed.
    assert m["spy_share_outbound_pct"] == pytest.approx(2 / 57 * 100)


def test_empty_population_does_not_crash():
    m = tm.compute_snapshot_metrics([], {}, {}, {}, {})
    assert m["degree_class_shares_absolute"]["light_pct"] is None
    assert m["hub_coverage_pct"] is None
    assert m["degree_assortativity"] is None
    assert m["inbound_per_reachable_honest"] is None
    assert m["spy_share_inbound_pct"] is None


# ---------------------------------------------------------------------------
# peerlist-dump spy share
# ---------------------------------------------------------------------------

def test_peerlist_entry_spy_share():
    by_ip = {
        "1.0.0.1": ("honest-1", "monerod"),
        "1.0.0.2": ("honest-2", "monerod"),
        "2.0.0.1": ("spy-a-001", "monerod"),
        "2.0.0.2": ("spy-a-002", "monerod"),
        "2.0.0.3": ("spy-a-003", "monerod"),
    }
    node_class = {"honest-1": "relay", "honest-2": "relay",
                  "spy-a-001": "spy", "spy-a-002": "spy", "spy-a-003": "spy"}
    entries = ["1.0.0.1:18080", "1.0.0.2:18080", "2.0.0.1:18080",
               "2.0.0.2:18080", "2.0.0.3:18080"]
    share = tm.peerlist_entry_spy_share(entries, node_class, by_ip)
    assert share == pytest.approx(3 / 5 * 100)


def test_peerlist_entry_spy_share_empty_is_none():
    assert tm.peerlist_entry_spy_share([], {}, {}) is None


def test_load_peerlist_dump_snapshots(tmp_path):
    dump = tmp_path / "peerlist_dump.jsonl"
    dump.write_text(
        json.dumps({"t": 946684830, "white": [["1.0.0.1:18080", 0]], "gray": []}) + "\n"
        + json.dumps({"t": 946684890, "white": [["1.0.0.1:18080", 0], ["2.0.0.1:18080", 0]],
                      "gray": [["3.0.0.1:1234", 0]]}) + "\n"
    )
    snaps = tm.load_peerlist_dump_snapshots(dump)
    assert [t for t, _ in snaps] == [30, 90]
    assert snaps[1][1] == ["1.0.0.1:18080", "2.0.0.1:18080", "3.0.0.1:1234"]

    best = tm.nearest_snapshot_at_or_before(snaps, 60)
    assert best[0] == 30
    best = tm.nearest_snapshot_at_or_before(snaps, 5)
    assert best is None


# ---------------------------------------------------------------------------
# Parser smoke test: a tiny synthetic monitor-log archive
# ---------------------------------------------------------------------------

# Exact tab-separated format copied from an archived run's bitmonero.log
# (monitor log-level, net.p2p / net.p2p.msg categories both match
# conn_matrix.MONEROD_TOKEN, which only looks at the trailing
# `[<ip>:<port> INC|OUT]` token, not the category column):
#   2000-01-01 00:00:11.791\t[P2P7]\tINFO\tnet.p2p\tsrc/p2p/net_node.inl:2753\t[3.0.0.11:50572 <peer-id> INC] NEW CONNECTION
LOG_LINE = (
    "2000-01-01 00:00:{sec:02d}.{ms:03d}\t[P2P0]\tINFO\tnet.p2p.msg\t"
    "src/cryptonote_protocol/cryptonote_protocol_handler.inl:2684\t"
    "[{ip}:18080 {direction}] -->>NOTIFY_GET_TXPOOL_COMPLEMENT: hashes.size()=0\n"
)


def _write_shadow_agents(archive, hosts):
    (archive).mkdir(parents=True, exist_ok=True)
    cfg = {
        "general": {"stop_time": 600, "bootstrap_end_time": "0s"},
        "hosts": hosts,
    }
    with open(archive / "shadow_agents.yaml", "w") as fh:
        yaml.safe_dump(cfg, fh)


def test_smoke_parses_synthetic_monitor_log(tmp_path):
    archive = tmp_path / "archive"
    hosts = {
        "relay-a": {"ip_addr": "1.0.0.10",
                    "processes": [{"path": "/usr/bin/monerod-sim"}]},
        "relay-b": {"ip_addr": "1.0.0.20",
                    "processes": [{"path": "/usr/bin/monerod-sim"}]},
    }
    _write_shadow_agents(archive, hosts)

    logs = archive / "daemon_logs"
    (logs / "monero-relay-a").mkdir(parents=True)
    (logs / "monero-relay-b").mkdir(parents=True)
    with open(logs / "monero-relay-a" / "bitmonero.log", "w") as fh:
        fh.write(LOG_LINE.format(sec=10, ms=100, ip="1.0.0.20", direction="OUT"))
    with open(logs / "monero-relay-b" / "bitmonero.log", "w") as fh:
        fh.write(LOG_LINE.format(sec=10, ms=200, ip="1.0.0.10", direction="INC"))

    node_events = tm.load_node_events(archive)
    assert set(node_events) == {"relay-a", "relay-b"}
    assert node_events["relay-a"] == [(10.1, "1.0.0.20", "OUT")]
    assert node_events["relay-b"] == [(10.2, "1.0.0.10", "IN")]

    by_ip, by_name, firewalled, node_class, general = tm.load_run_meta(archive)
    out_peers, in_peers = tm.snapshot_peer_sets(node_events, by_ip, 0, 60)
    assert out_peers["relay-a"] == {"relay-b"}
    assert in_peers["relay-b"] == {"relay-a"}
    assert firewalled == {"relay-a": False, "relay-b": False}
    assert node_class["relay-a"] == "relay"


def test_default_window_bounds_from_general():
    general = {"bootstrap_end_time": "10m", "stop_time": 3600}
    assert tm.default_window_bounds(general) == (600, 3600)


def test_default_window_bounds_falls_back_when_stop_before_bootstrap():
    general = {"bootstrap_end_time": "1h", "stop_time": 0}
    t_from, t_to = tm.default_window_bounds(general)
    assert t_from == 3600
    assert t_to == 3600 + 3600
