# X3b design: the adversary's strategies against stemmable inbound stems

Written 2026-10-28 — the design pass the 07:45 decision row called for
("the X3b adversary-strategy poles need a spy-side design pass and follow
these reads"). Predictions are filed with the cells, after E63/E64 land.

## The question

E62/X3a measured the lab-rate ceiling at shipped defaults, with EVERY inbound
connection stemmable (the empty-cidrs universal bound: the honest fabric and
the spies all "paid"). Tevador's #160 closing ask is the adversary against the
deployed feature. Three levers separate from that bound:

1. **The fleet's IP layout.** OQ8's identification: the real fleet sits in
   EIGHT dense /24s and rotates its addresses weekly. The /16 bucketing
   (one virtual per /16, cap 12) treats density and spread differently:
   42 spread /16s buy 42 bucket chances; 8 dense /16s buy 8.
2. **Who pays.** `--sim-stemmable-cidrs` models the paid set. Honest-only
   adoption, fleet-only adoption, or both are different deployments; a
   fleet-only feature (honest nodes ignore it, spies pay) is the case the
   guarantee must survive alone.
3. **The inbound-only isolation.** In every cell so far the spies are
   ordinary reachable peers — they receive stems through the normal outbound
   draw too, which confounds any stemmable-re-entry read. Spies that never
   appear in an honest white list (hide-my-port on the spy daemon) receive a
   stem ONLY through an X3 virtual, so their stem receipts become the
   re-entry rate directly.

## The poles (cells queued after the E63/E64 reads)

- **X3b-dense (layout pole).** The real fleet's shape: ~42 spies in 8 dense
  /24s (5-6 each), full take-up (empty cidrs), spread fleet otherwise as
  X3a. Question: does the /16 bucketing neutralize density — 8 buckets
  against the union — where spread bought 42? Read against the dense passive
  baseline (the E24/E30 family, ceiling ~0.032) and X3a's spy stem receipts.
- **X3b-pay (payment pole).** X3a's spread cell with the cidrs file naming
  ONLY the spies' /24s: the honest fabric does not run the feature, the
  fleet pays. Question: does paying re-open the first hop when nobody else
  adopts? The union's virtual side is all-spy, so edge 2's bucket lottery is
  spy-vs-outgoing-/16s. Read: spy stem receipts and sp recall against E27
  (stock) and X3a (universal).
- **X3b-hidden (isolation pole).** The spread fleet with inbound-only spies,
  run twice: empty cidrs (universal adoption) and cidrs = spy /24s
  (fleet-only). Every spy stem receipt is then a stemmable re-entry — the
  cleanest possible read of what paying buys, and of what the guarantee
  concedes. Control clause: hidden spies with the feature OFF receive ~no
  stems at all.

## Generator surgery (small, mechanical; no monerod change)

1. `--spy-hidden` (tag `_sph`): `hide-my-port: true` on the spy groups —
   one line in the spy block. The spies keep their outbound dials
   (`add-exclusive-node` to a seed), so their connections stay inbound at
   the relays; they drop out of every honest white list.
2. `--stemmable-cidrs` (tag `_sc`): make_lean computes the /24s its own
   placement math gives the spies (sequential from `--spy-node0`) and writes
   `cells/cidrs_<stem>.txt` (one a.b.c.d/24 per line), then passes the
   absolute path via `{"sim-stemmable-cidrs": path}` on the fabric groups —
   the ban-list staging pattern (one shared file, absolute path; hosts read
   it at init). The R7-fixed patch parses it; with a malformed line it now
   skips instead of crashing.

## Metrics and reading rules (pre-registered with the cells)

- Primary: stem receipts at spy nodes (spy-side `rx`, fluff false, from the
  txrelay log) — what the adversary buys, per layout and per payment side.
- Secondary: sp precision/recall on users (does re-entry BUY attribution?),
  light share against the layout's own ceiling, and the `x3` census
  (`adhoc/x3_census.py`: union size, virtual shares, relayed stems at users).
- Clauses fixed now: X3b-hidden OFF ≈ zero spy stems (isolation sanity);
  X3b-dense's passive-adjacent read sits near the dense ceiling, not the
  spread one.

## Costs

Both generator changes are one-liners plus a file writer. Cells are X3a-sized
(~145 m on tr; the dense cell's wall should match — same fleet size). The
X3b cells pass a cidrs file, so they need the R7-fixed binary: rebuild each
box when its queue empties (tr after P54 scores, simbox3 after P53 scores).

## Corrected 2026-10-28 18:15 — the fleet's connection direction

The "generator surgery" above assumed the spies' connections sit inbound at
the relays ("the spies keep their outbound dials (add-exclusive-node to a
seed), so their connections stay inbound at the relays"). They do not. An
exclusive-node spy dials only its seed; every connection between a spy and a
relay is the RELAY's outgoing dial — the spy is in the relay's white list and
gets picked like any reachable peer. `spy_stem_receipts.py` on runs 46 (E19),
63 (E27) and 102 (X3a): 622 / 1,031 / 885 spy stem receipts, every one
`dir=in`; in X3a, 0 of the 672 receipts from adopters arrived while the spy sat
in the sender's virtual list. The lab's fleet has never held a connection an
X3 virtual slot can carry, so:

- `--spy-hidden` alone produces spies with no connection to any relay (the
  seed is their only peer); the isolation pole would read zero trivially.
- `--stemmable-cidrs` naming the spy /24s would gate nothing (no spy inbound
  exists at any adopter); the payment pole would read exactly X3a.

Fix: `make_lean --spy-dial N` (tag `_sdN`) drops the exclusive node and gives
the spies `out-peers N`; the harness's `--seed-node` list applies and they
fill N outbound slots from the white list they learn, like any node. Their
connections are then inbound at the relays — stemmable under X3 — while
hide-my-port decides whether they ALSO stay relay-dialed (the pay pole: both
channels) or hold the inbound channel only (the hidden poles). `--spy-hidden`
requires `--spy-dial`. N = 12 (monerod's stock budget) for P55-P58; the
dial budget is the strategy axis (one-IP-many-CPU = few /16s with many
connections, capped at one virtual slot per /16; many-IP-few-CPU = many /16s
at a small budget) and gets its own pole — dense against spread, hidden,
`--spy-dial 64` — after P56-P58 read.

The dense pole (P59) keeps the relay-dialed fleet: it cannot test the /16
bucketing (no virtual slot is ever a relay-dialed spy) and reads instead
whether the passive multiplier survives X3 at the real fleet's layout — the
program's first k8 cell.

Metric added for all five: `spy_stem_receipts.py` (stem receipts at spies,
by direction; distinct and hop-1 txs; `virtual_rx_share` — the time-ordered
join of each receipt against the sender's latest x3 virtual list — the
isolation check the hidden poles turn on). Baselines committed as
`spy_stem_receipts_run{46,63,102}.json`.
