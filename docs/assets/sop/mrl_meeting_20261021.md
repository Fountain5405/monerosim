# Share-or-Perish in monerod: progress, 21 Oct 2026

Short version: in our simulations SoP does what it says at α = 1/3. Above
that it gives way, and we can't yet say how much of that the 20 Oct revision
fixes, because none of our runs include it.

## Setup

- SoP (research-lab #146) patched into monerod v0.18.5.1 and run under the
  Shadow network simulator: real RandomX, 120 s blocks, link latencies from
  the CAIDA topology.
- Most runs have 12 daemons: 2 honest miners, relays, seeds, the attacker's
  miner and a bridge node. Some have 40.
- The attacker withholds its blocks and shares, and releases its branch once
  it would win under SoP. It gives up after falling a set number of blocks
  behind (the "give-up depth" below).
- Every fork-choice decision a node makes is logged and recomputed by a
  separate checker written from the issue text. Over 40,000 decisions so far,
  no disagreements. That says the daemons follow the rule as we read it, not
  that the rule is right.
- We also compare against a simple race model of our own (no network delay).
- monerod isn't deterministic under Shadow, so a seed doesn't reproduce a
  run. Each run is an independent draw, and most settings have one or two.

The runs follow the 15 Oct revision. The issue has changed twice since, in
ways that matter here:

- 16 Oct: lateness applies while both branches have fewer than 32 work
  objects not counting the first block after the fork (it was fewer than 48
  counting it).
- 20 Oct: shares waiting in the pool on a chain's tip now count under the
  objective score. That goes straight at the main weakness described below.

We haven't simulated either yet. We've stopped the runs on the old rule and
are updating the simulator.

## α = 1/3

Attacker's share of blocks under SoP: 0.019 to 0.036 in ten runs (six 10-day
runs with 12 daemons, four 2-day runs with 40). The same attacker against
stock monerod gets about 0.30. This is the result we're most sure of.

Releases still get through, about 3 to 4 a day (a day being 720 blocks).
The text we implemented estimated about one per 10 days. The current text
gives about one per 1.5 days, averaging 3 blocks, for its own attacker under
the 20 Oct rule. Ours orphan 2.6 to 3.2 honest blocks on average, and the
deepest orphaned 8. There was no reorg of 10 or more blocks in 58 simulated
days.

Why they get through: the 15 Oct rule counts a share only once it is in a
block. Honest blocks arrive about every 3 minutes with about 15 shares each,
so the honest side usually holds a pile of shares that don't count yet, and
the attacker releases at those moments. At 208 releases, one honest node had
received a median of 40 such shares, and counting them would have blocked 204
of the releases. As we read it, the 20 Oct change counts exactly these
shares.

## α = 0.40

All nine 6-hour runs came in below 0.40, from 0.000 to 0.286. One 72-hour run
with the attacker using honest shares (give-up depth 2) gave 0.169, against
0.186 from our race model.

## α = 0.45

This is beyond what the proposal sets out to defend (its analysis uses 1/3),
but it's where the margin shows. Break-even is 0.45. All runs are 72 h, about
1,950 blocks each.

| attacker | give-up depth | share of blocks | our race model |
|---|---|---|---|
| ignores honest shares | 2 | 0.379, 0.370 | 0.356 |
| uses honest shares | 2 | 0.424 | 0.395 |
| ignores honest shares | 5 | 0.460, 0.468 | 0.366 |
| uses honest shares | 5 | 0.503, 0.520 | 0.426 |

"Uses honest shares" means the attacker's miner picks honest shares up from
gossip and puts them in its own private block where the slot rule allows, as
the attacker in tevador's simulator does. Our earlier attacker couldn't.

With give-up depth 5, all four runs came out above break-even and well above
the race model. At depth 2 the model is close. We don't know yet why depth 5
is so far off. The second run in each depth-5 row (0.468, 0.520) paid
tail-emission rewards. Each pair is within 0.02, so the reward schedule
doesn't seem to matter here, as expected when revenue is counted in blocks.
With two runs per row at most, treat this as a first look.

## An attacker that only wants deep reorgs

This one keeps its branch private until the honest chain is 10 blocks past
the fork, then releases if it would win. It gives up 2 blocks behind and
ignores honest shares. Rates are per 720 blocks.

| α | stock: 10+ reorgs a day | SoP: 10+ reorgs a day | SoP: attacker's share |
|---|---|---|---|
| 0.33 | 6.8 (12 in 48 h) | not run; race model about 0.35 a year | |
| 0.40 | 13.2 (22 in 48 h) | 0.52 (5 in 240 h) | 0.010 |
| 0.45 | 22.9 (39 in 48 h) | 6.4 (17 in 72 h) | 0.138 |

Stock at α 0.33 (6.8 a day) agrees with the issue's "several 10-block reorgs
per day" under Nakamoto consensus. SoP cut them about 25 times at α 0.40 and about 4
times at α 0.45, and the attacker paid for them with most of its revenue. But the ones that got
through under SoP could be much deeper: 17 and 23 blocks, against 12 at most
under stock. Once a fork is long enough, lateness stops applying and the
fork is decided on total work.

## Other things we ran into

- version_minor and the hard-fork vote: an unmodified v0.18 node rejected
  every SoP block it was sent. The 15 Oct revision fixed this.
- Peer scoring: stock monerod penalises a peer whose reported height drops,
  and SoP nodes do legitimately switch to shorter chains. In 3 of 5 depth-5
  runs honest nodes banned each other for 24 h. Not scoring height drops
  fixed it in our runs; a real deployment would want a narrower rule. This
  hasn't come up in the thread.
- Our race model matched the 17 Oct text's figure of one 10+ reorg about
  every 3 years at α = 1/3, once its attacker used honest shares the way
  tevador's does (2.9 years; his script then gave 2.1). The current text
  says about one per 2 years. We haven't rerun against it.

## What the latest revision might change (race model only)

Our race model has switches for both edits. Attacker's share of blocks:

| α, give-up depth | rule we ran | + 16 Oct | + 20 Oct |
|---|---|---|---|
| 1/3, 2, ignores honest shares | 0.023 | 0.037 | 0.0004 |
| 0.40, 2, uses honest shares | 0.187 | 0.208 | 0.020 |
| 0.45, 5, uses honest shares | 0.425 | 0.442 | 0.066 |

These are model numbers, not simulations, and they lean in SoP's favour: the
model has no network delay, and it doesn't yet credit the attacker for its own
tip shares, which the 20 Oct text also lets it publish. The daemon runs will
say how much survives.

## What we're doing next

We've stopped the queue of runs on the old rule. The simulator, the
independent checker and the attacker are being updated to the 20 Oct text.
Then:

- a 6-hour smoke test;
- 72-hour runs in this order: α 1/3 with give-up depth 2, α 0.45 with the
  honest-share attacker at depth 5, α 0.40 and α 0.45 at depth 2;
- after those, the α 0.45 depth-5 case with 1,000 relay nodes added, to see
  whether the result depends on the small network (a 300-node test first).

The machine runs two 12-daemon simulations at a time; a 72-hour run takes
about 6.5 hours.

Two points the 20 Oct text leaves open, which we'll have to choose for the
simulator:

- When two miners find a pool share for the same slot (same minor_version),
  does each count, or one per slot? We'll count one, first seen.
- Should a share arriving re-run the fork choice, or only a block? monerod
  only re-runs it on blocks, so that's what we'll do first, and we'll measure
  how often a share would have changed the outcome.

We'd like opinions on those, and on:

- Is α 0.45 worth the machine time, given the proposal targets 1/3?
- Which other attacker strategies are worth trying?
- Is a 12-daemon network with 2 honest miners too small to say much? The
  1,000-node run is meant to check that.
