# Antiproxy study: status

Status as of 2026-11-01; paths are relative to this folder. The study is
active, but the owner stopped all work on 2026-11-01 (about 11:20 UTC): the
queues are empty and nothing runs. Work resumes after the switch-over to main
(`SWITCHOVER.md`).

The study measures how spy fleets infiltrate Monero's peer lists and trace
transaction origins (Dandelion++ first-hop attribution), and tests defences at
the P2P layer. The full write-up is `docs/20261027_findings_summary.md`
(Findings 1-8). The experiment journal, `docs/SPY_EXPERIMENT_JOURNAL.md`, holds
entries E1-E71, predictions P1-P67 and 111 registered runs.

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
   and one slot per prefix; an inbound-only adversary never sits on the
   sender's first hop (E64-E71).

What stays live is observational: the monthly mainnet dump read (the fleet's
weekly address rotation and the candidate cut's freshness).

## Unfinished work

- Four finished cells are unscored: M1 (k9 m7), B1 (k9 m1), M2 (hpl1
  null-validation) and I1 (k42 m7). The data is on the lab boxes;
  `SESSION_HANDOFF_20261101.md` has the recipe.
- P62-P67 are filed, none scored. P68-P70 are not filed, and the S1-S3
  id-consistency cells are not generated.
- **The id-consistency patch (R9, `b051d548`) does not build.** It includes
  `p2p/id_evidence_map.h`, which the patch does not contain. It is commented
  out of `patches/series` until it is regenerated with the new file. Both lab
  boxes run R8 binaries.
- The port-front generator (same-IP daemons) is designed but unwritten
  (journal correction `3560f58a`).
- M2's run exited 1 from the post-run calibration scorer; its data is intact
  and the cause is undiagnosed.

## Corrections in force

- `docs/superpowers/specs/20261030-per-host-peerlist-accounting-design.md`:
  appendix A corrects section 1 (the stock white list is already one entry per
  host; the defence is gray-side only).
- The P62-P67 filings carry a correction block (2026-10-31 05:10): a cell's m
  daemons get distinct IPs, not shared-IP ports.
