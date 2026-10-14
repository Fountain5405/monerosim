# MRL #146 Briefing

Share-or-Perish (monero-project/research-lab #146), run as written: Tables
3–5, the `version_minor` slot rule, w = 16, k = 3, d = 5 s. It runs in
monerod v0.18.5.1 under the Shadow network simulator, with 12 daemons, real
RandomX and 120 s blocks.

Every fork-choice decision is logged and re-derived by an independent
checker: 43,949 decisions, 0 mismatches.

The attacker withholds its blocks. It reveals once its branch holds 48 work
objects and outweighs the honest chain, and gives up when honest leads by
d blocks.

## Two questions about the spec

Only the author can answer these.

### Q1. Which `n_f` is intended?

The issue gives two rules that are not the same:

> **Formal:** `n_f` counts work objects in the alt chain "not contained in
> the main chain".

> **Prose:** the lateness factors apply only if "the two chains differ by
> fewer than k*w work objects".

- **Formal reading:** which branch is the alt one decides whether a
  comparison is subjective (receive times count) or objective.
- **Prose reading:** a pair is objective as soon as either side holds
  k·w = 48 objects.

We implemented the formal reading.

### Q2. What happens to blocks displaced by a reorg?

The spec doesn't say. After a reorg, stock monerod pushes every displaced
block back through the fork choice (`blockchain.cpp:1163–1180`). Under
cumulative difficulty that check can never win. With SoP weights it can.

### Why it matters: one pair, both directions say SWITCH

An honest block **H** has 11 workshares, all gossiped early. Against it are
7 attacker blocks **A1–A7**, each with 8 workshares that were never gossiped.

| Node is on | Alt branch | Regime | Comparison | Result |
|---|---|---|---|---|
| A1–A7 | H (12 objects) | subjective | 912 vs 532 | **SWITCH to H** |
| H | A1–A7 (63 objects) | objective | 63 vs 12 objects | **SWITCH to A** |

The answer depends on which branch the node is already on, for two reasons:

- `n_f` counts the alt side only.
- Lateness is timed against whichever block is main at each height.

We saw this live in a log. The first line below was followed 1 ms later by
the second:

```
alt 4234/6 vs main 3796/4 -> SWITCH
alt 1022/1 vs main 438/6 -> SWITCH
```

Under the prose reading, the pair is objective in both directions once the
attacker's side holds 48 objects, and the flip can't happen.

Options we see, none chosen:

- Judge each pair symmetrically (the prose reading of `n_f`).
- Judge a displaced branch again only when a new block extends it (our
  simulator's default).
- Say in the spec that a reveal that won is final until the losing branch is
  extended.

Our default still lets reveals be reversed:

- In the 240 h runs, 7 of 367 reveals (2 %) were reversed within 3.3 s.
- Each was reversed by one honest block that made the honest branch heavier.
- In 3 of the 7, the honest branch was still the shorter one.

This is albinjm's question 1, seen at near-zero network delay.

> **Numbers not to quote.** In runs where monerod re-checked displaced
> blocks, the attacker's share came out near zero. That is an accident of
> monerod's code, and it says nothing about SoP:
>
> 1. The switch back runs inside the first switch.
> 2. The duplicate check (`:2073`) refuses to store the attacker's blocks
>    again.
> 3. The outer switch deletes them (`:1182–1186`).

## What we found

### Profit (agrees with the thread)

Attacker revenue share by α:

| α | Stock | SoP |
|---|---|---|
| 0.33 | 0.29–0.31 | 0.015–0.025 (13 × 240 h; give-up depth 2, 3, 5) |
| 0.40 | 0.38–0.46 | ≈ 0.14 (nine 6 h runs, all below 0.29) |

At α = 0.40, the Eyal–Sirer attacker earns 0.000 and the lead-2 attacker
earns 0.015 and 0.000 (n = 2). This matches albinjm's result that no
withholding strategy earns its fair share at α ≤ 0.33. We claim it only for
α ≤ 0.40.

### The `version_minor` rule vs the soft-fork claim

The issue calls SoP "a soft-forking proposal", and puts the workshare count
in `version_minor`. v0.18 uses that field as the hard-fork vote and requires
it to be at least 16 (`hardfork.cpp:109–113`). Honest blocks carry about 15
workshares on average, median 11.

We tested it: an unmodified monerod on the same chain rejected every SoP
block it was sent (10 of 10, each with at most 7 workshares) with "has old
version: 16, current: 16" (`blockchain.cpp:4079`), and dropped the peer.
The major version matched, so the vote is what failed. An offset (for
example 16 + the share count) or another field would avoid it.

### Peer bans (stock P2P scoring)

SoP nodes legitimately switch to a branch with fewer blocks. Stock monerod
scores a peer whose reported height drops (`hit_score`), and the fail score
never decays. So honest nodes ban each other for 24 h.

With a depth-5 attacker:

- Bans happened in 3 of 5 runs: 48, 57 and 10 bans.
- One relay was stuck on a stale branch for 13.7 simulated hours.
- Replaying the fail score from the logs predicts all 67 bans.
- Not scoring height drops gave 0 bans in three 240 h re-runs.

That fix is blunt; a deployment would want a narrower rule.

## Limits

- 12 daemons, two honest miners and fast propagation. Realistic delay and
  many pools are not tested.
- One attacker design. It is not tevador's T5 attacker, which gives up when
  it falls a set number of work objects behind and uses honest workshares in
  its first private block.
- α = 0.40 rests on 6 h runs.
- α = 0.45 is not established. Three 6 h runs gave 0.22, 0.47 and 0.43, too
  noisy to tell apart from α itself; a race model gives 0.36.
- Three seeds, and we haven't verified that a seed fixes network placement.
- The ban fix is untested at scale.

---

Every number is from the campaign-7 results write-up (sections 2–9). Code
references are to monero v0.18.5.1. An animated walk-through of the
displaced-block problem is in `fork_choice_loop.html`, next to this file.
