# Transaction Routing Analysis Tools

Monerosim includes two cross-validated analysis implementations (Rust and Python) for examining transaction routing behavior, network topology, and privacy characteristics after running a simulation.

## Prerequisites

Before running analysis, you need:
1. A completed Shadow simulation with logs in `shadow.data/`
2. Shared state files in `/tmp/monerosim_shared/` (created automatically during simulation)

## Quick Start

```bash
# Build Rust analyzer
cargo build --release --bin tx-analyzer

# Run full analysis
./target/release/tx-analyzer full

# Or use Python
python3 scripts/tx_analyzer.py full
```

Output is written to `analysis_output/` directory.

## Rust Analyzer (`tx-analyzer`)

### Installation

```bash
cargo build --release --bin tx-analyzer
```

### Commands

```bash
# Full analysis (recommended)
./target/release/tx-analyzer full

# Individual analyses
./target/release/tx-analyzer spy-node      # Spy node vulnerability
./target/release/tx-analyzer propagation   # Transaction propagation timing
./target/release/tx-analyzer resilience    # Network connectivity/centralization
./target/release/tx-analyzer dandelion     # Dandelion++ stem path analysis
./target/release/tx-analyzer tx-relay-v2   # TX Relay V2 protocol analysis
./target/release/tx-analyzer network-graph # P2P topology analysis
./target/release/tx-analyzer summary       # Quick summary stats
./target/release/tx-analyzer upgrade-analysis  # Compare pre/post upgrade metrics
```

### Options

```bash
# Common options (apply to all commands)
-d, --data-dir <PATH>     Shadow data directory [default: shadow.data]
-s, --shared-dir <PATH>   Shared state directory [default: /tmp/monerosim_shared]
-o, --output <PATH>       Output directory [default: analysis_output]
-j, --threads <N>         Parallel workers (0=auto) [default: 0]

# Spy node options
--min-confidence <F>      Filter results by confidence [default: 0.5]

# Dandelion options
--detailed                Show full path details
--short-stems <N>         Only show stems <= N hops

# Network graph options
--dot                     Export GraphViz DOT file

# Upgrade analysis options
--window-size <N>         Time window size in seconds [default: 60]
--manifest <PATH>         Path to upgrade manifest JSON file
--pre-upgrade-end <T>     Manual override: end of pre-upgrade period (seconds)
--post-upgrade-start <T>  Manual override: start of post-upgrade period (seconds)
```

### Example

```bash
# Detailed Dandelion analysis with short stem filtering
./target/release/tx-analyzer dandelion --detailed --short-stems 3

# Network graph with DOT export for visualization
./target/release/tx-analyzer network-graph --dot

# Upgrade impact analysis with manifest
./target/release/tx-analyzer upgrade-analysis --manifest upgrade_manifest.json

# Upgrade analysis with manual time boundaries
./target/release/tx-analyzer upgrade-analysis --pre-upgrade-end 300 --post-upgrade-start 600
```

## Python Analyzer (`tx_analyzer.py`)

### Installation

```bash
# Activate virtual environment (if using)
source venv/bin/activate

# No additional dependencies required (uses standard library)
```

### Commands

```bash
# Full analysis
python3 scripts/tx_analyzer.py full

# Individual analyses
python3 scripts/tx_analyzer.py spy-node
python3 scripts/tx_analyzer.py propagation
python3 scripts/tx_analyzer.py resilience
python3 scripts/tx_analyzer.py dandelion
python3 scripts/tx_analyzer.py relay-v2
python3 scripts/tx_analyzer.py summary
python3 scripts/tx_analyzer.py upgrade-analysis
```

### Options

```bash
--shadow-data <PATH>      Shadow data directory [default: shadow.data]
--shared-dir <PATH>       Shared state directory [default: /tmp/monerosim_shared]
--output-dir <PATH>       Output directory [default: analysis_output]
--max-workers <N>         Parallel workers [default: CPU count]
--detailed                Include per-TX details in output
--json                    Output JSON only (no text summary)

# Upgrade analysis options
--window-size <N>         Time window size in seconds [default: 60]
--manifest <PATH>         Path to upgrade manifest JSON file
--pre-upgrade-end <T>     Manual override: end of pre-upgrade period (seconds)
--post-upgrade-start <T>  Manual override: start of post-upgrade period (seconds)
```

## Analysis Types

### 1. Spy Node Vulnerability

Simulates a spy node attack where an adversary tries to identify transaction originators by observing first-seen timing patterns.

**Methodology:**
1. For each transaction, sort observations by timestamp
2. Look at the first 5 observations
3. Find the most common `source_ip` among those observations
4. Compare against the actual sender's IP
5. Calculate inference accuracy

**Output:**
- `inference_accuracy`: Percentage of transactions where the spy correctly identifies the sender
- `timing_distribution`: Count of high/moderate/low vulnerability transactions
- `vulnerable_senders`: List of senders most susceptible to deanonymization

**Interpretation:**
- Higher accuracy = worse privacy (attacker can identify senders)
- Transactions with tight timing spread (< 100ms) are most vulnerable
- Dandelion++ should reduce accuracy to near-random (~3% for 30 nodes)

### 2. Propagation Timing

Measures how quickly transactions spread through the network.

**Metrics:**
- `average_propagation_ms`: Mean time for TX to reach all nodes
- `median_propagation_ms`: Median propagation time
- `p95_propagation_ms`: 95th percentile (worst-case excluding outliers)
- `bottleneck_nodes`: Nodes that consistently receive transactions late

**Interpretation:**
- Lower propagation time = healthier network
- Large gap between median and P95 indicates some slow paths
- Bottleneck nodes may have connectivity issues

### 3. Network Resilience

Analyzes network connectivity and centralization.

**Metrics:**
- `average_peer_count`: Mean connections per node
- `gini_coefficient`: Inequality in first-seen distribution (0=equal, 1=centralized)
- `connected_components`: Number of separate network partitions
- `bridge_nodes`: Nodes whose removal would partition the network
- `isolated_nodes`: Nodes with no connections

**Interpretation:**
- Gini > 0.4 indicates significant centralization (surveillance risk)
- Multiple components indicate network partition
- Bridge nodes are critical for connectivity

### 4. Dandelion++ Stem Paths

Reconstructs the stem phase of Dandelion++ protocol.

**Methodology:**
1. Start from the transaction originator
2. Follow the chain: each hop receives from exactly one sender
3. Detect fluff point: when a node broadcasts to 3+ peers within 100ms
4. Calculate stem length and privacy score

**Metrics:**
- `avg_stem_length`: Average hops before fluff
- `min/max_stem_length`: Range of stem lengths
- `privacy_score`: Based on stem length (longer = better privacy)
- `frequent_fluff_points`: Nodes that often transition to fluff phase

**Interpretation:**
- Longer stems = better privacy (harder to trace back to origin)
- Consistent fluff points may indicate protocol configuration issues
- Short stems (< 3 hops) are concerning for privacy

### 5. TX Relay V2 Protocol

Analyzes usage of the new TX relay protocol (Monero PR #9933).

**Metrics:**
- `v1_tx_broadcasts`: Count of NOTIFY_NEW_TRANSACTIONS messages
- `v2_hash_announcements`: Count of NOTIFY_TX_POOL_HASH messages
- `v2_tx_requests`: Count of NOTIFY_REQUEST_TX_POOL_TXS messages
- `v2_usage_ratio`: Percentage of v2 protocol usage

**Interpretation:**
- v2 protocol reduces bandwidth by announcing hashes first
- Mixed v1/v2 usage indicates network transition period
- 100% v1 is expected for older Monero versions

### 6. Upgrade Impact Analysis

Compares network behavior before and after a software upgrade to detect changes in privacy, performance, and connectivity.

**Use Case:**
When testing a new Monero version, run a simulation that:
1. Establishes steady-state with old software
2. Performs rolling upgrades to new software
3. Runs in steady-state with new software

Then use upgrade-analysis to compare pre vs post upgrade metrics.

**Methodology:**
1. Divide simulation into time windows (default 60 seconds each)
2. Calculate all metrics (spy accuracy, propagation, peer count, Gini, stem length) per window
3. Label windows as "pre-upgrade", "transition", or "post-upgrade"
4. Compare pre vs post upgrade using Welch's t-test for statistical significance
5. Generate overall verdict and recommendations

**Input Options:**
- `--manifest <PATH>`: JSON file specifying when each node upgraded
- `--pre-upgrade-end <T>`: Manual override for end of pre-upgrade period
- `--post-upgrade-start <T>`: Manual override for start of post-upgrade period
- `--window-size <N>`: Size of each analysis window in seconds

**Upgrade Manifest Format:**
```json
{
  "pre_upgrade_version": "v0.18.3.3",
  "post_upgrade_version": "v0.19.0.0",
  "upgrades": [
    {"node_id": "miner-001", "timestamp": 300.0, "version": "v0.19"},
    {"node_id": "user-001", "timestamp": 305.0, "version": "v0.19"}
  ]
}
```

**Output:**
- Time series of all metrics per window
- Pre/post upgrade summaries with mean values
- Statistical comparison with p-values
- Overall verdict: Positive, Negative, Mixed, Neutral, or Inconclusive
- Identified concerns and recommendations

**Interpretation:**
- Significant decrease in propagation time = improvement
- Significant increase in spy accuracy = privacy concern
- Significant increase in Gini coefficient = centralization concern
- Mixed results warrant careful review of specific metrics

**Example Output:**
```
METRIC COMPARISON

Metric                    | Pre-Upgrade | Post-Upgrade |   Change | Significant
------------------------- | ----------- | ------------ | -------- | -----------
Spy Node Accuracy         |      52.6%  |       48.2%  |   -8.4%  |         NO
Avg Propagation (ms)      |      89965  |       72340  |  -19.6%  |      YES *
Avg Peer Count            |       22.0  |        24.5  |  +11.4%  |      YES *

ASSESSMENT
Verdict: POSITIVE - Upgrade improved network behavior

Findings:
  - Transaction propagation improved by 19.6% (faster)
  - Network connectivity increased by 11.4%

Recommendations:
  - Upgrade appears safe to deploy
```

### 7. Network Graph (Rust only)

Analyzes P2P connection topology.

**Output:**
- Connection degree distribution
- Inbound vs outbound connection balance
- Time-series snapshots of network state
- GraphViz DOT file for visualization (with `--dot` flag)

## Output Files

All output is written to the `analysis_output/` directory:

| File | Description |
|------|-------------|
| `report.txt` | Human-readable summary |
| `full_report.json` | Complete JSON data |
| `spy_node_report.json` | Spy node analysis details |
| `propagation_report.json` | Propagation timing details |
| `dandelion_report.json` | Stem path reconstructions |
| `upgrade_analysis.json` | Upgrade impact analysis with time series |
| `network_graph.dot` | GraphViz visualization (if `--dot`) |

## Cross-Validation

Both Rust and Python implementations use identical methodologies and produce matching results:

| Metric | Status |
|--------|--------|
| Spy Node Accuracy | Exact match |
| Propagation Timing | Exact match |
| Gini Coefficient | < 1% difference |
| Dandelion Stem Range | Exact match |
| Upgrade Analysis | Same methodology |

This cross-validation ensures the analysis is correct and reproducible.

## Example Workflow

### Standard Analysis

```bash
# 1. Run simulation
./run_sim.sh

# 2. Wait for simulation to complete
# (check shadow.data/hosts/*/monerod.*.stdout for progress)

# 3. Run analysis
./target/release/tx-analyzer full

# 4. View results
cat analysis_output/report.txt

# 5. For detailed data
python3 -c "import json; print(json.dumps(json.load(open('analysis_output/full_report.json')), indent=2))"
```

### Upgrade Impact Analysis

```bash
# 1. Run simulation with upgrade scenario
# (configure nodes to upgrade at specific times)
./run_sim.sh

# 2. Create upgrade manifest (or use manual time boundaries)
cat > upgrade_manifest.json << 'EOF'
{
  "pre_upgrade_version": "v0.18.3.3",
  "post_upgrade_version": "v0.19.0.0",
  "upgrades": [
    {"node_id": "miner-001", "timestamp": 300.0, "version": "v0.19"},
    {"node_id": "user-001", "timestamp": 310.0, "version": "v0.19"}
  ]
}
EOF

# 3. Run upgrade analysis
./target/release/tx-analyzer upgrade-analysis --manifest upgrade_manifest.json

# Or with manual boundaries (if upgrade times are known):
./target/release/tx-analyzer upgrade-analysis \
  --pre-upgrade-end 300 \
  --post-upgrade-start 600 \
  --window-size 30

# 4. View results
cat analysis_output/upgrade_analysis.json | python3 -m json.tool
```

## Troubleshooting

### "Agent registry not found"
Ensure simulation completed and `/tmp/monerosim_shared/agent_registry.json` exists.

### "No transactions found"
Check that transactions were actually sent during simulation. Look for `transactions.json` in the shared directory.

### Different results between runs
Both implementations use deterministic tie-breaking. If results differ, ensure you're analyzing the same `shadow.data/` directory.

### Out of memory
Use `--threads 1` to reduce memory usage for very large simulations.
