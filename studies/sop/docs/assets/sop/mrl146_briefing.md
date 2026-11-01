# MRL #146 Briefing

Share-or-Perish (monero-project/research-lab #146): Tables 3–5, the
`version_minor` slot rule, w = 16, k = 3, d = 5 s. It runs in monerod
v0.18.5.1 under the Shadow network simulator, with 12 daemons, real RandomX
and 120 s blocks.

Every fork-choice decision is logged and re-derived by an independent
checker: 43,949 decisions, 0 mismatches.

The attacker withholds its blocks. It reveals once its branch holds 48 work
objects and outweighs the honest chain, and gives up when honest leads by
d blocks.

> **Update 2026-10-16.** tevador revised the issue on 2026-10-15 and
> answered albinjm's questions in the thread the same day. The revision
> settles both of our questions below and the `version_minor` point. The
> simulator now follows the revised rules, apart from one edge case that the
> next build fixes (see Limits). Re-runs under them are in progress
> (results expected 2026-10-18). Unless marked otherwise, the numbers here
> come from campaign 7, which ran the earlier text.

## What the revision changed

| Point | Earlier text | Revised (2026-10-15) | Our check |
|---|---|---|---|
| `n_f` | Formal definition counts the alt chain only | <code>n<sub>f</sub> = max(n<sub>main</sub>(h<sub>f</sub>), n<sub>alt</sub>(h<sub>f</sub>))</code>: objective once either chain holds 48 objects past the fork | This is the "either" rule we had added. Replaying campaign 7's 5,325 switches under it, 0 would reverse; under the alt-only rule, 2,220 of 5,340 would |
| `main_seen` | "the main chain block of the same height", which changes when a node switches | Seen time of the first block at that height to join the node's main chain. Later switches don't change it. If no block there has been main, `main_seen = block_seen` | Hand-worked honest race, blocks 4 s apart: under the old reference, both directions say SWITCH. Under the fixed one, SWITCH (228 vs 76) one way and KEEP (76 vs 228) the other. New-build smoke: 1,410 decisions, 0 oracle mismatches, 0 that would switch straight back |
| "Seen" | Not defined | Needs valid PoW and a known parent. Out-of-order blocks aren't seen until they have both | The simulator drops a block's receive time if the block is orphaned or fails verification. A gossiped share is kept only if its parent is known, and its PoW is checked when weights are computed |
| `version_minor` | Equal to the workshare count | `version_major` + the count. Shares are numbered from `version_major` | An unmodified v0.18 node accepted a SoP block with 9 workshares. No block was rejected on the vote check |

The `version_minor` change keeps the stock check `version_minor >= version_major`. In tevador's words, it "allows SoP to be deployed as a soft fork without removing the consensus rule".

## The author's answers to albinjm (thread, 2026-10-15)

1. A shorter chain with more work objects winning is intended. Such a
   chain "is much more likely to belong to the hashrate-majority partition".
2. (Not applicable.)
3. Some honest shares will be late, and the chain still benefits from them
   later. Shares lost to duplicate `version_minor` values are "unavoidable".
4. The weight becomes objective three blocks after the fork point. With lost
   shares it can be slightly more.
5. Lateness is judged on both chains. "The 'original' main block can never
   be judged late even after a chain switch." The simulator does the same.
6. tevador's simulation used α = 1/3.

## Two questions we had (both now settled)

### Q1. Which `n_f` is intended?

The earlier text gave two rules that are not the same:

> **Formal:** `n_f` counts work objects in the alt chain "not contained in
> the main chain".

> **Prose:** the lateness factors apply only if "the two chains differ by
> fewer than k*w work objects".

Campaign 7 implemented the formal reading. **Settled:** the revision puts
the prose reading into the definition, as `max` of the two chains.

### Q2. What happens to blocks displaced by a reorg?

After a reorg, stock monerod pushes every displaced block back through the
fork choice (`blockchain.cpp:1163–1180`). Under cumulative difficulty that
check can never win. With SoP weights it can, if the weights depend on
which chain the node is on. Two things made them depend on it: the alt-only
`n_f`, and lateness timed against whichever block was main at the time.

**Settled:** the revision removes both. `n_f` is symmetric, and
`main_seen` is fixed per height.

### Why it mattered: one pair, both directions say SWITCH

Under the earlier text, here is a case where both directions say SWITCH.
An honest block **H** has 11 workshares, all gossiped early. Against it are
7 attacker blocks **A1–A7**, each with 8 workshares that were never gossiped.

| Node is on | Alt branch | Regime | Comparison | Result |
|---|---|---|---|---|
| A1–A7 | H (12 objects) | subjective | 912 vs 532 | **SWITCH to H** |
| H | A1–A7 (63 objects) | objective | 63 vs 12 objects | **SWITCH to A** |

We saw this live in a log. The first line below was followed 1 ms later by
the second:

```
alt 4234/6 vs main 3796/4 -> SWITCH
alt 1022/1 vs main 438/6 -> SWITCH
```

Under the revised `n_f`, the attacker's 63 objects make the pair objective
from both sides, so it doesn't flip.

Separately, the simulator judges a displaced branch again only when a new
block extends it. Reveals can still be reversed that way:

- In the 240 h runs, 7 of 367 reveals (2 %) were reversed within 3.3 s.
- Each was reversed by one honest block that made the honest branch heavier.
- In 3 of the 7, the honest branch was still the shorter one.

That is albinjm's question 1, which the author says is intended.

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

Attacker revenue share by α (campaign 7, earlier text):

| α | Stock | SoP |
|---|---|---|
| 0.33 | 0.29–0.31 | 0.015–0.025 (13 × 240 h; give-up depth 2, 3, 5) |
| 0.40 | 0.38–0.46 | ≈ 0.14 (nine 6 h runs, all below 0.29) |

At α = 0.40, the Eyal–Sirer attacker earns 0.000 and the lead-2 attacker
earns 0.015 and 0.000 (n = 2). This matches albinjm's result that no
withholding strategy earns its fair share at α ≤ 0.33. We claim it only for
α ≤ 0.40. Re-runs under the revised text are in progress.

### `version_minor` and the soft-fork claim (resolved)

Under the earlier rule, `version_minor` equalled the workshare count. v0.18
uses that field as the hard-fork vote and requires it to be at least 16
(`hardfork.cpp:109–113`). Honest blocks carry about 15 workshares on
average, with a median of 11. An unmodified monerod on the same chain
rejected every SoP block it was sent: 10 of 10, each with at most 7
workshares. It logged "has old version: 16, current: 16"
(`blockchain.cpp:4079`) and dropped the peer.

The revised rule numbers shares from `version_major`. Under it, the same
setup accepted a SoP block with 9 workshares, and no block failed the vote
check (2026-10-15).

### Peer bans (stock P2P scoring)

SoP nodes legitimately switch to a branch with fewer blocks. Stock monerod
scores a peer whose reported height drops (`hit_score`), and the fail score
never decays. So honest nodes ban each other for 24 h.

With a depth-5 attacker:

- Bans happened in 3 of 5 runs: 48, 57 and 10 bans.
- One relay was stuck on a stale branch for 13.7 simulated hours.
- Replaying the fail score from the logs predicts all 67 bans.
- Not scoring height drops gave 0 bans in three 240 h re-runs.

That fix is blunt; a deployment would want a narrower rule. The revision
doesn't touch this, and the thread hasn't discussed it.

## Limits

- 12 daemons, two honest miners and fast propagation. Realistic delay and
  many pools are not tested. A 40-daemon network is running now.
- One attacker design. It is not tevador's T5 attacker, which gives up when
  it falls a set number of work objects behind and uses honest workshares in
  its first private block.
- α = 0.40 rests on 6 h runs.
- α = 0.45 is not established. Three 6 h runs gave 0.22, 0.47 and 0.43, too
  noisy to tell apart from α itself; a race model gives 0.36.
- Three seeds. Parts of monerod aren't deterministic under Shadow, so a
  seed doesn't reproduce a run: each run is an independent draw.
- The ban fix is untested at scale.
- So far, the revised rules have been run only in 6 h runs and one
  stock-node check.
- One edge case remains in the current build. A node that started on the
  fork's last common block judges that fork subjectively; the revised text
  says objectively, because the node may have missed the gossip of shares
  mined on that block before it came online. It hit 4 decisions in the new
  build's runs so far and changed none of their outcomes. The next build
  fixes it.

---

The campaign-7 numbers are from its results write-up (sections 2–9). The
2026-10-15 checks are from campaign 8; a write-up will follow the re-runs.
Quotes from the thread are from tevador's comment of 2026-10-15. Code
references are to monero v0.18.5.1. An animated walk-through of the
displaced-block problem under the earlier text is in
`fork_choice_loop.html`, next to this file.
