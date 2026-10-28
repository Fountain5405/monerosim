# Sender exposure to spy relays: findings through 2026-10-27

A human-readable summary of the spy-relay research program's results. Two to three pages,
the important numbers only; every claim carries a pointer into
`docs/SPY_EXPERIMENT_JOURNAL.md` (entries E1-E62, predictions P1-P54, run register
`docs/spy_journal/runs/`, 102 runs) where the full method, clauses and raw scoring live.
The lab's design and question framing are in `docs/20261018_spy_node_defenses.md` and
its section 7 review.

**The question.** How much can a fleet of spy relays learn about Monero transaction
senders (Dandelion++ stem exposure), which peer-selection defenses reduce that, and what
does the adversary do about them?

**The lab.** Shadow simulations of patched monerod ("lean cells": 300 reachable honest
nodes, 40 unreachable users, 42 spy relays across 42 /24s, 13 h warmup, 4 h measurement
window). The subnet ceiling (0.1531) is the spies' share if outbound slots followed
their share of distinct /24s (42 of 284) — the null model every reading is quoted
against.

## Finding 1 — Passive exposure is a multiplier of the subnet share, and the candidate cap is the multiplier

Under today's stock peer selection, the passive spy fleet reads **0.337 = 2.20x the
ceiling** (E27, three seeds 0.334-0.337). The cause is narrow: stock draws outbound
candidates from the **20 newest-by-`last_seen` subnet-deduplicated** white-list entries,
and the spies — refreshed only when a node dials them — sit high in that order
(E21/E35). Lifting the 20-candidate cap collapses the multiplier to **0.158 = 1.03x**
(E36, three seeds), and the draw's recency shape is worth only 8% more (E37). Sender
attribution under the passive fleet: precision 1.000, recall equal to the sender's own
spy stem share (0.118-0.144). [Journal: open question 10, E27-E43.]

## Finding 2 — Mainnet's capped lists already sit in the flat region (the 2.2x does not transfer)

The stock rule was only ever exposed to lists that hold the whole lab network. Trim the
white list and every reading falls to the ceiling: **35 entries 0.99x, 70 1.06x, 140
1.07x** vs unlimited 2.20x (E45-E47, E49, E50). The owner's mainnet dumps (2026-10-27,
two nodes, 21 d and 5 d uptime) confirm mainnet is the trimmed case: **white pinned at
the 1000 cap, gray at 5000, every white entry under 12.3 h old (median ~6 h)**, lists
from the two nodes overlapping only 19% — the network's steady state, not a habit.
[Journal: open question 8, both 10-27 notes; raw dumps local-only,
`~/monerosim_local/mainnet_pl/`.]

## Finding 3 — The real spy fleet, measured

The 2026-09-23 crawl (18,026 reachable nodes probed): **12,368 (68.6%) carry the
peer-id-mismatch front-end fingerprint**, and 12,362 of them sit in **eight dense /24s**
— one operator, the same "9 dense /24s" the lab's cells were built to model. Against the
dumps: a 21-day node holds **152 of 1000 white entries in those /24s (15.2% — the pool
share) at median rank 580 of 1000 — the stale half — and 3 of the newest-20 candidate
cut (15%)**. A 5-day node holds **zero** September addresses: the fleet rotates its
whole address space on ~week timescales. So the passive fleet on mainnet sits exactly
where the lab's passive trimmed cells put it: at its pool share, aging. [Journal: OQ8
identification note; crawl source on `senior`, copy local-only.]

## Finding 4 — The active adversary: what monerod allows, what it achieves, and the one defense

- **The adversary the plan imagined does not exist.** Re-handshaking cannot refresh an
  existing white-list entry: the ping-back path calls `append_with_peer_white` with
  `trust_last_seen=false` and the guard preserves the old timestamp; only a node's own
  outbound connections refresh entries. Verified in source and in a live smoke (runs
  88, 90). [OQ13 (b).]
- **The adversary that exists eclipses everything untrimmed.** A fleet listening on
  extra ports, advertising a rotating one and serving the daemon's identity, inserts
  always-fresh entries at the top of every list (one per host — monerod's own
  anti-gaming eviction keeps the list clean), reaching even unreachable users via
  gray-list dials. Untrimmed result: **0.908 light share (5.9x), 96.7% of user
  transactions attributed at precision 1.000, all 40 users exposed** (E53/E54, two
  seeds 0.9083/0.9075). The uniform draw over all candidates — the one rule with no
  newest-cut — cuts it to **0.599** and restores direct attribution to passive levels,
  but cannot hold the subnet share: spy connections never drop while honest ones churn,
  so slots accumulate under any draw (E55). [OQ13 (c)-(e).]
- **The white-list trim is the defense.** With the list capped at 70, the same
  adversary reads **0.0248 — 1 of 40 users exposed** (E56); a 30x faster port rotation
  changes nothing, **0.0262** (E57). Mechanism: a capped list forces the honest network
  into a fast refresh cycle that outruns the fronts; stale fronts are evicted; the
  adversary's inserts feed the honest redraws. The trim converts dialing budget into
  refresh rate — its strength is adversary-relative.
- **On mainnet the race is contested, not won.** The dumps' newest-20 cut is
  minutes-fresh (1.4-8.8 min) — as fast as a 300 s-sweeping adversary — and honest
  connections live a median 10.4 h, so slot wins persist. Mainnet's trim protects by
  forcing that fast top cut; an adversary willing to spend a higher sweep budget, or to
  rotate addresses weekly as the real fleet already does, keeps three dials the lab has
  priced (sweep rate, port rotation, IP churn) but mainnet has not yet seen combined.
  [OQ8 + OQ13 (f), (g).]

## Finding 5 — Churn amplifies exposure and the candidate rules cost nothing

With every honest relay cycling on 1 h/1 h sessions (spies pinned up), the stock rule
reads **0.394** and the lifted cap **0.324** — absolute exposure *rises* over the
no-churn 0.337 even as the multiplier falls (the always-online fleet doubles its share
of live /24s; E51/E52). The honest cost is small and the objection to the candidate
rules is empty: the lifted cap is *cheaper* than stock under churn (1.37 vs 2.85 failed
dials per relay-hour; refill 1.7 vs 1.6 min; 1.3% of sessions unfilled). Attribution
precision degrades under churn (0.86-0.93 from 1.000). [OQ11, closed.]

## Finding 6 — Who is deanonymized today (mainnet rates, X1a)

At mainnet's sender rate over 24 h of activity (E61, run 100; passive fleet, stock
rule): unreachable senders are attributable one transaction at a time at
**precision 1.000** (recall 0.146; **21.6 %** of users had at least one
transaction attributed in 24 h). Occasional reachable senders read **precision
0.265** — one spy guess in four is right — but **38.8 %** of their own
transactions are attributed (reachability *doubles* per-tx first-hop exposure:
caps 0.388/0.189 against the users' 0.148) and **79.6 %** had at least one
exposed transaction in 24 h. Busy reachable nodes: **precision 0.843, 86 %**
exposed. The passive multiplier itself transfers to mainnet rate
(**0.2935 = 2.26x** its own ceiling, the cell's 0.1299 model — corrected 10-28; the first
write-up divided by the standard cell's 0.1531 — against 2.20x at lab rate). So the exposure
ordering is busy ≈ unreachable (cleanly attributable) > occasional reachable
(noisy per observation, exposed nearly as often): relayed-stem cover dilutes
attribution 4x for occasional senders and almost not at all for busy ones.
[Journal: open question 12, E61.]

## Finding 7 — The best MRL proposal, built and measured: works as designed, cover too thin (X3a)

Tevador's #160 stemmable-inbound variant (the plan's top-rated proposal) was implemented as the fourteenth sim patch and run at full take-up (E62, run 102). The mechanism is faithful — 30,961 epoch events, edge 2 drawing on virtual inbound connections, users receiving relayed stems for the first time — but the cover is **too thin to dilute attribution: sp precision on unreachable users 0.9828
against 1.000 stock** (own:cover 15:1; the plan's ~0.3 precision would need ~34x more cover
than the mechanism delivers — corrected 10-28 from a 15x phrasing that mixed the two ratios). The design's own throttles compound (one mixed edge, ~38% virtual epochs, a 12-way per-/16 lottery users mostly lose): **71 relayed stems reached all 40 users together, against 1,063 of their own sends**. Rate scaling doesn't rescue it (~0.85-0.9 at mainnet sender rates). What survives is structural: an inbound-only adversary can *never* sit on stem edge 1, and the /16 deduplication hardens the inbound side. The precision-cover rationale — the reason to deploy it — does not survive contact. The
blind-side check confirms it (E63, run 103): under the front-port eclipse X3 changes nothing
(light 0.9051 against E53's 0.9083, 40/40 users, combined 0.951 at precision 1.000) and its
cover collapses to 17 relayed stems at one user — the guarantee's blind side is where the real
attack lives.

## The bottom line

Nothing in the candidate rule set survives the active adversary untrimmed; the
white-list cap — which mainnet has run all along — is the measured defense, passive and
active, in the lab and in the wild. The arms race is now measured to the lab's floor:
the trim holds at every sweep rate the simulator can deliver (0.0248 at 300 s sweeps,
0.0239 at the agent's ~18-minute dial floor, E59), and the sub-10-minute regime a real
fleet could run is bounded by mainnet's own dump evidence instead (the cut is already
minutes-fresh). The fluff epoch adds no independent leak (E58). What remains live is
observational, not simulated: the standing monthly mainnet dump read (the fleet's
weekly address rotation and the cut's freshness), and optionally the 10x-rate arm of
the sender-class table and the IP-churn model.

## Pointers

- Journal: `docs/SPY_EXPERIMENT_JOURNAL.md` — entries E1-E62 (section 4), predictions
  P1-P54 (section 5), open questions (section 6), decisions (section 7), run register
  (section 3, 102 runs; per-run artifacts in `docs/spy_journal/runs/<id>/`).
- Tooling: `test_configs/x0/make_lean.py` (`--spy-refresh/--spy-rotate/--user-dumps`
  and the rule/trim flags), `agents/spy_refresh.py` (the adversary),
  `analysis/spy/{spy_estimators,churn_cost}.py` (scoring), `analysis/mainnet/` (crawl).
- Mainnet evidence: local-only on the control box at `~/monerosim_local/mainnet_pl/`
  (two node dumps, the 2026-09-23 crawl); never committed — the repo carries derived
  numbers only.
