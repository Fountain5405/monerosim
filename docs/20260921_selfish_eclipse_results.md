# Selfish-mining experiment 3, v1: eclipse composition (2026-09-21)

First run of the eclipse×selfish composition (`gamma_eclipse.yaml`: attacker
4 h/s + one eclipsed victim 3 h/s exclusive-peered to an isolated island
bridge, vs 8 h/s free honest; naive α=4/15≈0.267, α_eff=7/15≈0.467).
Run: `archived_runs/20260921_112254_gamma_eclipse` (6 sim-hours, exit 0).
Hypothesis (Nayak-style): the CONTROLLED canonical share (attacker + victim
blocks) lands on Eyal–Sirer at α_eff ≈ 0.733, because the victim's hashrate
extends the withheld chain through the island.

## Result: hypothesis REJECTED — 0.161 controlled vs 0.733 predicted

| Metric | Measured | Expected under the hypothesis |
|---|---|---|
| controlled share (attacker+victim) | **0.161** | 0.733 (ES at α_eff=0.467, γ=0) |
| attacker share alone | 0.146 | ≈ α·(…), unprofitable regime |
| attacker orphan rate | **0.651** | — |
| network orphan rate | **0.428** | — |
| reorg contest depths | up to **46**, multi-depth share 0.64 | length-1/2 |
| victim finds / canonical | 74 / ~3 | recruited, mostly canonical |

The verdict fails by 0.57 — not a near miss. The externality metrics tell
the story of WHY, and it is a genuine finding about the composition, not a
wiring bug (the 30-minute smoke first verified: victim peers ONLY with the
island, `--in-peers=0` refuses all inbound, island logs show zero
honest-network IPs, agent mirrors/pulls cleanly, MSB flags the attacker at
z=+10.2 and the victim at z=+11.2).

## The pathology: island branches cannot be resynced once they outrun honest

The victim mined 74 blocks along an island chain that topped out at height
117 while the honest chain reached 199 — a branch that fell permanently
behind and was never abandoned. The failure cycle:

1. While withholding, the island chain (attacker + victim blocks) can grow
   past what the free honest network has — that is the recruitment working.
2. When honest overtakes (it must, at α_eff < 1/2), the strategy concedes
   and the miner adopts the honest chain; the mirror pushes it to the
   island. But the island's own main chain — the old private branch plus
   victim extensions — can be LONGER than honest, so monerod at the island
   refuses the reorg: the shorter honest submission lands as an alt.
3. The stranded victims keep extending the dead branch (they are eclipsed;
   they know nothing else), the pull keeps feeding their blocks into the
   offline miner, and the miner — seeing a longer branch — flips back onto
   the dead chain. Withhold/concede oscillates around a branch the honest
   network will never accept.
4. Occasionally a long combined release still wins outright (the depth-46
   contest in the histogram is one such 40+-block override), which is why
   the attacker banked 29 canonical blocks at all — but 65% of its finds
   and nearly all victim finds died on stranded branches.

The network damage is nonetheless severe (orphan rate 0.43, reorg storms) —
as with Qubic, the attacker's loss coexists with public harm.

## What v1 establishes

- The apparatus works end-to-end: peer-pinning isolation holds for 6
  sim-hours, victim recruitment mechanics (mirror/pull) operate, and the
  analysis attributes controlled vs attacker share correctly.
- Naive continuous composition is **catastrophically unprofitable** at
  α_eff < 1/2: eclipse-recruited hashrate is only bankable while the
  composed branch stays winnable. The literature's "eclipse attacks on
  miners" assumes the attacker can reset victims (new poisoning rounds);
  our v1 has no reset, and the cost of that omission is measured above.

## v2 design (as specced after v1; implemented same day — outcome above)

Island lifecycle management — pick one or more:
1. **Recruitment cap**: pull victim blocks only while the combined branch
   stays within a cash-out margin of honest (release_lead semantics applied
   to the island view); cash the combined chain the moment the margin is
   hit, so the island never carries an unwinnable lead.
2. **Epochs**: on concession, abandon the island (victims stay stranded —
   itself an eclipse DoS on 3/15 of hashrate) and re-seek recruitment on
   the next withholding round only via a fresh short lead.
3. **Cash-on-lead**: always release the combined chain when the island
   branch is exactly k ahead of honest (never let it grow beyond k).

(1) and (3) are strategy-layer changes in `SelfishMinerAgent`; (2) needs a
per-epoch island state. v2 implemented (3) — it fixed the self-destruction
but not the recruitment itself; see the v2/v3 section for why.

## v2 (cash-on-lead, same day) and v3 (late victims): better, still rejected — and the real mechanism surfaced

**v2** (`20260921_162235_gamma_eclipse_v2`, `_island_cash_out` at lead 2):
controlled 0.161 → **0.291** (attacker alone 0.269 ≈ its honest 0.267).
The attacker stopped self-destructing, but victims still banked ~nothing
(~0.02). Network orphan rate ROSE to 0.490 — cash-outs orphan honest work,
and the leftover strandings still burn. First-pass analysis read γ=0.270
(our first nonzero!); corrected by excluding victim resolvers
(commit `a5418f17`): the true γ is **0.000** over 25 ties — the structural
result holds.

**ω-sweep under v2 semantics** (attacker 4 h/s fixed, total 15):

| Run | ω | α_eff | controlled | R_mod(α_eff) | verdict |
|---|---|---|---|---|---|
| `20260921_162236_ecl_sweep_omega0000` | 0 | 0.267 | 0.192 (attacker=controlled) | — | ES anchor PASSES (0.192 vs ES 0.220) |
| `20260921_171216_ecl_sweep_omega0200` | 0.133 | 0.400 | 0.283 (victim share 0.000) | 0.364 | PASS (band) |
| `20260921_171216_ecl_sweep_omega0300_3v` | 0.200 | 0.467 | 0.385 (victim share 0.000) | 0.485 | PASS (band) |

The anomaly that cracked the case: **victim canonical share is EXACTLY
zero in every run** while victims found 74–127 blocks each. Under v2 the
composition behaves as eclipse-DoS + plain selfish mining against a
smaller honest pool (attacker 0.385 at α=0.267 ≈ its 4/(4+8) share vs the
free honest 8 h/s) — victims removed from the honest side, never
recruited.

**v3** (victims start at 15m — after the island mirrors the chain, fixing
the height-1 first-seen race): `20260921_183612_gamma_eclipse_v3`,
controlled **0.295**, victims STILL zero canonical. The honest-strategy
control (`20260921_..._honest_baseline_v3`, attacker releases
immediately) shows the same zero — proving it is plumbing, not strategy.

**The v3 mechanism (from the run's own data):** the island chain tracked
the full 176-block chain perfectly (mirror ✓, pull kept the miner synced ✓
— the victim found 176 blocks, heights 1..176), yet no victim block is on
the island's main chain at release time. monerod's first-seen rule bites
at every level: when the mirror's copy of the attacker's block and the
victim's own block land at the same island height, the island keeps
whichever it saw first; the victim's daemon — which saw its OWN block
first, locally — keeps extending the losing fork on its side of the P2P
link. Those alt-branch blocks are invisible to `get_block` (main chain
only), so the pull never sees them, and they die. The victim is
effectively solo-mining against its own reflection of the attacker's
chain.

## What v1–v3 establish (negative results with mechanisms)

1. Peer-pinned eclipse isolation is solid (6 h, zero leaks) and the
   orchestrator/analysis plumbing is sound (γ metric needed one fix).
2. Recruitment via naive mirror/pull loses to monerod's first-seen
   semantics at the island: **hashrate capture requires the victim's
   blocks to win first-seen at the island**, which the attacker cannot
   arrange while also mining the same heights itself.
3. Even so, eclipsing honest miners is immediately valuable to a selfish
   attacker as pure DoS: removing ω=0.2 of hashrate from the honest side
   moved the attacker's canonical share from 0.192 (ω=0 anchor) to 0.385 —
   its effective α vs the free honest pool rose from 0.267 to 0.333.

## v4 design directions

- **Rest windows**: alternate phases — attacker stops mining (and mirrors
  only the committed prefix) so victims' extensions win first-seen at the
  island uncontested, then cashes the victim-extended branch; the victim
  hashrate is recruited in pulses rather than continuously.
- **Pull alt-chains**: monerod exposes no RPC for alternative blocks; a
  sim-only patch (like --sim-relay-alt-blocks) could expose them, making
  the pull whole — but that changes what a real attacker could observe,
  so prefer the strategy-level fix first.
- **Non-mining observer island**: keep the attacker's miner OFF the
  island's competing heights entirely (island carries only committed
  blocks + victim extensions).

## Caveats (v1–v3)

- Single run per configuration, `native_preemption: true` (σ≈0.05) — the
  headline failures are 3–11σ, not noise; the ω-sweep's PASS points sit
  within the band partly because the band is wide.
- The ω-sweep points ran under v2 victim-start semantics (t=0); under v3
  (15m start) the curve should be re-run once recruitment itself works
  (v4) — the v2-semantics points remain valid as eclipse-DoS
  characterizations.
- One victim topology per point except omega_0300_3v (3×1 h/s); island
  count fixed at one.

## v4–v10 (2026-09-21/22): five real bugs, recruitment finally works, release side next

The majority-regime validation loop (run → instrument → one probe per
hypothesis) found five genuine defects, each independently confirmed by
local two-daemon repro or run forensics:

1. **v4 — extension-only feeds** introduced while fixing first-seen
   collisions; correct idea, but (see 3) built on a misread height.
2. **v5 — divergence-aware pull**: v4's rule skipped the FIRST block of
   every victim-led branch (island T+1 vs the miner's own T+1 = "stale"),
   orphaning the branch at birth. Ported the honest forwarder's
   reorg-aware pattern to the island feed.
3. **v8 — submit_block status checking + offline islands/victims**: a
   local repro proved monerod answers rejected submits with HTTP 200 and
   the reason in `result.status` ("BUSY" while unsynchronized) — our
   client saw success. Every isolated-ONLINE daemon was a silent black
   hole. Islands and victims now run `--offline` (synchronized
   immediately, accepts submits — the attacker's own miner proved this
   all along); `submit_block` raises on any non-OK status.
4. **v8b — the count/index off-by-one**: monerod `get_info` height is a
   COUNT (top+1), block indexes are 0-based — all three feeds treated it
   as a top index. The mirror started one block past what the island
   needed (every submit parent-unknown → orphaned submits still answer
   OK), so **the mirror had never successfully fed any island in any
   version** (masked because victims built the island chain themselves
   over P2P). Convention now explicit at all three sites.
5. **v8c — feeds must not skip undelivered blocks**: the relay's push
   watermark advanced past blocks that failed while the victim daemon was
   absent (start_time 15m) — the victim received zero blocks forever.
   Transport failures now hold the watermark; daemon-side rejections
   (processed) still advance.

**v10 state (`20260921_*_gamma_eclipse_majority_v10`): recruitment
works.** The victim receives the fed chain (75 submits early), mines on
it (66+ finds in the first hour, properly extending the attacker's
chain) — the island→victim→island loop is closed and correct for the
first time. The composition still FAILs the majority verdict, but the
failure INVERTED: the attacker banks 0.000 (orphan rate 1.000) while the
victim mines happily — the residual is in the strategy/release side
against the now-synced island chain (withholding decisions and cash-outs
reason about a priv_height that now includes victim blocks; releases of
long combined branches vs the honest network need timeline forensics —
62 ties recorded). Next session starts there, with every feed verified.
- One victim, one island, α_eff 0.467; the pathology should be α_eff-driven
  (worse as α_eff → 1/2 from below), which v2 should confirm by sweep.


## v11 (2026-09-22): releases win — attacker 0.000 -> 0.463, one scoped gap left

`20260921_*_gamma_eclipse_majority_v11`. Forensics on v10: the island's
early burst resurrected the miner's STALE PRIVATE BRANCH via the pull, so
the miner's chain diverged from the public chain far below the strategy's
fork — every cash-out since submitted blocks whose parents the network
never had, and monerod files orphaned submits silently with status OK
(436 cash-outs of a 100-block branch: zero alt-adds, zero reorgs; a
locally reproduced 20-block sequential submit adopts instantly, proving
the mechanism fine when connected).

v11 fixes: `_island_cash_out` releases from the hash-verified common
ancestor with the bridge (walking down from min(pub, priv)) instead of
the strategy's fork, and commits `fork` only on verified adoption (the
bridge's height actually reaching ours), leaving the release watermark
intact to retry a non-adopted range.

Result: attacker canonical share **0.463** (from 0.000), attacker orphan
rate **0.026** (from 1.000) — the composition publishes and banks. Still
FAIL (0.463 < 0.5 majority), and controlled == attacker exactly: the
victim's 199 finds bank ZERO. Scope of the remaining bug: the miner never
adopts victim-led branches (the divergence-aware pull submits them into
the miner's alt-tree, but the switch to the longer branch is not
happening; the victim's 6 h/s burns against the mirror's flow — network
orphan rate 0.589). Next probe: the miner's alt-tree/adopt behavior
during a victim burst, one run, then the majority verdict should close.
