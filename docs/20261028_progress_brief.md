# Spy-relay exposure in Monero's transaction relay path: progress brief

**2026-10-28.** Seven findings closed, one confirm cell in flight. This document carries
derived numbers only; raw mainnet captures (peer-list dumps, a node crawl) stay on private
storage and are summarized here.

## The question and the instrument

How much can a coordinated fleet of spy relays learn about *who sent* a Monero transaction
through Dandelion++'s stem phase? Which peer-selection defenses reduce that, what does an
adaptive adversary do about them, and do the proposed protocol changes help?

We answer this with Shadow simulations of a patched monerod (v0.18.5.1 plus 14
simulation-only patches for measurement and rule variants). Standard cells: ~340 reachable
honest nodes, 40 unreachable users, and a 42-relay spy fleet spread across 42 /24 subnets,
with every reading quoted against a *subnet ceiling* — the spies' fair share of outbound
slots given their share of distinct /24s. Sender attribution is scored with ground-truth
estimators over the full relay path. Mainnet evidence — peer-list dumps from two real nodes
and a crawl of ~18,000 reachable nodes — anchors the parameters and confirms the mechanisms.

## What we found

**1. Today's passive excess is a selection-rule artifact, and the knob is known.** Under
stock peer selection the 42-spy fleet reads **2.2x its ceiling** (0.337 of outbound slots).
The cause is narrow: monerod draws outbound candidates from the *20 newest* subnet-deduplicated
white-list entries, and spies stay near the top of that order. Letting every subnet be a
candidate (or sampling 20 at random) collapses the excess to **1.0-1.08x**. Attribution
precision is 1.000 throughout — when a spy sees a stem, the sender identification is right;
the defense question is how often the spy sees one at all.

**2. Mainnet's capped lists already sit in the safe regime for that artifact.** Real peer
lists are pinned at the 1,000-entry cap and effectively recency-trimmed (every entry under
12.3 h old, median ~6 h). In the lab, trimming the list to 35/70/140 entries reads **0.99x /
1.06x / 1.07x** — the 2.2x disappears at any realistic list size. Mainnet's newest-20 cut is
minutes-fresh, so the mechanism is live at the top of the list even though the bulk is safe.

**3. The real spy fleet, measured.** 68.6 % of reachable nodes in the crawl carry one
proxy/front-end fingerprint; 12,362 of them sit in **eight dense /24s — one operator**. A
21-day node holds 15.2 % of its white list in those /24s (exactly the pool share, at stale
ranks); a 5-day node holds *zero* of their addresses: the fleet rotates its whole address
space on roughly weekly timescales. Today's passive exposure is therefore the pool share,
aging — consistent with the trimmed-lab result.

**4. The active adversary, and the one defense that works.** Re-handshake attacks cannot
refresh an existing white-list entry (verified in source and in a live smoke): only a node's
own outbound connections refresh timestamps. The attack that works is a rotating front end
that inserts always-fresh entries into every list: untrimmed, it reaches an **eclipse — 0.908
light share, 96.7 % of user transactions attributed at precision 1.000, all 40 users**. The
defense is the white-list length cap: trimming to 70 entries forces a fast honest refresh
cycle that evicts the fronts — the same adversary reads **0.0248, 1 of 40 users exposed**
(replicated across seeds; a 30x-faster port rotation changes nothing). The arms race is
measured to the lab's floor: an effective sweep below ~10 minutes per node is not deliverable
by the real adversary's dialing budget, and mainnet's own cut already lives at that freshness.

**5. Churn amplifies exposure; the candidate rules cost nothing.** With every honest relay
cycling hourly, absolute exposure rises (0.394 stock, 0.324 with the cap lifted) because
always-online fleets take a larger share of live subnets. The honest cost of the lifted cap
is *negative*: it makes fewer failed dials than stock (1.37 vs 2.85 per relay-hour).

**6. Who is deanonymized today, at mainnet sender rates.** Rebuilding the cell with ~mainnet
traffic over 24 h:

| Sender class | tx/day | attribution precision | own txs attributed | ≥1 tx exposed in 24 h |
|---|---|---|---|---|
| Unreachable (NAT) users | ~2 | **1.000** | 14.6 % | 21.6 % |
| Reachable, occasional | ~4 | **0.265** | 38.8 % | **79.6 %** |
| Reachable, busy | ~24 | **0.843** | 18.9 % | **86 %** |

Reachability *doubles* per-transaction first-hop exposure (more connections, more stem draws)
while relayed stems dilute attribution four-fold for occasional senders and barely at all for
busy ones. Unreachable and busy senders are cleanly attributable one observation at a time;
occasional reachable senders are noisy per guess but almost all touched within a day.

**7. The leading protocol proposal, built and measured.** We implemented the best-regarded
MRL proposal — stemmable inbound connections (stem edge 1 restricted to real outgoing
connections, edge 2 drawing on a /16-deduplicated pool including PoW-gated inbound
"virtual outgoing" connections) — as a simulation patch and ran it at full adoption. The
mechanism works exactly as specified (30,961 epoch events; users receive relayed stems for
the first time), **but the cover is far too thin to dilute attribution: precision 0.983
against 1.000 stock** — 67 relayed stems reached 25 of 40 users against their 1,063 own
sends. At mainnet sender rates the arithmetic gives ~0.85-0.9; a confirm cell is in flight.
Under the active adversary the feature changes nothing (light 0.9051 vs 0.9083, all 40 users,
combined attribution 0.951 at precision 1.000 — five of five on pre-registered clauses) and
its cover dies entirely (17 relayed stems, one user). What survives is structural: an
inbound-only adversary can never sit on stem edge 1, and the /16 deduplication hardens the
inbound side.

**Also closed — the fluff-epoch question.** A node's own transactions are stemmed even during
its fluff epochs, so a leak the plan worried about exists — but it is redundant (an oracle
mode-detector adds zero transactions beyond the first-hop stem exposure already counted) and
undetectable at relay density (the proposed cue detector lands in true fluff epochs 21-23 % of
the time against the 20 % prior; attack precision 0.05-0.07). Under the active adversary the
channel collapses with the stems. No monerod change is warranted for it.

## Bottom line

Today's exposure is priced: unreachable and busy senders are attributable cleanly, occasional
reachable senders are exposed almost as often through noise. The white-list length cap —
which mainnet already runs — is the measured defense, passive and active, in the lab and
against the real fleet's fingerprint. The leading protocol proposal's precision-cover
rationale does not survive its own throttles at any sender rate, and its structural guarantee
has its blind side exactly where the documented mainnet adversary operates.

## In flight and next

- Mainnet-rate confirm of the stemmable design (running; decides whether its parameter space
  deserves a design sweep at all).
- Adversary-strategy poles against stemmable designs: the real fleet's 8-dense-/24 layout vs
  spread under /16 bucketing, who pays the proof-of-work, and inbound-only fleet isolation.
- Standing: monthly mainnet dump reads (fleet rotation, cut freshness); optional IP-churn
  modeling.

*Full method, pre-registered predictions, and per-run artifacts live in the project's
experimental journal (docs/SPY_EXPERIMENT_JOURNAL.md and docs/spy_journal/).*
