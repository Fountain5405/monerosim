# analysis/

Offline analysis tools that read an archived run directory
(`archived_runs/<run_id>/`, or a compatible raw/live layout) and report on it.
None of these run a simulation; they only parse logs, dumps and the
generated `shadow_agents.yaml`.

## topology_metrics.py

Stage-2 validation: compares an archived run's connection graph against the
mainnet-topology literature targets (`docs/20260923_mainnet_topology_literature.md`,
sources S1-S11; targets table in
`docs/superpowers/specs/2026-09-23-mainnet-replica-design.md` #6).

```
python3 analysis/topology_metrics.py <archive_dir> [--window 300]
    [--from SECONDS] [--to SECONDS] [--hubs id1,id2,...] [--top-k N]
    [--json out.json]
```

It samples the connection graph on snapshots every `--window` seconds over
`[--from, --to]` (default: the run's post-bootstrap activity window) from
monitor-level daemon logs, reusing `conn_matrix.py`'s connection-token regex
and host loader rather than re-deriving them, plus observer
`peerlist_dump.jsonl` files for the spy-peerlist-share metric. It reports the
median and (min, max) spread across snapshots for: outbound-degree class
shares (absolute and N-scaled thresholds), the connection share held by the
top 13.2% of nodes, hub coverage and hub-neighbour overlap, degree
assortativity, modularity (via networkx, when importable), inbound
connections per reachable honest node, and spy share of honest nodes'
inbound/outbound slots and of peerlist entries. Run `--help` for a one-line
explanation of each metric. Connection-duration / >6h-tail metrics are out of
scope here; see `analysis/ruck_analysis_turnover.r`.

Tests: `analysis/test_topology_metrics.py` (a hand-built synthetic graph
fixture exercises every metric through the same `compute_snapshot_metrics`
function the tool calls per snapshot, plus a log/dump parser smoke test).
