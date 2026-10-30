# Per-host peer-list accounting — design spec

Status: design approved in conversation 2026-10-30; spec for review.
Owner artifact track: upstream monerod p2p proposal + lab measurement.
Evidence base: `docs/20261030_monero_p2p_code_map.md` (source dive at v0.18.5.1) and the
2026-09-23 crawl aggregates therein.

## 1. Problem

Peer-list entries are keyed by full address (ip:port) end to end: storage (unique index
`by_addr`), trimming, and the gossip head all count ports. The measured fleet holds 12,368
endpoints on 1,941 IPs (median 7 ports per IP, max 11), so per paid address it occupies ~6.4
entries in every white list that carries it and ~6.4x its fair share of every 250-entry gossip
head. The connection pick already collapses ports (`make_new_connection_from_peerlist` keeps
one candidate per host "to avoid ... advertising on a large number of ports"), and inbound
fan-in per host is capped (`has_too_many_connections`). The lists and the gossip channel are
the remaining port-multiplied surfaces.

## 2. Goal / non-goals

**Goal:** make the host the unit of account in the peer lists and the gossip head, so an
address's list footprint is independent of how many ports it opens. Deployable by upgrade
alone; no new messages, no consensus, no coordination.

**Non-goals:** changing the pick, Dandelion++, promotion, trim order, or bans; reducing the
fleet's address-base share (that is the /24 dedup's and the admission-cost axis's job);
detecting proxies (identity binding is a separate candidate).

## 3. The change (upstream semantics)

Two rules, one invariant: at most N entries per host, per list.

- **R1 (lists).** In white and in gray, at most N ports per IP; N=1. On insert that would
  exceed the cap, the newest same-host entry wins and the oldest same-host entry is dropped
  (same host_str as the pick's host-dedup uses; ipv4 and v4-mapped ipv6 both collapse to the
  IP). Applies at the three insert sites: gossiped gray merge, gray->white promotion, and
  white refresh of a different port of a known host.
- **R2 (gossip).** `get_peerlist_head` returns at most one entry per host within its 250
  (independent of R1, so the send side is fixed even against a mixed-version network).

Anchor list: unchanged (2-slot reconnect list; the pick's host-dedup already bounds its
usefulness to a multiplier).

Promotion when the host is at cap: the promoted (just-contacted) port replaces the host's
oldest white entry — contact always wins over stale entries, so no reachable port is ever
denied promotion by its own older ports.

Defaults: N=1. Fallback if the honest multi-node-per-IP cost is judged too high upstream:
N=2 (halves the measured multiplier; the lab cells read both).

## 4. Honest cost

The only pattern affected: several daemons on one IP (NAT, multi-daemon VPSes). The extra
ports lose *list presence* (white entry, gossip advertisement), not connectivity — they still
dial out, accept inbound, relay, and sync. Quantified in the lab cells (below): honest
occupancy gain vs any honest-connectivity regression, using the Finding 5 methodology
(failed dials per relay-hour, refill time, unfilled sessions).

## 5. Adversary analysis

Ports become free-loading no more: the fleet's list footprint drops from 12,368 network-wide
to at most 1 per address per list, matching the axis the /24 dedup already prices. Evasion
requires more addresses, which is exactly the scarce, /24-capped, costable unit. The defense
does not attempt to shrink the address base (28% of the reachable address universe) — it
removes the 6.4x multiplier on it. Residual exposure (the /24 slot share) is the candidate-1
and admission-cost axes' territory.

## 6. Lab implementation

**Sim patch** (`monero-sim-peerlist-ports-per-host.patch`, next in the R-series; default off =
stock): one flag `--sim-peerlist-ports-per-host N` (0 = stock infinity). R1 at the
`append_with_peer_white` / `append_with_peer_gray` / merge sites; R2 inside
`get_peerlist_head`. One MGINFO line when nonzero. No other behavior touched.

**Generator** (`make_lean.py`): `--spy-ports P` (tag `_pt{P}`), placing P spy daemons per spy
IP (same topology node, distinct ports), so `--spies-per-subnet` counts IPs per /24 and the
endpoint count is spies x P. Open item for the implementation plan: verify the harness and
scenario format support two daemons on one topology node with distinct ports, and how ports
are assigned (the expand step must not collide them). If the harness cannot, fall back to
P=2-3 modeled via shared-port daemons is NOT acceptable; the plan resolves this first.

**Cells** (filed as predictions before queueing, per the journal's standing rule):
- Main pair: `k9` spread fleet (the real layout), `--spies-per-subnet 7 --spy-ports 7` -> 63
  spy IPs, 441 endpoints, against 300 honest daemons (1 port each); stock vs `N=1` on the
  treatment arm, plus an `N=2` arm. Fleet endpoint:honest endpoint 441:300 approximates the
  mainnet 2.2:1 direction at lab scale; the read is the within-cell stock-vs-capped delta, so
  the ratio constants matter less than the multiplier 7.
- A `k42 m1 pt7` spread arm checks the interaction with the lab's standard layout.
- Baselines: the same cells with `pt1` (no port multiplication) bound the pure-listing effect.

**Metrics:** light share vs the cell's own `model_out` (the standing series); fleet share of
honest white lists and of gossip heads (from the peerlist-dump patch's dumps — no new
census); sp recall/precision and exposure at mainnet sender rate (X1a shape) on the main
pair; honest-connectivity health per Finding 5.

**Success criteria (pre-registered at filing):** the capped arm's fleet white-list share drops
by roughly the port multiplier relative to stock (toward the `pt1` baseline's share); honest
white occupancy rises by the displaced entries; no honest-connectivity regression beyond the
Finding 5 tolerance; attribution metrics move only as list position moves (first-hop access
is untouched by design — a null result on sp recall is the *expected* outcome and is itself a
finding: the multiplier is a list-occupancy attack, not an attribution channel).

## 7. Upstream artifact

A short proposal + PR sketch: the crawl numbers, the pick-path precedent comment, the NAT
trade-off, N choice with the N=2 fallback, and the lab deltas. Published at the owner's call
only (standing no-GitHub rule; internal docs until then).

## 8. Risks / open questions

- Harness multi-daemon-per-node support (resolves in the implementation plan, before any
  patch work).
- Same-host different-port promotion races (two ports promoting concurrently): the cap check
  must hold the peerlist lock it already holds; state it in the patch.
- Gray-list starvation of honest entries behind a churning same-host set: bounded because the
  gray cap N applies per host; watch in cells.
- IPv6 native (not v4-mapped) hosts: host_str already handles them; no extra rule.

## Appendix A — correction, 2026-10-30 (post code-read, pre build)

The dive's first pass missed that stock already enforces the white-list half: every new white
insert calls `evict_host_from_peerlist(true, ple)` (`net_peerlist.cpp:294` -> `filter`, erasing
ALL same-host entries), and `is_same_host` is IP-only (`net_utils_base.h:83`). **The white list
has been one-entry-per-host since >= 2021-07-27.** So R1-white was already stock and R2
(gossip one-per-host) is vacuous (gossip samples a one-per-host white list) - both dropped.

What the port front actually buys is the **gray-side freshness pump**: gray has no host dedup;
fleet endpoints keep siblings parked in victims' gray lists; gray housekeeping probes a uniform
random gray peer; each successful probe promotes that port to white (evicting the prior
same-host entry) with a fresh last_seen - the host's single white slot never goes stale. This
is E21/E35's "refreshed only when a node dials them," industrialized across ports.

**Revised defense (approved 2026-10-30):** `--sim-peerlist-ports-per-host N` (0 = stock)
enforces (a) gray capped at N entries per host, newest kept, oldest-by-last_seen dropped on
insert, and (b) on white insert of a new address, all same-host gray entries are erased, so
the rotation reservoir cannot refill while the host holds a white slot. Tests re-targeted to
gray; a baseline test pins stock's one-per-host white behavior. Cells unchanged.
