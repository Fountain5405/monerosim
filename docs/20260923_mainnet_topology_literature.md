# Monero mainnet P2P topology: literature and replica targets

**Date:** 2026-09-23
**Status:** Research complete. This document is the sourced basis for the
mainnet-replica scenario (`docs/superpowers/specs/2026-09-23-mainnet-replica-design.md`).
It extends `docs/20260618_mainnet_topology_targets.md`, which already covers the
reachable fraction, stock connection parameters and connection-duration targets.
Every number here carries its source and measurement date. Numbers the replica
derives rather than measures are marked *derived*.

## 1. Sources

| # | Source | Measured | Method |
|---|---|---|---|
| S1 | Cao, Yu, Decouchant, Luo, Veríssimo, *Exploring the Monero Peer-to-Peer Network*, FC 2020 ([eprint 2019/411](https://eprint.iacr.org/2019/411.pdf)) | Dec 2018 – early 2019 | Own nodes with 99,999 in/out caps, plus NeighborFinder (infers concurrent outbound neighbours, including unreachable nodes, from peerlist timestamps) |
| S2 | Gao, Piškorec, Zhang, Vallarano, Tessone, *Charting the Uncharted: The Landscape of Monero P2P Network* ([arXiv 2504.15986](https://arxiv.org/abs/2504.15986)) | 21 Dec 2024 – 10 Jan 2025 | Three monitors (US, EU, SG) on 18080; neighbours inferred from peerlists by k-means (timestamps removed from the protocol after 2019) |
| S3 | Gao, Zhang, Piškorec, Tessone, *Monero Peer-to-peer Network Topology Analysis* ([arXiv 2504.17809](https://arxiv.org/abs/2504.17809)) | same data as S2 | Degree, assortativity, k-core analysis of the S2 graph |
| S4 | Kopyciok, Schmid, Victor, *Friend or Foe? Identifying Anomalous Peers in Monero's P2P Network* ([arXiv 2509.10214](https://arxiv.org/abs/2509.10214)) | 240 h, Feb 2025, 5 vantage points | Traffic capture; 8 anomaly heuristics |
| S5 | ProbeLab, [*Peering into Privacy*](https://probelab.io/blog/peering-into-privacy-a-deep-dive-into-the-monero-network-topology/) | 24 Feb 2026 crawl | Nebula crawler from AWS us-east-1 |
| S6 | Boog900, [research-lab #126 "preventing P2P proxy nodes"](https://github.com/monero-project/research-lab/issues/126) | Oct 2024 | Protocol-deviation fingerprinting |
| S7 | Rucknium / Boog900, [meta #1124 MRL spy-node ban list](https://github.com/monero-project/meta/issues/1124), v2 Jan 2026; [ban_list.txt](https://raw.githubusercontent.com/Boog900/monero-ban-list/refs/heads/main/ban_list.txt) | Dec 2024, Jan 2026 | Subnet saturation, LinkingLion overlap |
| S8 | Monero v0.18.4.3 "Fluorine Fermi" [release notes](https://www.getmonero.org/2025/10/08/monero-0.18.4.3-released.html) | Oct 2025 | /24 subnet deduplication in peer selection |
| S9 | monerod v0.18.5.1 source (`../monero`, tag `v0.18.5.1`), the version monerosim pins | — | Code reading |
| S10 | `docs/20260618_mainnet_topology_targets.md` and `docs/20260620_network_topology_study.md` (this repo) | — | Earlier sourcing plus the validated sweep |
| S11 | Kirschner, *An Analysis of Monero's Network Topology*, IEEE DAPPS 2026 (DOI 10.1109/DAPPS69803.2026.00019; local copy `~/monerosim_scale/An_Analysis_of_Moneros_Network_Topology.pdf`) | one week in **2022** (per the user; the paper does not state it) | 11 VPN vantage points; edges = white-list peerlist adjacency gathered by iterative seed queries (not live connections) |
| S12 | Rucknium, [xmrnetscan](https://xmrnetscan.redteam.cash/) ([source](https://github.com/Rucknium/xmrnetscan)) — MRL daily network scan | daily since ~Jul 2025 (Jan 2026: ban list v2, hidden-spy counts) | Rust crawler on Cuprate's Levin handshaker from the hardcoded seeds; per node: pruning seed, peer id, support flags, disseminated peerlists; spy labels = MRL ban lists v1/v2, DNS blocklist, private fingerprint; ban-list adoption inferred from disseminated lists; Team Cymru ASNs. Data reachable only through the Shiny UI (the `plumber` API in the repo is not publicly exposed; no releases). **Requested from the author 2026-09-23.** |
| S13 | **Our own crawl + node poll**, `~/basement_monerosim/20260923_mainnet_observation/` (`analysis/mainnet/`) | 2026-09-23 | One Levin handshake per advertised ip:port seeded from a LAN mainnet node's peerlists (39,885 probed, 45 min); Team Cymru ASNs; MRL ban list v2 of that day |

## 2. Degree structure: hubs and periphery

- **Degree classes (S1, Table 2).** Classified by concurrent *outgoing*
  connections: light (≤8, the 2018 default) **86.8%** (3,146 nodes),
  medium (8–250) **12.5%** (452), heavy (>250) **0.7%** (28), out of
  3,626 reached active nodes; another 703 active nodes were never reached.
  The light nodes hold only **17.14%** of connections; the other **13.2% hold
  82.86%**. Degrees follow a power law, and the heaviest node held
  **>1,000** connections.
- **Who the heavy nodes are (S1).** Of 28 heavy nodes: **9 mining pools, 2 seed
  nodes, 17 unidentified** ("likely front-end nodes of private mining pools").
  Only 3 of the 8 hard-coded seeds were active at the time.
- **Hubs today (S2, S3).** The largest connected component has **4,837** nodes.
  **14** top-degree nodes are directly linked to **3,153** of them (**82.1%**).
  They are described as mostly public seed nodes or supernodes. Hubs share
  **>91%** of their neighbours (9 of 14 near 100%) but connect to the periphery
  rather than to each other.
  - Assortativity is **−0.28** (disassortative).
  - The densest k-core (k=16) has **178** peers.
  - Removing the 14 hubs shrinks the largest component by **20%**. It collapses
    at **9.4%** removal by betweenness or **12%** by degree.
- **Scaled hub share (derived).** 14/4,837 = **0.29%** (S2) and 28/3,626 =
  **0.77%** (S1). The replica uses **0.5%**, inside that band. It also keeps
  continuity with the 5-supernode runs validated in S10.

### Discrepancy: 8 versus 12 outbound

S1–S3 quote a default of **8** outgoing connections. monerod v0.18.5.1 has
`P2P_DEFAULT_CONNECTIONS_COUNT = 12` (S9, `src/cryptonote_config.h`), and
in-peers is unlimited by default (S10). The 8 comes from the 2018 protocol.
The replica uses **12**. So a light node today is ≤12, and "medium" means
raised above the default.

## 3. Reachability and inbound load

The 2018–2026 targets are carried over from S10 unchanged:
- **~15% reachable / ~85% unreachable** (triangulated from S1's degree skew,
  Rucknium's 50–100 inbound per reachable node, and 12/R arithmetic).
- Reachable nodes carry **50–100 inbound**.
- Median connection duration is **~23 min**, and **~1.5% / ~0%** of
  outbound / inbound connections last more than 6 h. S10 reproduced this at
  15% reachable with 1 h on / 1 h off turnover and 5 always-on supernodes.

S5's crawler-visible ratios (about 60% TCP-reachable of discovered
`IP:port`s) measure something else. They undercount NAT'd nodes, which never
enter peerlists. See S10 §2.

## 4. The spy population

Spies are a moving target. Share of reachable IPs by period:

| Period | Spy share | Size and shape | Source |
|---|---|---|---|
| Oct 2024 | **~40%** of IPs "are not real nodes" | **1,900** proxy IPs in **6** /24s (91.198.115, 100.42.27, 162.218.65, 193.142.4, 199.116.84, 209.222.252) plus secondary ranges | S6 |
| Feb 2025 | **14.74%** anomalous (1,924 of 13,050 IPs); conservative heuristics | one entity controls **≥1,582** nodes in **seven** /24s | S4 |
| Jan 2026 | ban list v2 after spies "switched to different IP address ranges" in Dec 2025 | **4,001** addresses in **336** distinct /24s: **14** fully banned /24s (~3,600 addrs) plus a long tail of 322 /24s with 1–3 IPs (one with 60) | S7, counted from `ban_list.txt` 2026-09-23 |
| Feb 2026 | **81.6%** (13,420 of 16,454 handshaking nodes), all in AS Spruce Creek Networks | honest reachable ≈ **2,944** | S5 |

Spy behaviour:
- **Spies are proxies.** "Proxying a few nodes through a large number of IP
  addresses" (S7).
  - S5 fingerprint: the peer ID in the handshake differs from the one returned
    to a ping, which is routed to a different backend or given a fresh ID.
  - S6 fingerprint: spies send `REQUEST_SUPPORT_FLAGS` (1007), which stock
    monerod never sends, and appear to be custom software.
  - S4 fingerprint: omitted support flags, deprecated timestamps, TCP
    fragmentation, low peerlist diversity (<10 subnets among 250 peers) and high
    cross-IP peerlist similarity.
- **Spy footprint at honest nodes (S4, Feb 2025, before deduplication).**
  - Anomalous peers held **20.37%** of inbound and **15.26%** of outbound
    connections.
  - An average peerlist was **16.93%** non-standard, and every full peerlist
    contained some.
  - With the ban list enabled, outbound exposure fell to **7.13%**.
- **Ban-list adoption (S5).** **46.2%** of legitimate nodes use it (8.5% of
  all nodes).
- **Countermeasure in our binary (S8, S9).** v0.18.4.3 added /24 deduplication.
  In v0.18.5.1, `net_node.inl` builds `connected_subnets` from **all current
  connections, inbound included**, and outbound candidate selection skips any
  /24 already present. It falls back to no deduplication only when nothing
  else is available. Consequences:
  - An honest node holds at most about one outbound connection per spy /24.
  - A spy that dials *in* also uses up its /24 for that node's outbound choices.
  - The spies' Dec 2025 move to many new ranges fits adapting to this filter.

## 4a. Kirschner (S11): the peerlist view

- **Scale:** 20,560 active nodes, 10,626,886 peerlist edges, 2,116 ASes, 8,387
  BGP prefixes, 141 countries; 31,684 IPs discovered before filtering.
- **Spies from a third angle.** **4,840 nodes (24%)** return peerlists larger than
  the 1,000-entry white-list maximum (half send >1,500; 468 send >2,000). They
  hold **67%** of all edges, are adjacent to **99%** of the network, and 57% of
  them sit in **43 ASes** (5% of ASes); 5% of BGP prefixes hold 55% of them.
  This is the fleet S4–S7 describe, seen through its oversized peerlists.
  - *To verify before modelling:* stock monerod may drop a peer that sends more
    than `P2P_MAX_PEERS_IN_HANDSHAKE` (250) entries. If so, the oversized lists
    only reach crawlers and custom software, not honest nodes.
- **Honest concentration.** 86% of nodes sit in 14% of ASes; **12% of BGP
  prefixes hold 55% of nodes**. Derived: the dense 12% of prefixes average
  about **11 nodes per prefix**, the rest about 1.25. A BGP prefix is often
  wider than a /24, so per-/24 density is lower than 11; treat 11 as an upper
  bound.
- **Geography:** US **33%**, Germany **>10%**, US+DE 46%. Matches S1's 2018 US
  figure exactly.
- **Structure:** modularity **0.088** (greedy) / ~0 (random walk): no community
  structure. Degree stats (mean 517, median 667, p90 1,750) are peerlist
  adjacency and are **not comparable** with connection degree.
- **Parameters quoted:** 8 out / unlimited in as the default (the old value; see
  §2), and a "production-recommended" **64 out / 1,024 in**, which supports
  the medium class's 64-out sub-group.

## 4b. Our measurement (S13, 2026-09-23)

- **Reachable:** 18,026 of 39,885 probed (failures: 12,925 timeouts, 7,030
  refused, 1,902 unreachable, 2 protocol).
- **Spies: 73.7% of reachable IPs** are on the MRL ban list; **68.6%** show the
  S5 peer-ID mismatch, and every mismatching node is also on the ban list; only
  3.2% omit support flags. **13,281 spy IPs in 63 distinct /24s** (~210 per
  /24), **99.6% in AS401476 Spruce Creek Networks**. So the 2026 shape is "63
  dense /24s", not the ban list's "14 dense + tail" (the ban list covers 4,001
  addresses; the fleet is 3× larger).
- **Honest reachable ≈ 4,745.** ASNs: DigitalOcean **44.6%**, OVH 6.5%,
  Hetzner 3.6%, Limestone 3.6%; countries: **US 64.1%**, DE 8.9%, LT 3.1%,
  FR 3.0%, NL 1.7%, CA 1.6%, GB 1.6%, RU 1.5%, SG 1.5%, AU 1.2%.
- **Honest /24 sharing:** 3,732 /24s hold the 4,745 honest nodes (mean 1.27);
  the densest 12% of /24s (448) hold **30.8%** (~3.3 per dense /24). This is
  the per-/24 counterpart of S11's per-BGP-prefix 55%: **the replica's
  `prefix_sharing` should be `fraction 0.31, per_prefix 3`.**
- **Peerlist adjacency** (each node's returned 250-entry list as edges):
  mean degree 202, median 153, p90 449; top 13.2% of nodes hold 31.6% of
  edges; the top 14 are adjacent to 17.4% of nodes. Not comparable with S2's
  inferred-connection graph (our edges are advertisements, not links).
- **LAN node (poll, first 48 ticks, ban list enabled):** 36 inbound / 12
  outbound; 0 spies in its slots and peerlists; completed-connection medians
  outbound 18 min, inbound 10 min (early, small n); some inbound connections
  alive >1 week.

## 5. Geography and hosting

- **By class (S1, 2018).** No later source publishes numbers, and S5 only says
  "heavy concentrations in North America and Europe".
  - Light nodes: USA 33.32, DE 7.68, RU 6.54, CN 5.87, CA 4.70, FR 3.49,
    NL 2.38, AU 1.84, other 34.18 (%).
  - Heavy nodes: USA 50.00, FR 17.87, DE 10.71, then UA, SK, PT, JP, FI and
    CN at 3.57 each.
- **Replica region weights (derived, low confidence).** Group S1's named light
  countries by region: NA 38.0, EU 20.1, Asia 5.9, Oceania 1.8. Allocate the
  unnamed 34.2% proportionally. The result is **NA 58 / EU 30 / Asia 9 /
  Oceania 3 / South America 0 / Africa 0**. Region only affects latency in the
  simulator, a second-order effect on topology.
- **Honest hosting (S5, spies excluded).** Hetzner, DigitalOcean and OVH lead,
  each at ≤2% of all nodes. **30%** of honest nodes expose reachable RPC, and
  **8.1%** of all nodes are pruned.

## 6. Out of scope for a Shadow replica, and why

| Feature | Reason |
|---|---|
| Pruned nodes (8.1%) | Pruning only touches blocks >5,500 below the tip (`CRYPTONOTE_PRUNING_TIP_BLOCKS`, S9); sim chains reach a few hundred blocks, so it is a no-op |
| Tor / I2P zones, IPv6 | Not modelled by the simulator's network |
| Software-version mix | No source publishes it. Implementation mix is available separately via `node_implementations` |
| Remote-node (RPC) wallet usage (30% expose RPC) | A privacy question for stage 3, not a topology parameter |

## 7. How literature numbers compare with simulator numbers

All published graphs are **inferred**. Neighbour-inference accuracy was 69–83%
in S2 and 94–98% in S1. The simulator gives **ground truth** from its logs. So
the stage-2 comparison should use shape and ratio metrics (class shares, hub
coverage, assortativity sign and size, spy slot shares), not absolute edge
counts.
