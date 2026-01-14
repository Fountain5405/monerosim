# Data Sources

This document lists the external data sources used in MoneroSim for network topology and IP allocation.

## IP Address Allocations

### IANA IPv4 Address Space Registry

**Source:** https://www.iana.org/assignments/ipv4-address-space/ipv4-address-space.xhtml

**Used in:** `src/ip/as_manager.rs`

**Purpose:** Assign realistic IP addresses to simulated agents based on their geographic region.

**Allocations by Regional Internet Registry (RIR):**

| RIR | Region | First Octets |
|-----|--------|--------------|
| ARIN | North America | 3, 4, 6, 7, 8, 9, 13, 15, 16, 18, 20, 23, 24, 50, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 96, 97, 98, 99, 100, 104, 107, 108, 192, 198, 199, 204, 205, 206, 207, 208, 209, 216 |
| RIPE NCC | Europe | 2, 5, 25, 31, 37, 46, 51, 53, 57, 62, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 109, 141, 145, 151, 176, 178, 185, 188, 193, 194, 195, 212, 213, 217 |
| APNIC | Asia-Pacific | 1, 14, 27, 36, 39, 42, 43, 49, 58, 59, 60, 61, 101, 103, 106, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 133, 150, 153, 163, 171, 175, 180, 182, 183, 202, 203, 210, 211, 218, 219, 220, 221, 222, 223 |
| LACNIC | Latin America | 177, 179, 181, 186, 187, 189, 190, 191, 200, 201 |
| AFRINIC | Africa | 41, 102, 105, 154, 196, 197 |

**Note:** We use a subset of each RIR's allocations (typically 6-20 first octets) to balance diversity with simplicity.

---

## Network Topology

### CAIDA AS-Links Dataset

**Source:** https://www.caida.org/catalog/datasets/as-relationships/

**File:** `gml_processing/cycle-aslinks.l7.t1.c008040.20200101.txt`

**Used in:** `gml_processing/create_caida_connected_with_loops.py`

**Purpose:** Provides Autonomous System (AS) connectivity data from real Internet measurements.

**Data format:**
- `I` lines: Indirect AS links
- `D` lines: Direct AS links
- Relationship types: `-1` (customer-provider), `0` (peer-peer), `-2` (sibling)

**Processing:**
1. Parse AS-links to build undirected graph
2. Extract largest connected component (up to N nodes)
3. Renumber AS numbers to 0-N for Shadow compatibility
4. Add self-loops for local routing
5. Apply region-based latencies (see below)

---

## Inter-Region Latencies

**Source:** Derived from submarine cable distances and published RTT measurements

**References:**
- WonderNetwork Global Ping Statistics: https://wondernetwork.com/pings
- Submarine Cable Map: https://www.submarinecablemap.com/
- Verizon Enterprise Latency Maps

**Used in:** `gml_processing/create_caida_connected_with_loops.py`

**Latency values (one-way, milliseconds):**

| Route | Latency | Notes |
|-------|---------|-------|
| Intra-North America | 25ms | US coast-to-coast |
| Intra-Europe | 15ms | Geographically smaller |
| Intra-Asia | 40ms | Spans huge distances |
| North America ↔ Europe | 45ms | Transatlantic cables |
| North America ↔ Asia | 90ms | Transpacific cables |
| Europe ↔ Asia | 75ms | Multiple routes |
| North America ↔ South America | 60ms | |
| Europe ↔ Africa | 45ms | Mediterranean route |
| Asia ↔ Oceania | 55ms | Relatively close |
| Europe ↔ Oceania | 140ms | Longest common route |
| Asia ↔ South America | 150ms | Longest route |

---

## Regional Bandwidth

### Ookla Speedtest Global Index

**Source:** https://worldpopulationreview.com/country-rankings/internet-speeds-by-country

**Primary Data:** Ookla Speedtest Global Index (2025) via World Population Review

**Used in:** `gml_processing/create_caida_connected_with_loops.py`

**Purpose:** Assign realistic bandwidth values to simulated nodes based on their geographic region.

**Regional median download speeds (Mbps):**

| Region | Median | Std Dev | Min | Max | Key Countries |
|--------|--------|---------|-----|-----|---------------|
| North America | 250 | 80 | 50 | 1000 | US 303, Canada 256, Mexico 92 |
| Europe | 170 | 60 | 30 | 500 | France 346, Germany 102, UK 163 |
| Asia | 130 | 90 | 15 | 500 | Singapore 407, Japan 230, India 62 |
| South America | 160 | 70 | 20 | 400 | Chile 357, Brazil 220, Argentina 110 |
| Africa | 28 | 20 | 5 | 100 | Egypt 92, South Africa 48, Nigeria 31 |
| Oceania | 70 | 50 | 10 | 300 | New Zealand 216, Australia 164, Fiji 13 |

**Bandwidth model:**
- Node bandwidth sampled from truncated normal distribution per region
- Upload/download asymmetry modeled (typical ratio 20-80%)
- Edge bandwidth based on CAIDA relationship type with 5x aggregation multiplier

**Additional references:**
- Carrier Bid asymmetric bandwidth analysis: https://www.carrierbid.com/different-upload-download-speeds/
- Typical upload:download ratio is 1:10 for cable/DSL, 1:1 for fiber

---

## Monero P2P Network

### Connection Limiting Mechanisms

**Source:** Monero source code (`src/p2p/net_node.inl`, `src/p2p/net_node.cpp`)

**Repository:** https://github.com/monero-project/monero

**Key findings:**
1. `max_connections_per_ip`: Default 1 connection per IP address
2. `/24 subnet deduplication`: Prefers peers from different /24 subnets when making outgoing connections
3. Subnet mask: `0xffffff00` (255.255.255.0)

**Used in:** `src/utils/validation.rs` (validate_ip_subnet_diversity)

---

## Future Data Sources

See `TODO/ripe-atlas-as-latency.md` for planned integration with:
- RIPE Atlas measurement data
- AS-to-AS latency measurements
- Google BigQuery integration for bulk data access
