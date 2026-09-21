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

## v2 design (next increment)

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
per-epoch island state. All measurable with the existing analysis.

## Caveats

- Single run, `native_preemption: true` (σ≈0.05) — the failure is ~11σ, not
  noise.
- One victim, one island, α_eff 0.467; the pathology should be α_eff-driven
  (worse as α_eff → 1/2 from below), which v2 should confirm by sweep.
