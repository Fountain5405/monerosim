# Antiproxy study: status

Status as of 2026-11-11. The study is active and its history is public
(`origin/main` through the latest commit). The full write-up is
`studies/antiproxy/docs/20261111_findings_summary.md` (Findings 1-10). The
experiment journal, `studies/antiproxy/docs/SPY_EXPERIMENT_JOURNAL.md`, holds
entries E1-E78, predictions P1-P76 and 124 registered runs.

The study measures how spy fleets infiltrate Monero's peer lists and trace
transaction origins (Dandelion++ first-hop attribution), and tests defences at
the P2P layer.

## Current findings

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
    `--sim-enforce-id-consistency`): a shared-id proxy fleet — the crawl's
    fingerprint — collapses 9.7x (light 0.3467 → 0.0359) and hop-1 attribution
    falls 11.9 % → 2.1 % of user transactions at precision 1.000, with zero
    honest refusals and unchanged honest throughput; a per-endpoint-id fleet
    pays exactly nothing (the priced bound), and flag-off is a structural
    null across three binaries. The version history is the design lesson:
    eviction needs a standing gate (v2's treadmill amplified the attack 4x),
    and observation must cover both connection directions (v1 was blind to
    relay-dialed fleets; v3's ephemeral-port keying manufactured honest
    collateral).

What stays live is observational: the monthly mainnet dump read (the fleet's
weekly address rotation and the candidate cut's freshness) and the observatory
daily pulls.

## Unfinished work

- The upstream note (candidate-draw fix + cap mapping + enforcement) is ready
  to draft on complete lab evidence; venue and timing are the owner's call.
- The E78 trio's second seeds (~8 h of lab time) — hardening, not blocking.
- The port-front generator (same-IP daemons) is designed but unwritten
  (journal correction `3560f58a`); it unblocks the R8 cap's real test.
- Mainnet monitor deployment on the owner's three nodes — approved, unbuilt.

## Corrections in force

- `studies/antiproxy/docs/superpowers/specs/20261030-per-host-peerlist-accounting-design.md`:
  appendix A corrects section 1 (the stock white list is already one entry per
  host; the defence is gray-side only).
- The P62-P67 filings carry a correction block (2026-10-31 05:10): a cell's m
  daemons get distinct IPs, not shared-IP ports.
- The 11-08 journal rows record the `_sid` generator fix (the 11-07 S2 cell
  gave every daemon the shared id and died of self-connection drops) and the
  mandatory flagged-smoke rule that followed.
