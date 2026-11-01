# DRAFT comment for monero-project/research-lab#146 (not posted)

Notes for the owner, not part of the comment:
- Section 6 is held back (replicates pending). Delete it or keep it out of the post.
- `[repo link]` is for you to fill or drop; the repository name would link the post to your GitHub identity.
- Every number below is in `docs/20261007_sop_campaign7_results.md` (section named in brackets, remove the brackets before posting).
- Nothing here names this machine or any account.

---

I ran Share-or-Perish as written in a network simulator with real monerod code and real fork choice, and looked at what a stubborn attacker earns and what else breaks. Summary: the incentive result agrees with the other simulations in this thread. Three implementation-level things came up that I did not see discussed: the `version_minor` rule makes this a hard fork, monerod's peer scoring bans honest peers under SoP's fork choice, and the spec does not say what to do with blocks displaced by a reorg.

**Setup.** monerod v0.18.5.1 with Tables 3–5, `version_minor` slot rule, w = 16, k = 3, d = 5 s, in Shadow (12 daemons: two honest miners, two relays, six seeds, the attacker's miner and bridge; real RandomX, 120 s blocks, LWMA from a preloaded chain). Every fork-choice decision is logged and re-derived by an independent checker (43,949 decisions, 0 mismatches). The attacker withholds, reveals once its branch holds 48 work objects and outweighs the honest chain, and gives up when the honest chain leads by d blocks; it embeds its own workshares and never an honest one. [§2]

**1. Profit.** Attacker revenue share, canonical chain:

| α | stock | SoP |
|---|---|---|
| 0.33 | 0.29–0.31 (3 × 240 h) | 0.015–0.025 (13 × 240 h, give-up depths 2, 3, 5) |
| 0.40 | 0.38–0.46 | about 0.14 (nine 6 h draws, all below 0.29) |
| 0.45 | about 0.50 | 0.22, 0.47, 0.43 (three 6 h draws; too noisy to tell from α; a race model gives 0.36) |

Eyal–Sirer (ES) and lead-2 attackers at α = 0.40 earn 0.000 and 0.015 / 0.000 (n = 2). This agrees with albinjm's finding that no withholding strategy earns its fair share at α ≤ 0.33. I only claim it for α ≤ 0.40. [§3, §8]

**2. The `version_minor` rule vs "soft-forking".** [REVISED 2026-10-14: tested with an unmodified monerod; it rejected 10 of 10 SoP blocks ("has old version: 16, current: 16", blockchain.cpp:4079). The "has old version" observation below was misattributed; see results doc §7 item 2.] The issue requires `version_minor` to equal the number of workshares in the block. In v0.18 `version_minor` is the hard-fork vote, and `HardFork::do_check` requires it to be at least the current fork version (16) (`hardfork.cpp:109–113`). A block with fewer than 16 workshares therefore looks like it has an old version to an unupgraded node. I saw this directly: an unmodified bridge rejected SoP blocks with "has old version" (`blockchain.cpp:1889`). Honest blocks here carry about 15 workshares on average, median 11. So most SoP blocks would be rejected by nodes that have not upgraded, and the "simplest backwards-compatible solution" for the share data does not extend to this field. Another field or an offset encoding would avoid it. [§7 item 2]

**3. Monero's peer scoring bans honest nodes under SoP.** SoP nodes legitimately switch to a branch with fewer blocks and more weight. Stock monerod calls `hit_score(context, 1)` when a peer reports a lower height than before (three sites in `cryptonote_protocol_handler.inl`); the second hit drops the connection with fail score 5, and a host whose fail score passes 10 is blocked for 24 h. The score never decays. With a depth-5 stubborn attacker, honest nodes, relays and seeds banned each other in 3 of 5 runs (48, 57 and 10 bans), and one relay was stuck on a stale branch for 13.7 simulated hours. Replaying the fail score from the logs predicts all 67 bans, on the same host within 5 ms. Not scoring height drops on SoP nodes gave 0 bans in three 240 h re-runs. That fix is blunt (it also stops penalising peers that misreport their height); a deployment would want a narrower rule. [§6]

**4. Displaced blocks and a pairwise rule that can disagree with itself.** The spec does not say how blocks displaced by a reorg are judged again. monerod re-runs the fork choice on every displaced block (`blockchain.cpp:1163–1180`); under cumulative difficulty that can never switch back, but with SoP weights it can. Two reasons:
- `n_f` counts work objects in the alt chain only, so which branch is "alt" decides whether the comparison is subjective or objective.
- Lateness is timed against whichever block is main at each height.

So the same two branches can give SWITCH in both directions. A small example: an honest block (11 shares, all gossiped) against 7 attacker blocks (8 never-gossiped shares each): with the honest block as alt the comparison is subjective (912 against 532) and switches to the honest block; with the attacker's blocks as alt it is objective (63 objects against 12) and switches to the attacker's. Both directions say SWITCH. In my runs, re-judging each displaced block as monerod does switched away from the attacker's branch within a millisecond, by an accident of monerod's re-insertion that I would not read as a statement about the spec. I therefore judge a displaced branch again only when a new block extends it.

Two questions for the spec:
- The text defines `n_f` as alt-chain objects "not contained in the main chain", but also says the factors apply "only if ... the two chains differ by fewer than `k*w` work objects". These are different rules. Which is intended?
- What should a node do with displaced blocks?

Even with my choice, 7 of 367 reveals (2 %) in the 240 h runs were reversed within 3.3 s by a single honest block that made the honest branch heavier. In three of the seven the honest branch was still shorter than the attacker's. That is albinjm's question 1, seen at near-zero network delay. [§4.2, §7 item 1]

**5. [WITHDRAWN 2026-10-14: tevador's 2025-09-28 table already covers this; do not post.] 10+ block reorgs depend on how long the attacker holds on.** "About 1 per 3 years" is the rate for tevador's T5 attacker, which gives up when honest leads by more than 5 work objects (under half a block). It is one attacker's rate. A race model I validated against the simulator (share, orphan rates and race shapes agree; reorg depth is within roughly 5–10 %) gives, at α = 0.33 for an attacker that reveals at the first chance and keeps mining up to 1, 2 or 4 blocks behind (give-up depth 2, 3, 5), one 10+ reorg per 2.9, 1.5 and 0.41 years. The simulator saw two in 48.7 days at depth 5, one of them 8 s after a ban wave (item 3). At α = 0.40 and 0.45 the model gives tens to hundreds per year. These rates are model output, at near-zero network delay. [§5]

**Limits.** 12 daemons and two honest miners, fast propagation, one attacker design (not tevador's T5 attacker, which gives up in objects and uses honest workshares in its first private block). The α = 0.40 and 0.45 rows are 6 h runs. Only three seeds were used, and I did not verify that a seed fixes network placement. Realistic delay, many pools and the ban fix at scale are not tested. [§9]

Code, patches and run records: [repo link]

---

## HELD BACK (section 6): do not post until replicated

**6. Success frequency.** The issue estimates that the attacker avoids the lateness penalties "on average once per 10 days of selfish mining" at α = 0.33. In the simulator, at give-up depth 2, an attacker reveals a heavier branch about 3 times per simulated day (2.98 per day in the simulator, 3.13 in the race model), each with at least 48 attacker objects, and with a mean reorg depth of 2.3 blocks, so the "3-block reorg" is about right and the frequency is about 30 times higher. The difference comes from what the fork choice can count. It sees only workshares that are inside blocks. Honest workshares found but not yet in a block count for nothing until the next honest block carries them. At each of 87 reveals the honest node had a median of 40 such shares (an estimate; the log has no share ids), against an attacker lead of a median 8 objects; counting them would have blocked all 87. In the race model, counting them removes 99.6 % of reveals. So the arithmetic behind "once per 10 days" is for a race against all honest work, and the chain only measures committed work. [§4.1]
