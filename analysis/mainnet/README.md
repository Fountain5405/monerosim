# Mainnet observation tools

Measure the live Monero mainnet with the same metrics used on the
monerosim simulator, so stage-2 replica validation
(`docs/superpowers/specs/2026-09-23-mainnet-replica-design.md` §6) has recent
data instead of only the 2018-2026 literature
(`docs/20260923_mainnet_topology_literature.md`).

## Tools

- **`poll_node.py`** — polls one monerod's RPC (`get_info` + `get_connections`
  every `--interval` seconds, `/get_peer_list` every `--peerlist-interval`
  seconds) and appends one JSON line per tick to daily files
  (`connections-YYYYMMDD.jsonl`, `peerlist-YYYYMMDD.jsonl`). On a UTC-date
  rollover the previous day's files are gzipped in place. RPC errors are
  logged and the tick is still recorded (`error` set, RPC fields `null`), so
  the poller survives a daemon restart or network blip. Writes a pid file and
  logs an hourly one-line summary. State-free: safe to kill (SIGTERM/SIGINT)
  and restart at any time.

- **`crawl.py`** — BFS crawl of the P2P network via raw Levin handshakes
  (`agents/levin_lib.py`, extended here with initiator helpers and peerlist
  parsing). Seeds from the given node's white+gray peer lists plus live DNS
  resolution of the mainnet fallback seed hostnames
  (`seeds.moneroseeds.{se,ae.org,ch,li}` — best-effort: these may not resolve
  from every host/resolver, the crawl still runs off the RPC-sourced seeds).
  For every unique `ip:port`, sends exactly one `COMMAND_HANDSHAKE` (with
  honest-looking sync data: the seed's current height/top hash **and current
  hard-fork version**) and one `COMMAND_PING`, records reachability, RTT, the
  handshake peer_id, top height, support-flags presence, and the peer's
  advertised peerlist (added to the frontier). Output: `nodes.jsonl`,
  `edges.jsonl.gz` (peerlist-adjacency edges), `crawl_summary.json`.

  **Trap fixed during validation:** `top_version` must match the CURRENT
  hard-fork version for the claimed height (fetched via the seed's
  `hard_fork_info`), not a hardcoded default. monerod's
  `process_payload_sync_data` rejects any post-v6-height claim with a stale
  `top_version` — it drops the connection and returns an all-default,
  all-zero handshake response instead of real data (indistinguishable, at
  first glance, from the literature's "genesis trick" spy fingerprint). Get
  this wrong and *every* live node looks like a decoy: 0/200 reachable with
  `top_version` defaulted to 1 at real mainnet heights, 148/200 reachable
  once `hard_fork_info`'s version was threaded through.

- **`enrich_asn.py`** — bulk ASN/country lookup of a crawl's IPs via the Team
  Cymru whois bulk interface (`whois.cymru.com:43`, "begin/verbose/ip
  lines/end"), chunked at ≤2,000 IPs per query, cached on disk
  (`<out>/.asn_cache.json` by default) so re-runs only look up new IPs.

- **`summarize.py`** — combines a crawl + poll dataset + a ban list + ASN
  data into `report.md` and `report.json`: the mainnet counterparts of the
  replica spec's §6 table and the literature's §4/§4a numbers (reachable
  count, three-way spy-label overlap, spy/honest /24 and ASN concentration,
  our node's connection counts and spy slot/peerlist shares over time,
  connection-duration distribution derived from consecutive poll ticks, and
  peerlist-adjacency degree/hub-coverage stats from the crawl). `--ban-list
  FILE` takes an already-downloaded list; `--fetch-ban-list DIR` downloads a
  fresh, date-stamped one instead.

- **`netscan_summarize.py`** — the S12 counterpart of `summarize.py`, for
  Rucknium's [xmrnetscan](https://github.com/Rucknium/xmrnetscan) daily
  snapshots (extract the `.tar.xz`; it holds `crawler-netscan.db` +
  `bad_peers.txt`). Reuses `summarize.py`'s metric helpers so S12 is computed
  identically to our own S13 crawl, and `enrich_asn.py`'s cache (only IPs not
  already cached are looked up; `--no-network` skips even that). Reports
  reachability, the spy share in **both** units (by ip:port node-instance and by
  distinct IP — the fleet multiplexes ~8 ports/IP), honest /24 and ASN
  concentration, chain-consensus health (height spread, hard-fork adoption,
  pruned share), and the peerlist-adjacency graph. `--snapshot DIR --out
  report.md [--asn-cache PATH] [--ban-list PATH] [--spy-asn 401476]`.

## The week-long recipe

Datasets live **outside the repo**, e.g.
`~/basement_monerosim/<date>_mainnet_observation/`.

```bash
OUT=~/basement_monerosim/20260923_mainnet_observation
mkdir -p "$OUT/poll"

systemd-run --user --unit monerosim-mainnet-poll \
  --description "monerosim mainnet RPC poller" \
  /path/to/venv/bin/python3 analysis/mainnet/poll_node.py \
  --rpc http://192.168.1.76:12345 --out "$OUT/poll" \
  --interval 60 --peerlist-interval 600 --duration 7d

# Check on it:
systemctl --user status monerosim-mainnet-poll
journalctl --user -u monerosim-mainnet-poll -f

# Stop early if needed (state-free, safe to restart):
systemctl --user stop monerosim-mainnet-poll
```

Run the crawl and enrichment once, any time during (or after) the poll week:

```bash
python3 analysis/mainnet/crawl.py --seed-rpc http://192.168.1.76:12345 \
  --out "$OUT/crawl" --max-nodes 20000 --concurrency 48 --timeout 8
python3 analysis/mainnet/enrich_asn.py --in "$OUT/crawl/nodes.jsonl" \
  --out "$OUT/crawl/asn.jsonl"
```

Then summarize:

```bash
python3 analysis/mainnet/summarize.py --crawl "$OUT/crawl" --poll "$OUT/poll" \
  --fetch-ban-list "$OUT" --asn "$OUT/crawl/asn.jsonl" --out "$OUT/report.md"
```

## Politeness

- `poll_node.py` never polls the given node more often than `--interval`
  (recommend ≥60s) / `--peerlist-interval` (recommend ≥600s); it is one node
  we've been given unrestricted RPC access to, used read-only.
- `crawl.py` sends **exactly one** handshake + one ping per `ip:port` for the
  whole crawl (a `visited` set is updated before submission, not after),
  concurrency is capped at 64, one connect+read timeout, no retries. It talks
  to the wider internet (real mainnet nodes), so keep `--max-nodes` and
  `--concurrency` modest for anything beyond a one-off full crawl.
- `enrich_asn.py` caches every IP it has ever looked up so re-runs (e.g. a
  second crawl a week later) don't re-query Team Cymru for known IPs.
- The ban list is fetched at most once per `summarize.py` invocation via
  `--fetch-ban-list`, into the dataset dir with a date stamp
  (`ban_list-YYYYMMDD.txt`) — not re-downloaded on every run.

## How the report maps onto the spec

`report.md` / `report.json` sections line up with
`docs/superpowers/specs/2026-09-23-mainnet-replica-design.md` §6 and
`docs/20260923_mainnet_topology_literature.md` §4/§4a:

| Report section | Spec / literature counterpart |
|---|---|
| Reachability | §3 "~15% reachable" (handshake-completing share of a peer-list sample, not the whole network) |
| Spy share of reachable IPs (3 labels + overlap) | §4 ban list / S5 peer-ID mismatch / S6+S4 support-flags-absent fingerprints |
| Spy /24 and ASN concentration | §4/4a "6 dense /24s", "43 ASes" |
| Honest ASN/prefix concentration | §4a "12% of BGP prefixes hold 55% of nodes" (per-/24, so an upper bound — see the design doc §3) |
| Our node's connection counts | §3 "50-100 inbound per reachable node" |
| Spy share of our node's slots | §4 "20.37% inbound / 15.26% outbound" (S4, pre-dedup) |
| Spy share of peerlist entries | §4 "16.93% average peerlist" |
| Connection-duration distribution | §3 / §6 "~23 min median, ~1.5%/~0% >6h" (S10) |
| Peerlist-adjacency degree distribution | §4a Kirschner (mean 517/median 667/p90 1,750; not comparable to connection degree) |

## Tests

`test_mainnet_tools.py` (pytest, no network) exercises parsers and summaries
against fixtures in `fixtures/` — including one real `get_info` /
`get_connections` / `/get_peer_list` response captured from the live node,
with peer IPs anonymised to `10.x` addresses.
