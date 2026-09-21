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
- One victim, one island, α_eff 0.467; the pathology should be α_eff-driven
  (worse as α_eff → 1/2 from below), which v2 should confirm by sweep.
