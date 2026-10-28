# scripts/test_gml_add_slow_nodes.py
"""The slow-link derivation of a Shadow GML graph: new nodes hang off an
anchor node by one high-latency edge each (both directions), so a host pinned
there with `topology_node` reaches everything through that link."""
import re

from scripts.gml_add_slow_nodes import add_slow_nodes, parse_records

TINY = """graph [
  directed 1
  node [
    id 0
    AS "0"
    region "north_america"
    bandwidth "238Mbit"
  ]
  node [
    id 1
    AS "1"
    region "europe"
    bandwidth "100Mbit"
  ]
  edge [
    source 0
    target 0
    latency "1ms"
    bandwidth "10Gbit"
  ]
  edge [
    source 1
    target 1
    latency "1ms"
    bandwidth "10Gbit"
  ]
  edge [
    source 0
    target 1
    latency "45ms"
    bandwidth "191Mbit"
  ]
  edge [
    source 1
    target 0
    latency "45ms"
    bandwidth "191Mbit"
  ]
]
"""


def test_adds_one_node_per_latency_with_loop_and_both_edges():
    out = add_slow_nodes(TINY, anchor=0, latencies_ms=[3000, 10000])
    nodes, edges = parse_records(out)
    assert [n["id"] for n in nodes] == ["0", "1", "2", "3"]
    new = {n["id"]: n for n in nodes if n["id"] in ("2", "3")}
    # The new nodes copy the anchor's region and bandwidth, own AS = id.
    assert new["2"]["region"] == '"north_america"'
    assert new["2"]["bandwidth"] == '"238Mbit"'
    assert new["2"]["AS"] == '"2"' and new["3"]["AS"] == '"3"'
    key = lambda e: (e["source"], e["target"])
    by = {key(e): e for e in edges}
    assert len(edges) == 4 + 2 * 3
    for nid, lat in (("2", "3000ms"), ("3", "10000ms")):
        assert by[(nid, nid)]["latency"] == '"1ms"'
        assert by[("0", nid)]["latency"] == f'"{lat}"'
        assert by[(nid, "0")]["latency"] == f'"{lat}"'
        assert by[("0", nid)]["bandwidth"] == '"238Mbit"'
    # The original records are untouched and the file still closes.
    assert out.startswith("graph [\n  directed 1\n")
    assert out.rstrip().endswith("]")
    assert re.search(r'source 0\n\s+target 1\n\s+latency "45ms"', out)


def test_unknown_anchor_is_an_error():
    import pytest
    with pytest.raises(ValueError, match="anchor 7"):
        add_slow_nodes(TINY, anchor=7, latencies_ms=[1000])
