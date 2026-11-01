> Status: current — patch committed (b051d548), logic validated, unbuilt on the boxes at 2026-11-01.

# Identity-consistency enforcement (observational layer) — design spec

Status: design approved in conversation 2026-10-31; spec for review.
Track: upstream monerod p2p policy (pure local, no wire changes) + lab measurement.
Evidence base: `docs/20261030_monero_p2p_code_map.md` (id generation/carriage verified at the
pin); the 2026-09-23 crawl (12,368 flagged endpoints, shared-id/proxy signature); RTT scoring
measured dead (fleet median 220 ms, better than honest 472 ms).

## 1. Problem

The real fleet fronts few backing monerods with 12,368 endpoints. Stock already carries the
evidence of this to every node — handshakes present a 64-bit id over a socket you opened to a
specific address, gossip and self-advertisements carry (address, id) — but nothing enforces the
one-id-one-address invariant. A byte-multiplexing front therefore costs almost nothing per
endpoint. Withdrawn alternatives: age-gating (requires external ban lists — rejected by the
owner); RTT scoring (fleet outperforms honest nodes on latency).

## 2. Goal / non-goals

**Goal:** monerod enforces, from its own direct observations alone, that a peer id occupies at
most one address at a time and that an address's advertised self-id matches its handshake id.
No wire changes, no coordination, public zone only, protection by upgrade.

**Non-goals (framed as the escalation path):** signed self-bindings (node keypair; kills
framing class entirely; wire change); per-identity recurring work commitments (prices the
per-endpoint-id evasion); any identification infrastructure.

## 3. The rules

- **R1 (shared id).** Direct observation only: if ids seen at >=2 distinct addresses within a
  grace window (parameter G, default 24 h) — from my own handshakes, ping-backs, or a peer's
  self-advertisement over our connection — then all white entries carrying that id except the
  freshest-observed address are demoted to gray, and the id's other addresses are refused white
  promotion while the pattern persists. Hearsay (third-party gossip entries) NEVER triggers R1.
- **R2 (self-contradiction).** If a peer's self-advertised (address, id) over a connection
  contradicts the id it presented in the handshake on that connection, demote and refuse
  promotion. Direct by construction.
- **Egress hygiene:** offending entries are not re-gossiped (a node never propagates an
  (address, id) it believes inconsistent).
- **Zone scope:** public zone only (non-public zones share a constant id in stock).
- **Restarts are safe by construction:** rules are address-keyed against simultaneous presence;
  an honest id change at the same address triggers nothing. Honest dynamic-IP migration is
  covered by G.

## 4. Adversary analysis

- Shared-id front (the measured fleet): collapses in every enforcing node's lists from
  endpoint-count to backing-count occupancy. Predicted light share falls from the fleet's
  usual levels toward one backing id's single-slot share.
- Per-endpoint-id front (the evasion): unaffected observationally — the defense's bound, priced
  by the escalation layers (signed bindings, per-identity work), not oversold here.
- Framing (gossiping a victim's id with fake addresses): inert — R1 requires direct
  observation; an attacker cannot make me directly observe an id at an address I did not
  connect to and that did not connect to me presenting it.

## 5. Lab implementation

- **Sim patch** (`monero-sim-id-consistency.patch`, 16th in the series, default off):
  `--sim-enforce-id-consistency G_hours` (0 = stock) implementing R1+R2+egress at the
  handshake/ping/timed_sync observation points and the white-promotion gate; a small id->(addr,
  seen) evidence map on node_server, public zone only.
- **Fleet mode** (same patch): `--sim-shared-spy-id` forces every spy's m_peer_id to one
  constant — the real fleet's shape. One line at the id-generation site.
- **Cells (k42 m7 layout, matching the running series):** S1 shared-id stock (the real fleet
  under today's rules; P68), S2 shared-id enforced (the headline; P69), S3 per-endpoint-id
  enforced (the evasion bound; P70). Baseline for S3 is I1, already running. k9 pair optional
  after the trio reads.
- **Success criteria (pre-registered at filing):** S1 within noise of I1 (the shared-id flag is
  inert under stock); S2's light collapses toward a single id's slot share (~0.004-0.02) and
  spy stem receipts fall accordingly; S3 within noise of I1 (enforcement inert against
  per-endpoint ids — the design's honest bound); no honest-connectivity regression beyond the
  Finding 5 tolerance.

## 6. Risks / open questions

- Evidence-map memory bound (id count): capped by observed ids (~ tens of thousands), trivial.
- The grace window's honest-migration coverage under churn: the churn cells (to1h1h series)
  re-run later with enforcement on.
- Whether demote-to-gray suffices or the egress rule starves the fleet's gossip faster than
  local demotion does: the cells read both (list share and gossip share at probe nodes).
