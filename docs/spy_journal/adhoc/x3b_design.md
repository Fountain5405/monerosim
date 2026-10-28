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
