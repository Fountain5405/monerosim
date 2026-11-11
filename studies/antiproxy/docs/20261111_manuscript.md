# One id, many addresses: how proxy fleets ride Monero's peer lists, and the local rule that stops them

A narrative manuscript for the antiproxy study, 2026-11-11. Everything here is
measured: each number cites an entry (En) or filing (Pn) in
`SPY_EXPERIMENT_JOURNAL.md`, where every prediction was filed before its
experiment ran and scored blind against the outcome afterwards — 125 registered
runs so far. The technical summary with full citations is
`20261111_findings_summary.md`; this document is the story for a reader who
wants to understand it without reading the journal.

## The short version

Someone wanting to learn who sends Monero transactions does not need to break
cryptography. It is enough to run many cheap proxies — one real `monerod`
backend behind many forwarded addresses — and let the network's own peer
selection carry honest nodes' traffic to them. A September 2026 crawl of the
live network found 12,368 of 18,026 reachable endpoints carrying the
fingerprint of exactly that design: many addresses, one backing peer identity
(E3). In our simulations such a fleet, entirely passive, occupies 2.2 times its
fair share of honest nodes' outbound connections and receives 11–12% of user
transactions *as the first hop* — the hop whose sender is, by construction, the
transaction's origin. The attribution is perfect-precision: every transaction
the fleet attributes, it attributes correctly.

Two defenses follow from the measurements, and they are not the two one would
guess. Fixing the rule that lets the fleet multiply its share — the obvious,
one-line fix, ready for upstream — makes the fleet's share *fair* but leaves
its tracing power untouched, or slightly worse. The defense that actually cuts
tracing is a local, observational rule: a node that has *directly seen* one
peer id presenting two different addresses simply refuses the second address a
place in its white list, for as long as the contradiction stands. That rule
collapses a shared-id fleet's position 9.7-fold, cuts origin attribution from
11.9% to 2.1% of user transactions, provably costs honest peers nothing — and
needs no protocol change, no new message, no coordination. And the two
defenses stack: with both in force, the fleet's origin tracing in the lab goes
to **zero** — not one of 984 user transactions attributed (E79).

![first-hop deanonymization by defense](figures/f3_deanonymization_ladder.png)

## Background: the two lists and the first hop

A Monero daemon keeps two lists of peers. The **white list** holds up to 1000
reachable peers it has actually talked to; the **gray list** holds peers it has
merely heard about. When the daemon needs a new outbound connection, it picks
*candidates* from the white list — and stock `monerod` picks them from the 20
**newest** entries by last contact, preferring whichever /24 subnet the least
recently-used entry came from. Freshness, in other words, is the currency of
connection slots.

Transaction propagation uses Dandelion++: a wallet's transaction first goes to
one node (the **first hop**), which holds it and forwards it through a random
*stem* of one or more intermediaries before it fluffs out to the network. The
privacy of the whole construction rests on the first hop being honest: the
first node in the stem necessarily learns the sender's IP address. A fleet
that occupies first-hop slots doesn't need to break anything — the origins
arrive on their own.

This is why "share of outbound slots" and "fraction of transactions
deanonymized" are the two numbers this study tracks. The first is the fleet's
*position*; the second is what the position *buys*.

## The threat, measured

The lab is a discrete-event network simulator (Shadow) running real, unmodified
`monerod` v0.18.5.1 binaries — patched only with flag-gated instrumentation
that is off by default and provably inert (E78's null arm: three successive
binaries, flag off, read the same slot share within noise). A typical
experiment is a 300-reachable-node network with a fleet modeled on the crawl:
294 spy endpoints spread over 42 /24 subnets, each subnet's addresses behind
the same shared backing id where the arm calls for it. Sender traffic mimics
mainnet rates. Fleet-side estimation uses only what a real spy could log: which
addresses received stem transactions, and when.

Three facts define the threat (Part I of the study):

**The 20-newest cut is the multiplier.** A passive fleet that does nothing but
accept connections and gossip ends up occupying 0.337 of honest outbound slots
— 2.2x its share of the address pool (E27). The mechanism is the candidate
rule above: a fleet with many addresses in dense /24s refreshes its own
entries constantly, so the "newest 20" is systematically fleet-heavy. Lift the
cap so candidates come from the whole deduplicated white list and the
multiplier collapses to 1.03x (E36/E37) — the fleet gets exactly its fair
share of slots and not one more.

![fleet slot share vs pool share, white-cap sweep](figures/f1_cap_sweep.png)

**The fleet's shape cannot buy more position.** More addresses per /24, /16
spreading, bigger budgets: none of it moves the passive needle, because the
per-/24 dedup means a fleet gets one white slot per prefix per node — stock
white lists are already one-entry-per-host (E72–E75). The port-multiplication
the real crawl shows buys gray-side gossip spread, not white-list standing.

**What the position buys is origin identity.** At that steady state the fleet
receives ~1,000 stem transactions per run and attributes 11.9% of user
transactions to their true origin at precision 1.000 (I1 baseline of the
enforcement trio). An *active* adversary — one that refreshes its own entries
to stay permanently newest — eclipses an untrimmed list entirely: 0.908 slot
share and 96.7% attribution (E58–E62). Mainnet context makes this concrete:
the owner's node dumps show white lists pinned at the 1000 cap with every
entry under 12.3 hours old — the flat, saturated regime right where these
mechanisms operate (Finding 2).

## The fairness trap

So the obvious defense is the one-line draw fix. It is cheap, it is fair, and
it works exactly as designed: share drops to 1.03x. One would expect tracing
to fall with it.

It doesn't. Across three seeds, networks running the draw fix — candidates
uncapped, selection uniform — show *higher* first-hop attribution than stock:
recall 0.146–0.173 against stock's 0.126, all at precision 1.000 (E36/E38/E41;
the uniform-pick-only arm E35 reads 0.101). Trimming the white list to
mainnet-like sizes (70 or 35 entries) lands back in the same 0.13–0.14 band
(E45, E50). The blue bars in the ladder figure are all the same height, and
the best "fairness" arm is the tallest of them.

The mechanism is simple once stated: slot-share defenses spread the fleet's
occupancy across more honest nodes, but every slot they keep is still a first
hop, and a first hop is a first hop. Spreading the fleet's share *fairly*
spreads the *origins* fairly — across more spies. **Fairness is a property of
the honest nodes' connection budgets; privacy is a property of who holds the
first-hop slots. The draw fix buys the first and not the second.**

This is the study's most cautionary result, and the reason the orange bar
matters.

## The defense that works: observe ids, gate addresses

The crawl's fingerprint — many addresses, one backing peer id — is also the
fleet's structural weakness. A proxy front cannot help presenting the same
peer id from many addresses: the id is minted by the one backing daemon, and
the PING-support handshake requires it. An honest node's own connections,
nothing else, are enough to see the contradiction.

The rule (patch R9 v3.2, `--sim-enforce-id-consistency`, off by default): a
node records, per its directly observed connections in *both* directions,
which peer id it saw at which advertised address. If one id is observed at two
or more addresses within a grace window (24h in the lab), every address but
the most recently observed one loses **standing**: existing white entries are
evicted, and every path that could re-insert them refuses while the
contradiction is live. The fleet is demoted to one standing address per
observing node. No wire format changes, no new messages, no coordination —
it is a local policy on local evidence.

**Measured** (k42-m7, 294 shared-id endpoints, 19-hour steady state, E78):

- Slot share: 0.3467 → **0.0359** — a 9.7x collapse, at or below the
  theoretical one-slot-per-prefix floor.
- Origin attribution: 11.9% → **2.1%** of user transactions, still at
  precision 1.000; Dandelion++ stem exposure falls from 1,004 receipts to 187.
- Cost: **zero honest refusals** — all 308 refusals land on spy addresses —
  and honest stem throughput unchanged (1,048 vs 1,004 baseline transactions).
- The bound: a fleet that mints a fresh id per endpoint pays *exactly nothing*
  (0.3494 vs 0.3467 baseline, refusals exactly 0, E78's bound arm). The rule
  prices the cheap design, and the priced alternative — per-identity keys or
  signed id bindings — is a different, harder game.
- The null: with the flag off, three successive binaries read the same slot
  share within noise. The instrumentation is inert when off, structurally.

![fleet slot share by enforcement arm](figures/f2_enforcement_arc.png)

![attribution and stem exposure under enforcement](figures/f5_fleet_losses.png)

## Four versions, one lesson

The rule looks obvious in retrospect. It took four versions to get right, and
each failure was caught by a pre-registered check, not by luck:

- **v1** recorded ids only on *inbound* handshakes — and the fleet, dialed
  outbound by honest nodes, never triggered it. 1,022 of 1,022 receipts were
  relay-dialed; the maps stayed empty (E76). *Observation must cover both
  connection directions.*
- **v2** added client-side observation but only *evicted* — evicted entries
  were immediately re-inserted by the next handshake, a freshness treadmill
  that briefly let the fleet *quadruple* its share (smoke cell: 0.6422 against
  0.1614 inert). *Demotion without a standing gate is worse than nothing.*
- **v3** gated re-insertion but keyed observations by the connection's
  ephemeral source port — so honest peers behind NAT rebinding read as
  id-contradictions, manufacturing 40,795 honest refusals (E77's no-collateral
  check caught it). *Key by the advertised address, the identity the network
  actually uses.*
- **v3.2** keys by advertised address and lands at the floor.

![the version ladder, one smoke cell](figures/f4_version_ladder.png)

Generalized: **a demotion rule must pair eviction with a standing gate, and an
observation rule must see what it claims to observe, in both directions.**
Both lessons generalize well past Monero.

## What transfers, and what doesn't

- The mechanisms — the 20-newest candidate cut, per-/24 dedup, one-slot-per-
  prefix, the shared-id fingerprint — are properties of the monerod code and
  the protocol, not of our lab, and the mainnet dumps sit in the regime the
  lab measures. The transfer caveat that remains is scale (300-reachable
  networks; single seed per arm for the newest results, with second seeds
  queued).
- The enforcement rule needs adoption by monerod to matter on mainnet; its
  grace window trades honest dynamic-IP moves against demotion speed, and
  that trade is a policy decision, not a measurement.
- Sophisticated fleets — per-endpoint ids, or per-identity proof work — are
  out of this rule's scope by design. It prices the design the crawl actually
  observed, which is the design that exists.
- The composition question is closed (E79, run 125): the draw fix stacked on
  enforcement takes the fleet's tracing to **zero** — 0 of 984 user
  transactions attributed, light share 0.006 (58x below baseline), stem
  receipts 1,004 → 26, refusals still all-spy/zero-honest. The fairness trap
  inverts: under enforcement the fleet survives as one standing address per
  observing node, and the uniform draw that alone *spread* first-hops to more
  spies now spreads honest dials away from that last address (~1/340 of
  candidate draws instead of riding the 20-newest window). The two defenses
  are complements — each fixes what the other cannot.

## How to read the evidence

Everything is reproducible from this repository: the journal
(`SPY_EXPERIMENT_JOURNAL.md`) with its 125 registered runs and pre-registered
predictions; the flag-gated patches (`studies/antiproxy/patches/`, applied via
`patches/series`); the generators and analysis tools; and per-run artifacts
(`docs/spy_journal/runs/`). Figures regenerate from journal-cited values with
`figures/make_figures.py`. The one thing not in the repository is raw mainnet
data — crawl outputs and node dumps stay local by policy; only derived,
aggregate numbers appear here.
