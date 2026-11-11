# Antiproxy study: status

Status as of 2026-11-11 (through E79). The study is active and its history is
public (`origin/main`). Documents: the one-page current state **below**; the
cited findings underneath it; the full write-up
`docs/20261111_findings_summary.md`; the human-readable narrative
`docs/20261111_manuscript.md`; figures in `docs/figures/`. The experiment
journal, `docs/SPY_EXPERIMENT_JOURNAL.md`, holds entries E1-E79, predictions
P1-P77 and 125 registered runs — the source of truth for every number.

The study measures how spy fleets infiltrate Monero's peer lists and trace
transaction origins (Dandelion++ first-hop attribution), and tests defences at
the P2P layer.

## The study in one page

**What we know, in order of importance:**

1. **A shared-id proxy fleet passively takes 2.2x its fair share of honest
   outbound slots and traces 11.9 % of user transactions to origin at perfect
   precision.** The mechanism is one rule: monerod draws outbound candidates
   from the 20 *newest* white-list entries, and a port-multiplied fleet is
   always newest. The real fleet exists: 12,368 of 18,026 crawl endpoints
   carry the fingerprint.
2. **Fixing that draw rule makes the fleet's share fair but does not reduce
   its tracing** — 0.10-0.17 across every slot-share arm, and the best
   fairness arm is the *worst* for privacy (0.146-0.173 vs stock 0.126).
   Fairness is a property of honest connection budgets; privacy is a property
   of who holds first-hop slots.
3. **Observational id-consistency enforcement works — with a spoofability
   bound that is now stated up front.** The rule (refuse
   a second address a white-list slot when the same peer id was directly
   observed at two addresses) collapses a shared-id fleet 9.7x and takes
   tracing to 2.1 % (zero honest cost, structural flag-off null). **But peer
   ids are self-declared and spoofable, the real fleet already spoofs them**
   (12,368 fronts, 12,368 unique handshake ids, 40 shared PING ids), and a
   front that rewrites consistently — one id per address everywhere — is
   indistinguishable from that many honest nodes: every id-consistency result
   is measured against *leaking* fleets. The ladder: v3.2 (measured, defeats
   lazy forwarding) -> v3.3 PING observation (designed, defeats the deployed
   polarity) -> priced identity (per-id PoW, or id keys anchored by an
   on-chain burn — the only rung a careful fleet cannot rewrite past;
   designed in the manuscript, not measured). Part I (threat + fairness trap)
   reads no peer id and is untouched.
4. **The two stacked take tracing to zero** (E79): share 0.006, receipts 26,
   **0 of 984 user transactions attributed**. The trap inverts — under
   enforcement the fleet is one standing address per node, and the uniform
   draw that alone raised tracing now gives that address ~1/340 of honest
   dials. The defenses are complements.
5. **The rest of the map:** one slot per /24 governs the whole passive
   surface (the real fleet's shape can buy no more); an active refresher
   eclipses untrimmed lists (96.7 % attribution) and a 70-entry trim kills it
   (2.5 %); stemmable-inbound (MRL #160) never buys hop 1; churn is
   neutral-to-favourable for the fixes; mainnet lists sit in the flat
   (saturated) regime the lab measures.

**What's left to do:**

- **R9 v3.3: PING-path observation** — feed the evidence map from PING
  responses and re-run the trio against a crawl-shaped fleet arm (unique
  handshake ids + shared ping ids; the measured polarity: 12,368 fronts, 40
  backends). The patch cycle + P78/E80 — next defense work.
- **Priced identity (the spoofability endgame)** — per-id PoW or id keys
  anchored by an on-chain burn; the design is sketched in the manuscript's
  "Tying ids to proof" section (wire change + adoption debate = the owner's
  call whether to develop it into a spec).
- Second seeds for the E78 trio + the E79 combo (~11 h of tr) — hardening;
  the only lab work that could move a published number.
- The upstream note (draw fix + cap mapping + enforcement + composition) —
  evidence complete; **venue and timing are the owner's call**.
- Variant-P proxy fleet (`agents/spy_proxy.py`, the real front/back split —
  unused so far) — **owner's go**; also the fleet model for scale-up.
- Scale ladder: 1k honest, then 2k (fleet at the real ~1.5 % ratio) —
  feasible on tr; wall-time and ratio faithfulness are the open questions —
  **owner's go**.
- Mainnet monitor on the owner's three nodes — approved, unbuilt.
- Same-IP generator feature — unblocks the R8 per-host cap's real test.
- Standing observational work: monthly mainnet dump read; observatory daily
  pulls.

## Current findings (cited detail)

1. **Passive exposure is a multiplier of the subnet share, and the candidate
   cap is the multiplier.** Stock monerod draws outbound candidates from the 20
   newest white-list entries, so a passive fleet reads 0.337, 2.20x its
   ceiling. Lifting the 20-candidate cap collapses that to 0.158 (1.03x).
2. **Mainnet's capped lists already sit in the flat region.** Trimming the
   white list brings every reading to the ceiling (35 entries 0.99x, 70 1.06x,
   140 1.07x). The owner's mainnet dumps show white pinned at the 1000 cap and
   every white entry under 12.3 h old.
3. **The real spy fleet, measured.** The 2026-09-23 crawl found 12,368 of
   18,026 reachable nodes (68.6 %) with the peer-id-mismatch fingerprint,
   nearly all in a handful of dense /24s. A 21-day node holds 152 of 1000
   white entries in them.
4. **An active adversary eclipses an untrimmed list** (0.908 light share,
   96.7 % of user transactions attributed at precision 1.000). The uniform
   draw cuts that to 0.599; a white list trimmed to 70 cuts it to 0.0248.
5. **Churn amplifies exposure, and the candidate rules cost nothing.** Under
   1 h/1 h honest churn, stock reads 0.394 and the lifted cap 0.324, and the
   lifted cap dials less (1.37 against 2.85 failed dials per relay-hour).
6. **Who is deanonymized today, at mainnet sender rates:** unreachable senders
   are attributed at precision 1.000 (recall 0.146); busy reachable nodes at
   0.843, with 86 % exposed. The passive multiplier transfers at 2.26x.
7. **Tevador's MRL #160 stemmable-inbound variant works as designed, but its
   cover is too thin:** spy precision on unreachable users is 0.9828 against
   1.000 stock, and 1.000 at mainnet sender rates.
8. **Stemmable inbound is closed end to end:** nothing buys the first hop.
   Every gain a hidden fleet gets is at hop 2 or later, with zero attribution
   and one slot per prefix (E64-E71).
9. **One slot per prefix governs the whole passive surface** (E72-E75): the
   addresses-per-/24 axis is flat (7x addresses move nothing; B1 vs I1), /16
   spread is dead, budgets scale sub-linearly — the /24 slot plus the
   20-newest cut is the entire passive position, and the real fleet's port
   multiplication buys gray-side pumping, not white slots (stock white is
   already one-per-host). The R8 per-host gray cap is provably inert without
   same-IP endpoints (M2 null) and waits on the same-IP generator feature.
10. **Observational id-consistency enforcement works** (E76-E78, R9 v3.2,
    `--sim-enforce-id-consistency`): a fleet presenting one peer id at all its
    addresses collapses 9.7x (light 0.3467 → 0.0359) and hop-1 attribution
    falls 11.9 % → 2.1 % of user transactions at precision 1.000, with zero
    honest refusals and unchanged honest throughput; a per-endpoint-id fleet
    pays exactly nothing (the priced bound), and flag-off is a structural
    null across three binaries. The version history is the design lesson:
    eviction needs a standing gate (v2's treadmill amplified the attack 4x),
    and observation must cover both connection directions (v1 was blind to
    relay-dialed fleets; v3's ephemeral-port keying manufactured honest
    collateral).
11. **The two defenses compose, and the composition is total** (E79, P77,
    run 125): the candidate-draw fix stacked on enforcement takes light share
    to 0.006 (58x below baseline), stem receipts to 26, and sp recall to
    **0.000 — 0 of 984 user transactions attributed** — refusals still
    312/zero-honest. The fairness trap inverts: under enforcement the fleet
    is one standing address per observing node; the uniform draw that alone
    *raised* tracing (0.126 → 0.146-0.173) now gives that address ~1/340 of
    honest candidate draws instead of the 20-newest window. Slot-share
    fairness and id-consistency enforcement are complements — each fixes what
    the other cannot.

What stays live is observational: the monthly mainnet dump read (the fleet's
weekly address rotation and the candidate cut's freshness) and the observatory
daily pulls.

## Corrections in force

- `studies/antiproxy/docs/superpowers/specs/20261030-per-host-peerlist-accounting-design.md`:
  appendix A corrects section 1 (the stock white list is already one entry per
  host; the defence is gray-side only).
- The P62-P67 filings carry a correction block (2026-10-31 05:10): a cell's m
  daemons get distinct IPs, not shared-IP ports.
- The 11-08 journal rows record the `_sid` generator fix (the 11-07 S2 cell
  gave every daemon the shared id and died of self-connection drops) and the
  mandatory flagged-smoke rule that followed.
