# Scaling Test Status

## Current Status: In Progress
**Date:** 2026-01-06
**Last Run:** 2026-01-06 00:05

## Tools Created

### 1. `scripts/generate_config.py`
Config generator for scaling tests.

**Usage:**
```bash
python scripts/generate_config.py --agents 50 -o test_50.yaml
python scripts/generate_config.py --agents 100 --duration 4h -o test_100.yaml
```

**Features:**
- Fixed 5 miners (core network) with hashrates: 25, 25, 30, 10, 10
- Variable users (total - 5) starting at 1h mark, staggered 1s apart
- Default duration: 4h
- Uses GML network topology (matches config_32_agents.yaml)
- Users get `can_receive_distributions: true` for funding
- Includes `enable_dns_server: true` (required for peer connectivity)

### 2. `scripts/scaling_test.sh`
Automated test harness for scaling tests.

**Usage:**
```bash
./scripts/scaling_test.sh
```

**Features:**
- Tests: 50, 100, 200, 400, 800 agents
- 30-minute timeout per test (may need increase for 100+ agents)
- Captures peak RAM via `/usr/bin/time -v`
- Outputs results to `scaling_results.txt`
- Properly handles Shadow's "processes still running" exit condition

## Test Results

### With GML Topology (Current - 2026-01-06)

| Agents | Users | Status  | Peak RAM | Wall Time | Sim Time | Notes |
|--------|-------|---------|----------|-----------|----------|-------|
| 50     | 45    | SUCCESS | 315 MB   | 21:20     | 4h       | Completed with GML topology |
| 100    | 95    | TIMEOUT | 234 MB   | 30:00     | ~2h 43m  | Got to 68%, needs ~44 min total |

### With Switch/Mesh Topology (Earlier Tests - 2026-01-05)

| Agents | Users | Status  | Peak RAM | Wall Time | Notes |
|--------|-------|---------|----------|-----------|-------|
| 50     | 45    | SUCCESS | 320 MB   | ~19 min   | Switch topology, faster but less realistic |
| 100    | 95    | RUNNING | hitting swap | - | Mesh creates O(n^2) connections |

## Issues Fixed

1. **Duration parsing:** Changed from milliseconds to seconds (monerosim doesn't support ms)
2. **DNS server:** Added `enable_dns_server: true` - required for peer connectivity
3. **Exit code handling:** Script checks for "Finished simulation" in logs (Shadow returns 1 when processes still running)
4. **Binary file grep:** Added `-a` flag for grep on shadow logs
5. **Users not funded:** Added `can_receive_distributions: true` to user agents
6. **Network topology:** Changed from switch/Mesh to GML (matches config_32_agents.yaml)

## Key Findings

1. **GML vs Switch topology:**
   - GML is slightly slower but more realistic
   - 50 agents: 21 min (GML) vs 19 min (switch)
   - GML uses proper internet-like latencies and bandwidth

2. **Mesh topology scaling issue:**
   - Mesh creates O(n^2) connections
   - Not recommended for >50 agents (validated in validation.rs)
   - 100 agents with Mesh was hitting swap

3. **Timeout needs adjustment:**
   - 100 agents with GML needs ~44 min (current timeout: 30 min)
   - Scaling appears sub-linear (good news for RAM)

4. **Transaction issue (earlier runs):**
   - Only miners showed transactions because users lacked `can_receive_distributions`
   - Now fixed in generate_config.py

## Next Steps

1. **Increase timeout** for 100+ agent tests (30 min -> 60 min?)
2. **Re-run scaling tests** with fixed config generator
3. **Goal:** Find maximum agent count on 32GB hardware

## Hardware
- RAM: 31GB
- CPUs: 24
- Target: Find maximum agent count before failure

## Notes
- RAM usage appears efficient (~300MB for 50-100 agents)
- Main constraint is wall time, not memory
- GML topology from `gml_processing/caida_connected_sparse_with_loops_fixed.gml`
