# Add `--small-footprint` Flag to Reduce Log Output

## Status: Planned

## Problem

At 1000 nodes, daemon logs consume ~30 GB per simulation run. The dominant source (77% of all log lines) is `net.p2p.traffic` — per-message byte-counting lines like:

```
[IP:PORT INC] 172 bytes sent for category command-1002 initiated by us
```

These are only used by the bandwidth analysis module. All other analysis (propagation, dandelion, spy node, network graph, upgrade analysis, success criteria) works without them.

Nodes with high incoming connection counts (300+) produce 10x the log volume of normal nodes (213 MB vs 22 MB), further skewing output.

## Proposed Solution

Add `--small-footprint` flag to `generate_config.py` that sets per-daemon log level to:

```
--log-level=1,net.p2p.traffic:0
```

Monero supports per-category log level overrides. This keeps all INFO-level logging globally but suppresses the `net.p2p.traffic` category specifically.

### What's preserved (all analysis except bandwidth)

| Pattern | Category | Used by |
|---------|----------|---------|
| `[IP:PORT] NEW/CLOSE CONNECTION` | `net.p2p` | network_graph |
| `Received NOTIFY_NEW_TRANSACTIONS` + `Including transaction <hash>` | `net.p2p` | propagation, dandelion, spy_node, tx_relay_v2 |
| `Received NOTIFY_NEW_FLUFFY_BLOCK` | `net.p2p` | propagation, success_criteria |
| `NOTIFY_TX_POOL_HASH`, `NOTIFY_REQUEST_TX_POOL_TXS` | `net.p2p` | tx_relay_v2 |
| `BLOCK SUCCESSFULLY ADDED`, `HEIGHT N`, `Transaction added to pool` | blockchain | propagation, success_criteria |

### What's suppressed

| Pattern | Category | Used by |
|---------|----------|---------|
| `N bytes sent/received for category command-XXXX initiated by us/peer` | `net.p2p.traffic` | bandwidth analysis only |

### Expected savings

- ~75% reduction in daemon log volume (~30 GB -> ~7.5 GB at 1000 nodes)
- Proportional reduction in Shadow's memory footprint for log buffering
- Hotspot nodes (300+ incoming connections) see the largest benefit

## Implementation

### 1. Add flag to `generate_config.py` argparse

```python
parser.add_argument(
    "--small-footprint",
    action="store_true",
    default=False,
    help="Reduce daemon log output by suppressing P2P traffic byte counts. "
         "Disables bandwidth analysis but keeps all other analysis working. "
         "Saves ~75%% of log volume."
)
```

### 2. Pass through to config generation

In `generate_config()` and `generate_upgrade_config()`, accept a `small_footprint` parameter that changes the daemon log level from `1` to `1,net.p2p.traffic:0`.

### 3. Rust side: `config_v2.rs` + `agent/` module

The daemon `log-level` arg is constructed in the Rust agent generation code. Add support for the config YAML to specify a custom log level string, or add a `small_footprint: true` field that the Rust code translates to the appropriate `--log-level` value.

### 4. Header comment

Include `[SMALL FOOTPRINT]` in the generated YAML header when enabled, similar to `[FAST MODE]`.

## Also Consider: `--in-peers` Limit

Separate from log suppression, adding `--in-peers 48` (or similar) to daemon args would cap incoming connections at a realistic mainnet level. This would:
- Prevent hotspot nodes from accumulating 300+ connections
- Reduce connection churn (44k connections over 32h on worst nodes)
- Reduce log volume even at level 1 (fewer connection events per node)
- More realistic network topology

This could be a separate flag (`--realistic-peers`) or bundled into `--small-footprint`.

## Verification

```bash
# With --small-footprint: bandwidth analysis should warn/skip gracefully
# Without: full analysis including bandwidth breakdown by command type

# Test log reduction
python3 scripts/generate_config.py --agents 10 --small-footprint -o /tmp/test_small.yaml
grep "log-level" /tmp/test_small.yaml
# Expected: log-level: "1,net.p2p.traffic:0"
```
